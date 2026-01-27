from django.urls import re_path, path

from . import consumers

corporate_websocket_urlpatterns = [
    path('corporate/notification/<slug:group_name>/', consumers.NotificationConsumer.as_asgi()),
]