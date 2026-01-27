from rest_framework import serializers


class UserProfileDetailSerializer(serializers.Serializer):
    ctf_score = serializers.IntegerField()
    scenario_score = serializers.IntegerField()
    corporate_score = serializers.IntegerField()


class UserListSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    user_full_name = serializers.CharField()
    user_avatar = serializers.CharField()
    user_role = serializers.CharField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    user_profile = UserProfileDetailSerializer()


class UserProfileSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    email = serializers.CharField()
    user_full_name = serializers.CharField()
    user_avatar = serializers.CharField()
    user_role = serializers.CharField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
