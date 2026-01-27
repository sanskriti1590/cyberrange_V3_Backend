from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import (
    UserRegisterView, 
    UserLoginView, 
    CustomTokenRefreshView, 
    SendOTPView,
    VerifyOTPView,
    UserAvatarView,
    UnverifiedUserDetailView,
    UserDetailView,
    UserListView,
    TopPerformerView,
    CommonWinningWallView,
    ForgotPasswordView, 
    UpdatePasswordView,
)


app_name = "user-management"


urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='refresh-token'),   
    path('avatar/list/', UserAvatarView.as_view(), name='user-avatars'), 
    path('unverified/', UnverifiedUserDetailView.as_view(), name='unverified-user'),
    path('detail/<slug:user_id>/', UserDetailView.as_view(), name='user-detail'),
    path('list/', UserListView.as_view(), name='user-list'),

    path('top-performer/', TopPerformerView.as_view(), name='top-performer'),

    path('common/winning-wall/<slug:keyword>/', CommonWinningWallView.as_view(), name='winning-wall'),

    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('update-password/', UpdatePasswordView.as_view(), name='update-password'),
    
]

urlpatterns = format_suffix_patterns(urlpatterns)
