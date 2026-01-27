import os

from rest_framework import serializers

from core.utils import generate_random_string
from database_management.pymongo_client import web_based_category_collection, web_based_game_collection
from webbased.api.serializers.base import CategoryBaseSerializer


class CategoryCreateSerializer(CategoryBaseSerializer):
    """Serializer for creating categories."""
    category_id = serializers.CharField(default=generate_random_string('category_id', length=5), required=False)


    def validate_category_id(self, value):
        if not value:
            raise serializers.ValidationError('category_id cannot be empty.')

        # Loop until we find a unique category_id
        while True:
            # Fetch the count of games for the given category_id
            games_count = web_based_game_collection.count_documents({'category_id': value})
            if games_count == 0:
                # If no games exist with this category_id, it's unique
                break
            else:
                # If there's already a game with this category_id, generate a new one
                value = generate_random_string('category_id', length=5)

        return value

    def create(self, validated_data):
        return super().create(validated_data)


class CategoryUpdateSerializer(CategoryBaseSerializer):
    """Serializer for updating categories."""

    def update(self, category_id, validated_data):
        return super().update(category_id, validated_data)


class CategoryListSerializer(CategoryBaseSerializer):
    """Serializer for listing categories."""

    def to_representation(self, instance):
        """Override to represent categories in a specific format."""
        representation_data = super().to_representation(instance)  # Get the base representation
        representation_data['games_count'] = self.get_games_count(instance)  # Add games count
        representation_data['thumbnail'] = instance['thumbnail']
        return representation_data

    @staticmethod
    def get_all_categories():
        """Retrieve all categories with basic details, newest first."""
        categories = web_based_category_collection.find(
            {},
            {
                "_id": 0, "category_id": 1, "name": 1, "thumbnail": 1, "description": 1,
                "created_at": 1, "updated_at": 1
            }
        ).sort("created_at", -1)  # Sort by 'created_at' field in descending order
        return list(categories)  # Convert cursor to list

    def get_games_count(self, instance):
        """Retrieve the games count for a specific category."""
        # Fetch the count of games for the given category_id
        games_count = web_based_game_collection.count_documents({'category_id': instance['category_id']})
        return games_count
