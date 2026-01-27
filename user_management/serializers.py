import datetime
import hashlib
import os
import re
import random

from rest_framework import serializers
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from asgiref.sync import async_to_sync

from core.utils import generate_random_string, API_URL, is_email_valid
from scenario_management.utils import convert_score
from database_management.pymongo_client import (
    user_collection,
    user_profile_collection,
    otp_hash_collection,
    blacklisted_token_collection,
    ctf_game_collection,
    ctf_player_arsenal_collection,
    ctf_category_collection,
    scenario_player_arsenal_collection,
    scenario_collection,
    archive_participant_collection,
)

from .authentications import CustomRefreshToken
from .encryption import cipher_suite
from .utils import ( 
    generate_access_token_payload,
    get_user_from_refresh_token,
    generate_otp,
    send_otp_by_sms,
    send_otp_by_email,
    USER_ROLES
)





# Define User serializer
class UserRegisterSerializer(serializers.Serializer):
    user_full_name = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=100)
    mobile_number = serializers.IntegerField()
    user_avatar = serializers.URLField(max_length=200, default = f'{API_URL}/static/images/user_avatars/avatar_{random.randint(1, 23)}.png')
    user_role = serializers.ChoiceField(choices=USER_ROLES)
    password = serializers.CharField(max_length=255, write_only=True)
    confirm_password = serializers.CharField(max_length=255, write_only=True)


    def validate(self, data):
        email = (data.get('email')).lower()
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        mobile_number = data.get('mobile_number')
        user_avatar = data.get('user_avatar')

        # Check that name contains only alphabets, digits, and spaces
        if not data['user_full_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Full Name can only contain alphabets, digits, and spaces.")

        if user_collection.find_one({'email': email}):
            raise serializers.ValidationError("Email address is already registered. Please provide another email address.")
        
        if not is_email_valid(email):
            raise serializers.ValidationError("Invalid Email Id. Enter a valid email id.")
        
        if len(str(data['mobile_number'])) != 10: 
            raise serializers.ValidationError("Invalid mobile number. Enter a valid mobile number.")
        
        if user_collection.find_one({'mobile_number': mobile_number}):
            raise serializers.ValidationError("Mobile number is already registered. Enter a valid mobile number.")

        validate_password(password)

        if password != confirm_password:
            raise serializers.ValidationError("Password and Confirm Password does not match. Enter passwords again.")
        
        # User Avatar URL Validation here
        if data.get('user_avatar'):
            directory = "static/images/user_avatars/"
            input_file_name = data.get('user_avatar').split("/")[-1]
            file_path = os.path.join(directory, input_file_name)
    
            if os.path.isfile(file_path):
                data['user_avatar'] = f'{API_URL}/static/images/user_avatars/{input_file_name}'
            else:
                data['user_avatar'] = f'{API_URL}/static/images/user_avatars/avatar_{random.randint(1, 23)}.png'
    
        return data

    def create(self, validated_data):
        validated_data['password'] = make_password(password = validated_data.get('password'))

        # Encrypt the password
        encrypted_password = cipher_suite.encrypt(validated_data["password"].encode())

        # For generating unique random User Id
        user_id = generate_random_string('user_id', length=10)
        
        current_time = datetime.datetime.now()

        # Store the user information in MongoDB
        user = {
            "user_id": user_id,
            "user_full_name": validated_data["user_full_name"],
            "mobile_number" : validated_data["mobile_number"],
            "email": validated_data["email"],
            "user_avatar": validated_data["user_avatar"],
            "user_role": validated_data["user_role"],
            "password": encrypted_password.decode(),
            "is_active": True,
            "is_premium": False,
            "is_verified": False,
            "is_admin": False,
            "is_superadmin": False,
            "created_at": current_time,
            "updated_at": current_time
        }
        user_collection.insert_one(user)

        user_profile = {
            "user_id": user_id,
            "user_bio": "",
            "user_ctf_score": 0,
            "user_scenario_score": 0,
            "user_badges_earned": [],
            "user_profile_liked_by": [],
            "user_profiles_liked": [],
            "assigned_games": {
                "ctf": [],
                "display_all_ctf": True,
                "scenario": [],
                "display_all_scenario": True,
                "corporate": [],
                "display_all_corporate":True,
                "display_locked_ctf": False,
                "display_locked_scenario": False,
                "display_locked_corporate": False
            },
            "user_profile_created_at": current_time,
            "user_profile_updated_at": current_time
        }
        user_profile_collection.insert_one(user_profile)

        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=100, write_only=True)
    password = serializers.CharField(max_length=255, write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        user = user_collection.find_one({'email': email})
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        
        # Decrypt the stored password and compare with the provided password
        stored_password = cipher_suite.decrypt(user['password'].encode()).decode()
        if check_password(password, stored_password):
            data['user'] = user
            return data
        else:
            raise serializers.ValidationError("Invalid credentials")
        
    def create(self, validated_data):
        refresh = CustomRefreshToken.for_user(validated_data['user'])
        refresh_token = str(refresh)
        access_token = str(refresh.access_token)
        new_access_token = generate_access_token_payload(access_token)

        response = {
                'access_token': new_access_token,
                'refresh_token': refresh_token
        }

        return response    


class CustomTokenRefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(max_length=500, write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        # Check if refresh token is blacklisted
        if blacklisted_token_collection.find_one({'token': data['refresh_token']}):
            raise serializers.ValidationError("Expired Token.")   

        user = get_user_from_refresh_token(data['refresh_token'])
        return data
    
    def create(self, validated_data):
        # Updating Database
        blacklisted_refresh_token = {
            'token': validated_data['refresh_token']
        }
        blacklisted_token_collection.insert_one(blacklisted_refresh_token)

        # Generating New Token
        # refresh = CustomRefreshToken.for_user(self.context['request'].user)
        refresh = CustomRefreshToken.for_user({"refresh":validated_data['refresh_token']})

        refresh_token = str(refresh)
        access_token = str(refresh.access_token)
        new_access_token = generate_access_token_payload(access_token)

        response = {
                'access_token': new_access_token,
                'refresh_token': refresh_token
        }

        return response
    

class SendOTPSerializer(serializers.Serializer):
    mobile_number = serializers.IntegerField(required=False)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        
        if data.get('mobile_number'):
            if len(str(data['mobile_number'])) != 10: 
                raise serializers.ValidationError("Invalid mobile number. Enter a valid mobile number.")
            
            if user_collection.find_one({'mobile_number': data['mobile_number']}):
                raise serializers.ValidationError("Mobile number is already registered. Enter a valid mobile number.")
            
        data['user'] = self.context['request'].user
        if not data['user']:
            raise serializers.ValidationError("Invalid User ID.")

        if data['user'].get("is_verified") == True:
            raise serializers.ValidationError("You are already verified.")

        otp_hash_obj = otp_hash_collection.find_one({"user_id": data["user"].get('user_id')})
        if otp_hash_obj:
            raise serializers.ValidationError("OTP has already been sent. If not received, please try again after 10 minutes.")
        
        return data
    
    def create(self, validated_data):
        user_obj  = validated_data['user']
        user_name_data = user_collection.find_one({"user_id": user_obj['user_id']},{"_id":0,"user_full_name":1})
        if validated_data.get('mobile_number'):
            mobile_number = validated_data.get('mobile_number')
            user_collection.update_one({"user_id": user_obj['user_id']}, { "$set": {"mobile_number": mobile_number, "updated_at": datetime.datetime.now()}})
        else:
            mobile_number = user_obj.get('mobile_number')

        otp, otp_hash = generate_otp()
                
        send_otp_by_sms(mobile_number, otp)
        send_otp_by_email.delay(user_obj['email'], otp, user_name_data.get("user_full_name", "Friend"))

        otp_details = {
            "user_id": user_obj['user_id'],
            "otp_hash": otp_hash, 
            "created_at": datetime.datetime.now()            
        }
        otp_hash_collection.insert_one(otp_details)

        return {}


class VerifyOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        data['user'] = self.context['request'].user                
        if not data['user']:
            raise serializers.ValidationError("Invalid User ID.")
        
        if data['user'].get('is_verified') == True:
            raise serializers.ValidationError("You are already verified.")
        
        if len(str(data['otp'])) != 6: 
            raise serializers.ValidationError("Invalid OTP")
        
        otp_hash_obj = otp_hash_collection.find_one({"user_id": data["user"].get('user_id')})
        if not otp_hash_obj:
            raise serializers.ValidationError("OTP Expired! Resend OTP and try again.")
        
        data['otp_hash'] = otp_hash_obj
        
        return data

    def create(self, validated_data):
        otp_hash_obj= validated_data['otp_hash']
        
        otp = validated_data['otp']
        otp_hash = hashlib.md5(otp.encode()).hexdigest()
        
        user_id = validated_data["user"].get('user_id')
        
        if otp_hash == otp_hash_obj["otp_hash"]:
            user_collection.update_one({"user_id": user_id}, 
                { "$set": {
                    "is_verified": True,
                    "updated_at": datetime.datetime.now()
                    }
            })
            otp_hash_collection.delete_one({"user_id": user_id})
        else:
            error_msg = {
                "errors": { "non_field_errors": ["Invalid OTP"]}
            }
            return error_msg
        
        refresh = CustomRefreshToken.for_user(validated_data['user'])
        refresh_token = str(refresh)
        access_token = str(refresh.access_token)
        new_access_token = generate_access_token_payload(access_token)

        response = {
                'access_token': new_access_token,
                'refresh_token': refresh_token
        }

        return response


class UserAvatarSerializer(serializers.Serializer):

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data  

    def get(self):
        avatar_dir = os.path.join(settings.STATICFILES_DIRS[0], 'images', 'user_avatars')
        avatar_url_list = []

        # Get a list of all avatar image files in the directory
        for file_name in os.listdir(avatar_dir):
            if file_name.endswith('.png'):
                filename = os.path.join(settings.STATICFILES_DIRS[0], 'images', 'user_avatars', file_name)
                file_url = f"{API_URL}/static/images/user_avatars/{file_name}"
                avatar_url_list.append(file_url)
                            
        return {"user_avatar_list": avatar_url_list}
    

class UnverifiedUserDetailSerializer(serializers.Serializer):
    def validate(self, user_id):
        user_obj = user_collection.find_one({'user_id': user_id}, {"user_id": 1, "mobile_number": 1, "email": 1, "_id": 0})

        if not user_obj:
            error_msg = {
                "errors": { "non_field_errors": ["Invalid Token"]}
            }
            return error_msg
                                
        return user_obj 

    def get(self, user_id):
        validated_data = self.validate(user_id)
        
        if "errors" in validated_data.keys():
            return validated_data
        else:
            user = validated_data

        user['mobile_number'] = re.sub(r'\d(?=\d{4})', 'X', str(user["mobile_number"]))
        
        email_starting, email_ending = user["email"].split("@")
        email_starting = email_starting[0] + ("*" * (len(email_starting) - 2)) + email_starting[-1]
        domain_name, domain_extension = email_ending.split(".") 
        domain_name = domain_name[0] + ("*" * (len(domain_name) - 2)) + domain_name[-1]
        user['email'] =  email_starting + "@" + domain_name + "." + domain_extension
                
        return user
    

class UserDetailSerializer(serializers.Serializer):
    def validate(self, user, params_user_id):
        if not isinstance(user, AnonymousUser) and user['user_id'] == params_user_id:
            user_obj = user_collection.find_one({'user_id': params_user_id}, {'_id': 0, 'password': 0})
        else:
            user_obj = user_collection.find_one({'user_id': params_user_id}, {
                '_id': 0,
                'user_id': 1, 
                'user_full_name': 1,
                'user_avatar': 1,
                'user_role': 1,
                'is_active': 1,
                'created_at': 1,
            })

        if not user_obj:
            error_msg = {
                "errors": { "non_field_errors": ["Invalid User ID"]}
            }
            return error_msg
                                
        return user_obj 

    def get(self, user, params_user_id):  
        validated_data = self.validate(user, params_user_id)
        if "errors" in validated_data.keys():
            return validated_data
        else:
            user = validated_data
            response = user
        
        user_profile = user_profile_collection.find_one({'user_id': user['user_id']}, {'_id': 0, "assigned_games":0})
        response.update(user_profile)
        
        ctf_games = ctf_game_collection.find({'ctf_creator_id': user['user_id']}, {
            '_id': 0, 
            'ctf_mapping_id': 0,
            'ctf_target_machine_name': 0,
            'ctf_attacker_machine_name': 0,
            'ctf_target_uploaded': 0,
        })
        temp_list = []
        for ctf_game in ctf_games:
            ctf_flag_list = ctf_game.pop('ctf_flags', None)
            ctf_game['ctf_total_flags'] = len(ctf_flag_list)


            ctf_category = ctf_category_collection.find_one({'ctf_category_id': ctf_game['ctf_category_id']}, {'_id': 0})
            ctf_game['ctf_category_name'] = ctf_category['ctf_category_name']
            ctf_game['ctf_category_description'] = ctf_category['ctf_category_description']
            ctf_game['ctf_category_thumbnail'] = ctf_category['ctf_category_thumbnail']
            
            temp_list.append(ctf_game)
        response['ctf_created'] = temp_list
        
        ctf_player_arsenals = ctf_player_arsenal_collection.find({'user_id': user['user_id']}, {
            '_id': 0,
            'ctf_archive_game_list': 0,
            'created_at': 0,
            'updated_at': 0,
        })
        temp_list = []
        for arsenal in ctf_player_arsenals:
            ctf_game_last_played = arsenal.pop('ctf_arsenal_updated_at', None)
            arsenal['ctf_game_last_played'] = ctf_game_last_played

            ctf_game = ctf_game_collection.find_one({'ctf_id': arsenal['ctf_id']}, {
                '_id': 0, 
                'ctf_mapping_id': 0,
                'ctf_target_machine_name': 0,
                'ctf_attacker_machine_name': 0,
                'ctf_target_uploaded': 0,
            })
            arsenal['ctf_total_flags'] = len(ctf_game['ctf_flags'])
            arsenal['ctf_flags_captured'] = len(arsenal['ctf_flags_captured'])
            arsenal['ctf_name'] = ctf_game['ctf_name']


            ctf_category = ctf_category_collection.find_one({'ctf_category_id': ctf_game['ctf_category_id']}, {'_id': 0})
            arsenal['ctf_category_name'] = ctf_category['ctf_category_name']
            arsenal['ctf_category_description'] = ctf_category['ctf_category_description']
            arsenal['ctf_category_thumbnail'] = ctf_category['ctf_category_thumbnail']

            temp_list.append(arsenal)
        response['ctf_played'] = temp_list

        return response
    

class UserListSerializer(serializers.Serializer):
    def get(self):
        users = user_collection.find({}, {
            '_id': 0, 
            'user_id': 1,
            'user_full_name': 1,
            'user_avatar': 1,
            'user_role': 1,
            'is_active': 1,
            'created_at': 1,
        })
        
        temp_list = []
        for user in users:
            user_profile = user_profile_collection.find_one({'user_id': user['user_id']}, {'_id': 0, 'user_profile_created_at': 0, 'assigned_games':0})
            user_profile['user_ctf_score'] = round(user_profile['user_ctf_score'])
            user_profile['user_scenario_score'] = round(user_profile['user_scenario_score'])

            user['user_profile_detail'] = user_profile

            temp_list.append(user)
        
        return temp_list
    

class TopPerformerSerializer(serializers.Serializer):
    def get(self):
        pipeline = [
            {
                "$lookup": {
                    "from": "user_collection",
                    "localField": "user_id",
                    "foreignField": "user_id",
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$project": {
                    "_id": 0,
                    "user_id": "$user_info.user_id",
                    "full_name": "$user_info.user_full_name",
                    "avatar": "$user_info.user_avatar",
                    "total_score": { "$add": ["$user_ctf_score", "$user_scenario_score"] },
                }
            }
        ]
        
        result = list(user_profile_collection.aggregate(pipeline))

        for user in result[:]:  
            if user["total_score"] > 0:
                user["total_score"] = round(user["total_score"])
                user["badge"] = "Gold"
            else:
                result.remove(user)

        top_7_users = sorted(result, key=lambda x: x["total_score"], reverse=True)[:7]
        
        return top_7_users


class CommonWinningWallSerializer(serializers.Serializer):
    def get(self, keyword):
        if keyword not in ('ctf', 'scenario', 'corporate'):
            return {
                "errors": {
                    "non_field_errors": ["Invalid Keyword"]
                }
            }  

        user_scores = {}
        winning_wall_data = []

        if keyword == 'ctf':
            challenge_ctf_games = ctf_game_collection.find({'ctf_is_challenge': True}, {'_id': 0, 'ctf_id': 1, 'ctf_score':1})
            challenge_ctf_ids = [game['ctf_id'] for game in challenge_ctf_games]
            ctf_players = ctf_player_arsenal_collection.find({}, {'_id': 0, 'user_id': 1, 'ctf_score_obtained': 1, 'ctf_id': 1})

            for player in ctf_players:
                user_id = player['user_id']
                ctf_score_obtained = player['ctf_score_obtained']
                ctf_id = player['ctf_id']

                if user_id not in user_scores:
                    user_scores[user_id] = {
                        'ctf_score_obtained': 0,
                        'ctf_challenge_score': 0,
                        'max_score': 0
                    }

                user_scores[user_id]['ctf_score_obtained'] += ctf_score_obtained

                ctf_scores = [game['ctf_score'] for game in ctf_game_collection.find({'ctf_id': ctf_id}, {'_id': 0, 'ctf_score': 1})]

                if ctf_scores:
                    user_scores[user_id]['max_score'] += sum(ctf_scores)  
                else:
                    user_scores[user_id]['max_score'] += 0

                if ctf_id in challenge_ctf_ids:
                    user_scores[user_id]['ctf_challenge_score'] += ctf_score_obtained

            for user_id, user_data in user_scores.items():
                user = user_collection.find_one({'user_id': user_id})

                if user:
                    winning_wall_data.append({
                        "user_id": user['user_id'],
                        "user_full_name": user["user_full_name"],
                        "user_avatar": user["user_avatar"],
                        "user_role": user.get("user_role", ""),
                        "score_obtained": str(round(user_data['ctf_score_obtained']))+'/'+str(round(user_data['max_score'])),
                        "challenge_score": str(round(user_data['ctf_challenge_score']))+'/'+str(round(user_data['max_score'])),
                        "badge_earned": "Gold"
                    })

            return sorted(winning_wall_data, key=lambda x: convert_score(x["score_obtained"]), reverse=True)

        elif keyword == 'scenario':
            scenario_game = scenario_collection.find({})

            if scenario_game:
                scenario_players_count = scenario_player_arsenal_collection.count_documents({})

                if scenario_players_count > 0:
                    scenario_players = scenario_player_arsenal_collection.find({})

                    for player in scenario_players:
                        scenario_score_obtained = player['scenario_score_obtained']
                        user_id = player['scenario_participant_id']
                        scenario_id = player['scenario_id']

                        if user_id not in user_scores:
                            user_scores[user_id] = {
                                'scenario_score_obtained': 0,
                                'max_score':0
                            }

                        user_scores[user_id]['scenario_score_obtained'] += scenario_score_obtained

                        scenario_scores = [game['scenario_score'] for game in scenario_collection.find({'scenario_id': scenario_id}, {'_id': 0, 'scenario_score': 1})]

                        if scenario_scores:
                            user_scores[user_id]['max_score'] += sum(scenario_scores)  
                        else:
                            user_scores[user_id]['max_score'] += 0

                    for user_id, user_data in user_scores.items():
                        user = user_collection.find_one({'user_id': user_id})

                        if user:
                            winning_wall_data.append({
                                "user_id": user['user_id'],
                                "user_full_name": user["user_full_name"],
                                "user_avatar": user["user_avatar"],
                                "user_role": user["user_role"],
                                "score_obtained": str(round(user_data['scenario_score_obtained']))+'/'+str(round(user_data['max_score'])),
                                "badge_earned": "Gold"
                            })

            return sorted(winning_wall_data, key=lambda x: convert_score(x["score_obtained"]), reverse=True)

        elif keyword == 'corporate':
            corporate_games = list(archive_participant_collection.find({},{"_id":0, "user_id":1, "scenario_id":1, "total_obtained_score":1,"total_score":1}))
            if corporate_games:
                p_array = {}
                for games in corporate_games:
                    if p_array.get(games["user_id"]):
                        p_array[games["user_id"]].append(games)
                    else:
                        p_array[games["user_id"]] = [games,]
                max_user_scores = []

                for user_id, records in p_array.items():
                    new_score_obj = {}
                    scenario_based = {}
                    for record in records:
                        if scenario_based.get(record["scenario_id"]):
                            scenario_based[record["scenario_id"]].append(record)
                        else:
                            scenario_based[record["scenario_id"]] = [record,]
                    total_obtained_score = 0
                    total_score = 0
                    for s_id, records1 in scenario_based.items():
                        
                        max_score_obj = max(records1, key=lambda x: x['total_obtained_score'])
                        total_obtained_score+=max_score_obj["total_obtained_score"]
                        total_score+=max_score_obj["total_score"]

                    new_score_obj["user_id"] = user_id
                    new_score_obj["total_obtained_score"] = total_obtained_score
                    new_score_obj["total_score"] = total_score
                    user_info = user_collection.find_one({"user_id":user_id},{"_id":0,"user_full_name":1,"user_role":1,"user_avatar":1})
                    new_score_obj.update(user_info)
                    new_score_obj["badge_earned"] = "Gold"
                    new_score_obj["score_obtained"]= str(round(total_obtained_score))+'/'+str(round(total_score))
                    max_user_scores.append(new_score_obj)

                    # adding corporate score to user profile collection
                    profile_obj = user_profile_collection.find_one({"user_id":user_id},{"_id":0})
                    if profile_obj.get("user_corporate_score"):
                        if round(profile_obj["user_corporate_score"]) != round(total_obtained_score):
                            user_profile_collection.update_one({"user_id":user_id},{"$set":{"user_corporate_score":round(total_obtained_score)}})
                    else:
                        user_profile_collection.update_one({"user_id":user_id},{"$set":{"user_corporate_score":round(total_obtained_score)}})

                sorted_achivers_data = sorted(max_user_scores, key=lambda x: x["total_obtained_score"], reverse=True)
            else:
                sorted_achivers_data = []
            return sorted_achivers_data
        
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=100, write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data
    
    def validate(self, data):
        user_data = user_collection.find_one({'email': data['email']}, {'_id': 0, 'user_id': 1})

        if user_data is None:
            raise serializers.ValidationError("Account does not exists.")

        user_id = user_data.get('user_id')
        data['user_id'] = user_id
        data['user_full_name'] = user_data.get("user_full_name","Friend")

        
        otp_hash_obj = otp_hash_collection.find_one({"user_id": user_id})
        if otp_hash_obj:
            previous_date = otp_hash_obj.get("created_at")
            current_date = datetime.datetime.now()
            # Calculate the time difference
            time_difference = current_date - previous_date

            # Check if the time difference is greater than one minute
            if time_difference < datetime.timedelta(minutes=1):
                raise serializers.ValidationError("OTP has already been sent. If not received, please try again after 1 minute.")
        
        return data
  
    def create(self, validated_data):
        otp, otp_hash = generate_otp()

        user_name_data = user_collection.find_one({"user_id": validated_data['user_id']},{"_id":0,"user_full_name":1})

        send_otp_by_email.delay(validated_data['email'], otp, user_name_data.get("user_full_name","Friend"), 'forgotpass')

        otp_details = {
            "otp_hash": otp_hash, 
            "created_at": datetime.datetime.now()            
        }
        otp_hash_collection.update_one({"user_id":validated_data['user_id']},{
                                       "$set": otp_details},upsert=True)

        return {}
    
class UpdatePasswordSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=6, write_only=True)
    password = serializers.CharField(max_length=255, write_only=True)
    confirm_password = serializers.CharField(max_length=255, write_only=True)

    def validate(self, data):
        otp_hash = hashlib.md5(data['otp'].encode()).hexdigest()

        otp_hash_obj = otp_hash_collection.find_one({"otp_hash": otp_hash}, {"_id": 0})
        if otp_hash_obj is None:
            raise serializers.ValidationError("Invalid OTP")
        
        user_id = otp_hash_obj.get('user_id')
        otp_hash = otp_hash_obj.get('otp_hash')

        data['user_id'] = user_id
        data['otp_hash'] = otp_hash

        password = data.get('password')
        confirm_password = data.get('confirm_password')

        validate_password(password)

        if password != confirm_password:
            raise serializers.ValidationError("Password and Confirm Password does not match. Enter passwords again.")
        
        if otp_hash_obj is None:
            raise serializers.ValidationError("OTP expired. Resend Again")

        return data

    def create(self, validated_data):

        validated_data['password'] = make_password(password = validated_data.get('password'))
        encrypted_password = cipher_suite.encrypt(validated_data['password'].encode())

        user_collection.update_one(
            {'user_id': validated_data['user_id']},
            {'$set': {
                'password': encrypted_password.decode(),
                'updated_at': datetime.datetime.now()
                }
            }
        )

        otp_hash_collection.delete_one({'otp_hash': validated_data['otp_hash']})
        return {}
