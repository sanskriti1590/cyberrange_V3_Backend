from bson import ObjectId
from django.utils import timezone
from pymongo.errors import PyMongoError
from rest_framework import serializers

from database_management.pymongo_client import web_based_game_ratings_collection, web_based_game_collection, web_based_game_started_collection


class GameRatingBaseSerializer(serializers.Serializer):
    played_game_id = serializers.CharField(max_length=50, required=True)
    user_id = serializers.CharField(max_length=50, required=True)
    game_id = serializers.CharField(max_length=50, required=True)
    stars = serializers.IntegerField(min_value=1, max_value=5, required=True)
    message = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)

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

        # Ensure the game is not active (completed)
        if not played_game.get('is_complete', False):
            raise serializers.ValidationError("You cannot provide feedback for an active game.")

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

        # Check if the game exists
        game = web_based_game_collection.find_one({"game_id": value})
        if not game:
            raise serializers.ValidationError("Game ID does not exist in the database.")

        return value

    def validate_stars(self, value: int) -> int:
        """Ensure that the star rating is between 1 and 5."""
        if not (1 <= value <= 5):  # More Pythonic range check
            raise serializers.ValidationError("Star rating must be an integer between 1 and 5.")
        return value

    def validate(self, data):
        """Validate if the user has already rated the game."""
        user_id = data.get('user_id')
        game_id = data.get('game_id')
        payed_game_id = data.get('payed_game_id')

        # Check if the user has already rated this game in MongoDB
        existing_rating = web_based_game_ratings_collection.find_one({
            "payed_game_id": payed_game_id,
            "user_id": user_id,
            "game_id": game_id
        })

        if existing_rating:
            raise serializers.ValidationError("You have already submitted a rating for this game.")

        return data

    def create(self, validated_data: dict) -> dict:
        """Create a new game rating entry."""
        game_id = validated_data.get("game_id")
        user_id = validated_data.get("user_id")

        # Ensure the game exists
        game = web_based_game_collection.find_one({"game_id": game_id})
        if not game:
            raise serializers.ValidationError("Game ID does not exist.")

        try:
            # Prepare the data for insertion into the database
            game_rating_data = {
                "payed_game_id": validated_data["payed_game_id"],
                "user_id": user_id,
                "game_id": game_id,
                "stars": validated_data["stars"],
                "message": validated_data.get("message", ""),
                "created_at": timezone.now(),  # Ensure the current UTC time is used
            }

            # Insert the new game rating data into the database
            result = web_based_game_ratings_collection.insert_one(game_rating_data)

            # Check if the insertion was successful
            if result.acknowledged:
                game_rating_data['_id'] = str(result.inserted_id)  # Convert ObjectId to string
                return game_rating_data  # Return the created game data
            else:
                raise serializers.ValidationError("Failed to create the game rating.")

        except PyMongoError as e:
            # Handle any MongoDB-specific errors
            raise serializers.ValidationError(f"Database error: {str(e)}")

        except Exception as e:
            # Handle any other unexpected errors
            raise serializers.ValidationError(f"Failed to create game rating: {str(e)}")
