from rest_framework import permissions
from django.urls import path, include

from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="CyberRange API Documentation",
      default_version='v2.1',
      description="User authentication",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="support@bhumiitech.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(),
   authentication_classes=[],
)

urlpatterns = [

    path('api/user/', include('user_management.urls', namespace="user-management")),
    path('api/database/', include('database_management.urls', namespace="database-management")),
    path('api/ctf/', include('ctf_management.urls', namespace="ctf-management")),
    path('api/core/', include('core.urls', namespace="core")),
    path('api/scenario/', include('scenario_management.urls', namespace="scenario-management")),
    path('api/challenge/', include('challenge_management.urls', namespace="challenge")),
    path('api/admin/', include('admin_management.urls', namespace="admin")),
    path('api/notification/', include('notification_management.urls', namespace="notification")),
    path('api/corporate/', include('corporate_management.urls', namespace="corporate-management")),


    path('api/', include('cyber_range_platform.api_urls', namespace="webbased_api")),

    path('api/swagger/5db89e7472f81a4ea6b7a73f7c6729f1/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]
