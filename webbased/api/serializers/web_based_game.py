import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from core.utils import generate_random_string, API_URL
from database_management.pymongo_client import web_based_game_collection, web_based_game_started_collection
from webbased.utils import validate_image_format


class WebBasedGameBaseSerializer(serializers.Serializer):
    """Base serializer for web-based game objects."""

    game_id = serializers.CharField(default=generate_random_string('game_id', length=5), required=False)
    is_approved = serializers.BooleanField(default=False)
    name = serializers.CharField(max_length=100, required=True)
    description = serializers.CharField(min_length=50, max_length=5000, required=True)

    rules_regulations_text = serializers.CharField(max_length=2000, required=True)
    flag_content_text = serializers.CharField(max_length=2000, required=True)
    thumbnail = serializers.ImageField(required=True, write_only=True, validators=[validate_image_format])  # Apply custom validator
    walkthrough_file = serializers.FileField(required=True, write_only=True)

    category_id = serializers.CharField(max_length=50, required=True)
    created_by = serializers.CharField(max_length=50, required=True)

    assigned_severity = serializers.ChoiceField(required=True, choices=[
        ("very_easy", "Very Easy"),
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
        ("very_hard", "Very Hard")
    ])

    game_points = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    time_limit = serializers.IntegerField(required=True)  # Assuming time limit is in hours
    game_url = serializers.URLField(required=False)
    is_for_premium_user = serializers.BooleanField(default=False)
    rated_severity = serializers.IntegerField(required=False)

    flags = serializers.CharField(max_length=500, required=True, write_only=True)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def validate_thumbnail(self, value):
        if not value:
            raise serializers.ValidationError('Please provide a thumbnail!')

        thumbnail_file_name, thumbnail_file_extension = os.path.splitext(value.name)

        # Validate file extension
        if thumbnail_file_extension.lower() not in ['.png', '.jpg', '.jpeg']:
            raise serializers.ValidationError("Thumbnail must be a PNG or JPG file.")

        return value

    def validate_time_limit(self, value):
        if value < 1:
            raise serializers.ValidationError("Time limit must be greater than or equal to 1.")
        return value

    @staticmethod
    def get_default_thumbnail_url() -> str:
        """Returns the default thumbnail URL."""
        return f'{API_URL}/static/images/web_based_game_thumbnails/default.jpg'

    def _handle_thumbnail(self, thumbnail_file, game_id: str) -> str:
        """Handles the uploading of the thumbnail file and returns its URL.

        If no thumbnail is provided, the default thumbnail URL is returned.

        Args:
            thumbnail_file: The uploaded thumbnail file.
            game_id: The unique identifier of the game.

        Returns:
            str: The URL of the uploaded thumbnail or the default thumbnail URL.
        """
        if thumbnail_file:
            # Generate a new filename for the thumbnail
            thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)
            current_timestamp = str(datetime.now().timestamp()).split(".")[0]
            thumbnail_file_name = f"{game_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"

            # Store the file in the specified directory
            with open(f"static/web_based_game/images/{thumbnail_file_name}", 'wb+') as destination:
                for chunk in thumbnail_file.chunks():
                    destination.write(chunk)

            return f'{API_URL}/static/web_based_game/images/{thumbnail_file_name}'
        else:
            return self.get_default_thumbnail_url()

    def _handle_walkthrough_file(self, walkthrough_file, game_id: str) -> str:
        """Handles the uploading of the walkthrough file and returns its URL.

        If no walkthrough file is provided, returns None.

        Args:
            walkthrough_file: The uploaded walkthrough file.
            game_id: The unique identifier of the game.

        Returns:
            str: The URL of the uploaded walkthrough file or None if not provided.
        """
        if walkthrough_file:
            # Generate a new filename for the walkthrough file
            walkthrough_file_name, walkthrough_file_extension = os.path.splitext(walkthrough_file.name)
            current_timestamp = str(datetime.now().timestamp()).split(".")[0]
            walkthrough_file_name = f"{game_id}_walkthrough_{current_timestamp}{walkthrough_file_extension.lower()}"

            # Store the file in the specified directory
            with open(f"static/web_based_game/files/{walkthrough_file_name}", 'wb+') as destination:
                for chunk in walkthrough_file.chunks():
                    destination.write(chunk)

            return f'{API_URL}/static/web_based_game/files/{walkthrough_file_name}'
        return None  # No walkthrough file provided

    def create(self, validated_data: dict) -> dict:
        """Creates a new web-based game.

        Args:
            validated_data: The validated data for creating a new game.

        Returns:
            dict: The created game data.
        """

        # Convert validated_data to a mutable dictionary if it's a QueryDict
        if hasattr(validated_data, 'dict'):
            validated_data = validated_data.dict()

        # Handle thumbnail file and get its URL
        thumbnail_url = self._handle_thumbnail(validated_data.pop("thumbnail", None), validated_data.get("game_id"))
        if thumbnail_url:
            validated_data['thumbnail'] = thumbnail_url
        walkthrough_file_url = self._handle_walkthrough_file(validated_data.pop("walkthrough_file", None), validated_data.get("game_id"))
        if walkthrough_file_url:
            validated_data['walkthrough_file_url'] = walkthrough_file_url

        # Validate and process flags
        flags = validated_data.get("flags")
        if flags:
            flags_list = [flag.strip() for flag in flags.split(',')]
            if len(flags_list) != len(set(flags_list)):
                raise serializers.ValidationError("Duplicate flags found. Modify the flags and try again.")
            validated_data['flags'] = flags_list  # Update to the cleaned list

        # Ensure game_points is a decimal and not an array
        game_points = validated_data.get("game_points")

        # If game_points is a list, take the first element
        if isinstance(game_points, list) and len(game_points) > 0:
            game_points = game_points[0]  # Take the first element if it's a list

        # Convert to Decimal
        try:
            game_points = Decimal(game_points)
        except (ValueError, InvalidOperation):
            raise ValueError("Invalid value for game_points; must be a valid decimal.")

        # Convert game_points to float for MongoDB
        game_points_float = float(game_points)

        # Prepare the data for insertion into the database
        game_id = validated_data.get("game_id")
        validated_data['game_id'] = game_id
        validated_data['game_points'] = game_points_float
        validated_data['created_at'] = datetime.now(),  # Set creation timestamp
        validated_data['updated_at'] = datetime.now()  # Set update timestamp

        # Insert the new game data into the database
        result = web_based_game_collection.insert_one(validated_data)

        return self.detailed_data(game_id=game_id)

    def update(self, game_id: str, validated_data: dict) -> dict:
        """Updates an existing web-based game with the provided data.

        This method fetches the current game instance using the game_id, processes any file uploads (thumbnail and walkthrough file),
        and updates the game attributes with either new validated data or existing values if not provided.

        Args:
            game_id (str): The unique identifier of the game to be updated.
            validated_data (dict): A dictionary containing the validated data for updating the game.

        Returns:
            dict: The updated game data, including the ObjectId converted to a string.
        """
        # Retrieve the existing game instance
        existing_instance = self.get(game_id=game_id)

        # Convert validated_data to a mutable dictionary if it's a QueryDict
        if hasattr(validated_data, 'dict'):
            validated_data = validated_data.dict()

        # Validate and process flags
        flags = validated_data.get("flags")
        if flags:
            flags_list = [flag.strip() for flag in flags.split(',')]
            if len(flags_list) != len(set(flags_list)):
                raise serializers.ValidationError("Duplicate flags found. Modify the flags and try again.")
            validated_data['flags'] = flags_list  # Update to the cleaned list

        # Handle thumbnail upload if provided
        thumbnail_file = validated_data.pop("thumbnail", None)
        if thumbnail_file:
            thumbnail_url = self._handle_thumbnail(thumbnail_file, game_id) if thumbnail_file else existing_instance['thumbnail']
            if thumbnail_url:
                validated_data["thumbnail"] = thumbnail_url

        # Handle walkthrough file upload if provided
        walkthrough_file = validated_data.pop("walkthrough_file", None)
        if walkthrough_file:
            walkthrough_file_url = self._handle_walkthrough_file(walkthrough_file, game_id) if walkthrough_file else existing_instance[
                'walkthrough_file']
            if walkthrough_file_url:
                validated_data["walkthrough_file"] = walkthrough_file_url

        # Ensure game_points is a decimal and not an array
        game_points = validated_data.get("game_points")
        if game_points:
            # If game_points is a list, take the first element
            if isinstance(game_points, list) and len(game_points) > 0:
                game_points = game_points[0]  # Take the first element if it's a list

            # Convert to Decimal
            try:
                game_points = Decimal(game_points)
            except (ValueError, InvalidOperation):
                raise ValueError("Invalid value for game_points; must be a valid decimal.")

            # Convert game_points to float for MongoDB
            game_points_float = float(game_points)
            validated_data['game_points'] = game_points_float

        # time_limit
        time_limit = validated_data.get("time_limit")
        if time_limit:
            validated_data["time_limit"] = int(time_limit)

        # Prepare the updated game data, falling back to existing values if necessary
        validated_data["updated_at"] = datetime.now()  # Update timestamp for the record

        # Update the game data in the database
        web_based_game_collection.update_one({"game_id": game_id}, {"$set": validated_data})

        # Convert the existing instance's ObjectId to string for the response
        # update_data['_id'] = str(existing_instance['_id'])
        return self.detailed_data(game_id=existing_instance['game_id'])

    @staticmethod
    def get(game_id: str, player_id=None) -> dict | None:
        """Retrieves a web-based game by its game_id.

        Args:
            game_id: The unique identifier of the game.
            player_id: user id.

        Returns:
            dict: The web-based game data.

        Raises:
            serializers.ValidationError: If the game is not found.
        """
        instance = web_based_game_collection.find_one({'game_id': game_id}, {"flags": 0})
        if not instance:
            return None

        # Convert ObjectId to string and return the web-based game
        instance['_id'] = str(instance['_id'])  # Convert ObjectId to string

        query = {
            'game_id': instance.get('game_id'),
            "is_complete": False,
        }
        if player_id:
            query["player_id"] = player_id
            ongoing_game = web_based_game_started_collection.find_one(query)
            instance['game_status'] = {
                'is_ready': True,
                '_id': str(ongoing_game.get('_id'))
            } if ongoing_game else None
        return instance

    @staticmethod
    def get_admin(game_id: str, player_id=None) -> dict | None:
        """Retrieves a web-based game by its game_id.

        Args:
            game_id: The unique identifier of the game.
            player_id: user id.

        Returns:
            dict: The web-based game data.

        Raises:
            serializers.ValidationError: If the game is not found.
        """
        instance = web_based_game_collection.find_one({'game_id': game_id})
        if not instance:
            return None

        # Convert ObjectId to string and return the web-based game
        instance['_id'] = str(instance['_id'])  # Convert ObjectId to string

        query = {
            'game_id': instance.get('game_id'),
            "is_complete": False,
        }
        if player_id:
            query["player_id"] = player_id
            ongoing_game = web_based_game_started_collection.find_one(query)
            instance['game_status'] = {
                'is_ready': True,
                '_id': str(ongoing_game.get('_id'))
            } if ongoing_game else None
        return instance

    @staticmethod
    def detailed_data(game_id):
        all_items = web_based_game_collection.find_one(
            {"game_id": game_id},  # Use the constructed query for filtering
            {
                "_id": 0,  # Exclude the MongoDB ObjectId from the results
                "game_id": 1,
                "is_approved": 1,
                "name": 1,
                "description": 1,
                "flag_content_text": 1,
                "rules_regulations_text": 1,
                "category_id": 1,
                "created_by": 1,
                "thumbnail": 1,
                "walkthrough_file": 1,
                "assigned_severity": 1,
                "game_points": 1,
                "time_limit": 1,
                "game_url": 1,
                "is_for_premium_user": 1,
                "rated_severity": 1,
                "flags": 1,
            }
        )
        return dict(all_items)  # Convert the cursor to a list and return


