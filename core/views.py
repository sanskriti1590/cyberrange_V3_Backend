from rest_framework import generics, status
from rest_framework.response import Response
from ctf_management.views import CTFDeleteGameView
from scenario_management.views import ScenarioGameDeleteView
from user_management.permissions import CustomIsSuperAdmin
from .serializers import MailingListSerializer, InstanceEssentialsSerializer, TotalResourcesSerializer, NewsListSerializer
from drf_yasg.utils import swagger_auto_schema


class CTFForceDeleteGameView(CTFDeleteGameView):
    permission_classes = [CustomIsSuperAdmin]
    

class MailingListView(generics.CreateAPIView):
    serializer_class = MailingListSerializer

    @swagger_auto_schema(
        request_body=MailingListSerializer,
        operation_summary="Mailing List Registration",
        responses={201: "Success", 400: "Bad Request"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            response = serializer.data
            response['message'] = "Mailing List Registration: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class InstanceEssentialsView(generics.ListAPIView):
    serializer_class = InstanceEssentialsSerializer
    
    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset
    
    @swagger_auto_schema(
        operation_summary="Instance Essentials",
        responses={200: InstanceEssentialsSerializer(), 400: "Bad Request"},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)    
        

class ScenarioForceDeleteGameView(ScenarioGameDeleteView):
    permission_classes = [CustomIsSuperAdmin]

class TotalResourcesView(generics.ListAPIView):
    serializer_class = TotalResourcesSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset
    
    @swagger_auto_schema(
        operation_summary="Total Resources",
        responses={200: TotalResourcesSerializer(), 400: "Bad Request"},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)   
    

class NewsListView(generics.ListAPIView):
    serializer_class = NewsListSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        operation_summary="News List",
        responses={200: NewsListSerializer(), 400: "Bad Request"},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)