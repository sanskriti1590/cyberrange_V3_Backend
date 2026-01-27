import string
import random
import socket
import whois
import requests
import time

from database_management.pymongo_client import id_collection, ctf_active_game_collection, scenario_active_game_collection
from celery import shared_task
from django.conf import settings


API_URL = settings.API_URL
FRONTEND_URL = settings.FRONTEND_URL 
EMAIL_LOGO_URL = settings.EMAIL_LOGO_URL 
NEWS_API_KEY = settings.NEWS_API_KEY 

BLACKLISTED_DOMAINS_URL = settings.BLACKLISTED_DOMAINS_URL
WHITELISTED_DOMAINS_URL = settings.WHITELISTED_DOMAINS_URL

BLACKLISTED_REGISTRARS = [
    'porkbun',
    'internet',
    'namesilo',
    'namecheap',
    'cloudflare',
    'eurodns',
    'key-systems',
    'тов',
    'cv.',
    'hosting',
    'gname.com',
    'nominalia',
    'dynadot',
]

BLACKLISTED_DOMAINS = []


def generate_random_string(id_type, length=10):

    letters_and_digits = string.ascii_letters + string.digits

    id = ''.join(random.choice(letters_and_digits) for i in range(length))

    while id_collection.find_one({'id': id, 'id_type': id_type}):
        id = ''.join(random.choice(letters_and_digits) for i in range(length))

    id_obj = {
        'id': id,
        'id_type': id_type
    }
    id_collection.insert_one(id_obj)

    return id


@shared_task(bind = True)
def update_blacklisted_domains(self):
    filename = r"./blacklisted_domains.txt"
    with open(filename, 'r') as file:
        stored_content = file.read().splitlines()
 
    response = requests.get(BLACKLISTED_DOMAINS_URL)
    latest_content = response.text.split()
    blacklisted_domains = list(set(stored_content + latest_content))

    with open(filename, 'w') as file:
        file.write('\n'.join(blacklisted_domains))

    global BLACKLISTED_DOMAINS
    BLACKLISTED_DOMAINS = blacklisted_domains

    return "Blacklisted Domains Updated Successfully."

 
def get_registrar(domain):
    try:
        w = whois.whois(domain)
        return w.registrar
    except whois.parser.PywhoisError:
        return None

def is_domain_valid(domain, blaclisted_domains=[]):
    if domain in WHITELISTED_DOMAINS_URL:
        return True
    elif domain in BLACKLISTED_DOMAINS:
        return False
    else:
        try:
            socket.gethostbyname(domain)
            return True
        except socket.gaierror:
            return False

def is_email_valid(email):
    domain = email.split('@')[1]
    flag = False

    try:
        if domain in WHITELISTED_DOMAINS_URL:
            flag = True
        elif is_domain_valid(domain):
            registrar = get_registrar(domain)
            if registrar:
                registrar_first_name = registrar.split()[0].split(",")[0]
                if registrar_first_name.lower() not in BLACKLISTED_REGISTRARS:
                    flag = True
    except Exception:
        flag = False

    return flag


def auto_login():
    credentials_data = {"email":settings.USER_EMAIL,"password":settings.USER_PASSWORD}
    url = f"{API_URL}/api/user/login/"
    headers = {'content-type' : 'application/json'}
    response = requests.post(url, json= credentials_data, headers=headers)
    return response.json()["access_token"]

def auto_delete_service_in_openstack(ctf_game_id):
    token = auto_login()
    url = f"{API_URL}/api/core/game/force/delete/{ctf_game_id}/"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(url, headers= headers)
    return response

@shared_task(bind = True)
def game_auto_delete_in_30_min(self):
    ctf_active_game_list = list(ctf_active_game_collection.find({},{"_id":0,"ctf_game_id":1,"ctf_end_time":1}))

    active_game_id_list = list()
    error_list = list()
    for active_game in ctf_active_game_list:
        actual_time_remaining = active_game["ctf_end_time"] - time.time()
        if actual_time_remaining <= 0 :
            delete_response = auto_delete_service_in_openstack(active_game["ctf_game_id"])
            if delete_response.status_code == 202:
                active_game_id_list.append(active_game["ctf_game_id"])
            else:
                error_list.append(active_game["ctf_game_id"])
    
    if ctf_active_game_list and active_game_id_list:
        response = {
            "message" : "Games Delete Successfully.",
            "ctf_game_id_list" : active_game_id_list,
            "error_list" : error_list,
        }
        return response
    else:
        response = {
            "message" : "No pending games to delete.",
            "ctf_game_id_list" : [],
            "error_list" : error_list,
        }
        return response

############################
### Commented Now later use
   
# def scenario_auto_delete_service_in_openstack(scenario_game_id):
#     token = auto_login()
#     url = f"{API_URL}/api/core/scenario/game/force/delete/{scenario_game_id}/"
#     headers = {"Authorization": f"Bearer {token}"}
#     response = requests.delete(url, headers= headers)

# @shared_task(bind = True)
# def scenario_game_auto_delete_in_30_min(self):
#     scenario_active_game_list = list(scenario_active_game_collection.find({},{"_id":0,"scenario_game_id":1,"scenario_end_time":1}))

#     active_game_id_list = list()
#     for active_game in scenario_active_game_list:
#         actual_time_remaining = active_game["scenario_end_time"] - time.time()
#         if actual_time_remaining <= 0 :
#             scenario_auto_delete_service_in_openstack(active_game["scenario_game_id"])
#             active_game_id_list.append(active_game["scenario_game_id"])
    
#     if active_game_id_list:
#         response = {
#             "message" : "Scenario Games Delete Successfully.",
#             "scenario_game_id_list" : active_game_id_list
#         }
#         return response
#     else:
#         response = {
#             "message" : "No pending scenario games to delete.",
#             "scenario_game_id_list" : []
#         }
#         return response
