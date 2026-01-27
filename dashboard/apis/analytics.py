from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from dashboard.serializers.analytics import AnalyticsSerializer
from dashboard.services.analytics import AnalyticsServices
from user_management.permissions import CustomIsSuperAdmin


class AnalyticsAPIView(APIView):
    permission_classes = [CustomIsSuperAdmin]

    def get(self, request):
        analytics_data = AnalyticsServices.get_analytics()
        if "error" in analytics_data:
            return Response(analytics_data, status=status.HTTP_400_BAD_REQUEST)

        serializer = AnalyticsSerializer(data=analytics_data)
        if serializer.is_valid():
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
