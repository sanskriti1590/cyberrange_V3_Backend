import datetime
import os
import json
import jsonschema

from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from rest_framework import serializers
from notification_management.utils import send_notification
from ctf_management.utils import validate_file_size

from core.utils import generate_random_string, API_URL, is_email_valid
from . utils import convert_score, create_scenario_game
from database_management.pymongo_client import (
    user_collection,
    scenario_category_collection,
    scenario_collection,
    scenario_active_game_collection,
    scenario_player_arsenal_collection,
    scenario_invitation_collection,
    user_profile_collection,
    scenario_archive_game_collection,
    notification_collection,
    resource_credentials_collection
)
from cloud_management.utils import (
    create_cloud_network,
    create_cloud_router,
    create_cloud_instance,
    connect_router_to_public_network,
    connect_router_to_private_network,
    disconnect_router_from_private_network,
    get_cloud_subnet,
    get_cloud_instance,
    get_instance_images,
    get_instance_flavors,
    get_instance_console,
    get_flavor_detail,
    get_instance_private_ip,
    get_cloud_router,
    delete_cloud_instance,
    delete_cloud_router,
    delete_cloud_network
)

from .utils import send_invitation_by_email


class ScenarioCategorySerializer(serializers.Serializer):

    def get(self):
        scenarios = list(scenario_category_collection.find({}, {'_id': 0}))

        for category in scenarios:
            scenario_games_length = scenario_collection.count_documents({"scenario_category_id": category['scenario_category_id'], "scenario_is_approved": True})
            category["count"] = scenario_games_length

        return sorted(scenarios, key=lambda x: x["count"], reverse=True)



