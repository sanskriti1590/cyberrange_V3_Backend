from rest_framework import serializers


# For simple use cases (name + one IP only)
class ActiveScenarioPrivateIPListSerializer(serializers.Serializer):
    name = serializers.CharField()
    ip = serializers.IPAddressField()


# For full IP data
class IPAddressSerializer(serializers.Serializer):
    network = serializers.CharField()
    addr = serializers.IPAddressField()
    type = serializers.CharField()
    mac = serializers.CharField()
    version = serializers.IntegerField()


class InstanceSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    ips = IPAddressSerializer(many=True)


class ActiveScenarioIPListSerializer(serializers.Serializer):
    id = serializers.CharField()
    instances = InstanceSerializer(many=True)
