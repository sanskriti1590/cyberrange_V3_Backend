import math
import datetime, os, ipaddress, logging
from asgiref.sync import async_to_sync
from celery import shared_task
from notification_management.utils import send_notification
from fpdf  import FPDF
import pandas as pd
import json
import random
from pathlib import Path

from django.conf import settings
from core.utils import generate_random_string
from database_management.pymongo_client import (
    corporate_scenario_collection,   
    flag_data_collection,
    milestone_data_collection,
    user_collection,
    participant_data_collection,
    active_scenario_collection,
    archive_participant_collection,
    notification_collection,
archive_scenario_collection
)
from cloud_management.utils import (
    create_cloud_network,
    create_cloud_router,
    create_cloud_instance,
    connect_router_to_private_network,
    connect_router_to_public_network,
    get_cloud_subnet,
    get_cloud_instance,
    delete_cloud_instance,
    disconnect_router_from_private_network,
    get_cloud_router,
    delete_cloud_router,
    delete_cloud_network,
)


from database_management.pymongo_client import notification_collection,participant_data_collection
from core.utils import generate_random_string
from channels.layers import get_channel_layer

NARRATIVE_PATH = Path(
    settings.BASE_DIR / "corporate_management" / "report_narratives"
)
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Scenario Report', 0, 1, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(10)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, body)
        self.ln()
        
    def add_table(self, df):
        self.set_font("Arial", size=10)
        row_height = self.font_size * 2  # Increased row height for readability

        for _, row in df.iterrows():
            for col in df.columns:
                # Print column name
                self.cell(40, row_height, col, border=1)
                # Print column value, ensure it's converted to string
                self.cell(80, row_height, str(row[col]), border=1)
                self.ln(row_height)  # Move to the next line after each key-value pair
            self.ln(row_height)

    def add_circle(self, x, y, radius, color):
        if color == "green":
            self.set_fill_color(0, 255, 0)  # Green color
        elif color == "yellow":
            self.set_fill_color(255, 255, 0)  # Yellow color
        else:
            self.set_fill_color(255, 0, 0)  # Red color
        self.ellipse(x - radius, y - radius, 2 * radius, 2 * radius, style='F')



def add_scenario_details(pdf, scenario_details):
    # Add scenario thumbnail
    thumbnail_x = 10
    thumbnail_y = pdf.get_y() + 10
    thumbnail_width = 50
    thumbnail_height = 50
    thumbnail_url = scenario_details['thumbnail_url']
    # pdf.image(scenario_details['thumbnail_url'], x=thumbnail_x, y=thumbnail_y, w=thumbnail_width, h=thumbnail_height)
    thumbnail_path = thumbnail_url.split('cyberrangebackend1.bhumiitech.com')[1]  # Extract path after 'static'
    pdf.image(thumbnail_path, x=thumbnail_x, y=thumbnail_y, w=thumbnail_width, h=thumbnail_height)

    # Set font for scenario details
    pdf.set_font("Arial", size=12, style='B')

    # Add scenario name
    pdf.set_xy(thumbnail_x + thumbnail_width + 5, thumbnail_y + 3)
    name = f"Scenario: {scenario_details['name']}"
    name_height = math.ceil(len(name) / 44) * 5
    pdf.multi_cell(100, 0, name)

    # Add description
    description_text = f"Description: {scenario_details['description']}"
    description_height = math.ceil(len(description_text) / 44) * 5  # Calculate description height
    pdf.set_xy(thumbnail_x + thumbnail_width + 5, thumbnail_y + name_height + 5)
    pdf.multi_cell(100, 5, description_text)

    # Add severity
    severity_text = f"Severity: {scenario_details['severity']}"
    severity_height = math.ceil(len(severity_text) / 44) * 5
    pdf.set_xy(thumbnail_x + thumbnail_width + 5, thumbnail_y + name_height + description_height + 10)
    pdf.multi_cell(100, 5, severity_text)

    # Add objective
    objective_text = f"Objective: {scenario_details['objective']}"
    objective_height = math.ceil(len(objective_text) / 44) * 5  # Calculate objective height
    pdf.set_xy(thumbnail_x + thumbnail_width + 5, thumbnail_y + name_height + description_height + severity_height + 15)
    pdf.multi_cell(100, 5, objective_text)

    # Add prerequisite
    prerequisite_text = f"Prerequisite: {scenario_details['prerequisite']}"
    pdf.set_xy(thumbnail_x + thumbnail_width + 5, thumbnail_y + 10 + name_height + description_height + severity_height + objective_height + 10)
    pdf.multi_cell(100, 5, prerequisite_text)

    pdf.ln(300)  # Move to the next line after the thumbnail and scenario details

