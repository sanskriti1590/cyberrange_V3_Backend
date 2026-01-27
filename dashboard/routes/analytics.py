from django.urls import path

from dashboard.apis.analytics import AnalyticsAPIView

urlpatterns = [
    path("", AnalyticsAPIView.as_view(), name="get_analytics"),
]
