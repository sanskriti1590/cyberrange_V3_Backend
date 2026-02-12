from django.shortcuts import render
from rest_framework import generics, status, views
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from asgiref.sync import async_to_sync
from threading import Thread
from rest_framework.views import APIView


from corporate_management.serializers import _sanitize_meta
from dashboard.services.corporate import CorporateScenarioService
from user_management.permissions import CustomIsAuthenticated, CustomIsAdmin, CustomIsSuperAdmin
from .serializers import (
    CorporateScenarioCreateSerializer,
    CorporateScenarioInfraSerializer,
    CorporateScenarioListSerializer,
    CorporateScenarioDetailSerializer,
    CorporateScenarioWalkthroughCreateSerializer,
    CorporateScenarioWalkthroughListSerializer,
    CorporateScenarioStartSerializer,
    CorporateScenarioConsoleSerializer,
    CorporateScenarioSubmitFlagSerializer,
    CorporateScenarioAchieveMilestoneSerializer,
    CorporateScenarioApproveMilestoneSerializer,
    CorporateScenarioRejectMilestoneSerializer,
    CorporateScenarioShowHintSerializer,
    CorporateActiveScenarioSerializer,
    CorporateScenarioModeratorSerializer,
    CorporateScenarioModeratorConsoleSerializer,
    CorporateActiveScenarioDeleteSerializer,
    CorporateScenarioModeratorConsoleDetailSerializer,
    CorporateByCategoryIdSerializer,
    CorporateExecutiveScenarioReportSerializer,
    CorporateScenarioEvidenceReportSerializer,
    CorporateUserReportSerializer,
    ActiveScenarioParticipantsSerializer,
    CorporateScenarioAchiversSerializer,
    CorporateUserReportApiSerializer,
    FlagStatusSerializer,
    CorporateTopologySerializer,
    CorporateScenarioPhaseSerializer,
    CorporateScenarioFlagCreateSerializer,
    CorporateScenarioMilestoneCreateSerializer,
    CorporateScenarioInfraDetailSerializer,
    CorporateScenarioSwitchMachineSerializer,
    ScenarioChatSendSerializer,
    ScenarioChatMessageListSerializer,
)
from corporate_management.api.serializers.scenario import ActiveScenarioIPListSerializer
from corporate_management.services.chat_access import build_chat_channels
from .utils import corporate_send_notification,send_notification_reload


class CorporateScenarioPhaseCreateView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioPhaseSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.save(), status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=400)


class CorporateScenarioFlagCreateView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioFlagCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.save(), status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=400)


class CorporateScenarioMilestoneCreateView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioMilestoneCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.save(), status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=400)

class CorporateScenarioCreateView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request}  # ✅ THIS WAS MISSING
        )

        if not serializer.is_valid():
            print("❌ SCENARIO CREATE ERRORS:", serializer.errors)
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        scenario = serializer.save()
        return Response(
            scenario,  # ← RETURN ACTUAL OBJECT
            status=status.HTTP_201_CREATED
        )
    

class CorporateScenarioInfraView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioInfraSerializer
    
    def create(self, request, *args, **kwargs):
        scenario_id = request.query_params.get('scenario_id')
        serializer = self.get_serializer(data=request.data, context={'scenario_id': scenario_id, 'request': request})
        if serializer.is_valid():
            scenario = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class CorporateScenarioListView(generics.ListAPIView):
    serializer_class = CorporateScenarioListSerializer
    
    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)


class CorporateScenarioDetailView(generics.RetrieveAPIView):
    serializer_class = CorporateScenarioDetailSerializer
    permission_classes = [CustomIsAuthenticated]

    def get_queryset(self, scenario_id, user):
        serializer = self.serializer_class()
        queryset = serializer.get(scenario_id, user)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['scenario_id'], request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        queryset.pop("_id", None)
        return Response(queryset, status=status.HTTP_200_OK)
    

class CorporateScenarioAchiversView(generics.RetrieveAPIView):
    serializer_class = CorporateScenarioAchiversSerializer

    def get_queryset(self, scenario_id):
        serializer = self.serializer_class()
        queryset = serializer.get(scenario_id)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['scenario_id'])

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        return Response(queryset, status=status.HTTP_200_OK)
    

class CorporateScenarioStartView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioStartSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request}  
        )

        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)

        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