def add_section(pdf, participant_name, team, data_df, max_rows_per_page, is_flag_section):
    # Participant Name and Team
    pdf.set_font("Arial", size=12, style='B')
    participant_name = participant_name[0].capitalize() + participant_name[1:].lower()
    pdf.cell(0, 10, f"Participant: {participant_name}", ln=True, align='L')
    team = team[0].capitalize() + team[1:].lower()
    pdf.multi_cell(0, 15, f"Team: {team}", align='L')

    # Divide the data into chunks to fit on pages
    data_chunks = [data_df[i:i + max_rows_per_page] for i in range(0, len(data_df), max_rows_per_page)]

    for chunk in data_chunks:
        # Draw rectangular boxes
        max_circle_radius = 5
        box_width = 160  # Adjust as needed
        box_height = 25  # Adjust as needed
        initial_x = 20
        initial_y = pdf.get_y() + 10

        # Initialize coordinates for connecting lines
        last_circle_x = initial_x + 20
        last_circle_y = initial_y + 10

        for index, row in chunk.iterrows():
            x = initial_x
            y = initial_y + (index % max_rows_per_page) * (box_height + 10)

            # Check if index is a multiple of max_rows_per_page and not the first entry
            if index % max_rows_per_page == 0 and index != 0:
                y = initial_y  # Reset y coordinate to the top of the page

            # Draw circle for status
            circle_x = x + 20
            circle_y = y + 12
            color = "green" if is_flag_section and row['submitted_response'] else \
                    "green" if not is_flag_section and row['is_approved'] == "Yes" and row['is_achieved'] == "Yes" else \
                    "red" if is_flag_section and not row['submitted_response'] else \
                    "yellow" if not is_flag_section and (row['is_approved'] == "Yes" or row['is_achieved'] == "Yes") else \
                    "red"
            pdf.add_circle(circle_x, circle_y, radius=max_circle_radius, color=color)
            # pdf.ellipse(x=circle_x,y=circle_y,w=5,h=5,style='R')

            # Draw a line connecting circles except for the first one
            if index > 0 and index % max_rows_per_page != 0:
                pdf.set_draw_color(0, 0, 0)  # Set draw color to black
                pdf.line(last_circle_x, last_circle_y + 5, circle_x, circle_y - 5)

            # Update coordinates for the next iteration
            last_circle_x = circle_x
            last_circle_y = circle_y

            # Add index number inside the circle
            pdf.set_font("Arial", size=14)
            text_width = pdf.get_string_width(str(index + 1))  # Get width of the index text
            pdf.text(circle_x - text_width / 2, circle_y + 2, str(index + 1))  # Center text inside the circle

            # Add details inside the rectangular box
            pdf.set_font("Arial", size=10)
            pdf.set_text_color(0, 0, 0)  # Set text color to black
            if is_flag_section:
                pdf.text(x + 40, y + 5, f"Flag Hint: {row['flag_hint']}")
                pdf.text(x + 40, y + 10, f"Flag Question: {row['flag_question'][:40]}{'...' if len(row['flag_question']) > 40 else ''}")
                pdf.text(x + 40, y + 15, f"Flag Answer: {row['flag_answer'][:40]}{'...' if len(row['flag_answer']) > 40 else ''}")
                pdf.text(x + 40, y + 20, f"Submitted Response: {row['submitted_response']}")
            else:
                pdf.text(x + 40, y + 5, f"Milestone Name: {row['milestone_name']}")
                pdf.text(x + 40, y + 10, f"Description: {row['milestone_description'][:40]}{'...' if len(row['milestone_description']) > 40 else ''}")
                pdf.text(x + 40, y + 15, f"Hint Used: {row['hint_used']}")
            pdf.text(x + 40, y + 25 if is_flag_section else y + 20, f"Score: {row['score']}")

        # Add a new page for the next chunk of data
        pdf.add_page()

    # Add some space after the section
    pdf.ln(20)

def generate_report_for_participant(pdf, user_id, p_data_id):
    p_data = archive_participant_collection.find_one({"id": p_data_id})
    # user = prod_db.get_collection('user_collection').find_one({'user_id': user_id})
    user = user_collection.find_one({'user_id': user_id})
    user_name = user['user_full_name']
    if p_data:
        # Correctly fetching milestone data for each participant
        if 'flag_data' in p_data:
            flag_docs = []
            for flag_info in p_data.get('flag_data', []):
                flag_id = flag_info.get('flag_id')
                if flag_id:
                    flag = flag_data_collection.find_one({"id": flag_id})
                    if flag:
                        flag['submitted_response'] = flag_info.get('submitted_response', [])
                        flag['obtained_Score'] = flag_info.get('obtained_score', 0)
                        flag_docs.append(flag)

            if flag_docs:
                transformed_docs = [{
                'flag_hint': doc.get('hint', ''),
                'flag_question': doc.get('question', ''),
                'flag_answer': doc.get('answer', ''),
                'hint_used': "Yes" if doc.get('hint_used') else "No",
                'submitted_response': doc.get('submitted_response', []),
                'score':f"{doc.get('obtained_score', 0)}/{doc.get('score', 0)}"
            } for doc in flag_docs]

            flag_df = pd.DataFrame(transformed_docs)

            add_section(pdf, user_name, p_data['team'], flag_df, max_rows_per_page=6, is_flag_section=True)

        elif 'milestone_data' in p_data:
            milestone_docs = []
            for milestone_info in p_data.get('milestone_data', []):
                milestone_id = milestone_info.get('milestone_id')
                if milestone_id:
                    milestone = milestone_data_collection.find_one({"id": milestone_id})
                    if milestone:
                        milestone['is_approved'] = milestone_info.get('is_approved', False)
                        milestone['is_achieved'] = milestone_info.get('is_achieved', False)
                        milestone['obtained_score'] = milestone_info.get('obtained_score', 0)
                        milestone_docs.append(milestone)

            # Creating a DataFrame from the list of milestone documents
            if milestone_docs:
                transformed_docs = [{
                'milestone_name': doc.get('name', ''),
                'milestone_description': doc.get('description', ''),
                'hint_used': "Yes" if doc.get('hint_used') else "No",
                'score':f"{doc.get('obtained_score', 0)}/{doc.get('score', 0)}",
                'is_achieved': "Yes" if doc.get('is_achieved') else "No",
                'is_approved': "Yes" if doc.get('is_approved') else "No",
            } for doc in milestone_docs]
            
            milestone_df = pd.DataFrame(transformed_docs)

            add_section(pdf, user_name, p_data['team'], milestone_df, max_rows_per_page=6, is_flag_section=False)

    else:
        return f"No participant data found."



