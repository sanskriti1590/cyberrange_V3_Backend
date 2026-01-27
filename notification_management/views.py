from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import generics
from user_management.permissions import CustomIsAuthenticated, CustomIsAdmin
from .serializers import NotificationPartialListSerializer


class NotificationPartialListView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = NotificationPartialListSerializer

    def get_queryset(self,user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(user_id)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(request.user.get("user_id"))
        return Response(queryset)