class ScenarioCreateSerializer(serializers.Serializer):
    scenario_name = serializers.CharField(max_length=500, required=True)
    scenario_category_id = serializers.ChoiceField(choices=())
    scenario_assigned_severity = serializers.ChoiceField(choices=('Very Easy', 'Easy', 'Medium', 'Hard', 'Very Hard'), required=True, write_only=True)
    scenario_score = serializers.IntegerField(max_value=100, min_value=10, required=True)
    scenario_time = serializers.IntegerField(max_value=10, min_value=1, required=True)
    scenario_description = serializers.CharField(min_length=50, max_length=5000, required=True)
    
    scenario_external_references = serializers.ListField(
        child=serializers.URLField(max_length=500, allow_blank=False),
        required=False
    )
    scenario_thumbnail = serializers.FileField(required=False, validators=[validate_file_size])
    scenario_documents = serializers.ListField(
        child=serializers.FileField(validators=[validate_file_size]),
        allow_empty=False
    )
    
    scenario_red_team_flags = serializers.CharField(max_length=500, write_only = True, default="")
    scenario_blue_team_flags = serializers.CharField(max_length=500,  write_only = True, default="")
    scenario_purple_team_flags = serializers.CharField(max_length=500, write_only = True, default="")
    scenario_yellow_team_flags = serializers.CharField(max_length=500, write_only = True, default="")
    
    scenario_tools_technologies = serializers.CharField(min_length=100, max_length=5000, required=False)
    scenario_prerequisites = serializers.CharField(min_length=100, max_length=5000, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scenario_category_id'].choices = self.get_scenario_category_choices()

    def get_scenario_category_choices(self):
        categories = scenario_category_collection.find({}, {'scenario_category_id': 1, 'scenario_category_name': 1})
        return [(category['scenario_category_id'], category['scenario_category_name']) for category in categories]
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data    
    
    def validate(self, data):
        data['user'] = self.context['request'].user

        if data['user'].get('user_role') != "WHITE TEAM":
            raise serializers.ValidationError("You are not allowed to perform this operation. Only white team members can create a scenario.")

        # Check that name contains only alphabets, digits, and spaces
        if not data['scenario_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Scenario Name can only contain alphabets, digits, and spaces.")
        
        if scenario_collection.find_one({'scenario_name': data['scenario_name']}):
            raise serializers.ValidationError("Scenario Name already exists, it must be unique. Try another name.")
        
        if data.get('scenario_thumbnail'):
            if not data['scenario_thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png')):
                raise serializers.ValidationError("Unsupported file format. Only jpeg, jpg, and png are allowed for Scenario Thumbnail.")
            
        for scenario_document in data['scenario_documents']:
            if not scenario_document.name.lower().endswith(('pdf')):
                raise serializers.ValidationError("Unsupported file format. Only PDF is allowed for Scenario Documents.")
                    
        return data
    

    def create(self, validated_data):
        # For generating unique random Scenario Game Id
        scenario_id = generate_random_string('scenario_id', length=15)
        current_date_time = datetime.datetime.now()
        current_timestamp = str(current_date_time.timestamp()).split(".")[0]

        # For document
        document_url_list = list()
        document_files = validated_data['scenario_documents']
        
        counter = 0
        for document_file in document_files:
            document_file_name, document_file_extension = os.path.splitext(document_file.name)
            
            counter += 1
            new_file_name = f"{scenario_id}_document_{current_timestamp}_{counter}{document_file_extension.lower()}"
            # Store the file in the specified directory
            with open(f"static/documents/scenario_game_documents/{new_file_name}", 'wb+') as destination:
                for chunk in document_file.chunks():
                    destination.write(chunk)
            document_url = f'{API_URL}/static/documents/scenario_game_documents/{new_file_name}'
            document_url_list.append(document_url)

        # For Thumbnail
        if validated_data.get('scenario_thumbnail'):
            # Get file name and extension
            thumbnail_file = validated_data.pop('scenario_thumbnail', None)
            thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)

            # Rename the file
            thumbnail_file_name = f"{scenario_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"
            # Store the file in the specified directory
            with open(f"static/images/scenario_game_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                for chunk in thumbnail_file.chunks():
                    destination.write(chunk)

            thumbnail_url = f'{API_URL}/static/images/scenario_game_thumbnails/{thumbnail_file_name}'
        else:
            thumbnail_url = f'{API_URL}/static/images/scenario_game_thumbnails/default.jpg'

        scenario = {
            'scenario_id' : scenario_id,
            'scenario_name' : validated_data['scenario_name'],
            'scenario_category_id' : validated_data['scenario_category_id'],
            'scenario_assigned_severity' : validated_data['scenario_assigned_severity'],
            'scenario_score' : validated_data['scenario_score'],
            'scenario_time' : validated_data['scenario_time'],
            'scenario_description' : validated_data['scenario_description'],
            'scenario_external_references': validated_data.get('scenario_external_references', []),
            'scenario_thumbnail' : thumbnail_url,
            'scenario_documents' : document_url_list,
            'scenario_rated_severity' : {
                "very_easy" : 0,
                "easy" : 0,
                "medium" : 0,
                "hard" : 0,
                "very_hard" : 0
            },
            'scenario_creator_id' : validated_data['user'].get('user_id'),
            'scenario_players_count' : 0,
            'scenario_for_premium_user' : False,
            'scenario_rating_count' : 0,
            'scenario_played_by' : [],
            'scenario_is_approved' : False,
            'scenario_is_prepared' : False,
            'scenario_flags': {
                'Red Team': validated_data['scenario_red_team_flags'].split(),
                'Blue Team': validated_data['scenario_blue_team_flags'].split(),
                'Purple Team': validated_data['scenario_purple_team_flags'].split(),
                'Yellow Team': validated_data['scenario_yellow_team_flags'].split(),
            },
            'scenario_tools_technologies' : validated_data.get('scenario_tools_technologies', ""),
            'scenario_prerequisites' : validated_data.get('scenario_prerequisites', ""),
            'scenario_is_challenge' : False,
            'scenario_created_at' : current_date_time,
            'scenario_updated_at' : current_date_time,
        }
        scenario_collection.insert_one(scenario)

        return scenario
    

class ScenarioGameDraftSerializer(serializers.Serializer):
    def get(self, user_id):        
        user = user_collection.find_one({'user_id': user_id}, {'_id': 0, 'password': 0})
        if not user:
            return {
                "errors": {
                    "non_field_errors": ["Invalid User Id"]
                }
            }
        
        scenario_drafts = scenario_collection.find({
            'scenario_creator_id': user_id,
            'scenario_is_prepared': False
        }, {'_id': 0})

        return list(scenario_drafts)
    

class ScenarioInfraCreateSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(max_length=50, required=True)
    scenario_infra = serializers.JSONField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data    

    def validate_name(self, name):
        # Check that name contains only alphabets, digits, and spaces
        if not name.isalnum():
            raise serializers.ValidationError(f"Special characters are not allowed in names: {name}")    
        return name

    def validate_unique_network_names(self, networks):
        network_names = [self.validate_name(network["network_name"]) for network in networks]
        duplicates = set(name for name in network_names if network_names.count(name) > 1)
        if duplicates:
            raise serializers.ValidationError(f"Duplicate network names are not allowed: {duplicates}")

    def validate_unique_router_names(self, routers):
        router_names = [self.validate_name(router["router_name"]) for router in routers]
        duplicates = set(name for name in router_names if router_names.count(name) > 1)
        if duplicates:
            raise serializers.ValidationError(f"Duplicate router names are not allowed: {duplicates}")
        
    def validate_unique_instance_names(self, instances):
        instance_names = [self.validate_name(instance["instance_name"]) for instance in instances]
        duplicates = set(name for name in instance_names if instance_names.count(name) > 1)
        if duplicates:
            raise serializers.ValidationError(f"Duplicate instance names are not allowed: {duplicates}")
        
    def validate_router_internal_interfaces(self, networks, routers):
        network_names = set(network["network_name"] for network in networks)
        for router in routers:
            internal_interfaces = set(router["internal_interfaces"])
            invalid_interfaces = internal_interfaces - network_names
            if invalid_interfaces:
                raise serializers.ValidationError(f"Invalid internal interfaces in router '{router['router_name']}': {invalid_interfaces}")
            
    def validate_instance_network_location(self, networks, instances):
        network_names = set(network["network_name"] for network in networks)
        for instance in instances:
            network_location = instance['network_location']
            if network_location not in network_names:
                raise serializers.ValidationError(f"Invalid network location in instance '{instance['instance_name']}': {network_location}")
            
    def validate_instance_image_id(self, instances):
        images = get_instance_images()
        image_id_list = [image[0] for image in images]
        for instance in instances:
            instance_image_id = instance['image_id']
            if instance_image_id not in image_id_list:
                raise serializers.ValidationError(f"Invalid Image ID in instance '{instance['instance_name']}': {instance_image_id}")
            
    def validate_instance_flavor_id(self, instances):
        flavors = get_instance_flavors()
        flavor_id_list = [flavor[0] for flavor in flavors]
        for instance in instances:
            instance_flavor_id = instance['flavor_id']
            if instance_flavor_id not in flavor_id_list:
                raise serializers.ValidationError(f"Invalid Flavor ID in instance '{instance['instance_name']}': {instance_flavor_id}")

    def validate_json(self, json_data):
        schema = {
            "type": "object",
            "properties": {
                "networks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "network_name": {"type": "string"},
                            "subnet_name": {"type": "string"},
                            "subnet_cidr": {"type": "string", "format": "ipv4-cidr"}
                        },
                        "required": ["network_name", "subnet_name", "subnet_cidr"]
                    }
                },
                "routers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "router_name": {"type": "string"},
                            "external_gateway_connected": {"type": "boolean"},
                            "internal_interfaces": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["router_name", "external_gateway_connected", "internal_interfaces"]
                    }
                },
                "instances": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "instance_name": {"type": "string"},
                            "network_location": {"type": "string"},
                            "static_ip": {"type": "string", "format": "ipv4"},
                            "image_id": {"type": "string"},
                            "flavor_id": {"type": "string"},
                            "instance_for": {"type": "string", "enum": ["Red Team", "Blue Team", "Yellow Team", 'Purple Team']},
                        },
                        "required": ["instance_name", "network_location", "image_id", "flavor_id", "instance_for"]
                    }
                }
            },
            "required": ["networks", "routers", "instances"]
        }

        # Load the JSON data
        data = json.loads(json_data)

        # Validate the input JSON against the schema
        try:
            jsonschema.validate(data, schema)

            self.validate_unique_network_names(data["networks"])
            self.validate_unique_router_names(data["routers"])
            self.validate_unique_instance_names(data["instances"])

            self.validate_router_internal_interfaces(data["networks"], data["routers"])

            self.validate_instance_network_location(data["networks"], data["instances"])
            self.validate_instance_image_id(data["instances"])
            self.validate_instance_flavor_id(data["instances"])
            
            return True
        except jsonschema.ValidationError as e:
            return False

    def validate(self, data):
        data['user'] = self.context['request'].user
        data['scenario'] = scenario_collection.find_one({
            'scenario_id': data['scenario_id'], 
            'scenario_creator_id': data['user'].get('user_id'),
            'scenario_is_prepared': False
        }, {'_id': 0})

        if not data['scenario']:
            raise serializers.ValidationError("Invalid Scenario ID")

        if data['user'].get('user_role') != "WHITE TEAM":
            raise serializers.ValidationError("You are not allowed to perform this operation. Only white team members can create a scenario.")
        
        # Validate the complete scenario infra
        is_valid = self.validate_json(json.dumps(data['scenario_infra']))
        if not is_valid:
            raise serializers.ValidationError("Invalid scenario infra data format. Enter correct data.")        
        
        return data

    def create(self, validated_data):

        updated_scenario = scenario_collection.update_one({'scenario_id': validated_data['scenario'].get('scenario_id')}, {'$set': {
            'scenario_infra': validated_data['scenario_infra'],
            'scenario_is_prepared': True,
            'scenario_updated_at': datetime.datetime.now()
        }})

        response = {
            'scenario_id': validated_data['scenario_id'],
            'scenario_infra': validated_data['scenario_infra']
        }

        return response
    

