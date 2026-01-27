import datetime
import os

from rest_framework import serializers
from core.utils import generate_random_string, API_URL

from database_management.pymongo_client import (
    ctf_game_collection,
    scenario_collection,
    challenge_game_collection,
)
from ctf_management.utils import validate_file_size

class GameChallengedListSerializer(serializers.Serializer):
    def get(self,game_type):
        if game_type not in ["ctf","scenario"]:
            return {"errors": {"non_field_errors": ["Invalid Game Type."]}}
    
        if game_type == "ctf":
            return list(ctf_game_collection.find({"ctf_is_challenge":True},{"_id":0,"ctf_id":1,"ctf_name":1,"ctf_description":1,"ctf_thumbnail":1,"type":"ctf"}))
        else:
            return list(scenario_collection.find({"scenario_is_challenge":True},{"_id":0,"scenario_id":1,"scenario_name":1,"scenario_description":1,"scenario_thumbnail":1,"type":"scenario"}))
        

class GameChallengeSerializer(serializers.Serializer):
    game_type = serializers.CharField(required=True)
    ctf_or_scenario_id = serializers.CharField(required=True)
    challenge_thumbnail = serializers.FileField(required=True, validators=[validate_file_size])

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data 
    
    def get(self):
        ctf_challenges_list = list(challenge_game_collection.find({},{"_id":0}))      
        return ctf_challenges_list

    def validate(self, data):
        if data["game_type"] not in ["ctf", "scenario"]:
            raise serializers.ValidationError("Invalid Game Type.") 
        
        if not data['challenge_thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png', 'webp')):
            raise serializers.ValidationError("Unsupported file format. Only jpeg, jpg ,webp and png are allowed.")
    
        
        if data["game_type"] == "ctf":
            if not ctf_game_collection.find_one({"ctf_id":data["ctf_or_scenario_id"]}):
                raise serializers.ValidationError("Invalid CTF Id.")

            if ctf_game_collection.find_one({"ctf_id":data["ctf_or_scenario_id"],"ctf_is_challenge":True}):
                raise serializers.ValidationError("Already a Challenge.")
            
            if ctf_game_collection.find_one({"ctf_id":data["ctf_or_scenario_id"],"ctf_is_approved":False}):
                raise serializers.ValidationError("CTF under inspection, can't make it a challenge now.")

        else:
            if not scenario_collection.find_one({"scenario_id":data["ctf_or_scenario_id"]}):
                raise serializers.ValidationError("Invalid Scenario Id.")

            if scenario_collection.find_one({"scenario_id":data["ctf_or_scenario_id"],"scenario_is_challenge":True}):
                raise serializers.ValidationError("Already a Challenge.")
            
            if scenario_collection.find_one({"scenario_id":data["ctf_or_scenario_id"],"scenario_is_approved":False}):
                raise serializers.ValidationError("Scenario under inspection, can't make it a challenge now.")

            
            
        return data

    def create(self, validated_data):
        # For generating unique random Challenge Id
        challenge_id = generate_random_string('challenge_id', length=8)
        current_date = datetime.datetime.now()
        current_timestamp = str(current_date.timestamp()).split(".")[0]

        if validated_data["game_type"] == "ctf":
            ctf_game_collection.update_one({"ctf_id":validated_data["ctf_or_scenario_id"]},{"$set":{
                "ctf_is_challenge": True
            }})
        else:
            scenario_collection.update_one({"scenario_id":validated_data["ctf_or_scenario_id"]},{"$set":{
                "scenario_is_challenge": True
            }})

        # For Thumbnail
        if validated_data.get('challenge_thumbnail'):
            # Get file name and extension
            thumbnail_file = validated_data.pop('challenge_thumbnail', None)
            thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)

            # Rename the file
            thumbnail_file_name = f"{validated_data['game_type']}_{challenge_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"
            # Store the file in the specified directory
            with open(f"static/images/challenge_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                for chunk in thumbnail_file.chunks():
                    destination.write(chunk)

            thumbnail_url = f'{API_URL}/static/images/challenge_thumbnails/{thumbnail_file_name}'
        
        
        # Store the user information in MongoDB
        challenge = {
            "challenge_id": challenge_id,
            "ctf_or_scenario_id": validated_data["ctf_or_scenario_id"],
            "game_type": validated_data["game_type"],
            "challenge_thumbnail": thumbnail_url,
            "challenge_created_by": self.context['request'].user['user_id'],
            "created_at": current_date,
            "updated_at": current_date
        }

        challenge_game_collection.insert_one(challenge)
        del challenge["_id"]

        return challenge
    
class GameChallengeDeleteserializer(serializers.Serializer):
    def validate(self, data):
        ctf_or_scenario_id = self.context['view'].kwargs.get('ctf_or_scenario_id')
        # user = self.context['request'].user  
        challenge = challenge_game_collection.find_one({'ctf_or_scenario_id': ctf_or_scenario_id})

        if not challenge:
            raise serializers.ValidationError("Invalid ID.")
        
        data["challenge_game"] = challenge

        return data 

    def create(self, validated_data):

        file_path = validated_data["challenge_game"]["challenge_thumbnail"].split("static")[1] if "default.jpg" not in  validated_data["challenge_game"]["challenge_thumbnail"].split("static")[1] else None
        if os.path.exists(f"static{file_path}"):
            os.remove(f"static{file_path}")

        if validated_data["challenge_game"]["game_type"] == "ctf":
            ctf_game_collection.update_one({"ctf_id":validated_data["challenge_game"]["ctf_or_scenario_id"]},{"$set":{
                "ctf_is_challenge": False
            }})
        else:
            scenario_collection.update_one({"scenario_id":validated_data["challenge_game"]["ctf_or_scenario_id"]},{"$set":{
                "scenario_is_challenge": False
            }})

        challenge_game_collection.delete_one({"ctf_or_scenario_id":validated_data["challenge_game"]["ctf_or_scenario_id"]})
        
        return {}
        
