import datetime
import io
import ipaddress
import os
from bson import ObjectId
import uuid
from collections import defaultdict

from rest_framework import serializers
from django.utils import timezone
from django.conf import settings


from cloud_management.utils import (
    get_instance_images,
    get_instance_flavors,
    get_cloud_instance,
    get_instance_console,
    get_flavor_detail,
)
from core.utils import generate_random_string, API_URL
from ctf_management.utils import validate_file_size
from corporate_management.scoring.decay import compute_decay_score
from corporate_management.scoring.standard import compute_standard_score
from database_management.pymongo_client import (
    scenario_category_collection,
    corporate_scenario_collection,
    corporate_scenario_infra_collection,
    flag_data_collection,
    milestone_data_collection,
    user_collection,
    participant_data_collection,
    archive_scenario_collection,
    archive_participant_collection,
    resource_credentials_collection,
    user_profile_collection,
    active_scenario_collection,
    scenario_chat_messages_collection,
)
from .utils import *

def _sanitize_meta(meta):
    if meta is None:
        return None
    if isinstance(meta, datetime.datetime):
        return meta.isoformat()
    if isinstance(meta, dict):
        return {k: _sanitize_meta(v) for k, v in meta.items()}
    if isinstance(meta, list):
        return [_sanitize_meta(x) for x in meta]
    return meta


class CorporateScenarioCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=500, required=True)
    category_id = serializers.ChoiceField(choices=())
    severity = serializers.ChoiceField(
        choices=('Very Easy', 'Easy', 'Medium', 'Hard', 'Very Hard'),
        required=True
    )
    description = serializers.CharField(min_length=10, max_length=5000, required=True)
    objective = serializers.CharField(min_length=10, max_length=5000, required=False, allow_blank=True)
    prerequisite = serializers.CharField(min_length=10, max_length=5000, required=False, allow_blank=True)
    thumbnail = serializers.FileField(required=False, validators=[validate_file_size])
    type = serializers.ChoiceField(choices=('FLAG', 'MILESTONE'), required=True)

    # 🔹 NEW — scoring controls
    scoring_type = serializers.ChoiceField(
        choices=("standard", "decay"),
        required=False,
        default="standard"
    )
    decay_start_after_minutes = serializers.IntegerField(required=False, default=15)
    decay_penalty_per_interval = serializers.IntegerField(required=False, default=10)
    decay_interval_minutes = serializers.IntegerField(required=False, default=10)
    decay_min_score = serializers.IntegerField(required=False, default=20)

    red_team_files = serializers.ListField(
        child=serializers.FileField(validators=[validate_file_size]),
        allow_empty=True, required=False
    )
    blue_team_files = serializers.ListField(
        child=serializers.FileField(validators=[validate_file_size]),
        allow_empty=True, required=False
    )
    purple_team_files = serializers.ListField(
        child=serializers.FileField(validators=[validate_file_size]),
        allow_empty=True, required=False
    )
    yellow_team_files = serializers.ListField(
        child=serializers.FileField(validators=[validate_file_size]),
        allow_empty=True, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category_id'].choices = self.get_scenario_category_choices()

    def get_scenario_category_choices(self):
        categories = scenario_category_collection.find(
            {}, {'scenario_category_id': 1, 'scenario_category_name': 1}
        )
        return [(c['scenario_category_id'], c['scenario_category_name']) for c in categories]

    def validate(self, data):
        data['user'] = self.context['request'].user

        if data['user'].get('user_role') != "WHITE TEAM":
            raise serializers.ValidationError("Only white team members can create a scenario.")

        if corporate_scenario_collection.find_one({'name': data['name']}):
            raise serializers.ValidationError("Scenario Name already exists.")

        if data.get('thumbnail') and not data['thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png')):
            raise serializers.ValidationError("Scenario Thumbnail must be jpeg/jpg/png.")

        for team_files in ['red_team_files', 'blue_team_files', 'purple_team_files', 'yellow_team_files']:
            if data.get(team_files):
                for doc in data[team_files]:
                    if not doc.name.lower().endswith(('pdf',)):
                        raise serializers.ValidationError("Scenario Documents must be PDF only.")

        return data

    def create(self, validated_data):
        scenario_id = generate_random_string('scenario_id', length=15)
        now = datetime.datetime.now()
        ts = str(now.timestamp()).split(".")[0]

        # ---------- FILE UPLOADS (unchanged) ----------
        files_data = {}
        for team_files, team_key in [
            ('red_team_files', 'red_team'),
            ('blue_team_files', 'blue_team'),
            ('purple_team_files', 'purple_team'),
            ('yellow_team_files', 'yellow_team')
        ]:
            urls = []
            if validated_data.get(team_files):
                for f in validated_data[team_files]:
                    _, ext = os.path.splitext(f.name)
                    rnd = generate_random_string(id_type="File", length=40)
                    new_name = f"{scenario_id}_document_{rnd}{ext.lower()}"
                    with open(f"static/documents/corporate_scenario_documents/{new_name}", "wb+") as dst:
                        for chunk in f.chunks():
                            dst.write(chunk)
                    urls.append(f"{API_URL}/static/documents/corporate_scenario_documents/{new_name}")
            files_data[team_key] = urls

        # ---------- THUMBNAIL ----------
        if validated_data.get("thumbnail"):
            thumb = validated_data.pop("thumbnail")
            _, ext = os.path.splitext(thumb.name)
            thumb_name = f"{scenario_id}_thumbnail_{ts}{ext.lower()}"
            with open(f"static/images/corporate_scenario_thumbnails/{thumb_name}", "wb+") as dst:
                for chunk in thumb.chunks():
                    dst.write(chunk)
            thumbnail_url = f"{API_URL}/static/images/corporate_scenario_thumbnails/{thumb_name}"
        else:
            thumbnail_url = f"{API_URL}/static/images/scenario_game_thumbnails/default.jpg"

        # ---------- SCORING CONFIG (NEW & CLEAN) ----------
        scoring_type = validated_data.get("scoring_type", "standard")
        scoring_config = {
            "type": scoring_type
        }

        if scoring_type == "decay":
            scoring_config["decay"] = {
                "mode": "time",
                "start_after_minutes": validated_data.get("decay_start_after_minutes", 15),
                "penalty_per_interval": validated_data.get("decay_penalty_per_interval", 10),
                "interval_minutes": validated_data.get("decay_interval_minutes", 10),
                "min_score": validated_data.get("decay_min_score", 20)
            }

        scenario = {
            "id": scenario_id,
            "creator_id": validated_data["user"]["user_id"],
            "name": validated_data["name"],
            "category_id": validated_data["category_id"],
            "severity": validated_data["severity"],
            "description": validated_data["description"],
            "objective": validated_data.get("objective", ""),
            "prerequisite": validated_data.get("prerequisite", ""),
            "thumbnail_url": thumbnail_url,
            "files_data": files_data,

            "type": validated_data["type"],              # FLAG / MILESTONE
            "scoring_config": scoring_config,            # ✅ NEW

            "phases": [],
            "infra_id": None,
            "is_prepared": False,
            "is_approved": False,
            "created_at": now,
            "updated_at": now
        }

        corporate_scenario_collection.insert_one(scenario)
        scenario.pop("_id", None)
        return scenario



class CorporateScenarioPhaseSerializer(serializers.Serializer):
    scenario_id = serializers.CharField()
    phases = serializers.ListField(child=serializers.DictField())

    def validate(self, data):
        scenario = corporate_scenario_collection.find_one({"id": data["scenario_id"]}, {"_id": 0})
        if not scenario:
            raise serializers.ValidationError("Invalid Scenario ID.")
        if not isinstance(data.get("phases"), list):
            raise serializers.ValidationError({"phases": "phases must be a list"})
        return data

    def create(self, validated_data):
        scenario_id = validated_data["scenario_id"]
        phases = validated_data["phases"]
        now = datetime.datetime.now()

        phase_list = []
        for phase in phases:
            if not isinstance(phase, dict):
                continue

            pid = phase.get("local_id") or phase.get("id") or generate_random_string("PHASE", 12)
            pname = phase.get("phase_name") or phase.get("name") or ""

            phase_list.append({
                "id": pid,
                "phase_name": pname,  # ✅ PreviewPanel expects phase_name
                "name": pname,        # ✅ FlagMilestonePanel sometimes expects name
            })

        corporate_scenario_collection.update_one(
            {"id": scenario_id},
            {"$set": {"phases": phase_list, "updated_at": now}}
        )

        return {"phases": phase_list}


class CorporateScenarioFlagCreateSerializer(serializers.Serializer):
    scenario_id = serializers.CharField()
    flags = serializers.ListField(child=serializers.DictField())

    def validate(self, data):
        scenario = corporate_scenario_collection.find_one({"id": data["scenario_id"]}, {"_id": 0})
        if not scenario:
            raise serializers.ValidationError("Invalid Scenario ID.")
        if scenario.get("type") != "FLAG":
            raise serializers.ValidationError("This scenario is not FLAG type.")
        if not isinstance(data.get("flags"), list):
            raise serializers.ValidationError({"flags": "flags must be a list"})
        return data

    def create(self, validated_data):
        scenario_id = validated_data["scenario_id"]
        flags = validated_data["flags"]
        now = datetime.datetime.now()

        created = []

        # ✅ collect ids by team to store inside scenario doc
        by_team = {
            "red_team": [],
            "blue_team": [],
            "purple_team": [],
            "yellow_team": [],
        }

        def team_key(team):
            t = (team or "").upper()
            return {
                "RED": "red_team",
                "BLUE": "blue_team",
                "PURPLE": "purple_team",
                "YELLOW": "yellow_team",
            }.get(t)

        for f in flags:
            if not isinstance(f, dict):
                continue

            fid = generate_random_string("FLAG", 16)

            flag_doc = {
                "id": fid,
                "scenario_id": scenario_id,
                "team": (f.get("team") or "").upper(),
                "phase_id": f.get("phase_id", ""),

                # keep your current naming
                "question": f.get("name", ""),
                "answer": f.get("answer", ""),
                "hint": f.get("hint", ""),

                "score": int(f.get("points", 100) or 100),
                "hint_penalty": int(f.get("hint_penalty", 0) or 0),

                "placeholder": f.get("placeholder", ""),
                "show_placeholder": bool(f.get("show_placeholder", True)),
                "is_locked": bool(f.get("is_locked", False)),

                "created_at": now,
                "updated_at": now,
            }

            # ✅ insert (mongo will add _id internally, but we are NOT returning it)
            flag_data_collection.insert_one(flag_doc)

            # ✅ ensure response JSON is safe
            flag_doc.pop("_id", None)

            created.append(flag_doc)

            tk = team_key(flag_doc["team"])
            if tk:
                by_team[tk].append(fid)

        # ✅ IMPORTANT: store flag ids into scenario doc (set to avoid duplicates)
        corporate_scenario_collection.update_one(
            {"id": scenario_id},
            {
                "$set": {
                    "flag_data": by_team,  # overwrite with latest selection
                    "updated_at": now,
                }
            }
        )

        return {"flags": created}


class CorporateScenarioMilestoneCreateSerializer(serializers.Serializer):
    scenario_id = serializers.CharField()
    milestones = serializers.ListField(child=serializers.DictField())

    def validate(self, data):
        scenario = corporate_scenario_collection.find_one({"id": data["scenario_id"]}, {"_id": 0})
        if not scenario:
            raise serializers.ValidationError("Invalid Scenario ID.")
        if scenario.get("type") != "MILESTONE":
            raise serializers.ValidationError("This scenario is not MILESTONE type.")
        if not isinstance(data.get("milestones"), list):
            raise serializers.ValidationError({"milestones": "milestones must be a list"})
        return data

    def create(self, validated_data):
        scenario_id = validated_data["scenario_id"]
        milestones = validated_data["milestones"]
        now = datetime.datetime.now()

        created = []

        by_team = {
            "red_team": [],
            "blue_team": [],
            "purple_team": [],
            "yellow_team": [],
        }

        def team_key(team):
            t = (team or "").upper()
            return {
                "RED": "red_team",
                "BLUE": "blue_team",
                "PURPLE": "purple_team",
                "YELLOW": "yellow_team",
            }.get(t)

        for m in milestones:
            if not isinstance(m, dict):
                continue

            mid = generate_random_string("MILE", 16)

            doc = {
                "id": mid,
                "scenario_id": scenario_id,
                "team": (m.get("team") or "").upper(),
                "phase_id": m.get("phase_id", ""),

                "name": m.get("name", ""),
                "description": m.get("description", ""),

                "hint": m.get("hint", ""),
                "score": int(m.get("points", 100) or 100),
                "hint_penalty": int(m.get("hint_penalty", 0) or 0),

                "is_locked": bool(m.get("is_locked", False)),

                # optional fields (won't hurt)
                "placeholder": m.get("placeholder", ""),
                "show_placeholder": bool(m.get("show_placeholder", True)),

                "created_at": now,
                "updated_at": now,
            }

            milestone_data_collection.insert_one(doc)

            # ✅ ensure response JSON safe
            doc.pop("_id", None)

            created.append(doc)

            tk = team_key(doc["team"])
            if tk:
                by_team[tk].append(mid)

        # ✅ IMPORTANT: store milestone ids into scenario doc (set to avoid duplicates)
        corporate_scenario_collection.update_one(
            {"id": scenario_id},
            {
                "$set": {
                    "milestone_data": by_team,
                    "updated_at": now,
                }
            }
        )

        return {"milestones": created}
    