class ActiveCorporateScenarioGetipView(views.APIView):
    # permission_classes = [CustomIsAuthenticated]

    def get(self, request, active_scenario_id):
        scenario = CorporateScenarioService.get_active_scenario_ips(active_scenario_id=active_scenario_id)

        if 'errors' in scenario:
            return Response(scenario, status=status.HTTP_400_BAD_REQUEST)

        serializer = ActiveScenarioIPListSerializer(scenario)
        return Response(serializer.data)

class CorporateScenarioConsoleView(generics.RetrieveAPIView):
    serializer_class = CorporateScenarioConsoleSerializer
    permission_classes = [CustomIsAuthenticated]

    def get_queryset(self, active_scenario_id, user):
        serializer = self.serializer_class()
        queryset = serializer.get(active_scenario_id, user)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['active_scenario_id'], request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        queryset.pop("_id", None)
        return Response(queryset, status=status.HTTP_200_OK)
    

class CorporateScenarioWalkthroughCreateView(APIView):
    permission_classes = [CustomIsAuthenticated]

    def post(self, request):
        serializer = CorporateScenarioWalkthroughCreateSerializer(
            data=request.data,
            context={"request": request}
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        result = serializer.save()

        return Response(
            result,
            status=status.HTTP_201_CREATED
        )
    
class CorporateScenarioWalkthroughListView(APIView):
    permission_classes = [CustomIsAuthenticated]

    def get(self, request):
        scenario_id = request.query_params.get("scenario_id")
        team = request.query_params.get("team")

        if not scenario_id or not team:
            return Response(
                {"errors": "scenario_id and team required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CorporateScenarioWalkthroughListSerializer()
        files = serializer.get(scenario_id, team)

        return Response({"walkthroughs": files})
    
class CorporateScenarioSubmitFlagView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioSubmitFlagSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.save()

        # respond first (SAFE)
        response = Response(result, status=status.HTTP_201_CREATED)

        if result.get("is_correct") is True:
            Thread(
                target=corporate_send_notification,
                kwargs={"group_name": request.data["active_scenario_id"]}
            ).start()

        return response
    

class CorporateScenarioAchieveMilestoneView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioAchieveMilestoneSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            scenario = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            if response:
                async_to_sync(send_notification_reload)(group_name=request.data["active_scenario_id"])
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class CorporateScenarioApproveMilestoneView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioApproveMilestoneSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            scenario = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            if response:
                async_to_sync(corporate_send_notification)(group_name=request.data["active_scenario_id"])
                async_to_sync(send_notification_reload)(group_name=request.data["active_scenario_id"])
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class CorporateScenarioRejectMilestoneView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioRejectMilestoneSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            scenario = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            if response:
                async_to_sync(send_notification_reload)(group_name=request.data["active_scenario_id"])
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class CorporateScenarioShowHintView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioShowHintSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            scenario = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class CorporateActiveScenarioView(generics.RetrieveAPIView):
    serializer_class = CorporateActiveScenarioSerializer
    permission_classes = [CustomIsAuthenticated]

    def get_queryset(self, user):
        serializer = self.serializer_class()
        queryset = serializer.get(user)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    

class CorporateScenarioModeratorView(generics.RetrieveAPIView):
    serializer_class = CorporateScenarioModeratorSerializer
    permission_classes = [CustomIsAuthenticated]

    def get_queryset(self, user):
        serializer = self.serializer_class()
        queryset = serializer.get(user)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    

class CorporateScenarioModeratorConsoleView(generics.RetrieveAPIView):
    serializer_class = CorporateScenarioModeratorConsoleSerializer
    permission_classes = [CustomIsAuthenticated]

    def get_queryset(self, user):
        serializer = self.serializer_class()
        queryset = serializer.get(user)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    

class CorporateActiveScenarioDeleteView(generics.RetrieveAPIView):
    serializer_class = CorporateActiveScenarioDeleteSerializer
    permission_classes = [CustomIsAuthenticated]

    def get_queryset(self, active_scenario_id, user):
        serializer = self.serializer_class()
        queryset = serializer.get(active_scenario_id, user)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['active_scenario_id'], request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    
class CorporateScenarioModeratorConsoleDetailView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioModeratorConsoleDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.save()

        return Response(result, status=status.HTTP_200_OK)

class CorporateByCategoryIdView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateByCategoryIdSerializer

    def get_queryset(self):
        category_id = self.kwargs['category_id']
        user_id = self.request._user['user_id']
        return self.serializer_class().get(category_id, user_id)
    
    @swagger_auto_schema(
        responses={200: CorporateByCategoryIdSerializer()},
        operation_summary="Retrieve Corporate by category ID",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)
    
class CorporateExecutiveScenarioReportView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateExecutiveScenarioReportSerializer

    def get_queryset(self):
        archive_scenario_id = self.kwargs["archive_scenario_id"]
        team_group = self.kwargs["team_group"]

        return self.serializer_class().get(
            archive_scenario_id,
            team_group
        )

    def get(self, request, *args, **kwargs):
        data = self.get_queryset()

        if "errors" in data:
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)

class CorporateScenarioEvidenceReportView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioEvidenceReportSerializer

    def get_queryset(self):
        archive_scenario_id = self.kwargs["archive_scenario_id"]
        team_group = self.kwargs["team_group"]

        return self.serializer_class().get(
            archive_scenario_id,
            team_group
        )

    def get(self, request, *args, **kwargs):
        data = self.get_queryset()

        if "errors" in data:
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)
        
class CorporateUserReportView(generics.ListAPIView):
    permission_classes=[CustomIsAuthenticated]
    serializer_class = CorporateUserReportSerializer

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        return self.serializer_class().get(user_id)
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)
    
 #active_participants    
