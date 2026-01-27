from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.permissions import CustomIsAuthenticated
from webbased.api.serializers.base import CategoryBaseSerializer
from webbased.api.serializers.categories import CategoryCreateSerializer, CategoryUpdateSerializer, CategoryListSerializer


class CategoryAPIView(APIView):
    """API endpoint for category operations."""

    serializer_class = CategoryBaseSerializer
    permission_classes = [CustomIsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Retrieve all categories",
        responses={
            200: openapi.Response('List of categories', CategoryListSerializer(many=True)),
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
