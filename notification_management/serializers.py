from rest_framework import serializers
from database_management.pymongo_client import (
    user_collection,
    notification_collection
)


class NotificationPartialListSerializer(serializers.Serializer):
    
    def get(self, user_id):
        notifications = list(notification_collection.find({"user_id": user_id}, {"_id": 0}).sort('timestamp', -1))
        
        return notifications