class CorporateScenarioWalkthroughCreateSerializer(serializers.Serializer):
    scenario_id = serializers.CharField()
    team = serializers.ChoiceField(choices=["RED", "BLUE", "PURPLE", "YELLOW"])
    phase_id = serializers.CharField(required=False)
    files = serializers.ListField(
        child=serializers.FileField(validators=[validate_file_size]),
        allow_empty=False
    )

    def validate(self, data):
        scenario = corporate_scenario_collection.find_one(
            {"id": data["scenario_id"]}, {"_id": 1}
        )
        if not scenario:
            raise serializers.ValidationError("Invalid Scenario ID")
        return data

    def create(self, validated_data):
        scenario_id = validated_data["scenario_id"]
        team = validated_data["team"]
        files = validated_data["files"]

        team_key_map = {
            "RED": "red_team",
            "BLUE": "blue_team",
            "PURPLE": "purple_team",
            "YELLOW": "yellow_team",
        }
        team_key = team_key_map[team]

        now = datetime.datetime.utcnow()

        base_dir = "static/documents/scenario_walkthroughs"
        os.makedirs(base_dir, exist_ok=True)

        uploaded_urls = []

        for f in files:
            if not f.name.lower().endswith(".pdf"):
                raise serializers.ValidationError("Only PDF allowed")

            rnd = generate_random_string("DOC", 20)
            _, ext = os.path.splitext(f.name)
            new_name = f"{scenario_id}_{team}_{rnd}{ext}"
            path = f"{base_dir}/{new_name}"

            with open(path, "wb+") as dst:
                for chunk in f.chunks():
                    dst.write(chunk)

            uploaded_urls.append(f"{API_URL}/{path}")

        # ✅ ONLY update scenario.files_data
        corporate_scenario_collection.update_one(
            {"id": scenario_id},
            {
                "$push": {
                    f"files_data.{team_key}": {"$each": uploaded_urls}
                },
                "$set": {"updated_at": now},
            }
        )

        return {
            "team": team,
            "uploaded_files": uploaded_urls,
        }
    
class CorporateScenarioWalkthroughListSerializer(serializers.Serializer):
    def get(self, scenario_id, team):
        scenario = corporate_scenario_collection.find_one(
            {"id": scenario_id}, {"_id": 0, "files_data": 1}
        )
        if not scenario:
            return []

        team_key_map = {
            "RED": "red_team",
            "BLUE": "blue_team",
            "PURPLE": "purple_team",
            "YELLOW": "yellow_team",
        }
        team_key = team_key_map.get(team)

        return scenario.get("files_data", {}).get(team_key, [])
    
class NetworkSerializer(serializers.Serializer):
    network_name = serializers.CharField(max_length=50, min_length=3)
    subnet_name = serializers.CharField(max_length=50, min_length=3)
    cidr_ip = serializers.CharField(max_length=18, min_length=7)

    def validate_cidr_ip(self, value):
        try:
            network_range = ipaddress.ip_network(value, strict=False)
            if not network_range.overlaps(ipaddress.ip_network('192.168.0.0/16')):
                raise serializers.ValidationError('CIDR must be within the 192.168.0.0/16 subnet')
        except ValueError as e:
            raise serializers.ValidationError(f'{value} is not a valid CIDR notation. {str(e)}')
        return value


class RouterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50, min_length=3)
    is_internet_required = serializers.BooleanField()
    network_name = serializers.ListField(child=serializers.CharField())  # List of network names


class FirewallSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50, min_length=3)
    network_name = serializers.ListField(child=serializers.CharField())
    flavor = serializers.CharField(max_length=50)
    image = serializers.CharField(max_length=50)
    team = serializers.ChoiceField(choices=['RED', 'BLUE', 'PURPLE', 'YELLOW'])
    ip_address = serializers.CharField(max_length=15, min_length=7, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].choices = get_instance_images()
        self.fields['flavor'].choices = get_instance_flavors()


class InstanceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50, min_length=3)
    flavor = serializers.CharField(max_length=50)
    # network = serializers.CharField(max_length=50)
    network = serializers.ListField(child=serializers.CharField())
    image = serializers.CharField(max_length=50)
    team = serializers.ChoiceField(choices=['RED', 'BLUE', 'PURPLE', 'YELLOW'])
    ip_address = serializers.CharField(max_length=15, min_length=7, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].choices = get_instance_images()
        self.fields['flavor'].choices = get_instance_flavors()


