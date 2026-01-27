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
    CorporateGenerateScenarioReportSerializer,
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
    CorporateScenarioAdminToggleFlagLockSerializer,
    CorporateScenarioAdminToggleMilestoneLockSerializer,
    CorporateScenarioAdminTogglePhaseLockSerializer
)
from corporate_management.api.serializers.scenario import ActiveScenarioIPListSerializer
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
    

class CorporateScenarioWalkthroughListView(APIView):
    permission_classes = [CustomIsAuthenticated]

    def get(self, request):
        scenario_id = request.query_params.get("scenario_id")
        team = request.query_params.get("team")
        phase_ids = request.query_params.getlist("phase_ids")

        if not scenario_id or not team or not phase_ids:
            return Response(
                {"errors": "scenario_id, team, and phase_ids are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CorporateScenarioWalkthroughListSerializer()
        docs = serializer.get(
            scenario_id=scenario_id,
            team=team,
            phase_ids=phase_ids
        )

        return Response(
            {"walkthroughs": docs},
            status=status.HTTP_200_OK
        )
    
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
    serializer_class = CorporateScenarioModeratorConsoleDetailSerializer
    permission_classes = [CustomIsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            scenario = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

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
    

class CorporateGenerateScenarioReportView(generics.ListAPIView):
    # permission_classes=[CustomIsAuthenticated]
    serializer_class = CorporateGenerateScenarioReportSerializer
    def get_queryset(self):
        active_scenario_id = self.kwargs['active_scenario_id']
        participant_id = self.kwargs['user_id']
        return self.serializer_class().get(active_scenario_id,participant_id)
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        try :
            if queryset.headers.get('Content-Type') == "application/pdf":
                return queryset
            else:
                return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        
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

class CorporateScenarioAdminToggleFlagLockView(generics.GenericAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioAdminToggleFlagLockSerializer

    @swagger_auto_schema(
        request_body=CorporateScenarioAdminToggleFlagLockSerializer,
        operation_summary="Admin lock/unlock a flag during gameplay",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response(result, status=status.HTTP_200_OK)

class CorporateScenarioAdminToggleMilestoneLockView(generics.GenericAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioAdminToggleMilestoneLockSerializer

    @swagger_auto_schema(
        request_body=CorporateScenarioAdminToggleMilestoneLockSerializer,
        operation_summary="Admin lock/unlock a milestone during gameplay",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response(result, status=status.HTTP_200_OK)

class CorporateScenarioAdminTogglePhaseLockView(generics.GenericAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CorporateScenarioAdminTogglePhaseLockSerializer

    @swagger_auto_schema(
        request_body=CorporateScenarioAdminTogglePhaseLockSerializer,
        operation_summary="Admin lock/unlock an entire kill-chain phase",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response(result, status=status.HTTP_200_OK)

    