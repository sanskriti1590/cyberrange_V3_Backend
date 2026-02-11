from rest_framework import generics, status, serializers
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.views import APIView


import datetime
import pandas as pd

from corporate_management.serializers import (
    CorporateScenarioFlagCreateSerializer,
    CorporateScenarioMilestoneCreateSerializer,
    CorporateScenarioPhaseSerializer,
)
from user_management.permissions import  CustomIsAdmin
from .serializers import (
    UserRetrieveAdminSerializer, 
    UserAdminSerializer,
    UserUpdateAdminSerializer,
    UserRemoveAdminSerializer,

    CTFCategoryListSerializer,
    CTFCategorySerializer,
    CTFCategoryUpdateSerializer,
    CTFUnmappedGameSerializer,
    CTFMappedGameSerializer,
    CTFGameMappingSerializer,
    CTFDeleteMappingSerializer,
    CTFGameListSerializer,
    CTFGameUpdateSerializer,

    ScenarioCategoryListSerializer,
    ScenarioCategorySerializer,
    ScenarioCategoryUpdateSerializer,
    ScenarioApproveSerializer,
    ScenarioUnapproveSerializer,
    ScenarioGameListSerializer,
    ScenarioGameUpdateSerializer,
    ScenarioGameDocumentRemoveSerializer,

    ImageValidateSerializer,
    GetCTFScenarioSerializer,
    AddCTFForUserSerializer,
    AddScenarioForUserSerializer,
    AddCorporateForUserSerializer,
    RemoveCTFScenarioForUserSerializer,
    GetCTFScenarioForUserSpecificSerializer,
    CorporateApproveSerializer,
    CorporateUnapproveSerializer,
    CorporateInfraReviewGetSerializer,
    CorporateInfraReviewSaveSerializer,
    AdminCorporateScenarioUpdateSerializer,
    AdminCorporateScenarioDetailSerializer,
)

from database_management.pymongo_client import (
    corporate_scenario_collection,
    milestone_data_collection,
    flag_data_collection,
    corporate_scenario_infra_collection,
    user_collection,
    user_profile_collection
)
from core.utils import API_URL