async def corporate_send_notification(group_name="",data=""):
    channel_layer = get_channel_layer()
    if group_name != "":
        active_game = active_scenario_collection.find_one({"id":group_name}, {"_id": 0})
        
        data=[] 
        # print('here i am',active_game.get("participant_data"))   
        for key in active_game.get("participant_data"):
            user = user_collection.find_one({"user_id": key}, {"_id": 0})
            
            active_user = participant_data_collection.find_one({"id":active_game.get("participant_data")[key]}, {"_id": 0,"updated_at":0})
            active_user["user_avatar"] = user["user_avatar"]
            active_user["user_role"] = user["user_role"]
            active_user["user_full_name"] = user["user_full_name"]

            if active_user.get("updated_at"):
                del active_user['updated_at']
            
            data.append(active_user)
        new_list = sorted(data, key=lambda x: x["total_obtained_score"], reverse=True)
        
        for obj in new_list:
            if obj.get("milestone_data"):
                for i in obj["milestone_data"]:
                    del i["updated_at"]
            if obj.get("flag_data"):
                for i in obj["flag_data"]:
                    del i["updated_at"]

        await channel_layer.group_send(group_name, {
            'type': 'notification.message',
            'notification': new_list 
        })


async def send_notification_reload(group_name="",data=""):
    # print("reload data",data)
    channel_layer = get_channel_layer()
    await channel_layer.group_send(group_name, {
        'type': 'notification.message',
        'notification': "reload"
    })
    

# NOTE:
# - This version supports BOTH old payloads (flat participant_machine_dict) and new payloads (team-wise dict).
# - It creates a DEDICATED OpenStack clone per team group (Team A / Team B etc.) so machines can repeat across teams.
# - It DOES NOT break your existing DB contract:
#     active_scenario: { networks:[], routers:[], instances:[], participant_data:{user_id: participant_data_id}, ... }
#   ADDed non-breaking extra fields like team_group / cloud_name.

