import datetime
import os
from itertools import groupby

from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password

from core.utils import generate_random_string, API_URL, is_email_valid
from database_management.pymongo_client import (
    user_collection,
    user_profile_collection,
    ctf_category_collection,
    ctf_game_collection,
    ctf_cloud_mapping_collection,
    scenario_category_collection,
    scenario_collection,
    ctf_player_arsenal_collection,
    scenario_player_arsenal_collection,
    resource_credentials_collection,
    corporate_scenario_collection,
    milestone_data_collection,
    flag_data_collection,
    corporate_scenario_infra_collection,
)
from user_management.encryption import cipher_suite
from user_management.utils import USER_ROLES
from cloud_management.utils import (
    get_instance_flavors, 
    get_instance_images,
    get_image_detail,
)
from ctf_management.utils import validate_file_size

class UserAdminSerializer(serializers.Serializer):
    user_full_name = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=100)
    mobile_number = serializers.IntegerField()
    user_avatar = serializers.URLField(max_length=200, default=f'{API_URL}/static/images/user_avatars/avatar_1.png')
    user_role = serializers.ChoiceField(choices=USER_ROLES)
    password = serializers.CharField(max_length=255, write_only=True)
    confirm_password = serializers.CharField(max_length=255, write_only=True)
    is_active = serializers.BooleanField(default=False)
    is_verified = serializers.BooleanField(default=False)
    is_premium = serializers.BooleanField(default=False)
    is_admin = serializers.BooleanField(default=False)
    # is_superadmin = serializers.BooleanField(default=False)

    def key_func(self, k):
        return k['user_id']


    def get(self):
        # users = list(user_collection.find({},{"_id":0,"password":0, "created_at":0, "updated_at":0}))

        # filtered_data = {}
        # user_profile_array = list(user_profile_collection.find({},{"_id":0,"user_id":1, "user_ctf_score":1, "user_scenario_score":1}))
        # user_profile_sorted_array = sorted(user_profile_array, key= self.key_func)

        # for key, value in groupby(user_profile_sorted_array, self.key_func):
        #     filtered_data[key] = list(value)
        
        # for n,user in enumerate(users):
        #     if user["is_superadmin"]:
        #         users.pop(n)
        #     else:
        #         if user['is_active'] and user['is_verified'] and user['is_admin'] :
        #             user['privilege_access'] = "Admin"
        #         elif user['is_active'] and user['is_verified'] and user['is_premium'] :
        #             user['privilege_access'] = "Premium"
        #         elif user['is_active'] and user['is_verified'] :
        #             user['privilege_access'] = "Verified"
        #         elif user['is_active'] and not user['is_verified'] :
        #             user['privilege_access'] = "Unverified"
        #         elif not user['is_active']:
        #             user['privilege_access'] = "Not Active"
            
        #         del user["is_superadmin"]

        #         user["ctf_total_score"] = filtered_data[user["user_id"]][0]["user_ctf_score"] 
        #         user["scenario_total_score"] =  filtered_data[user["user_id"]][0]["user_scenario_score"] 

        # return users

        pipeline = [
                    {
                        "$project": {
                            "_id": 0,
                            "password": 0,
                            "created_at": 0,
                            "updated_at": 0
                        }
                    },
                    {
                        "$lookup": {
                            "from": "user_profile_collection",
                            "localField": "user_id",
                            "foreignField": "user_id",
                            "as": "user_profile"
                        }
                    },
                    {
                        "$unwind": {
                            "path": "$user_profile",
                            "preserveNullAndEmptyArrays": True
                        }
                    },
                    {
                        "$match": {
                            "is_superadmin": False
                        }
                    },
                    {
                        "$project": {
                            "user_id": 1,
                            "user_full_name": 1,
                            "mobile_number": 1,
                            "email": 1,
                            "user_avatar":1,
                            "user_role": 1,
                            "is_active": 1,
                            "is_verified": 1,
                            "is_admin": 1,
                            "is_premium": 1,
                            "ctf_total_score": { "$round": ["$user_profile.user_ctf_score", 0] }, #"$user_profile.user_ctf_score",
                            "scenario_total_score": { "$round": ["$user_profile.user_scenario_score", 0] }, # "$user_profile.user_scenario_score",
                            "privilege_access": {
                                "$switch": {
                                    "branches": [
                                        {"case": {"$and": ["$is_active", "$is_verified", "$is_admin"]}, "then": "Admin"},
                                        {"case": {"$and": ["$is_active", "$is_verified", "$is_premium"]}, "then": "Premium"},
                                        {"case": {"$and": ["$is_active", "$is_verified"]}, "then": "Verified"},
                                        {"case": {"$and": ["$is_active", { "$not": "$is_verified" }]}, "then": "Unverified"},
                                        {"case": {"$and": [{ "$not": "$is_active" }]}, "then": "Not Active"}
                                    ],
                                    "default": "Unknown"
                                }
                            }
                        }
                    }
                ]

        result = list(user_collection.aggregate(pipeline))
        return result
    
    
    def validate(self, data):
        email = (data.get('email')).lower()
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        mobile_number = data.get('mobile_number')
        
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
            raise serializers.ValidationError("Password and Confirm Password do not match. . Enter passwords again.")
        
        if data.get('user_avatar'):
            directory = "static/images/user_avatars/"
            input_file_name = data.get('user_avatar').split("/")[-1]
            file_path = os.path.join(directory, input_file_name)
    
            if os.path.isfile(file_path):
                data['user_avatar'] = f'{API_URL}/static/images/user_avatars/{input_file_name}'
            else:
                data['user_avatar'] = f'{API_URL}/static/images/user_avatars/avatar_1.png'

        return data

    def create(self, validated_data):
        validated_data['password'] = make_password(password = validated_data.get('password'))
        encrypted_password = cipher_suite.encrypt(validated_data["password"].encode())
        user_id = generate_random_string('user_id', length=10)
        current_time = datetime.datetime.now()

        user = {
            "user_id": user_id,
            "user_full_name": validated_data["user_full_name"],
            "mobile_number" : validated_data["mobile_number"],
            "email": validated_data["email"],
            "user_avatar": validated_data["user_avatar"],
            "user_role": validated_data["user_role"],
            "password": encrypted_password.decode(),
            "is_active": True,
            "is_premium": validated_data["is_premium"],
            "is_verified": validated_data["is_verified"],
            "is_admin": validated_data["is_admin"],
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
            "user_profile_created_at": current_time,
            "user_profile_updated_at": current_time,
            "assigned_games": {"ctf":[],
                               "display_all_ctf": True,
                               "scenario": [],
                               "display_all_scenario": True,
                               "corporate": [],
                               "display_all_corporate":True,
                               "display_locked_ctf": False,
                               "display_locked_scenario": False,
                               "display_locked_corporate": False
                             }
        }
        user_profile_collection.insert_one(user_profile)

        return user


    class Meta:
        ref_name = 'AdminUserAdmin'  
        

class UserRetrieveAdminSerializer(serializers.Serializer):
    def get(self, user_id):
        user = user_collection.find_one({'user_id': user_id}, {'_id': 0, 'password': 0})
        assigned_games = user_profile_collection.find_one({'user_id': user_id}, {'_id': 0, 'assigned_games': 1})

        if not user:
            return {
                "errors": {
                    "non_field_errors": ["Invalid User Id"]
                }
            }
        user['password'] = None
        user['confirm_password'] = None        
        user['display_all_ctf'] = assigned_games['assigned_games'].get('display_all_ctf')
        user['display_all_scenario'] = assigned_games['assigned_games'].get('display_all_scenario')
        user['display_all_corporate'] = assigned_games['assigned_games'].get('display_all_corporate')
        user['display_locked_ctf'] = assigned_games['assigned_games'].get('display_locked_ctf')
        user['display_locked_scenario'] = assigned_games['assigned_games'].get('display_locked_scenario')
        user['display_locked_corporate'] = assigned_games['assigned_games'].get('display_locked_corporate')

        return user


