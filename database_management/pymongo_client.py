import pymongo
from django.conf import settings

client = pymongo.MongoClient(settings.MONGO_DB_URI)

# Define Db Name
dbname = client['cyber_range']

# For All Apps
id_collection = dbname.get_collection("id_collection")

# For User Management App
user_collection = dbname.get_collection("user_collection")
user_profile_collection = dbname.get_collection("user_profile_collection")
blacklisted_token_collection = dbname.get_collection("blacklisted_token_collection")

otp_hash_dump_collection = dbname.get_collection("otp_hash_dump_collection")
otp_hash_collection = dbname.get_collection("otp_hash_collection")
otp_hash_collection.create_index("created_at", expireAfterSeconds=180)

user_resource_collection = dbname.get_collection("user_resource_collection")

# For CTF Management App
ctf_category_collection = dbname.get_collection("ctf_category_collection")
ctf_game_collection = dbname.get_collection("ctf_game_collection")
ctf_cloud_mapping_collection = dbname.get_collection("ctf_cloud_mapping_collection")
ctf_active_game_collection = dbname.get_collection("ctf_active_game_collection")
ctf_archive_game_collection = dbname.get_collection("ctf_archive_game_collection")
ctf_player_arsenal_collection = dbname.get_collection("ctf_player_arsenal_collection")

# For Scenario Management App
scenario_category_collection = dbname.get_collection("scenario_category_collection")
scenario_collection = dbname.get_collection("scenario_collection")
scenario_active_game_collection = dbname.get_collection("scenario_active_game_collection")
scenario_archive_game_collection = dbname.get_collection("scenario_archive_game_collection")
scenario_player_arsenal_collection = dbname.get_collection("scenario_player_arsenal_collection")
scenario_invitation_collection = dbname.get_collection("scenario_invitation_collection")
scenario_user_resource_collection = dbname.get_collection("scenario_user_resource_collection")

# For webbased
web_based_category_collection = dbname.get_collection("web_based_category_collection")
web_based_game_collection = dbname.get_collection("web_based_game_collection")
web_based_game_started_collection = dbname.get_collection("web_based_game_started_collection")
web_based_game_ratings_collection = dbname.get_collection("web_based_game_ratings_collection")

# For Challenge Management App
challenge_game_collection = dbname.get_collection("challenge_game_collection")

# For Core Management App
email_collection = dbname.get_collection("email_collection")

# For notification
notification_group_collection = dbname.get_collection("notification_group_collection")
notification_collection = dbname.get_collection("notification_collection")

# For Buffer
game_start_buffer_collection = dbname.get_collection("game_start_buffer_collection")
game_start_buffer_collection.create_index("created_at", expireAfterSeconds=900)

# For News
news_collection = dbname.get_collection("news_collection")

resource_credentials_collection = dbname.get_collection("resource_credentials_collection")

# Corporate
corporate_scenario_collection = dbname.get_collection("corporate_scenario")
corporate_scenario_infra_collection = dbname.get_collection("corporate_scenario_infra")
flag_data_collection = dbname.get_collection("corporate_flag_data")
milestone_data_collection = dbname.get_collection("corporate_milestone_data")

participant_data_collection = dbname.get_collection("corporate_participant_data")
corporate_participant_data = dbname.get_collection("corporate_participant_data")
active_scenario_collection = dbname.get_collection("corporate_active_scenario")
archive_scenario_collection = dbname.get_collection("corporate_archive_scenario")
corporate_archive_scenario = dbname.get_collection("corporate_archive_scenario")
archive_participant_collection = dbname.get_collection("corporate_archive_participant_data")
corporate_flag_data_collection = dbname.get_collection("corporate_flag_data")

# Scenario Team Chat 
scenario_chat_channels_collection = dbname.get_collection(
    "scenario_chat_channels"
)
scenario_chat_messages_collection = dbname.get_collection(
    "scenario_chat_messages"
)
scenario_chat_messages_collection.create_index("channel_key")
scenario_chat_messages_collection.create_index(
    [("channel_key", 1), ("created_at", 1)]
)