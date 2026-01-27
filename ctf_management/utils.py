import datetime
from asgiref.sync import async_to_sync
from celery import shared_task

from core.utils import generate_random_string, API_URL, FRONTEND_URL
from notification_management.utils import send_notification
from database_management.pymongo_client import (
    ctf_active_game_collection,
    user_resource_collection,
    ctf_archive_game_collection,
    ctf_game_collection,
    game_start_buffer_collection,
    notification_collection,
)
from cloud_management.utils import (
    get_cloud_network,
    get_cloud_router,
    get_cloud_subnet,
    get_cloud_instance,
    get_instance_private_ip,
    create_cloud_network,
    create_cloud_router,
    create_cloud_instance,
    connect_router_to_public_network,
    connect_router_to_private_network,
    disconnect_router_from_private_network,
    delete_cloud_instance,
    delete_cloud_router,
    delete_cloud_network
 )
from django.core.exceptions import ValidationError


@shared_task
def create_ctf_game(user_id, ctf_mapping, ctf_name):
    target_image_id = ctf_mapping['ctf_target_image_id']
    target_flavor_id = ctf_mapping['ctf_target_flavor_id']
    attacker_image_id = ctf_mapping['ctf_attacker_image_id']
    attacker_flavor_id = ctf_mapping['ctf_attacker_flavor_id']
    ctf_time = ctf_mapping['ctf_time']
    ctf_mapping_id = ctf_mapping['ctf_mapping_id']

    # For generating unique random Game Id
    ctf_game_id = generate_random_string('ctf_game_id', length=25)

    user_resource = user_resource_collection.find_one({"user_id": user_id})
    if user_resource:
        network = get_cloud_network(user_resource['network_id'])
        subnet = get_cloud_subnet(user_resource['subnet_id'])
        router = get_cloud_router(user_resource['router_id'])
        user_resource_id = user_resource['user_resource_id']
        new_user_resource = False
    else:
        network, subnet = create_cloud_network(user_id)
        router = create_cloud_router(user_id)
        updated_router = connect_router_to_public_network(router)
        connect_router_to_private_network(updated_router, subnet)
        user_resource_id = generate_random_string('user_resource_id', length=10)
        new_user_resource = True
        
    # Creating Target Machine Server
    target_instance_name = user_id + "_" + ctf_game_id +  "_target"
    target_cloud_instance, target_ip = create_cloud_instance(target_instance_name, target_image_id, target_flavor_id, network.id)

    target_cloud_instance = get_cloud_instance(target_cloud_instance.id)
    if not target_ip:
        target_ip = get_instance_private_ip(target_cloud_instance)

    # Creating Attacker Machine Server
    attacker_instance_name = user_id + "_" + ctf_game_id + "_attacker"
    attacker_cloud_instance, attacker_ip = create_cloud_instance(attacker_instance_name, attacker_image_id, attacker_flavor_id, network.id)

    attacker_cloud_instance = get_cloud_instance(attacker_cloud_instance.id)
    if not attacker_ip:
        attacker_ip = get_instance_private_ip(attacker_cloud_instance)

    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(hours=ctf_time)

    ctf_active_game = {
        "ctf_game_id": ctf_game_id,
        "user_id": user_id,
        "ctf_mapping_id": ctf_mapping_id,
        "ctf_id": ctf_mapping['ctf_id'],
        "ctf_start_time": start_time.timestamp(),
        "ctf_end_time": end_time.timestamp(),
        "ctf_time_extended": False,
        "ctf_flags_captured": [],
        "ctf_target_machine_id": target_cloud_instance.id,
        "ctf_target_private_ip": target_ip,
        "ctf_attacker_machine_id": attacker_cloud_instance.id,
        "ctf_attacker_private_ip": attacker_ip,
        "user_resource_id": user_resource_id,
        "ctf_game_created_at": start_time,
        "ctf_game_updated_at": start_time,
        "ctf_is_ready": True
    }
    ctf_active_game_collection.insert_one(ctf_active_game)

    if new_user_resource:
        user_resource_detail = {
            "user_resource_id": user_resource_id,
            "user_id": user_id,
            "network_id": network.id,
            "subnet_id": subnet.id,
            "router_id": router.id,
            "ctf_active_game_list": [ctf_game_id,],
            "user_resource_created_at": start_time,
            "user_resource_updated_at": start_time
        }
        user_resource_collection.insert_one(user_resource_detail)
    else:
        ctf_active_game_list = user_resource['ctf_active_game_list']
        ctf_active_game_list.append(ctf_game_id)
        update_user_resource_detail = {"$set": {
            "ctf_active_game_list": ctf_active_game_list,
            "user_resource_updated_at": start_time,
        }}
        user_resource_collection.update_one({"user_resource_id": user_resource_id}, update_user_resource_detail)
    
    response = {
        "ctf_game_id": ctf_game_id
    }

    game_start_buffer_collection.delete_one({"user_id": user_id})

    notification = {
        "type": "redirection",
        "title": f"{ctf_name} CTF Started",
        "description": f"{ctf_name} CTF started successfully.",
        "timestamp": start_time,
        "user_id": user_id,
        "action_urls": [],
        "redirection_url": "/activegame",
    }
    notification_collection.insert_one(notification)
    
    async_to_sync(send_notification)(group_name=user_id)
    
    # async_to_sync(send_notification)(group_name=user_id, message=f"CTF {ctf_name} is ready. Navigate CTF Arena > Active Machine in order to play the game.")