class UserUpdateAdminSerializer(serializers.Serializer):
    user_full_name = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=100)
    mobile_number = serializers.IntegerField()
    user_role = serializers.ChoiceField(choices=USER_ROLES)
    user_avatar = serializers.URLField(max_length=200, default=f'{API_URL}/static/images/user_avatars/avatar_1.png')
    password = serializers.CharField(max_length=255, write_only=True, allow_null=True)
    confirm_password = serializers.CharField(max_length=255, write_only=True, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    is_verified = serializers.BooleanField(default=False)
    is_premium = serializers.BooleanField(default=False)
    is_admin = serializers.BooleanField(default=False)
    display_all_ctf = serializers.BooleanField(default=True)
    display_all_scenario = serializers.BooleanField(default=True)
    display_all_corporate = serializers.BooleanField(default=True)
    display_locked_ctf = serializers.BooleanField(default=False)
    display_locked_scenario = serializers.BooleanField(default=False)
    display_locked_corporate = serializers.BooleanField(default=False)

    # is_superadmin = serializers.BooleanField(default=False)


    def validate(self, data):
        email = data.get('email')
        mobile_number = data.get('mobile_number')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        user_id = self.context['view'].kwargs.get('user_id')

        user = user_collection.find_one({'user_id': user_id})
        if not user:
            raise serializers.ValidationError("Invalid User Id")

        if user['email'] != email :
            users_count = user_collection.count_documents({'email': email, 'user_id': {'$ne': user_id}})
            if users_count >= 1:
                raise serializers.ValidationError("Email address is already registered.")
            
        if user['mobile_number'] != mobile_number:
            users_count = user_collection.count_documents({'mobile_number': mobile_number, 'user_id': {'$ne': user_id}})
            if users_count >= 1:
                raise serializers.ValidationError("Mobile number is already registered. Enter a valid mobile number.")

        if not data['user_full_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Full Name can only contain alphabets, digits, and spaces.")        
        
        if not is_email_valid(email):
            raise serializers.ValidationError("Invalid Email Id. Enter a valid email id.")
                    
        if len(str(data['mobile_number'])) != 10: 
            raise serializers.ValidationError("Invalid mobile number. Enter a valid mobile number.")

        if password:
            validate_password(password)
            if password != confirm_password:
                raise serializers.ValidationError("Password and Confirm Password do not match.")
                
        if data.get('user_avatar'):
            directory = "static/images/user_avatars/"
            input_file_name = data.get('user_avatar').split("/")[-1]
            file_path = os.path.join(directory, input_file_name)
    
            if os.path.isfile(file_path):
                data['user_avatar'] = f'{API_URL}/static/images/user_avatars/{input_file_name}'
            else:
                data['user_avatar'] = f'{API_URL}/static/images/user_avatars/avatar_1.png'
        
        data['user_id'] = user_id
        data['user_data'] = user

        return data

    def create(self, validated_data):
        # Store the user information in MongoDB
        user = {
            "user_full_name": validated_data["user_full_name"],
            "mobile_number" : validated_data["mobile_number"],
            "email": validated_data["email"],
            "user_avatar": validated_data["user_avatar"],
            "user_role": validated_data["user_role"],
            "is_active": validated_data["is_active"],
            "is_premium": validated_data["is_premium"],
            "is_verified": validated_data["is_verified"],
            "is_admin": validated_data["is_admin"],
            "is_superadmin": validated_data["user_data"]["is_superadmin"],
            "updated_at": datetime.datetime.now()
        }

        if validated_data['password']:
            validated_data['password'] = make_password(password = validated_data.get('password'))
            encrypted_password = cipher_suite.encrypt(validated_data["password"].encode())
            user["password"] = encrypted_password.decode()

        user_values = { "$set": user}
        user_update = user_collection.update_one({'user_id':validated_data['user_id']}, user_values)
        user_game_update = user_profile_collection.update_one({'user_id':validated_data['user_id']}, {"$set": 
            {
                'assigned_games.display_all_ctf': validated_data['display_all_ctf'],
                'assigned_games.display_all_scenario': validated_data['display_all_scenario'],
                'assigned_games.display_all_corporate': validated_data['display_all_corporate'],
                'assigned_games.display_locked_ctf': validated_data['display_locked_ctf'],
                'assigned_games.display_locked_scenario': validated_data['display_locked_scenario'],
                'assigned_games.display_locked_corporate': validated_data['display_locked_corporate']
            }
        })
        return user
    

    class Meta:
        ref_name = 'AdminUserUpdateAdmin'  
    
class UserRemoveAdminSerializer(serializers.Serializer):
    def validate(self, data):
        user_id = self.context['view'].kwargs.get('pk')
        user = user_collection.find_one({'user_id': user_id})
        admin_count = user_collection.count_documents({'is_admin': True})

        if not user:
            raise serializers.ValidationError("Invalid User ID")
        
        if user["is_admin"] or user["is_superadmin"]:
            raise serializers.ValidationError("Admin cannot delete.")

        if admin_count <= 1:
            raise serializers.ValidationError("Atleast one admin is required.")
        
        data['user_id'] = user_id 
        return data 

    def create(self, validated_data):        
        user_collection.delete_one({ "user_id": validated_data['user_id']})
        user_profile_collection.delete_one({ "user_id": validated_data['user_id']})
        ctf_player_arsenal_collection.delete_one({ "user_id": validated_data['user_id']})
        scenario_player_arsenal_collection.delete_one({ "scenario_participant_id": validated_data['user_id']})
        
        return {}
    

# CTF


class CTFCategoryListSerializer(serializers.Serializer):
    def get(self):
        ctf_categories_list = list(ctf_category_collection.find({},{"_id":0,"ctf_category_description":0,"updated_at":0}))
        for category in ctf_categories_list:
            category["no_of_ctf"] = ctf_game_collection.count_documents({"ctf_category_id":category["ctf_category_id"]})
        
        return ctf_categories_list

class CTFCategorySerializer(serializers.Serializer):
    ctf_category_name = serializers.CharField(max_length=100, required=True)
    ctf_category_description = serializers.CharField(min_length=50, max_length=5000, required=True)
    ctf_category_thumbnail = serializers.FileField(required=False, write_only=True, validators=[validate_file_size])

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data
    
    def get(self):
        ctf_categories_list = []
        ctf_categories = ctf_category_collection.find()

        for category in ctf_categories:
            ctf_games_list = []

            ctf_games = ctf_game_collection.find({"ctf_category_id": category['ctf_category_id'], "ctf_target_uploaded": True})
            
            for ctf_game in ctf_games:
                temp_game = {
                    "ctf_id": ctf_game['ctf_id'],
                    "ctf_name": ctf_game['ctf_name'],
                    "ctf_description": ctf_game['ctf_description'],
                    "ctf_thumbnail": ctf_game['ctf_thumbnail'],
                    "ctf_creator_id": ctf_game['ctf_creator_id'],
                    "ctf_creator_name": ctf_game['ctf_creator_name'],
                    "ctf_assigned_severity": ctf_game['ctf_assigned_severity'],
                    "ctf_rated_severity": ctf_game['ctf_rated_severity'],
                    "ctf_score": ctf_game['ctf_score'],
                    "ctf_players_count": ctf_game['ctf_players_count']
                }
                ctf_games_list.append(temp_game)
            
            temp_category = {
                "ctf_category_id": category['ctf_category_id'],
                "ctf_category_name": category['ctf_category_name'],
                "ctf_category_description": category['ctf_category_description'],
                "ctf_category_thumbnail": category["ctf_category_thumbnail"],
                "category_items": ctf_games_list,
            }

            ctf_categories_list.append(temp_category)

        return ctf_categories_list
    
    def validate(self, data): 
        # Check that name contains only alphabets, digits, and spaces
        if not data['ctf_category_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Category Name can only contain alphabets, digits, and spaces.")
        
        if ctf_category_collection.find_one({'ctf_category_name': data['ctf_category_name']}):
            raise serializers.ValidationError("Category Name already exists, it must be unique. Try another name.")
        
        if data.get('ctf_category_thumbnail'):
            if not data['ctf_category_thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png')):
                raise serializers.ValidationError("Unsupported file format. Only jpeg, jpg, and png are allowed.")
        
        return data
    
    def create(self, validated_data):
        # For generating unique random CTF Game Id
        ctf_category_id = generate_random_string('ctf_category_id', length=5)
        current_date_time = datetime.datetime.now()
        current_timestamp = str(current_date_time.timestamp()).split(".")[0]

        # For Thumbnail
        if validated_data.get('ctf_category_thumbnail'):
            # Get file name and extension
            thumbnail_file = validated_data.pop('ctf_category_thumbnail', None)
            thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)

            # Rename the file
            thumbnail_file_name = f"{ctf_category_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"
            # Store the file in the specified directory
            with open(f"static/images/ctf_category_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                for chunk in thumbnail_file.chunks():
                    destination.write(chunk)

            thumbnail_url = f'{API_URL}/static/images/ctf_category_thumbnails/{thumbnail_file_name}'
        else:
            thumbnail_url = f'{API_URL}/static/images/ctf_category_thumbnails/default.jpg'
        
        # Store the user information in MongoDB
        ctf_category = {
            "ctf_category_id": ctf_category_id,
            "ctf_category_name": validated_data['ctf_category_name'],
            "ctf_category_description": validated_data['ctf_category_description'],
            "ctf_category_thumbnail" : thumbnail_url,
            "created_at": current_date_time,
            "updated_at": current_date_time
        }

        ctf_category_collection.insert_one(ctf_category)
        
        return ctf_category
    
    class Meta:
        ref_name = 'AdminCTFCategory'

class CTFCategoryUpdateSerializer(serializers.Serializer):
    ctf_category_name = serializers.CharField(max_length=200, required=True)
    ctf_category_description = serializers.CharField(min_length=50, max_length=5000, required=True)
    ctf_category_thumbnail = serializers.FileField(required=False, write_only=True, validators=[validate_file_size])

    def get(self, ctf_category_id):
        ctf_category_detail = ctf_category_collection.find_one(
            {"ctf_category_id":ctf_category_id},
            {"_id":0,
             "ctf_category_name":1,
             "ctf_category_description":1,
             "ctf_category_thumbnail":1
                })
        
        if not ctf_category_detail:
            return  {
                "errors": { "non_field_errors": ["Invalid CTF Category Id."]}
            }
        
        ctf_category_detail["category_name"] = ctf_category_detail.pop("ctf_category_name")
        ctf_category_detail["category_description"] = ctf_category_detail.pop("ctf_category_description")
        ctf_category_detail["category_thumbnail"] = ctf_category_detail.pop("ctf_category_thumbnail")

        return ctf_category_detail

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        ctf_category_id = self.context['view'].kwargs.get('ctf_category_id')

        data['user'] = self.context['request'].user

        if not ctf_category_collection.find_one({'ctf_category_id': ctf_category_id}):
            raise serializers.ValidationError("Invalid CTF Category Id.")
        
        # Check that name contains only alphabets, digits, and spaces
        if not data['ctf_category_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Name can only contain alphabets, digits, and spaces.")
        
        if data['ctf_category_name'] != ctf_category_collection.find_one({'ctf_category_id': ctf_category_id})["ctf_category_name"]:
            if ctf_category_collection.find_one({'ctf_category_name': data['ctf_category_name']}):
                raise serializers.ValidationError("Name already exists, it must be unique. Try another name.")
        
        # Check if file format is allowed
        if data.get('ctf_category_thumbnail'):
            if not data['ctf_category_thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png')):
                raise serializers.ValidationError("Unsupported file format. Only jpeg, jpg, and png are allowed for CTF Category Thumbnail.")
            
        data["ctf_category_id"] = ctf_category_id

        return data

    def create(self, validated_data):
        ctf_category_id = validated_data["ctf_category_id"]
        current_date_time = datetime.datetime.now()
        current_timestamp = str(current_date_time.timestamp()).split(".")[0]
        ctf_category_detail = ctf_category_collection.find_one({'ctf_category_id': ctf_category_id})

        # For Thumbnail
        if not validated_data.get('ctf_category_thumbnail'):
            thumbnail_url = ctf_category_detail["ctf_category_thumbnail"]
        else:
            if validated_data.get('ctf_category_thumbnail'):
                # Get file name and extension
                thumbnail_file = validated_data.pop('ctf_category_thumbnail', None)
                thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)

                # Rename the file
                thumbnail_file_name = f"{ctf_category_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"
                # Store the file in the specified directory
                with open(f"static/images/ctf_category_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                    for chunk in thumbnail_file.chunks():
                        destination.write(chunk)

                thumbnail_url = f'{API_URL}/static/images/ctf_category_thumbnails/{thumbnail_file_name}'

                file_path = ctf_category_detail["ctf_category_thumbnail"].split("static")[1] if "default.jpg" not in  ctf_category_detail["ctf_category_thumbnail"].split("static")[1] else None
                if os.path.exists(f"static{file_path}"):
                    try:
                        os.remove(f"static{file_path}")
                    except Exception as e:
                        pass

            else:
                thumbnail_url = f'{API_URL}/static/images/ctf_category_thumbnails/default.jpg'
        
        # Store the user information in MongoDB
        ctf_category = {
            "ctf_category_name": validated_data['ctf_category_name'],
            "ctf_category_description": validated_data['ctf_category_description'],
            "ctf_category_thumbnail": thumbnail_url,
            "updated_at": current_date_time
        }

        ctf_category_collection.update_one({"ctf_category_id":ctf_category_id},{"$set":ctf_category})
        
        return ctf_category
    
class CTFUnmappedGameSerializer(serializers.Serializer):
    def get(self, user_id):        
        user = user_collection.find_one({'user_id': user_id}, {'_id': 0, 'password': 0})
        if not user:
            return {
                "errors": {
                    "non_field_errors": ["Invalid User Id"]
                }
            }
        
        unmapped_games = ctf_game_collection.find({'ctf_is_approved': False})

        unmapped_game_list = []
        for ctf in unmapped_games:
            temp = {
                'ctf_id': ctf['ctf_id'],
                'ctf_name': ctf['ctf_name'],
                'ctf_flag_count': len(ctf['ctf_flags']),
                'ctf_target_uploaded': ctf['ctf_target_uploaded'],
                'ctf_description': ctf['ctf_description'],
                'ctf_thumbnail': ctf['ctf_thumbnail'],
                'ctf_assigned_severity': ctf['ctf_assigned_severity'],
                'ctf_time': ctf['ctf_time'],
                'ctf_is_approved': ctf['ctf_is_approved'],
                'ctf_created_at': ctf['ctf_created_at'],
                'ctf_updated_at': ctf['ctf_updated_at']
            }
            unmapped_game_list.append(temp)

        return unmapped_game_list

class CTFMappedGameSerializer(serializers.Serializer):
    def get(self):
        list_of_ctf = list(ctf_game_collection.find({"ctf_is_approved":True},{"_id":0,
                                                                              "ctf_name":1,
                                                                              "ctf_id":1,
                                                                              "ctf_flag_count":1,
                                                                              "ctf_target_uploaded":1,
                                                                              "ctf_description":1,
                                                                              "ctf_thumbnail":1,
                                                                              "ctf_time": 1,
                                                                              "ctf_assigned_severity": 1,
                                                                              "ctf_is_approved":1,
                                                                              "ctf_created_at":1,
                                                                              "ctf_updated_at":1,
                                                                              }))
        for i in list_of_ctf:
            mapping_id = ctf_cloud_mapping_collection.find_one({"ctf_id":i["ctf_id"]},{"_id":0,"ctf_mapping_id":1})
            if mapping_id:
                i["ctf_mapping_id"] = mapping_id.get("ctf_mapping_id")
                del i["ctf_id"]
        return list_of_ctf


class CTFGameMappingSerializer(serializers.Serializer):
    ctf_id = serializers.CharField(max_length=50, required=True)
    ctf_target_image_id = serializers.ChoiceField(choices=[], required=True)
    ctf_target_flavor_id = serializers.ChoiceField(choices=[], required=True)
    ctf_attacker_image_id = serializers.ChoiceField(choices=[], required=True)
    ctf_attacker_flavor_id = serializers.ChoiceField(choices=[], required=True)
    ctf_time = serializers.IntegerField(max_value=10, min_value=1, required=True)
    ctf_attacker_username = serializers.CharField(max_length=50, required=True)
    ctf_attacker_password = serializers.CharField(max_length=50, required=True)
    ctf_score = serializers.IntegerField(max_value=100, min_value=10, required=True)
    ctf_for_premium_user = serializers.BooleanField(default=False)



    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)

        image_ids = get_instance_images()
        flavor_ids = get_instance_flavors()

        self.fields['ctf_target_image_id'].choices = image_ids
        self.fields['ctf_target_flavor_id'].choices = flavor_ids
        self.fields['ctf_attacker_image_id'].choices = image_ids
        self.fields['ctf_attacker_flavor_id'].choices = flavor_ids
    
    
    
    # def get(self):
    #     image_ids = get_instance_images()
    #     flavor_ids = get_instance_flavors()

    #     choices = {
    #         'target_machine': [{'id': image[0], 'name': image[1]} for image in image_ids],
    #         'attacker_machine': [{'id': image[0], 'name': image[1]} for image in image_ids],
    #         'target_flavor': [{'id': flavor[0], 'name': flavor[1]} for flavor in flavor_ids],
    #         'attacker_flavor': [{'id': flavor[0], 'name': flavor[1]} for flavor in flavor_ids],
    #     }

    #     return choices


    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        ctf_machine = ctf_game_collection.find_one({'ctf_id': data['ctf_id']})

        if not ctf_machine:
            raise serializers.ValidationError("Invalid CTF ID")
        
        if len(ctf_machine['ctf_mapping_id']) != 0:
            raise serializers.ValidationError("This CTF is already mapped.")
                
        if not ctf_machine['ctf_target_uploaded']:
            raise serializers.ValidationError("The target machine has not been uploaded for this game. Upload a target machine first.")
        
        data['user'] = self.context['request'].user
                    
        return data 

    def create(self, validated_data):
        # For generating unique random Mapping Id
        ctf_mapping_id = generate_random_string('ctf_mapping_id', length=15)
        current_datetime = datetime.datetime.now() 

        ctf_mapping = {
            "ctf_mapping_id": ctf_mapping_id,
            "ctf_id": validated_data['ctf_id'],
            "ctf_target_image_id": validated_data['ctf_target_image_id'],
            "ctf_target_flavor_id": validated_data['ctf_target_flavor_id'],
            "ctf_attacker_image_id": validated_data['ctf_attacker_image_id'],
            "ctf_attacker_flavor_id": validated_data['ctf_attacker_flavor_id'],
            "ctf_time": validated_data['ctf_time'],
            "ctf_score": validated_data['ctf_score'],
            "ctf_for_premium_user": validated_data['ctf_for_premium_user'],
            "ctf_mapped_by": validated_data['user']['user_id'],
            "ctf_attacker_username" : validated_data['ctf_attacker_username'],
            "ctf_attacker_password" : validated_data['ctf_attacker_password'],
            "ctf_mapping_created_at": current_datetime,
            "ctf_mapping_updated_at": current_datetime
        }
        
        ctf_cloud_mapping_collection.insert_one(ctf_mapping)
        
        ctf_game_collection.update_one(
            {'ctf_id': validated_data['ctf_id']}, 
            {
                '$set': {
                    'ctf_is_approved': True, 
                    'ctf_mapping_id': ctf_mapping_id,
                    'ctf_score': validated_data['ctf_score'],
                    'ctf_for_premium_user': validated_data['ctf_for_premium_user'],
                    'ctf_updated_at': current_datetime, 
                }
            }
        )
        
        return ctf_mapping


class CTFDeleteMappingSerializer(serializers.Serializer):

    def validate(self, data):
        ctf_mapping_id = self.context['view'].kwargs.get('mapping_id')
        ctf_mapping = ctf_cloud_mapping_collection.find_one({'ctf_mapping_id': ctf_mapping_id})

        if not ctf_mapping:
            raise serializers.ValidationError("Invalid CTF Mapping ID")
        
        data['ctf_mapping_id'] = ctf_mapping_id
                        
        return data 

    def create(self, validated_data):        
        ctf_cloud_mapping_collection.delete_one({ "ctf_mapping_id": validated_data['ctf_mapping_id']})
        
        ctf_game_collection.update_one(
            {'ctf_mapping_id': validated_data['ctf_mapping_id']}, 
            {
                '$set': {
                    'ctf_is_approved': False, 
                    'ctf_mapping_id': "", 
                    'ctf_updated_at': datetime.datetime.now(), 
                }
            }
        )
        
        return {}
    
class CTFGameListSerializer(serializers.Serializer):
    def get(self):        
        ctf_game_list = list(ctf_game_collection.find({},{"_id":0,"ctf_id":1,"ctf_name":1}))
        return ctf_game_list
    
    class Meta:
        ref_name = 'AdminCTFGameList'
    

class CTFGameUpdateSerializer(serializers.Serializer):
    ctf_name = serializers.CharField(max_length=200, required=True)
    ctf_description = serializers.CharField(min_length=50, max_length=5000, required=True)
    ctf_category_id = serializers.ChoiceField(choices=())
    ctf_severity = serializers.ChoiceField(choices=('Very Easy', 'Easy', 'Medium', 'Hard', 'Very Hard'), required=True, write_only=True)
    ctf_time = serializers.IntegerField(max_value=10, min_value=1, required=True)
    ctf_flags = serializers.CharField(max_length=500, required=True, write_only=True)   
    ctf_score = serializers.CharField(max_length=10, required=True, write_only=True)   
    ctf_thumbnail = serializers.FileField(required=False, write_only=True, validators=[validate_file_size])
    ctf_walkthrough = serializers.FileField(required=False, write_only=True, validators=[validate_file_size])
    ctf_for_premium_user = serializers.BooleanField(required=True, write_only=True)
    ctf_flags_information = serializers.CharField(required=False, min_length=100, max_length=5000)
    ctf_rules_regulations = serializers.CharField(required=False, min_length=100, max_length=5000)

    def get(self, ctf_id):
        ctf_game_detail = ctf_game_collection.find_one(
            {"ctf_id":ctf_id},
            {"_id":0,
            "ctf_id": 1,
            "ctf_name": 1,
            "ctf_description": 1,
            "ctf_flags": 1,
            "ctf_category_id": 1,
            "ctf_thumbnail": 1,
            "ctf_walkthrough": 1,
            "ctf_time": 1,
            "ctf_assigned_severity": 1,
            "ctf_score": 1,
            "ctf_for_premium_user": 1,
            "ctf_flags_information": 1,
            "ctf_rules_regulations": 1

                })
        
        ctf_game_detail["ctf_severity"] = ctf_game_detail["ctf_assigned_severity"]
        del ctf_game_detail["ctf_assigned_severity"]
        
        if not ctf_game_detail:
            return {}
        return ctf_game_detail

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ctf_category_id'].choices = self.get_ctf_category_choices()

    def get_ctf_category_choices(self):
        categories = ctf_category_collection.find({}, {'ctf_category_id': 1, 'ctf_category_name': 1})
        return [(category['ctf_category_id'], category['ctf_category_name']) for category in categories]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        ctf_id = self.context['view'].kwargs.get('ctf_id')

        data['user'] = self.context['request'].user

        if not ctf_game_collection.find_one({'ctf_id': ctf_id}):
            raise serializers.ValidationError("Invalid CTF Id.")
        
        # Check that name contains only alphabets, digits, and spaces
        if not data['ctf_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Game Name can only contain alphabets, digits, and spaces.")
        
        if data['ctf_name'] != ctf_game_collection.find_one({'ctf_id': ctf_id})["ctf_name"]:
            if ctf_game_collection.find_one({'ctf_name': data['ctf_name']}):
                raise serializers.ValidationError("Game Name already exists, it must be unique. Try another name.")
        
        # submitted_machines_count = ctf_game_collection.count_documents({
        #     'ctf_creator_id': data['user'].get('user_id'),
        #     "ctf_is_approved": False,
        # })
        # if data.get('user')['is_premium']:
        #     if submitted_machines_count >= 3:
        #         raise serializers.ValidationError("We are validating your previously submitted machines. Please try again later.")
        # else:
        #     if submitted_machines_count >= 1:
        #         raise serializers.ValidationError("We are validating your previously submitted machine. Please upgrade to premium or try again later.")

        if len(data['ctf_flags'].split()) != len(set(data['ctf_flags'].split())):
            raise serializers.ValidationError("Duplicate flags found. Modify the flags and try again.")
        
        # Check if file format is allowed
        if data.get('ctf_thumbnail'):
            if not data['ctf_thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png')):
                raise serializers.ValidationError("Unsupported file format. Only jpeg, jpg, and png are allowed for CTF Thumbnail.")
        
        if data.get('ctf_walkthrough'):
            if not data.get('ctf_walkthrough').name.lower().endswith(('pdf')):
                raise serializers.ValidationError("Unsupported file format. Only PDF is allowed for CTF Walkthrough.")
        data["ctf_id"] = ctf_id

        return data

    def create(self, validated_data):
        ctf_id = validated_data["ctf_id"]
        current_date_time = datetime.datetime.now()
        current_timestamp = str(current_date_time.timestamp()).split(".")[0]
        ctf_game_detail = ctf_game_collection.find_one({'ctf_id': ctf_id})


        # For Walkthrough
        if not validated_data.get("ctf_walkthrough"):
            walkthrough_url = ctf_game_detail["ctf_walkthrough"]
        else:
            walkthrough_file = validated_data.pop('ctf_walkthrough', None)
            walkthrough_file_name, walkthrough_file_extension = os.path.splitext(walkthrough_file.name)
            # Rename the file
            walkthrough_file_name = f"{ctf_id}_walkthrough_{current_timestamp}{walkthrough_file_extension.lower()}"
            # Store the file in the specified directory
            with open(f"static/documents/ctf_game_walkthroughs/{walkthrough_file_name}", 'wb+') as destination:
                for chunk in walkthrough_file.chunks():
                    destination.write(chunk)
            walkthrough_url = f'{API_URL}/static/documents/ctf_game_walkthroughs/{walkthrough_file_name}'

            file_path = ctf_game_detail["ctf_walkthrough"].split("static")[1]
            if os.path.exists(f"static{file_path}"):
                try:
                    os.remove(f"static{file_path}")
                except Exception as e:
                    pass

        # For Thumbnail
        if not validated_data.get('ctf_thumbnail'):
            thumbnail_url = ctf_game_detail["ctf_thumbnail"]
        else:
            if validated_data.get('ctf_thumbnail'):
                # Get file name and extension
                thumbnail_file = validated_data.pop('ctf_thumbnail', None)
                thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)

                # Rename the file
                thumbnail_file_name = f"{ctf_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"
                # Store the file in the specified directory
                with open(f"static/images/ctf_game_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                    for chunk in thumbnail_file.chunks():
                        destination.write(chunk)

                thumbnail_url = f'{API_URL}/static/images/ctf_game_thumbnails/{thumbnail_file_name}'

                file_path = ctf_game_detail["ctf_thumbnail"].split("static")[1] if "default.jpg" not in  ctf_game_detail["ctf_thumbnail"].split("static")[1] else None
                if os.path.exists(f"static{file_path}"):
                    try:
                        os.remove(f"static{file_path}")
                    except Exception as e:
                        pass

            else:
                thumbnail_url = f'{API_URL}/static/images/ctf_game_thumbnails/default.jpg'
        
        # Store the user information in MongoDB
        ctf = {
            "ctf_name": validated_data['ctf_name'],
            "ctf_description": validated_data['ctf_description'],
            "ctf_flags": validated_data["ctf_flags"].split(),
            "ctf_thumbnail": thumbnail_url,
            "ctf_walkthrough": walkthrough_url,
            "ctf_category_id": validated_data['ctf_category_id'],
            "ctf_time": validated_data['ctf_time'],
            "ctf_score": int(validated_data['ctf_score']),
            "ctf_assigned_severity": validated_data['ctf_severity'],
            "ctf_for_premium_user": validated_data['ctf_for_premium_user'],
            "ctf_flags_information": validated_data.get('ctf_flags_information', ""),
            "ctf_rules_regulations": validated_data.get('ctf_rules_regulations', ""),
            "ctf_updated_at": current_date_time
        }

        ctf_game_collection.update_one({"ctf_id":ctf_id},{"$set":ctf})
        
        return ctf
    
    class Meta:
        ref_name = 'AdminGameUpdate'        

# SCENARIO

class ScenarioCategoryListSerializer(serializers.Serializer):
    def get(self):
        scenario_categories_list = list(scenario_category_collection.find({},{"_id":0,"scenario_category_description":0,"updated_at":0}))
        for category in scenario_categories_list:
            category["no_of_scenario"] = scenario_collection.count_documents({"scenario_category_id":category["scenario_category_id"]})
        
        return scenario_categories_list

class ScenarioCategorySerializer(serializers.Serializer):
    scenario_category_name = serializers.CharField(max_length=100, required=True)
    scenario_category_description = serializers.CharField(min_length=50, max_length=5000, required=True)
    scenario_category_thumbnail = serializers.FileField(required=False, write_only=True, validators=[validate_file_size])

    # def to_representation(self, instance):
    #     data = super().to_representation(instance)
    #     additional_fields = instance
    #     data.update(additional_fields)
    #     return data
    
    def get(self):
        scenarios = scenario_category_collection.find({}, {'_id': 0})
        return list(scenarios)
    
    def validate(self, data):
        # Check that name contains only alphabets, digits, and spaces
        if not data['scenario_category_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Category Name can only contain alphabets, digits, and spaces.")
        
        if scenario_category_collection.find_one({'scenario_category_name': data['scenario_category_name']}):
            raise serializers.ValidationError("Category Name already exists, it must be unique. Try another name.")
        
        if data.get('scenario_category_thumbnail'):
            if not data['scenario_category_thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png')):
                raise serializers.ValidationError("Unsupported file format. Only jpeg, jpg, and png are allowed.")
        
        return data
    
    def create(self, validated_data):
        # For generating unique random scenario Game Id
        scenario_category_id = generate_random_string('scenario_category_id', length=5)

        current_date_time = datetime.datetime.now()
        current_timestamp = str(current_date_time.timestamp()).split(".")[0]

        # For Thumbnail
        if validated_data.get('scenario_category_thumbnail'):
            # Get file name and extension
            thumbnail_file = validated_data.pop('scenario_category_thumbnail', None)
            thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)

            # Rename the file
            thumbnail_file_name = f"{scenario_category_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"
            # Store the file in the specified directory
            with open(f"static/images/scenario_category_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                for chunk in thumbnail_file.chunks():
                    destination.write(chunk)

            thumbnail_url = f'{API_URL}/static/images/scenario_category_thumbnails/{thumbnail_file_name}'
        else:
            thumbnail_url = f'{API_URL}/static/images/scenario_category_thumbnails/default.jpg'

        # Store the user information in MongoDB
        scenario_category = {
            "scenario_category_id": scenario_category_id,
            "scenario_category_name": validated_data['scenario_category_name'],
            "scenario_category_description": validated_data['scenario_category_description'],
            "scenario_category_thumbnail" : thumbnail_url,
            "created_at": current_date_time,
            "updated_at": current_date_time
        }

        scenario_category_collection.insert_one(scenario_category)
        
        return scenario_category
    

    class Meta:
        ref_name = 'AdminScenarioCategory'

class ScenarioCategoryUpdateSerializer(serializers.Serializer):
    scenario_category_name = serializers.CharField(max_length=200, required=True)
    scenario_category_description = serializers.CharField(min_length=50, max_length=5000, required=True)
    scenario_category_thumbnail = serializers.FileField(required=False, write_only=True, validators=[validate_file_size])

    def get(self, scenario_category_id):

        scenario_category_detail = scenario_category_collection.find_one(
            {"scenario_category_id":scenario_category_id},
            {"_id":0,
             "scenario_category_name":1,
             "scenario_category_description":1,
             "scenario_category_thumbnail":1
                })
        if not scenario_category_detail:
            return  {
                "errors": { "non_field_errors": ["Invalid Scenario Category Id."]}
            }

        scenario_category_detail["category_name"] = scenario_category_detail.pop("scenario_category_name")
        scenario_category_detail["category_description"] = scenario_category_detail.pop("scenario_category_description")
        scenario_category_detail["category_thumbnail"] = scenario_category_detail.pop("scenario_category_thumbnail")

        return scenario_category_detail

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        scenario_category_id = self.context['view'].kwargs.get('scenario_category_id')

        data['user'] = self.context['request'].user

        if not scenario_category_collection.find_one({'scenario_category_id': scenario_category_id}):
            raise serializers.ValidationError("Invalid Scenario Category Id.")
        
        # Check that name contains only alphabets, digits, and spaces
        if not data['scenario_category_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Name can only contain alphabets, digits, and spaces.")
        
        if data['scenario_category_name'] != scenario_category_collection.find_one({'scenario_category_id': scenario_category_id})["scenario_category_name"]:
            if scenario_category_collection.find_one({'scenario_category_name': data['scenario_category_name']}):
                raise serializers.ValidationError("Name already exists, it must be unique. Try another name.")
        
        # Check if file format is allowed
        if data.get('scenario_category_thumbnail'):
            if not data['scenario_category_thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png')):
                raise serializers.ValidationError("Unsupported file format. Only jpeg, jpg, and png are allowed for Scenario Category Thumbnail.")
            
        data["scenario_category_id"] = scenario_category_id

        return data

    def create(self, validated_data):
        scenario_category_id = validated_data["scenario_category_id"]
        current_date_time = datetime.datetime.now()
        current_timestamp = str(current_date_time.timestamp()).split(".")[0]
        scenario_category_detail = scenario_category_collection.find_one({'scenario_category_id': scenario_category_id})

        # For Thumbnail
        if not validated_data.get('scenario_category_thumbnail'):
            thumbnail_url = scenario_category_detail["scenario_category_thumbnail"]
        else:
            if validated_data.get('scenario_category_thumbnail'):
                # Get file name and extension
                thumbnail_file = validated_data.pop('scenario_category_thumbnail', None)
                thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)

                # Rename the file
                thumbnail_file_name = f"{scenario_category_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"
                # Store the file in the specified directory
                with open(f"static/images/scenario_category_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                    for chunk in thumbnail_file.chunks():
                        destination.write(chunk)

                thumbnail_url = f'{API_URL}/static/images/scenario_category_thumbnails/{thumbnail_file_name}'

                file_path = scenario_category_detail["scenario_category_thumbnail"].split("static")[1] if "default.jpg" not in  scenario_category_detail["scenario_category_thumbnail"].split("static")[1] else None
                if os.path.exists(f"static{file_path}"):
                    try:
                        os.remove(f"static{file_path}")
                    except Exception as e:
                        pass
            else:
                thumbnail_url = f'{API_URL}/static/images/scenario_category_thumbnails/default.jpg'
        
        # Store the user information in MongoDB
        scenario_category = {
            "scenario_category_name": validated_data['scenario_category_name'],
            "scenario_category_description": validated_data['scenario_category_description'],
            "scenario_category_thumbnail": thumbnail_url,
            "updated_at": current_date_time
        }

        scenario_category_collection.update_one({"scenario_category_id":scenario_category_id},{"$set":scenario_category})
        
        return scenario_category
    
    class Meta:
        ref_name = 'AdminScenarioCategoryUpdate'

class ScenarioApproveSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(max_length=50, required=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data  
    
    def get(self):
        unapproved_scenario = list(scenario_collection.find({"scenario_is_approved":False,"scenario_is_prepared":True},
                                                            {"_id":0,
                                                             "scenario_id":1,
                                                             "scenario_name":1,
                                                             "scenario_assigned_severity":1,
                                                             "scenario_score":1,
                                                             "scenario_time":1,
                                                             "scenario_description":1,
                                                             "scenario_thumbnail":1,
                                                             "scenario_documents":1,
                                                             "scenario_players_count":1,
                                                             "mitre_mapping":"",
                                                             "network_topology":""
                                                             }))
        return unapproved_scenario
    
    def validate(self, data):
        data['scenario'] = scenario_collection.find_one({
            'scenario_id': data['scenario_id']
        }, {'_id': 0})

        if not data['scenario']:
            raise serializers.ValidationError("Invalid Scenario ID")   
        if data['scenario']["scenario_is_approved"] == True and data['scenario']["scenario_is_prepared"] == True:
            raise serializers.ValidationError("Scenario Already Approved.")


        return data

    def create(self, validated_data):

        updated_scenario = scenario_collection.update_one({'scenario_id': validated_data['scenario'].get('scenario_id')}, {'$set': {
            'scenario_is_approved': True,
            'scenario_updated_at': datetime.datetime.now()
        }})

        response = {
            'scenario_id': validated_data['scenario_id'],
            'message' : "Scenario Approve Successfully."
        }

        return response
    
    
    class Meta:
        ref_name = 'AdminScenarioApprove'


class ScenarioUnapproveSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(max_length=50, required=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data  
    
    def get(self):
        approved_scenario = list(scenario_collection.find({"scenario_is_approved":True,"scenario_is_prepared":True},
                                                          {"_id":0,
                                                           "scenario_id":1,
                                                           "scenario_name":1,
                                                           "scenario_assigned_severity":1,
                                                           "scenario_score":1,
                                                           "scenario_time":1,
                                                           "scenario_description":1,
                                                           "scenario_thumbnail":1,
                                                           "scenario_documents":1,
                                                           "scenario_players_count":1,
                                                           "mitre_mapping":"",
                                                           "network_topology":"",
                                                           }))
        return approved_scenario
    
    def validate(self, data):
        data['scenario'] = scenario_collection.find_one({
            'scenario_id': data['scenario_id']
        }, {'_id': 0})

        if not data['scenario']:
            raise serializers.ValidationError("Invalid Scenario ID")   
        
        if data['scenario']["scenario_is_approved"] == False and data['scenario']["scenario_is_prepared"] == True:
            raise serializers.ValidationError("Scenario needs to be Approve.")
        return data

    def create(self, validated_data):

        updated_scenario = scenario_collection.update_one({'scenario_id': validated_data['scenario'].get('scenario_id')}, {'$set': {
            'scenario_is_approved': False,
            'scenario_updated_at': datetime.datetime.now()
        }})

        response = {
            'scenario_id': validated_data['scenario_id'],
            'message' : "Scenario Un-Approve Successfully."
        }

        return response
    
    
    class Meta:
        ref_name = 'AdminScenarioUnapprove'
    

class ScenarioGameListSerializer(serializers.Serializer):
    def get(self):        
        scenario_game_list = list(scenario_collection.find({},{"_id":0,"scenario_id":1,"scenario_name":1}))
        return scenario_game_list
    
class ScenarioGameUpdateSerializer(serializers.Serializer):
    scenario_name = serializers.CharField(max_length=200, required=True)
    scenario_category_id = serializers.ChoiceField(choices=())
    scenario_assigned_severity = serializers.ChoiceField(choices=('Very Easy', 'Easy', 'Medium', 'Hard', 'Very Hard'), required=True, write_only=True)
    scenario_score = serializers.IntegerField(max_value=100, min_value=10, required=True)
    scenario_time = serializers.IntegerField(max_value=10, min_value=1, required=True)
    scenario_description = serializers.CharField(min_length=50, max_length=5000, required=True)
    scenario_thumbnail = serializers.FileField(required=False, validators=[validate_file_size])
    scenario_documents = serializers.ListField(
        child=serializers.FileField(validators=[validate_file_size]),
        allow_empty=False,
        required=False
    )
    scenario_for_premium_user = serializers.BooleanField(required=True)
    scenario_tools_technologies = serializers.CharField(min_length=100, max_length=5000, required=False)
    scenario_prerequisites = serializers.CharField(required=False, min_length=100, max_length=5000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scenario_category_id'].choices = self.get_scenario_category_choices()

    def get_scenario_category_choices(self):
        categories = scenario_category_collection.find({}, {'scenario_category_id': 1, 'scenario_category_name': 1})
        return [(category['scenario_category_id'], category['scenario_category_name']) for category in categories]


    def get(self, scenario_id):
        if not scenario_collection.find_one({"scenario_id":scenario_id}):
            return {
                "errors": {
                    "non_field_errors": ["Invalid Scenario Id."]
                }
            }
        scenario_game_detail = scenario_collection.find_one(
            {"scenario_id":scenario_id},
            {"_id":0,
            "scenario_name": 1,
            "scenario_category_id": 1,
            "scenario_assigned_severity": 1,
            "scenario_score": 1,
            "scenario_time": 1,
            "scenario_description": 1,
            "scenario_thumbnail": 1,
            "scenario_documents": 1,
            "scenario_for_premium_user": 1,
            "scenario_tools_technologies": 1,
            "scenario_prerequisites": 1,
                })
        
        if not scenario_game_detail:
            return {}
        return scenario_game_detail

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data    
    
    def validate(self, data):

        scenario_id = self.context['view'].kwargs.get('scenario_id')

        if not scenario_collection.find_one({'scenario_id': scenario_id}):
            raise serializers.ValidationError("Invalid Scenario Id.")

        if not data['scenario_name'].replace(' ', '').isalnum():
            raise serializers.ValidationError("Scenario Name can only contain alphabets, digits, and spaces.")
        if data['scenario_name'] != scenario_collection.find_one({'scenario_name': data['scenario_name']})["scenario_name"]:
            if scenario_collection.find_one({'scenario_name': data['scenario_name']}):
                raise serializers.ValidationError("Scenario Name already exists, it must be unique. Try another name.")
        
        # Check if file format is allowed
        if data.get('scenario_thumbnail'):
            if not data['scenario_thumbnail'].name.lower().endswith(('jpeg', 'jpg', 'png')):
                raise serializers.ValidationError("Unsupported file format. Only jpeg, jpg, and png are allowed for Scenario Thumbnail.")
            
        if data.get('scenario_documents'):
            for scenario_document in data.get('scenario_documents'):
                if not scenario_document.name.lower().endswith(('pdf')):
                    raise serializers.ValidationError("Unsupported file format. Only PDF is allowed for Scenario Documents.")
        data['scenario_id'] = scenario_id

        return data
    
    def create(self, validated_data):
        # For generating unique random Scenario Game Id
        scenario_id =  validated_data["scenario_id"]
        current_date_time = datetime.datetime.now()
        current_timestamp = str(current_date_time.timestamp()).split(".")[0]
        scenario_game_detail = scenario_collection.find_one({'scenario_id': scenario_id})

        # For document
        document_url_list = list()
        document_files = validated_data.get('scenario_documents')
        
        counter = 0
        if not document_files:
            document_url_list = scenario_game_detail["scenario_documents"]
        else:
            for document_file in document_files:
                document_file_name, document_file_extension = os.path.splitext(document_file.name)
                
                counter += 1
                new_file_name = f"{scenario_id}_document_{current_timestamp}_{counter}{document_file_extension.lower()}"
                # Store the file in the specified directory
                with open(f"static/documents/scenario_game_documents/{new_file_name}", 'wb+') as destination:
                    for chunk in document_file.chunks():
                        destination.write(chunk)
                document_url = f'{API_URL}/static/documents/scenario_game_documents/{new_file_name}'
                scenario_game_detail["scenario_documents"].append(document_url)
                document_url_list = scenario_game_detail["scenario_documents"]

        # For Thumbnail
        if not validated_data.get('scenario_thumbnail'):
            thumbnail_url = scenario_game_detail["scenario_thumbnail"]
        else:
            if validated_data.get('scenario_thumbnail'):
                # Get file name and extension
                thumbnail_file = validated_data.pop('scenario_thumbnail', None)
                thumbnail_file_name, thumbnail_file_extension = os.path.splitext(thumbnail_file.name)

                # Rename the file
                thumbnail_file_name = f"{scenario_id}_thumbnail_{current_timestamp}{thumbnail_file_extension.lower()}"
                # Store the file in the specified directory
                with open(f"static/images/scenario_game_thumbnails/{thumbnail_file_name}", 'wb+') as destination:
                    for chunk in thumbnail_file.chunks():
                        destination.write(chunk)

                thumbnail_url = f'{API_URL}/static/images/scenario_game_thumbnails/{thumbnail_file_name}'

                file_path = scenario_game_detail["scenario_thumbnail"].split("static")[1] if "default.jpg" not in  scenario_game_detail["scenario_thumbnail"].split("static")[1] else None
                if os.path.exists(f"static{file_path}"):
                    try:
                        os.remove(f"static{file_path}")
                    except Exception as e:
                        pass
            else:
                thumbnail_url = f'{API_URL}/static/images/scenario_game_thumbnails/default.jpg'

        scenario = {
            'scenario_name' : validated_data['scenario_name'],
            'scenario_category_id' : validated_data['scenario_category_id'],
            'scenario_assigned_severity' : validated_data['scenario_assigned_severity'],
            'scenario_score' : validated_data['scenario_score'],
            'scenario_time' : validated_data['scenario_time'],
            'scenario_description' : validated_data['scenario_description'],
            'scenario_thumbnail' : thumbnail_url,
            'scenario_documents' : document_url_list,
            'scenario_for_premium_user' : validated_data["scenario_for_premium_user"],
            'scenario_tools_technologies' : validated_data.get('scenario_tools_technologies', ""),
            'scenario_prerequisites' : validated_data.get('scenario_prerequisites', ""),
            'scenario_created_at' : current_date_time,
        }

        scenario_collection.update_one({"scenario_id":scenario_id},{"$set":scenario})

        return scenario
    
    class Meta:
        ref_name = 'AdminScenarioGameUpdate'

class ScenarioGameDocumentRemoveSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(required=True)
    document_url = serializers.CharField(required=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data 

    def validate(self, data):
        scenario_id = data["scenario_id"]
        doc_url = data["document_url"]

        scenario_detail = scenario_collection.find_one({'scenario_id': scenario_id})

        if not scenario_detail:
            raise serializers.ValidationError("Invalid Scenario Id.")
        
        if doc_url not in scenario_detail.get("scenario_documents"):
            raise serializers.ValidationError("Invalid Document.")
        
        data["scenario_data"] = scenario_detail
        return data
    
    def create(self, validated_data):
        current_date_time = datetime.datetime.now()

        if validated_data['document_url'] in validated_data["scenario_data"]["scenario_documents"]:
            file_path = validated_data['document_url'].split("static")[1]
            if os.path.exists(f"static{file_path}"):
                try:
                    os.remove(f"static{file_path}")
                except Exception as e:
                    pass
                validated_data["scenario_data"]["scenario_documents"].remove(validated_data['document_url'])

            scenario = {
                'scenario_documents' : validated_data["scenario_data"]["scenario_documents"],
                'scenario_created_at' : current_date_time,
            }
            scenario_collection.update_one({"scenario_id":validated_data["scenario_id"]},{"$set":scenario})

        return {
            "scenario_id": validated_data["scenario_id"],
            "document_url" : validated_data["document_url"]
        }
        

    class Meta:
        ref_name = 'AdminScenarioGameDocumentRemove'

class ImageValidateSerializer(serializers.Serializer):
    image_id = serializers.ChoiceField(choices=get_instance_images(), required=True)
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image_id'].choices = get_instance_images()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        result = resource_credentials_collection.find_one({'image_id': data['image_id']})

        if get_image_detail(data['image_id']) is None:
            raise serializers.ValidationError("Not a valid Image ID")
        
        if result != None:
            raise serializers.ValidationError("Already mapped with user credentials")
        
        return data
    
    def create(self, validated_data):
        resource_credentials_collection.insert_one(validated_data)
        return validated_data
    
class GetCTFScenarioSerializer(serializers.Serializer):
    def get(self, keyword, user_id):
        user = user_profile_collection.find_one({'user_id': user_id}, {'_id': 0, 'assigned_games': 1})
        if not user:
            return {
                "errors": {
                    "non_field_errors": ["Invalid User Id."]
                }
            }
        
        assigned_games = user['assigned_games']

        if keyword == 'ctf':
            ctf_list = []
            ctf_ids = assigned_games.get('ctf', [])

            for ctf_id in ctf_ids:
                ctf = ctf_game_collection.find_one({'ctf_id': ctf_id}, {'ctf_name': 1, 'ctf_description': 1, 'ctf_assigned_severity': 1, 'ctf_time': 1, 'ctf_thumbnail': 1})
                if ctf:
                    ctf_data = {
                        'ctf_id': ctf_id, 
                        'ctf_name': ctf.get('ctf_name'),
                        'ctf_description': ctf.get('ctf_description'),
                        'ctf_assigned_severity': ctf.get('ctf_assigned_severity'),
                        'ctf_time': ctf.get('ctf_time'),
                        'ctf_thumbnail': ctf.get('ctf_thumbnail')
                    }
                    ctf_list.append(ctf_data)

            return ctf_list

        elif keyword == 'scenario':
            scenario_list = []
            scenario_ids = assigned_games.get('scenario', [])

            for scenario_id in scenario_ids:
                scenario = scenario_collection.find_one({'scenario_id': scenario_id}, {'scenario_name': 1, 'scenario_description': 1, 'scenario_assigned_severity': 1, 'scenario_time': 1, 'scenario_thumbnail': 1})
                if scenario:
                    scenario_data = {
                        'scenario_id': scenario_id,
                        'scenario_name': scenario.get('scenario_name'),
                        'scenario_description': scenario.get('scenario_description'),
                        'scenario_assigned_severity': scenario.get('scenario_assigned_severity'),
                        'scenario_time': scenario.get('scenario_time'),
                        'scenario_thumbnail': scenario.get('scenario_thumbnail')
                    }
                    scenario_list.append(scenario_data)

            return scenario_list
        
        elif keyword == 'corporate':
            corporate_list = []
            corporate_ids = assigned_games.get('corporate', [])

            for corporate_id in corporate_ids:
                corporate = corporate_scenario_collection.find_one({'id': corporate_id}, {'name': 1, 'description': 1, 'severity': 1, 'thumbnail_url': 1, 'milestone_data':1})
                if corporate:
                    corporate_data = {
                        'id': corporate_id,
                        'name': corporate.get('name'),
                        'description': corporate.get('description'),
                        'severity': corporate.get('severity'),
                        'time': 1,
                        'thumbnail_url': corporate.get('thumbnail_url'),
                        'type' :  "Milestone" if corporate.get("milestone_data") else "Flag"
                    }
                    corporate_list.append(corporate_data)

            return corporate_list
        
        return []


class AddCTFForUserSerializer(serializers.Serializer):
    ctf_id = serializers.CharField(required=True, write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data

    def validate(self, data):
        user_id = self.context['view'].kwargs.get('user_id')
        user = user_profile_collection.find_one({'user_id': user_id}, {'assigned_games': 1})
        if not user:
            raise serializers.ValidationError("User does not exist")

        ctf = ctf_game_collection.find_one({'ctf_id': data['ctf_id']})
        if not ctf:
            raise serializers.ValidationError("Invalid CTF ID")

        assigned_ctfs = user.get('assigned_games', {}).get('ctf', [])
        if data['ctf_id'] in assigned_ctfs:
            raise serializers.ValidationError("CTF already assigned to the user")

        return data
    
    def create(self, validated_data):
        user_id = self.context['view'].kwargs.get('user_id')
        ctf_id = validated_data['ctf_id']

        user_profile_collection.update_one(
            {'user_id': user_id},
            {'$addToSet': {'assigned_games.ctf': ctf_id}}
        )

        return {}
    
class AddScenarioForUserSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(required=True, write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(instance)
        return data 
    
    def validate(self, data):
        user_id = self.context['view'].kwargs.get('user_id')
        user = user_profile_collection.find_one({'user_id': user_id}, {'assigned_games': 1})

        if not user:
            raise serializers.ValidationError("User does not exist")
        
        scenario = scenario_collection.find_one({'scenario_id': data['scenario_id']})
        if not scenario:
            raise serializers.ValidationError("Invalid Scenario ID")
        
        assigned_scenarios = user.get('assigned_games', {}).get('scenario', [])
        if data['scenario_id'] in assigned_scenarios:
            raise serializers.ValidationError("Scenario already assigned to the user")
        
        return data
    
    def create(self, validated_data):
        user_id = self.context['view'].kwargs.get('user_id')
        scenario_id = validated_data['scenario_id']

        user_profile_collection.update_one(
            {'user_id': user_id},
            {'$addToSet': {'assigned_games.scenario': scenario_id}}
        )

        return {}
    
class AddCorporateForUserSerializer(serializers.Serializer):
    corporate_id = serializers.CharField(required=True, write_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(instance)
        return data 
    
    def validate(self, data):
        user_id = self.context['view'].kwargs.get('user_id')
        user = user_profile_collection.find_one({'user_id': user_id}, {'assigned_games': 1})

        if not user:
            raise serializers.ValidationError("User does not exist")
        
        corporate = corporate_scenario_collection.find_one({'id': data['corporate_id']})
        if not corporate:
            raise serializers.ValidationError("Invalid Corporate Scenario ID")
        
        assigned_corporates = user.get('assigned_games', {}).get('corporate', [])
        if data['corporate_id'] in assigned_corporates:
            raise serializers.ValidationError("Corporate Scenario already assigned to the user")
        
        return data
    
    def create(self, validated_data):
        user_id = self.context['view'].kwargs.get('user_id')
        corporate_id = validated_data['corporate_id']

        user_profile_collection.update_one(
            {'user_id': user_id},
            {'$addToSet': {'assigned_games.corporate': corporate_id}}
        )

        return {}
    
class RemoveCTFScenarioForUserSerializer(serializers.Serializer):
    def delete(self, keyword, user_id, item_id):
        user = user_profile_collection.find_one({'user_id': user_id}, {'_id': 0, 'assigned_games': 1})
        if not user:
            return {
                "errors": {
                    "non_field_errors": ["Invalid User Id."]
                }
            }
        
        assigned_games = user['assigned_games']
        items = assigned_games.get(keyword, [])
        data = None

        if item_id in items:
            if keyword == 'ctf':
                ctf = ctf_game_collection.find_one({'ctf_id': item_id}, {'_id': 0, 'ctf_name': 1})
                data = ctf.get('ctf_name')
            elif keyword == 'scenario':
                scenario = scenario_collection.find_one({'scenario_id': item_id}, {'_id': 0, 'scenario_name': 1})
                data = scenario.get('scenario_name')
            elif keyword == 'corporate':
                corporate = corporate_scenario_collection.find_one({'id': item_id}, {'_id': 0, 'name': 1})
                data = corporate.get('name')

            items.remove(item_id)
            user_profile_collection.update_one({'user_id': user_id}, {'$set': {'assigned_games': assigned_games}})
            return {"message": f"{keyword.capitalize()} '{data}' removed successfully."}
        else:
            if keyword == 'ctf':
                data = ctf_game_collection.find_one({'ctf_id': item_id}, {'_id': 0, 'ctf_name': 1})
            elif keyword == 'scenario':
                data = scenario_collection.find_one({'scenario_id': item_id}, {'_id': 0, 'scenario_name': 1})
            elif keyword == 'corporate':
                data = corporate_scenario_collection.find_one({'id': item_id}, {'_id': 0, 'name': 1})
            return {"errors": f"{keyword.capitalize()} '{data.get(keyword + '_name')}' does not exist."}
        

class GetCTFScenarioForUserSpecificSerializer(serializers.Serializer):
    def get(self, game_type, category_id, user_id):

        if game_type == "ctf":
            if not ctf_category_collection.find_one({"ctf_category_id":category_id}):
                return {"errors": {"non_field_errors": ["Invalid CTF Category Id"]}}
        
            if user_id and not user_collection.find_one({"user_id":user_id}):
                return {"errors": {"non_field_errors": ["Invalid User Id"]}}
            
            assigned_games = user_profile_collection.find_one({"user_id":user_id},{"_id":0,"assigned_games":1})

            if user_id:
                ctf_game_list = list(ctf_game_collection.find(
                    {"ctf_category_id":category_id, "ctf_is_approved": True},
                    {"_id":0,
                    "ctf_id": 1,
                    "ctf_name": 1,
                    "ctf_description": 1,
                    "ctf_flags": 1,
                    "ctf_thumbnail": 1,
                    "ctf_walkthrough": 1,
                    "ctf_time": 1,
                    "ctf_assigned_severity": 1,
                    "ctf_score": 1,
                    "ctf_for_premium_user": 1,
                    "ctf_is_challenge": 1,
                    'mitre_mapping': "", 
                    'network_topology': ""
                            }))
                
                return [ctf for ctf in ctf_game_list if ctf["ctf_id"] not in assigned_games["assigned_games"]["ctf"]]
        elif game_type == "scenario":
            if not scenario_category_collection.find_one({"scenario_category_id":category_id}):
                return {"errors": {"non_field_errors": ["Invalid Scenario Category Id"]}}
        
            if user_id and not user_collection.find_one({"user_id":user_id}):
                return {"errors": {"non_field_errors": ["Invalid User Id"]}}
            
            assigned_games = user_profile_collection.find_one({"user_id":user_id},{"_id":0,"assigned_games":1})

            scenario_category_detail_list = list(
                scenario_collection.find({
                    "scenario_category_id": category_id,
                    "scenario_is_approved": True
                }, 
                { '_id': 0,
                'scenario_id': 1,
                'scenario_name': 1,
                'scenario_assigned_severity': 1,
                'scenario_score': 1, 
                'scenario_description': 1, 
                'mitre_mapping': "", 
                'network_topology': "", 
                'scenario_time': 1, 
                'scenario_thumbnail': 1, 
                'scenario_documents': 1, 
                'scenario_is_challenge': 1,
                'scenario_players_count': 1
                }))
            return [scenario for scenario in scenario_category_detail_list if scenario["scenario_id"] not in assigned_games["assigned_games"]["scenario"]]
        
        elif game_type == "corporate":
            if not scenario_category_collection.find_one({"scenario_category_id":category_id}):
                return {"errors": {"non_field_errors": ["Invalid Scenario Category Id"]}}
        
            if user_id and not user_collection.find_one({"user_id":user_id}):
                return {"errors": {"non_field_errors": ["Invalid User Id"]}}
            
            assigned_games = user_profile_collection.find_one({"user_id":user_id},{"_id":0,"assigned_games":1})

            scenario_category_detail_list = list(
                corporate_scenario_collection.find({
                    "category_id": category_id,
                    "is_approved": True
                }, 
                { '_id': 0,
                'infra_id':0,
                'is_approved':0,
                'is_prepared':0,
                'created_at':0,
                'updated_at':0,
                'files_data':0,
                }))
            
            for scenario in scenario_category_detail_list:
                user = user_collection.find_one({"user_id": scenario["creator_id"]})
                scenario["creator_name"] = user["user_full_name"]
                scenario["type"] =  "Milestone" if scenario.get("milestone_data") else "Flag"


                if scenario.get("milestone_data"):
                    inner_score = 0
                    if scenario["milestone_data"].get("red_team"):
                        for i in scenario["milestone_data"].get("red_team"):
                            score = milestone_data_collection.find_one({"id":i},{"_id":0,"score":1})
                            inner_score += score["score"]
                    if scenario["milestone_data"].get("blue_team"):
                        for i in scenario["milestone_data"].get("blue_team"):
                            score = milestone_data_collection.find_one({"id":i},{"_id":0,"score":1})
                            inner_score += score["score"]
                    if scenario["milestone_data"].get("purple_team"):
                        for i in scenario["milestone_data"].get("purple_team"):
                            score = milestone_data_collection.find_one({"id":i},{"_id":0,"score":1})
                            inner_score += score["score"]
                    if scenario["milestone_data"].get("yellow_team"):
                        for i in scenario["milestone_data"].get("yellow_team"):
                            score = milestone_data_collection.find_one({"id":i},{"_id":0,"score":1})
                            inner_score += score["score"]

                else:
                    inner_score = 0
                    if scenario["flag_data"].get("red_team"):
                        for i in scenario["flag_data"].get("red_team"):
                            score = flag_data_collection.find_one({"id":i},{"_id":0,"score":1})
                            inner_score += score["score"]
                    if scenario["flag_data"].get("blue_team"):
                        for i in scenario["flag_data"].get("blue_team"):
                            score = flag_data_collection.find_one({"id":i},{"_id":0,"score":1})
                            inner_score += score["score"]
                    if scenario["flag_data"].get("purple_team"):
                        for i in scenario["flag_data"].get("purple_team"):
                            score = flag_data_collection.find_one({"id":i},{"_id":0,"score":1})
                            inner_score += score["score"]
                    if scenario["flag_data"].get("yellow_team"):
                        for i in scenario["flag_data"].get("yellow_team"):
                            score = flag_data_collection.find_one({"id":i},{"_id":0,"score":1})
                            inner_score += score["score"]
                
                scenario["points"] = inner_score
            
                
            return [scenario for scenario in scenario_category_detail_list if scenario["id"] not in assigned_games["assigned_games"]["corporate"]]
            
        else:
            return {
                "errors": {
                    "non_field_errors": ["Invalid Game Type."]
                }
            }
        
class CorporateApproveSerializer(serializers.Serializer):
    corporate_id = serializers.CharField(max_length=50, required=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data  

    def get(self):
        unapproved_scenario = list(
            corporate_scenario_collection.find(
                {"is_approved": False, "is_prepared": True},
                {
                    "_id": 0,
                    "infra_id": 0,
                    "files_data": 0,
                    "is_approved": 0,
                    "is_prepared": 0,
                    "created_at": 0,
                    "updated_at": 0,
                },
            )
        )

        for scenario in unapproved_scenario:
            scenario["type"] = "Milestone" if scenario.get("milestone_data") else "Flag"
            scenario.pop("milestone_data", None)
            scenario.pop("flag_data", None)
            scenario["review_done"] = bool(scenario.get("review_done", False))

        return unapproved_scenario

    def validate(self, data):
        corporate = corporate_scenario_collection.find_one(
            {"id": data["corporate_id"]},
            {"_id": 0}
        )

        if not corporate:
            raise serializers.ValidationError("Invalid Corporate ID")

        if corporate.get("is_approved"):
            raise serializers.ValidationError("Corporate already approved.")

        infra_id = corporate.get("infra_id")
        if not infra_id:
            raise serializers.ValidationError("Infra ID missing.")

        infra = corporate_scenario_infra_collection.find_one(
            {"id": infra_id},
            {"_id": 0}
        )

        if not infra:
            raise serializers.ValidationError("Infra not found.")

        # 🔥 ONLY CHECK THAT MATTERS
        if infra.get("status") != "REVIEWED":
            raise serializers.ValidationError("Please review infra before approval.")

        data["corporate"] = corporate
        data["infra"] = infra
        return data

    def create(self, validated_data):
        corporate = validated_data["corporate"]
        infra = validated_data["infra"]
        now = datetime.datetime.utcnow()

        # Approve infra
        corporate_scenario_infra_collection.update_one(
            {"id": infra["id"]},
            {"$set": {
                "status": "APPROVED",
                "review.approved_at": now,
                "updated_at": now
            }}
        )

        # Approve scenario
        corporate_scenario_collection.update_one(
            {"id": corporate["id"]},
            {"$set": {
                "is_approved": True,
                "approved_at": now,
                "updated_at": now
            }}
        )

        return {
            "corporate_id": corporate["id"],
            "infra_id": infra["id"],
            "message": "Corporate approved successfully."
        }

class CorporateInfraReviewGetSerializer(serializers.Serializer):
    corporate_id = serializers.CharField(required=True)

    def validate(self, data):
        corporate = corporate_scenario_collection.find_one(
            {"id": data["corporate_id"]},
            {"_id": 0}
        )
        if not corporate:
            raise serializers.ValidationError("Invalid Corporate ID")

        if corporate.get("is_approved") is True:
            raise serializers.ValidationError("Already approved")

        data["corporate"] = corporate
        return data

    def get_infra(self):
        corporate = self.validated_data["corporate"]
        infra_id = corporate.get("infra_id")

        if not infra_id:
            return {"corporate_id": corporate["id"], "infra": {}}

        infra = corporate_scenario_infra_collection.find_one(
            {"id": infra_id},
            {"_id": 0}
        ) or {}

        return {
            "corporate_id": corporate["id"],
            "infra": infra, 
        }
    
class CorporateInfraReviewSaveSerializer(serializers.Serializer):
    corporate_id = serializers.CharField(required=True)
    reviewed_infra = serializers.JSONField(required=True)

    def validate(self, data):
        corporate = corporate_scenario_collection.find_one(
            {"id": data["corporate_id"]},
            {"_id": 0}
        )
        if not corporate:
            raise serializers.ValidationError("Invalid Corporate ID")

        if corporate.get("is_approved") is True:
            raise serializers.ValidationError("Already approved")

        infra_id = corporate.get("infra_id")
        if not infra_id:
            raise serializers.ValidationError("Infra ID missing.")

        data["corporate"] = corporate
        data["infra_id"] = infra_id
        return data

    def create(self, validated_data):
        infra_id = validated_data["infra_id"]
        reviewed = validated_data["reviewed_infra"]
        now = datetime.datetime.utcnow()

        # ✅ overwrite infra content + set review status
        corporate_scenario_infra_collection.update_one(
            {"id": infra_id},
            {"$set": {
                "networks": reviewed.get("networks", []),
                "routers": reviewed.get("routers", []),
                "instances": reviewed.get("instances", []),
                "firewall": reviewed.get("firewall", []),

                "status": "REVIEWED",
                "review": {
                    "review_done": True,
                    "reviewed_at": now,
                    "reviewed_by": getattr(self.context["request"].user, "email", "admin"),
                },
                "updated_at": now
            }}
        )

        return {"message": "Infra review saved successfully.", "infra_id": infra_id}

class CorporateUnapproveSerializer(serializers.Serializer):
    corporate_id = serializers.CharField(max_length=50, required=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        additional_fields = instance
        data.update(additional_fields)
        return data  
    
    def get(self):
        approved_scenario = list(corporate_scenario_collection.find({"is_approved":True,"is_prepared":True},
                                                          { '_id': 0,
                                                            'infra_id':0,
                                                            'files_data':0,
                                                            'is_approved':0,
                                                            'is_prepared':0,
                                                            'created_at':0,
                                                            'updated_at':0,
                                                        }))
        
        for scenario in approved_scenario:
            scenario["type"] =  "Milestone" if scenario.get("milestone_data") else "Flag"
            scenario.pop("milestone_data") if scenario.get("milestone_data") else scenario.pop("flag_data")
        return approved_scenario
    
    def validate(self, data):
        data['corporate'] = corporate_scenario_collection.find_one({
            'id': data['corporate_id']
        }, {'_id': 0})

        if not data['corporate']:
            raise serializers.ValidationError("Invalid Corporate ID")   
        
        if data['corporate']["is_approved"] == False and data['corporate']["is_prepared"] == True:
            raise serializers.ValidationError("Corporate needs to be Approve.")
        return data

    def create(self, validated_data):

        updated_scenario = corporate_scenario_collection.update_one({'id': validated_data['corporate'].get('id')}, {'$set': {
            'is_approved': False,
            'updated_at': datetime.datetime.now()
        }})

        response = {
            'corporate_id': validated_data['corporate_id'],
            'message' : "Corporate Un-Approve Successfully."
        }

        return response
    
    
    class Meta:
        ref_name = 'AdminCorporateUnapprove'



class AdminCorporateScenarioDetailSerializer(serializers.Serializer):

    def get(self, scenario_id):
        scenario = corporate_scenario_collection.find_one(
            {"id": scenario_id},
            {"_id": 0}
        )
        if not scenario:
            raise serializers.ValidationError("Invalid Corporate Scenario Id")

        # creator
        user = user_collection.find_one(
            {"user_id": scenario.get("creator_id")},
            {"_id": 0, "user_full_name": 1}
        )
        scenario["creator_name"] = user["user_full_name"] if user else "—"

        is_flag = bool(scenario.get("flag_data"))
        scenario["type"] = "FLAG" if is_flag else "MILESTONE"

        # ✅ scoring config (THIS FIXES DECAY / STANDARD DEFAULT)
        scenario["scoring_config"] = scenario.get("scoring_config", {
            "type": "standard",
            "decay": {}
        })

        items = []

        if is_flag:
            for team, ids in scenario.get("flag_data", {}).items():
                for fid in ids:
                    flag = flag_data_collection.find_one({"id": fid}, {"_id": 0})
                    if not flag:
                        continue

                    items.append({
                        "id": flag["id"],
                        "team": team.replace("_team", "").upper(),
                        "phase_id": flag.get("phase_id", ""),
                        "name": flag.get("question", ""),     # ✅ FIX
                        "answer": flag.get("answer", ""),
                        "hint": flag.get("hint", ""),
                        "points": flag.get("score", 100),     # ✅ FIX
                        "hint_penalty": flag.get("hint_penalty", 0),
                        "placeholder": flag.get("placeholder", ""),
                        "show_placeholder": flag.get("show_placeholder", True),
                        "is_locked": flag.get("is_locked", False),
                    })

        else:
            for team, ids in scenario.get("milestone_data", {}).items():
                for mid in ids:
                    ms = milestone_data_collection.find_one({"id": mid}, {"_id": 0})
                    if not ms:
                        continue

                    items.append({
                        "id": ms["id"],
                        "team": team.replace("_team", "").upper(),
                        "phase_id": ms.get("phase_id", ""),
                        "name": ms.get("name", ""),
                        "hint": ms.get("hint", ""),
                        "points": ms.get("score", 100),
                        "hint_penalty": ms.get("hint_penalty", 0),
                        "placeholder": "",
                        "show_placeholder": False,
                        "is_locked": False,
                    })

        scenario["items"] = items
        return scenario

    
class AdminCorporateScenarioUpdateSerializer(serializers.Serializer):
    scenario_id = serializers.CharField()

    name = serializers.CharField(required=False)
    category_id = serializers.CharField(required=False)
    severity = serializers.CharField(required=False)
    description = serializers.CharField(required=False)
    objective = serializers.CharField(required=False, allow_blank=True)
    prerequisite = serializers.CharField(required=False, allow_blank=True)

    scoring_type = serializers.ChoiceField(
        choices=("standard", "decay"),
        required=False
    )
    scoring_decay = serializers.DictField(required=False)

    def validate(self, data):
        scenario = corporate_scenario_collection.find_one(
            {"id": data["scenario_id"]},
            {"_id": 0}
        )
        if not scenario:
            raise serializers.ValidationError("Invalid Scenario ID")

        if scenario.get("is_approved") is True:
            raise serializers.ValidationError("Approved scenario cannot be edited")

        data["scenario"] = scenario
        return data

    def create(self, validated_data):
        scenario_id = validated_data.pop("scenario_id")
        validated_data.pop("scenario")

        update_doc = {
            k: v for k, v in validated_data.items()
            if v is not None
        }
        update_doc["updated_at"] = datetime.datetime.utcnow()

        corporate_scenario_collection.update_one(
            {"id": scenario_id},
            {"$set": update_doc}
        )

        return {"message": "Scenario updated successfully"}