class ScenarioListSerializer(serializers.Serializer):
    def get(self, user_id):
        if user_id:
            user_profile = user_profile_collection.find_one({"user_id":user_id},{"_id":0,"assigned_games":1})
            if not user_profile["assigned_games"]["display_all_scenario"]:
                query = {
                    'scenario_id': {'$in': user_profile["assigned_games"]["scenario"]},
                    'scenario_is_prepared': True,
                    'scenario_is_approved': True,
                    }
            else:
                query = {
                    'scenario_is_prepared': True,
                    'scenario_is_approved': True,
                    }
        else:      
            query = {
                'scenario_is_prepared': True,
                'scenario_is_approved': True,
                }   
        scenarios = list(scenario_collection.find(query,
                                            {'_id': 0,"scenario_flags": 0}))
        for scenario in scenarios:
            category_name = scenario_category_collection.find_one({"scenario_category_id":scenario["scenario_category_id"]},{"_id":0,"scenario_category_name":1})
            scenario["scenario_category_name"] = category_name["scenario_category_name"]

        return scenarios
    

class ScenarioGameStartSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(max_length=50, required=True, write_only=True)
    scenario_players_info = serializers.JSONField(write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data    

    def validate_user_availability(self, email):
        user = user_collection.find_one({'email': email}, {'user_id': 1})
        query = {"scenario_participants.scenario_participant_id": user['user_id']}
        record_exists = scenario_active_game_collection.count_documents(query) > 0
        if record_exists:
            raise serializers.ValidationError(f"{email} is already playing a scenario. Please invite another player.")
        return email

    def validate_email(self, email):
        if not user_collection.find_one({'email': email, 'is_active': True, 'is_verified': True}):
            raise serializers.ValidationError(f"{email} is not a member yet. Please invite the player to join this platform first.")
        return self.validate_user_availability(email)

    def validate_unique_player_email(self, players):        
        emails = [self.validate_email(player["player_email"]) for player in players]
        duplicates = set(email for email in emails if emails.count(email) > 1)
        if duplicates:
            raise serializers.ValidationError(f"Multiple machines for players {duplicates} are not allowed.")
        
    def validate_unique_player_instance(self, players):
        instances = [player["player_instance"] for player in players]
        duplicates = set(instance for instance in instances if instances.count(instance) > 1)
        if duplicates:
            raise serializers.ValidationError(f"Same machines {duplicates} assigned multiple times.")

    def validate_json(self, json_data, scenario_id):
        scenario = scenario_collection.find_one({"scenario_id": scenario_id}, {"scenario_infra.instances.instance_name": 1, "_id": 0})
        instance_name_obj_list = scenario["scenario_infra"]["instances"]
        
        instance_name_list = []  
        for instance_obj in scenario["scenario_infra"]["instances"]:
            instance_name_list.append(instance_obj['instance_name'])

        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "player_email": {"type": "string", "format": "email"},
                    "player_instance": {"type": "string", "enum": instance_name_list}
                },
                "required": ["player_email", "player_instance"]
            }
        }

        # Load the JSON data
        data = json.loads(json_data)

        # Validate the input JSON against the schema
        try:
            jsonschema.validate(data, schema)
            self.validate_unique_player_email(data)
            self.validate_unique_player_instance(data)
            return True
        except jsonschema.ValidationError as e:
            return False
        
    def count_member_requirement(self, data_dict):
        team_counts = {}
    
        for instance in data_dict["instances"]:
            team = instance["instance_for"]
            team_counts[team] = team_counts.get(team, 0) + 1
        
        return team_counts
    
    def count_actual_members(self, player_list):
        role_counts = {}

        for player in player_list:
            role = player["player_instance"]
            role_counts[role] = role_counts.get(role, 0) + 1

        return role_counts

    def validate(self, data):
        data['user'] = self.context['request'].user
        data['scenario'] = scenario_collection.find_one({
            'scenario_id': data['scenario_id'], 
            'scenario_is_prepared': True,
        }, {'_id': 0})

        if not data['scenario']:
            raise serializers.ValidationError("Invalid Scenario ID")
        
        assigned_games = user_profile_collection.find_one({"user_id": data['user']["user_id"]},{"_id":0,"assigned_games":1})
        if not assigned_games["assigned_games"]["display_all_scenario"] and data["scenario_id"] not in assigned_games["assigned_games"]["scenario"]:
            raise serializers.ValidationError("You are not authorised to start this game.")
        
        
        if scenario_active_game_collection.find_one({'scenario_is_ready': False, 'scenario_id': data['scenario_id']}):
            raise serializers.ValidationError("Some operations are being performed. Please Wait!!")
        
        if not data['scenario'].get('scenario_is_approved'):
            raise serializers.ValidationError("This scenario is still under inspection. Please try some different scenario.")
        
        scenario_active_game = scenario_active_game_collection.find_one({'user_id': data['user'].get('user_id'), 'scenario_id': data['scenario_id']})
        if scenario_active_game:
            raise serializers.ValidationError("You have already started this scenario. Please navigate to Active Scenario to resume it.")
        
        # Validate the complete scenario infra
        is_valid = self.validate_json(json.dumps(data['scenario_players_info']), data['scenario_id'])
        if not is_valid:
            raise serializers.ValidationError("Invalid scenario player data. Enter correct data.")
        
        for item in data['scenario_players_info']:
            user_details = user_collection.find_one({"email":item["player_email"]},{"_id":0, "user_id":1})
            if user_details["user_id"] != data['user']["user_id"]:
                users_assigned_games = user_profile_collection.find_one({"user_id": user_details["user_id"]},{"_id":0, "assigned_games":1})
                if not users_assigned_games["assigned_games"]["display_all_scenario"] and data["scenario_id"] not in users_assigned_games["assigned_games"]["scenario"]:
                    raise serializers.ValidationError("You are not authorised to add this user.") 
        
        
        return data
    
    def create(self, validated_data):

        create_scenario_game.delay(validated_data)
        
        # scenario_participants = []

        # scenario_instances_detail = scenario_collection.find_one({"scenario_id": validated_data["scenario_id"]}, {"scenario_infra.instances.instance_for": 1, "scenario_infra.instances.instance_name": 1, "_id": 0})['scenario_infra']['instances']
        # player_instance_dict = {}

        # for player_info in validated_data['scenario_players_info']:
        #     scenario_invitation_id = generate_random_string('scenario_invitation_id', length=15)
        #     player = user_collection.find_one({'email': player_info['player_email']})
        #     current_datetime = datetime.datetime.now()

        #     player_role = next((item for item in scenario_instances_detail if item['instance_name'] == player_info["player_instance"]), None)['instance_for']

        #     player_instance_dict[player_info["player_instance"]] = player['user_id']
    
        #     invitation = {
        #         'scenario_invitation_id': scenario_invitation_id,
        #         'scenario_id': validated_data['scenario'].get('scenario_id'),
        #         'scenario_game_owner_id': validated_data['user'].get('user_id'),
        #         'scenario_participant_id': player['user_id'],
        #         'scenario_participant_role': player_role,
        #         'scenario_invitation_accepted': False,
        #         'scenario_invitation_denied': False,
        #         'scenario_invitation_created_at': current_datetime,
        #         'scenario_invitation_updated_at': current_datetime
        #     }
        #     scenario_invitation_collection.insert_one(invitation)

        #     invitation_mailing_detail = {
        #         'scenario_name': validated_data['scenario'].get('scenario_name'),
        #         'player_name': player['user_full_name'],
        #         'game_owner': validated_data['user'].get('user_full_name'),
        #         'accept_invitation_url': f"{API_URL}/api/scenario/invitation/accept/{scenario_invitation_id}/",
        #         'deny_invitation_url': f"{API_URL}/api/scenario/invitation/deny/{scenario_invitation_id}/",
        #         'scenario_time': validated_data['scenario'].get('scenario_time'),
        #         'player_instance': player_role,
        #         'scenario_description': validated_data['scenario'].get('scenario_description'),
        #         'player_email': player['email']
        #     }
        #     send_invitation_by_email.delay(invitation_mailing_detail)

        #     temp = {
        #         'scenario_participant_id': player['user_id'],
        #         'scenario_participant_role': player_role,
        #         'scenario_flags_captured': [],
        #         'scenario_invitation_id': scenario_invitation_id
        #     }
        #     scenario_participants.append(temp)

        # start_time = datetime.datetime.now()
        # end_time = start_time + datetime.timedelta(hours=validated_data['scenario'].get('scenario_time'))
        
        # scenario_game_id = generate_random_string('scenario_game_id', length=25)
        # scenario_active_game = {
        #     'scenario_game_id': scenario_game_id,
        #     'scenario_id': validated_data['scenario'].get('scenario_id'),
        #     'scenario_game_owner_id': validated_data['user'].get('user_id'),
        #     'scenario_start_time': start_time,
        #     'scenario_end_time': end_time,
        #     'scenario_flags_captured': [],
        #     'scenario_participants': scenario_participants,
        #     'scenario_game_created_at': start_time,
        #     'scenario_game_updated_at': start_time,
        # }

        # scenario_infra = validated_data['scenario'].get('scenario_infra')
        # scenario_networks = scenario_infra.get('networks')
        # scenario_routers = scenario_infra.get('routers')
        # scenario_instances = scenario_infra.get('instances')

        # network_subnet_dict = {}
        # network_dict = {}

        # # Creating Networks
        # scenario_infra_networks = []
        # for scenario_network in scenario_networks:
        #     network_name = scenario_network.get('network_name')
        #     subnet_name = scenario_network.get('subnet_name')
        #     subnet_cidr = scenario_network.get('subnet_cidr')

        #     network, subnet = create_cloud_network(subnet_cidr=subnet_cidr,  network_name=network_name, subnet_name=subnet_name)
            
        #     temp = {
        #         'network_name': network_name,
        #         'network_id': network.id,
        #         'subnet_name': subnet_name,
        #         "subnet_id": subnet.id,
        #     }
        #     scenario_infra_networks.append(temp)

        #     network_subnet_dict[network_name] = subnet.id
        #     network_dict[network_name] = network.id

        # # Creating Routers
        # scenario_infra_routers = []
        # for scenario_router in scenario_routers:
        #     router_name = scenario_router.get('router_name')
        #     external_gateway_connected = scenario_router.get('external_gateway_connected')
        #     internal_interfaces = scenario_router.get('internal_interfaces')

        #     router = create_cloud_router(router_name=router_name)

        #     if external_gateway_connected:
        #         updated_router = connect_router_to_public_network(router)
        #         router = updated_router

        #     internal_subnet_id_list = []
        #     for internal_interface in internal_interfaces:
        #         internal_subnet_id = network_subnet_dict[internal_interface]
        #         internal_subnet = get_cloud_subnet(internal_subnet_id)
        #         connect_router_to_private_network(router, internal_subnet)
        #         internal_subnet_id_list.append(internal_subnet_id)
        
        #     temp = {
        #         'router_id': router.id,
        #         "internal_subnet_id_list": internal_subnet_id_list,
        #     }
        #     scenario_infra_routers.append(temp)


        # # Creating Instances
        # scenario_infra_instances = []
        # for scenario_instance in scenario_instances:
        #     instance_name = scenario_instance.get('instance_name')
        #     network_location = scenario_instance.get('network_location')
        #     image_id = scenario_instance.get('image_id')
        #     flavor_id = scenario_instance.get('flavor_id')
        #     instance_for = scenario_instance.get('instance_for')
            
        #     cloud_instance = create_cloud_instance(instance_name, image_id, flavor_id, network_dict[network_location])
        #     last_user_id = player_instance_dict[instance_name]
            
        #     temp = {
        #         'instance_id': cloud_instance.id,
        #         'instance_name': instance_name,
        #         'instance_user': last_user_id,
        #         'instance_user_role': instance_for
        #     }
        #     scenario_infra_instances.append(temp)        

        # # Creating Scenario User Resources Collection Record
        # scenario_user_resource = {
        #     'scenario_infra_networks': scenario_infra_networks,
        #     'scenario_infra_routers': scenario_infra_routers,
        #     'scenario_infra_instances': scenario_infra_instances,
        #     'scenario_user_resource_created_at': datetime.datetime.now(),
        #     'scenario_user_resource_updated_at': datetime.datetime.now()
        # }
        # scenario_active_game['scenario_user_resource'] = scenario_user_resource
        # scenario_active_game_collection.insert_one(scenario_active_game)


        # response = {
        #     'scenario_id': validated_data['scenario'].get('scenario_id'),
        #     'scenario_game_id': scenario_game_id,
        #     'scenario_players_info': validated_data['scenario_players_info']
        # }

        response = {}
        
        return response
    

