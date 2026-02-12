from rest_framework import serializers
import datetime
import uuid
from typing import List, Optional

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
from user_management.permissions import CustomIsAuthenticated, CustomIsAdmin, CustomIsSuperAdmin

class SuperAdminActiveScenarioListSerializer(serializers.Serializer):
    def get(self):
        items = list(
            active_scenario_collection.find(
                {"end_time": None}, {"_id": 0}
            )
        )

        out = []

        for a in items:
            scenario = corporate_scenario_collection.find_one(
                {"id": a.get("scenario_id")}, {"_id": 0}
            ) or {}

            participant_map = a.get("participant_data") or {}
            user_ids = list(participant_map.keys())

            users = list(
                user_collection.find(
                    {"user_id": {"$in": user_ids}},
                    {"_id": 0, "user_id": 1, "user_role": 1},
                )
            )

            # roles from users
            roles_present = sorted(
                {
                    u.get("user_role")
                    for u in users
                    if u.get("user_role")
                }
            )

            teams_present = a.get("team_groups") or []

            out.append(
                {
                    "active_scenario_id": a.get("id"),
                    "scenario_id": a.get("scenario_id"),
                    "scenario_name": scenario.get("name")
                    or scenario.get("scenario_name")
                    or "Active Scenario",
                    "start_time": a.get("start_time"),
                    "started_by": a.get("started_by"),
                    "participants_count": len(user_ids),
                    "teams_present": teams_present,
                    "roles_present": roles_present,
                }
            )

        out.sort(
            key=lambda x: x.get("start_time") or 0,
            reverse=True,
        )

        return out

class SuperAdminActiveScenarioOverviewSerializer(serializers.Serializer):
    def get(self, active_scenario_id):
        a = active_scenario_collection.find_one(
            {"id": active_scenario_id},
            {"_id": 0}
        )

        if not a:
            return {"errors": "Invalid Active Scenario ID"}

        scenario = corporate_scenario_collection.find_one(
            {"id": a.get("scenario_id")},
            {"_id": 0}
        ) or {}

        participant_map = a.get("participant_data") or {}
        user_ids = list(participant_map.keys())

        users = list(
            user_collection.find(
                {"user_id": {"$in": user_ids}},
                {
                    "_id": 0,
                    "user_id": 1,
                    "user_role": 1,
                    "user_full_name": 1,
                },
            )
        )

        # Roles from users
        roles_present = sorted(
            {
                u.get("user_role")
                for u in users
                if u.get("user_role")
            }
        )

        teams_present = a.get("team_groups") or []

        return {
            "active_scenario_id": a.get("id"),
            "scenario_id": a.get("scenario_id"),
            "scenario_name": scenario.get("name")
            or scenario.get("scenario_name")
            or "Active Scenario",
            "start_time": a.get("start_time"),
            "scoring_config": scenario.get(
                "scoring_config",
                {"type": "standard"},
            ),
            "roles_present": roles_present,
            "teams_present": teams_present,
            "participants_count": len(user_ids),
        }



def safe_int(v, default=0):
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def to_ms(value):
    if not value:
        return None

    if isinstance(value, datetime.datetime):
        return int(value.timestamp() * 1000)

    if isinstance(value, str):
        try:
            dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            return None

    return None


