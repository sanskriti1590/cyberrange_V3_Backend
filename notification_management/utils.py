import datetime
from channels.layers import get_channel_layer

from database_management.pymongo_client import notification_collection
from core.utils import generate_random_string


async def send_notification(group_name=""):
    channel_layer = get_channel_layer()

    await channel_layer.group_send(group_name, {
        'type': 'notification.message',
        'notification': "New Notification Added"
    })
