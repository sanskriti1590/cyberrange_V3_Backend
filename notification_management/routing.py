from django.urls import re_path, path

from . import consumers

websocket_urlpatterns = [
    path('notification/<slug:group_name>/', consumers.NotificationConsumer.as_asgi()),
]