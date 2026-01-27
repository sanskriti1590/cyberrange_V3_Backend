import datetime
import json
import os

import requests
from django.contrib.auth.models import AnonymousUser
from rest_framework import serializers

from cloud_management.utils import (
    get_image_detail,
    get_flavor_detail,
    get_cloud_instance,
    get_instance_private_ip,
    get_instance_console,
)
from core.utils import generate_random_string, API_URL
from database_management.pymongo_client import (
    ctf_category_collection,
    ctf_game_collection,
    ctf_cloud_mapping_collection,
    ctf_active_game_collection,
    ctf_archive_game_collection,
    ctf_player_arsenal_collection,
    user_collection,
    user_profile_collection,
    user_resource_collection,
    game_start_buffer_collection
)
from .utils import create_ctf_game, delete_ctf_game, validate_file_size


class CTFCategorySerializer(serializers.Serializer):

    def get(self):
        ctf_categories_list = []
        ctf_categories = ctf_category_collection.find()

        for category in ctf_categories:
            ctf_games_list = []

            ctf_games = ctf_game_collection.find({"ctf_category_id": category['ctf_category_id'], "ctf_target_uploaded": True})

            for ctf_game in ctf_games:
                temp_game = {
                    "ctf_id": ctf_game['ctf_id'],
                    "ctf_name": ctf_game['ctf_name'],
                    "ctf_description": ctf_game['ctf_description'],
                    "ctf_thumbnail": ctf_game['ctf_thumbnail'],
                    "ctf_creator_id": ctf_game['ctf_creator_id'],
                    "ctf_creator_name": ctf_game['ctf_creator_name'],
                    "ctf_assigned_severity": ctf_game['ctf_assigned_severity'],
                    "ctf_rated_severity": ctf_game['ctf_rated_severity'],
                    "ctf_score": ctf_game['ctf_score'],
                    "ctf_players_count": ctf_game['ctf_players_count']
                }
                ctf_games_list.append(temp_game)

            temp_category = {
                "ctf_category_id": category['ctf_category_id'],
                "ctf_category_name": category['ctf_category_name'],
                "ctf_category_description": category['ctf_category_description'],
                "ctf_category_thumbnail": category["ctf_category_thumbnail"],
                "category_items": ctf_games_list,
                "count": len(ctf_games_list),
            }

            ctf_categories_list.append(temp_category)

        return sorted(ctf_categories_list, key=lambda x: x["count"], reverse=True)

    class Meta:
        ref_name = 'CTFCategory'