# SUPER ADMIN ACTIVE SCENARIO LEADERBOARD (UPDATED VERSION)
class SuperAdminActiveScenarioLeaderboardSerializer(serializers.Serializer):

    def get(self, active_scenario_id):

        # ACTIVE SCENARIO
        active = active_scenario_collection.find_one(
            {"id": active_scenario_id}, {"_id": 0}
        )
        if not active:
            return {"errors": "Invalid Active Scenario ID"}

        scenario_id = active.get("scenario_id")

        scenario = corporate_scenario_collection.find_one(
            {"id": scenario_id}, {"_id": 0}
        ) or {}

        # PHASE MAP
        phase_map = {
            p["id"]: p.get("name")
            for p in scenario.get("phases", [])
            if p.get("id")
        }

        phases_list = [
            {"phase_id": pid, "phase_name": pname}
            for pid, pname in phase_map.items()
        ]

        # FLAGS & MILESTONES CONFIG
        flags = list(flag_data_collection.find(
            {"scenario_id": scenario_id}, {"_id": 0}
        )) or []

        milestones = list(milestone_data_collection.find(
            {"scenario_id": scenario_id}, {"_id": 0}
        )) or []

        flag_map = {f.get("id"): f for f in flags if f.get("id")}
        milestone_map = {m.get("id"): m for m in milestones if m.get("id")}

        total_items = len(flags) if len(flags) > 0 else len(milestones)

        # PARTICIPANTS
        participant_map = active.get("participant_data") or {}
        user_ids = list(participant_map.keys())

        users = list(user_collection.find(
            {"user_id": {"$in": user_ids}},
            {"_id": 0, "user_id": 1, "user_full_name": 1, "user_role": 1}
        )) or []

        user_by_id = {u["user_id"]: u for u in users if u.get("user_id")}

        participant_ids = [participant_map[uid] for uid in user_ids if participant_map.get(uid)]

        participants = list(participant_data_collection.find(
            {"id": {"$in": participant_ids}}, {"_id": 0}
        )) or []

        part_by_id = {p["id"]: p for p in participants if p.get("id")}

        players = []

        # BUILD PLAYERS
        for uid in user_ids:

            pid = participant_map.get(uid)
            pdoc = part_by_id.get(pid) or {}
            u = user_by_id.get(uid) or {}

            # total obtained score (primary)
            total_score = safe_int(pdoc.get("total_obtained_score"))

            team_group = pdoc.get("team_group") or "NO_GROUP"
            role = pdoc.get("team") or u.get("user_role") or "UNKNOWN"

            milestone_data = pdoc.get("milestone_data") or []
            flag_data = pdoc.get("flag_data") or []

            breakdown = []
            submit_times = []
            response_times = []
            items_completed = 0

            # -------- Milestones --------
            for m in milestone_data:
                mid = m.get("milestone_id")
                config = milestone_map.get(mid, {}) if mid else {}

                score = safe_int(m.get("obtained_score"))
                visible = to_ms(m.get("first_visible_at"))
                submitted = to_ms(m.get("submitted_at"))

                if visible and submitted:
                    response_times.append(submitted - visible)

                if score > 0:
                    items_completed += 1

                breakdown.append({
                    "type": "MILESTONE",
                    "phase_id": m.get("phase_id"),
                    "item_id": mid,
                    "name": config.get("name") or mid,
                    "description": config.get("description") or "",
                    "points": safe_int(config.get("score") or config.get("points")),
                    "role": config.get("team") or role,
                    "score": score,
                    "status": bool(m.get("status", True)),
                    "locked_by_admin": bool(m.get("locked_by_admin", False)),
                    "submitted_at": submitted,
                })

                if submitted:
                    submit_times.append(submitted)

            # -------- Flags --------
            for f in flag_data:
                fid = f.get("flag_id")
                config = flag_map.get(fid, {}) if fid else {}

                score = safe_int(f.get("obtained_score"))
                visible = to_ms(f.get("first_visible_at"))
                submitted = to_ms(f.get("submitted_at"))

                if visible and submitted:
                    response_times.append(submitted - visible)

                if score > 0:
                    items_completed += 1

                breakdown.append({
                    "type": "FLAG",
                    "phase_id": f.get("phase_id"),
                    "item_id": fid,
                    "name": config.get("name") or fid,
                    "description": config.get("description") or "",
                    "points": safe_int(config.get("score") or config.get("points")),
                    "role": config.get("team") or role,
                    "score": score,
                    "status": bool(f.get("status", True)),
                    "locked_by_admin": bool(f.get("locked_by_admin", False)),
                    "submitted_at": submitted,
                })

                if submitted:
                    submit_times.append(submitted)

            completion = (
                round((items_completed / total_items) * 100, 2)
                if total_items > 0 else 0
            )

            last_submit = max(submit_times) if submit_times else None

            avg_response_time_ms = (
                int(sum(response_times) / len(response_times))
                if response_times else None
            )

            players.append({
                "user_id": uid,
                "participant_id": pid,
                "name": u.get("user_full_name") or uid,
                "role": role,
                "team_group": team_group,
                "score": total_score,
                "items_completed": items_completed,
                "total_items": total_items,
                "completion": completion,
                "avg_response_time_ms": avg_response_time_ms,
                "last_submit": last_submit,
                "breakdown": breakdown,
            })

        # SORT
        players.sort(
            key=lambda x: (
                -safe_int(x.get("score")),
                x.get("last_submit") if x.get("last_submit") else float("inf")
            )
        )


        config_by_phase = {}

        # base items from scenario config (default locked=True)
        for f in flags:
            phase_id = f.get("phase_id")
            if not phase_id:
                continue
            config_by_phase.setdefault(phase_id, []).append({
                "type": "FLAG",
                "id": f.get("id"),
                "name": f.get("name") or f.get("id"),
                "description": f.get("description") or "",
                "points": safe_int(f.get("score") or f.get("points")),
                "role": f.get("team") or "BLUE",
                "locked": True,
                "assigned_to": [],
            })

        for m in milestones:
            phase_id = m.get("phase_id")
            if not phase_id:
                continue
            config_by_phase.setdefault(phase_id, []).append({
                "type": "MILESTONE",
                "id": m.get("id"),
                "name": m.get("name") or m.get("id"),
                "description": m.get("description") or "",
                "points": safe_int(m.get("score") or m.get("points")),
                "role": m.get("team") or "BLUE",
                "locked": True,
                "assigned_to": [],
            })

        # aggregate lock + assigned_to (team_groups where visible)
        for pdoc in participants:
            tg = pdoc.get("team_group") or "NO_GROUP"

            for fd in (pdoc.get("flag_data") or []):
                phase_id = fd.get("phase_id")
                fid = fd.get("flag_id")
                if not phase_id or not fid:
                    continue
                for item in config_by_phase.get(phase_id, []):
                    if item["type"] == "FLAG" and item["id"] == fid:
                        is_locked = bool(fd.get("locked_by_admin", False)) or (not bool(fd.get("status", True)))
                        if not is_locked:
                            item["locked"] = False
                            if tg not in item["assigned_to"]:
                                item["assigned_to"].append(tg)

            for md in (pdoc.get("milestone_data") or []):
                phase_id = md.get("phase_id")
                mid = md.get("milestone_id")
                if not phase_id or not mid:
                    continue
                for item in config_by_phase.get(phase_id, []):
                    if item["type"] == "MILESTONE" and item["id"] == mid:
                        is_locked = bool(md.get("locked_by_admin", False)) or (not bool(md.get("status", True)))
                        if not is_locked:
                            item["locked"] = False
                            if tg not in item["assigned_to"]:
                                item["assigned_to"].append(tg)

 
        # SCORE ADJUSTMENTS (audit)
 
        adjustments = active.get("score_adjustments") or []
        for a in adjustments:
            ts = a.get("timestamp") or a.get("created_at")
            if isinstance(ts, datetime.datetime):
                a["timestamp_ms"] = to_ms(ts)
            elif isinstance(ts, str):
                a["timestamp_ms"] = to_ms(ts)

        return {
            "players": players,
            "phases": phases_list,
            "teams_present": list(set(p["team_group"] for p in players)),
            "roles_present": list(set(p["role"] for p in players)),
            "score_adjustments": adjustments,
            "config": {
                "by_phase": config_by_phase,
                "team_groups": list(set(p["team_group"] for p in players)),
            }
        }

class SuperAdminManualScoreSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100)
    participant_id = serializers.CharField(max_length=100)
    delta = serializers.IntegerField()
    note = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.ChoiceField(choices=["BONUS", "PENALTY"])

    def validate(self, data):
        active = active_scenario_collection.find_one(
            {"id": data["active_scenario_id"]},
            {"_id": 0}
        )
        if not active:
            raise serializers.ValidationError("Invalid active_scenario_id")

        participant_map = active.get("participant_data", {}) or {}

        incoming = data["participant_id"]

        participant_data_id = None
        user_id = None

        # Case 1: participant_id is user_id
        if incoming in participant_map:
            user_id = incoming
            participant_data_id = participant_map[incoming]

        # Case 2: participant_id is participant_data_id
        else:
            for uid, pdid in participant_map.items():
                if pdid == incoming:
                    user_id = uid
                    participant_data_id = pdid
                    break

        if not participant_data_id:
            raise serializers.ValidationError("Invalid participant_id")

        data["participant_data_id"] = participant_data_id
        data["user_id"] = user_id
        data["active_doc"] = active
        return data

    def create(self, validated_data):
        now = utcnow()

        delta = validated_data["delta"]
        reason = validated_data["reason"]

        #  Structure you requested
        adjustment_entry = {
            "type": reason,
            "delta": delta,
            "note": validated_data.get("note", ""),
            "timestamp": now
        }


        # Update participant document

        update_query = {
            "$inc": {
                "total_obtained_score": delta,
            },
            "$push": {
                "manual_adjustments": adjustment_entry
            },
            "$set": {
                "updated_at": now
            }
        }

        # Maintain separate bonus / penalty tracking
        if reason == "BONUS":
            update_query["$inc"]["bonus_score"] = delta
        else:
            update_query["$inc"]["penalty_score"] = delta

        participant_data_collection.update_one(
            {"id": validated_data["participant_data_id"]},
            update_query
        )

        # Also store in active scenario

        active_scenario_collection.update_one(
            {"id": validated_data["active_scenario_id"]},
            {
                "$push": {
                    "score_adjustments": {
                        "participant_data_id": validated_data["participant_data_id"],
                        "type": reason,
                        "delta": delta,
                        "note": validated_data.get("note", ""),
                        "timestamp": now
                    }
                },
                "$set": {"updated_at": now}
            }
        )

        return {
            "message": "Score adjustment applied",
            "adjustment": adjustment_entry
        }

