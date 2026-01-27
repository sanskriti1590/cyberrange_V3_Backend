import datetime

from celery import shared_task
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from asgiref.sync import async_to_sync

from notification_management.utils import send_notification
from core.utils import EMAIL_LOGO_URL, generate_random_string, API_URL, FRONTEND_URL
from database_management.pymongo_client import (
    scenario_collection,
    user_collection,
    scenario_invitation_collection,
    notification_collection,
    scenario_active_game_collection,

)
from cloud_management.utils import (
    create_cloud_network,
    create_cloud_router,
    connect_router_to_public_network,
    get_cloud_subnet,
    connect_router_to_private_network,
    create_cloud_instance,    
)

import re 


def remove_html_tags(text): 
    clean = re.compile('<.*?>') 
    return re.sub(clean, '', text) 


@shared_task
def send_invitation_by_email(invitation_mailing_detail):
    logo_url = EMAIL_LOGO_URL

    subject = 'Cyber Range Platform - Game Invitation'
    from_email = 'support@bhumiitech.com'
    recipient_list = [invitation_mailing_detail['player_email'],]

    # Render the HTML template with OTP
    html_content = render_to_string('scenario_invitation_template.html', {'logo_url': logo_url, 'data': invitation_mailing_detail})

    # Create the email message object
    msg = EmailMultiAlternatives(subject, '', from_email, recipient_list)
    msg.attach_alternative(html_content, "text/html")

    # Send the email
    msg.send()


def convert_score(score_str):
    parts = score_str.split("/")
    if len(parts) == 2:
        numerator = parts[0]
        if numerator == '0':
            return int(numerator)
        elif numerator.replace(".", "", 1).isdigit():
            return float(numerator)
    return 0


