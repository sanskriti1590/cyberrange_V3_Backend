from rest_framework import generics, status
from rest_framework.response import Response

from user_management.permissions import CustomIsAuthenticated, CustomIsAdmin

from .serializers import (
    CTFGameSerializer,
    CTFGameDraftSerializer,
    CTFGameMachineSerializer,
    CTFCategorySerializer,
    CTFGameDetailSerializer,
    CTFStartGameSerializer,
    CTFGameConsoleSerializer,
    CTFGameExtendTimeSerializer,
    CTFSubmitFlagSerializer,
    CTFActiveGameListSerializer,
    CTFDeleteGameSerializer,
    CTFRatedSeveritySerializer,
    CTFGameListSerializer,
    CTFTargetIPSerializer,
    CTFLMSListSerializer,
    CTFGetScoreByGameIdSerializer
)
from drf_yasg.utils import swagger_auto_schema


class CTFCategoryListView(generics.ListAPIView):
    serializer_class = CTFCategorySerializer
    
    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        responses={200: CTFCategorySerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)    
        

class CTFGameView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFGameSerializer

    @swagger_auto_schema(
        request_body=CTFGameSerializer,
        responses={201: CTFGameSerializer()}
    )        
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            ctf = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response.pop('ctf_flags', None)
            response['message'] = "CTF Game Creation: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class CTFGameDraftView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFGameDraftSerializer

    def get_queryset(self, user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(user_id)
        return queryset
    
    @swagger_auto_schema(
        responses={200: CTFGameDraftSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(request.user['user_id'])

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    

class CTFGameMachineView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFGameMachineSerializer

    @swagger_auto_schema(
        request_body=CTFGameMachineSerializer,
        responses={201: CTFGameMachineSerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            ctf = serializer.save()
            response = serializer.data
            response['message'] = "CTF Machine Upload: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
   
      

class CTFGameDetailView(generics.RetrieveAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFGameDetailSerializer

    def get_queryset(self, ctf_id, user):
        serializer = self.serializer_class()
        user_id = self.request._user['user_id']
        queryset = serializer.get(ctf_id, user, user_id)
        return queryset

    @swagger_auto_schema(
        responses={200: CTFGameDetailSerializer()}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['ctf_id'], request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        queryset.pop("_id", None)
        return Response(queryset, status=status.HTTP_200_OK)


class CTFStartGameView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFStartGameSerializer

    @swagger_auto_schema(
        request_body=CTFStartGameSerializer,
        responses={201: CTFStartGameSerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            game = serializer.save()
            response = serializer.data
            response['message'] = "Please wait while we are creating dedicated machines for you."
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class CTFGameConsoleView(generics.RetrieveAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFGameConsoleSerializer

    def get_queryset(self, ctf_game_id, user):
        serializer = self.serializer_class()
        queryset = serializer.get(ctf_game_id, user)
        return queryset
    
    @swagger_auto_schema(
        responses={200: CTFGameConsoleSerializer()}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['ctf_game_id'], request.user)

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        queryset.pop("_id", None)
        return Response(queryset, status=status.HTTP_200_OK)
    

class CTFGameExtendTimeView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFGameExtendTimeSerializer

    @swagger_auto_schema(
        request_body=CTFGameExtendTimeSerializer,
        responses={200: CTFGameExtendTimeSerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            ctf_extend_time = serializer.save()
            response = serializer.data
            return Response(response, status=status.HTTP_200_OK)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class CTFSubmitFlagView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFSubmitFlagSerializer

    @swagger_auto_schema(
        request_body=CTFSubmitFlagSerializer,
        responses={201: CTFSubmitFlagSerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            flag_submission = serializer.save()
            response = serializer.data
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class CTFActiveGameListView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFActiveGameListSerializer

    def get_queryset(self, user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(user_id)
        return queryset
    
    @swagger_auto_schema(
        responses={200: CTFActiveGameListSerializer()}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(request.user.get('user_id'))

        # if 'errors' in queryset:
        #     return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        return Response(queryset, status=status.HTTP_200_OK)


class CTFDeleteGameView(generics.DestroyAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFDeleteGameSerializer

    @swagger_auto_schema(
        responses={202: CTFDeleteGameSerializer()}
    )
    def delete(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            ctf_game_id = self.kwargs.get('ctf_game_id')
            user_id = request.user.get('user_id')

            ctf_archive_game = serializer.delete_game(ctf_game_id, user_id)
            
            response = ctf_archive_game
            response['message'] = 'CTF Game Deletion: Successful'
            response.pop("_id", None)
            return Response(response, status=status.HTTP_202_ACCEPTED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        
class CTFRatedSeverityView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFRatedSeveritySerializer

    @swagger_auto_schema(
        request_body=CTFRatedSeveritySerializer,
        responses={201: CTFRatedSeveritySerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            rating_submission = serializer.save()
            response = serializer.data
            response['message'] = 'CTF Severity Submission: Successful'
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class CTFGameListView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFGameListSerializer

    def get_queryset(self):
        category_id = self.kwargs['category_id']
        user_id = self.request._user['user_id']
        return self.serializer_class().get(category_id, user_id)
    
    @swagger_auto_schema(
        responses={200: CTFGameListSerializer()}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        return Response(queryset, status=status.HTTP_200_OK)
    

class CTFTargetIPView(generics.ListAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFTargetIPSerializer

    def get_queryset(self):
        user_id = self.request._user['user_id']
        ctf_game_id = self.kwargs['ctf_game_id']
        return self.serializer_class().get(ctf_game_id, user_id)
    
    @swagger_auto_schema(
        responses={200: CTFTargetIPSerializer()}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)

        return Response(queryset, status=status.HTTP_200_OK)
    

class CTFLMSListView(generics.ListAPIView):
    serializer_class = CTFLMSListSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset
    
    @swagger_auto_schema(
        responses={200: CTFLMSListSerializer()}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)   


class CTFGetScoreByGameIdView(generics.CreateAPIView):
    permission_classes = [CustomIsAuthenticated]
    serializer_class = CTFGetScoreByGameIdSerializer

    @swagger_auto_schema(
        request_body=CTFGetScoreByGameIdSerializer,
        responses={201: CTFGetScoreByGameIdSerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            response = serializer.data
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