class CTFGameSerializer(serializers.Serializer):
    ctf_name = serializers.CharField(max_length=200, required=True)
    ctf_description = serializers.CharField(min_length=50, max_length=5000, required=True)
    ctf_category_id = serializers.ChoiceField(choices=())
    ctf_severity = serializers.ChoiceField(choices=('Very Easy', 'Easy', 'Medium', 'Hard', 'Very Hard'), required=True, write_only=True)
    ctf_time = serializers.IntegerField(max_value=10, min_value=1, required=True)
    ctf_flags = serializers.CharField(max_length=500, required=True, write_only=True)
    ctf_thumbnail = serializers.FileField(required=False, write_only=True, validators=[validate_file_size])
    ctf_walkthrough = serializers.FileField(required=True, write_only=True, validators=[validate_file_size])
    ctf_flags_information = serializers.CharField(min_length=100, max_length=5000, required=False)
    ctf_rules_regulations = serializers.CharField(min_length=100, max_length=5000, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ctf_category_id'].choices = self.get_ctf_category_choices()

    def get_ctf_category_choices(self):
        categories = ctf_category_collection.find({}, {'ctf_category_id': 1, 'ctf_category_name': 1})
        return [(category['ctf_category_id'], category['ctf_category_name']) for category in categories]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        data['user'] = self.context['request'].user

        # Check that name contains only alphabets, digits, and spaces
        if not data['ctf_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Game Name can only contain alphabets, digits, and spaces.")

        if ctf_game_collection.find_one({'ctf_name': data['ctf_name']}):
            raise serializers.ValidationError("Game Name already exists, it must be unique. Try another name.")

        submitted_machines_count = ctf_game_collection.count_documents({
            'ctf_creator_id': data['user'].get('user_id'),
            "ctf_is_approved": False,
        })
        if data.get('user')['is_premium']:
            if submitted_machines_count >= 300:
                raise serializers.ValidationError("We are validating your previously submitted machines. Please try again later.")
        else:
            if submitted_machines_count >= 1:
                raise serializers.ValidationError(
                    "We are validating your previously submitted machine. Please upgrade to premium or try again later.")

        if len(data['ctf_flags'].split()) != len(set(data['ctf_flags'].split())):
            raise serializers.ValidationError("Duplicate flags found. Modify the flags and try again.")

        # Check if file format is allowed
        if data.get('ctf_thumbnail'):
            if not data['ctf_thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png')):
                raise serializers.ValidationError("Unsupported file format. Only jpeg, jpg, and png are allowed for CTF Thumbnail.")

        if not data['ctf_walkthrough'].name.lower().endswith(('pdf')):
            raise serializers.ValidationError("Unsupported file format. Only PDF is allowed for CTF Walkthrough.")

        return data

    def create(self, validated_data):
        # For generating unique random CTF Game Id
        ctf_id = generate_random_string('ctf_id', length=15)
        current_date_time = datetime.datetime.now()
        current_timestamp = str(current_date_time.timestamp()).split(".")[0]

        # For Walkthrough
        walkthrough_file = validated_data.pop('ctf_walkthrough', None)
        walkthrough_file_name, walkthrough_file_extension = os.path.splitext(walkthrough_file.name)
        # Rename the file
        walkthrough_file_name = f"{ctf_id}_walkthrough_{current_timestamp}{walkthrough_file_extension.lower()}"
        # Store the file in the specified directory
        with open(f"static/documents/ctf_game_walkthroughs/{walkthrough_file_name}", 'wb+') as destination:
            for chunk in walkthrough_file.chunks():
                destination.write(chunk)
        walkthrough_url = f'{API_URL}/static/documents/ctf_game_walkthroughs/{walkthrough_file_name}'

        # For Thumbnail
        if validated_data.get('ctf_thumbnail'):
            # Get file name and extension
            thumbnail_file = validated_data.pop('ctf_thumbnail', None)
            thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)

            # Rename the file
            thumbnail_file_name = f"{ctf_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"
            # Store the file in the specified directory
            with open(f"static/images/ctf_game_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                for chunk in thumbnail_file.chunks():
                    destination.write(chunk)

            thumbnail_url = f'{API_URL}/static/images/ctf_game_thumbnails/{thumbnail_file_name}'
        else:
            thumbnail_url = f'{API_URL}/static/images/ctf_game_thumbnails/default.jpg'

        # Store the user information in MongoDB
        ctf = {
            "ctf_id": ctf_id,
            "ctf_name": validated_data['ctf_name'],
            "ctf_description": validated_data['ctf_description'],
            "ctf_flags": validated_data["ctf_flags"].split(),
            "ctf_thumbnail": thumbnail_url,
            "ctf_walkthrough": walkthrough_url,
            "ctf_category_id": validated_data['ctf_category_id'],
            "ctf_time": validated_data['ctf_time'],
            "ctf_creator_id": validated_data['user']['user_id'],
            "ctf_creator_name": validated_data['user']['user_full_name'],
            "ctf_assigned_severity": validated_data['ctf_severity'],
            "ctf_rated_severity": {
                "very_easy": 0,
                "easy": 0,
                "medium": 0,
                "hard": 0,
                "very_hard": 0
            },
            "ctf_players_count": 0,
            "ctf_rating_count": 0,
            "ctf_score": 0,
            "ctf_mapping_id": "",
            "ctf_for_premium_user": False,
            "ctf_target_machine_name": "",
            "ctf_attacker_machine_name": "",
            "ctf_solved_by": [],
            "ctf_is_approved": False,
            "ctf_is_challenge": False,
            "ctf_target_uploaded": False,
            "ctf_flags_information": validated_data.get('ctf_flags_information', ""),
            "ctf_rules_regulations": validated_data.get('ctf_rules_regulations', ""),
            "ctf_created_at": current_date_time,
            "ctf_updated_at": current_date_time
        }

        ctf_game_collection.insert_one(ctf)

        return ctf

    class Meta:
        ref_name = 'CTFCTFGame'


class CTFGameDraftSerializer(serializers.Serializer):
    def get(self, user_id):
        user = user_collection.find_one({'user_id': user_id}, {'_id': 0, 'password': 0})
        if not user:
            return {
                "errors": {
                    "non_field_errors": ["Invalid User Id"]
                }
            }

        ctf_drafts = ctf_game_collection.find({
            'ctf_target_machine_name': '',
            'ctf_creator_id': user_id,
            'ctf_is_approved': False
        }, {'_id': 0})

        ctf_draft_list = []
        for ctf in ctf_drafts:
            ctf_category = ctf_category_collection.find_one({"ctf_category_id": ctf['ctf_category_id']})

            temp = {
                'ctf_id': ctf['ctf_id'],
                'ctf_name': ctf['ctf_name'],
                'ctf_category_id': ctf_category['ctf_category_id'],
                'ctf_category_name': ctf_category['ctf_category_name'],
                'ctf_flag_count': len(ctf['ctf_flags']),
                'ctf_target_uploaded': ctf['ctf_target_uploaded'],
                'ctf_description': ctf['ctf_description'],
                'ctf_thumbnail': ctf['ctf_thumbnail'],
                'ctf_is_approved': ctf['ctf_is_approved'],
                'ctf_created_at': ctf['ctf_created_at'],
                'ctf_updated_at': ctf['ctf_updated_at']
            }
            ctf_draft_list.append(temp)

        return ctf_draft_list

    class Meta:
        ref_name = 'CTFGameDraft'


class CTFGameMachineSerializer(serializers.Serializer):
    ctf_id = serializers.CharField(max_length=50, required=True)
    target_machine = serializers.FileField(required=True, write_only=True, validators=[validate_file_size])

    def validate(self, data):
        user_id = self.context['request'].user['user_id']

        ctf_machine = ctf_game_collection.find_one({'ctf_id': data['ctf_id'], 'ctf_creator_id': user_id})
        if not ctf_machine:
            raise serializers.ValidationError("Invalid CTF ID")

        if ctf_machine['ctf_target_uploaded']:
            raise serializers.ValidationError("The target machine has already been uploaded.")

        return data

    def create(self, validated_data):
        ctf_id = validated_data['ctf_id']

        current_date_time = datetime.datetime.now()
        current_timestamp = str(current_date_time.timestamp()).split(".")[0]

        # Get file name and extension
        target_machine_file = validated_data.pop('target_machine', None)
        target_machine_file_name, target_machine_file_extension = os.path.splitext(target_machine_file.name)

        # Rename the file
        target_machine_file_name = f"{ctf_id}_{current_timestamp}{target_machine_file_extension.lower()}"

        # Store the file in the specified directory
        with open(f"private_static/ctf_target_machines/{target_machine_file_name}", 'wb+') as destination:
            for chunk in target_machine_file.chunks():
                destination.write(chunk)

        ctf_values = {"$set": {
            "ctf_target_uploaded": True,
            "ctf_target_machine_name": target_machine_file_name,
            'ctf_updated_at': current_date_time
        }}
        ctf_update = ctf_game_collection.update_one({'ctf_id': ctf_id}, ctf_values)

        return validated_data

    class Meta:
        ref_name = 'CTFGameMachine'


class CTFGameDetailSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def get(self, ctf_id, user, user_id):
        assigned_games = user_profile_collection.find_one({"user_id": user_id}, {"_id": 0, "assigned_games": 1})
        if not assigned_games["assigned_games"]["display_all_ctf"] and ctf_id not in assigned_games["assigned_games"]["ctf"]:
            return {
                "errors": {
                    "non_field_errors": ["You are not authorised to view this game."]
                }
            }

        ctf_game = ctf_game_collection.find_one({'ctf_id': ctf_id}, {
            "_id": 0,
            "ctf_target_machine_name": 0,
            "ctf_attacker_machine_name": 0,
            "ctf_target_uploaded": 0,
            "ctf_is_approved": 0,
        })

        if not ctf_game:
            return {
                "errors": {
                    "non_field_errors": ["Invalid CTF Id"]
                }
            }

        ctf_flag_list = ctf_game.pop('ctf_flags', None)
        ctf_game['ctf_flag_count'] = len(ctf_flag_list)

        ctf_mapping = ctf_cloud_mapping_collection.find_one({'ctf_mapping_id': ctf_game['ctf_mapping_id']})
        if ctf_mapping:
            ctf_attacker_image = get_image_detail(ctf_mapping['ctf_attacker_image_id'])
            ctf_game['ctf_attacker_image_name'] = ctf_attacker_image.name if ctf_attacker_image else ""

            ctf_attacker_flavor = get_flavor_detail(ctf_mapping['ctf_attacker_flavor_id'])
            ctf_game['ctf_attacker_disk_size'] = str(round(ctf_attacker_flavor.disk)) + " GB"
            ctf_game['ctf_attacker_ram_size'] = str(round(ctf_attacker_flavor.ram)) + " MB"
            ctf_game['ctf_attacker_vcpus'] = str(ctf_attacker_flavor.vcpus)
        else:
            ctf_game['ctf_attacker_image_name'] = ""
            ctf_game['ctf_attacker_disk_size'] = ""
            ctf_game['ctf_attacker_ram_size'] = ""
            ctf_game['ctf_attacker_vcpus'] = ""

        if not isinstance(user, AnonymousUser):
            ctf_active_game = ctf_active_game_collection.find_one({'ctf_id': ctf_game['ctf_id'], 'user_id': user['user_id']})

            if ctf_active_game:
                ctf_game['ctf_game_id'] = ctf_active_game['ctf_game_id']
                ctf_game['ctf_is_ready'] = ctf_active_game['ctf_is_ready']

        # Included winning wall details
        player_count = ctf_game.get('ctf_players_count', 0)
        total_score = ctf_game.get('ctf_score', 0)

        if player_count == 0:
            ctf_game['winning_wall'] = []
        else:
            player_ids = ctf_game.get('ctf_solved_by', [])

            user_details_cursor = user_collection.find(
                {"user_id": {"$in": player_ids}},
                {"_id": 0, "user_id": 1, "user_full_name": 1, "user_role": 1, "user_avatar": 1}
            )

            user_details_dict = {user["user_id"]: user for user in user_details_cursor}

            winning_wall_data = []

            for player_id in player_ids:
                user_details = user_details_dict.get(player_id)
                ctf_details = ctf_player_arsenal_collection.find_one(
                    {"ctf_id": ctf_id, "user_id": player_id},
                    {"_id": 0, "ctf_score_obtained": 1, "updated_at": 1}
                )

                winning_wall_data.append({
                    "user_id": player_id,
                    "user_full_name": user_details["user_full_name"],
                    "user_avatar": user_details["user_avatar"],
                    "user_role": user_details["user_role"],
                    "ctf_score_obtained": round(ctf_details.get("ctf_score_obtained", 0)),
                    "score_obtained": str(round(ctf_details.get("ctf_score_obtained", 0))) + '/' + str(total_score),
                    "badge_earned": "Gold",
                    "date": ctf_details.get("updated_at", None),
                })

            sorted_winning_wall_data = sorted(winning_wall_data, key=lambda x: x["ctf_score_obtained"], reverse=True)

            ctf_game['winning_wall'] = sorted_winning_wall_data

        return ctf_game

    class Meta:
        ref_name = 'CTFGameDetail'


class CTFStartGameSerializer(serializers.Serializer):
    ctf_id = serializers.CharField(max_length=50, required=True, write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        data['user'] = self.context['request'].user
        user_id = data['user'].get('user_id')
        is_premium_user = data['user'].get('is_premium')

        assigned_games = user_profile_collection.find_one({"user_id": user_id}, {"_id": 0, "assigned_games": 1})
        if not assigned_games["assigned_games"]["display_all_ctf"] and data["ctf_id"] not in assigned_games["assigned_games"]["ctf"]:
            raise serializers.ValidationError("You are not authorised to start this game.")

        buffer_game = game_start_buffer_collection.find_one({"user_id": user_id})
        if buffer_game:
            raise serializers.ValidationError("Please Wait! Your machines are being created.")

        ctf_game = ctf_game_collection.find_one({"ctf_id": data['ctf_id']})
        if not ctf_game:
            raise serializers.ValidationError("Invalid CTF ID")

        if ctf_active_game_collection.find_one({"ctf_id": data['ctf_id'], "user_id": user_id, "ctf_is_ready": False}):
            raise serializers.ValidationError("Some operations are being performed. Please Wait!!")

        ctf_is_approved = ctf_game['ctf_is_approved']
        if not ctf_is_approved:
            raise serializers.ValidationError("This CTF game is still under inspection. Please try some different game.")

        ctf_active_game = ctf_active_game_collection.find_one({'user_id': user_id, 'ctf_id': data['ctf_id']})
        if ctf_active_game:
            raise serializers.ValidationError("You have already started this game. Please navigate to Active Games to resume it.")

        player_arsenal = ctf_player_arsenal_collection.find_one({'user_id': user_id, 'ctf_id': data['ctf_id']})
        if player_arsenal:
            if not is_premium_user:
                raise serializers.ValidationError("Upgrade your membership to replay this game.")
            # if is_premium_user:
            # if player_arsenal.get('ctf_score_obtained') == ctf_game['ctf_score']:
            #     raise serializers.ValidationError("You already finished this game. Please try another game.")
            # else:
            # raise serializers.ValidationError("Upgrade your membership to replay this game.")

        games_count = ctf_active_game_collection.count_documents({'user_id': user_id})
        if is_premium_user and games_count >= 3:
            raise serializers.ValidationError("Please finish your previous games to start a new game.")
        elif not is_premium_user and games_count >= 1:
            raise serializers.ValidationError("Upgrade your membership or finish your previous game to start a new game.")

        if ctf_game['ctf_for_premium_user'] and not is_premium_user:
            raise serializers.ValidationError("Upgrade your membership to play this game.")

        data["ctf_game"] = ctf_game

        return data

    def create(self, validated_data):
        user_id = validated_data['user']['user_id']
        ctf_mapping = ctf_cloud_mapping_collection.find_one({"ctf_id": validated_data['ctf_game'].get('ctf_id')}, {"_id": 0})
        ctf_name = validated_data['ctf_game'].get('ctf_name')

        buffer_id = generate_random_string('buffer_id', length=10)
        buffer = {
            "buffer_id": buffer_id,
            "user_id": user_id,
            "ctf_scenario_id": validated_data['ctf_id'],
            "created_at": datetime.datetime.utcnow()
        }
        game_start_buffer_collection.insert_one(buffer)

        create_ctf_game.delay(user_id, ctf_mapping, ctf_name)

        response = {}

        return response

    class Meta:
        ref_name = 'CTFStartGame'


class CTFGameConsoleSerializer(serializers.Serializer):
    ctf_game_id = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def get(self, ctf_game_id, user):
        active_game = ctf_active_game_collection.find_one({'ctf_game_id': ctf_game_id, 'user_id': user['user_id']}, {
            "ctf_game_id": 1,
            "ctf_mapping_id": 1,
            "user_id": 1,
            "ctf_start_time": 1,
            "ctf_end_time": 1,
            "ctf_target_private_ip": 1,
            "ctf_target_machine_id": 1,
            "ctf_attacker_private_ip": 1,
            "ctf_attacker_machine_id": 1,
            "ctf_flags_captured": 1,
            "ctf_game_created_at": 1,
            "ctf_game_updated_at": 1,
            "ctf_is_ready": 1
        })

        if not active_game:
            return {
                "errors": {
                    "non_field_errors": ["Invalid CTF Game Id"]
                }
            }

        if active_game['ctf_is_ready'] == False:
            raise serializers.ValidationError("Some operations are being performed. Please Wait!!")

        ctf_game = ctf_game_collection.find_one({'ctf_mapping_id': active_game['ctf_mapping_id']})
        active_game['ctf_name'] = ctf_game['ctf_name']
        active_game['ctf_description'] = ctf_game['ctf_description']
        active_game['ctf_flag_count'] = len(ctf_game['ctf_flags'])
        active_game['ctf_thumbnail'] = ctf_game['ctf_thumbnail']
        active_game['ctf_assigned_severity'] = ctf_game['ctf_assigned_severity']
        active_game['ctf_score'] = ctf_game['ctf_score']
        active_game['ctf_players_count'] = ctf_game['ctf_players_count']
        active_game['ctf_walkthrough'] = ctf_game['ctf_walkthrough'] if type(ctf_game['ctf_walkthrough']) == list else [ctf_game['ctf_walkthrough']]

        ctf_mapping = ctf_cloud_mapping_collection.find_one({'ctf_mapping_id': active_game['ctf_mapping_id']})
        active_game['ctf_attacker_username'] = ctf_mapping['ctf_attacker_username']
        active_game['ctf_attacker_password'] = ctf_mapping['ctf_attacker_password']

        # For creating a new console url for the attacker machine
        attacker_instance = get_cloud_instance(active_game['ctf_attacker_machine_id'])
        attacker_console = get_instance_console(attacker_instance)
        attacker_console_url = attacker_console.url
        active_game['ctf_attacker_console_url'] = attacker_console_url

        target_instance = get_cloud_instance(active_game['ctf_target_machine_id'])
        active_game['ctf_target_private_ip'] = get_instance_private_ip(target_instance)
        active_game.pop('ctf_target_machine_id', None)

        return active_game

    class Meta:
        ref_name = 'CTFGameConsole'


class CTFGameExtendTimeSerializer(serializers.Serializer):
    ctf_game_id = serializers.CharField(max_length=50, required=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        user = self.context['request'].user
        ctf_active_game = ctf_active_game_collection.find_one({'ctf_game_id': data['ctf_game_id'], 'user_id': user['user_id']}, {"_id": 0})

        if not ctf_active_game:
            raise serializers.ValidationError("Invalid Game ID")

        if ctf_active_game['ctf_time_extended']:
            if not user['is_premium']:
                raise serializers.ValidationError("Upgrade to Premium membership to extend the time again.")

        data["ctf_active_game"] = ctf_active_game

        return data

    def create(self, validated_data):
        ctf_end_time = validated_data["ctf_active_game"]["ctf_end_time"]
        datetime_object = datetime.datetime.fromtimestamp(ctf_end_time) + datetime.timedelta(minutes=15)
        updated_timestamp = datetime_object.timestamp()

        updated_values = {"$set": {
            "ctf_end_time": updated_timestamp,
            "ctf_time_extended": True,
            "ctf_game_updated_at": datetime.datetime.now()
        }}
        ctf_game_update = ctf_active_game_collection.update_one({'ctf_game_id': validated_data["ctf_game_id"]}, updated_values)

        response = {
            "ctf_game_id": validated_data["ctf_game_id"],
            "ctf_end_time": updated_timestamp
        }

        return response

    class Meta:
        ref_name = 'CTFGameExtendTime'


class CTFSubmitFlagSerializer(serializers.Serializer):
    ctf_game_id = serializers.CharField(max_length=25, required=True, write_only=True)
    ctf_flag = serializers.CharField(max_length=50, required=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        user_id = self.context['request'].user['user_id']
        ctf_active_game = ctf_active_game_collection.find_one({'ctf_game_id': data['ctf_game_id'], 'user_id': user_id}, {"_id": 0})

        if not ctf_active_game:
            raise serializers.ValidationError("Invalid CTF Game ID")

        data["ctf_active_game"] = ctf_active_game
        data['user_id'] = user_id
        return data

    def create(self, validated_data):

        ctf_game = ctf_game_collection.find_one({'ctf_id': validated_data['ctf_active_game'].get('ctf_id')})

        submitted_flag = validated_data['ctf_flag']
        ctf_flags = ctf_game.get('ctf_flags', [])
        ctf_flags_captured = validated_data['ctf_active_game'].get('ctf_flags_captured', [])

        if submitted_flag in ctf_flags_captured:
            message = "Flag Already Captured!"
            is_flag_correct = False
            all_flags_captured = False
        elif submitted_flag in ctf_flags:
            ctf_flags_captured.append(validated_data["ctf_flag"])

            all_flags_captured = len(ctf_flags_captured) == len(ctf_flags)
            message = "Congratulations! All Flags Captured" if all_flags_captured else "Kudos! You Captured a Flag"
            is_flag_correct = True
        else:
            message = "Better Luck Next Time"
            is_flag_correct = False
            all_flags_captured = False

        if is_flag_correct:
            ctf_update = ctf_active_game_collection.update_one(
                {'ctf_game_id': validated_data["ctf_game_id"]},
                {"$set": {
                    "ctf_flags_captured": ctf_flags_captured,
                    "ctf_game_updated_at": datetime.datetime.now()
                }
                }
            )

        response_to_return = {
            "ctf_game_id": validated_data["ctf_game_id"],
            "ctf_flag": submitted_flag,
            "message": message,
            "is_flag_correct": is_flag_correct,
            "all_flags_captured": all_flags_captured
        }

        if all_flags_captured:
            # Get the request object from the serializer's context
            request = self.context.get('request', None)
            jwt_token = request.META.get('HTTP_AUTHORIZATION', None)

            url = f'{API_URL}/api/ctf/game/delete/{validated_data["ctf_game_id"]}/'

            payload = {}
            headers = {'Content-Type': 'application/json', 'Authorization': jwt_token}
            response = requests.delete(url, json=payload, headers=headers)
            response = json.loads(response._content)
            response['ctf_flag'] = submitted_flag
            return response

        return response_to_return

    class Meta:
        ref_name = 'CTFSubmitFlag'


class CTFActiveGameListSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def get(self, user_id):
        ctf_active_game_count = ctf_active_game_collection.count_documents({'user_id': user_id, 'ctf_is_ready': True})

        if not ctf_active_game_count >= 1:
            return {
                "message": "No Active Games"
            }

        ctf_active_games = ctf_active_game_collection.find({'user_id': user_id, 'ctf_is_ready': True}, {"_id": 0})

        response = []
        for ctf_active_game in ctf_active_games:
            ctf_game = ctf_game_collection.find_one({'ctf_id': ctf_active_game['ctf_id']})
            ctf_category = ctf_category_collection.find_one({'ctf_category_id': ctf_game['ctf_category_id']})

            temp = ctf_active_game

            temp['ctf_flags_captured_count'] = len(ctf_active_game['ctf_flags_captured'])
            temp['ctf_flags_count'] = len(ctf_game['ctf_flags'])
            temp['ctf_name'] = ctf_game['ctf_name']
            temp['ctf_description'] = ctf_game['ctf_description']
            temp['ctf_thumbnail'] = ctf_game['ctf_thumbnail']
            temp['ctf_category_name'] = ctf_category['ctf_category_name']
            temp['ctf_creator_id'] = ctf_game['ctf_creator_id']
            temp['ctf_creator_name'] = ctf_game['ctf_creator_name']
            temp['ctf_assigned_severity'] = ctf_game['ctf_assigned_severity']
            temp['ctf_rated_severity'] = ctf_game['ctf_rated_severity']
            temp['ctf_score'] = ctf_game['ctf_score']
            temp['ctf_time'] = ctf_game['ctf_time']
            temp['ctf_players_count'] = ctf_game['ctf_players_count']

            response.append(temp)

        return response

    class Meta:
        ref_name = 'CTFActiveGameList'


class CTFDeleteGameSerializer(serializers.Serializer):

    def validate(self, data):
        request = self.context['request']
        ctf_game_id = self.context['view'].kwargs['ctf_game_id']
        user_id = request.user.get('user_id')
        if request.user.get("is_superadmin"):
            ctf_game = ctf_active_game_collection.find_one(
                {'ctf_game_id': ctf_game_id},
                {"_id": 0}
            )
        else:
            ctf_game = ctf_active_game_collection.find_one(
                {'ctf_game_id': ctf_game_id, "user_id": user_id},
                {"_id": 0}
            )

        if not ctf_game:
            raise serializers.ValidationError("Invalid CTF Game ID")

        if ctf_active_game_collection.find_one({'ctf_game_id': ctf_game_id, "user_id": user_id, 'ctf_is_ready': False}):
            raise serializers.ValidationError("Some operations are being performed. Please Wait!!")

        return data

    def update_player_arsenal(self, ctf_active_game, ctf_archive_game_id):
        current_time = datetime.datetime.now()

        ctf_game = ctf_game_collection.find_one({'ctf_id': ctf_active_game['ctf_id']})

        original_flags_count = len(ctf_game['ctf_flags'])
        captured_flags_count = len(ctf_active_game["ctf_flags_captured"])

        max_score = ctf_game['ctf_score']

        if captured_flags_count == 0:
            score_obtained = 0
        else:
            score_obtained = min(captured_flags_count / original_flags_count * max_score, max_score)

        score_obtained = round(score_obtained, 2)
        score_percentage = round((score_obtained / max_score) * 100, 2)

        if score_obtained == max_score:
            ctf_game_status = "owned"
            ctf_solved_by = ctf_game['ctf_solved_by']

            if ctf_active_game['user_id'] not in ctf_solved_by:
                ctf_solved_by.append(ctf_active_game['user_id'])
                ctf_players_count = int(ctf_game['ctf_players_count']) + 1

                updated_ctf_game = ctf_game_collection.update_one(
                    {'ctf_id': ctf_game['ctf_id']},
                    {'$set': {
                        'ctf_solved_by': ctf_solved_by,
                        'ctf_players_count': ctf_players_count,
                        'ctf_updated_at': current_time
                    }
                    }
                )

        elif score_percentage >= 65:
            ctf_game_status = "pass"
        else:
            ctf_game_status = "fail"

        ctf_players_arsenal = ctf_player_arsenal_collection.find_one(
            {'user_id': ctf_active_game['user_id'], 'ctf_id': ctf_game['ctf_id']},
            {'_id': 0}
        )

        if ctf_players_arsenal:
            ctf_archive_game_list = ctf_players_arsenal['ctf_archive_game_list']
            ctf_archive_game_list.append(ctf_archive_game_id)

            ctf_player_arsenal_collection.update_one(
                {'user_id': ctf_active_game['user_id'], 'ctf_id': ctf_game['ctf_id']},
                {'$set': {
                    'ctf_score_obtained': score_obtained,
                    'ctf_game_status': ctf_game_status,
                    'ctf_flags_captured': ctf_active_game['ctf_flags_captured'],
                    'ctf_archive_game_list': ctf_archive_game_list,
                    'ctf_arsenal_updated_at': current_time
                }
                }
            )
        else:
            arsenal_id = generate_random_string('arsenal_id', length=25)
            new_player_arsenal = {
                'arsenal_id': arsenal_id,
                'user_id': ctf_active_game['user_id'],
                'ctf_id': ctf_game['ctf_id'],
                'ctf_score_obtained': score_obtained,
                'ctf_game_status': ctf_game_status,
                'ctf_flags_captured': ctf_active_game['ctf_flags_captured'],
                'ctf_rated_severity': 0,
                'ctf_archive_game_list': [ctf_archive_game_id, ],
                'created_at': current_time,
                'updated_at': current_time
            }
            ctf_player_arsenal_collection.insert_one(new_player_arsenal)

        return score_obtained, max_score, ctf_game_status

    def update_user_profile(self, ctf_active_game):
        ctf_player_arsenal = ctf_player_arsenal_collection.find({'user_id': ctf_active_game['user_id']}, {'_id': 0})

        user_ctf_score = 0
        for game in ctf_player_arsenal:
            user_ctf_score += game['ctf_score_obtained']

            # For updating total score
        user_profile_update = user_profile_collection.update_one({'user_id': ctf_active_game['user_id']}, {'$set': {
            'user_ctf_score': user_ctf_score,
            'user_profile_updated_at': datetime.datetime.now()
        }})

    def delete_game(self, ctf_game_id, user_id):
        request = self.context['request']
        if request.user.get("is_superadmin"):
            ctf_active_game = ctf_active_game_collection.find_one(
                {'ctf_game_id': ctf_game_id},
                {"_id": 0}
            )
        else:
            ctf_active_game = ctf_active_game_collection.find_one(
                {'ctf_game_id': ctf_game_id, "user_id": user_id},
                {"_id": 0}
            )

        user_resource = user_resource_collection.find_one({"user_id": ctf_active_game['user_id']}, {"_id": 0})

        ctf_archive_game_id = generate_random_string('ctf_archive_game_id', length=35)

        ctf_score_obtained, ctf_score, ctf_game_status = self.update_player_arsenal(ctf_active_game, ctf_archive_game_id)
        self.update_user_profile(ctf_active_game)

        delete_ctf_game.delay(ctf_active_game, user_resource, ctf_archive_game_id)

        response = {
            "ctf_archive_game_id": ctf_archive_game_id,
            "ctf_id": ctf_active_game['ctf_id'],
            "ctf_score_obtained": ctf_score_obtained,
            "ctf_score": ctf_score,
            "ctf_game_status": ctf_game_status
        }

        return response

    class Meta:
        ref_name = 'CTFDeleteGame'


class CTFRatedSeveritySerializer(serializers.Serializer):
    ctf_id = serializers.CharField(max_length=50, required=True)
    ctf_rated_severity = serializers.IntegerField(max_value=5, min_value=1, required=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def update_ctf_severity(self, ctf_id):
        severity_key_dict = {
            1: 'very_easy',
            2: 'easy',
            3: 'medium',
            4: 'hard',
        }
        severity_dict = {
            "very_easy": 0,
            "easy": 0,
            "medium": 0,
            "hard": 0,
            "very_hard": 0,
        }
        total_rating = 0

        arsenals = ctf_player_arsenal_collection.find({'ctf_id': ctf_id})

        for game in arsenals:
            ctf_rated_severity = game['ctf_rated_severity']
            severity_dict[severity_key_dict.get(ctf_rated_severity, 'very_hard')] += 1
            total_rating += 1

        ctf_game_collection.update_one({'ctf_id': ctf_id}, {'$set': {
            'ctf_rated_severity': severity_dict,
            'ctf_rating_count': total_rating,
            'ctf_updated_at': datetime.datetime.now()
        }})

    def validate(self, data):
        user_id = self.context['request'].user['user_id']

        ctf_game = ctf_game_collection.find_one({'ctf_id': data['ctf_id']}, {"_id": 0})
        if not ctf_game:
            raise serializers.ValidationError("Invalid CTF ID")

        ctf_player_arsenal = ctf_player_arsenal_collection.find_one({'user_id': user_id, 'ctf_id': ctf_game['ctf_id']}, {'_id': 0})
        if not ctf_player_arsenal:
            raise serializers.ValidationError("You cannot rate this game. Play this game first to rate it.")

        data["ctf_player_arsenal"] = ctf_player_arsenal
        data['user_id'] = user_id

        return data

    def create(self, validated_data):

        ctf_players_arsenal = ctf_player_arsenal_collection.update_one(
            {'user_id': validated_data['ctf_player_arsenal'].get('user_id'), 'arsenal_id': validated_data['ctf_player_arsenal'].get('arsenal_id')},
            {'$set': {'ctf_rated_severity': validated_data['ctf_rated_severity']}}
        )

        self.update_ctf_severity(validated_data['ctf_id'])

        response = {
            'ctf_id': validated_data['ctf_id'],
            'ctf_rated_severity': validated_data['ctf_rated_severity']
        }

        return response

    class Meta:
        ref_name = 'CTFRatedSeverity'


class CTFGameListSerializer(serializers.Serializer):
    def get(self, category_id, user_id):
        if not ctf_category_collection.find_one({"ctf_category_id": category_id}):
            return {"errors": {"non_field_errors": ["Invalid CTF Category Id"]}}

        assigned_games = user_profile_collection.find_one({"user_id": user_id}, {"_id": 0, "assigned_games": 1})

        if not assigned_games["assigned_games"]["display_all_ctf"]:
            query = {"$in": assigned_games["assigned_games"]["ctf"]}
            if not assigned_games["assigned_games"]["display_locked_ctf"]:
                ctf_game_list = list(ctf_game_collection.find(
                    {"ctf_category_id": category_id, "ctf_is_approved": True, "ctf_id": query},
                    {"_id": 0,
                     "ctf_id": 1,
                     "ctf_name": 1,
                     "ctf_description": 1,
                     "ctf_flags": 1,
                     "ctf_thumbnail": 1,
                     "ctf_walkthrough": 1,
                     "ctf_time": 1,
                     "ctf_assigned_severity": 1,
                     "ctf_score": 1,
                     "ctf_for_premium_user": 1,
                     "ctf_is_challenge": 1,
                     'mitre_mapping': "",
                     'network_topology': ""
                     }))
            else:
                ctf_game_list = list(ctf_game_collection.find(
                    {"ctf_category_id": category_id, "ctf_is_approved": True},
                    {"_id": 0,
                     "ctf_id": 1,
                     "ctf_name": 1,
                     "ctf_description": 1,
                     "ctf_flags": 1,
                     "ctf_thumbnail": 1,
                     "ctf_walkthrough": 1,
                     "ctf_time": 1,
                     "ctf_assigned_severity": 1,
                     "ctf_score": 1,
                     "ctf_for_premium_user": 1,
                     "ctf_is_challenge": 1,
                     'mitre_mapping': "",
                     'network_topology': ""}))
                for game in ctf_game_list:
                    game['display'] = game['ctf_id'] in query['$in']
        else:
            ctf_game_list = list(ctf_game_collection.find(
                {"ctf_category_id": category_id, "ctf_is_approved": True},
                {"_id": 0,
                 "ctf_id": 1,
                 "ctf_name": 1,
                 "ctf_description": 1,
                 "ctf_flags": 1,
                 "ctf_thumbnail": 1,
                 "ctf_walkthrough": 1,
                 "ctf_time": 1,
                 "ctf_assigned_severity": 1,
                 "ctf_score": 1,
                 "ctf_for_premium_user": 1,
                 "ctf_is_challenge": 1,
                 'mitre_mapping': "",
                 'network_topology': ""
                 }))

        for game in ctf_game_list:
            game["no_of_flags"] = len(game["ctf_flags"])
            del game["ctf_flags"]

        return ctf_game_list

    class Meta:
        ref_name = 'CTFGameList'


class CTFTargetIPSerializer(serializers.Serializer):
    def get(self, ctf_game_id, user_id):
        ctf_active_game = ctf_active_game_collection.find_one({'ctf_game_id': ctf_game_id, 'user_id': user_id}, {'_id': 0})
        if not ctf_active_game:
            return {
                "errors": {
                    "non_field_errors": ["Invalid CTF Game Id"]
                }
            }
        if ctf_active_game.get("ctf_target_private_ip", ""):
            target_private_ip = ctf_active_game["ctf_target_private_ip"]
        else:
            target_instance = get_cloud_instance(ctf_active_game['ctf_target_machine_id'])
            target_private_ip = get_instance_private_ip(target_instance)
        return {'ctf_target_private_ip': target_private_ip}


class CTFLMSListSerializer(serializers.Serializer):
    def get(self):
        ctf_game_list = list(ctf_game_collection.find({'ctf_is_approved': True}, {"_id": 0, "ctf_id": 1, "ctf_name": 1, "ctf_description": 1}))
        return ctf_game_list


class CTFGetScoreByGameIdSerializer(serializers.Serializer):
    ctf_game_id = serializers.CharField(required=True, max_length=25)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        user_id = self.context['request'].user['user_id']
        ctf = ctf_active_game_collection.find_one({'ctf_game_id': data['ctf_game_id'], 'user_id': user_id})

        if ctf:
            data['ctf_archive_game_id'] = None
            data['ctf_score_obtained'] = 0
            data['message'] = "Game in progress"
        else:
            ctf_id = ctf_archive_game_collection.find_one({'ctf_game_id': data['ctf_game_id'], 'user_id': user_id},
                                                          {'ctf_id': 1, 'ctf_archive_game_id': 1})

            if ctf_id:
                ctf_score_obtained = ctf_player_arsenal_collection.find_one({'user_id': user_id, 'ctf_id': ctf_id['ctf_id']},
                                                                            {'ctf_score_obtained': 1})

                data['ctf_archive_game_id'] = ctf_id['ctf_archive_game_id']
                data['ctf_score_obtained'] = ctf_score_obtained.get('ctf_score_obtained', 0)
                data['message'] = "Game Over"
            else:
                raise serializers.ValidationError("Invalid CTF Game ID")

        data['ctf_id'] = ctf_id['ctf_id']

        return data

    def create(self, validated_data):
        return validated_data
