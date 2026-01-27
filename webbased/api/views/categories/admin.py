from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from database_management.pymongo_client import web_based_category_collection
from user_management.permissions import CustomIsAdmin
from webbased.api.exceptions.swagger import response_403
from webbased.api.serializers.base import CategoryBaseSerializer
from webbased.api.serializers.categories import CategoryCreateSerializer, CategoryUpdateSerializer, CategoryListSerializer


class CategoryAPIView(APIView):
    """API endpoint for category operations."""

    serializer_class = CategoryBaseSerializer
    permission_classes = [CustomIsAdmin]

    @swagger_auto_schema(
        operation_summary="Retrieve all categories",
        responses={
            200: openapi.Response('List of categories', CategoryListSerializer(many=True)),
            403: response_403,
        }
    )
    def get(self, request):
        """Retrieve all categories."""
        categories_data = CategoryListSerializer.get_all_categories()  # Get all categories

        # If no categories are found, return an empty array
        if not categories_data:
            return Response([], status=status.HTTP_200_OK)  # Return an empty list if no categories are found

        # Serialize the categories
        serializer = CategoryListSerializer(categories_data, many=True)  # Use the serializer here
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Create a new category",
        request_body=CategoryCreateSerializer,
        responses={
            201: openapi.Response('Category created', CategoryCreateSerializer),
            400: 'Invalid input',
            403: response_403,
        }
    )
    def post(self, request):
        """Create a new category."""
        serializer = CategoryCreateSerializer(data=request.data)
        if serializer.is_valid():
            category_data = serializer.create(serializer.validated_data)
            return Response(category_data, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetailAPIView(APIView):
    """API endpoint for category operations."""
    permission_classes = [CustomIsAdmin]
    serializer_class = CategoryBaseSerializer

    @swagger_auto_schema(
        operation_summary="Retrieve a category by ID",
        responses={
            200: openapi.Response('Category details', CategoryListSerializer),
            403: response_403,
            404: 'Category not found.',
        }
    )
    def get(self, request, category_id):
        """Retrieve a single category by its ID."""
        category = web_based_category_collection.find_one({'category_id': category_id})
        if not category:
            return Response({"errors": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

        category_data = self.serializer_class.get(category_id=category_id)
        if not category_data:
            return Response({"errors": "Category not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(category_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Partially update a category",
        request_body=CategoryUpdateSerializer,
        responses={
            200: openapi.Response('Category updated', CategoryUpdateSerializer),
            400: 'Invalid input',
            403: response_403,
            404: 'Category not found',
        }
    )
    def patch(self, request, category_id):
        """Partially update an existing category."""
        serializer = CategoryUpdateSerializer()
        try:
            if not request.data.get('name'):
                return Response({"errors": {"name": ["Please provide category name!"]}}, status=status.HTTP_400_BAD_REQUEST)
            if not request.data.get('description'):
                return Response({"errors": {"description": ["Please provide category description!"]}}, status=status.HTTP_400_BAD_REQUEST)
            if request.data.get('description') and len(request.data.get('description')) < 50:
                return Response({"errors": {"description": ["Ensure this field has at least 50 characters."]}}, status=status.HTTP_400_BAD_REQUEST)
            if not request.data.get('thumbnail'):
                return Response({"errors": {"thumbnail": ["Please provide a thumbnail."]}}, status=status.HTTP_400_BAD_REQUEST)

            updated_data = serializer.update(category_id, request.data)
            return Response(updated_data, status=status.HTTP_200_OK)
        except serializers.ValidationError as e:
            return Response({"errors": str(e)}, status=status.HTTP_400_BAD_REQUEST)