class WebBasedGameCreateSerializer(WebBasedGameBaseSerializer):
    """Serializer for creating a web-based game."""

    def create(self, validated_data: dict) -> dict:
        """Creates a new web-based game with an auto-generated game_id.

        Args:
            validated_data: The validated data for creating a new game.

        Returns:
            dict: The created game data.
        """
        # Auto-generate game_id
        validated_data['game_id'] = generate_random_string('game_id', length=5)
        return super().create(validated_data)


class WebBasedGameListSerializer(serializers.Serializer):
    """Serializer for listing web-based games with detailed attributes."""

    def get_all_games(self, category_id=None, is_approved=None):
        """Retrieve all web-based games with basic details.

        This method queries the database for web-based games, filtering by
        approval status and optional category ID. It returns a list of games
        with their key details.

        Args:
            category_id (str, optional): The ID of the category to filter games by.
                                          If not provided, all categories are included.
            is_approved (bool, optional): Indicates whether to filter games based
                                           on their approval status. If not provided,
                                           all games (approved and unapproved) are included.

        Returns:
            list: A list of dictionaries containing the details of all games
                  that match the query. Each dictionary contains:
                      - game_id (str): The unique identifier for the game.
                      - name (str): The name of the game.
                      - is_approved (bool): The approval status of the game.
                      - thumbnail (str): The URL of the game's thumbnail image.
                      - description (str): A brief description of the game.
                      - assigned_severity (int): The severity assigned to the game.
                      - game_points (int): The points associated with the game.
                      - time_limit (int): The time limit for the game (if applicable).
                      # - created_at (datetime): The timestamp when the game was created.
                      # - updated_at (datetime): The timestamp when the game was last updated.
        """
        query = {}

        if is_approved is not None:
            query['is_approved'] = is_approved  # Add filter for approval status if provided

        if category_id is not None:
            query['category_id'] = category_id  # Add filter for category_id if provided

        all_items = web_based_game_collection.find(
            query,  # Use the constructed query for filtering
            {
                "_id": 0,  # Exclude the MongoDB ObjectId from the results
                "game_id": 1,
                "name": 1,
                "is_approved": 1,
                "thumbnail": 1,
                "description": 1,
                "assigned_severity": 1,
                "game_points": 1,
                "time_limit": 1,
                # "created_at": 1,
                # "updated_at": 1,
            }
        )

        # Convert the cursor to a list
        all_items = list(all_items)
        return all_items

    def get_all_approved_games(self, category_id=None):
        """Retrieve all approved web-based games, optionally filtered by category.

        This method calls _get_games to return only the games that have been
        approved, optionally filtering by category ID.

        Args:
            category_id (str, optional): The ID of the category to filter games by.
                                          If not provided, all categories are included.

        Returns:
            list: A list of dictionaries containing the details of all approved games
                  that match the query.
        """
        return self.get_all_games(category_id=category_id, is_approved=True)


