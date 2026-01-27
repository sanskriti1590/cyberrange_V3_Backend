from datetime import datetime, timedelta

from bson import ObjectId
from rest_framework import serializers

from database_management.pymongo_client import (
    web_based_game_started_collection,
    web_based_game_collection,
    user_collection,
)
from webbased.tasks import check_and_complete_webbased_game


class GamePlayBaseSerializer(serializers.Serializer):
    """
    Serializer for starting a game. Validates player and game existence, and handles
    the creation of a game instance with appropriate checks for ongoing games.
    """
    game_id = serializers.CharField(max_length=100, required=True)
    player_id = serializers.CharField(min_length=1, max_length=5000, required=True)
    end_time = serializers.DateTimeField(read_only=True)
    is_complete = serializers.BooleanField(default=False)
    completed_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class GameStartSerializer(GamePlayBaseSerializer):
    def validate(self, attrs):
        game_id = attrs.get('game_id')
        player_id = attrs.get('player_id')
        current_time = datetime.now()

        # Validate game existence
        game = web_based_game_collection.find_one({"game_id": game_id})
        if not game:
            raise serializers.ValidationError({"error": "Game ID does not exist."})

        if not game.get("is_approved"):
            raise serializers.ValidationError({"error": "Game is not approved."})

        if not game.get("game_url"):
            raise serializers.ValidationError({"error": "Game URL cannot be empty."})

        # Validate player existence
        player = user_collection.find_one({"user_id": player_id})
        if not player:
            raise serializers.ValidationError({"error": "Player does not exist."})

        is_premium_user = player.get('is_premium')

        if game.get('is_for_premium_user') and not is_premium_user:
            raise serializers.ValidationError({"error": "This game is only for premium players."})

        played_game_count = web_based_game_started_collection.count_documents({"game_id": game_id, "player_id": player_id, "is_complete": True})

        if not is_premium_user:
            if played_game_count > 0:
                raise serializers.ValidationError({"error": "You’ve played this game already. Upgrade your membership to play again."})

            ongoing_game = web_based_game_started_collection.find_one({
                "player_id": player_id,
                "is_complete": False,
                "end_time": {"$gt": current_time},
            })
            if ongoing_game:
                raise serializers.ValidationError({"error": "This game has already been started by the player."})
        else:
            # elif is_premium_user and played_game_count >= 3:
            #     raise serializers.ValidationError({"error": "Game Limit Reached. Maximum of 3 games allowed. Close an active game to start a new one."})
            ongoing_game = web_based_game_started_collection.find_one({
                "game_id": game_id,
                "player_id": player_id,
                "is_complete": False,
                "end_time": {"$gt": current_time},
            })
            if ongoing_game:
                raise serializers.ValidationError({"error": "This game has already been started by the player."})

            ongoing_games_count = web_based_game_started_collection.count_documents({
                "player_id": player_id,
                "is_complete": False,
                "end_time": {"$gt": current_time},
            })
            if ongoing_games_count >= 3:
                raise serializers.ValidationError(
                    {"error": "Game Limit Reached. Maximum of 3 games allowed. Close an active game to start a new one."})

        # Store context for later use
        self.context['current_time'] = current_time
        self.context['game'] = game

        return attrs

    def create(self, validated_data):
        current_time = self.context['current_time']
        game = self.context['game']

        # Retrieve game-specific details
        game_id = validated_data.get('game_id')
        player_id = validated_data.get('player_id')

        # Set the end time based on the game's time limit (default 30 hours)
        time_limit = game.get('time_limit', 30)
        end_time = current_time + timedelta(hours=time_limit)

        # Print for debugging
        # print(f"Time Limit: {time_limit} hours")
        # print(f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        # print(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Create the new game instance
        new_instance = {
            "game_id": game_id,
            "player_id": player_id,
            "end_time": end_time,
            "is_complete": False,
            "is_timeout_completed": False,
            "completed_at": None,
            "score": 0,
            "flags": [],
            "created_at": current_time,
            "updated_at": current_time,
        }

        # Insert into the database
        result = web_based_game_started_collection.insert_one(new_instance)

        player_details = user_collection.find_one({"user_id": player_id}, {
            "_id": 0,
            "user_id": 1,
            "user_full_name": 1,
        })
        game_details = web_based_game_collection.find_one({"game_id": game_id}, {
            "_id": 0,
            "game_id": 1,
            "name": 1,
            "is_approved": 1,
            "thumbnail": 1,
            "description": 1,
            "assigned_severity": 1,
            "game_points": 1,
            "time_limit": 1
        })

        # Convert to ISO format strings for consistency
        new_instance['created_at'] = new_instance['created_at'].isoformat() + "Z"
        new_instance['updated_at'] = new_instance['updated_at'].isoformat() + "Z"
        new_instance['end_time'] = new_instance['end_time'].isoformat() + "Z"
        new_instance['player'] = player_details
        new_instance['game'] = game_details
        new_instance['_id'] = str(result.inserted_id)  # Convert ObjectId to string

        # Calculate countdown for the task
        countdown_seconds = (end_time - current_time).total_seconds()

        # Schedule task to check and complete the game
        check_and_complete_webbased_game.apply_async(
            args=[str(result.inserted_id)],
            countdown=countdown_seconds
        )

        return new_instance