@shared_task
def start_corporate_game(validated_data):
    # --------- helpers ----------
    def _safe_slug(s: str) -> str:
        s = (s or "").strip().lower()
        s = s.replace(" ", "-")
        return "".join(ch for ch in s if ch.isalnum() or ch in "-_") or "team"

    def _now():
        # keep naive datetime like your current code (consistent with existing records)
        return datetime.datetime.now()

    # --------- init ----------
    current_time_stamp = _now()
    participant_array = []
    participant_id_dict = {}   # user_id -> participant_data_id  (keep same as before)
    networks_obj_list = []     # flattened (across all teams)
    routers_obj_list = []      # flattened (across all teams)
    instances_obj_list = []    # flattened (across all teams)

    scenario = validated_data["scenario"]
    scenario_infra = validated_data["scenario_infra"]
    user = validated_data["user"]

    # participant_machine_dict can be either:
    # 1) OLD: { "machineName": "user_id", ... }
    # 2) NEW: { "Team A": { "machineName": "user_id", ... }, "Team B": {...} }
    pmd = validated_data.get("participant_machine_dict") or {}

    # Normalize to NEW shape always: team_name -> {machine -> user_id}
    team_machine_map = {}
    if pmd:
        first_val = next(iter(pmd.values()))
        if isinstance(first_val, dict):
            # already team-wise
            team_machine_map = pmd
        else:
            # old flat mapping -> single group
            team_machine_map = {"Team": pmd}
    else:
        logging.error("participant_machine_dict missing/empty in validated_data")
        return

    # Build allowed mapping ROLE -> [logical_machine_names] from base infra
    allowed = {}
    for inst in scenario_infra.get("instances", []):
        role = (inst.get("team") or "").upper()
        if not role:
            continue
        allowed.setdefault(role, []).append(inst.get("name"))

    # --------- per-team cloning ----------
    for team_name, machine_to_user in team_machine_map.items():
        team_slug = _safe_slug(team_name)

        # 1) Create team networks
        team_network_subnet_dict = {}  # logical_network_name -> subnet_id
        team_network_dict = {}         # logical_network_name -> network_id
        team_networks_obj = []

        for network in scenario_infra.get("networks", []):
            try:
                logical_net = network["network_name"]
                logical_sub = network["subnet_name"]

                cloud_network, cloud_subnet = create_cloud_network(
                    network_name=f"{team_slug}-{logical_net}",
                    subnet_name=f"{team_slug}-{logical_sub}",
                    subnet_cidr=network["cidr_ip"]
                )

                team_network_subnet_dict[logical_net] = cloud_subnet.id
                team_network_dict[logical_net] = cloud_network.id

                team_networks_obj.append({
                    "team_group": team_name,
                    "network_name": logical_net,          # keep logical
                    "cloud_name": f"{team_slug}-{logical_net}",
                    "network_id": cloud_network.id,
                    "subnet_name": logical_sub,           # keep logical
                    "cloud_subnet_name": f"{team_slug}-{logical_sub}",
                    "subnet_id": cloud_subnet.id,
                    "cidr_ip": network["cidr_ip"]
                })
            except Exception as e:
                logging.error("Network Exception Occured (team=%s): %s", team_name, e)

        networks_obj_list.extend(team_networks_obj)

        # 2) Create team routers
        team_routers_obj = []
        for router in scenario_infra.get("routers", []):
            try:
                logical_router_name = router["name"]
                cloud_router = create_cloud_router(router_name=f"{team_slug}-{logical_router_name}")

                if router.get("is_internet_required"):
                    cloud_router = connect_router_to_public_network(cloud_router)

                for internal_interface in router.get("network_name", []):
                    internal_subnet_id = team_network_subnet_dict.get(internal_interface)
                    if not internal_subnet_id:
                        continue
                    internal_subnet = get_cloud_subnet(internal_subnet_id)
                    connect_router_to_private_network(cloud_router, internal_subnet)

                team_routers_obj.append({
                    "team_group": team_name,
                    "id": cloud_router.id,
                    "name": logical_router_name,              # keep logical
                    "cloud_name": f"{team_slug}-{logical_router_name}",
                    "is_internet_required": router.get("is_internet_required", False),
                    "network_name": router.get("network_name", [])
                })
            except Exception as e:
                logging.error("Router Exception Occured (team=%s): %s", team_name, e)

        routers_obj_list.extend(team_routers_obj)

        # 3) Create instances + participant_data for THIS team
        for base_inst in scenario_infra.get("instances", []):
            logical_machine_name = base_inst.get("name")
            role = (base_inst.get("team") or "").upper()

            # If this machine isn't assigned in this team group, skip
            if logical_machine_name not in machine_to_user:
                continue

            # Validate role -> machine allowed (defensive; serializer already did this)
            if role and role in allowed and logical_machine_name not in allowed[role]:
                logging.error("Machine %s not allowed for role %s (team=%s)", logical_machine_name, role, team_name)
                continue

            participant_id = machine_to_user.get(logical_machine_name)
            if not participant_id:
                logging.error("No participant mapped for machine=%s (team=%s)", logical_machine_name, team_name)
                continue

            # Build team-specific OpenStack instance name (unique)
            cloud_machine_name = f"{team_slug}-{logical_machine_name}"

            # Resolve network ids for this team
            networks = base_inst.get("network")
            if isinstance(networks, list):
                network_ids = [team_network_dict.get(n) for n in networks if team_network_dict.get(n)]
            elif isinstance(networks, str):
                network_ids = [team_network_dict.get(networks)] if team_network_dict.get(networks) else []
            else:
                network_ids = []

            image = base_inst.get("image")
            flavor = base_inst.get("flavor")
            team_role = base_inst.get("team")

            try:
                cloud_instance, instance_ip = create_cloud_instance(
                    cloud_machine_name, image, flavor, network_ids
                )

                # Save instance object (keep logical name to not break existing UI)
                instances_obj_list.append({
                    "team_group": team_name,
                    "id": cloud_instance.id,
                    "name": logical_machine_name,     # logical machine name (existing usage)
                    "cloud_name": cloud_machine_name, # unique in openstack
                    "flavor": flavor,
                    "network": networks,
                    "image": image,
                    "team": team_role,
                    "ip": instance_ip,                # safe extra for reports/ops
                })

                # ---- Create participant_data (ONLY AFTER cloud_instance + participant_id exist) ----
                participant_data_id = generate_random_string(id_type="Particiapnt Data", length=40)

                participant_data = {
                    "id": participant_data_id,
                    "user_id": participant_id,
                    "team": team_role,                         # RED/BLUE/PURPLE/YELLOW (role)
                    "team_group": team_name,                   # Team A / Team B (non-breaking extra)
                    "instance_id": cloud_instance.id,
                    "logical_machine_name": logical_machine_name,
                    "cloud_machine_name": cloud_machine_name,
                    "total_obtained_score": 0,
                    "scenario_id": scenario["id"],
                    "created_at": current_time_stamp,
                    "updated_at": current_time_stamp,
                }

                if participant_id not in participant_array:
                    participant_array.append(participant_id)

                # ----- Flag init -----
                if scenario.get("flag_data"):
                    flag_data_list = []
                    flag_ids = scenario["flag_data"].get(team_role.lower() + "_team", [])
                    total_score = 0

                    for fid in flag_ids:
                        flag_doc = flag_data_collection.find_one({"id": fid}) or {}
                        total_score += int(flag_doc.get("score", 0))

                        flag_data_list.append({
                            "flag_id": fid,
                            #(for phase-wise UI)
                            "phase_id": flag_doc.get("phase_id"),  
                            "submitted_response": "",
                            "obtained_score": 0,
                            "hint_used": False,
                            "retires": 0,
                            "assigned_at": current_time_stamp,
                            "first_visible_at": current_time_stamp,  #  (decay anchor)
                            "submitted_at": None,
                            "approved_at": None,
                            "locked_by_admin": bool(flag_doc.get("is_locked", False)),
                            "updated_at": current_time_stamp,
                            "status": True
                        })

                    participant_data["flag_data"] = flag_data_list
                    participant_data["total_score"] = total_score

                # ----- Milestone init -----
                elif scenario.get("milestone_data"):
                    milestone_data_list = []
                    milestone_ids = scenario["milestone_data"].get(team_role.lower() + "_team", [])
                    total_score = 0

                    milestone_data_list = []
                    total_score = 0

                    for mid in milestone_ids:
                        milestone_doc = milestone_data_collection.find_one({"id": mid}) or {}
                        total_score += int(milestone_doc.get("score", 0))

                        milestone_data_list.append({
                            "milestone_id": mid,

                            # phase mapping (kill-chain UI)
                            "phase_id": milestone_doc.get("phase_id"),

                            "is_achieved": False,
                            "is_approved": False,
                            "obtained_score": 0,
                            "hint_used": False,
                            "retires": 0,
                            "screenshot_url": "",

                            # locking + decay anchors
                            "status": True,
                            "locked_by_admin": bool(milestone_doc.get("is_locked", False)),
                            "first_visible_at": current_time_stamp,

                            # timestamps
                            "assigned_at": current_time_stamp,
                            "submitted_at": None,
                            "achieved_at": None,
                            "approved_at": None,
                            "updated_at": current_time_stamp,
                        })

                    participant_data["milestone_data"] = milestone_data_list
                    participant_data["total_score"] = total_score

                else:
                    logging.error("Unknown Error: scenario has neither flag_data nor milestone_data")

                participant_data_collection.insert_one(participant_data)
                participant_id_dict[participant_id] = participant_data_id

            except Exception as e:
                # This catches instance creation failures too
                logging.error("Instance Exception Occured (team=%s, machine=%s): %s", team_name, logical_machine_name, e)
                continue

    # --------- active scenario record (keep SAME keys to avoid breaking existing code) ----------
    active_scenario_id = generate_random_string(id_type="Active Scenario Id", length=40)
    active_scenario_data = {
        "id": active_scenario_id,
        "scenario_id": scenario["id"],
        "started_by": user["user_id"],

        # keep existing top-level lists (flattened across team groups)
        "networks": networks_obj_list,
        "routers": routers_obj_list,
        "instances": instances_obj_list,

        "start_time": current_time_stamp,
        "participant_data": participant_id_dict,  # user_id -> participant_data_id (same as before)

        # non-breaking extra (handy later for UI):
        "team_groups": list(team_machine_map.keys()),
        "created_at": current_time_stamp,
        "updated_at": current_time_stamp,
    }

    start_time = _now()
    corporate_game = corporate_scenario_collection.find_one({"id": scenario["id"]}, {"_id": 0}) or {}
    user_emails = [
        u.get("email")
        for u in list(user_collection.find({"user_id": {"$in": participant_array}}, {"_id": 0, "email": 1}))
    ]

    active_scenario_collection.insert_one(active_scenario_data)

    # --------- notifications ----------
    for participant in participant_array:
        notification = {
            "type": "action",
            "title": f"{corporate_game.get('name', 'Corporate')} Corporate Started",
            "description": f"{corporate_game.get('name', 'Corporate')} Corporate started successfully.",
            "timestamp": start_time,
            "user_id": participant,
            "action_urls": [],
            "redirection_url": "/ActiveGameSenario/corporate",
        }
        notification_collection.insert_one(notification)
        async_to_sync(send_notification)(group_name=participant)

    # white team notification (keep your existing else-style semantics)
    notification = {
        "type": "information",
        "title": f"{corporate_game.get('name', 'Corporate')} Corporate Started",
        "description": f"{corporate_game.get('name', 'Corporate')} Corporate started successfully for {user_emails}.",
        "timestamp": start_time,
        "user_id": user["user_id"],
        "action_urls": [],
        "redirection_url": "",
    }
    notification_collection.insert_one(notification)
    async_to_sync(send_notification)(group_name=user["user_id"])

