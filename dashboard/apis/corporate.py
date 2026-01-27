from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from dashboard.serializers.corporate import ScenarioListSerializer, ActiveScenarioListSerializer, ActiveScenarioDetailSerializer, ConsoleMilestoneScenarioSerializer, ConsoleFlagScenarioSerializer
from dashboard.serializers.scenario.corporate.details import CorporateScenarioDetailSerializer
from dashboard.services.corporate import CorporateScenarioService
from dashboard.utils.paginations import DefaultPagination
from user_management.permissions import CustomIsSuperAdmin


class ScenariosListAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def get(self, request):
        is_approved = request.query_params.get('approved')
        is_prepared = request.query_params.get('prepared')
        category_id = request.query_params.get('category_id')

        scenarios = CorporateScenarioService.get_all_scenarios(is_approved=is_approved, is_prepared=is_prepared, category_id=category_id)

        # Paginate manually
        paginator = DefaultPagination()
        paginated_scenarios = paginator.paginate_queryset(scenarios, request, view=self)

        serializer = ScenarioListSerializer(paginated_scenarios, many=True)
        return paginator.get_paginated_response(serializer.data)

class ScenarioDetailAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def get(self, request, scenario_id):
        response_data = CorporateScenarioService.get_scenarios_detail(scenario_id)

        if "errors" in response_data:
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        serializer = CorporateScenarioDetailSerializer(response_data)
        return Response(serializer.data)


class ActiveScenariosListAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def get(self, request):
        scenarios = CorporateScenarioService.get_active_scenarios()

        # Paginate manually
        paginator = DefaultPagination()
        paginated_scenarios = paginator.paginate_queryset(scenarios, request, view=self)

        serializer = ActiveScenarioListSerializer(paginated_scenarios, many=True)
        return paginator.get_paginated_response(serializer.data)


class ActiveScenarioDetailAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def get(self, request, id):
        scenario = CorporateScenarioService.get_single_active_scenario(active_scenario_id=id)

        if 'errors' in scenario:
            return Response(scenario, status=status.HTTP_400_BAD_REQUEST)

        serializer = ActiveScenarioDetailSerializer(scenario, many=False)
        return Response(serializer.data)


class ActiveScenarioConsoleAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def get(self, request, id):
        participant = request.query_params.get('participant')
        response_data = CorporateScenarioService.get_console(active_scenario_id=id, participant_id=participant)

        if 'errors' in response_data:
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        scenario_type = response_data.get("scenario", {}).get("type")

        if scenario_type == "FLAG":
            serializer = ConsoleFlagScenarioSerializer(response_data)
        elif scenario_type == "MILESTONE":
            serializer = ConsoleMilestoneScenarioSerializer(response_data)
        else:
            return Response(
                {"errors": {"scenario": ["Unknown scenario type"]}},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.data)


class StartScenarioAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def post(self, request, id):
        response_data = CorporateScenarioService.start_scenario(request=request, scenario_id=id)

        if 'errors' in response_data:
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        return Response(response_data)


class EndScenarioAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def post(self, request, id):
        user_id = request.user.get('user_id')
        response_data = CorporateScenarioService.end_scenarios(active_scenario_id=id, user_id=user_id)

        if 'errors' in response_data:
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        return Response(response_data)