class GameEndSerializer(GamePlayBaseSerializer):
    def validate(self, attrs):
        game_id = attrs.get('game_id')
        player_id = attrs.get('player_id')
        current_time = datetime.now()

        # Validate game existence
        game = web_based_game_collection.find_one({"game_id": game_id})
        if not game:
            raise serializers.ValidationError({"error": "Game ID does not exist."})

        if not game.get("is_approved"):
            raise serializers.ValidationError({"error": "Game is not approved."})

        if not game.get("game_url"):
            raise serializers.ValidationError({"error": "Game URL cannot be empty."})

        # Validate player existence
        player = user_collection.find_one({"user_id": player_id})
        if not player:
            raise serializers.ValidationError({"error": "Player does not exist."})

        # Store context for later use
        self.context['current_time'] = current_time
        self.context['game'] = game

        return attrs

    def update_data(self, ongoing_game, object_id, is_timeout_completed=False):
        """
        Update the game instance to mark it as complete (either manually or via timeout).
        """
        current_time = datetime.now()

        # Initialize the update dictionary with common fields
        updated_instance = {
            "is_complete": True,
            "completed_at": current_time,
            "updated_at": current_time,
        }

        if is_timeout_completed:
            updated_instance['is_timeout_completed'] = True

        # Update the game instance in the database
        web_based_game_started_collection.update_one(
            {"_id": object_id},
            {"$set": updated_instance}
        )

        if is_timeout_completed:
            raise serializers.ValidationError({"error": "This game has already been completed."})

        # Convert date fields to ISO format strings for consistency in the response
        updated_instance['completed_at'] = updated_instance['completed_at'].isoformat() + "Z"
        updated_instance['updated_at'] = updated_instance['updated_at'].isoformat() + "Z"

        ongoing_game['_id'] = str(ongoing_game['_id'])

        # Return the updated instance combined with the original game data
        return {**ongoing_game, **updated_instance}

    def update(self, game_started_id, validated_data):
        """
        Main method to handle updating the game. Checks for errors and updates
        game completion based on whether the game is completed manually or via timeout.
        """
        # Convert the game_started_id to ObjectId
        object_id = ObjectId(game_started_id)

        game_id = validated_data.get('game_id')
        player_id = validated_data.get('player_id')

        # Fetch the game instance from the database
        ongoing_game = web_based_game_started_collection.find_one({
            "_id": object_id,
            "game_id": game_id,
            "player_id": player_id,
        })

        # Check if the game exists
        if not ongoing_game:
            raise serializers.ValidationError({"error": ["Invalid game active ID."]})

        # Check if the game has already been completed
        if ongoing_game.get('is_complete'):
            raise serializers.ValidationError({"error": ["The game has already been completed."]})

        # Get the current time
        current_time = datetime.now()

        # Fetch the end_time from the database (assumed to be stored in UTC or any other timezone)
        end_time = ongoing_game.get('end_time')

        # Print for debugging
        # print(f"Current Time (UTC): {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        # print(f"End Time (UTC): {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Now compare the two times
        if current_time <= end_time:
            # The game is still within the time limit
            return self.update_data(ongoing_game, object_id)
        else:
            # The game has timed out
            return self.update_data(ongoing_game, object_id, is_timeout_completed=True)