class UserRegisterAdminView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = UserAdminSerializer

    @swagger_auto_schema(
        operation_summary="Register a new user",
        operation_description="Endpoint to register a new user as an admin",
        responses={201: "User registration successful"},
    )        
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            response = serializer.data
            response['message'] = "User Registration: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class UserListAdminView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = UserAdminSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        operation_summary="List all users",
        operation_description="Endpoint to list all users",
        responses={200: UserAdminSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response(queryset)

class BulkUserUploadView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = UserAdminSerializer

    @swagger_auto_schema(
        operation_summary="Bulk upload users via Excel",
        operation_description="Upload Excel to bulk create users (password required)",
        manual_parameters=[
            openapi.Parameter(
                name="file",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
            )
        ],
    )
    def create(self, request, *args, **kwargs):
        file = request.FILES.get("file")

        if not file:
            return Response({"errors": "File not provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            df = pd.read_excel(file)
            df.columns = [c.strip() for c in df.columns]
        except Exception:
            return Response({"errors": "Invalid Excel file"}, status=status.HTTP_400_BAD_REQUEST)

        required_columns = {
            "user_full_name",
            "email",
            "mobile_number",
            "user_role",
            "password",
        }

        if not required_columns.issubset(df.columns):
            return Response(
                {"errors": f"Missing columns: {required_columns - set(df.columns)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success_rows = []
        failed_rows = []

        for index, row in df.iterrows():
            row_data = row.to_dict()

            # 🔑 Make bulk compatible with UserAdminSerializer
            row_data["confirm_password"] = row_data.get("password")
            row_data.setdefault("is_verified", False)
            row_data.setdefault("is_premium", False)
            row_data.setdefault("is_admin", False)
            row_data.setdefault("is_active", True)

            serializer = self.get_serializer(data=row_data)

            if not serializer.is_valid():
                failed_rows.append({
                    "row": index + 2,
                    "errors": serializer.errors,
                })
                continue

            try:
                serializer.save()
                success_rows.append({
                    "row": index + 2,
                    "email": row_data.get("email"),
                })
            except Exception as e:
                failed_rows.append({
                    "row": index + 2,
                    "errors": str(e),
                })

        return Response(
            {
                "message": "Bulk User Upload Completed",
                "total": len(df),
                "success_count": len(success_rows),
                "failed_count": len(failed_rows),
                "failed_rows": failed_rows,
            },
            status=status.HTTP_200_OK,
        )



class UserRetrieveAdminView(generics.RetrieveAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = UserRetrieveAdminSerializer

    def get_queryset(self, user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(user_id)
        return queryset

    @swagger_auto_schema(
        operation_summary="Retrieve a user by ID",
        operation_description="Endpoint to retrieve user details by user ID",
        responses={200: UserRetrieveAdminSerializer()},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['user_id'])
        return Response(queryset)


class UserUpdateAdminView(generics.UpdateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = UserUpdateAdminSerializer

    @swagger_auto_schema(
        operation_summary="Update a user by ID",
        operation_description="Endpoint to update user details by user ID",
        responses={200: "User update successful"},
    )
    def put(self, request, user_id):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = serializer.data
            response['message'] = "User Updation: Successful"
            return Response(response, status=status.HTTP_200_OK)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
 
 
class UserDeleteAdminView(APIView):
    permission_classes = [CustomIsAdmin]

    @swagger_auto_schema(
        operation_summary="Remove a user by ID",
        operation_description="Soft delete (deactivate) a user",
        responses={202: "User removal successful"},
    )
    def delete(self, request, user_id, *args, **kwargs):
        serializer = UserRemoveAdminSerializer(
            data={"user_id": user_id}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "user_id": user_id,
                "message": "User Deletion: Successful",
            },
            status=status.HTTP_202_ACCEPTED,
        )
# CTF

class CTFCategoryListView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CTFCategoryListSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        operation_summary="List all CTF categories",
        operation_description="Endpoint to list all CTF categories",
        responses={200: CTFCategoryListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response(queryset)

class CTFCategoryCreateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CTFCategorySerializer

    @swagger_auto_schema(
        operation_summary="Create a new CTF category",
        operation_description="Endpoint to create a new CTF category",
        responses={201: "CTF category creation successful"},
    )  
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            ctf_category = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response['message'] = "CTF Game Category Creation: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class CTFCategoryUpdateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CTFCategoryUpdateSerializer

    def get_queryset(self, ctf_category_id):
        serializer = self.serializer_class()
        queryset = serializer.get(ctf_category_id)
        return queryset
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['ctf_category_id'])
        return Response(queryset)

    @swagger_auto_schema(
        operation_summary="Update a CTF category by ID",
        operation_description="Endpoint to update a CTF category by category ID",
        responses={200: "CTF category update successful"},
    )        
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            ctf = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response['message'] = "CTF Category Updation: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class CTFUnmappedGameView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CTFUnmappedGameSerializer

    def get_queryset(self, user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(user_id)
        return queryset
    
    @swagger_auto_schema(
        operation_summary="List all unmapped CTF games",
        operation_description="Endpoint to list all unmapped CTF games",
        responses={200: CTFUnmappedGameSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(request.user['user_id'])

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    
class CTFMappedGameView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CTFMappedGameSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        operation_summary="List all mapped CTF games",
        operation_description="Endpoint to list all mapped CTF games",
        responses={200: CTFMappedGameSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK) 
    

class CTFGameMappingView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CTFGameMappingSerializer 

    @swagger_auto_schema(
        operation_summary="Map a CTF game",
        operation_description="Endpoint to map a CTF game to a category",
        responses={201: "CTF game mapping successful"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            mapping = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response['message'] = "CTF Game Mapping: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class CTFMappingDeleteView(generics.DestroyAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CTFDeleteMappingSerializer

    @swagger_auto_schema(
        operation_summary="Delete a CTF game mapping",
        operation_description="Endpoint to delete a mapping of a CTF game",
        responses={202: "CTF game mapping deletion successful"},
    )
    def delete(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            mapping = serializer.save()
            response = serializer.data
            response['message'] = "CTF Mapping Deletion: Successful"
            return Response(response, status=status.HTTP_202_ACCEPTED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class CTFGameListView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CTFGameListSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        operation_summary="List all CTF games",
        operation_description="Endpoint to list all CTF games",
        responses={200: CTFGameListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)

class CTFGameUpdateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CTFGameUpdateSerializer

    def get_queryset(self, ctf_id):
        serializer = self.serializer_class()
        queryset = serializer.get(ctf_id)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['ctf_id'])
        return Response(queryset)
    
    @swagger_auto_schema(
        operation_summary="Update a CTF game by ID",
        operation_description="Endpoint to update a CTF game by game ID",
        responses={201: "CTF game update successful"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            ctf = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response.pop('ctf_flags', None)
            response['message'] = "CTF Game Updation: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
# Scenario

class ScenarioCategoryListView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = ScenarioCategoryListSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        operation_summary="List all scenario categories",
        operation_description="Endpoint to list all scenario categories",
        responses={200: ScenarioCategoryListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response(queryset)
    
class ScenarioCategoryCreateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = ScenarioCategorySerializer
        
    @swagger_auto_schema(
        operation_summary="Create a new scenario category",
        operation_description="Endpoint to create a new scenario category",
        responses={201: "Scenario category creation successful"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            scenario_category = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response['message'] = "Scenario Category Creation: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class ScenarioCategoryUpdateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = ScenarioCategoryUpdateSerializer

    def get_queryset(self, ctf_category_id):
        serializer = self.serializer_class()
        queryset = serializer.get(ctf_category_id)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['scenario_category_id'])
        return Response(queryset)
    
    @swagger_auto_schema(
        operation_summary="Update a scenario category by ID",
        operation_description="Endpoint to update a scenario category by category ID",
        responses={200: "Scenario category update successful"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            ctf = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response['message'] = "Scenario Category Updation: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class ScenarioApproveView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = ScenarioApproveSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)  

    @swagger_auto_schema(
        operation_summary="Approve a scenario",
        operation_description="Endpoint to approve a scenario",
        responses={201: "Scenario approval successful"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            flag_submission = serializer.save()
            response = serializer.data
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    
class ScenarioUnapproveView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = ScenarioUnapproveSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)  
    
    @swagger_auto_schema(
        operation_summary="Unapprove a scenario",
        operation_description="Endpoint to unapprove a scenario",
        responses={201: "Scenario unapproval successful"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            flag_submission = serializer.save()
            response = serializer.data
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class ScenarioGameListView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = ScenarioGameListSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    @swagger_auto_schema(
        operation_summary="List all scenario games",
        operation_description="Endpoint to list all scenario games",
        responses={200: ScenarioGameListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)
    
class ScenarioGameUpdateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = ScenarioGameUpdateSerializer

    def get_queryset(self, ctf_id):
        serializer = self.serializer_class()
        queryset = serializer.get(ctf_id)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['scenario_id'])
        return Response(queryset)
    
    @swagger_auto_schema(
        operation_summary="Update a scenario game by ID",
        operation_description="Endpoint to update a scenario game by game ID",
        responses={201: "Scenario game update successful"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            ctf = serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response.pop('scenario_flags', None)
            response['message'] = "Scenario Game Updation: Successful"
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class ScenarioGameDocumentRemoveView(generics.DestroyAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = ScenarioGameDocumentRemoveSerializer

    @swagger_auto_schema(
        operation_summary="Remove a scenario game document",
        operation_description="Endpoint to remove a document from a scenario game",
        responses={202: "Document removal successful"},
    )
    def put(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            mapping = serializer.save()
            response = serializer.data
            response['message'] = "Document Removed."
            return Response(response, status=status.HTTP_202_ACCEPTED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class ImageValidateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = ImageValidateSerializer

    @swagger_auto_schema(
        operation_summary="Validate an image",
        operation_description="Endpoint to validate an image",
        responses={202: "Image validation successful"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response['message'] = "Credentials saved successfully."
            return Response(response, status=status.HTTP_202_ACCEPTED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class GetCTFScenarioView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = GetCTFScenarioSerializer

    def get_queryset(self, keyword, user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(keyword, user_id)
        return queryset
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['keyword'], kwargs['user_id'])
        return Response(queryset)
    
class AddCTFForUserView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = AddCTFForUserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response['message'] = "CTF added successfully."
            return Response(response, status=status.HTTP_202_ACCEPTED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class AddScenarioForUserView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = AddScenarioForUserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response['message'] = "Scenario added successfully."
            return Response(response, status=status.HTTP_202_ACCEPTED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class AddCorporateForUserView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = AddCorporateForUserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            response = serializer.data
            response.pop('_id', None)
            response['message'] = "Corporate Scenario added successfully."
            return Response(response, status=status.HTTP_202_ACCEPTED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class RemoveCTFScenarioForUserView(generics.DestroyAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = RemoveCTFScenarioForUserSerializer

    def delete(self, request, *args, **kwargs):
        serializer = self.serializer_class()
        response = serializer.delete(kwargs['keyword'], kwargs['user_id'], kwargs['item_id'])

        return Response(response, status=status.HTTP_200_OK if 'message' in response else status.HTTP_404_NOT_FOUND)
    
class GetCTFScenarioForUserSpecificView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = GetCTFScenarioForUserSpecificSerializer

    def get_queryset(self, game_type, category_id, user_id):
        serializer = self.serializer_class()
        queryset = serializer.get(game_type, category_id, user_id)
        return queryset
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset(kwargs['game_type'], kwargs['category_id'], kwargs['user_id'])
        return Response(queryset)
    

class CorporateApproveListView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CorporateApproveSerializer

    def list(self, request, *args, **kwargs):
        serializer = self.serializer_class()
        data = serializer.get()
        return Response(data, status=status.HTTP_200_OK)
    
class CorporateApproveCreateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CorporateApproveSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.save(), status=status.HTTP_201_CREATED)

class CorporateInfraReviewGetView(generics.ListAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CorporateInfraReviewGetSerializer

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.get_infra(), status=status.HTTP_200_OK)
    
class CorporateInfraReviewSaveView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CorporateInfraReviewSaveSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.save(), status=status.HTTP_201_CREATED)



class CorporateUnapproveView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CorporateUnapproveSerializer

    def get_queryset(self):
        serializer = self.serializer_class()
        queryset = serializer.get()
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if 'errors' in queryset:
            return Response(queryset, status=status.HTTP_400_BAD_REQUEST)
        return Response(queryset, status=status.HTTP_200_OK)  
    
    @swagger_auto_schema(
        operation_summary="Unapprove a corporate",
        operation_description="Endpoint to unapprove a Corporate",
        responses={201: "Corporate unapproval successful"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            flag_submission = serializer.save()
            response = serializer.data
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class AdminCorporateScenarioUpdateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = AdminCorporateScenarioUpdateSerializer

    @swagger_auto_schema(
        operation_summary="Update corporate scenario (admin)",
        operation_description="Admin can update scenario details, scoring, description",
        responses={201: "Scenario updated successfully"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            response = serializer.save()
            return Response(response, status=status.HTTP_201_CREATED)

        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

class AdminCorporateScenarioPhaseUpdateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CorporateScenarioPhaseSerializer

    @swagger_auto_schema(
        operation_summary="Update scenario phases (admin)",
        operation_description="Replace phases for a scenario",
        responses={201: "Phases updated"},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            response = serializer.save()
            return Response(response, status=status.HTTP_201_CREATED)

        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
class AdminCorporateScenarioFlagUpdateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CorporateScenarioFlagCreateSerializer

    @swagger_auto_schema(
        operation_summary="Update flags (admin)",
        operation_description="Replace all flags for scenario",
        responses={201: "Flags updated"},
    )
    def create(self, request, *args, **kwargs):
        scenario_id = request.data.get("scenario_id")

        if not scenario_id:
            return Response(
                {"error": "scenario_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔥 delete old flags
        flag_data_collection.delete_many({"scenario_id": scenario_id})

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            response = serializer.save()
            return Response(response, status=status.HTTP_201_CREATED)

        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
class AdminCorporateScenarioMilestoneUpdateView(generics.CreateAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = CorporateScenarioMilestoneCreateSerializer

    @swagger_auto_schema(
        operation_summary="Update milestones (admin)",
        operation_description="Replace all milestones for scenario",
        responses={201: "Milestones updated"},
    )
    def create(self, request, *args, **kwargs):
        scenario_id = request.data.get("scenario_id")

        if not scenario_id:
            return Response(
                {"error": "scenario_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔥 delete old milestones
        milestone_data_collection.delete_many({"scenario_id": scenario_id})

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            response = serializer.save()
            return Response(response, status=status.HTTP_201_CREATED)

        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
class AdminCorporateScenarioDetailView(generics.GenericAPIView):
    permission_classes = [CustomIsAdmin]
    serializer_class = AdminCorporateScenarioDetailSerializer

    @swagger_auto_schema(
        operation_summary="Get corporate scenario detail (admin)",
        operation_description="Fetch full corporate cyberdrill details for admin update",
        responses={200: "Scenario detail fetched"},
    )
    def get(self, request, scenario_id):
        serializer = self.get_serializer()
        try:
            data = serializer.get(scenario_id)
        except serializers.ValidationError as e:
            return Response(
                {"errors": e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(data, status=status.HTTP_200_OK)