class CorporateScenarioInfraSerializer(serializers.Serializer):
    scenario_infra = serializers.JSONField(write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        scenario_id = self.context.get('scenario_id')
        data['user'] = self.context['request'].user

        scenario = corporate_scenario_collection.find_one({"id": scenario_id, "creator_id": data['user'].get("user_id")}, {"_id": 0})
        if not scenario:
            raise serializers.ValidationError("Invalid Scenario ID.")
        else:
            data['scenario'] = scenario

        if not data['scenario_infra'].get('networks'):
            raise serializers.ValidationError("Atleast one network is required.")
        else:
            networks = []
            for network in data['scenario_infra']['networks']:
                network_serializer = NetworkSerializer(data=network)
                if network_serializer.is_valid():
                    network_validated_data = network_serializer.validated_data
                    networks.append(network_validated_data)
                else:
                    raise serializers.ValidationError(network_serializer.errors)
            data['networks'] = networks

        if data['scenario_infra'].get('routers'):
            routers = []
            for router in data['scenario_infra']['routers']:
                router_serializer = RouterSerializer(data=router)
                if router_serializer.is_valid():
                    router_validated_data = router_serializer.validated_data
                    routers.append(router_validated_data)
                else:
                    raise serializers.ValidationError(router_serializer.errors)

        if not data['scenario_infra'].get('instances'):
            raise serializers.ValidationError("Atleast one instance is required.")
        else:
            instances = []
            for instance in data['scenario_infra']['instances']:
                instance_serializer = InstanceSerializer(data=instance)
                if instance_serializer.is_valid():
                    instance_validated_data = instance_serializer.validated_data
                    instances.append(instance_validated_data)
                else:
                    raise serializers.ValidationError(instance_serializer.errors)

        firewalls = []
        if data['scenario_infra'].get('firewall'):
            for firewall in data['scenario_infra']['firewall']:
                firewall_serializer = FirewallSerializer(data=firewall)
                if firewall_serializer.is_valid():
                    firewall_validated_data = firewall_serializer.validated_data
                    firewalls.append(firewall_validated_data)
                else:
                    raise serializers.ValidationError(firewall_serializer.errors)

        data.pop("scenario_infra")
        data["networks"] = networks
        data["routers"] = routers
        data["instances"] = instances
        data["firewall"] = firewalls
        return data

    def create(self, validated_data):
        id = generate_random_string(id_type="Corporate Scenario Infra", length=20)
        current_time = datetime.datetime.now()
        infra = {
            "id": id,
            "networks": validated_data["networks"],
            "routers": validated_data["routers"],
            "instances": validated_data["instances"],
            "firewall": validated_data["firewall"],
            "created_at": current_time,
            "updated_at": current_time,
        }
        corporate_scenario_infra_collection.insert_one(infra)
        corporate_scenario_collection.update_one({"id": validated_data["scenario"]["id"]}, {"$set": {
            "infra_id": id,
            "is_prepared": True,
            "updated_at": current_time
        }})

        validated_data["scenario_infra"] = infra
        return infra


class CorporateScenarioListSerializer(serializers.Serializer):
    def get(self):
        scenarios = list(corporate_scenario_collection.find({
            'is_prepared': True,
            'is_approved': True,
        }, {'_id': 0, "infra_id": 0, "files_data": 0, "is_prepared": 0, "is_approved": 0}))
        for scenario in scenarios:
            category_name = scenario_category_collection.find_one({"scenario_category_id": scenario["category_id"]}, {"_id": 0, "scenario_category_name": 1})
            scenario["category_name"] = category_name["scenario_category_name"]

            user = user_collection.find_one({"user_id": scenario["creator_id"]})
            scenario["creator_name"] = user["user_full_name"]

            if scenario.get("milestone_data"):
                inner_score = 0
                if scenario["milestone_data"].get("red_team"):
                    for i in scenario["milestone_data"].get("red_team"):
                        score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                        inner_score += score["score"]
                if scenario["milestone_data"].get("blue_team"):
                    for i in scenario["milestone_data"].get("blue_team"):
                        score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                        inner_score += score["score"]
                if scenario["milestone_data"].get("purple_team"):
                    for i in scenario["milestone_data"].get("purple_team"):
                        score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                        inner_score += score["score"]
                if scenario["milestone_data"].get("yellow_team"):
                    for i in scenario["milestone_data"].get("yellow_team"):
                        score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                        inner_score += score["score"]

            else:
                inner_score = 0
                if scenario["flag_data"].get("red_team"):
                    for i in scenario["flag_data"].get("red_team"):
                        score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                        inner_score += score["score"]
                if scenario["flag_data"].get("blue_team"):
                    for i in scenario["flag_data"].get("blue_team"):
                        score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                        inner_score += score["score"]
                if scenario["flag_data"].get("purple_team"):
                    for i in scenario["flag_data"].get("purple_team"):
                        score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                        inner_score += score["score"]
                if scenario["flag_data"].get("yellow_team"):
                    for i in scenario["flag_data"].get("yellow_team"):
                        score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                        inner_score += score["score"]

            scenario["points"] = inner_score

        return scenarios


class CorporateScenarioDetailSerializer(serializers.Serializer):

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def get(self, scenario_id, user):
        assigned_games = user_profile_collection.find_one({"user_id": user["user_id"]}, {"_id": 0, "assigned_games": 1})
        if not assigned_games["assigned_games"]["display_all_corporate"] and scenario_id not in assigned_games["assigned_games"]["corporate"]:
            return {
                "errors": {
                    "non_field_errors": ["You are not authorised to view this game."]
                }
            }

        query = {"id": scenario_id, "is_prepared": True, "is_approved": True}
        projection = {'_id': 0, "is_prepared": 0, "is_approved": 0}

        scenario = corporate_scenario_collection.find_one(query, projection)

        if not scenario:
            # raise serializers.ValidationError("Invalid Scenario ID")
            return {"errors": "Invalid Scenario ID"}

        category_name = scenario_category_collection.find_one({"scenario_category_id": scenario["category_id"]}, {"_id": 0, "scenario_category_name": 1})
        scenario["category_name"] = category_name["scenario_category_name"]

        scenario["type"] = "Milestone" if scenario.get("milestone_data") else "Flag"

        user = user_collection.find_one({"user_id": scenario["creator_id"]})
        scenario["creator_name"] = user["user_full_name"]

        scenario_infra = corporate_scenario_infra_collection.find_one({"id": scenario["infra_id"]}, {"_id": 0})
        instance_names = []
        corporate_hardware_details = {
            "vcpu": 0,
            "disk_size": 0,
            "RAM": 0,
            "vm_count": 0
        }
        for instance in scenario_infra["instances"]:
            instance_names.append(instance["name"])
            flavor_detail = get_flavor_detail(instance["flavor"])

            ram_as_flavor = round(flavor_detail['ram'])

            corporate_hardware_details['vcpu'] += flavor_detail['vcpus']
            corporate_hardware_details['disk_size'] += flavor_detail['disk']
            corporate_hardware_details['RAM'] += ram_as_flavor
            corporate_hardware_details['vm_count'] += 1

        corporate_hardware_details['disk_size'] = f"{corporate_hardware_details['disk_size']} GB"
        corporate_hardware_details['RAM'] = f"{round(corporate_hardware_details['RAM'] / 1024)} GB"

        scenario["machine_names"] = instance_names

        scenario["hardware_details"] = corporate_hardware_details

        if scenario.get("milestone_data"):
            inner_score = 0
            if scenario["milestone_data"].get("red_team"):
                for i in scenario["milestone_data"].get("red_team"):
                    score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                    inner_score += score["score"]
            if scenario["milestone_data"].get("blue_team"):
                for i in scenario["milestone_data"].get("blue_team"):
                    score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                    inner_score += score["score"]
            if scenario["milestone_data"].get("purple_team"):
                for i in scenario["milestone_data"].get("purple_team"):
                    score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                    inner_score += score["score"]
            if scenario["milestone_data"].get("yellow_team"):
                for i in scenario["milestone_data"].get("yellow_team"):
                    score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                    inner_score += score["score"]

        else:
            inner_score = 0
            if scenario["flag_data"].get("red_team"):
                for i in scenario["flag_data"].get("red_team"):
                    score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                    inner_score += score["score"]
            if scenario["flag_data"].get("blue_team"):
                for i in scenario["flag_data"].get("blue_team"):
                    score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                    inner_score += score["score"]
            if scenario["flag_data"].get("purple_team"):
                for i in scenario["flag_data"].get("purple_team"):
                    score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                    inner_score += score["score"]
            if scenario["flag_data"].get("yellow_team"):
                for i in scenario["flag_data"].get("yellow_team"):
                    score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                    inner_score += score["score"]

        scenario["points"] = inner_score

        return scenario


class CorporateScenarioAchiversSerializer(serializers.Serializer):

    def get(self, scenario_id):
        scenario = corporate_scenario_collection.find_one({"id": scenario_id, "is_prepared": True, "is_approved": True})
        if not scenario:
            return {"errors": "Invalid Scenario ID"}

        corporate_games = list(
            archive_participant_collection.find({'scenario_id': scenario_id}, {"_id": 0, "user_id": 1, "scenario_id": 1, "total_obtained_score": 1, "total_score": 1}))
        if corporate_games:
            p_array = {}
            for games in corporate_games:
                if p_array.get(games["user_id"]):
                    p_array[games["user_id"]].append(games)
                else:
                    p_array[games["user_id"]] = [games, ]

            max_score_objects = {}
            for user_id, records in p_array.items():
                max_score_obj = max(records, key=lambda x: x['total_obtained_score'])
                max_score_objects[user_id] = max_score_obj

            score_array = []
            for user_id, obj in max_score_objects.items():
                user_info = user_collection.find_one({"user_id": obj["user_id"]}, {"_id": 0, "user_full_name": 1, "user_role": 1, "user_avatar": 1})
                obj.update(user_info)
                obj["badge_earned"] = "Gold"
                obj["score_obtained"] = str(obj.get("total_obtained_score", 0)) + '/' + str(obj["total_score"])
                score_array.append(obj)
            sorted_achivers_data = sorted(score_array, key=lambda x: x["total_obtained_score"], reverse=True)
        else:
            sorted_achivers_data = []

        return sorted_achivers_data


class CorporateScenarioInfraDetailSerializer(serializers.Serializer):

    def get(self, infra_id):
        infra = corporate_scenario_infra_collection.find_one(
            {"id": infra_id},
            {"_id": 0}
        )

        if not infra:
            return {
                "errors": {
                    "non_field_errors": ["Infra not found"]
                }
            }

        return infra

class CorporateScenarioStartSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(write_only=True)
    teams = serializers.JSONField(write_only=True)

    def validate(self, data):
        request = self.context["request"]
        user = request.user
        data["user"] = user

        # ---- Scenario checks ----
        scenario = corporate_scenario_collection.find_one(
            {"id": data["scenario_id"], "is_approved": True},
            {"_id": 0}
        )
        if not scenario:
            raise serializers.ValidationError("Invalid Scenario ID")

        if user.get("user_role") != "WHITE TEAM":
            raise serializers.ValidationError("Only WHITE TEAM can start a scenario")

        if active_scenario_collection.find_one({"started_by": user["user_id"]}):
            raise serializers.ValidationError("This WHITE TEAMER already started a scenario")

        # ---- Infra ----
        infra = corporate_scenario_infra_collection.find_one(
            {"id": scenario["infra_id"]},
            {"_id": 0}
        )
        if not infra:
            raise serializers.ValidationError("Scenario infra not found")

        infra_instances = infra["instances"]

        # Build allowed mapping: ROLE → MACHINES
        allowed = {}
        for inst in infra_instances:
            role = inst["team"].upper()
            allowed.setdefault(role, []).append(inst["name"])

        # ---- Validation state ----
        #used_machines = set()
        team_machine_usage = {}  # team_name → set(machines)
        participant_machine_dict = {}  # team → {machine → user_id}

        used_users = set()
        participant_machine_dict = {}

        # ---- Teams validation ----
        if not data["teams"]:
            raise serializers.ValidationError("At least one team is required")

        all_infra_machines = {i["name"] for i in infra_instances}

        team_machine_usage = {}
        participant_machine_dict = {}

        for team in data["teams"]:
            team_name = team.get("team_name")
            if not team_name:
                raise serializers.ValidationError("team_name is required")

            team_machine_usage[team_name] = set()
            participant_machine_dict[team_name] = {}

            for player in team.get("players", []):
                email = player.get("email")
                role = player.get("role", "").upper()
                machines = player.get("machines", [])

                if not email or not role or not machines:
                    raise serializers.ValidationError("Email, role and machines are required")

                user_obj = user_collection.find_one({"email": email})
                if not user_obj:
                    raise serializers.ValidationError(f"{email} is not a registered user")

                if user_obj["user_role"] == "WHITE TEAM":
                    raise serializers.ValidationError("WHITE TEAM cannot be a participant")

                if role not in allowed:
                    raise serializers.ValidationError(f"Role {role} has no machines in infra")

                for m in machines:
                    if m not in allowed[role]:
                        raise serializers.ValidationError(f"{m} is not allowed for role {role}")

                    # 🔐 per-team uniqueness
                    if m in team_machine_usage[team_name]:
                        raise serializers.ValidationError(
                            f"Machine {m} already assigned in team {team_name}"
                        )

                    team_machine_usage[team_name].add(m)
                    participant_machine_dict[team_name][m] = user_obj["user_id"]

            # 🚨 Ensure THIS TEAM assigned all machines
            if team_machine_usage[team_name] != all_infra_machines:
                raise serializers.ValidationError(
                    f"Team '{team_name}' must assign ALL infrastructure machines"
                )

        data["participant_machine_dict"] = participant_machine_dict
        data["scenario"] = scenario
        data["scenario_infra"] = infra
        return data

    def create(self, validated_data):
        start_corporate_game.delay(validated_data)
        return {"message": "Please wait while we are creating dedicated environment for you."}

class CorporateScenarioConsoleSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(instance)
        return data

    def get(self, active_scenario_id, user):
        active_scenario = active_scenario_collection.find_one({"id": active_scenario_id}, {"_id": 0})
        if not active_scenario:
            return {"errors": "No Active Game Console Found."}

        if not active_scenario.get("participant_data", {}).get(user["user_id"]):
            return {"errors": "Invalid Active Scenario ID"}

        participant_data_id = active_scenario["participant_data"][user["user_id"]]
        participant_data = participant_data_collection.find_one({"id": participant_data_id}, {"_id": 0})
        if not participant_data:
            return {"errors": "Invalid Active Scenario ID"}

        scenario = corporate_scenario_collection.find_one({"id": active_scenario["scenario_id"]}, {"_id": 0})
        if not scenario:
            return {"errors": "Scenario not found"}

        # ---------- MULTI MACHINE SUPPORT ----------
        # Determine accessible instances for this user
        instance_ids = []
        if active_scenario.get("participant_instances", {}).get(user["user_id"]):
            instance_ids = active_scenario["participant_instances"][user["user_id"]]
        else:
            # backward compatible
            if participant_data.get("instance_id"):
                instance_ids = [participant_data["instance_id"]]

        # Selected instance (for iframe)
        selected_instance_id = participant_data.get("selected_instance_id") or (instance_ids[0] if instance_ids else None)

        consoles = []
        console_url = None
        if selected_instance_id:
            for iid in instance_ids:
                try:
                    instance = get_cloud_instance(iid)
                    console = get_instance_console(instance)
                    url = console.url
                except Exception:
                    url = None
                consoles.append({"instance_id": iid, "console_url": url})

            # current console url (selected)
            for c in consoles:
                if c["instance_id"] == selected_instance_id:
                    console_url = c["console_url"]

        # ---------- TEAM FILES ----------
        files_data = scenario.get("files_data") or {}
        team_key_map = {"RED":"red_team","BLUE":"blue_team","PURPLE":"purple_team","YELLOW":"yellow_team"}
        file_urls = files_data.get(team_key_map.get(participant_data.get("team"), "red_team"), [])

        # ---------- RESOURCE CREDS ----------
        username = "NA"
        password = "NA"
        try:
            if selected_instance_id:
                image_id = [i["image"] for i in active_scenario.get("instances", []) if i["id"] == selected_instance_id]
                if image_id:
                    resource = resource_credentials_collection.find_one(
                        {"image_id": image_id[0]},
                        {'_id': 0, 'username': 1, 'password': 1}
                    )
                    if resource:
                        username = resource.get("username", "NA")
                        password = resource.get("password", "NA")
        except Exception:
            pass

        scoring_config = scenario.get("scoring_config") or {"type": "standard"}

        data = {
            "active_scenario_id": active_scenario_id,
            "started_by": active_scenario.get("started_by"),
            "start_time": active_scenario.get("start_time"),
            "participant_id": user["user_id"],
            "team": participant_data.get("team"),
            "total_score": participant_data.get("total_score", 0),
            "total_obtained_score": participant_data.get("total_obtained_score", 0),

            # NEW
            "scoring_config": scoring_config,
            "consoles": consoles,
            "selected_instance_id": selected_instance_id,

            # existing
            "console_url": console_url,
            "name": scenario.get("name"),
            "category_id": scenario.get("category_id"),
            "severity": scenario.get("severity"),
            "thumbnail_url": scenario.get("thumbnail_url"),
            "document_urls": file_urls,
            "username": username,
            "password": password,
        }

        # ---------- KILL CHAIN PHASE MAP ----------
        # scenario["phases"] items: {id, phase_name, name}
        phases = scenario.get("phases") or []
        phase_map = {p["id"]: p for p in phases}

        def phase_bucket():
            return {
                "phase_name": "",
                "total": 0,
                "completed": 0,
                "pending": 0,
                "locked": False,
                "items": []
            }

        items_by_phase = {}

        # ---------- FLAG ----------
        if participant_data.get("flag_data") is not None:
            flag_items = []
            for f in participant_data.get("flag_data", []):
                flag_db = flag_data_collection.find_one({"id": f["flag_id"]}, {"_id": 0}) or {}

                # phase_id: prefer participant copy, fallback to db
                phase_id = f.get("phase_id") or flag_db.get("phase_id")
                locked = (f.get("status") is False) or f.get("locked_by_admin", False)

                item = {
                    "flag_id": f.get("flag_id"),
                    "phase_id": phase_id,
                    "index": flag_db.get("index"),
                    "score": flag_db.get("score") if not locked else "",
                    "question": flag_db.get("question") if not locked else "",
                    "show_placeholder": flag_db.get("show_placeholder", False),
                    "placeholder": flag_db.get("placeholder", ""),
                    "locked": locked,
                    "locked_label": "Locked by Admin" if locked else "",
                    "is_correct": f.get("is_correct", False),
                    "obtained_score": f.get("obtained_score", 0),
                    "retires": f.get("retires", 0),
                    "hint_used": f.get("hint_used", False),
                    "hint_string": f.get("hint_string", ""),
                    # timestamps (NEW)
                    "submitted_at": f.get("submitted_at"),
                    "achieved_at": f.get("achieved_at"),
                    "approved_at": f.get("approved_at"),
                    "unlocked_at": f.get("unlocked_at"),
                    "updated_at": f.get("updated_at"),
                }
                flag_items.append(item)

                # group by phase
                pid = phase_id or "unassigned"
                if pid not in items_by_phase:
                    items_by_phase[pid] = phase_bucket()
                    items_by_phase[pid]["phase_name"] = phase_map.get(pid, {}).get("phase_name", "Unassigned")
                items_by_phase[pid]["total"] += 1
                if locked:
                    items_by_phase[pid]["locked"] = True
                if item["is_correct"]:
                    items_by_phase[pid]["completed"] += 1
                items_by_phase[pid]["items"].append(item)

            for pid in items_by_phase:
                items_by_phase[pid]["pending"] = items_by_phase[pid]["total"] - items_by_phase[pid]["completed"]

            data["scenario_type"] = "FLAG"
            data["flag_data"] = flag_items

        # ---------- MILESTONE ----------
        elif participant_data.get("milestone_data") is not None:
            milestone_items = []
            for m in participant_data.get("milestone_data", []):
                mdb = milestone_data_collection.find_one({"id": m["milestone_id"]}, {"_id": 0}) or {}

                phase_id = m.get("phase_id") or mdb.get("phase_id")
                locked = (m.get("status") is False) or m.get("locked_by_admin", False)

                item = {
                    "milestone_id": m.get("milestone_id"),
                    "phase_id": phase_id,
                    "milestone_index": mdb.get("index"),
                    "milestone_name": mdb.get("name") if not locked else "",
                    "milestone_description": mdb.get("description") if not locked else "",
                    "milestone_score": mdb.get("score") if not locked else "",
                    "show_placeholder": mdb.get("show_placeholder", False),
                    "placeholder": mdb.get("placeholder", ""),
                    # state
                    "locked": locked,
                    "locked_label": "Locked by Admin" if locked else "",
                    "is_achieved": m.get("is_achieved", False),
                    "is_approved": m.get("is_approved", False),
                    "obtained_score": m.get("obtained_score", 0),

                    # NEW submissions
                    "submitted_text": m.get("submitted_text", ""),
                    "evidence_files": m.get("evidence_files", []),

                    # timestamps (NEW)
                    "submitted_at": m.get("submitted_at"),
                    "achieved_at": m.get("achieved_at"),
                    "approved_at": m.get("approved_at"),
                    "rejected_at": m.get("rejected_at"),
                    "unlocked_at": m.get("unlocked_at"),
                    "updated_at": m.get("updated_at"),
                    "hint_used": m.get("hint_used", False),
                    "hint_string": m.get("hint_string", ""),
                    "hint_used_at": m.get("hint_used_at"),
                }
                milestone_items.append(item)

                pid = phase_id or "unassigned"
                if pid not in items_by_phase:
                    items_by_phase[pid] = phase_bucket()
                    items_by_phase[pid]["phase_name"] = phase_map.get(pid, {}).get("phase_name", "Unassigned")
                items_by_phase[pid]["total"] += 1
                if locked:
                    items_by_phase[pid]["locked"] = True
                if item["is_approved"] or item["is_achieved"]:
                    items_by_phase[pid]["completed"] += 1
                items_by_phase[pid]["items"].append(item)

            for pid in items_by_phase:
                items_by_phase[pid]["pending"] = items_by_phase[pid]["total"] - items_by_phase[pid]["completed"]

            data["scenario_type"] = "MILESTONE"
            data["milestone_data"] = milestone_items

        else:
            return {"errors": "Flag/Milestone Data Retrieval Error"}

        # ---------- KILL CHAIN PROGRESS (for UI bar/graph) ----------
        kill_chain_progress = []
        # preserve scenario order
        for p in phases:
            pid = p["id"]
            bucket = items_by_phase.get(pid) or {"total": 0, "completed": 0, "pending": 0, "locked": False}
            total = bucket["total"]
            completed = bucket["completed"]
            pct = int((completed / total) * 100) if total else 0
            kill_chain_progress.append({
                "phase_id": pid,
                "phase_name": p.get("phase_name") or p.get("name"),
                "total": total,
                "completed": completed,
                "pending": total - completed,
                "percent": pct,
                "is_complete": (total > 0 and completed == total),
                "is_locked": bucket.get("locked", False),
            })

        data["items_by_phase"] = items_by_phase
        data["kill_chain_progress"] = kill_chain_progress

        return data

class CorporateScenarioSwitchMachineSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100, required=True)
    instance_id = serializers.CharField(max_length=100, required=True)

    def validate(self, data):
        user = self.context["request"].user
        active = active_scenario_collection.find_one({"id": data["active_scenario_id"]}, {"_id":0})
        if not active:
            raise serializers.ValidationError("Invalid Active Scenario ID")

        if not active.get("participant_data", {}).get(user["user_id"]):
            raise serializers.ValidationError("Invalid Active Scenario ID")

        allowed = []
        if active.get("participant_instances", {}).get(user["user_id"]):
            allowed = active["participant_instances"][user["user_id"]]
        else:
            # backward compatible
            participant_data_id = active["participant_data"][user["user_id"]]
            pd = participant_data_collection.find_one({"id": participant_data_id}, {"_id":0})
            if pd and pd.get("instance_id"):
                allowed = [pd["instance_id"]]

        if data["instance_id"] not in allowed:
            raise serializers.ValidationError("Instance not assigned to this user")
        data["participant_data_id"] = active["participant_data"][user["user_id"]]
        return data

    def create(self, validated_data):
        participant_data_collection.update_one(
            {"id": validated_data["participant_data_id"]},
            {"$set": {"selected_instance_id": validated_data["instance_id"], "updated_at": datetime.datetime.now()}}
        )
        return {"message": "Machine switched", "instance_id": validated_data["instance_id"]}

