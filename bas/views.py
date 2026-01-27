# views.py
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AssetExecutionRequestSerializer

# Get the service from settings
four_core_attack_client_service = settings.FOUR_CORE_ATTACK_SERVICE


class AssetsView(APIView):
    def get(self, request):
        """
        Retrieve all assets.
        """
        try:
            data = four_core_attack_client_service.get_assets()
            return Response(data)
        except Exception as e:
            return Response(
                {"detail": f"Error retrieving assets: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class ChainsView(APIView):
    def get(self, request):
        """
        Retrieve a paginated list of chains.
        Supports `limit` (size) and `offset` as query parameters.
        Example: /api/chains?limit=10&offset=20
        """
        try:
            # Get query parameters with default values
            size = int(request.query_params.get('limit', 10))
            offset = int(request.query_params.get('offset', 0))

            # Optional filtering (e.g., by name, platform)
            filter_params = {}
            if 'name' in request.query_params:
                filter_params['filter[name]'] = request.query_params['name']
            if 'platforms' in request.query_params:
                filter_params['platforms'] = request.query_params['platforms']

            # Call the service
            data = four_core_attack_client_service.get_chains_list(
                size=size,
                offset=offset,
                filter_params=filter_params if filter_params else None
            )
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"detail": f"Error retrieving chains: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class ExecutionsView(APIView):
    def get(self, request):
        """
        Retrieve all executions.
        """
        try:
            data = four_core_attack_client_service.get_executions()
            return Response(data)
        except Exception as e:
            return Response(
                {"detail": f"Error retrieving executions: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class ExecutionReportView(APIView):
    def get(self, request, execution_id):
        """
        Retrieve a specific execution report.
        """
        try:
            data = four_core_attack_client_service.get_execution_report(execution_id=execution_id)
            return Response(data)
        except Exception as e:
            return Response(
                {"detail": f"Error retrieving execution report: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class ExecuteChainView(APIView):
    def post(self, request, chain_id):
        """
        Execute an attack chain by ID.
        """
        serializer = AssetExecutionRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                result = four_core_attack_client_service.execute_endpoint_attack_chain(
                    chain_id=chain_id,
                    assets=serializer.validated_data['asset_ids'],
                    run_elevated=serializer.validated_data['run_elevated']
                )
                return Response(result)
            except Exception as e:
                return Response(
                    {"detail": f"Error executing attack chain: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, chain_id):
        """
        Retrieve a specific chain detail.
        """
        try:
            data = four_core_attack_client_service.get_chains_detail(chain_id=chain_id)
            return Response(data)
        except Exception as e:
            return Response(
                {"detail": f"Error retrieving chain detail: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