# collections (import from wherever you keep them)
# from corporate_management.mongo import (
#   active_scenario_collection, participant_data_collection
# )

def utcnow():
    return datetime.datetime.utcnow()

def resolve_scope_participant_ids(
    active_doc: dict,
    scope: str,
    participant_id: Optional[str] = None,
    team_group: Optional[str] = None,
) -> List[str]:
    """
    Returns participant_data IDs (NOT user_ids).
    active_doc['participant_data'] is assumed like:
      { user_id: participant_data_id, ... }
    """
    participant_map = active_doc.get("participant_data", {}) or {}
    participant_data_ids = list(participant_map.values())

    if scope == "ALL":
        return participant_data_ids

    if scope == "TEAM":
        if not team_group:
            raise serializers.ValidationError({"non_field_errors": ["team_group required for TEAM scope"]})

        docs = list(participant_data_collection.find(
            {"id": {"$in": participant_data_ids}, "team_group": team_group},
            {"_id": 0, "id": 1}
        ))
        return [d["id"] for d in docs]

    if scope == "PARTICIPANT":
        if not participant_id:
            raise serializers.ValidationError({"non_field_errors": ["participant_id required for PARTICIPANT scope"]})

        # participant_id can be user_id OR participant_data_id
        if participant_id in participant_map:
            return [participant_map[participant_id]]

        if participant_id in participant_data_ids:
            return [participant_id]

        raise serializers.ValidationError({"non_field_errors": ["Invalid participant_id for scope"]})

    raise serializers.ValidationError({"non_field_errors": ["Invalid scope"]})

class SuperAdminToggleFlagLockSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100, required=True)
    flag_id = serializers.CharField(max_length=100, required=True)
    locked = serializers.BooleanField(required=True)

    scope = serializers.ChoiceField(choices=["ALL", "TEAM", "PARTICIPANT"], required=True)
    team_group = serializers.CharField(max_length=50, required=False, allow_blank=True)
    participant_id = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, data):
        active = active_scenario_collection.find_one({"id": data["active_scenario_id"]}, {"_id": 0})
        if not active:
            raise serializers.ValidationError({"non_field_errors": ["Invalid active_scenario_id"]})
        data["active_doc"] = active
        return data

    def create(self, validated_data):
        now = utcnow()
        active = validated_data["active_doc"]

        target_ids = resolve_scope_participant_ids(
            active_doc=active,
            scope=validated_data["scope"],
            team_group=(validated_data.get("team_group") or None),
            participant_id=(validated_data.get("participant_id") or None),
        )

        status = not validated_data["locked"]  # True => visible

        set_fields = {
            "flag_data.$[f].status": status,
            "flag_data.$[f].locked_by_admin": bool(validated_data["locked"]),
            "flag_data.$[f].updated_at": now,
        }

        # only anchor on unlock (do not wipe on lock)
        if status:
            set_fields["flag_data.$[f].first_visible_at"] = now

        res = participant_data_collection.update_many(
            {"id": {"$in": target_ids}},
            {"$set": set_fields},
            array_filters=[{"f.flag_id": validated_data["flag_id"]}]
        )

        return {
            "message": "Flag lock updated",
            "flag_id": validated_data["flag_id"],
            "locked": bool(validated_data["locked"]),
            "scope": validated_data["scope"],
            "updated_participants": res.modified_count,
            "timestamp_ms": to_ms(now),
        }


