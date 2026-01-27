from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from dashboard.serializers.users import UserListSerializer, UserProfileSerializer
from dashboard.services.users import UserService
from dashboard.utils.paginations import DefaultPagination
from user_management.permissions import CustomIsSuperAdmin


class MyProfileAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def get(self, request):
        user = request.user
        users = UserService.get_user_profile_by_id(user_id=user.get('user_id'))

        serializer = UserProfileSerializer(users)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserListAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def get(self, request):
        role = request.query_params.get('team')

        is_active_param = request.query_params.get('status')
        is_active = None
        if is_active_param is not None:
            is_active = is_active_param.lower() == 'true'

        users = UserService.get_users_with_profiles(role=role, is_active=is_active)

        # Paginate manually
        paginator = DefaultPagination()
        paginated_users = paginator.paginate_queryset(users, request, view=self)

        serializer = UserListSerializer(paginated_users, many=True)
        return paginator.get_paginated_response(serializer.data)