class ScenarioAcceptInvitationSerializer(serializers.Serializer):
    def get(self, invitation_id):        
        invitation = scenario_invitation_collection.find_one({
            'scenario_invitation_id': invitation_id,
            'scenario_invitation_accepted': False,
            'scenario_invitation_denied': False
        })
        if not invitation:
            return {
                "errors": {
                    "non_field_errors": ["Invalid Invitation"]
                }
            }
        
        update_invitation = scenario_invitation_collection.update_one({'scenario_invitation_id': invitation_id}, {'$set': {
            'scenario_invitation_accepted': True,
            'scenario_invitation_updated_at': datetime.datetime.now()
        }})

        return {'message': 'Invitation Accepted!'}
    

class ScenarioDenyInvitationSerializer(serializers.Serializer):
    def get(self, invitation_id):        
        invitation = scenario_invitation_collection.find_one({
            'scenario_invitation_id': invitation_id,
            'scenario_invitation_accepted': False,
            'scenario_invitation_denied': False
        })
        if not invitation:
            return {
                "errors": {
                    "non_field_errors": ["Invalid Invitation"]
                }
            }
        
        update_invitation = scenario_invitation_collection.update_one({'scenario_invitation_id': invitation_id}, {'$set': {
            'scenario_invitation_denied': True,
            'scenario_invitation_updated_at': datetime.datetime.now()
        }})

        return {'message': 'Invitation Denied!'}
    

