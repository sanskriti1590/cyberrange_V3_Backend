import datetime
from collections import defaultdict
from typing import Optional

from cloud_management.utils import get_cloud_instance, get_instance_console, get_instance_private_ip, get_flavor_detail
from corporate_management.utils import start_corporate_game, end_corporate_game
from database_management.pymongo_client import (
    corporate_scenario_collection,
    scenario_category_collection,
    milestone_data_collection,
    flag_data_collection,
    user_profile_collection,
    user_collection, active_scenario_collection, corporate_participant_data, participant_data_collection, corporate_scenario_infra_collection, corporate_flag_data_collection,
    archive_scenario_collection, archive_participant_collection, )


class CorporateScenarioService:
    TEAM_KEYS = ["red_team", "blue_team", "purple_team", "yellow_team"]

    @staticmethod
    def _get_scenario_type(scenario: dict):
        return "Milestone" if scenario.get("milestone_data") else "Flag"

    @staticmethod
    def _get_scenario_category_name(scenario: dict):
        category_name = scenario_category_collection.find_one({"scenario_category_id": scenario["category_id"]}, {"_id": 0, "scenario_category_name": 1})
        return category_name["scenario_category_name"]

    @classmethod
    def _calculate_points(cls, scenario: dict) -> int:
        total_score = 0
        data_source = scenario.get("milestone_data") or scenario.get("flag_data", {})

        collection = milestone_data_collection if scenario.get("milestone_data") else flag_data_collection

        for team in cls.TEAM_KEYS:
            for item_id in data_source.get(team, []):
                score_doc = collection.find_one({"id": item_id}, {"_id": 0, "score": 1})
                total_score += score_doc.get("score", 0) if score_doc else 0

        return total_score

    @classmethod
    def get_all_scenarios(cls, is_approved: Optional[bool] = None, is_prepared: Optional[bool] = None, category_id: Optional[str] = None, user_id: Optional[str] = None):
        # Validate category if provided
        if category_id:
            if not scenario_category_collection.find_one({"scenario_category_id": category_id}):
                return {"errors": {"non_field_errors": ["Invalid Scenario Category Id"]}}

        query = {}

        if is_approved is not None:
            query["is_approved"] = is_approved
        else:
            query["is_approved"] = True

        if is_prepared is not None:
            query["is_prepared"] = is_prepared
        else:
            query["is_prepared"] = True

        if category_id:
            query["category_id"] = category_id

        projection = {"_id": 0, "is_approved": 0, "is_prepared": 0, "created_at": 0, "updated_at": 0, }

        assigned_ids = set()
        display_all = True
        display_locked = True

        if user_id:
            user_profile = user_profile_collection.find_one(
                {"user_id": user_id}, {"_id": 0, "assigned_games": 1}
            )
            if user_profile and "assigned_games" in user_profile:
                assigned = user_profile["assigned_games"]
                display_all = assigned.get("display_all_corporate", False)
                display_locked = assigned.get("display_locked_corporate", False)
                assigned_ids = set(assigned.get("corporate", []))

        scenarios = list(corporate_scenario_collection.find(query, projection))

        for scenario in scenarios:
            # Apply display flag if needed
            if not display_all and user_id:
                scenario["display"] = scenario["id"] in assigned_ids

            # Add category name
            scenario["category_name"] = cls._get_scenario_category_name(scenario)

            # Add scenario type
            scenario["type"] = cls._get_scenario_type(scenario)

            # Add score
            scenario["points"] = cls._calculate_points(scenario)

        return scenarios

    @staticmethod
    def get_scenarios_detail(scenario_id: str) -> dict:
        """
        Return full corporate scenario details including:
        - Expanded flag data per team
        - Infrastructure and hardware summary
        - Files data if available
        """

        # --- Fetch scenario document ---
        scenario = corporate_scenario_collection.find_one(
            {"id": scenario_id},
            {"_id": 0}
        )
        if not scenario:
            return {"errors": f"Invalid Scenario ID: {scenario_id}"}

        # --- Fetch related category info ---
        category_doc = scenario_category_collection.find_one(
            {"scenario_category_id": scenario.get("category_id")},
            {"_id": 0, "scenario_category_name": 1}
        )
        category_name = category_doc.get("scenario_category_name") if category_doc else "Unknown"

        # --- Fetch creator info ---
        user_doc = user_collection.find_one(
            {"user_id": scenario.get("creator_id")},
            {"_id": 0, "user_full_name": 1}
        )
        creator_name = user_doc.get("user_full_name") if user_doc else "Unknown"

        # --- Infrastructure / Hardware ---
        infra_doc = corporate_scenario_infra_collection.find_one(
            {"id": scenario.get("infra_id")},
            {"_id": 0, "instances": 1}
        )

        instance_names = []
        hardware_summary = {"vcpu": 0, "disk_size_gb": 0, "ram_gb": 0, "vm_count": 0}

        if infra_doc and infra_doc.get("instances"):
            for instance in infra_doc["instances"]:
                name = instance.get("name")
                if name:
                    instance_names.append(name)

                flavor = instance.get("flavor")
                if flavor:
                    flavor_detail = get_flavor_detail(flavor)
                    if not flavor_detail:
                        continue
                    hardware_summary["vcpu"] += flavor_detail.get("vcpus", 0)
                    hardware_summary["disk_size_gb"] += flavor_detail.get("disk", 0)
                    hardware_summary["ram_gb"] += round(flavor_detail.get("ram", 0) / 1024)
                    hardware_summary["vm_count"] += 1

        # --- Flag Data Expansion ---
        flag_data = scenario.get("flag_data", {})
        team_keys = ["red_team", "blue_team", "purple_team", "yellow_team"]
        expanded_flag_data = {}
        total_points = 0

        for team in team_keys:
            flag_ids = flag_data.get(team, [])
            if not flag_ids:
                expanded_flag_data[team] = []
                continue

            flags = list(corporate_flag_data_collection.find(
                {"id": {"$in": flag_ids}},
                {"_id": 0}
            ))
            expanded_flag_data[team] = flags
            total_points += sum(flag.get("score", 0) for flag in flags)

        # --- Files Data ---
        files_data = scenario.get("files_data", {})
        expanded_files_data = {team: files_data.get(team, []) for team in team_keys}

        # --- Construct structured response ---
        data_params = {
            "id": scenario.get("id"),
            "name": scenario.get("name"),
            "severity": scenario.get("severity"),
            "description": scenario.get("description"),
            "objective": scenario.get("objective"),
            "prerequisite": scenario.get("prerequisite"),
            "thumbnail_url": scenario.get("thumbnail_url"),

            "files_data": expanded_files_data,
            "machine_names": instance_names,
            "hardware_details": hardware_summary,
            "points": total_points,
            "creator": {
                "id": scenario.get("creator_id"),
                "full_name": creator_name
            },
            "category": {
                "id": scenario.get("category_id"),
                "name": category_name
            },
            "flag_data_full": expanded_flag_data,
            "created_at": scenario.get("created_at"),
            "updated_at": scenario.get("updated_at"),
        }

        return data_params


    @staticmethod
    def get_active_scenarios():
        response = []
        active_scenarios = active_scenario_collection.find({}, {"_id": 0})
        for active_scenario in active_scenarios:
            scenario = corporate_scenario_collection.find_one({"id": active_scenario['scenario_id']}, {"_id": 0})
            started_by_user = user_collection.find_one({"user_id": active_scenario['started_by']}, {"user_full_name": 1, "_id": 0})

            started_by = started_by_user["user_full_name"] if started_by_user and "user_full_name" in started_by_user else f"Unknown User - {active_scenario['started_by']}"

            temp_data = {
                'id': active_scenario['id'],
                'started_by': started_by,
                'start_time': active_scenario['start_time'],
                'scenario': {
                    'id': active_scenario['scenario_id'],
                    'name': scenario['name'],
                    'type': CorporateScenarioService._get_scenario_type(scenario),
                    'category_name': CorporateScenarioService._get_scenario_category_name(scenario),
                    'severity': scenario['severity'],
                    'description': scenario['description'],
                    'thumbnail_url': scenario["thumbnail_url"],
                    'points': CorporateScenarioService._calculate_points(scenario),
                },
                "total_participant": len(active_scenario.get("participant_data", {})),
                'total_network': len(active_scenario.get("networks", [])),
                'total_routers': len(active_scenario.get("routers", [])),
                'total_instances': len(active_scenario.get("instances", [])),
            }
            response.append(temp_data)
        return response

    @staticmethod
    def end_scenarios(active_scenario_id: str, user_id: str):
        # Fetch the active scenario (exclude Mongo’s internal _id from output)
        active_scenario = active_scenario_collection.find_one(
            {"id": active_scenario_id},
            {"_id": 0}
        )
        if not active_scenario:
            return {"errors": "Invalid Active Scenario ID"}

        # Fetch the user
        user_data = user_collection.find_one({"user_id": user_id})
        if not user_data:
            return {"errors": "Invalid User ID"}

        is_superadmin = user_data.get("is_superadmin", False)

        # Authorization: either the user who started the scenario, or a superadmin
        if user_id != active_scenario.get("started_by"):
            if not is_superadmin:
                return {"errors": "You are not authorised to delete this scenario."}

        # Mark end time
        active_scenario["end_time"] = datetime.datetime.now()

        # Archive the scenario
        archive_scenario_collection.insert_one(active_scenario)

        # Delete from active (pop _id if present to avoid conflicts)
        active_scenario.pop("_id", None)
        active_scenario_collection.delete_one({"id": active_scenario["id"]})

        # Trigger any post‑end processing asynchronously
        end_corporate_game.delay(active_scenario)

        # Archive participants and delete from active participants
        participant_ids = active_scenario.get("participant_data", {}).values()
        for pid in participant_ids:
            participant_data = participant_data_collection.find_one({"id": pid})
            if participant_data:
                archive_participant_collection.insert_one(participant_data)
                participant_data_collection.delete_one({"id": pid})

        return {"message": "Scenario Deleted Successfully"}

    @staticmethod
    def get_single_active_scenario(active_scenario_id):
        active_scenario = active_scenario_collection.find_one({"id": active_scenario_id}, {"_id": 0})
        if not active_scenario:
            return {"errors": {"non_field_errors": ["Invalid Scenario ID"]}}

        user_started = user_collection.find_one({"user_id": active_scenario['started_by']}, {"user_full_name": 1, "_id": 0})
        started_by = user_started.get("user_full_name") if user_started else "Unknown"

        scenario = corporate_scenario_collection.find_one({"id": active_scenario['scenario_id']}, {"_id": 0})

        participants = []
        participant_data = active_scenario.get("participant_data") or {}

        for user_id in participant_data:
            user = user_collection.find_one({"user_id": user_id}, {"_id": 0})
            participant_id = participant_data.get(user_id)
            if not user or not participant_id:
                continue

            participant_raw = corporate_participant_data.find_one({"id": participant_id}, {"_id": 0})
            if not participant_raw:
                continue

            # Enrich user info
            participant_user = dict(participant_raw)
            participant_user["avatar"] = user.get("user_avatar")
            participant_user["role"] = user.get("user_role")
            participant_user["full_name"] = user.get("user_full_name")

            # Per-participant flag data grouping
            flag_data_map = defaultdict(lambda: {
                "flag_id": None,
                "question": None,
                "score": None,
                "team": None,
                "participant_answers": []
            })

            for flag_entry in participant_raw.get("flag_data", []):
                flag_id = flag_entry.get("flag_id")
                if not flag_id:
                    continue

                flag_details = corporate_flag_data_collection.find_one({"id": flag_id}, {"_id": 0})
                if not flag_details:
                    continue

                if flag_data_map[flag_id]["flag_id"] is None:
                    flag_data_map[flag_id].update({
                        "flag_id": flag_id,
                        "question": flag_details.get("question"),
                        "score": flag_details.get("score"),
                        "team": flag_details.get("team")
                    })

                flag_data_map[flag_id]["participant_answers"].append({
                    "flag_id": flag_id,
                    "submitted_response": flag_entry.get("submitted_response", ""),
                    "obtained_score": flag_entry.get("obtained_score", 0),
                    "hint_used": flag_entry.get("hint_used", False),
                    "retires": flag_entry.get("retires", 0),
                    "updated_at": flag_entry.get("updated_at", ""),
                    "status": flag_entry.get("status", False),
                })

            # Assign grouped flag_data to participant
            participant_user["flag_data"] = list(flag_data_map.values())

            # Calculate total_obtained_score from participant_answers
            total_obtained_score = 0
            for flag in participant_user["flag_data"]:
                for ans in flag.get("participant_answers", []):
                    total_obtained_score += ans.get("obtained_score", 0)

            participant_user["total_obtained_score"] = total_obtained_score

            participants.append(participant_user)

        # Sort participants by total_obtained_score descending
        new_list = sorted(participants, key=lambda x: x.get("total_obtained_score", 0), reverse=True)

        data_params = {
            'id': active_scenario['id'],
            'started_by': started_by,
            'start_time': active_scenario['start_time'],
            'scenario': {
                'id': active_scenario['scenario_id'],
                'name': scenario['name'],
                'type': CorporateScenarioService._get_scenario_type(scenario),
                'category_name': CorporateScenarioService._get_scenario_category_name(scenario),
                'severity': scenario['severity'],
                'description': scenario['description'],
                'thumbnail_url': scenario["thumbnail_url"],
                'points': CorporateScenarioService._calculate_points(scenario),
            },
            'total_network': len(active_scenario.get("networks", [])),
            'total_routers': len(active_scenario.get("routers", [])),
            'total_instances': len(active_scenario.get("instances", [])),
            "participants": new_list
        }

        return data_params

    @staticmethod
    def get_active_scenario_private_ips(active_scenario_id):
        # Step 1: Fetch the active scenario
        active_scenario = active_scenario_collection.find_one(
            {"id": active_scenario_id},
            {"_id": 0}
        )
        if not active_scenario:
            return {"errors": {"non_field_errors": ["Invalid Active Scenario ID"]}}

        instances = active_scenario.get("instances", [])
        ip_list = []

        if len(instances) == 0:
            return {"errors": {"non_field_errors": ["No instances found in this scenario."]}}

        for instance in instances:
            instance_id = instance.get("id")
            if not instance_id:
                return {"errors": {"non_field_errors": [f"Instance id not found in scenario {active_scenario_id}"]}}

            cloud_instance = get_cloud_instance(instance_id)
            if not cloud_instance:
                return {"errors": {"non_field_errors": [f"Cloud instance not found for ID: {instance_id}"]}}

            ip_address = get_instance_private_ip(cloud_instance)
            if not ip_address:
                return {"errors": {"non_field_errors": [f"IP address not found for instance: {instance_id}"]}}

            print(cloud_instance.addresses)

            instance_name = cloud_instance.get('name', 'Unknown')
            ip_list.append({
                "name": instance_name,
                "ip": ip_address
            })

        return ip_list

    @staticmethod
    def get_active_scenario_ips(active_scenario_id):
        # Step 1: Fetch the active scenario from MongoDB
        active_scenario = active_scenario_collection.find_one(
            {"id": active_scenario_id},
            {"_id": 0}
        )

        if not active_scenario:
            return {
                "errors": {
                    "non_field_errors": ["Invalid Active Scenario ID"]
                }
            }

        instances = active_scenario.get("instances", [])
        if not instances:
            return {
                "errors": {
                    "non_field_errors": ["No instances found in this scenario."]
                }
            }

        result_instances = []
        errors = []

        for instance in instances:
            instance_id = instance.get("id")
            if not instance_id:
                errors.append(f"Instance ID missing in scenario {active_scenario_id}")
                continue

            cloud_instance = get_cloud_instance(instance_id)
            if not cloud_instance:
                errors.append(f"Cloud instance not found for ID: {instance_id}")
                continue

            addresses = getattr(cloud_instance, "addresses", {}) or {}
            all_ip_info = []

            for net_name, addr_list in addresses.items():
                for addr in addr_list:
                    ip_info = {
                        "network": net_name,
                        "addr": addr.get("addr"),
                        "type": addr.get("OS-EXT-IPS:type", "unknown"),
                        "mac": addr.get("OS-EXT-IPS-MAC:mac_addr", "unknown"),
                        "version": addr.get("version", "unknown")
                    }
                    all_ip_info.append(ip_info)

            if not all_ip_info:
                errors.append(f"No IPs found for instance ID: {instance_id}")
                continue

            instance_name = getattr(cloud_instance, "name", "Unknown")
            result_instances.append({
                "id": instance_id,
                "name": instance_name,
                "ips": all_ip_info
            })

        #  Final result structure matches what the serializer expects
        result = {
            "id": active_scenario_id,  # Required field
            "instances": result_instances
        }

        if errors:
            result["errors"] = {
                "non_field_errors": errors
            }

        return result

    @staticmethod
    def get_console(active_scenario_id, participant_id):
        # Step 1: Fetch the active scenario
        active_scenario = active_scenario_collection.find_one({"id": active_scenario_id}, {"_id": 0})
        if not active_scenario:
            return {"errors": {"non_field_errors": ["Invalid Active Scenario ID"]}}

        participant_data_map = active_scenario.get('participant_data', {})
        participant_data_id = participant_data_map.get(participant_id)
        if not participant_data_id:
            return {"errors": {"non_field_errors": [f"Invalid participant ID: '{participant_id}'"]}}

        # Step 2: Fetch the participant's data
        participant_data = participant_data_collection.find_one({"id": participant_data_id}, {"_id": 0})
        if not participant_data:
            return {"errors": {"non_field_errors": [f"Invalid participant data ID: '{participant_data_id}'"]}}

        # Step 3: Fetch the scenario
        scenario = corporate_scenario_collection.find_one({"id": active_scenario.get("scenario_id")}, {"_id": 0})
        if not scenario:
            return {"errors": {"non_field_errors": ["Scenario not found."]}}

        # Step 4: Get console URL for the current participant
        try:
            instance = get_cloud_instance(participant_data['instance_id'])
            console = get_instance_console(instance)
            console_url = console.url
        except Exception as e:
            return {"errors": {"non_field_errors": str(e)}}

        # Step 5: Fetch all participants' user data
        participants = []
        for pid, pdata_id in participant_data_map.items():
            user_data = user_collection.find_one({"user_id": pid}, {"_id": 0})
            if user_data:
                participants.append({
                    'id': pid,
                    'full_name': user_data.get('user_full_name'),
                    'avatar': user_data.get('user_avatar'),
                    'role': user_data.get('user_role'),
                })

        # Step 6: Handle FLAG-based scenario
        if scenario.get("flag_data"):
            return {
                'active_scenario_id': active_scenario_id,
                'started_by': active_scenario.get('started_by'),
                'start_time': active_scenario.get('start_time'),
                'current_participant_id': participant_id,
                'console_url': console_url,
                'category_name': CorporateScenarioService._get_scenario_category_name(scenario),
                'scenario': {
                    'name': scenario.get('name'),
                    'type': 'FLAG',
                },
                'participants': participants,
            }

        # Step 6: Prepare team files
        participant_data_team = participant_data['team']
        file_urls = None
        if participant_data_team == "RED":
            file_urls = scenario['files_data']['red_team']
        if participant_data_team == "BLUE":
            file_urls = scenario['files_data']['blue_team']
        if participant_data_team == "PURPLE":
            file_urls = scenario['files_data']['purple_team']
        if participant_data_team == "YELLOW":
            file_urls = scenario['files_data']['yellow_team']

        data_params = {
            'active_scenario_id': active_scenario_id,
            'started_by': active_scenario['started_by'],
            'start_time': active_scenario['start_time'],
            'participant_id': participant_id,
            'team': participant_data_team,
            'total_score': participant_data['total_score'],
            'total_obtained_score': participant_data['total_obtained_score'],
            'console_url': console_url,
            'scenario': {
                'name': scenario['name'],
                'category_id': scenario['category_id'],
                'severity': scenario['severity'],
                'description': scenario['description'],
                'thumbnail_url': scenario['thumbnail_url'],
            },
            'document_urls': file_urls
        }

        # Step 7: Build milestone data
        milestone_data = []
        total_milestone_count = 0
        approved_milestone_count = 0
        for milestone in participant_data['milestone_data']:
            milestone_db_data = milestone_data_collection.find_one({'id': milestone['milestone_id']})

            total_milestone_count += 1
            if milestone['is_approved']:
                approved_milestone_count += 1

            milestone['index'] = milestone_db_data['index']
            milestone['name'] = milestone_db_data['name']
            milestone['description'] = milestone_db_data['description']
            milestone['score'] = milestone_db_data['score']

            milestone_data.append(milestone)

        data_params['scenario']['type'] = 'MILESTONE'
        data_params['milestones'] = milestone_data
        data_params['total_milestone_count'] = total_milestone_count
        data_params['approved_milestone_count'] = approved_milestone_count
        return data_params

    @staticmethod
    def _get_pre_start_scenario_data(request, scenario_id: str) -> dict:
        try:
            login_user = request.user
            login_user_id = login_user.get('user_id')
            user_role = login_user.get('user_role')

            participant_data = request.data.get('participant_data', [])

            if not participant_data:
                return {"errors": {"non_field_errors": ["Invalid participant data."]}}

            if user_role != "WHITE TEAM":
                return {"errors": {"non_field_errors": ["Only WHITE TEAM members are allowed to start a corporate scenario."]}}

            scenario = corporate_scenario_collection.find_one({"id": scenario_id, "is_approved": True}, {"_id": 0})
            if not scenario:
                return {"errors": {"non_field_errors": ["Invalid Scenario ID."]}}

            assigned_games = user_profile_collection.find_one({"user_id": login_user_id}, {"_id": 0, "assigned_games": 1})

            if (not assigned_games.get("assigned_games", {}).get("display_all_corporate", False)
                    and scenario_id not in assigned_games.get("assigned_games", {}).get("corporate", [])
            ):
                return {"errors": {"non_field_errors": ["You are not authorized to start this game."]}}

            scenario_infra = corporate_scenario_infra_collection.find_one(
                {"id": scenario["infra_id"]}, {"_id": 0}
            )
            if not scenario_infra:
                return {"errors": {"non_field_errors": ["Invalid Scenario Infrastructure."]}}

            instance_names = [inst["name"] for inst in scenario_infra.get("instances", [])]
            participant_email_ids = set()
            participant_machine_dict = {}

            for participant in participant_data:
                participant_email = participant.get("participant_email")
                participant_machine = participant.get("participant_machine")

                if not participant_email:
                    return {"errors": {"non_field_errors": ["participant_email is required."]}}

                if not participant_machine:
                    return {"errors": {"non_field_errors": ["participant_machine is required."]}}

                if participant_email in participant_email_ids:
                    return {"errors": {"non_field_errors": [f"{participant_email} is used more than once."]}}

                user = user_collection.find_one({"email": participant_email}, {"_id": 0})
                if not user:
                    return {"errors": {"non_field_errors": [f"{participant_email} is not a valid email address."]}}

                if user.get("user_role") == "WHITE TEAM":
                    return {"errors": {"non_field_errors": [f"{participant_email} is a WHITE TEAM member and cannot be a participant."]}}

                user_id = user.get("user_id")

                if participant_data_collection.find_one({"user_id": user_id}):
                    return {"errors": {"non_field_errors": [f"{participant_email} is already playing a game."]}}

                if participant_machine not in instance_names:
                    return {"errors": {"non_field_errors": [f"{participant_machine} is not a valid machine name."]}}

                instance_names.remove(participant_machine)
                participant_machine_dict[participant_machine] = user_id
                participant_email_ids.add(participant_email)

            if instance_names:
                return {"errors": {"non_field_errors": ["All instances must be assigned to participants before starting the scenario."]}}

            return {
                "user": login_user,
                "participant_data": participant_data,
                "scenario": scenario,
                "scenario_infra": scenario_infra,
                "participant_machine_dict": participant_machine_dict,
            }
        except Exception as e:
            return {"errors": {"non_field_errors": [str(e)]}}

    @staticmethod
    def start_scenario(request, scenario_id):
        validated_data = CorporateScenarioService._get_pre_start_scenario_data(request, scenario_id)
        if 'errors' in validated_data:
            return validated_data

        start_corporate_game.delay(validated_data)
        return {"message": "Please wait while we are creating dedicated environment for you."}
