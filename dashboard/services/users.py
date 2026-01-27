from database_management.pymongo_client import user_collection, user_profile_collection


class UserService:
    @classmethod
    def get_users_with_profiles(cls, role: str = None, is_active: bool = None):
        # Build dynamic query based on filters
        query = {}
        if role:
            query['user_role'] = role
        if is_active is not None:
            query['is_active'] = is_active

        users_cursor = user_collection.find(query, {
            '_id': 0,
            'user_id': 1,
            'user_full_name': 1,
            'user_avatar': 1,
            'user_role': 1,
            'is_active': 1,
            'created_at': 1,
        })

        enriched_users = []

        for user in users_cursor:
            profile = user_profile_collection.find_one(
                {'user_id': user['user_id']},
                {'_id': 0, 'user_profile_created_at': 0, 'assigned_games': 0}
            )

            if profile:
                profile['ctf_score'] = round(profile.get('user_ctf_score', 0))
                profile['scenario_score'] = round(profile.get('user_scenario_score', 0))
                profile['corporate_score'] = round(profile.get('user_corporate_score', 0))
            else:
                profile = {
                    'ctf_score': 0,
                    'scenario_score': 0,
                    'corporate_score': 0,
                }

            user['user_profile'] = profile
            enriched_users.append(user)

        return enriched_users

    @staticmethod
    def get_user_profile_by_id(user_id: int):
        # Build dynamic query based on filters
        query = {
            'user_id': user_id,
            'is_active': True,
        }
        users_cursor = user_collection.find_one(query, {
            '_id': 0,
            'user_id': 1,
            'email': 1,
            'user_full_name': 1,
            'user_avatar': 1,
            'user_role': 1,
            'is_active': 1,
            'created_at': 1,
        })

        return users_cursor
