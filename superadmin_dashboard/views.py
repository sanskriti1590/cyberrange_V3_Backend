# superadmin/views.py
from rest_framework import generics, status
from rest_framework.response import Response

from user_management.permissions import CustomIsAuthenticated, CustomIsAdmin, CustomIsSuperAdmin

from .serializers import *

class SuperAdminActiveScenariosView(generics.GenericAPIView):
    permission_classes = [CustomIsSuperAdmin]
    serializer_class = SuperAdminActiveScenarioListSerializer

    def get(self, request):
        data = self.get_serializer().get()
        return Response(data, status=status.HTTP_200_OK)

class SuperAdminActiveScenarioOverviewView(generics.GenericAPIView):
    permission_classes = [CustomIsSuperAdmin]
    serializer_class = SuperAdminActiveScenarioOverviewSerializer

    def get(self, request, active_scenario_id):
        data = self.get_serializer().get(active_scenario_id)
        if isinstance(data, dict) and data.get("errors"):
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        return Response(data, status=status.HTTP_200_OK)

class SuperAdminActiveScenarioLeaderboardView(generics.GenericAPIView):
    permission_classes = [CustomIsSuperAdmin]
    serializer_class = SuperAdminActiveScenarioLeaderboardSerializer

    def get(self, request, active_scenario_id):
        data = self.get_serializer().get(active_scenario_id)
        if isinstance(data, dict) and data.get("errors"):
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        return Response(data, status=status.HTTP_200_OK)

class SuperAdminManualScoreView(generics.CreateAPIView):
    permission_classes = [CustomIsSuperAdmin]
    serializer_class = SuperAdminManualScoreSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class SuperAdminToggleFlagLockView(generics.CreateAPIView):
    permission_classes = [CustomIsSuperAdmin]
    serializer_class = SuperAdminToggleFlagLockSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_200_OK)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class SuperAdminToggleMilestoneLockView(generics.CreateAPIView):
    permission_classes = [CustomIsSuperAdmin]
    serializer_class = SuperAdminToggleMilestoneLockSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_200_OK)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class SuperAdminTogglePhaseLockView(generics.CreateAPIView):
    permission_classes = [CustomIsSuperAdmin]
    serializer_class = SuperAdminTogglePhaseLockSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_200_OK)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)