class ScenarioGameConsoleSerializer(serializers.Serializer):
    # scenario_game_id = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data
    
    def get(self, scenario_game_id, user):

        query = {"scenario_participants.scenario_participant_id": user['user_id'], "scenario_game_id": scenario_game_id}
        projection = {}

        scenario_active_game = scenario_active_game_collection.find_one(query, projection)
        
        if not scenario_active_game:
            raise serializers.ValidationError("Invalid Scenario Game ID")

        if not scenario_active_game["scenario_is_ready"]:
            raise serializers.ValidationError("Some operations are being performed. Please Wait!!")
        
        scenario_game = scenario_collection.find_one({'scenario_id': scenario_active_game['scenario_id']})

        scenario_infra_instances = scenario_active_game['scenario_user_resource'].get('scenario_infra_instances')
        
        scenario_instance_ip_list = []
        for instance in scenario_infra_instances:
            instance_id = instance['instance_id']
            image_id = instance['image_id']
            cloud_instance = get_cloud_instance(instance_id)
            scenario_instance_ip_list.append(get_instance_private_ip(cloud_instance))

            resource = resource_credentials_collection.find_one({"image_id": image_id}, {'_id': 0, 'username': 1, 'password': 1})
            
            if instance['instance_user'] == user['user_id']:
                console_url = get_instance_console(cloud_instance).url
            
                if not resource:
                    username = "NA"
                    password = "NA"
                else:
                    username = resource.get('username',"NA")
                    password = resource.get('password',"NA")
        
        for participant in scenario_active_game['scenario_participants']:
            if participant['scenario_participant_id'] == user['user_id']:
                participant_role = participant['scenario_participant_role']
                if participant_role == "Yellow Team":
                    flag_count = 0
                else:
                    flag_count = len(scenario_game['scenario_flags'].get(participant_role))

        response = {
            "scenario_game_id": scenario_active_game['scenario_game_id'],
            "scenario_start_time": scenario_active_game['scenario_start_time'],
            "scenario_end_time": scenario_active_game['scenario_end_time'],
            "scenario_name" : scenario_game['scenario_name'],
            "scenario_description": scenario_game['scenario_description'],
            "scenario_flag_count" : flag_count,
            "scenario_thumbnail" : scenario_game['scenario_thumbnail'],
            "scenario_walkthrough": scenario_game['scenario_documents'],
            "scenario_assigned_severity" : scenario_game['scenario_assigned_severity'],
            "scenario_score" : scenario_game['scenario_score'],
            "scenario_player_count": len(scenario_active_game['scenario_participants']),
            "scenario_console_url": console_url,
            "scenario_instance_ip_list": scenario_instance_ip_list,
            "scenario_vm_username": username,
            "scenario_vm_password": password
        }
        
        return response
    

class ScenarioActiveGameListSerializer(serializers.Serializer):
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data
    
    def get(self, user_id):

        query = {"scenario_participants.scenario_participant_id": user_id}
        projection = {}
        scenario_active_game = scenario_active_game_collection.find_one(query, projection)
        
        if not scenario_active_game:
            return {
                "message": "No Active Games"
            }
        
        if not scenario_active_game["scenario_is_ready"]:
            return {
                "message": "No Active Games"
            }

        
        scenario_game = scenario_collection.find_one({'scenario_id': scenario_active_game['scenario_id']})
        scenario_category = scenario_category_collection.find_one({'scenario_category_id': scenario_game['scenario_category_id']})
        game_owner = user_collection.find_one({'user_id': scenario_active_game['scenario_game_owner_id']})

        for participant in scenario_active_game['scenario_participants']:
            if participant['scenario_participant_id'] == user_id:
                participant_role = participant['scenario_participant_role']
                if participant_role == "Yellow Team":
                    flag_count = 0
                    flags_captured = participant['scenario_flags_captured']
                else:
                    flag_count = len(scenario_game['scenario_flags'].get(participant_role))
                    flags_captured = participant['scenario_flags_captured']

            

        response = {
            "scenario_game_id": scenario_active_game['scenario_game_id'],
            "scenario_start_time": scenario_active_game['scenario_start_time'],
            "scenario_end_time": scenario_active_game['scenario_end_time'],
            "scenario_flags_captured": flags_captured,
            "scenario_flags_captured_count": len(flags_captured),
            "scenario_flag_count" : flag_count,
            "scenario_name" : scenario_game['scenario_name'],
            "scenario_description": scenario_game['scenario_description'],
            "scenario_thumbnail" : scenario_game['scenario_thumbnail'],
            "scenario_category_id": scenario_game['scenario_category_id'],
            "scenario_category_name": scenario_category['scenario_category_name'],
            "scenario_game_owner_id": scenario_active_game['scenario_game_owner_id'],
            "scenario_game_owner_name": game_owner['user_full_name'],
            "scenario_assigned_severity" : scenario_game['scenario_assigned_severity'],
            "scenario_score" : scenario_game['scenario_score'],
            "scenario_time" : scenario_game['scenario_time'],
            "scenario_player_count": len(scenario_active_game['scenario_participants']),
            "scenario_game_created_at": scenario_active_game['scenario_game_created_at'],
            "scenario_game_updated_at": scenario_active_game['scenario_game_updated_at'],
        }
        
        return response
    

class ScenarioGameDetailSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data
    
    def get(self, scenario_id, user, user_id):

        assigned_games = user_profile_collection.find_one({"user_id":user_id},{"_id":0,"assigned_games":1})
        if not assigned_games["assigned_games"]["display_all_scenario"] and scenario_id not in assigned_games["assigned_games"]["scenario"]:
            return {
                "errors": {
                    "non_field_errors": ["You are not authorised to view this game."]
                }
            }

        scenario = scenario_collection.find_one({'scenario_id': scenario_id})

        if not scenario:
            raise serializers.ValidationError("Invalid Scenario Id.")

        scenario_category = scenario_category_collection.find_one({'scenario_category_id': scenario['scenario_category_id']})
        scenario_creator = user_collection.find_one({'user_id': scenario['scenario_creator_id']})
        if not scenario_creator:
            raise serializers.ValidationError(f"Scenario creator not found: {scenario['scenario_creator_id']}")

        scenario_instances = scenario['scenario_infra'].get('instances')
        scenario_hardware_details = {
            "vcpu": 0,
            "disk_size": 0,
            "RAM": 0,
            "vm_count": 0
        }
        scenario_instances_name_list = []

        for instance in scenario_instances:
            instance_flavor = instance['flavor_id']
            flavor_detail = get_flavor_detail(instance_flavor)

            ram_as_flavor = round(flavor_detail['ram'])

            scenario_hardware_details['vcpu'] += flavor_detail['vcpus']
            scenario_hardware_details['disk_size'] += flavor_detail['disk']
            scenario_hardware_details['RAM'] += ram_as_flavor
            scenario_hardware_details['vm_count'] += 1

            scenario_instances_name_list.append(instance['instance_name'])

        scenario_hardware_details['disk_size'] = f"{scenario_hardware_details['disk_size']} GB"
        scenario_hardware_details['RAM'] = f"{round(scenario_hardware_details['RAM']/1024)} GB"

        response = {
            "scenario_id": scenario['scenario_id'],
            "scenario_thumbnail": scenario['scenario_thumbnail'],
            "scenario_category_name": scenario_category['scenario_category_name'],
            "scenario_score": scenario['scenario_score'],
            "scenario_time": scenario['scenario_time'],
            "scenario_assigned_severity": scenario['scenario_assigned_severity'],
            "scenario_name": scenario['scenario_name'],
            "scenario_rated_severity": scenario['scenario_rated_severity'],
            "scenario_description": scenario['scenario_description'],
            "scenario_hardware_details": scenario_hardware_details,
            "scenario_objectives": "",
            "scenario_tools_technologies": scenario['scenario_tools_technologies'],
            "scenario_prerequisites": scenario['scenario_prerequisites'],
            # "scenario_external_references": scenario['scenario_external_references'],
            "scenario_documents": scenario['scenario_documents'],
            "scenario_creator_id": str(scenario_creator['user_id']),
            "scenario_creator_name": scenario_creator['user_full_name'],
            # "scenario_players_count": scenario['scenario_players_count'],
            "scenario_for_premium_user": scenario['scenario_for_premium_user'],
            "scenario_solved_by": [],
            "scenario_created_at": scenario['scenario_created_at'],
            "scenario_red_team_flag_count": len(scenario['scenario_flags'].get('Red Team')),
            "scenario_blue_team_flag_count": len(scenario['scenario_flags'].get('Blue Team')),
            "scenario_purple_team_flag_count": len(scenario['scenario_flags'].get('Purple Team')),
            "scenario_yellow_team_flag_count": len(scenario['scenario_flags'].get('Yellow Team')),
             "scenario_instances_name_list": scenario_instances_name_list,
            }

        print(response)
        if not isinstance(user, AnonymousUser):
            query = {"scenario_participants.scenario_participant_id": user['user_id'], "scenario_id": scenario['scenario_id'],}
            projection = {}

            scenario_active_game = scenario_active_game_collection.find_one(query, projection)
            
            if scenario_active_game:
                response['scenario_game_id'] = scenario_active_game['scenario_game_id']
                response['scenario_is_ready'] = scenario_active_game['scenario_is_ready']


        # Adding scenario winning wall details
        scenario_players_count = scenario_player_arsenal_collection.count_documents({'scenario_id': scenario_id})
        if scenario_players_count > 0:
            winning_wall_data = []
            scenario_players = scenario_player_arsenal_collection.find({'scenario_id': scenario_id})

            for player in scenario_players:
                scenario_score_obtained = str(round(player['scenario_score_obtained'])) + "/" + str(round(response['scenario_score']))
                scenario_flags_captured = str(len(player['scenario_flags_captured'])) + "/" + str(response['scenario_red_team_flag_count'] + response['scenario_blue_team_flag_count'] + response['scenario_purple_team_flag_count'])

                user = user_collection.find_one({'user_id': player['scenario_participant_id']})
                if user:
                
                    winning_wall_data.append({
                    "user_id": user['user_id'],
                    "user_full_name": user["user_full_name"],
                    "user_avatar": user["user_avatar"],
                    "user_role": user['user_role'],
                    "score_obtained": scenario_score_obtained,
                    "flags_captured": scenario_flags_captured,
                    "badge_earned": "Gold"
                    })
        
            sorted_winning_wall_data = sorted(winning_wall_data, key=lambda x: convert_score(x["score_obtained"]), reverse=True)

            response['winning_wall'] = sorted_winning_wall_data

        return response


