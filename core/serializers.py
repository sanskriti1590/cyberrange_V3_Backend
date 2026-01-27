import datetime
import requests
import pymongo

from rest_framework import serializers
from core.utils import  is_email_valid
from database_management.pymongo_client import (
    email_collection,
    user_collection,
    ctf_game_collection,
    scenario_collection,
    news_collection,
)
from cloud_management.utils import (
    get_instance_images, 
    get_instance_flavors,
)

from .utils import NEWS_API_KEY


class MailingListSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=100)

    def validate(self, data):
        email = data.get('email')

        if email_collection.find_one({'email': email}):
            raise serializers.ValidationError("You are already on our Mailing List.")
        
        if not is_email_valid(email):
            raise serializers.ValidationError("Invalid Email Id. Enter a valid email id.")
    
        return data

    def create(self, validated_data):        
        # Store the user information in MongoDB
        email = {
            "email": validated_data["email"],
        }
        email_collection.insert_one(email)

        return email
    

class InstanceEssentialsSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def get(self):

        images_list, flavors_list = [], []
        for image in get_instance_images():
            images_list.append({
                "image_id": image[0],
                "image_name": image[1]
            })
            
        for flavor in get_instance_flavors():
            flavors_list.append({
                "flavor_id": flavor[0],
                "flavor_name": flavor[1]
            })

        response = {
            "images" : images_list,
            "flavors": flavors_list
        }
        
        return response
    
class TotalResourcesSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def get(self):
        user_collection_count = user_collection.count_documents({})
        ctf_game_collection_count = ctf_game_collection.count_documents({})
        scenario_collection_count = scenario_collection.count_documents({'scenario_is_approved': True})

        response = {
            "total_members" : user_collection_count + 800,
            "total_ctf" : ctf_game_collection_count,
            "total_scenario" : scenario_collection_count
        }


        return response


class NewsListSerializer(serializers.Serializer):
    def get(self):
        return []
