from rest_framework import serializers


class FlagDataSerializer(serializers.Serializer):
    id = serializers.CharField()
    index = serializers.IntegerField(required=False)
    question = serializers.CharField(required=False, allow_blank=True)
    answer = serializers.CharField(required=False, allow_blank=True)
    hint = serializers.CharField(required=False, allow_blank=True)
    score = serializers.IntegerField(required=False, default=0)
    category_id = serializers.CharField(required=False, allow_blank=True)
    team = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class HardwareSummarySerializer(serializers.Serializer):
    vcpu = serializers.IntegerField(default=0)
    disk_size_gb = serializers.IntegerField(default=0)
    ram_gb = serializers.IntegerField(default=0)
    vm_count = serializers.IntegerField(default=0)


class FilesDataSerializer(serializers.Serializer):
    """Serializer for team-specific file URLs."""
    red_team = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    blue_team = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    purple_team = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    yellow_team = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )


class CreatorSerializer(serializers.Serializer):
    id = serializers.CharField()
    full_name = serializers.CharField(required=False, allow_blank=True)


class CategorySerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)


class CorporateScenarioDetailSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    severity = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    objective = serializers.CharField(required=False, allow_blank=True)
    prerequisite = serializers.CharField(required=False, allow_blank=True)
    thumbnail_url = serializers.CharField(required=False, allow_blank=True)

    files_data = FilesDataSerializer(required=False, default=dict)
    machine_names = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    hardware_details = HardwareSummarySerializer(required=False)
    points = serializers.IntegerField(default=0)
    flag_data_full = serializers.DictField(
        child=serializers.ListField(child=FlagDataSerializer()), required=False, default=dict
    )

    creator = CreatorSerializer(required=False)
    category = CategorySerializer(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)