def _now():
    return datetime.datetime.now()

@shared_task
def end_corporate_game(active_scenario):
    
    subnet_dict = {}

    for network in active_scenario["networks"]:
        subnet_dict[network["network_name"]] = network["subnet_id"]

    for instance in active_scenario["instances"]:
        cloud_instance = get_cloud_instance(instance["id"])
        if cloud_instance:
            deleted_cloud_instance = delete_cloud_instance(cloud_instance)

    for router in active_scenario["routers"]:
        cloud_router = get_cloud_router(router['id'])
        if cloud_router:
            for network_name in router["network_name"]:
                disconnect_router_from_private_network(router['id'], subnet_dict[network_name])
            delete_cloud_router(router['id'])

    for network in active_scenario["networks"]:
        delete_cloud_network(network['network_id'], network['subnet_id'])

    end_time = datetime.datetime.now()
    corporate_game = corporate_scenario_collection.find_one({"id":active_scenario["scenario_id"]},{"_id":0})

    for key in active_scenario["participant_data"]:
        notification = {
            "type": "information",
            "title": f"{corporate_game['name']} Corporate Ended",
            "description": f"{corporate_game['name']} Corporate ended successfully.",
            "timestamp": end_time,
            "user_id": key,
            "redirection_url": "",
        }
        notification_collection.insert_one(notification)
        async_to_sync(send_notification)(group_name=key)
    else:
        notification = {
            "type": "information",
            "title": f"{corporate_game['name']} Corporate Ended",
            "description": f"{corporate_game['name']} Corporate ended successfully.",
            "timestamp": end_time,
            "user_id": active_scenario["started_by"],
            "redirection_url": "",
        }
        notification_collection.insert_one(notification)
        async_to_sync(send_notification)(group_name=active_scenario["started_by"])


