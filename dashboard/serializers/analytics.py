from rest_framework import serializers


class ScenarioArchiveSerializer(serializers.Serializer):
    total_ctf_scenario = serializers.IntegerField()
    total_corporate_scenario = serializers.IntegerField()
    total_scenario = serializers.IntegerField()


class ScenarioReadySerializer(serializers.Serializer):
    total_ctf_scenario = serializers.IntegerField()
    total_corporate_scenario = serializers.IntegerField()
    total_scenario = serializers.IntegerField()
    total_webbased_scenario = serializers.IntegerField()


class ScenarioSerializer(serializers.Serializer):
    archive = ScenarioArchiveSerializer()
    ready = ScenarioReadySerializer()


class UserAnalyticsSerializer(serializers.Serializer):
    total_user = serializers.IntegerField()


class AverageScoresSerializer(serializers.Serializer):
    avg_ctf_score = serializers.FloatField()
    avg_scenario_score = serializers.FloatField()
    avg_corporate_score = serializers.FloatField()
    total_users = serializers.IntegerField()


class TopRankUserSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    user_ctf_score = serializers.FloatField()
    user_scenario_score = serializers.FloatField()
    user_corporate_score = serializers.FloatField(required=False)
    total_score = serializers.FloatField()
    user_full_name = serializers.CharField(required=False, allow_null=True)
    user_avatar = serializers.URLField(required=False, allow_null=True)
    user_role = serializers.CharField(required=False, allow_null=True)


class ScoresSerializer(serializers.Serializer):
    average_scores = AverageScoresSerializer()
    top_rank_users = TopRankUserSerializer(many=True)


class NotificationSerializer(serializers.Serializer):
    type = serializers.CharField()
    title = serializers.CharField()
    timestamp = serializers.DateTimeField()


class AnalyticsSerializer(serializers.Serializer):
    scenario = ScenarioSerializer()
    user = UserAnalyticsSerializer()
    scores = ScoresSerializer()
    notifications = NotificationSerializer(many=True)