class ScenarioSubmitFlagSerializer(serializers.Serializer):
    scenario_game_id = serializers.CharField(max_length=50, required=True)
    scenario_flag = serializers.CharField(max_length=50, required=True, write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data    

    def validate(self, data):
        user = self.context['request'].user

        query = {"scenario_participants.scenario_participant_id": user['user_id'], "scenario_game_id": data['scenario_game_id']}
        projection = {}

        scenario_active_game = scenario_active_game_collection.find_one(query, projection)
        
        if not scenario_active_game:
            raise serializers.ValidationError("Invalid Scenario Game ID")
    
        data["scenario_active_game"] = scenario_active_game
        data['user'] = user

        return data

    def create(self, validated_data):
        scenario_flags_captured = validated_data['scenario_active_game'].get('scenario_flags_captured')
        scenario = scenario_collection.find_one({'scenario_id': validated_data['scenario_active_game'].get('scenario_id')})
        
        if validated_data['scenario_flag'] in scenario_flags_captured:
            message = "Flag Already Captured!"
            is_flag_correct = False
        else:
            for participant in validated_data['scenario_active_game'].get('scenario_participants'):
                if participant['scenario_participant_id'] == validated_data['user'].get('user_id'):
                    participant_role = participant['scenario_participant_role']
                    if participant_role == 'Yellow Team' and participant_role == 'White Team':
                        raise serializers.ValidationError("This operation is not allowed for your current role in this scenario.")
                        
                    original_flags = scenario['scenario_flags'].get(participant_role, None)
                    participant_captured_flags = participant['scenario_flags_captured']
                    participant_id = participant['scenario_participant_id']

                    if validated_data['scenario_flag'] in original_flags:
                        scenario_flags_captured.append(validated_data['scenario_flag'])
                        participant_captured_flags.append(validated_data['scenario_flag'])

                        # Update the document
                        filter_query = {"scenario_participants.scenario_participant_id": participant_id, }
                        update_query = {"$set": {"scenario_participants.$[participant].scenario_flags_captured": participant_captured_flags}}
                        array_filters = [{"participant.scenario_participant_id": participant_id}]
                        scenario_active_game_update = scenario_active_game_collection.update_one(filter_query, update_query, array_filters=array_filters)

                        scenario_active_game_update = scenario_active_game_collection.update_one(
                            {   'scenario_game_id':validated_data["scenario_game_id"] }, 
                            {   "$set": {  
                                    "scenario_flags_captured": scenario_flags_captured,
                                    "scenario_game_updated_at": datetime.datetime.now()
                                }
                            }
                        )

                        message = "Kudos! You Captured a Flag."
                        is_flag_correct = True

                    else:
                        message = "Better Luck Next Time!"
                        is_flag_correct = False

        response_to_return = {
            "scenario_game_id" : validated_data["scenario_game_id"],
            "ctf_flag" : validated_data['scenario_flag'],
            "message" : message,
            "is_flag_correct" : is_flag_correct,
        }

        return response_to_return
    

class ScenarioGameDeleteSerializer(serializers.Serializer):

    def validate(self, data):
        scenario_game_id = self.context['view'].kwargs['scenario_game_id']
        scenario_game = scenario_active_game_collection.find_one({'scenario_game_id': scenario_game_id}, {"_id": 0})

        if not scenario_game:
            raise serializers.ValidationError("Invalid Scenario Game ID")
        
        if scenario_game["scenario_is_ready"] == False:
            raise serializers.ValidationError("Some operations are being performed. Please Wait!!")

        return data
    
    def update_player_arsenal(self, scenario_archive_game):
        current_time = datetime.datetime.now()
        scenario_game = scenario_collection.find_one({'scenario_id': scenario_archive_game['scenario_id']}, {'_id': 0})
        scenario_flags = scenario_game['scenario_flags']
        scenario_played_by = scenario_game['scenario_played_by']
        scenario_players_count = int(scenario_game['scenario_players_count'])
        max_score = scenario_game['scenario_score']

        for participant in scenario_archive_game['scenario_participants']:
            scenario_participant_id = participant['scenario_participant_id']
            scenario_participant_role = participant['scenario_participant_role']

            if scenario_participant_role == 'White Team' or scenario_participant_role == 'Yellow Team':
                continue

            captured_flags_count = len(participant['scenario_flags_captured'])
            original_flags_count = len(scenario_flags[scenario_participant_role])

            if captured_flags_count == 0:
                score_obtained = 0
            else:
                score_obtained = min(captured_flags_count / original_flags_count * max_score, max_score)
            
            score_obtained = round(score_obtained, 2)
            score_percentage = round((score_obtained/max_score)*100, 2)

            if scenario_participant_id not in scenario_played_by:
                scenario_played_by.append(scenario_participant_id)
                scenario_players_count += 1

            scenario_players_arsenal = scenario_player_arsenal_collection.find_one(
                {'scenario_participant_id': participant['scenario_participant_id'], 'scenario_id': scenario_game['scenario_id']},
                {'_id': 0}
            )
            if scenario_players_arsenal:
                scenario_archive_game_list = scenario_players_arsenal['scenario_archive_game_list']
                scenario_archive_game_list.append(scenario_archive_game['scenario_archive_game_id'])
                
                scenario_player_arsenal_collection.update_one(
                    {'scenario_participant_id': participant['scenario_participant_id'], 'scenario_id': scenario_game['scenario_id']},
                    { '$set': {
                            'scenario_participant_role': scenario_participant_role,
                            'scenario_score_obtained': score_obtained, 
                            'scenario_flags_captured': participant['scenario_flags_captured'],
                            'scenario_archive_game_list': scenario_archive_game_list,
                            'scenario_arsenal_updated_at': current_time
                        }
                    }
                )
            else:
                scenario_arsenal_id = generate_random_string('scenario_arsenal_id', length=25)
                new_player_arsenal = {
                    'scenario_arsenal_id': scenario_arsenal_id,
                    'scenario_participant_id': participant['scenario_participant_id'],
                    'scenario_id': scenario_game['scenario_id'],
                    'scenario_participant_role': scenario_participant_role,
                    'scenario_score_obtained': score_obtained, 
                    'scenario_max_score': max_score, 
                    'scenario_flags_captured': participant['scenario_flags_captured'],
                    'scenario_rated_severity': 0,
                    'scenario_archive_game_list': [scenario_archive_game['scenario_archive_game_id'],],
                    'scenario_arsenal_created_at': current_time,
                    'scenario_arsenal_updated_at': current_time
                }
                scenario_player_arsenal_collection.insert_one(new_player_arsenal)

        
        updated_scenario_game = scenario_collection.update_one(
            { 'scenario_id': scenario_game['scenario_id'] },
            { '$set': {
                    'scenario_played_by': scenario_played_by,
                    'scenario_players_count': scenario_players_count,
                    'scenario_updated_at': current_time
                }
            }
        )        

        return score_obtained, max_score
    
    def update_user_profile(self, scenario_archive_game):
        for participant in scenario_archive_game['scenario_participants']:
            scenario_player_arsenal = scenario_player_arsenal_collection.find({'scenario_participant_id': participant['scenario_participant_id']}, {'_id': 0})
            
            user_scenario_score = 0
            for game in scenario_player_arsenal:
                user_scenario_score += game['scenario_score_obtained'] 

            # For updating total score
            user_profile_update = user_profile_collection.update_one({'user_id': participant['scenario_participant_id']}, {'$set': {
                'user_scenario_score': user_scenario_score,
                'user_profile_updated_at': datetime.datetime.now()
            }})

    def delete_game(self, scenario_game_id):
        scenario_active_game_collection.update_one({'scenario_game_id': scenario_game_id}, {"$set": {"scenario_is_ready":False}})

        scenario_active_game = scenario_active_game_collection.find_one({'scenario_game_id': scenario_game_id}, {"_id": 0})
        scenario_user_resource = scenario_active_game['scenario_user_resource']
        scenario_infra_networks = scenario_user_resource['scenario_infra_networks']
        scenario_infra_routers = scenario_user_resource['scenario_infra_routers']
        scenario_infra_instances = scenario_user_resource['scenario_infra_instances']
        
        for instance in scenario_infra_instances:
            cloud_instance = get_cloud_instance(instance['instance_id'])
            if cloud_instance:
                deleted_cloud_instance = delete_cloud_instance(cloud_instance)

        for router in scenario_infra_routers:
            cloud_router = get_cloud_router(router['router_id'])
            if cloud_router:
                internal_subnet_id_list = router['internal_subnet_id_list']    
                for subnet_id in internal_subnet_id_list:
                    disconnect_router_from_private_network(router['router_id'], subnet_id)
                delete_cloud_router(router['router_id'])
        
        for network in scenario_infra_networks:
            delete_cloud_network(network['network_id'], network['subnet_id'])            

        scenario_archive_game_id = generate_random_string('scenario_archive_game_id', length=35)
        current_time = datetime.datetime.now()
        
        scenario_archive_game = {
            "scenario_archive_game_id": scenario_archive_game_id,
            "scenario_archive_created_at": current_time,
            "scenario_archive_updated_at": current_time,
        }
        scenario_archive_game.update(scenario_active_game)

        scenario_archive_game_collection.insert_one(scenario_archive_game)

        # For calculating and updating Game Score and Status
        scenario_score_obtained, scenario_score = self.update_player_arsenal(scenario_archive_game)
        # For updating total gaming score of a user
        self.update_user_profile(scenario_archive_game)

        scenario_name = scenario_collection.find_one({"scenario_id":scenario_active_game["scenario_id"]},{"_id":0,"scenario_name":1})

        for user_object in scenario_active_game["scenario_participants"]:
            notification = {
                    "type": "information",
                    "title": f"{scenario_name['scenario_name']} Scenario Deleted.",
                    "description": f"{scenario_name['scenario_name']} Scenario deleted successfully.",
                    "timestamp": datetime.datetime.now(),
                    "user_id": user_object['scenario_participant_id'],
                    "action_urls": [],
                    "redirection_url": "",
                }
            notification_collection.insert_one(notification)
            async_to_sync(send_notification)(group_name=user_object['scenario_participant_id'])

        scenario_active_game_collection.delete_one({ "scenario_game_id": scenario_active_game['scenario_game_id']})

        return scenario_archive_game

class ScenariosByCategoryIdSerializer(serializers.Serializer):
    def get(self, category_id, user_id):
        if not scenario_category_collection.find_one({"scenario_category_id": category_id}):
            return {"errors": {"non_field_errors": ["Invalid Scenario Category Id"]}}
        
        assigned_games = user_profile_collection.find_one({"user_id":user_id},{"_id":0,"assigned_games":1})

        if not assigned_games["assigned_games"]["display_all_scenario"]:
            query ={"$in":assigned_games["assigned_games"]["scenario"]}
            if not assigned_games["assigned_games"]["display_locked_scenario"]:
                scenario_category_detail_list = list(
                    scenario_collection.find({
                        "scenario_category_id": category_id,
                        "scenario_is_approved": True,
                        "scenario_id": query
                    }, 
                    { '_id': 0,
                    'scenario_id': 1,
                    'scenario_name': 1,
                    'scenario_assigned_severity': 1,
                    'scenario_score': 1, 
                    'scenario_description': 1, 
                    'mitre_mapping': "", 
                    'network_topology': "", 
                    'scenario_time': 1, 
                    'scenario_thumbnail': 1, 
                    'scenario_documents': 1, 
                    'scenario_is_challenge': 1,
                    'scenario_players_count': 1
                    }))
            else:
                scenario_category_detail_list = list(
                    scenario_collection.find({
                        "scenario_category_id": category_id,
                        "scenario_is_approved": True
                    }, 
                    { '_id': 0,
                    'scenario_id': 1,
                    'scenario_name': 1,
                    'scenario_assigned_severity': 1,
                    'scenario_score': 1, 
                    'scenario_description': 1, 
                    'mitre_mapping': "", 
                    'network_topology': "", 
                    'scenario_time': 1, 
                    'scenario_thumbnail': 1, 
                    'scenario_documents': 1, 
                    'scenario_is_challenge': 1,
                    'scenario_players_count': 1
                    }))
                for game in scenario_category_detail_list:
                    game['display'] = game['scenario_id'] in query['$in']
        
        else:
        
            scenario_category_detail_list = list(
                scenario_collection.find({
                    "scenario_category_id": category_id,
                    "scenario_is_approved": True
                }, 
                { '_id': 0,
                'scenario_id': 1,
                'scenario_name': 1,
                'scenario_assigned_severity': 1,
                'scenario_score': 1, 
                'scenario_description': 1, 
                'mitre_mapping': "", 
                'network_topology': "", 
                'scenario_time': 1, 
                'scenario_thumbnail': 1, 
                'scenario_documents': 1, 
                'scenario_is_challenge': 1,
                'scenario_players_count': 1
                }))

        return scenario_category_detail_list

class ScenarioTopologySerializer(serializers.Serializer):

    def coordinates(self, item_type, item_len):
        item_coords = {
            "networks": (150, 150),
            "routers": (150, 200),
            "instances": (150, 100)
        }

        cord_array = []
        min_value = 50

        if item_len == 1:
            return [item_coords[item_type]]

        n = 200 // (item_len + 1)
        for i in range(1, item_len + 1):
            min_value += n
            cord_array.append((min_value, item_coords[item_type][1]))

        return cord_array

    def create_topology(self, scenario_infra):
        nodes = []
        edges = []
        ite = 1
        for key_name in [("networks","network_name",),("routers","router_name",),("instances","instance_name")]:
            for key,value in scenario_infra.items():
                if key == key_name[0]:
                    item_len = len(value)
                    for name, cord in zip([item[key_name[1]] for item in value], self.coordinates(key, item_len)):
                        nodes.append({"id":ite,
                                "label":name,
                                "title":"Lorem Ipsum",
                                "x": cord[0],
                                "y": cord[1],  
                                "image":f"{API_URL}/static/images/topology/{key_name[0]}.png"
                                })
                        ite+=1

        for node in nodes:
            for inst in scenario_infra["instances"]:
                if inst["network_location"] == node["label"]:
                    for inner_node in nodes:
                        if inner_node["label"] == inst["instance_name"]:
                            edges.append({"from":node["id"],"to":inner_node["id"]})
            for rout in scenario_infra["routers"]:
                if node["label"] in rout["internal_interfaces"]:
                    for inner_node in nodes:
                        if inner_node["label"] == rout["router_name"]:
                            edges.append({"from":inner_node["id"],"to":node["id"]})
        return {"nodes":nodes,"edges":edges}

    def get(self, scenario_id):
        scenario_game = scenario_collection.find_one({"scenario_id": scenario_id})
        if not scenario_game:
            return {"errors": {"non_field_errors": ["Invalid Scenario Id"]}}
        
        if not scenario_game["scenario_is_prepared"]:
            return {"errors": {"non_field_errors": ["Prepare Scenario first."]}}
        
        topology_infra = self.create_topology(scenario_game["scenario_infra"])

        return topology_infra
    
class ScenarioUserEmailStatusSerializer(serializers.Serializer):
    def get(self,email):

        user = user_collection.find_one({'email': email, 'is_active': True, 'is_verified': True}, {'user_id': 1})

        if not user:
            return {"errors": {"non_field_errors": [f"{email} is not a member yet. Please invite the player to join this platform first."]}}
        
        query = {"scenario_participants.scenario_participant_id": user['user_id']}
        record_exists = scenario_active_game_collection.count_documents(query) > 0
        if record_exists:
            return {"errors": {"non_field_errors": [f"{email} is already playing a scenario. Please invite another player."]}}
            
        
        return {"status":True}


class ScenarioIPListSerializer(serializers.Serializer):
    def get(self, scenario_game_id, user_id):
        query = {"scenario_participants.scenario_participant_id": user_id, "scenario_game_id": scenario_game_id}
        projection = {}

        scenario_active_game = scenario_active_game_collection.find_one(query, projection)
        
        if not scenario_active_game:
            return {
                "errors": {
                    "non_field_errors": ["Invalid Scenario Game Id"]
                }
            }
        
        scenario_infra_instances = scenario_active_game['scenario_user_resource'].get('scenario_infra_instances')
        
        scenario_instance_ip_list = []
        for instance in scenario_infra_instances:
            if instance.get("instance_ip",""):
                instance_name = instance['instance_name']
                ip_address = instance["instance_ip"]
            else:
                instance_id = instance['instance_id']
                cloud_instance = get_cloud_instance(instance_id)
                instance_name = cloud_instance['name']
                ip_address = get_instance_private_ip(cloud_instance)
            
            temp = {
                'instance_name': instance_name,
                'ip_address': ip_address
            }
            scenario_instance_ip_list.append(temp)


        return {'scenario_instance_ip_list': scenario_instance_ip_list}