# report data 


def report_data(participant_id,user_id):
       
        user_details = user_collection.find_one({"user_id": user_id})
        # Fetch user data
        user_data = archive_participant_collection.find_one({"id": participant_id}, {"_id": 0})
        if not user_data:
            return {"errors": "Invalid User corporate_id."}

        # Fetch corporate scenario
        corporate_scenario = corporate_scenario_collection.find_one({"id": user_data["scenario_id"]}, {'_id': 0})
        if not corporate_scenario:
            return {"errors": "Invalid scenario ID."}

        # Fetch played games related to the user
        played_games = {}
        documents = list(archive_scenario_collection.find({}, {'_id': 0}))
        for doc in documents:
            if doc["participant_data"].get(user_id) == participant_id:
                played_games = doc
                break  # Break the loop once the relevant document is found

        if not played_games:
            return {"errors": "Invalid User ID."}
        question_answer = []
        # Process flag_data if present
        if "flag_data" in user_data:
           
            flag_data = user_data["flag_data"]
            for element in flag_data:
                data =  flag_data_collection.find_one(
                        {"id": element["flag_id"]},
                        {'_id': 0, "index": 0, "hint": 0, "category_id": 0, "id": 0, "created_at": 0, "updated_at": 0}
                    )
                data['submitted_response'] = element['submitted_response']
                data["obtained_score"] = element["obtained_score"]
                data["retires"] = element["retires"]
                data["hint_used"] = element["hint_used"]
                question_answer.append(data)
            user_data["type"] = "flag_based"
            user_data['question'] = question_answer

        elif "milestone_data" in user_data:
            flag_data = user_data["milestone_data"]
            for element in flag_data:
                value = milestone_data_collection.find_one(
                        {"id": element["milestone_id"]},
                        {'_id': 0, "index": 0, "hint": 0, "category_id": 0, "id": 0, "created_at": 0, "updated_at": 0}
                    )
                value['is_achieved'] = element["is_achieved"]
                value['is_approved'] = element["is_approved"]
                value["obtained_score"] = element["obtained_score"]
                question_answer.append(value)
                
            user_data["type"] = "milestone_based"
            user_data['question'] = question_answer
        else:
            return {"errors": "key is not present in the database"}

        # Calculate the number of hints used and total hints
        hints_used = sum(flag["hint_used"] for flag in flag_data)
        total_hints = len(flag_data)

        # Calculate the time taken for each flag update
        start_time = datetime.datetime.fromisoformat(str(played_games["start_time"]))
        time_data = [
            round((datetime.datetime.fromisoformat(str(flag["updated_at"])) - start_time).total_seconds() / 60.0)
            for flag in flag_data
        ]

        # Create series data for hints used and unused
        series_data = [
            {
                "data": [
                    {"id": 0, "value": hints_used, "label": 'Used Hints'},
                    {"id": 1, "value": total_hints - hints_used, "label": 'Un-used Hint'}
                ]
            }
        ]

        # Create data for retires and the corresponding x-values
        retires_array = [flag["retires"] for flag in flag_data]
        retires_array_x_value = [f"Q {index + 1}" for index in range(len(flag_data))]

        # Add series data to user_data
        user_data["series"] = series_data
        user_data["retires"] = retires_array
        user_data["retires_array_x_value"] = retires_array_x_value

        # Create and add score_obtained series to user_data
        score_obtained_data = [
            {
                "data": [
                    {"id": idx, "value": flag["obtained_score"], "label": f'Q {idx + 1}'}
                    for idx, flag in enumerate(flag_data)
                ]
            }
        ]
        user_data["score_obtained"] = score_obtained_data
        user_data["time_taken"] = time_data

        # Add additional user and scenario details
        user_data['user_full_name'] = user_details["user_full_name"]
        user_data["user_avatar"] = user_details["user_avatar"]
        user_data['email'] = user_details['email']
        user_data["scenario_name"] = corporate_scenario["name"]
        user_data["description"] = corporate_scenario["description"]
        user_data['scenario_severity'] = corporate_scenario['severity']
        user_data["thumbnail_url"] = corporate_scenario['thumbnail_url']

        # Remove sensitive or irrelevant fields from user_data
        for key in ["id", "user_id", "instance_id", "scenario_id"]:
            user_data.pop(key, None)

        # Optionally update the document with the new report data (commented out)
        # filter = {"id": participant_id}
        # update = {"$set": {"report_data": user_data}}
        # options = {"projection": {"_id": 0}, "returnDocument": "after"}
        # user_data_updated = archive_participant_collection.find_one_and_update(filter, update, **options)
        # print(user_data_updated)

        return user_data