# SUPERADMIN TOGGLE MILESTONE LOCK 
class SuperAdminToggleMilestoneLockSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100, required=True)
    milestone_id = serializers.CharField(max_length=100, required=True)
    locked = serializers.BooleanField(required=True)

    scope = serializers.ChoiceField(choices=["ALL", "TEAM", "PARTICIPANT"], required=True)
    team_group = serializers.CharField(max_length=50, required=False, allow_blank=True)
    participant_id = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, data):
        active = active_scenario_collection.find_one({"id": data["active_scenario_id"]}, {"_id": 0})
        if not active:
            raise serializers.ValidationError({"non_field_errors": ["Invalid active_scenario_id"]})
        data["active_doc"] = active
        return data

    def create(self, validated_data):
        now = utcnow()
        active = validated_data["active_doc"]

        target_ids = resolve_scope_participant_ids(
            active_doc=active,
            scope=validated_data["scope"],
            team_group=(validated_data.get("team_group") or None),
            participant_id=(validated_data.get("participant_id") or None),
        )

        status = not validated_data["locked"]

        set_fields = {
            "milestone_data.$[m].status": status,
            "milestone_data.$[m].locked_by_admin": bool(validated_data["locked"]),
            "milestone_data.$[m].updated_at": now,
        }

        if status:
            set_fields["milestone_data.$[m].first_visible_at"] = now

        res = participant_data_collection.update_many(
            {"id": {"$in": target_ids}},
            {"$set": set_fields},
            array_filters=[{"m.milestone_id": validated_data["milestone_id"]}]
        )

        return {
            "message": "Milestone lock updated",
            "milestone_id": validated_data["milestone_id"],
            "locked": bool(validated_data["locked"]),
            "scope": validated_data["scope"],
            "updated_participants": res.modified_count,
            "timestamp_ms": to_ms(now),
        }

# SUPERADMIN TOGGLE PHASE LOCK (scope)
class SuperAdminTogglePhaseLockSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField(max_length=100, required=True)
    phase_id = serializers.CharField(max_length=100, required=True)
    locked = serializers.BooleanField(required=True)

    scope = serializers.ChoiceField(choices=["PARTICIPANT", "TEAM", "ALL"], required=True)
    team_group = serializers.CharField(required=False, allow_blank=True)
    participant_id = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        active = active_scenario_collection.find_one({"id": data["active_scenario_id"]}, {"_id": 0})
        if not active:
            raise serializers.ValidationError({"non_field_errors": ["Invalid active_scenario_id"]})
        data["active_doc"] = active
        return data

    def create(self, validated_data):
        now = utcnow()
        status = not validated_data["locked"]
        active_doc = validated_data["active_doc"]

        target_ids = resolve_scope_participant_ids(
            active_doc=active_doc,
            scope=validated_data["scope"],
            team_group=(validated_data.get("team_group") or None),
            participant_id=(validated_data.get("participant_id") or None),
        )

        set_fields = {
            "flag_data.$[f].status": status,
            "flag_data.$[f].locked_by_admin": bool(validated_data["locked"]),
            "flag_data.$[f].updated_at": now,

            "milestone_data.$[m].status": status,
            "milestone_data.$[m].locked_by_admin": bool(validated_data["locked"]),
            "milestone_data.$[m].updated_at": now,
            "updated_at": now,
        }

        # anchor only on unlock
        if status:
            set_fields["flag_data.$[f].first_visible_at"] = now
            set_fields["milestone_data.$[m].first_visible_at"] = now

        res = participant_data_collection.update_many(
            {"id": {"$in": target_ids}},
            {"$set": set_fields},
            array_filters=[
                {"f.phase_id": validated_data["phase_id"]},
                {"m.phase_id": validated_data["phase_id"]},
            ]
        )

        return {
            "message": "Phase lock updated",
            "phase_id": validated_data["phase_id"],
            "locked": bool(validated_data["locked"]),
            "scope": validated_data["scope"],
            "updated_participants": res.modified_count,
            "timestamp_ms": to_ms(now),
        }