class GamePlayersSerializer(serializers.Serializer):

    def list(self, game_id, player_id=None):
        """
        Fetch and return the list of players for a given game_id and optional player_id.
        Filters by game_id, player_id (optional), is_complete=True, and is_timeout_completed=False.
        """
        if not game_id:
            raise ValueError("Game ID is required.")

        # Define the query filters for the game collection (web_based_game_started_collection)
        query = {
            "game_id": game_id,  # Filter by game_id
            "is_complete": True,
            "is_timeout_completed": False,
        }

        if player_id:
            query["player_id"] = player_id  # Optionally filter by player_id

        try:
            # MongoDB aggregation pipeline to fetch active games and join with player details
            pipeline = [
                {"$match": query},  # Match games based on the provided query
                {
                    "$lookup": {
                        "from": "user_collection",  # The collection to join (user details)
                        "localField": "player_id",  # Field from the game collection (web_based_game_started_collection)
                        "foreignField": "user_id",  # Field in the user collection (user_collection)
                        "as": "player_details"  # Resulting array of player details
                    }
                },
                {
                    "$unwind": {
                        "path": "$player_details",  # Flatten the player details
                        "preserveNullAndEmptyArrays": False  # Don't keep empty player details
                    }
                },
                {
                    "$lookup": {
                        "from": "web_based_game_collection",  # Another collection to join (game details)
                        "localField": "game_id",  # Field from the game collection (web_based_game_started_collection)
                        "foreignField": "game_id",  # Field in the game collection (game_collection)
                        "as": "game_details"  # Resulting array of game details
                    }
                },
                {
                    "$unwind": {
                        "path": "$game_details",  # Flatten the game details
                        "preserveNullAndEmptyArrays": False  # Don't keep empty game details
                    }
                },
                {
                    "$project": {
                        "_id": {"$toString": "$_id"},  # Convert _id to string
                        "player_id": 1,
                        "is_complete": 1,
                        "score": 1,
                        "user_id": "$player_details.user_id",  # Flatten player details into the root document
                        "user_full_name": "$player_details.user_full_name",
                        "user_role": "$player_details.user_role",
                        "user_avatar": "$player_details.user_avatar",
                        "game_id": "$game_details.game_id",  # Include game_id from the game collection
                        "game_points": "$game_details.game_points",
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "player_id": "$player_id",  # Group by player_id
                            "game_id": "$game_id"  # Group by game_id
                        },
                        "is_complete": {"$first": "$is_complete"},  # Get the first value for other fields
                        "score": {"$first": "$score"},
                        "user_id": {"$first": "$user_id"},
                        "user_full_name": {"$first": "$user_full_name"},
                        "user_role": {"$first": "$user_role"},
                        "user_avatar": {"$first": "$user_avatar"},
                        "game_points": {"$first": "$game_points"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,  # Remove _id field from the output
                        "player_id": "$_id.player_id",  # Flatten player_id
                        "game_id": "$_id.game_id",  # Flatten game_id
                        "is_complete": 1,
                        "score": 1,
                        "user_id": 1,
                        "user_full_name": 1,
                        "user_role": 1,
                        "user_avatar": 1,
                        "game_points": 1,
                    }
                }
            ]

            # Fetch the games and their associated player details using the aggregation pipeline
            played_games = web_based_game_started_collection.aggregate(pipeline)

            # Convert the cursor to a list
            players = list(played_games)

            if not players:
                # If no players found, return an empty list
                return []

            return players

        except Exception as e:
            raise Exception(f"Error during aggregation: {str(e)}")


class ActiveGameSerializer(serializers.Serializer):
    """
    Serializer for active game data with detailed player information.
    This serializer handles fetching and serializing active game data,
    including player details (player information embedded as 'game').
    """

    @classmethod
    def get_active_games(cls, request):
        """
        Fetch and return all active (incomplete) games where `is_complete=False` and `is_timeout_completed=False`.
        Additionally, embeds game details in the response.
        """
        player_id = request.user.get('user_id')

        # Define the query filters to get active games
        query = {
            "is_complete": False,  # Filter documents where 'is_complete' is False
            "is_timeout_completed": False  # Also filter by 'is_timeout_completed' = False
        }
        if player_id:
            query["player_id"] = player_id

        # MongoDB aggregation pipeline to fetch active games and join with game details
        pipeline = [
            {"$match": query},
            {
                "$lookup": {
                    "from": "web_based_game_collection",  # The collection to join
                    "localField": "game_id",  # Field from the current collection
                    "foreignField": "game_id",  # Field from the game collection
                    "as": "game"  # Resulting array of game objects
                }
            },
            {
                "$unwind": "$game"  # Unwind the 'game' array to flatten the result
            },
            {
                "$lookup": {
                    "from": "web_based_category_collection",  # The collection for categories
                    "localField": "game.category_id",  # Field from 'game' document
                    "foreignField": "category_id",  # Field in the category collection
                    "as": "category"  # Resulting array of category objects
                }
            },
            {
                "$unwind": {
                    "path": "$category",  # Unwind the category array to flatten it
                    "preserveNullAndEmptyArrays": True  # Preserve games that don't have a category
                }
            },
            {
                "$project": {
                    "_id": {"$toString": "$_id"},  # Convert the '_id' to string
                    "player_id": 1,
                    "is_complete": 1,
                    "game": {
                        "game_id": 1,
                        "name": 1,
                        "is_approved": 1,
                        "thumbnail": 1,
                        "description": 1,
                        "assigned_severity": 1,
                        "game_points": 1,
                        "time_limit": 1,
                        "category_id": 1,
                        "category": {
                            "category_id": "$category.category_id",  # Flatten and include category_id from category collection
                            "category_name": "$category.name"  # Flatten and include category name from category collection
                        }
                    }
                }
            }
        ]

        # Fetch active games with game details using the aggregation pipeline
        active_games_cursor = web_based_game_started_collection.aggregate(pipeline)

        # Convert the cursor to a list
        active_games = list(active_games_cursor)

        return active_games

    @classmethod
    def get_serialized_data(cls, request):
        """
        Fetch the active games and return the serialized data with embedded game details.
        """
        active_games = cls.get_active_games(request=request)
        return active_games
