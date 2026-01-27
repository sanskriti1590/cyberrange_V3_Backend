from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import NotificationPartialListView

app_name = "notification-management"

urlpatterns = [
    path('', NotificationPartialListView.as_view(), name='notification-partial-list'),
]

urlpatterns = format_suffix_patterns(urlpatterns)