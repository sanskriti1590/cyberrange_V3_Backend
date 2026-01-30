from database_management.pymongo_client import (
    active_scenario_collection,
    participant_data_collection,
)

ROLE_CHANNELS = ["RED", "BLUE", "PURPLE", "YELLOW"]

def build_chat_channels(active_scenario_id: str, user: dict):
    if not active_scenario_id or not user:
        return []

    active = active_scenario_collection.find_one(
        {"id": active_scenario_id},
        {"_id": 0}
    )
    if not active:
        return []

    channels = []

    user_id = user.get("user_id")
    user_role = (user.get("user_role") or "").upper()

    is_superadmin = user.get("is_superadmin", False)
    is_admin = user.get("is_admin", False)
    is_white = "WHITE" in user_role


    # ==========================================================
    # SUPERADMIN → EVERYTHING
    # ==========================================================
    if is_superadmin:
        team_groups = set()

        for pid in active.get("participant_data", {}).values():
            p = participant_data_collection.find_one({"id": pid}, {"_id": 0})
            if p:
                team_groups.add(p.get("team_group", "DEFAULT"))

        for tg in sorted(team_groups):
            channels.append(_team_all_channel(active_scenario_id, tg))
            channels.extend(_team_role_channels(active_scenario_id, tg))

        channels.append(_global_channel(active_scenario_id))
        return channels

    # ==========================================================
    # WHITE / ADMIN → ONLY ALLOWED TEAMS
    # ==========================================================
# ==========================================================
    if is_white:
        # 🔐 white team only sees scenarios they started
        if active.get("started_by") != user_id:
            return []

        team_groups = _derive_team_groups_from_participants(active)

        for tg in team_groups:
            channels.append(_team_all_channel(active_scenario_id, tg))
            channels.extend(_team_role_channels(active_scenario_id, tg))

        channels.append(_global_channel(active_scenario_id))
        return channels
    
    # ==========================================================
    # NORMAL PLAYER
    # ==========================================================
    participant = participant_data_collection.find_one(
        {"id": active.get("participant_data", {}).get(user_id)},
        {"_id": 0}
    )
    if not participant:
        return []

    team_group = participant.get("team_group", "DEFAULT")
    role = (participant.get("team") or "").upper()

    return [
        _team_role_channel(active_scenario_id, team_group, role),
        _team_all_channel(active_scenario_id, team_group),
    ]


def _team_role_channel(scn_id, team, role):
    return {
        "channel_key": f"{scn_id}__{team}_{role}",
        "team_group": team,
        "scope": f"{role}_TEAM",
        "label": f"{team} — {role} Team",
    }

def _team_role_channels(scn_id, team):
    return [
        _team_role_channel(scn_id, team, role)
        for role in ROLE_CHANNELS
    ]

def _team_all_channel(scn_id, team):
    return {
        "channel_key": f"{scn_id}__{team}_ALL",
        "team_group": team,
        "scope": "ALL",
        "label": f"{team} — All Teams",
    }

def _global_channel(scn_id):
    return {
        "channel_key": f"{scn_id}__ALL_TEAMS_ALL",
        "team_group": "ALL",
        "scope": "GLOBAL",
        "label": "All Teams — All Roles",
    }

def _derive_team_groups_from_participants(active):
    team_groups = set()

    for pd_id in active.get("participant_data", {}).values():
        pd = participant_data_collection.find_one(
            {"id": pd_id},
            {"_id": 0}
        )
        if pd and pd.get("team_group"):
            team_groups.add(pd["team_group"])

    return sorted(team_groups)