class ToggleWebBasedGameApprovalSerializer(serializers.Serializer):
    """Serializer for toggling the approval status of a web-based game."""

    game_id = serializers.CharField(required=True)

    def validate(self, attrs):
        """Validation to check if the game exists and has a URL."""

        game_id = attrs.get('game_id')

        # Retrieve the existing game
        existing_game = self.get(game_id=game_id)

        # Check if the game has a URL
        if not existing_game.get('game_url'):
            raise serializers.ValidationError("You can't approve this game because it does not have a URL.")

        # Store existing game in the context for later use
        self.context['existing_game'] = existing_game
        return attrs

    @staticmethod
    def get(game_id: str) -> dict:
        """Retrieves a web-based game by its game_id.

        Args:
            game_id: The unique identifier of the game.

        Returns:
            dict: The web-based game data.

        Raises:
            serializers.ValidationError: If the game is not found.
        """
        instance = web_based_game_collection.find_one({'game_id': game_id})
        if not instance:
            raise serializers.ValidationError("Web-based game not found.")

        # Convert ObjectId to string and return the web-based game
        instance['_id'] = str(instance['_id'])  # Convert ObjectId to string
        return instance

    def toggle_approval_status(self) -> dict:
        """Toggles the approval status of the game based on the validated game_id.

        Raises:
            ValidationError: If the game is not found.

        Returns:
            dict: The updated game data after toggling the approval status.
        """
        existing_game = self.context['existing_game']

        # Toggle the approval status
        new_approval_status = not existing_game.get('is_approved', False)

        # Update the game in the database with the new approval status
        update_data = {"is_approved": new_approval_status}
        web_based_game_collection.update_one({"game_id": existing_game['game_id']}, {"$set": update_data})

        # Retrieve and return the updated game data
        updated_game = self.get(game_id=existing_game['game_id'])  # Reusing the get method to fetch updated data
        return updated_game