def build_channel_key(
    scenario_id,
    active_scenario_id,
    team_group,
    scope
):
    """
    scope:
      - ALL
      - RED / BLUE / YELLOW / PURPLE
      - GLOBAL (superadmin / white)
    """
    return (
        f"SCN_{scenario_id}"
        f"::ACT_{active_scenario_id}"
        f"::TG_{team_group}"
        f"::SCOPE_{scope}"
    )
def parse_dt(value):
    if value is None:
        return None

    if isinstance(value, datetime.datetime):
        return value

    if isinstance(value, dict) and "$date" in value:
        value = value["$date"]

    try:
        s = str(value)
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def minutes_between(a, b):
    da = parse_dt(a)
    db = parse_dt(b)
    if not da or not db:
        return None
    return round((db - da).total_seconds() / 60.0, 2)


def normalize_time(minutes):
    if minutes is None:
        return None
    return {
        "minutes": round(minutes, 2),
        "hours": round(minutes / 60, 2)
    }


# ─────────────────────────────────────────────
# Item timing
# ─────────────────────────────────────────────

def time_to_first_action(item):
    assigned_at = item.get("assigned_at") or item.get("first_visible_at")
    if not assigned_at:
        return None

    action_time = item.get("achieved_at") or item.get("submitted_at")
    if not action_time:
        return None

    return minutes_between(assigned_at, action_time)


def approval_delay(item):
    achieved_at = item.get("achieved_at") or item.get("submitted_at")
    approved_at = item.get("approved_at")
    if not achieved_at or not approved_at:
        return None
    return minutes_between(achieved_at, approved_at)


# ─────────────────────────────────────────────
# Scoring helpers
# ─────────────────────────────────────────────

def extract_score_meta(item):
    sm = item.get("score_meta")
    if not isinstance(sm, dict):
        sm = {}

    base = sm.get("base_score")
    if base is None:
        base = item.get("score") or item.get("base_score") or 0

    final = sm.get("final_score")
    if final is None:
        final = item.get("obtained_score") or 0

    return {
        "type": sm.get("type", "standard"),
        "base_score": base,
        "final_score": final,
        "hint_penalty": sm.get("hint_penalty", item.get("hint_penalty", 0) or 0),
        "decay_penalty": sm.get("decay_penalty", 0),
    }


# ─────────────────────────────────────────────
# Readiness logic
# ─────────────────────────────────────────────

def classify_overall_readiness(score_ratio):
    if score_ratio >= 0.75:
        return "Strong"
    if score_ratio >= 0.5:
        return "Moderate"
    return "Weak"


# ─────────────────────────────────────────────
# Narrative engine
# ─────────────────────────────────────────────

def pick_narrative(file_name, key):
    path = NARRATIVE_PATH / file_name
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    options = data.get(key, [])
    return random.choice(options) if options else None


def pick_final_conclusion(score_ratio):
    key = "strong" if score_ratio >= 0.75 else "moderate" if score_ratio >= 0.5 else "weak"
    return pick_narrative("final_conclusion.json", key)


def build_executive_narrative(quant):
    if not quant or not quant.get("base_score"):
        return ["Insufficient data available to generate executive assessment."]

    lines = []

    avg_tfa = quant.get("average_time_to_first_action_min")
    if avg_tfa is not None:
        key = "fast" if avg_tfa <= 10 else "moderate" if avg_tfa <= 60 else "slow"
        line = pick_narrative("response_time.json", key)
        if line:
            lines.append(line)

    score_ratio = quant.get("score_ratio", 0)
    key = "strong" if score_ratio >= 0.75 else "moderate" if score_ratio >= 0.5 else "weak"
    line = pick_narrative("score_quality.json", key)
    if line:
        lines.append(line)

    hint_pct = quant.get("hint_utilisation_percent", 0)
    key = "high" if hint_pct >= 50 else "medium" if hint_pct >= 20 else "low"
    line = pick_narrative("hint_dependency.json", key)
    if line:
        lines.append(line)

    return lines


# ─────────────────────────────────────────────
# Quantitative aggregation
# ─────────────────────────────────────────────