ALLOWED_CHAT_FILE_TYPES = (
    ".pdf", ".png", ".jpg", ".jpeg",
    ".txt", ".log", ".csv", ".json"
)

CHAT_UPLOAD_DIR = "static/chat_attachments"


class ScenarioChatSendSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField()
    channel_key = serializers.CharField()
    message = serializers.CharField(
        max_length=2000,
        allow_blank=True,
        required=False
    )
    attachments = serializers.ListField(
        child=serializers.FileField(validators=[validate_file_size]),
        required=False
    )

    def validate(self, data):
        message = data.get("message", "").strip()
        attachments = data.get("attachments", [])

        if not message and not attachments:
            raise serializers.ValidationError(
                "Either message or attachment is required"
            )

        for f in attachments:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_CHAT_FILE_TYPES:
                raise serializers.ValidationError(
                    f"File type {ext} not allowed"
                )

        return data

    def create(self, validated_data):
        user = self.context["request"].user
        now = timezone.now()

        attachments_meta = []

        for f in validated_data.get("attachments", []):
            ext = os.path.splitext(f.name)[1]
            att_id = f"ATT_{uuid.uuid4().hex[:12]}"
            new_name = f"{att_id}{ext}"

            save_path = os.path.join(CHAT_UPLOAD_DIR, new_name)
            os.makedirs(CHAT_UPLOAD_DIR, exist_ok=True)

            with open(save_path, "wb+") as dst:
                for chunk in f.chunks():
                    dst.write(chunk)

            attachments_meta.append({
                "id": att_id,
                "file_name": f.name,
                "file_type": f.content_type,
                "file_url": f"{settings.API_URL}/{save_path}",
                "uploaded_at": now.isoformat(),
            })

        # =====================================================
        # 🔑 FIX: DETERMINE CHAT ROLE FROM PARTICIPANT DATA
        # =====================================================
        sender_role = "WHITE"
        sender_team_group = "WHITE"

        participant = participant_data_collection.find_one(
            {"user_id": user["user_id"]},
            {"_id": 0}
        )

        if participant:
            # NORMAL PLAYER
            sender_role = (participant.get("team") or "WHITE").upper()
            sender_team_group = participant.get("team_group", "DEFAULT")
        else:
            # WHITE TEAM / ADMIN / SUPERADMIN
            if user.get("is_superadmin"):
                sender_role = "SUPERADMIN"
            else:
                sender_role = "WHITE"

            sender_team_group = "WHITE"

        # =====================================================
        # MESSAGE DOCUMENT
        # =====================================================
        doc = {
            "id": f"MSG_{int(now.timestamp() * 1000)}",
            "active_scenario_id": validated_data["active_scenario_id"],
            "channel_key": validated_data["channel_key"],

            "sender_user_id": str(user["user_id"]),
            "sender_name": str(user.get("user_full_name") or ""),
            "sender_role": sender_role,                 # ✅ FIXED
            "sender_team_group": sender_team_group,     # ✅ FIXED

            "message": validated_data.get("message", "").strip(),
            "attachments": attachments_meta,
            "created_at": now.isoformat(),
        }

        scenario_chat_messages_collection.insert_one(doc)
        doc.pop("_id", None)
        return doc

class ScenarioChatMessageListSerializer(serializers.Serializer):
    def get(self, channel_key):
        return list(
            scenario_chat_messages_collection.find(
                {"channel_key": channel_key},
                {"_id": 0}
            ).sort("created_at", 1)
        )
    
class CorporateScenarioAdminToggleFlagLockSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100, required=True)
    participant_id = serializers.CharField(max_length=100, required=True)
    flag_id = serializers.CharField(max_length=100, required=True)
    locked = serializers.BooleanField(required=True)  # True=lock, False=unlock

    def validate(self, data):
        user = self.context["request"].user
        active = active_scenario_collection.find_one({"id": data["active_scenario_id"]}, {"_id":0})
        if not active:
            raise serializers.ValidationError("Invalid Active Scenario ID")
        if active.get("started_by") != user["user_id"]:
            raise serializers.ValidationError("Permission Denied")
        if not active.get("participant_data", {}).get(data["participant_id"]):
            raise serializers.ValidationError("Invalid participant")

        data["participant_data_id"] = active["participant_data"][data["participant_id"]]
        return data

    def create(self, validated_data):
        now = datetime.datetime.now()
        status = not validated_data["locked"]  # your UI uses status=True to show question

        participant_data_collection.update_one(
            {"id": validated_data["participant_data_id"], "flag_data.flag_id": validated_data["flag_id"]},
            {"$set": {
                "flag_data.$.status": status,
                "flag_data.$.locked_by_admin": validated_data["locked"],
                "flag_data.$.unlocked_at": (now if status else None),
                "flag_data.$.updated_at": now,
                # start decay anchor at unlock (recommended)
                "flag_data.$.first_visible_at": (now if status else None),
            }}
        )

        return {"message": "Updated", "flag_id": validated_data["flag_id"], "locked": validated_data["locked"]}

class CorporateScenarioAdminToggleMilestoneLockSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100, required=True)
    participant_id = serializers.CharField(max_length=100, required=True)
    milestone_id = serializers.CharField(max_length=100, required=True)
    locked = serializers.BooleanField(required=True)

    def validate(self, data):
        user = self.context["request"].user
        active = active_scenario_collection.find_one({"id": data["active_scenario_id"]}, {"_id":0})
        if not active:
            raise serializers.ValidationError("Invalid Active Scenario ID")
        if active.get("started_by") != user["user_id"]:
            raise serializers.ValidationError("Permission Denied")
        if not active.get("participant_data", {}).get(data["participant_id"]):
            raise serializers.ValidationError("Invalid participant")

        data["participant_data_id"] = active["participant_data"][data["participant_id"]]
        return data

    def create(self, validated_data):
        now = datetime.datetime.now()
        status = not validated_data["locked"]

        participant_data_collection.update_one(
            {"id": validated_data["participant_data_id"], "milestone_data.milestone_id": validated_data["milestone_id"]},
            {"$set": {
                "milestone_data.$.status": status,
                "milestone_data.$.locked_by_admin": validated_data["locked"],
                "milestone_data.$.unlocked_at": (now if status else None),
                "milestone_data.$.updated_at": now,
                "milestone_data.$.first_visible_at": (now if status else None),
            }}
        )
        # TODO: websocket event "unlock"
        return {"message": "Updated", "milestone_id": validated_data["milestone_id"], "locked": validated_data["locked"]}


class CorporateScenarioAdminTogglePhaseLockSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100, required=True)
    participant_id = serializers.CharField(max_length=100, required=True)
    phase_id = serializers.CharField(max_length=100, required=True)
    locked = serializers.BooleanField(required=True)

    def validate(self, data):
        user = self.context["request"].user
        active = active_scenario_collection.find_one({"id": data["active_scenario_id"]}, {"_id":0})
        if not active:
            raise serializers.ValidationError("Invalid Active Scenario ID")
        if active.get("started_by") != user["user_id"]:
            raise serializers.ValidationError("Permission Denied")
        if not active.get("participant_data", {}).get(data["participant_id"]):
            raise serializers.ValidationError("Invalid participant")
        data["participant_data_id"] = active["participant_data"][data["participant_id"]]
        return data

    def create(self, validated_data):
        now = datetime.datetime.now()
        status = not validated_data["locked"]

        # Flags in this phase
        participant_data_collection.update_one(
            {"id": validated_data["participant_data_id"]},
            {"$set": {"updated_at": now}}
        )

        participant_data_collection.update_many(
            {"id": validated_data["participant_data_id"]},
            {"$set": {}}
        )

        # Use arrayFilters to update embedded arrays by phase_id
        participant_data_collection.update_one(
            {"id": validated_data["participant_data_id"]},
            {"$set": {
                "flag_data.$[f].status": status,
                "flag_data.$[f].locked_by_admin": validated_data["locked"],
                "flag_data.$[f].unlocked_at": (now if status else None),
                "flag_data.$[f].first_visible_at": (now if status else None),
                "flag_data.$[f].updated_at": now,
                "milestone_data.$[m].status": status,
                "milestone_data.$[m].locked_by_admin": validated_data["locked"],
                "milestone_data.$[m].unlocked_at": (now if status else None),
                "milestone_data.$[m].first_visible_at": (now if status else None),
                "milestone_data.$[m].updated_at": now,
            }},
            array_filters=[
                {"f.phase_id": validated_data["phase_id"]},
                {"m.phase_id": validated_data["phase_id"]},
            ]
        )

        # TODO: websocket event "unlock_phase" when unlocked
        return {"message": "Phase updated", "phase_id": validated_data["phase_id"], "locked": validated_data["locked"]}


class CorporateScenarioSubmitFlagSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(write_only=True)
    flag_id = serializers.CharField(write_only=True)
    submitted_answer = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context["request"].user
        data["user"] = user

        active = active_scenario_collection.find_one(
            {"id": data["active_scenario_id"]},
            {"_id": 0}
        )
        if not active:
            raise serializers.ValidationError("Invalid Active Scenario")

        if user["user_id"] not in active.get("participant_data", {}):
            raise serializers.ValidationError("User not part of scenario")

        pd_id = active["participant_data"][user["user_id"]]
        participant = participant_data_collection.find_one(
            {"id": pd_id, "flag_data.flag_id": data["flag_id"]},
            {"_id": 0}
        )
        if not participant:
            raise serializers.ValidationError("Invalid Flag")

        data["_active"] = active
        data["_participant"] = participant
        data["_participant_data_id"] = pd_id
        return data

    def create(self, validated_data):
        active = validated_data["_active"]
        participant = validated_data["_participant"]
        pd_id = validated_data["_participant_data_id"]

        scenario = corporate_scenario_collection.find_one(
            {"id": active["scenario_id"]},
            {"_id": 0}
        ) or {}

        scoring_config = scenario.get("scoring_config", {"type": "standard"})

        flag = flag_data_collection.find_one(
            {"id": validated_data["flag_id"]},
            {"_id": 0}
        ) or {}

        base_score = int(flag.get("score", 0))
        hint_penalty = int(flag.get("hint_penalty", 0))

        now = datetime.datetime.now()

        # ---------------- FIND FLAG STATE ----------------
        attempts = 0
        already_correct = False
        hint_used = False

        for f in participant.get("flag_data", []):
            if f.get("flag_id") == validated_data["flag_id"]:
                attempts = int(f.get("retires", 0))
                already_correct = bool(f.get("is_correct", False))
                hint_used = bool(f.get("hint_used", False))
                break

        # ❌ No re-scoring
        if already_correct:
            return {
                "message": "Flag already solved",
                "is_correct": True,
                "awarded_score": 0,
                "total_obtained_score": participant.get("total_obtained_score", 0),
            }

        attempts_next = attempts + 1

        # ---------------- VERIFY ANSWER ----------------
        is_correct = (
            str(validated_data["submitted_answer"]).strip()
            == str(flag.get("answer")).strip()
        )

        filter_q = {
            "id": pd_id,
            "flag_data.flag_id": validated_data["flag_id"],
        }

        # ---------------- WRONG ANSWER ----------------
        if not is_correct:
            participant_data_collection.update_one(
                filter_q,
                {
                    "$set": {
                        "flag_data.$.is_correct": False,
                        "flag_data.$.submitted_response": validated_data["submitted_answer"],
                        "flag_data.$.submitted_at": now,
                        "flag_data.$.updated_at": now,
                        "flag_data.$.retires": attempts_next,
                        "flag_data.$.obtained_score": 0,
                    }
                }
            )

            return {
                "message": "Wrong Answer",
                "is_correct": False,
                "awarded_score": 0,
                "total_obtained_score": participant.get("total_obtained_score", 0),
            }

        raw_start = active.get("start_time")

        # ---------------- FIX START TIME ----------------
        start_time = active.get("start_time")
        if isinstance(raw_start, str):
            parsed_start = datetime.datetime.fromisoformat(raw_start.replace("Z", ""))
        else:
            parsed_start = raw_start

        print("PARSED start_time:", parsed_start, type(parsed_start))

        if isinstance(parsed_start, datetime.datetime):
            print("ELAPSED MINUTES:",
                (now - parsed_start).total_seconds() / 60)

        print("SCORING CONFIG:", scoring_config)
        print("=============================")

        # ---------------- SCORING ----------------
        if scoring_config.get("type") == "decay":
            awarded, meta = compute_decay_score(
                base_score=base_score,
                scoring_config=scoring_config,
                start_time=start_time,
                event_time=now,
                attempts=attempts_next,
                hint_used=hint_used,
                hint_penalty=hint_penalty,
            )
        else:
            awarded, meta = compute_standard_score(
                base_score=base_score,
                hint_used=hint_used,
                hint_penalty=hint_penalty,
            )

        meta = _sanitize_meta(meta)

        # ---------------- UPDATE FLAG ----------------
        participant_data_collection.update_one(
            filter_q,
            {
                "$set": {
                    "flag_data.$.is_correct": True,
                    "flag_data.$.obtained_score": int(awarded),
                    "flag_data.$.submitted_response": validated_data["submitted_answer"],
                    "flag_data.$.submitted_at": now,
                    "flag_data.$.updated_at": now,
                    "flag_data.$.achieved_at": now,
                    "flag_data.$.retires": attempts_next,
                    "flag_data.$.score_meta": meta,
                }
            }
        )

        # ---------------- TOTAL SCORE ----------------
        updated_pd = participant_data_collection.find_one(
            {"id": pd_id},
            {"_id": 0}
        )

        total = sum(int(x.get("obtained_score", 0)) for x in updated_pd["flag_data"])

        participant_data_collection.update_one(
            {"id": pd_id},
            {"$set": {"total_obtained_score": total}}
        )

        return {
            "message": "Correct Answer",
            "is_correct": True,
            "awarded_score": int(awarded),
            "scoring_type": scoring_config.get("type", "standard"),
            "total_obtained_score": total,
        }

ALLOWED_EVIDENCE_EXT = ("pdf", "jpg", "jpeg", "png")

def _safe_ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lower().replace(".", "")

def _now():
    return datetime.datetime.now()

class CorporateScenarioAchieveMilestoneSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100, required=True, write_only=True)
    milestone_id = serializers.CharField(max_length=100, required=True, write_only=True)

    # NEW
    submitted_text = serializers.CharField(required=False, allow_blank=True, write_only=True)
    evidence_files = serializers.ListField(
        child=serializers.FileField(validators=[validate_file_size]),
        required=False,
        allow_empty=True,
        write_only=True
    )

    # old field kept for backward compatibility
    screenshot_url = serializers.FileField(required=False, write_only=True, validators=[validate_file_size])


    def validate(self, data):
        user = self.context["request"].user
        data["user"] = user

        active = active_scenario_collection.find_one({"id": data["active_scenario_id"]}, {"_id": 0})
        if not active:
            raise serializers.ValidationError("Invalid Active Scenario ID")

        if not active.get("participant_data", {}).get(user["user_id"]):
            raise serializers.ValidationError("Invalid Active Scenario ID")

        pd_id = active["participant_data"][user["user_id"]]
        data["participant_data_id"] = pd_id

        participant_data = participant_data_collection.find_one(
            {"id": pd_id, "milestone_data": {"$elemMatch": {"milestone_id": data["milestone_id"]}}},
            {"_id": 0}
        )
        if not participant_data:
            raise serializers.ValidationError("Invalid Milestone ID")

        # disallow submit if locked
        for m in participant_data.get("milestone_data", []):
            if m.get("milestone_id") == data["milestone_id"]:
                if (m.get("status") is False) or m.get("locked_by_admin", False):
                    raise serializers.ValidationError("This milestone is locked by Admin")
                break

        # validate evidence (new + old)
        files = []
        if data.get("evidence_files"):
            files.extend(data["evidence_files"])
        if data.get("screenshot_url"):
            files.append(data["screenshot_url"])

        for f in files:
            ext = _safe_ext(f.name)
            if ext not in ALLOWED_EVIDENCE_EXT:
                raise serializers.ValidationError("Evidence must be PDF/JPG/JPEG/PNG only.")

        # require at least one thing (text or file)
        if (not (data.get("submitted_text") or "").strip()) and len(files) == 0:
            raise serializers.ValidationError("Submit either text or at least one evidence file.")

        data["_active"] = active
        return data

    def create(self, validated_data):
        """
        Stores:
        - submitted_text
        - evidence_files[] (pdf/images) and legacy screenshot_url (also goes into evidence_files)
        - sets is_achieved=True (approval pending)
        """
        now = _now()
        active = validated_data["_active"]

        # find current retries + existing evidence list
        pd = participant_data_collection.find_one(
            {"id": validated_data["participant_data_id"]},
            {"_id": 0, "milestone_data": 1}
        ) or {}

        no_of_retries = 0
        existing_text = ""
        existing_files = []
        already_achieved = False

        for m in pd.get("milestone_data", []):
            if m.get("milestone_id") == validated_data["milestone_id"]:
                no_of_retries = int(m.get("retires", 0))
                existing_text = m.get("submitted_text", "") or ""
                existing_files = m.get("evidence_files", []) or []
                already_achieved = bool(m.get("is_achieved", False))
                break

        # collect uploads: evidence_files + screenshot_url (legacy)
        upload_list = []
        if validated_data.get("evidence_files"):
            upload_list.extend(validated_data["evidence_files"])
        if validated_data.get("screenshot_url"):
            upload_list.append(validated_data["screenshot_url"])

        new_file_records = []
        if upload_list:
            current_timestamp = str(int(now.timestamp()))
            base_dir = "static/documents/milestone_evidence"  # choose your own dir
            os.makedirs(base_dir, exist_ok=True)

            for f in upload_list:
                ext = _safe_ext(f.name)
                kind = "pdf" if ext == "pdf" else "image"
                rnd = generate_random_string(id_type="Evidence", length=20)
                new_name = f"{validated_data['milestone_id']}_evidence_{current_timestamp}_{rnd}.{ext}"

                with open(os.path.join(base_dir, new_name), "wb+") as dst:
                    for chunk in f.chunks():
                        dst.write(chunk)

                url = f"{API_URL}/static/documents/milestone_evidence/{new_name}"
                new_file_records.append({
                    "url": url,
                    "name": f.name,
                    "type": kind,
                    "uploaded_at": now
                })

        # merge (append) evidence files
        merged_files = existing_files + new_file_records

        # merge submitted_text (if provided overwrite; else keep old)
        submitted_text = (validated_data.get("submitted_text") or "").strip()
        final_text = submitted_text if submitted_text else existing_text

        # update participant milestone element
        filter_query = {
            "id": validated_data["participant_data_id"],
            "milestone_data.milestone_id": validated_data["milestone_id"]
        }

        update_operation = {
            "$set": {
                "milestone_data.$.is_achieved": True,
                "milestone_data.$.submitted_text": final_text,
                "milestone_data.$.evidence_files": merged_files,
                "milestone_data.$.submitted_at": now,
                "milestone_data.$.updated_at": now,
                "milestone_data.$.retires": no_of_retries + 1,
            }
        }

        # set achieved_at only once (first submit)
        if not already_achieved:
            update_operation["$set"]["milestone_data.$.achieved_at"] = now

        participant_data_collection.update_one(filter_query, update_operation)

        # response: keep your old message + include evidence count
        return {
            "message": "Milestone Submitted. Approval Pending.",
            "milestone_id": validated_data["milestone_id"],
            "submitted_text": final_text,
            "evidence_count": len(merged_files),
        }


class CorporateScenarioApproveMilestoneSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(write_only=True)
    milestone_id = serializers.CharField(write_only=True)
    participant_id = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context["request"].user
        data["user"] = user

        active_scenario = active_scenario_collection.find_one(
            {"id": data["active_scenario_id"]},
            {"_id": 0},
        )
        if not active_scenario:
            raise serializers.ValidationError("Invalid Active Scenario ID")

        if active_scenario["started_by"] != user["user_id"]:
            raise serializers.ValidationError("Permission denied")

        participant_data_id = active_scenario["participant_data"].get(data["participant_id"])
        if not participant_data_id:
            raise serializers.ValidationError("Invalid Participant ID")

        participant_data = participant_data_collection.find_one(
            {
                "id": participant_data_id,
                "milestone_data": {"$elemMatch": {"milestone_id": data["milestone_id"]}},
            }
        )
        if not participant_data:
            raise serializers.ValidationError("Invalid Milestone ID")

        milestone_entry = next(
            (m for m in participant_data["milestone_data"]
             if m["milestone_id"] == data["milestone_id"]),
            None
        )

        if not milestone_entry or not milestone_entry.get("is_achieved"):
            raise serializers.ValidationError("Milestone not yet achieved")

        data["participant_data_id"] = participant_data_id
        data["milestone_entry"] = milestone_entry
        data["active_scenario"] = active_scenario

        return data

    def create(self, validated_data):
        now = datetime.datetime.now()

        milestone_db = milestone_data_collection.find_one(
            {"id": validated_data["milestone_id"]},
            {"_id": 0},
        )
        if not milestone_db:
            raise serializers.ValidationError("Milestone not found")

        base_score = int(milestone_db.get("score", 0))
        hint_used = bool(validated_data["milestone_entry"].get("hint_used", False))
        hint_penalty = int(milestone_db.get("hint_penalty", 0))

        scenario = corporate_scenario_collection.find_one(
            {"id": validated_data["active_scenario"]["scenario_id"]},
            {"_id": 0},
        ) or {}

        scoring_config = scenario.get("scoring_config", {"type": "standard"})

        if scoring_config.get("type") == "decay":
            event_time = validated_data["milestone_entry"].get("achieved_at") or now
            final_score, meta = compute_decay_score(
                base_score,
                scoring_config=scoring_config,
                start_time=validated_data["active_scenario"].get("start_time"),
                event_time=event_time,
                hint_used=hint_used,
                hint_penalty=hint_penalty,
            )
        else:
            final_score, meta = compute_standard_score(
                base_score,
                hint_used=hint_used,
                hint_penalty=hint_penalty,
            )

        result = participant_data_collection.update_one(
            {
                "id": validated_data["participant_data_id"],
                "milestone_data.milestone_id": validated_data["milestone_id"],
            },
            {
                "$set": {
                    "milestone_data.$.is_approved": True,
                    "milestone_data.$.obtained_score": final_score,
                    "milestone_data.$.score_meta": meta,
                    "milestone_data.$.approved_at": now,
                }
            }
        )

        if result.matched_count == 0:
            raise serializers.ValidationError("Milestone approval failed")

        total = sum(
            int(m.get("obtained_score", 0))
            for m in participant_data_collection.find_one(
                {"id": validated_data["participant_data_id"]},
                {"_id": 0},
            )["milestone_data"]
        )

        participant_data_collection.update_one(
            {"id": validated_data["participant_data_id"]},
            {"$set": {"total_obtained_score": total}},
        )

        return {
            "message": "Milestone Approved",
            "final_score": final_score,
            "scoring_type": scoring_config.get("type", "standard"),
        }

class CorporateScenarioRejectMilestoneSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(write_only=True)
    milestone_id = serializers.CharField(write_only=True)
    participant_id = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context["request"].user

        active_scenario = active_scenario_collection.find_one(
            {"id": data["active_scenario_id"]},
            {"_id": 0},
        )
        if not active_scenario:
            raise serializers.ValidationError("Invalid Active Scenario ID")

        if active_scenario["started_by"] != user["user_id"]:
            raise serializers.ValidationError("Permission denied")

        participant_data_id = active_scenario["participant_data"].get(data["participant_id"])
        if not participant_data_id:
            raise serializers.ValidationError("Invalid Participant ID")

        data["participant_data_id"] = participant_data_id
        return data

    def create(self, validated_data):
        participant_data_collection.update_one(
            {
                "id": validated_data["participant_data_id"],
                "milestone_data.milestone_id": validated_data["milestone_id"],
            },
            {
                "$set": {
                    "milestone_data.$.is_achieved": False,
                    "milestone_data.$.is_approved": False,
                    "milestone_data.$.obtained_score": 0,
                    "milestone_data.$.approved_at": None,
                    "milestone_data.$.achieved_at": None,
                }
            }
        )

        total = sum(
            int(m.get("obtained_score", 0))
            for m in participant_data_collection.find_one(
                {"id": validated_data["participant_data_id"]},
                {"_id": 0},
            )["milestone_data"]
        )

        participant_data_collection.update_one(
            {"id": validated_data["participant_data_id"]},
            {"$set": {"total_obtained_score": total}},
        )

        return {"message": "Milestone Rejected"}



class CorporateScenarioShowHintSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100, required=True, write_only=True)
    milestone_id = serializers.CharField(max_length=100, required=False, write_only=True)
    flag_id = serializers.CharField(max_length=100, required=False, write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(instance)
        return data

    def validate(self, data):
        user = self.context['request'].user
        data['user'] = user

        active = active_scenario_collection.find_one(
            {"id": data["active_scenario_id"]},
            {"_id": 0}
        )
        if not active:
            raise serializers.ValidationError("Invalid Active Scenario ID")

        participant_id = active["participant_data"].get(user["user_id"])
        if not participant_id:
            raise serializers.ValidationError("Invalid Active Scenario ID")

        data["participant_data_id"] = participant_id

        # ---------- MILESTONE ----------
        if data.get("milestone_id"):
            participant = participant_data_collection.find_one(
                {"id": participant_id, "milestone_data.milestone_id": data["milestone_id"]}
            )
            if not participant:
                raise serializers.ValidationError("Invalid Milestone ID")

            for m in participant.get("milestone_data", []):
                if m["milestone_id"] == data["milestone_id"]:
                    if m.get("is_achieved"):
                        raise serializers.ValidationError("Milestone already achieved")
                    break

            data["scenario_type"] = "MILESTONE"

        # ---------- FLAG ----------
        elif data.get("flag_id"):
            participant = participant_data_collection.find_one(
                {"id": participant_id, "flag_data.flag_id": data["flag_id"]}
            )
            if not participant:
                raise serializers.ValidationError("Invalid Flag ID")

            data["scenario_type"] = "FLAG"

        else:
            raise serializers.ValidationError("Flag or Milestone ID is required")

        return data

    def create(self, validated_data):
        now = datetime.datetime.now()

        response = {
            "active_scenario_id": validated_data["active_scenario_id"],
            "participant_id": validated_data["user"]["user_id"],
        }

        # ================== MILESTONE ==================
        if validated_data["scenario_type"] == "MILESTONE":
            milestone = milestone_data_collection.find_one(
                {"id": validated_data["milestone_id"]},
                {"_id": 0}
            )

            hint = milestone.get("hint", "")
            hint_penalty = int(milestone.get("hint_penalty", 0))

            participant_data_collection.update_one(
                {
                    "id": validated_data["participant_data_id"],
                    "milestone_data.milestone_id": validated_data["milestone_id"],
                },
                {
                    "$set": {
                        "milestone_data.$.hint_used": True,
                        "milestone_data.$.hint_string": hint,
                        "milestone_data.$.hint_penalty": hint_penalty,
                        "milestone_data.$.hint_used_at": now,
                    }
                },
            )

            response.update({
                "milestone_id": validated_data["milestone_id"],
                "hint": hint,
                "hint_penalty": hint_penalty,
            })

        # ================== FLAG ==================
        else:
            flag = flag_data_collection.find_one(
                {"id": validated_data["flag_id"]},
                {"_id": 0}
            )

            hint = flag.get("hint", "")
            hint_penalty = int(flag.get("hint_penalty", 0))

            participant_data_collection.update_one(
                {
                    "id": validated_data["participant_data_id"],
                    "flag_data.flag_id": validated_data["flag_id"],
                },
                {
                    "$set": {
                        "flag_data.$.hint_used": True,
                        "flag_data.$.hint_string": hint,
                        "flag_data.$.hint_penalty": hint_penalty,
                        "flag_data.$.hint_used_at": now,
                    }
                },
            )

            response.update({
                "flag_id": validated_data["flag_id"],
                "hint": hint,
                "hint_penalty": hint_penalty,
            })

        return response



class CorporateActiveScenarioSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def get(self, user):
        response = []
        active_scenarios = active_scenario_collection.find({}, {"_id": 0})
        for active_scenario in active_scenarios:
            if not active_scenario["participant_data"].get(user["user_id"]):
                continue

            scenario = corporate_scenario_collection.find_one({"id": active_scenario['scenario_id']}, {"_id": 0})
            started_by = user_collection.find_one({"user_id": active_scenario['started_by']}, {"user_full_name": 1, "_id": 0})["user_full_name"]

            game_type = "flag" if scenario.get('flag_data') else "milestone"
            temp_data = {
                'participant_id': user["user_id"],
                'active_scenario_id': active_scenario['id'],
                'started_by': started_by,
                'start_time': active_scenario['start_time'],
                'scenario_id': active_scenario['scenario_id'],
                'name': scenario['name'],
                'type': game_type,
                'category_id': scenario['category_id'],
                'severity': scenario['severity'],
                'description': scenario['description'],
                'objective': scenario['objective'],
                'prerequisite': scenario['prerequisite'],
                'thumbnail_url': scenario["thumbnail_url"],
            }

            participant_data = participant_data_collection.find_one({'id': active_scenario['participant_data'][user["user_id"]]})
            temp_data['team'] = participant_data['team']
            temp_data['total_score'] = participant_data['total_score']
            temp_data['total_obtained_score'] = participant_data['total_obtained_score']

            response.append(temp_data)

        return response


class CorporateScenarioModeratorSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(instance)
        return data

    def get(self, user):
        # Default response if no active scenario
        scenario = {"type": "None"}

        active_scenario = active_scenario_collection.find_one(
            {"started_by": user["user_id"]},
            {"_id": 0}
        )
        if not active_scenario:
            return scenario

        scenario = corporate_scenario_collection.find_one(
            {"id": active_scenario["scenario_id"]},
            {"_id": 0}
        )
        if not scenario:
            return {"errors": "Scenario not found"}

        # ---------- COMMON METADATA ----------
        scenario["active_scenario_id"] = active_scenario["id"]
        scenario["started_by"] = active_scenario["started_by"]
        scenario["start_time"] = active_scenario.get("start_time")

        # ---------- DATA STRUCTURES ----------
        participants_data = {
            "red_team": [],
            "blue_team": [],
            "purple_team": [],
            "yellow_team": [],
        }

        team_groups = {}   # 🔥 NEW: Team A / Team B / etc

        # ---------- PARTICIPANTS LOOP ----------
        for key in active_scenario["participant_data"]:
            participant_data = participant_data_collection.find_one(
                {"id": active_scenario["participant_data"][key]},
                {"_id": 0}
            )
            if not participant_data:
                continue

            # 🔑 NEW FIELD (defaults safe)
            team_group = participant_data.get("team_group", "Default")

            if team_group not in team_groups:
                team_groups[team_group] = {
                    "red_team": [],
                    "blue_team": [],
                    "purple_team": [],
                    "yellow_team": [],
                }

            user_info = user_collection.find_one(
                {"user_id": participant_data["user_id"]},
                {"_id": 0}
            )

            temp = {
                "participant_data_id": participant_data["id"],
                "participant_id": participant_data["user_id"],
                "participant_name": user_info["user_full_name"],
                "participant_avatar": user_info["user_avatar"],
                "team": participant_data["team"],
                "team_group": team_group,            # 🔥 NEW
                "total_score": participant_data["total_score"],
                "total_obtained_score": participant_data["total_obtained_score"],
            }

            # ---------- MILESTONE ENRICHMENT ----------
            if scenario.get("milestone_data"):
                milestones_list = []
                milestone_approved_count = 0
                total_hint_count = 0
                hint_used_count = 0

                for md in participant_data.get("milestone_data", []):
                    milestone = milestone_data_collection.find_one(
                        {"id": md["milestone_id"]},
                        {"_id": 0}
                    )

                    milestone_temp = {
                        "id": md["milestone_id"],
                        "phase_id": milestone.get("phase_id"),
                        "name": milestone.get("name"),
                        "description": milestone.get("description", ""),
                        "hint": milestone.get("hint"),
                        "score": milestone.get("score", 0),
                        # participant-specific fields
                        "is_achieved": md.get("is_achieved", False),
                        "is_approved": md.get("is_approved", False),
                        "obtained_score": md.get("obtained_score", 0),
                        "hint_used": md.get("hint_used", False),
                        "submitted_at": md.get("submitted_at"),
                        "achieved_at": md.get("achieved_at"),
                        "approved_at": md.get("approved_at"),
                        "hint_used_at": md.get("hint_used_at"),
                    }

                    if md["is_approved"]:
                        milestone_approved_count += 1
                    if milestone.get("hint"):
                        total_hint_count += 1
                    if md["hint_used"]:
                        hint_used_count += 1

                    milestones_list.append(milestone_temp)

                temp.update({
                    "milestone_data": milestones_list,
                    "total_milestone": len(milestones_list),
                    "milestone_approved": milestone_approved_count,
                    "total_hint": total_hint_count,
                    "hint_used_count": hint_used_count,
                })

            # ---------- ROLE + TEAM GROUP DISTRIBUTION ----------
            role = participant_data["team"]

            if role == "RED":
                participants_data["red_team"].append(temp)
                team_groups[team_group]["red_team"].append(temp)

            elif role == "BLUE":
                participants_data["blue_team"].append(temp)
                team_groups[team_group]["blue_team"].append(temp)

            elif role == "PURPLE":
                participants_data["purple_team"].append(temp)
                team_groups[team_group]["purple_team"].append(temp)

            elif role == "YELLOW":
                participants_data["yellow_team"].append(temp)
                team_groups[team_group]["yellow_team"].append(temp)

        # ---------- SCENARIO TYPE ----------
        if scenario.get("flag_data"):
            scenario["type"] = "flag_data"
        else:
            scenario["type"] = "milestone"
            category = scenario_category_collection.find_one(
                {"scenario_category_id": scenario["category_id"]},
                {"_id": 0}
            )
            scenario["category_name"] = category["scenario_category_name"]

        # ---------- ATTACH NEW STRUCTURES ----------
        scenario["participants_data"] = participants_data     
        scenario["team_groups"] = team_groups                 

        # ---------- CLEANUP ----------
        for key in [
            "creator_id",
            "category_id",
            "infra_id",
            "is_approved",
            "is_prepared",
            "created_at",
            "updated_at",
            "milestone_data",
        ]:
            scenario.pop(key, None)
        
        try:
            instance_id = None

            # pick any participant (first is fine for moderator)
            for pd_id in active_scenario["participant_data"].values():
                pd = participant_data_collection.find_one({"id": pd_id}, {"_id": 0})
                if pd and pd.get("instance_id"):
                    instance_id = pd["instance_id"]
                    break

            if instance_id:
                instance = get_cloud_instance(instance_id)
                console = get_instance_console(instance)
                scenario["console_url"] = console.url
            else:
                scenario["console_url"] = None

        except Exception:
            scenario["console_url"] = None

        return scenario



class CorporateScenarioModeratorConsoleSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return instance

    def get(self, user):
        active = active_scenario_collection.find_one(
            {"started_by": user["user_id"]},
            {"_id": 0}
        )
        if not active:
            return {"errors": "No active scenario"}

        scenario = corporate_scenario_collection.find_one(
            {"id": active["scenario_id"]},
            {"_id": 0}
        )
        if not scenario:
            return {"errors": "Scenario not found"}

        payload = {
            "scenario_type": "MILESTONE" if scenario.get("milestone_data") else "FLAG",
            "active_scenario_id": active["id"],
            "start_time": active.get("start_time"),
            "participants_data": [],
            "milestone_data": [],
            "kill_chain_progress": scenario.get("kill_chain_progress", []),
        }

        # ---------- PARTICIPANTS ----------
        for uid, pd_id in active["participant_data"].items():
            pd = participant_data_collection.find_one({"id": pd_id}, {"_id": 0})
            user_obj = user_collection.find_one({"user_id": uid}, {"_id": 0})
            if not pd or not user_obj:
                continue

            payload["participants_data"].append({
                "participant_id": uid,
                "participant_name": user_obj.get("user_full_name"),
                "team": pd.get("team"),
                "team_group": pd.get("team_group", "Default"),
                "total_score": pd.get("total_score", 0),
                "total_obtained_score": pd.get("total_obtained_score", 0),
            })

            # ---------- MILESTONES (JOIN CORRECTLY) ----------
            for md in pd.get("milestone_data", []):
                milestone = milestone_data_collection.find_one(
                    {"id": md["milestone_id"]},
                    {"_id": 0}
                )
                if not milestone:
                    continue

                payload["milestone_data"].append({
                    "milestone_id": md["milestone_id"],
                    "phase_id": milestone.get("phase_id"),
                    "milestone_name": milestone.get("name"),
                    "milestone_description": milestone.get("description", ""),
                    "milestone_score": milestone.get("score", 0),
                    "obtained_score": md.get("obtained_score", 0),
                    "is_achieved": md.get("is_achieved", False),
                    "is_approved": md.get("is_approved", False),
                    "hint_used": md.get("hint_used", False),
                    "hint_string": milestone.get("hint"),
                    "submitted_at": md.get("submitted_at"),
                    "approved_at": md.get("approved_at"),
                })

        return payload


class CorporateActiveScenarioDeleteSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def get(self, active_scenario_id, user):

        active_scenario = active_scenario_collection.find_one({"id": active_scenario_id}, {"_id": 0})
        if not active_scenario:
            return {"errors": "Invalid Active Scenario ID"}

        if user["user_id"] != active_scenario["started_by"]:
            return {"errors": "You are not authorised to deleted this game."}

        # scenario_game = corporate_scenario_collection.find_one({"id":active_scenario["scenario_id"]},{"_id":0})
        # if scenario_game.get("milestone_data"):
        #     if user["user_id"] != active_scenario["started_by"]:
        #         return {"errors":"You are not authorised to deleted this game."}
        # else:
        #     if not active_scenario["participant_data"].get(user["user_id"]):
        #         return {"errors":"You are not authorised to deleted this game."}
        # if active_scenario["participant_data"].get(user["user_id"]):
        #     return {"errors":"You are not authorised to deleted this game."}

        active_scenario["end_time"] = datetime.datetime.now()
        archive_scenario_collection.insert_one(active_scenario)
        active_scenario.pop("_id")
        active_scenario_collection.delete_one({"id": active_scenario["id"]})

        end_corporate_game.delay(active_scenario)

        # subnet_dict = {}

        # for network in active_scenario["networks"]:
        #     subnet_dict[network["network_name"]] = network["subnet_id"]

        # for instance in active_scenario["instances"]:
        #     cloud_instance = get_cloud_instance(instance["id"])
        #     if cloud_instance:
        #         deleted_cloud_instance = delete_cloud_instance(cloud_instance)

        # for router in active_scenario["routers"]:
        #     cloud_router = get_cloud_router(router['id'])
        #     if cloud_router:
        #         for network_name in router["network_name"]:
        #             disconnect_router_from_private_network(router['id'], subnet_dict[network_name])
        #         delete_cloud_router(router['id'])

        # for network in active_scenario["networks"]:
        #     delete_cloud_network(network['network_id'], network['subnet_id'])

        for key in active_scenario["participant_data"]:
            participant_data = participant_data_collection.find_one({"id": active_scenario["participant_data"][key]})
            archive_participant_collection.insert_one(participant_data)
            participant_data_collection.delete_one({"id": active_scenario["participant_data"][key]})

        return {'message': 'Scenario Deleted Successfully'}


class CorporateScenarioModeratorConsoleDetailSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(write_only=True)
    participant_id = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context["request"].user

        active_scenario = active_scenario_collection.find_one(
            {
                "id": data["active_scenario_id"],
                "started_by": user["user_id"],
            },
            {"_id": 0},
        )
        if not active_scenario:
            raise serializers.ValidationError("Invalid Active Scenario ID")

        participant_data_id = active_scenario["participant_data"].get(data["participant_id"])
        if not participant_data_id:
            raise serializers.ValidationError("Invalid Participant ID")

        participant = participant_data_collection.find_one(
            {"id": participant_data_id},
            {"_id": 0},
        )
        if not participant:
            raise serializers.ValidationError("Participant not found")

        scenario = corporate_scenario_collection.find_one(
            {"id": active_scenario["scenario_id"]},
            {"_id": 0},
        ) or {}

        data["active_scenario"] = active_scenario
        data["participant"] = participant
        data["scenario"] = scenario

        return data

    def create(self, validated_data):
        participant = validated_data["participant"]
        scenario = validated_data["scenario"]

        # ---------- BUILD ITEMS ----------
        phase_lookup = {
            p["id"]: p.get("phase_name") or p.get("name") or "Phase"
            for p in scenario.get("phases", [])
        }

        items_by_phase = {}

        for md in participant.get("milestone_data", []):
            milestone_db = milestone_data_collection.find_one(
                {"id": md["milestone_id"]},
                {"_id": 0},
            )
            if not milestone_db:
                continue

            phase_id = milestone_db.get("phase_id")
            phase_name = phase_lookup.get(phase_id, "Phase")

            items_by_phase.setdefault(phase_id, {
                "phase_id": phase_id,
                "phase_name": phase_name,
                "items": [],
            })["items"].append({
                "milestone_id": md["milestone_id"],
                "milestone_name": milestone_db.get("name"),
                "milestone_description": milestone_db.get("description", ""),
                "milestone_score": milestone_db.get("score", 0),
                "obtained_score": md.get("obtained_score", 0),
                "is_achieved": md.get("is_achieved", False),
                "is_approved": md.get("is_approved", False),
                "submitted_text": md.get("submitted_text"),
                "evidence_files": md.get("evidence_files", []),
                "hint_used": md.get("hint_used", False),
                "hint_string": milestone_db.get("hint"),
                "hint_penalty": milestone_db.get("hint_penalty", 0),
                "submitted_at": md.get("submitted_at"),
                "achieved_at": md.get("achieved_at"),
                "approved_at": md.get("approved_at"),
                "locked": md.get("locked", False),
                "locked_by_admin": md.get("locked_by_admin", False),
            })

        # ---------- FETCH CONSOLE URL (🔥 FIX) ----------
        console_url = None
        instance_id = participant.get("instance_id")

        if instance_id:
            try:
                instance = get_cloud_instance(instance_id)
                console = get_instance_console(instance)
                console_url = getattr(console, "url", None)
            except Exception:
                console_url = None

        # ---------- FINAL RESPONSE ----------
        return {
            "scenario_type": "MILESTONE",
            "active_scenario_id": validated_data["active_scenario"]["id"],
            "participant_id": participant["user_id"],
            "team": participant["team"],
            "console_url": console_url,   # ✅ FIXED
            "itemsByPhase": items_by_phase,
            "total_milestone_count": sum(len(v["items"]) for v in items_by_phase.values()),
            "approved_milestone_count": sum(
                1 for v in items_by_phase.values() for m in v["items"] if m["is_approved"]
            ),
        }

class CorporateByCategoryIdSerializer(serializers.Serializer):
    def get(self, category_id, user_id):
        if not scenario_category_collection.find_one({"scenario_category_id": category_id}):
            return {"errors": {"non_field_errors": ["Invalid Scenario Category Id"]}}

        assigned_games = user_profile_collection.find_one({"user_id": user_id}, {"_id": 0, "assigned_games": 1})

        if not assigned_games["assigned_games"]["display_all_corporate"]:
            query = {"$in": assigned_games["assigned_games"]["corporate"]}
            if not assigned_games["assigned_games"]["display_locked_corporate"]:

                scenario_category_detail_list = list(
                    corporate_scenario_collection.find({
                        "category_id": category_id,
                        'is_prepared': True,
                        'is_approved': True,
                        'id': query
                    },
                        {'_id': 0,
                         'is_approved': 0,
                         'is_prepared': 0,
                         'created_at': 0,
                         'updated_at': 0,
                         }))
            else:
                scenario_category_detail_list = list(
                    corporate_scenario_collection.find({
                        "category_id": category_id,
                        'is_prepared': True,
                        'is_approved': True
                    },
                        {'_id': 0,
                         'is_approved': 0,
                         'is_prepared': 0,
                         'created_at': 0,
                         'updated_at': 0,
                         }))

                for scenario in scenario_category_detail_list:
                    scenario['display'] = scenario['id'] in query["$in"]

                for scenario in scenario_category_detail_list:
                    user = user_collection.find_one({"user_id": scenario["creator_id"]})
                    scenario["creator_name"] = user["user_full_name"]

                    scenario["type"] = "Milestone" if scenario.get("milestone_data") else "Flag"

                    if scenario.get("milestone_data"):
                        inner_score = 0
                        if scenario["milestone_data"].get("red_team"):
                            for i in scenario["milestone_data"].get("red_team"):
                                score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                                inner_score += score["score"]
                        if scenario["milestone_data"].get("blue_team"):
                            for i in scenario["milestone_data"].get("blue_team"):
                                score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                                inner_score += score["score"]
                        if scenario["milestone_data"].get("purple_team"):
                            for i in scenario["milestone_data"].get("purple_team"):
                                score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                                inner_score += score["score"]
                        if scenario["milestone_data"].get("yellow_team"):
                            for i in scenario["milestone_data"].get("yellow_team"):
                                score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                                inner_score += score["score"]

                    else:
                        inner_score = 0
                        if scenario["flag_data"].get("red_team"):
                            for i in scenario["flag_data"].get("red_team"):
                                score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                                inner_score += score["score"]
                        if scenario["flag_data"].get("blue_team"):
                            for i in scenario["flag_data"].get("blue_team"):
                                score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                                inner_score += score["score"]
                        if scenario["flag_data"].get("purple_team"):
                            for i in scenario["flag_data"].get("purple_team"):
                                score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                                inner_score += score["score"]
                        if scenario["flag_data"].get("yellow_team"):
                            for i in scenario["flag_data"].get("yellow_team"):
                                score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                                inner_score += score["score"]

                    scenario["points"] = inner_score


        else:
            scenario_category_detail_list = list(
                corporate_scenario_collection.find({
                    "category_id": category_id,
                    'is_prepared': True,
                    'is_approved': True,
                },
                    {'_id': 0,
                     'is_approved': 0,
                     'is_prepared': 0,
                     'created_at': 0,
                     'updated_at': 0,
                     }))
            for scenario in scenario_category_detail_list:
                user = user_collection.find_one({"user_id": scenario["creator_id"]})
                scenario["creator_name"] = user["user_full_name"]

                scenario["type"] = "Milestone" if scenario.get("milestone_data") else "Flag"

                if scenario.get("milestone_data"):
                    inner_score = 0
                    if scenario["milestone_data"].get("red_team"):
                        for i in scenario["milestone_data"].get("red_team"):
                            score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                            inner_score += score["score"]
                    if scenario["milestone_data"].get("blue_team"):
                        for i in scenario["milestone_data"].get("blue_team"):
                            score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                            inner_score += score["score"]
                    if scenario["milestone_data"].get("purple_team"):
                        for i in scenario["milestone_data"].get("purple_team"):
                            score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                            inner_score += score["score"]
                    if scenario["milestone_data"].get("yellow_team"):
                        for i in scenario["milestone_data"].get("yellow_team"):
                            score = milestone_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                            inner_score += score["score"]

                else:
                    inner_score = 0
                    if scenario["flag_data"].get("red_team"):
                        for i in scenario["flag_data"].get("red_team"):
                            score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                            inner_score += score["score"]
                    if scenario["flag_data"].get("blue_team"):
                        for i in scenario["flag_data"].get("blue_team"):
                            score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                            inner_score += score["score"]
                    if scenario["flag_data"].get("purple_team"):
                        for i in scenario["flag_data"].get("purple_team"):
                            score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                            inner_score += score["score"]
                    if scenario["flag_data"].get("yellow_team"):
                        for i in scenario["flag_data"].get("yellow_team"):
                            score = flag_data_collection.find_one({"id": i}, {"_id": 0, "score": 1})
                            inner_score += score["score"]

                scenario["points"] = inner_score

        return scenario_category_detail_list

##report data

class CorporateExecutiveScenarioReportSerializer(serializers.Serializer):

    def get(self, archive_scenario_id, team_group):

        scenario = archive_scenario_collection.find_one(
            {"id": archive_scenario_id, "end_time": {"$ne": None}},
            {"_id": 0}
        )

        if not scenario:
            return {"errors": "Scenario has not ended or archive record not found"}

        scenario_meta = corporate_scenario_collection.find_one(
            {"id": scenario.get("scenario_id")},
            {"_id": 0}
        ) or {}

        # ✅ BUILD PHASE LOOKUP
        phase_lookup = build_phase_lookup(scenario_meta)

        team_participants = []
        player_summaries = []

        for user_id, pid in (scenario.get("participant_data") or {}).items():

            participant = archive_participant_collection.find_one(
                {"id": pid},
                {"_id": 0}
            )

            if not participant or participant.get("team_group") != team_group:
                continue

            team_participants.append(participant)

            user = user_collection.find_one(
                {"user_id": user_id},
                {"_id": 0, "user_full_name": 1, "email": 1}
            ) or {}

            player_summaries.append({
                "user_id": user_id,
                "participant_id": pid,
                "name": user.get("user_full_name", user_id),
                "email": user.get("email"),
                "team": participant.get("team"),
                "team_group": participant.get("team_group"),
                "metrics": compute_participant_quantitative(participant)
            })

        team_quant = compute_team_quantitative(
            team_participants,
            scenario.get("start_time"),
            scenario.get("end_time")
        )

        evidence = collect_team_evidence(team_participants)

        # ✅ PASS PHASE LOOKUP
        phase_analysis = compute_phase_analysis(evidence, phase_lookup)

        return {
            "scenario_meta": {
                "archive_scenario_id": archive_scenario_id,
                "scenario_id": scenario.get("scenario_id"),
                "name": scenario_meta.get("name"),
                "severity": scenario_meta.get("severity"),
                "scoring_type": scenario_meta.get("scoring_type")
            },
            "team": team_group,
            "team_overview": {
                "players": player_summaries,
                "team_metrics": team_quant
            },
            "phase_analysis": {
                "phases": phase_analysis
            },
            "executive_assessment": {
                "overall_readiness": team_quant.get("overall_readiness"),
                "summary_lines": build_executive_narrative(team_quant),
                "final_conclusion": pick_final_conclusion(
                    team_quant.get("score_ratio", 0)
                )
            }
        }
    
class CorporateScenarioEvidenceReportSerializer(serializers.Serializer):

    def get(self, archive_scenario_id, team_group):

        scenario = archive_scenario_collection.find_one(
            {"id": archive_scenario_id, "end_time": {"$ne": None}},
            {"_id": 0}
        )

        if not scenario:
            return {"errors": "Scenario has not ended or archive record not found"}

        # ✅ FETCH SCENARIO META
        scenario_meta = corporate_scenario_collection.find_one(
            {"id": scenario.get("scenario_id")},
            {"_id": 0}
        ) or {}

        # ✅ BUILD PHASE LOOKUP
        phase_lookup = build_phase_lookup(scenario_meta)

        players = []

        for user_id, participant_id in (scenario.get("participant_data") or {}).items():

            participant = archive_participant_collection.find_one(
                {"id": participant_id},
                {"_id": 0}
            )

            if not participant or participant.get("team_group") != team_group:
                continue

            user = user_collection.find_one(
                {"user_id": user_id},
                {"_id": 0, "user_full_name": 1, "email": 1}
            ) or {}

            submissions = []

            for item in participant.get("flag_data", []) + participant.get("milestone_data", []):

                phase_id = item.get("phase_id")
                phase = phase_lookup.get(
                    phase_id,
                    {"id": phase_id, "name": "Unknown Phase"}
                )

                submissions.append({
                    "item": {
                        "id": item.get("flag_id") or item.get("milestone_id"),
                        "type": "flag" if item.get("flag_id") else "milestone"
                    },
                    "phase": {
                        "id": phase["id"],
                        "name": phase["name"]
                    },
                    "status": (
                        "Approved" if item.get("approved_at")
                        else "Submitted" if item.get("submitted_at")
                        else "Not Acted"
                    ),
                    "time_to_first_action": normalize_time(
                        time_to_first_action(item)
                    ),
                    "approval_delay": normalize_time(
                        approval_delay(item)
                    ),
                    "retires": item.get("retires", 0),
                    "score_meta": extract_score_meta(item),
                    "submitted_text": item.get("submitted_text"),
                    "evidence_files": item.get("evidence_files", [])
                })

            players.append({
                "user_id": user_id,
                "participant_id": participant_id,
                "name": user.get("user_full_name", user_id),
                "email": user.get("email"),
                "team": participant.get("team"),
                "team_group": participant.get("team_group"),
                "submissions": submissions
            })

        return {
            "team": team_group,
            "players": players
        }
    
class CorporateUserReportSerializer(serializers.Serializer):
    def get(self, user_id):

        if not user_collection.find_one({"user_id": user_id}):
            return {"errors": "Invalid User ID."}
        # archive-scenario_collection is "corporate_archive_scenario"
        started_by = list(archive_scenario_collection.find({"started_by": user_id}, {"_id": 0}))
        if started_by:
            played_games = started_by
        else:
            played_games = []
            documents = list(archive_scenario_collection.find({}, {'_id': 0}))
            for doc in documents:
                if doc["participant_data"].get(user_id):
                    played_games.append(doc)

        # Initialize a list to store scenario IDs

        scenario_details = []

        # Iterate through the cursor to collect scenario IDs
        for user_data in played_games:
            if user_data.get("started_by") == user_id:
                user_list = []
                for key in user_data["participant_data"].keys():
                    user_list.append(user_collection.find_one({"user_id": key}, {"user_full_name": 1, "_id": 0}))
                scenario_id = user_data.get("scenario_id")
                active_scenario_id = user_data.get("id")
                scenario_document = corporate_scenario_collection.find_one({"id": scenario_id}, {'_id': 0})
                # Extract scenario_name from the scenario document
                scenario_name = scenario_document.get("name") if scenario_document else "Unknown Scenario"
                # Determine the type of data available (flag or milestone)
                data_type = "Flag" if scenario_document.get("flag_data") else "Milestone" if scenario_document.get("milestone_data") else "Unknown Type"
                scenario_details.append({"scenario_id": scenario_id,
                                         "name": scenario_name,
                                         "id": user_data['id'],
                                         "type": data_type,
                                         "score": "NA",
                                         "participant": user_list,
                                         "active_scenario_id": active_scenario_id})
            else:
                scenario_id = user_data.get("scenario_id")
                active_scenario_id = user_data.get("id")
                scenario_document = corporate_scenario_collection.find_one({"id": scenario_id}, {'_id': 0})
                # Extract scenario_name from the scenario document
                scenario_name = scenario_document.get("name") if scenario_document else "Unknown Scenario"
                # Determine the type of data available (flag or milestone)
                data_type = "Flag" if scenario_document.get("flag_data") else "Milestone" if scenario_document.get("milestone_data") else "Unknown Type"
                # archive_participant_collection is corporate_archive_participant_data
                participant_data = archive_participant_collection.find_one({"id": user_data.get("participant_data").get(user_id)}, {"_id": 0})
                scenario_details.append({"scenario_id": scenario_id,
                                         "id": participant_data["id"],
                                         "name": scenario_name,
                                         "type": data_type,
                                         "score": f'{participant_data["total_obtained_score"]}/{participant_data["total_score"]}',
                                         "active_scenario_id": active_scenario_id})
        # If scenario IDs are found, return them
        return scenario_details
        # if scenario_details:
        #     return scenario_details
        # # If no scenario IDs are found, return a message
        # else:
        #     return []


# active scenario participants data
class ActiveScenarioParticipantsSerializer(serializers.Serializer):
    # Assuming corporate_archive_participant_data is a MongoDB collection
    def get(self, active_scenario_id):
        active_game = active_scenario_collection.find_one({"id": active_scenario_id}, {"_id": 0})
        if not active_game:
            return {"errors": "Invalid Active Scenario ID."}
        data = []

        for key in active_game.get("participant_data"):
            user = user_collection.find_one({"user_id": key}, {"_id": 0})

            active_user = dict(participant_data_collection.find_one({"id": active_game.get("participant_data")[key]}, {"_id": 0}))
            active_user["user_avatar"] = user["user_avatar"]
            active_user["user_role"] = user["user_role"]
            active_user["user_full_name"] = user["user_full_name"]
            data.append(active_user)
        new_list = sorted(data, key=lambda x: x["total_obtained_score"], reverse=True)
        return new_list


class CorporateUserReportApiSerializer(serializers.Serializer):
    def get(self, participant_id, user_id):
        # Fetch user details
        data = []
        user_details = user_collection.find_one({"user_id": user_id})
        if not user_details:
            return {"errors": "Invalid User ID."}

        # Check if the user is an admin
        if user_details["is_admin"]:
            # Admin can access documents directly
            documents = archive_scenario_collection.find_one({"id": participant_id}, {'_id': 0})

            for key, value in documents['participant_data'].items():
                user_detail = user_collection.find_one({"user_id": user_id})
                data.append(report_data(value, key))

            return data
        data.append(report_data(participant_id, user_id))
        return data


class FlagStatusSerializer(serializers.Serializer):
    def get(self, participant_id, flag_id):
        participant_data = participant_data_collection.find_one({"id": participant_id}, {"_id": 0})
        if not participant_data:
            return {"errors": "Invalid Participant ID."}

        if not flag_data_collection.find_one({"id": flag_id}):
            return {"errors": "Invalid Flag ID."}

        if not participant_data.get("flag_data"):
            return {"errors": "It is a Milestone based game."}

        for flag in participant_data["flag_data"]:
            if flag.get("flag_id") == flag_id:
                status = [False, "Question hide."] if flag['status'] == True else [True, "Question visible."]
                flag['status'] = status[0]

        participant_data_collection.update_one({"id": participant_id},
                                               {"$set": {
                                                   "flag_data": participant_data["flag_data"]
                                               }})

        return {"message": status[1]}

class CorporateTopologySerializer(serializers.Serializer):

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
        for key_name in [("networks", "network_name",), ("routers", "name",), ("instances", "name")]:
            print('items', scenario_infra)
            for key, value in scenario_infra.items():
                if key == key_name[0]:
                    item_len = len(value)
                    for name, cord in zip([item[key_name[1]] for item in value], self.coordinates(key, item_len)):
                        nodes.append({"id": ite,
                                      "label": name,
                                      "title": "Lorem Ipsum",
                                      "x": cord[0],
                                      "y": cord[1],
                                      "image": f"{API_URL}/static/images/topology/{key_name[0]}.png"
                                      })
                        ite += 1

        for node in nodes:
            for inst in scenario_infra["instances"]:
                networks = inst["network"]
                # If it's a list, loop through it
                if isinstance(networks, list):
                    for net in networks:
                        if net == node["label"]:
                            for inner_node in nodes:
                                if inner_node["label"] == inst["name"]:
                                    edges.append({"from": node["id"], "to": inner_node["id"]})
                # If it's a single string, compare directly
                elif isinstance(networks, str):
                    if networks == node["label"]:
                        for inner_node in nodes:
                            if inner_node["label"] == inst["name"]:
                                edges.append({"from": node["id"], "to": inner_node["id"]})
            for rout in scenario_infra["routers"]:
                if node["label"] in rout["network_name"]:
                    for inner_node in nodes:
                        if inner_node["label"] == rout["name"]:
                            edges.append({"from": inner_node["id"], "to": node["id"]})
        return {"nodes": nodes, "edges": edges}

    def get(self, scenario_id):
        scenario_game = corporate_scenario_collection.find_one({"id": scenario_id})
        if not scenario_game:
            return {"errors": {"non_field_errors": ["Invalid Scenario Id"]}}
        print("infra", scenario_game)
        infra = corporate_scenario_infra_collection.find_one({"id": scenario_game["infra_id"]})
        print('infra', infra)
        # if not scenario_game["scenario_is_prepared"]:
        #     return {"errors": {"non_field_errors": ["Prepare Scenario first."]}}

        topology_infra = self.create_topology(infra)

        return topology_infra
