import os
from datetime import datetime

from django.utils import timezone
from rest_framework import serializers

from core.utils import generate_random_string, API_URL
from database_management.pymongo_client import web_based_category_collection
from webbased.utils import validate_image_format


class CategoryBaseSerializer(serializers.Serializer):
    category_id = serializers.CharField(default=generate_random_string('category_id', length=5), required=False, read_only=True)
    name = serializers.CharField(max_length=100, required=True)
    description = serializers.CharField(min_length=50, max_length=5000, required=False)
    # thumbnail = serializers.ImageField(required=False, write_only=True)
    thumbnail = serializers.ImageField(required=False, validators=[validate_image_format])  # Apply custom validator

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    @staticmethod
    def get_default_thumbnail_url():
        return f'{API_URL}/static/images/web_based_category_thumbnails/default.jpg'

    def validate_name(self, value):
        # Check that the category name is unique
        if web_based_category_collection.find_one({'name': value}):
            raise serializers.ValidationError("Category Name already exists, it must be unique. Try another name.")
        return value

    def validate_thumbnail(self, value):
        if not value:
            raise serializers.ValidationError('Please provide a thumbnail!')

        thumbnail_file_name, thumbnail_file_extension = os.path.splitext(value.name)

        # Validate file extension
        if thumbnail_file_extension.lower() not in ['.png', '.jpg', '.jpeg']:
            raise serializers.ValidationError("Thumbnail must be a PNG or JPG file.")

        return value

    def _handle_thumbnail(self, thumbnail_file, category_id):
        if thumbnail_file:
            thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)
            current_timestamp = str(datetime.now().timestamp()).split(".")[0]
            thumbnail_file_name = f"{category_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"

            # Store the file in the specified directory
            with open(f"static/images/web_based_category_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                for chunk in thumbnail_file.chunks():
                    destination.write(chunk)

            return f'{API_URL}/static/images/web_based_category_thumbnails/{thumbnail_file_name}'
        else:
            return self.get_default_thumbnail_url()

    def create(self, validated_data):
        thumbnail_url = self._handle_thumbnail(validated_data.pop("thumbnail", None), validated_data["category_id"])

        category_data = {
            "category_id": validated_data['category_id'],
            'name': validated_data['name'],
            'description': validated_data['description'],
            'thumbnail': thumbnail_url,
            "created_at": timezone.now(),  # Use the auto-generated timestamp
            "updated_at": timezone.now(),  # Use the auto-generated timestamp
        }

        web_based_category_collection.insert_one(category_data)
        category_data['_id'] = str(category_data['_id'])  # Convert ObjectId to string
        return category_data

    def update(self, category_id, validated_data):
        existing_category = web_based_category_collection.find_one({'category_id': category_id})
        if not existing_category:
            raise serializers.ValidationError("Category not found.")

        thumbnail = validated_data.get("thumbnail", None)
        thumbnail_url = None
        if thumbnail:
            # print(thumbnail)
            # thumbnail = validated_data.pop("thumbnail", None)
            thumbnail_url = self._handle_thumbnail(thumbnail, category_id)

        update_data = {
            'name': validated_data.get('name', existing_category['name']),
            'description': validated_data.get('description', existing_category['description']),
            "updated_at": timezone.now(),  # Use the auto-generated timestamp
        }
        if thumbnail_url is not None:
            update_data['thumbnail'] = thumbnail_url

        web_based_category_collection.update_one({"category_id": category_id}, {"$set": update_data})
        update_data['_id'] = str(existing_category['_id'])

        if not thumbnail_url:
            update_data['thumbnail'] = existing_category['thumbnail']
        return update_data

    @staticmethod
    def get(category_id):
        category = web_based_category_collection.find_one({'category_id': category_id})
        if not category:
            raise serializers.ValidationError("Category not found.")

        # Convert ObjectId to string and return the category
        category['_id'] = str(category['_id'])  # Convert ObjectId to string
        category['category_name'] = category['name']
        category['category_description'] = category['description']
        category['category_thumbnail'] = category['thumbnail']
        return category
