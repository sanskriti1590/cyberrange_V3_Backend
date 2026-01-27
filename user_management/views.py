from rest_framework import generics, status
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from .permissions import CustomIsAuthenticated, CustomIsAdmin, IsAuthenticatedNotVerified
from .serializers import (
    UserRegisterSerializer, 
    UserLoginSerializer, 
    CustomTokenRefreshSerializer, 
    VerifyOTPSerializer,
    SendOTPSerializer,
    UserAvatarSerializer,
    UnverifiedUserDetailSerializer,
    UserDetailSerializer,
    UserListSerializer,
    TopPerformerSerializer,
    CommonWinningWallSerializer,
    ForgotPasswordSerializer,
    UpdatePasswordSerializer,
)


class UserRegisterView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer

    @swagger_auto_schema(
        request_body=UserRegisterSerializer,
        responses={201: UserRegisterSerializer()},
        operation_summary="Register a new user",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            response = serializer.data
            response['message'] = "User Registration: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class UserLoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer

    @swagger_auto_schema(
        request_body=UserLoginSerializer,
        responses={200: UserLoginSerializer()},
        operation_summary="Login user",
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            login_token = serializer.save()
            response = serializer.data
            response['message'] = "User Login: Successful"
            return Response(response, status=status.HTTP_200_OK)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class CustomTokenRefreshView(generics.GenericAPIView):
    # permission_classes = [CustomIsAuthenticated]
    serializer_class = CustomTokenRefreshSerializer

    @swagger_auto_schema(
        request_body=CustomTokenRefreshSerializer,
        responses={200: CustomTokenRefreshSerializer()},
        operation_summary="Refresh user token",
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            token = serializer.save()
            response = serializer.data
            response['message'] = "User Token Refresh: Successful"
            return Response(response, status=status.HTTP_200_OK)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class SendOTPView(generics.CreateAPIView):
    permission_classes = [IsAuthenticatedNotVerified]
    serializer_class = SendOTPSerializer

    @swagger_auto_schema(
        request_body=SendOTPSerializer,
        responses={200: SendOTPSerializer()},
        operation_summary="Send OTP",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            capture_flag = serializer.save()
            response = serializer.data
            response["message"] = "OTP Sent: Successful"
            return Response(response, status=status.HTTP_200_OK)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class VerifyOTPView(generics.CreateAPIView):
    permission_classes = [IsAuthenticatedNotVerified]
    serializer_class = VerifyOTPSerializer

    @swagger_auto_schema(
        request_body=VerifyOTPSerializer,
        responses={200: VerifyOTPSerializer()},
        operation_summary="Verify OTP",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            capture_flag = serializer.save()
            response = serializer.data
            if not "errors" in response.keys():
                response["message"] = "OTP Verification: Successful"
            return Response(response, status=status.HTTP_200_OK)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class UserAvatarView(generics.ListAPIView):
    serializer_class = UserAvatarSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset
    
    @swagger_auto_schema(
        responses={200: UserAvatarSerializer()},
        operation_summary="User Avatar List",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response(queryset)
    
    
class UnverifiedUserDetailView(generics.ListAPIView):
    permission_classes = [IsAuthenticatedNotVerified]
    serializer_class = UnverifiedUserDetailSerializer
    
    def get_queryset(self, user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(user_id)
        return queryset
    
    @swagger_auto_schema(
        responses={200: UnverifiedUserDetailSerializer()},
        operation_summary="Unverified User Detail",
    )
    def get(self, request, *args, **kwargs):
        user_id = request.user['user_id']
        queryset = self.get_queryset(user_id)
        return Response(queryset)
    

class UserDetailView(generics.ListAPIView):
    serializer_class = UserDetailSerializer

    def get_queryset(self, user, params_user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(user, params_user_id)
        return queryset
    
    @swagger_auto_schema(
        responses={200: UserDetailSerializer()},
        operation_summary="User Detail",
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        params_user_id = kwargs['user_id']
        queryset = self.get_queryset(user, params_user_id)
        return Response(queryset)
    

class UserListView(generics.ListAPIView):
    serializer_class = UserListSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        responses={200: UserListSerializer()},
        operation_summary="User List",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response(queryset)
    
     

class TopPerformerView(generics.ListAPIView):
    serializer_class = TopPerformerSerializer

    def get_queryset(self):
        return self.serializer_class().get()

    @swagger_auto_schema(
        responses={200: TopPerformerSerializer()},
        operation_summary="Top Performers List",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response(queryset)
    

class CommonWinningWallView(generics.ListAPIView):
    serializer_class = CommonWinningWallSerializer

    def get_queryset(self):
        keyword = self.kwargs['keyword']
        return self.serializer_class().get(keyword)
    
    @swagger_auto_schema(
        responses={200: CommonWinningWallSerializer()},
        operation_summary="Common Winning Wall",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response(queryset)
    
class ForgotPasswordView(generics.CreateAPIView):
    serializer_class = ForgotPasswordSerializer
    
    @swagger_auto_schema(
        request_body=ForgotPasswordSerializer,
        responses={200: ForgotPasswordSerializer()},
        operation_summary="Forgot Password",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            response = serializer.save()
            response["message"] = "OTP Sent: Successful"
            return Response(response, status=status.HTTP_200_OK)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class UpdatePasswordView(generics.CreateAPIView):
    serializer_class = UpdatePasswordSerializer

    @swagger_auto_schema(
        request_body=UpdatePasswordSerializer,
        responses={200: UpdatePasswordSerializer()},
        operation_summary="Update Password",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            response = serializer.save()
            response["message"] = "Password has been updated successfully"
            return Response(response, status=status.HTTP_200_OK)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