class ActiveParticipantView(generics.ListAPIView):
    serializer_class = ActiveScenarioParticipantsSerializer
    
    def get_queryset(self):
        user_id = self.kwargs['active_scenario_id']
        return self.serializer_class().get(user_id)
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)


class CorporateUserReportApi(generics.ListAPIView):
    permission_classes=[CustomIsAuthenticated]
    serializer_class = CorporateUserReportApiSerializer

    def get_queryset(self):
        participant_id = self.kwargs['participant_id']
        user_id = self.kwargs['user_id']
        return self.serializer_class().get(participant_id,user_id)
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)
    


class FlagStatusView(generics.ListAPIView):
    permission_classes=[CustomIsAuthenticated]
    serializer_class = FlagStatusSerializer

    def get_queryset(self):
        participant_id = self.kwargs['participant_id']
        flag_id = self.kwargs['flag_id']
        return self.serializer_class().get(participant_id,flag_id)
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)


class CorporateTopologyView(generics.ListAPIView):
    serializer_class = CorporateTopologySerializer

    def get_queryset(self):
        scenario_id = self.kwargs['scenario_id']
        return self.serializer_class().get(scenario_id)
    
    @swagger_auto_schema(
        responses={200: CorporateTopologySerializer()},
        operation_summary="Retrieve topology of a scenario",
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(queryset, status=status.HTTP_200_OK)


class CorporateScenarioInfraDetailView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioInfraDetailSerializer

    def get_queryset(self):
        infra_id = self.kwargs['infra_id']
        return self.serializer_class().get(infra_id)

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        return Response(queryset, status=status.HTTP_200_OK)

class CorporateScenarioSwitchMachineView(generics.GenericAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioSwitchMachineSerializer

    @swagger_auto_schema(
        request_body=CorporateScenarioSwitchMachineSerializer,
        operation_summary="Switch console machine for participant",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response(result, status=status.HTTP_200_OK)


#chat view
class ScenarioChatChannelsView(APIView):
    permission_classes = [CustomIsAuthenticated]

    def get(self, request, active_scenario_id):
        channels = build_chat_channels(active_scenario_id, request.user)  # ✅ correct order
        return Response({"channels": channels})


class ScenarioChatMessagesView(APIView):
    permission_classes = [CustomIsAuthenticated]

    def get(self, request, channel_key):
        serializer = ScenarioChatMessageListSerializer()
        messages = serializer.get(channel_key)
        return Response({"messages": messages})

class ScenarioChatSendView(APIView):
    permission_classes = [CustomIsAuthenticated]

    def post(self, request):
        serializer = ScenarioChatSendSerializer(
            data=request.data,
            context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        msg = serializer.save()

        # 🔍 HARD DEBUG — DO NOT SKIP
        from bson import ObjectId
        import json

        def find_objectid(obj, path="root"):
            if isinstance(obj, ObjectId):
                raise RuntimeError(f"ObjectId found at {path}")
            if isinstance(obj, dict):
                for k, v in obj.items():
                    find_objectid(v, f"{path}.{k}")
            if isinstance(obj, list):
                for i, v in enumerate(obj):
                    find_objectid(v, f"{path}[{i}]")

        find_objectid(msg)

        # If this line runs, msg is clean
        json.dumps(msg)

        return Response(msg, status=status.HTTP_201_CREATED)