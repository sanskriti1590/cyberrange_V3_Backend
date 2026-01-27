from bson import ObjectId
from rest_framework import serializers

from database_management.pymongo_client import web_based_game_started_collection


class ConsolePageDetailSerializer(serializers.Serializer):
    """
    Serializer to fetch details of a specific game along with the associated player and game information.
    """

    def get(self, _id):
        """
        Retrieves the game and associated player details based on the provided _id (game ID).
        Returns None if no game is found.
        """
        # MongoDB aggregation pipeline to fetch game details and player information
        pipeline = [
            {"$match": {"_id": ObjectId(_id)}},  # Match the game by _id
            {
                "$lookup": {
                    "from": "user_collection",  # Join with user_collection for player details
                    "localField": "player_id",  # Field from the game collection
                    "foreignField": "user_id",  # Field in the user collection
                    "as": "player_details"  # Output field to store player details
                }
            },
            {
                "$unwind": {
                    "path": "$player_details",  # Flatten player details array
                    "preserveNullAndEmptyArrays": False  # Don't keep empty player details
                }
            },
            {
                "$lookup": {
                    "from": "web_based_game_collection",  # Join with web_based_game_collection for game details
                    "localField": "game_id",  # Field from the game collection
                    "foreignField": "game_id",  # Field in the game collection
                    "as": "game_details"  # Output field to store game details
                }
            },
            {
                "$unwind": {
                    "path": "$game_details",  # Flatten game details array
                    "preserveNullAndEmptyArrays": False  # Don't keep empty game details
                }
            },
            {
                "$project": {  # Specify the fields to include in the result
                    "_id": {"$toString": "$_id"},  # Convert ObjectId to string for easy use in response
                    "player_id": 1,
                    "is_complete": 1,
                    "game_id": 1,
                    "score": 1,
                    "game_details": {  # Flatten game details
                        "_id": 0,  # Exclude internal _id
                        "game_id": 1,
                        "is_approved": 1,
                        "name": 1,
                        "description": 1,
                        "thumbnail": 1,
                        "walkthrough_file_url": 1,
                    },
                    "player_details": {  # Flatten player details
                        "user_id": 1,
                        "user_full_name": 1,
                        "user_role": 1,
                        "user_avatar": 1,
                        "game_points": 1,
                    }
                }
            }
        ]

        # Execute the aggregation pipeline and fetch the first document
        played_game_cursor = web_based_game_started_collection.aggregate(pipeline)
        print(played_game_cursor)
        # Check if the aggregation returned any result
        played_game = next(played_game_cursor, None)
        print(played_game)
        return played_game  # Return None if no game is found
