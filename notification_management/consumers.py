import pymongo

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from database_management.pymongo_client import notification_group_collection, notification_collection
from user_management.utils import get_user_from_access_token
from database_management.pymongo_client import user_collection

class NotificationConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.group_name = self.scope['url_route']['kwargs']['group_name']
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def receive(self, text_data):
        await self.send_json(text_data)

    # async def receive_json(self, content, **kwargs):
    #     print("\n\n Data Received from Client: \n", content, "\n\n")
    #     await self.send_json(content)
        # token = content['token']

        # try:
        #     user = get_user_from_access_token(token)
        #     user_id = user['user_id']

        #     user = user_collection.find_one({'user_id': user_id}, {'_id': 0})

        #     if not user:
        #         await self.close()
        #         return
            
        #     if self.group_name != user_id:
        #         await self.close()
        #         return

        #     # Add the WebSocket connection to the group
        #     self.group_name = self.scope['url_route']['kwargs']['group_name']
        #     await self.channel_layer.group_add(self.group_name, self.channel_name)
        #     notifications = list(notification_collection.find({"group_name": self.group_name}, {"_id": 0}).sort([("date", pymongo.DESCENDING)]))
        #     await self.channel_layer.group_send(self.group_name, {
        #         'type': 'notification.message',
        #         'notifications': notifications
        #     })

        # except Exception as e:
        #     print("\n\n", e, "\n\n")
        #     await self.close()
        #     return 


    # async def notification_message(self, notification):
    #     print("\n\n 11 \n\n")
    #     await self.send_json({
    #         'notification': notification
    #     })
    #     print("\n\n 22 \n\n")

    async def notification_message(self, event):
        await self.send_json({
            'notifications': event['notification']
        })        
        
    async def disconnect(self, close_code):         
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        