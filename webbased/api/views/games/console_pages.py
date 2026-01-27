from bson import ObjectId
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from database_management.pymongo_client import web_based_game_started_collection
from user_management.permissions import CustomIsAuthenticated


class ConsolePageDetailAPIView(APIView):
    """
    API View to fetch details of a specific game along with the associated player and game information.
    """
    permission_classes = [CustomIsAuthenticated]

    def get(self, request, _id):
        # Validate that _id is provided
        if not _id:
            # If _id is empty, raise a validation error with exception format
            return Response({"error": ["_id cannot be empty."]}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the provided _id is a valid ObjectId format
        try:
            object_id = ObjectId(_id)
        except Exception:
            # If _id is not a valid ObjectId, raise a validation error with exception format
            return Response({"error": ["Invalid _id format. Ensure it's a valid ObjectId."]}, status=status.HTTP_400_BAD_REQUEST)

        # MongoDB aggregation pipeline to fetch game details and player information
        pipeline = [
            {"$match": {"_id": object_id}},  # Match the game by _id
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
                "$project": {
                    "_id": {"$toString": "$_id"},  # Convert _id to string
                    "player_id": 1,
                    "is_complete": 1,
                    "game_id": 1,
                    "end_time": 1,
                    "game_details": {
                        "game_id": 1,
                        "is_approved": 1,
                        "name": 1,
                        "description": 1,
                        "time_limit": 1,
                        "game_points": 1,
                        "assigned_severity": 1,
                        "game_url": 1,
                        "thumbnail": 1,
                        "walkthrough_file_url": 1
                    },
                    "player_details": {
                        "user_id": 1,
                        "user_full_name": 1,
                        "user_role": 1,
                        "user_avatar": 1,
                        "game_points": 1
                    }
                }
            }
        ]

        # Execute the aggregation pipeline and fetch the result
        played_game_cursor = web_based_game_started_collection.aggregate(pipeline)

        # Fetch the first game result or None if no result
        played_game = next(played_game_cursor, None)

        if not played_game:
            # If no game found, return an exception response
            return Response({"error": "No game found with the provided _id."}, status=status.HTTP_404_NOT_FOUND)

        if not played_game.get("player_id") == request.user.get('user_id'):
            return Response({"error": ["You are not authorized to access this content!"]}, status=status.HTTP_401_UNAUTHORIZED)

        # If game is found, return the details in the response
        return Response(played_game, status=status.HTTP_200_OK)