@shared_task
def create_scenario_game(validated_data):
    scenario_participants = []
    invitations = []

    scenario_instances_detail = scenario_collection.find_one({"scenario_id": validated_data["scenario_id"]}, {"scenario_infra.instances.instance_for": 1, "scenario_infra.instances.instance_name": 1, "_id": 0})['scenario_infra']['instances']
    player_instance_dict = {}

    for player_info in validated_data['scenario_players_info']:
        scenario_invitation_id = generate_random_string('scenario_invitation_id', length=15)
        player = user_collection.find_one({'email': player_info['player_email']})
        current_datetime = datetime.datetime.now()

        player_role = next((item for item in scenario_instances_detail if item['instance_name'] == player_info["player_instance"]), None)['instance_for']

        player_instance_dict[player_info["player_instance"]] = player['user_id']

        invitation = {
            'scenario_invitation_id': scenario_invitation_id,
            'scenario_id': validated_data['scenario'].get('scenario_id'),
            'scenario_name': validated_data['scenario'].get('scenario_name'),
            'scenario_game_owner_id': validated_data['user'].get('user_id'),
            'scenario_participant_id': player['user_id'],
            'scenario_participant_role': player_role,
            'scenario_invitation_accepted': False,
            'scenario_invitation_denied': False,
            'scenario_invitation_created_at': current_datetime,
            'scenario_invitation_updated_at': current_datetime
        }
        scenario_invitation_collection.insert_one(invitation)
        invitations.append(invitation)

        invitation_mailing_detail = {
            'scenario_name': validated_data['scenario'].get('scenario_name'),
            'player_name': player['user_full_name'],
            'game_owner': validated_data['user'].get('user_full_name'),
            'accept_invitation_url': f"{API_URL}/api/scenario/invitation/accept/{scenario_invitation_id}/",
            'deny_invitation_url': f"{API_URL}/api/scenario/invitation/deny/{scenario_invitation_id}/",
            'scenario_time': validated_data['scenario'].get('scenario_time'),
            'player_instance': player_role,
            'scenario_description': remove_html_tags(validated_data['scenario'].get('scenario_description')),
            'player_email': player['email'],
            'url': "https://cyberrange.bhumiitech.com/ActiveGameSenario"
        }
        send_invitation_by_email.delay(invitation_mailing_detail)

        temp = {
            'scenario_participant_id': player['user_id'],
            'scenario_participant_role': player_role,
            'scenario_flags_captured': [],
            'scenario_invitation_id': scenario_invitation_id
        }
        scenario_participants.append(temp)

    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(hours=validated_data['scenario'].get('scenario_time'))
    
    scenario_game_id = generate_random_string('scenario_game_id', length=25)
    scenario_active_game = {
        'scenario_game_id': scenario_game_id,
        'scenario_id': validated_data['scenario'].get('scenario_id'),
        'scenario_game_owner_id': validated_data['user'].get('user_id'),
        'scenario_start_time': start_time,
        'scenario_end_time': end_time,
        'scenario_flags_captured': [],
        'scenario_participants': scenario_participants,
        'scenario_user_resource': {},
        'scenario_game_created_at': start_time,
        'scenario_game_updated_at': start_time,
        'scenario_is_ready': False
    }

    scenario_active_game_collection.insert_one(scenario_active_game)

    scenario_infra = validated_data['scenario'].get('scenario_infra')
    scenario_networks = scenario_infra.get('networks')
    scenario_routers = scenario_infra.get('routers')
    scenario_instances = scenario_infra.get('instances')

    network_subnet_dict = {}
    network_dict = {}

    # Creating Networks
    scenario_infra_networks = []
    for scenario_network in scenario_networks:
        network_name = scenario_network.get('network_name')
        subnet_name = scenario_network.get('subnet_name')
        subnet_cidr = scenario_network.get('subnet_cidr')

        network, subnet = create_cloud_network(subnet_cidr=subnet_cidr,  network_name=network_name, subnet_name=subnet_name)
        
        temp = {
            'network_name': network_name,
            'network_id': network.id,
            'subnet_name': subnet_name,
            "subnet_id": subnet.id,
        }
        scenario_infra_networks.append(temp)

        network_subnet_dict[network_name] = subnet.id
        network_dict[network_name] = network.id

    # Creating Routers
    scenario_infra_routers = []
    for scenario_router in scenario_routers:
        router_name = scenario_router.get('router_name')
        external_gateway_connected = scenario_router.get('external_gateway_connected')
        internal_interfaces = scenario_router.get('internal_interfaces')

        router = create_cloud_router(router_name=router_name)

        if external_gateway_connected:
            updated_router = connect_router_to_public_network(router)
            router = updated_router

        internal_subnet_id_list = []
        for internal_interface in internal_interfaces:
            internal_subnet_id = network_subnet_dict[internal_interface]
            internal_subnet = get_cloud_subnet(internal_subnet_id)
            connect_router_to_private_network(router, internal_subnet)
            internal_subnet_id_list.append(internal_subnet_id)
    
        temp = {
            'router_id': router.id,
            "internal_subnet_id_list": internal_subnet_id_list,
        }
        scenario_infra_routers.append(temp)


    # Creating Instances
    scenario_infra_instances = []
    for scenario_instance in scenario_instances:
        instance_name = scenario_instance.get('instance_name')
        network_location = scenario_instance.get('network_location')
        image_id = scenario_instance.get('image_id')
        flavor_id = scenario_instance.get('flavor_id')
        instance_for = scenario_instance.get('instance_for')
        
        cloud_instance, instance_ip = create_cloud_instance(instance_name, image_id, flavor_id, network_dict[network_location])
        last_user_id = player_instance_dict[instance_name]
        
        temp = {
            'instance_id': cloud_instance.id,
            'instance_name': instance_name,
            'instance_user': last_user_id,
            'instance_user_role': instance_for,
            'image_id': image_id,
            'instance_ip': instance_ip
        }
        scenario_infra_instances.append(temp)        

    # Creating Scenario User Resources Collection Record
    scenario_user_resource = {
        'scenario_infra_networks': scenario_infra_networks,
        'scenario_infra_routers': scenario_infra_routers,
        'scenario_infra_instances': scenario_infra_instances,
        'scenario_user_resource_created_at': datetime.datetime.now(),
        'scenario_user_resource_updated_at': datetime.datetime.now()
    }
    
    scenario_active_game_collection.update_one(
        {'scenario_game_id': scenario_active_game['scenario_game_id']}, 
        {'$set': {'scenario_user_resource': scenario_user_resource,'scenario_is_ready':True}}
    )

    for invitation in invitations:
        notification = {
            "type": "action",
            "title": f"{invitation['scenario_name']} Scenario Started",
            "description": f"{invitation['scenario_name']} Scenario started successfully.",
            "timestamp": start_time,
            "user_id": invitation["scenario_participant_id"],
            "action_urls": [
                {
                    "action_name": "Accept",
                    "action_url": f"{API_URL}/scenario/invitation/accept/{invitation['scenario_invitation_id']}/"
                },
                {
                    "action_name": "Deny",
                    "action_url": f"{API_URL}/scenario/invitation/deny/{invitation['scenario_invitation_id']}/"
                }
            ],
            "redirection_url": "/ActiveGameSenario",
        }

        notification_collection.insert_one(notification)
        async_to_sync(send_notification)(group_name=invitation["scenario_participant_id"])