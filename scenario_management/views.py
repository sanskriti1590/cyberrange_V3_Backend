from rest_framework import generics, status
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from user_management.permissions import CustomIsAuthenticated, CustomIsAdmin, CustomIsSuperAdmin

from .serializers import (
    ScenarioCategorySerializer,
    ScenarioCreateSerializer,
    ScenarioGameDraftSerializer,
    ScenarioInfraCreateSerializer,
    ScenarioListSerializer,
    ScenarioGameStartSerializer,
    ScenarioAcceptInvitationSerializer,
    ScenarioDenyInvitationSerializer,
    ScenarioGameConsoleSerializer,
    ScenarioActiveGameListSerializer,
    ScenarioGameDetailSerializer,
    ScenarioGameDeleteSerializer,
    ScenarioSubmitFlagSerializer,
    ScenariosByCategoryIdSerializer,
    ScenarioTopologySerializer,
    ScenarioUserEmailStatusSerializer,
    ScenarioIPListSerializer,
)

class ScenarioCategoryListView(generics.ListAPIView):
    serializer_class = ScenarioCategorySerializer
    
    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset
    
    @swagger_auto_schema(
        responses={200: ScenarioCategorySerializer(many=True)},
        operation_summary="List all scenario categories",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)    
        


class ScenarioCreateView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenarioCreateSerializer

    @swagger_auto_schema(
        request_body=ScenarioCreateSerializer,
        responses={201: ScenarioCreateSerializer()},
        operation_summary="Create a new scenario",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            scenario = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class ScenarioGameDraftView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenarioGameDraftSerializer

    def get_queryset(self, user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(user_id)
        return queryset

    @swagger_auto_schema(
        responses={200: ScenarioGameDraftSerializer(many=True)},
        operation_summary="List all draft scenarios",
        security=[{"Bearer": []}]
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(request.user['user_id'])

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    

class ScenarioInfraCreateView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenarioInfraCreateSerializer

    @swagger_auto_schema(
        request_body=ScenarioInfraCreateSerializer,
        responses={201: ScenarioInfraCreateSerializer()},
        operation_summary="Create infrastructure for a scenario",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            scenario_infra = serializer.save()
            response = serializer.data
            response['message'] = "Scenario Infra Upload: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class ScenarioListView(generics.ListAPIView):
    def get_permissions(self):
        # Check if the request has an Authorization header with a token
        if 'HTTP_AUTHORIZATION' in self.request.META:
            permission_classes = [CustomIsAuthenticated]
        else:
            permission_classes = []

        return [permission() for permission in permission_classes]
    
    serializer_class = ScenarioListSerializer

    def get_queryset(self, user_id= None):
        serializer = self.serializer_class()
        queryset = serializer.get(user_id)
        return queryset
    
    @swagger_auto_schema(
        responses={200: ScenarioListSerializer(many=True)},
        operation_summary="List all scenarios",
    )
    def get(self, request, *args, **kwargs):
        try:
            user_id = request.user['user_id']
        except:
            user_id = None
        queryset = self.get_queryset(user_id)
        
        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    

class ScenarioGameStartView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenarioGameStartSerializer

    @swagger_auto_schema(
        request_body=ScenarioGameStartSerializer,
        responses={201: ScenarioGameStartSerializer()},
        operation_summary="Start a scenario game",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            scenario_invitation = serializer.save()
            response = serializer.data
            response['message'] = "Please wait while we are creating dedicated environment for you."
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class ScenarioAcceptInvitationView(generics.ListAPIView):
    serializer_class = ScenarioAcceptInvitationSerializer

    def get_queryset(self, invitation_id):
        serializer = self.serializer_class()
        queryset = serializer.get(invitation_id)
        return queryset

    @swagger_auto_schema(
        responses={200: ScenarioAcceptInvitationSerializer()},
        operation_summary="Accept invitation to join a scenario game",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['invitation_id'])
        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    

class ScenarioDenyInvitationView(generics.ListAPIView):
    serializer_class = ScenarioDenyInvitationSerializer

    def get_queryset(self, invitation_id):
        serializer = self.serializer_class()
        queryset = serializer.get(invitation_id)
        return queryset

    @swagger_auto_schema(
        responses={200: ScenarioDenyInvitationSerializer()},
        operation_summary="Deny invitation to join a scenario game",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['invitation_id'])
        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    

class ScenarioGameConsoleView(generics.RetrieveAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenarioGameConsoleSerializer

    def get_queryset(self, scenario_game_id, user):
        serializer = self.serializer_class()
        queryset = serializer.get(scenario_game_id, user)
        return queryset
    
    @swagger_auto_schema(
        responses={200: ScenarioGameConsoleSerializer()},
        operation_summary="Retrieve scenario game console details",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['scenario_game_id'], request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        queryset.pop("_id", None)
        return Response(queryset, status=status.HTTP_200_OK)
    

class ScenarioActiveGameListView(generics.RetrieveAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenarioActiveGameListSerializer

    def get_queryset(self, user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(user_id)
        return queryset
    
    @swagger_auto_schema(
        responses={200: ScenarioActiveGameListSerializer()},
        operation_summary="Retrieve active scenario game list",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(request.user.get('user_id'))

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        return Response(queryset, status=status.HTTP_200_OK)
    
class ScenarioGameDetailView(generics.RetrieveAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenarioGameDetailSerializer

    def get_queryset(self, scenario_id, user):
        serializer = self.serializer_class()
        user_id = self.request._user['user_id']
        queryset = serializer.get(scenario_id, user, user_id)
        return queryset
    
    @swagger_auto_schema(
        responses={200: ScenarioGameDetailSerializer()},
        operation_summary="Retrieve details of a scenario game",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['scenario_id'], request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        queryset.pop("_id", None)
        return Response(queryset, status=status.HTTP_200_OK)


class ScenarioSubmitFlagView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenarioSubmitFlagSerializer

    @swagger_auto_schema(
        responses={201: ScenarioSubmitFlagSerializer()},
        operation_summary="Submit flag for a scenario game",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            flag_submission = serializer.save()
            response = serializer.data
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class ScenarioGameDeleteView(generics.DestroyAPIView):
    permission_classes = [CustomIsAuthenticated]

    serializer_class = ScenarioGameDeleteSerializer

    @swagger_auto_schema(
        responses={202: ScenarioGameDeleteSerializer()},
        operation_summary="Delete a scenario game",
    )
    def delete(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            scenario_game_id = self.kwargs.get('scenario_game_id')
            # delete_scenario_game_task.delay(scenario_game_id)
            scenario_archive_game = serializer.delete_game(scenario_game_id)
            
            response = scenario_archive_game
            response['message'] = 'Scenario Game Deletion: Successful'
            response.pop("_id", None)
            return Response(response, status=status.HTTP_202_ACCEPTED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
  
    
class ScenariosByCategoryIdView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenariosByCategoryIdSerializer

    def get_queryset(self):
        category_id = self.kwargs['category_id']
        user_id = self.request._user['user_id']
        return self.serializer_class().get(category_id, user_id)
    
    @swagger_auto_schema(
        responses={200: ScenariosByCategoryIdSerializer()},
        operation_summary="Retrieve scenarios by category ID",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)


class ScenarioTopologyView(generics.ListAPIView):
    serializer_class = ScenarioTopologySerializer

    def get_queryset(self):
        scenario_id = self.kwargs['scenario_id']
        return self.serializer_class().get(scenario_id)
    
    @swagger_auto_schema(
        responses={200: ScenarioTopologySerializer()},
        operation_summary="Retrieve topology of a scenario",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)
    
class ScenarioUserEmailStatusView(generics.ListAPIView):
    serializer_class = ScenarioUserEmailStatusSerializer

    def get_queryset(self):
        email = self.kwargs['email']
        return self.serializer_class().get(email)
    
    @swagger_auto_schema(
        responses={200: ScenarioUserEmailStatusSerializer()},
        operation_summary="Retrieve status of a user's email",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)


class ScenarioIPListView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = ScenarioIPListSerializer

    def get_queryset(self):
        user_id = self.request._user['user_id']
        scenario_game_id = self.kwargs['scenario_game_id']
        return self.serializer_class().get(scenario_game_id, user_id)
    
    @swagger_auto_schema(
        responses={200: ScenarioIPListSerializer()},
        operation_summary="Retrieve IP list for a scenario game",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)