from corporate_management.utils import (build_channel_key)

import datetime
from database_management.pymongo_client import (
    active_scenario_collection,
    participant_data_collection,
    scenario_chat_channels_collection,

)

ROLE_CHANNELS = ["RED", "BLUE", "PURPLE", "YELLOW"]

def build_chat_channels(active_scenario_id, user):
    active = active_scenario_collection.find_one(
        {"id": active_scenario_id},
        {"_id": 0}
    )
    if not active:
        return []

    channels = []
    user_id = user["user_id"]

    # find participant
    participant = participant_data_collection.find_one(
        {"id": active["participant_data"].get(user_id)},
        {"_id": 0}
    )

    # WHITE TEAM / ADMIN
    if user.get("role") in ["ADMIN", "SUPERADMIN", "WHITE"]:
        team_groups = set()

        for pid in active["participant_data"].values():
            p = participant_data_collection.find_one({"id": pid}, {"_id": 0})
            if p:
                team_groups.add(p.get("team_group", "DEFAULT"))

        for tg in team_groups:
            channels.append({
                "channel_key": f"{tg}_ALL",
                "team_group": tg,
                "scope": "ALL"
            })
            for r in ROLE_CHANNELS:
                channels.append({
                    "channel_key": f"{tg}_{r}",
                    "team_group": tg,
                    "scope": f"{r}_TEAM"
                })

        return channels

    # PLAYER
    if not participant:
        return []

    team_group = participant.get("team_group", "DEFAULT")
    role = participant.get("team")

    channels.append({
        "channel_key": f"{team_group}_{role}",
        "team_group": team_group,
        "scope": f"{role}_TEAM"
    })

    channels.append({
        "channel_key": f"{team_group}_ALL",
        "team_group": team_group,
        "scope": "ALL"
    })

    return channels

