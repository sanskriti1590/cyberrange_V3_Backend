from rest_framework import generics, status
from user_management.permissions import CustomIsAuthenticated, CustomIsAdmin, CustomIsSuperAdmin
from drf_yasg.utils import swagger_auto_schema
from rest_framework.response import Response
from .serializers import (GameChallengedListSerializer,
                          GameChallengeSerializer,
                          GameChallengeDeleteserializer,
                          )

# Create your views here.

class GameChallengedListView(generics.ListAPIView):
    serializer_class = GameChallengedListSerializer  

    def get_queryset(self, game_type):
        serializer = self.serializer_class()
        queryset = serializer.get(game_type)
        return queryset

    @swagger_auto_schema(
        operation_summary="Get list of game challenges",
        operation_description="Get a list of game challenges by game type",
        responses={200: GameChallengedListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['game_type'])

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK) 

class GameChallengeView(generics.ListCreateAPIView):
    serializer_class = GameChallengeSerializer  

    def get_permissions(self):
        if self.request.method == 'POST' or self.request.method == 'DELETE':
            return [CustomIsAdmin()]
        return []
    
    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        operation_summary="Get list of game challenges",
        operation_description="Get a list of game challenges",
        responses={200: GameChallengeSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)  

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            create_challenge = serializer.save()
            response = serializer.data
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class GameChallengeDeleteView(generics.DestroyAPIView):
    serializer_class = GameChallengeDeleteserializer
    permission_classes = [CustomIsAdmin]

    @swagger_auto_schema(
        operation_summary="Delete game challenge",
        operation_description="Delete an existing game challenge",
        responses={202: "{'message': 'Challenge Removed: Successful'}"},
    )
    def delete(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            mapping = serializer.save()
            response = serializer.data
            response['message'] = "Challenge Removed: Successful"
            return Response(response, status=status.HTTP_202_ACCEPTED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
