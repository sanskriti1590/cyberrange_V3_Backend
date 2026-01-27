from django.urls import path

from dashboard.apis.users import UserListAPIView, MyProfileAPIView

urlpatterns = [
    path("", UserListAPIView.as_view(), name="get_all_users"),
    path("me", MyProfileAPIView.as_view(), name="get_my_profile"),
]