@shared_task
def delete_ctf_game(ctf_active_game, user_resource, ctf_archive_game_id):
    ctf_active_game_collection.update_one({"ctf_game_id": ctf_active_game['ctf_game_id']}, {"$set": {"ctf_is_ready":False}})

    target_cloud_instance = get_cloud_instance(ctf_active_game['ctf_target_machine_id'])
    if target_cloud_instance:
        deleted_target_cloud_instance = delete_cloud_instance(target_cloud_instance)

    attacker_cloud_instance = get_cloud_instance(ctf_active_game['ctf_attacker_machine_id'])
    if attacker_cloud_instance:
        deleted_attacker_cloud_instance = delete_cloud_instance(attacker_cloud_instance)

    current_time = datetime.datetime.now()
    
    if len(user_resource['ctf_active_game_list']) == 1 and ctf_active_game['ctf_game_id'] in user_resource['ctf_active_game_list']:
        user_resource_collection.delete_one({"user_id": ctf_active_game['user_id']})
        disconnect_router_from_private_network(user_resource['router_id'], user_resource['subnet_id'])
        delete_cloud_router(user_resource['router_id'])
        delete_cloud_network(user_resource['network_id'], user_resource['subnet_id'])
    else:
        ctf_active_game_list = user_resource['ctf_active_game_list']
        ctf_active_game_list.remove(ctf_active_game['ctf_game_id'])
        user_resource_collection.update_one({"user_id": ctf_active_game['user_id']}, {
            "$set": {
                "ctf_active_game_list": ctf_active_game_list,
                "user_resource_updated_at": current_time
            }}
        )

    ctf_active_game_collection.delete_one({ "ctf_game_id": ctf_active_game['ctf_game_id']})

    ctf_archive_game = {
        "ctf_archive_game_id": ctf_archive_game_id,
        "ctf_archive_created_at": current_time,
        "ctf_archive_updated_at": current_time,
    }
    ctf_archive_game.update(ctf_active_game)
    ctf_archive_game_collection.insert_one(ctf_archive_game)
    
    ctf_game = ctf_game_collection.find_one({'ctf_id': ctf_active_game['ctf_id']}, {'_id': 0,'ctf_name':1})

    notification = {
        "type": "information",
        "title": f"{ctf_game['ctf_name']} CTF Deleted.",
        "description": f"{ctf_game['ctf_name']} CTF deleted successfully.",
        "timestamp": datetime.datetime.now(),
        "user_id": ctf_active_game['user_id'],
        "action_urls": [],
        "redirection_url": "",
    }

    notification_collection.insert_one(notification)
    async_to_sync(send_notification)(group_name=ctf_active_game['user_id'])
    
    # async_to_sync(send_notification)(group_name=ctf_active_game['user_id'], message=f"CTF {ctf_game.get('ctf_name')} is deleted successfully. View your profile to check out the score obtained.")
    

def validate_file_size(file):
    max_size = 5 * 1024 * 1024  # 5 MB in bytes
    if file.size > max_size:
        raise ValidationError(f"File size should not exceed {max_size / (1024 * 1024)} MB.")