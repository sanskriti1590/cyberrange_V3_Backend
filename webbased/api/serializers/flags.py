from bson import ObjectId
from django.utils import timezone
from rest_framework import serializers

from database_management.pymongo_client import web_based_game_collection, web_based_game_started_collection


class GameFlagSubmitSerializer(serializers.Serializer):
    payed_game_id = serializers.CharField(max_length=50, required=True)
    user_id = serializers.CharField(max_length=50, required=True)
    game_id = serializers.CharField(max_length=50, required=True)
    flag = serializers.CharField(max_length=1000, required=True)

    def validate_payed_game_id(self, value: str) -> str:
        """Ensure that the payed_game_id is valid and check the game status."""
        if not value:
            raise serializers.ValidationError("Payed game ID cannot be empty.")

        # Ensure the provided payed_game_id is a valid ObjectId
        try:
            object_id = ObjectId(value)
        except Exception:
            raise serializers.ValidationError("Invalid payed_game_id format.")

        # Check if the played game exists
        played_game = web_based_game_started_collection.find_one({"_id": object_id})
        if not played_game:
            raise serializers.ValidationError("The provided payed_game_id does not exist.")

        # Ensure the game is not completed
        if played_game.get('is_complete', False):
            raise serializers.ValidationError("You cannot submit flags for a completed game.")

        return value

    def validate_user_id(self, value: str) -> str:
        """Ensure the user_id is not empty and valid."""
        if not value:
            raise serializers.ValidationError("User ID cannot be empty.")
        return value

    def validate_game_id(self, value: str) -> str:
        """Ensure that the game exists in the database and the game_id is valid."""
        if not value:
            raise serializers.ValidationError("Game ID cannot be empty.")
        return value

    def validate(self, data):
        """Validate if the user has already rated the game and flag validity."""
        game_id = data.get('game_id')
        playing_game_id = data.get('payed_game_id')
        flag = data.get('flag')

        # Check if the game exists
        game_instance = web_based_game_collection.find_one({"game_id": game_id})
        if not game_instance:
            raise serializers.ValidationError({"error": ["Game ID does not exist in the database."]})

        # Check if the playing game exists and is valid
        playing_game = web_based_game_started_collection.find_one({
            "_id": ObjectId(playing_game_id),
            "is_complete": False
        })
        if not playing_game:
            raise serializers.ValidationError({"error": ["Invalid playing game ID."]})

        # Check if the flag has already been captured
        if flag in playing_game.get('flags', []):
            raise serializers.ValidationError({"error": ["Flag Already Captured!"]})

        # Ensure the flag is part of the game's possible flags
        if flag not in game_instance.get('flags', []):
            raise serializers.ValidationError({"error": ["Better Luck Next Time!"]})

        self.context['game_instance'] = game_instance
        self.context['playing_game'] = playing_game
        return data

    def create(self, validated_data: dict) -> dict:
        """Create a new game rating entry."""
        flag = validated_data.get('flag')
        playing_game_id = validated_data.get('payed_game_id')

        # Retrieve the context for game and playing game
        playing_game = self.context['playing_game']
        game_instance = self.context['game_instance']

        # Append flag to the list of flags for the playing game
        playing_game_flags = playing_game.get('flags', [])

        playing_game_flags.append(flag)

        # Check if all flags are captured
        if len(game_instance.get('flags', [])) == len(playing_game_flags):
            game_points = game_instance.get('game_points', 0)
            current_time = timezone.now()

            # Update the playing game to mark it as complete
            updated_instance = {
                "is_complete": True,
                "completed_at": current_time,
                "updated_at": current_time,
                "score": game_points,
            }
            web_based_game_started_collection.update_one(
                {"_id": ObjectId(playing_game_id)},
                {"$set": updated_instance}
            )

            return {
                "message": "Congratulations! All Flags Captured",
                "is_complete": True,
                "score": game_points,
            }

        # If not all flags are captured, just return an updated message
        web_based_game_started_collection.update_one(
            {"_id": ObjectId(playing_game_id)},
            {"$set": {"flags": playing_game_flags}}
        )

        return {
            "message": "Kudos! You Captured a Flag",
            "is_complete": False,
        }
