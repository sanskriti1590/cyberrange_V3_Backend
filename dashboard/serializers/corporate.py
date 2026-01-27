from rest_framework import serializers


class ScenarioListSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    severity = serializers.CharField()
    thumbnail_url = serializers.CharField()
    points = serializers.IntegerField(required=False)
    category_name = serializers.CharField()
    type = serializers.CharField()


class ActiveScenarioListSerializer(serializers.Serializer):
    id = serializers.CharField()
    started_by = serializers.CharField()
    start_time = serializers.DateTimeField()
    scenario = ScenarioListSerializer()
    total_participant = serializers.IntegerField()
    total_network = serializers.IntegerField()
    total_routers = serializers.IntegerField()
    total_instances = serializers.IntegerField()


class FlagParticipantAnswerSerializer(serializers.Serializer):
    flag_id = serializers.CharField()
    submitted_response = serializers.CharField()
    obtained_score = serializers.IntegerField()
    hint_used = serializers.BooleanField()
    retires = serializers.IntegerField()
    updated_at = serializers.CharField()
    status = serializers.BooleanField()

class GroupedFlagDataSerializer(serializers.Serializer):
    flag_id = serializers.CharField()
    question = serializers.CharField()
    score = serializers.IntegerField()
    team = serializers.CharField()
    participant_answers = FlagParticipantAnswerSerializer(many=True)



class ParticipantListSerializer(serializers.Serializer):
    id = serializers.CharField()
    user_id = serializers.CharField()
    team = serializers.CharField()
    instance_id = serializers.CharField()
    total_obtained_score = serializers.CharField()
    scenario_id = serializers.CharField()
    total_score = serializers.IntegerField()
    avatar = serializers.CharField()
    role = serializers.CharField()
    full_name = serializers.CharField()
    flag_data = GroupedFlagDataSerializer(many=True)


class ActiveScenarioDetailSerializer(serializers.Serializer):
    id = serializers.CharField()
    started_by = serializers.CharField()
    start_time = serializers.DateTimeField()
    scenario = ScenarioListSerializer()
    participants = ParticipantListSerializer(many=True)
    total_network = serializers.IntegerField()
    total_routers = serializers.IntegerField()
    total_instances = serializers.IntegerField()




class UserSerializer(serializers.Serializer):
    id = serializers.CharField()
    role = serializers.CharField()
    avatar = serializers.CharField()
    full_name = serializers.CharField()


class ScenarioBaseSerializer(serializers.Serializer):
    name = serializers.CharField()
    type = serializers.ChoiceField(choices=["FLAG", "MILESTONE"])


class ConsoleFlagScenarioSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField()
    started_by = serializers.CharField()
    start_time = serializers.DateTimeField()
    current_participant_id = serializers.CharField()
    console_url = serializers.URLField()
    category_name = serializers.CharField()
    scenario = ScenarioBaseSerializer()
    participants = UserSerializer(many=True)


class MilestoneSerializer(serializers.Serializer):
    milestone_id = serializers.CharField()
    is_approved = serializers.BooleanField()
    index = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    score = serializers.IntegerField()


class ConsoleMilestoneScenarioSerializer(serializers.Serializer):
    active_scenario_id = serializers.CharField()
    started_by = serializers.CharField()
    start_time = serializers.DateTimeField()
    participant_id = serializers.CharField()
    team = serializers.CharField()
    total_score = serializers.IntegerField()
    total_obtained_score = serializers.IntegerField()
    console_url = serializers.URLField()
    scenario = ScenarioListSerializer()
    document_urls = serializers.ListField(child=serializers.URLField())
    milestones = MilestoneSerializer(many=True)
    total_milestone_count = serializers.IntegerField()
    approved_milestone_count = serializers.IntegerField()


