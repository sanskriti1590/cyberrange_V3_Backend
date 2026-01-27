from database_management.pymongo_client import (
    ctf_archive_game_collection,
    corporate_archive_scenario,
    scenario_archive_game_collection,
    user_collection,
    user_profile_collection,
    notification_collection,
    corporate_scenario_collection,
    scenario_collection,
    web_based_game_collection,
    ctf_game_collection
)


class AnalyticsServices:

    @staticmethod
    def safe_round(value, digits=2):
        """Safely round a value, treating None as 0."""
        return round(value or 0, digits)

    # Archive/Completed scenario
    @staticmethod
    def get_total_ctf_scenario_archive():
        return ctf_archive_game_collection.count_documents({})

    @staticmethod
    def get_total_corporate_scenario_archive():
        return corporate_archive_scenario.count_documents({})

    @staticmethod
    def get_total_scenario_archive():
        return scenario_archive_game_collection.count_documents({})

    # Ready scenario
    @staticmethod
    def get_total_ctf_scenario_ready():
        return ctf_game_collection.count_documents({"ctf_is_approved": True})

    @staticmethod
    def get_total_corporate_scenario_ready():
        return corporate_scenario_collection.count_documents({"is_approved": True, "is_prepared": True})

    @staticmethod
    def get_total_scenario_ready():
        return scenario_collection.count_documents({"scenario_is_approved": True, "scenario_is_prepared": True})

    @staticmethod
    def get_total_web_based_scenario_ready():
        return web_based_game_collection.count_documents({"is_approved": True})

    @staticmethod
    def get_total_user():
        return user_collection.count_documents({})

    @staticmethod
    def get_latest_notifications(limit=10):
        cursor = notification_collection.find(
            {},
            {
                "_id": 0,
                "action_urls": 0,
                "redirection_url": 0,
                "description": 0
            }
        ).sort("timestamp", -1).limit(limit)

        return [
            {
                "type": doc.get("type"),
                "title": doc.get("title"),
                "timestamp": doc.get("timestamp").isoformat() if doc.get("timestamp") else None
            }
            for doc in cursor
        ]

    @staticmethod
    def get_average_scores():
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "avg_ctf_score": {"$avg": "$user_ctf_score"},
                    "avg_scenario_score": {"$avg": "$user_scenario_score"},
                    "avg_corporate_score": {"$avg": "$user_corporate_score"},
                    "total_users": {"$sum": 1}
                }
            }
        ]
        result = list(user_profile_collection.aggregate(pipeline))
        if result:
            return {
                "avg_ctf_score": AnalyticsServices.safe_round(result[0].get("avg_ctf_score")),
                "avg_scenario_score": AnalyticsServices.safe_round(result[0].get("avg_scenario_score")),
                "avg_corporate_score": AnalyticsServices.safe_round(result[0].get("avg_corporate_score")),
                "total_users": result[0].get("total_users", 0)
            }
        else:
            return {
                "avg_ctf_score": 0,
                "avg_scenario_score": 0,
                "avg_corporate_score": 0,
                "total_users": 0
            }

    @staticmethod
    def get_top_rank_users(limit=5):
        pipeline = [
            {
                "$addFields": {
                    "total_score": {
                        "$add": [
                            {"$ifNull": ["$user_ctf_score", 0]},
                            {"$ifNull": ["$user_scenario_score", 0]},
                            {"$ifNull": ["$user_corporate_score", 0]}
                        ]
                    }
                }
            },
            {"$sort": {"total_score": -1}},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "user_collection",
                    "localField": "user_id",
                    "foreignField": "user_id",
                    "as": "user_info"
                }
            },
            {
                "$unwind": {
                    "path": "$user_info",
                    "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "user_id": 1,
                    "user_ctf_score": 1,
                    "user_scenario_score": 1,
                    "user_corporate_score": 1,
                    "total_score": 1,
                    "user_full_name": "$user_info.user_full_name",
                    "user_avatar": "$user_info.user_avatar",
                    "user_role": "$user_info.user_role"
                }
            }
        ]

        return list(user_profile_collection.aggregate(pipeline))

    @staticmethod
    def get_analytics():
        average_scores = AnalyticsServices.get_average_scores()
        top_rank_users = AnalyticsServices.get_top_rank_users(limit=5) or []
        latest_notifications = AnalyticsServices.get_latest_notifications() or []

        data_params = {
            "scenario": {
                "archive": {
                    "total_ctf_scenario": AnalyticsServices.get_total_ctf_scenario_archive() or 0,
                    "total_corporate_scenario": AnalyticsServices.get_total_corporate_scenario_archive() or 0,
                    "total_scenario": AnalyticsServices.get_total_scenario_archive() or 0
                },
                "ready": {
                    "total_ctf_scenario": AnalyticsServices.get_total_ctf_scenario_ready() or 0,
                    "total_corporate_scenario": AnalyticsServices.get_total_corporate_scenario_ready() or 0,
                    "total_scenario": AnalyticsServices.get_total_scenario_ready() or 0,
                    "total_webbased_scenario": AnalyticsServices.get_total_web_based_scenario_ready() or 0
                }
            },
            "user": {
                "total_user": AnalyticsServices.get_total_user() or 0
            },
            "scores": {
                "average_scores": average_scores,
                "top_rank_users": top_rank_users
            },
            "notifications": latest_notifications
        }

        return data_params