def compute_participant_quantitative(participant):
    base = final = hint_pen = decay_pen = 0
    tfa, appr = [], []

    items = participant.get("flag_data", []) + participant.get("milestone_data", [])

    for it in items:
        sm = extract_score_meta(it)
        base += sm["base_score"]
        final += sm["final_score"]
        hint_pen += sm["hint_penalty"]
        decay_pen += sm["decay_penalty"]

        x = time_to_first_action(it)
        if x is not None:
            tfa.append(x)

        y = approval_delay(it)
        if y is not None:
            appr.append(y)

    ratio = final / base if base else 0

    return {
        "base_score": base,
        "final_score": final,
        "score_ratio": round(ratio, 2),
        "overall_readiness": classify_overall_readiness(ratio),
        "average_time_to_first_action_min": round(sum(tfa) / len(tfa), 2) if tfa else None,
        "average_approval_delay_min": round(sum(appr) / len(appr), 2) if appr else None,
        "total_hint_penalty": hint_pen,
        "total_decay_penalty": decay_pen,
    }


def collect_team_evidence(participants):
    evidence = []

    for p in participants:
        for it in p.get("flag_data", []) + p.get("milestone_data", []):
            evidence.append({
                "phase_id": it.get("phase_id"),
                "status": (
                    "Approved" if it.get("approved_at")
                    else "Submitted" if it.get("submitted_at")
                    else "Not Acted"
                ),
                "time_to_first_action_min": time_to_first_action(it),
                "approval_delay_min": approval_delay(it),
                "score_meta": extract_score_meta(it)
            })

    return evidence


def compute_phase_analysis(evidence_items, phase_lookup):
    phase_map = {}

    for it in evidence_items:
        pid = it.get("phase_id")
        if not pid:
            continue
        phase_map.setdefault(pid, []).append(it)

    results = []

    for pid, items in phase_map.items():
        base = sum(i["score_meta"]["base_score"] for i in items)
        final = sum(i["score_meta"]["final_score"] for i in items)
        not_acted = sum(1 for i in items if i["status"] == "Not Acted")

        tfa = [i["time_to_first_action_min"] for i in items if i["time_to_first_action_min"]]
        appr = [i["approval_delay_min"] for i in items if i["approval_delay_min"]]

        ratio = final / base if base else 0

        gap = (
            "High" if not_acted > 0 or ratio < 0.6
            else "Moderate" if ratio < 0.8
            else "Low"
        )

        results.append({
            "phase": {
                "id": pid,
                "name": phase_lookup.get(pid, {}).get("name", "Unknown Phase")
            },
            "metrics": {
                "items": len(items),
                "approved": sum(1 for i in items if i["status"] == "Approved"),
                "not_acted": not_acted,
                "base_score": base,
                "final_score": final,
                "score_ratio": round(ratio, 2),
                "avg_time_to_first_action_hr": round(sum(tfa) / len(tfa) / 60, 2) if tfa else None,
                "avg_approval_delay_hr": round(sum(appr) / len(appr) / 60, 2) if appr else None,
                "phase_gap": gap
            }
        })

    return results


def compute_team_quantitative(participants, start=None, end=None):
    items = []
    for p in participants:
        items += p.get("flag_data", []) + p.get("milestone_data", [])

    base = final = hint_pen = decay_pen = 0
    tfa, appr = [], []
    hint_used = hint_total = 0

    for it in items:
        sm = extract_score_meta(it)
        base += sm["base_score"]
        final += sm["final_score"]
        hint_pen += sm["hint_penalty"]
        decay_pen += sm["decay_penalty"]

        hint_total += 1
        if it.get("hint_used"):
            hint_used += 1

        x = time_to_first_action(it)
        if x is not None:
            tfa.append(x)

        y = approval_delay(it)
        if y is not None:
            appr.append(y)

    ratio = final / base if base else 0
    duration = minutes_between(start, end) if start and end else None

    return {
        "team_duration_min": duration,
        "base_score": base,
        "final_score": final,
        "score_ratio": round(ratio, 2),
        "overall_readiness": classify_overall_readiness(ratio),
        "hint_utilisation_percent": round((hint_used / hint_total) * 100, 2) if hint_total else 0,
        "total_hint_penalty": hint_pen,
        "total_decay_penalty": decay_pen,
        "average_time_to_first_action_min": round(sum(tfa) / len(tfa), 2) if tfa else None,
        "average_approval_delay_min": round(sum(appr) / len(appr), 2) if appr else None,
    }

def build_phase_lookup(scenario_meta):
    """
    Builds: { phase_id -> phase_object }
    """
    phases = scenario_meta.get("phases", []) or []

    lookup = {}
    for p in phases:
        pid = p.get("id")
        if pid:
            lookup[pid] = {
                "id": pid,
                "name": p.get("phase_name") or p.get("name"),
            }

    return lookup

def resolve_item_meta(item):
    if item.get("flag_id"):
        doc = flag_data_collection.find_one(
            {"id": item["flag_id"]},
            {"_id": 0, "id": 1, "title": 1}
        )
        return {
            "type": "flag",
            "id": item["flag_id"],
            "title": doc.get("title") if doc else "Unknown Flag"
        }

    if item.get("milestone_id"):
        doc = milestone_data_collection.find_one(
            {"id": item["milestone_id"]},
            {"_id": 0, "id": 1, "title": 1}
        )
        return {
            "type": "milestone",
            "id": item["milestone_id"],
            "title": doc.get("title") if doc else "Unknown Milestone"
        }

    return None