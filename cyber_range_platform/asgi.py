import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

from notification_management.routing import websocket_urlpatterns as notification_websocket_urlpatterns
from corporate_management.routing import corporate_websocket_urlpatterns as corporate_websocket_urlpatterns


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cyber_range_platform.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            # Define separate URL patterns for notification and corporate management
            *notification_websocket_urlpatterns,
            *corporate_websocket_urlpatterns,
        ])
    ),
})