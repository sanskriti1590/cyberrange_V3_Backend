from rest_framework import serializers


class AssetExecutionRequestSerializer(serializers.Serializer):
    asset_ids = serializers.ListField(
        child=serializers.CharField(), allow_empty=False
    )
    run_elevated = serializers.BooleanField(default=False)
