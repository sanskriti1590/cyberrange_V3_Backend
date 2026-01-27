from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.permissions import CustomIsAdmin
from webbased.api.exceptions.swagger import response_403
from webbased.api.serializers.web_based_game import (
    WebBasedGameBaseSerializer,
    WebBasedGameListSerializer,
    WebBasedGameCreateSerializer, ToggleWebBasedGameApprovalSerializer, )


class WebbasedAPIView(APIView):
    """API endpoint for managing web-based game operations.

    This API provides endpoints to retrieve and create web-based games.
    It requires the user to be authenticated and have admin permissions.
    """

    serializer_class = WebBasedGameBaseSerializer
    permission_classes = [CustomIsAdmin]

    @swagger_auto_schema(
        operation_summary="Retrieve all web-based games",
        responses={
            200: openapi.Response('List of web-based games', WebBasedGameListSerializer(many=True)),
            403: response_403,
        }
    )
    def get(self, request):
        """Retrieve all web-based games.

        This method fetches web-based games from the database, filtering by
        category and approval status. If no games are found, an empty list is returned.

        Args:
            request: The HTTP request object.

        Returns:
            Response: A response object containing the serialized data of the web-based games.
        """
        # Get the 'category' and 'approved' query parameters from the request
        category = request.GET.get('category')
        is_approved = request.GET.get('approved')  # 'approved' can be '0' or '1'

        # Convert the 'approved' value to a boolean
        if is_approved is not None:
            is_approved = is_approved == '1'  # True if '1', otherwise False

        # Retrieve web-based games, filtering by category and approval status
        webbased_data = WebBasedGameListSerializer().get_all_games(category_id=category, is_approved=is_approved)

        # If no web-based games are found, return an empty array
        if not webbased_data:
            return Response([], status=status.HTTP_200_OK)  # Return an empty list if no games are found

        return Response(webbased_data, status=status.HTTP_200_OK)  # Return serialized data with 200 OK status

    @swagger_auto_schema(
        operation_summary="Create a new web-based game",
        request_body=WebBasedGameCreateSerializer,
        responses={
            201: openapi.Response('Web-based game created', WebBasedGameCreateSerializer),
            400: 'Invalid input',
            403: response_403,
        }
    )
    def post(self, request):
        """Create a new web-based game.

        This method accepts the data for a new web-based game, validates it,
        and creates a new entry in the database if the data is valid.

        Args:
            request: The HTTP request object containing the new game data.

        Returns:
            Response: A response object containing the created game data or error messages.
        """
        # Convert request.data to a mutable dictionary
        request_data = request.data.copy()  # Create a mutable copy of the QueryDict

        request_data['created_by'] = request.user.get('user_id')

        # Initialize the serializer with the mutable request data
        serializer = WebBasedGameCreateSerializer(data=request_data)

        # Validate the serializer input
        if serializer.is_valid():
            # Create a new web-based game and return the created data
            game_data = serializer.create(serializer.validated_data)  # Create game entry in the database
            return Response(game_data, status=status.HTTP_201_CREATED)  # Return created game data with 201 Created status

        # Return validation errors if the input is invalid
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)  # Return error messages with 400 Bad Request status


class WebbasedGameDetailAPIView(APIView):
    """
    API view to retrieve and update details of a specific web-based game.

    This view handles GET requests to fetch the details of a web-based game
    based on the provided game ID. It also handles PATCH requests to update
    the game details. Only admin users have permission to access these endpoints.

    Attributes:
        serializer_class (WebBasedGameBaseSerializer): The serializer
            used to validate and serialize web-based game data.
        permission_classes (list): List of permission classes that define
            the access control for this view.
    """

    serializer_class = WebBasedGameBaseSerializer
    permission_classes = [CustomIsAdmin]

    @swagger_auto_schema(
        operation_id="get_webbased_game_details",
        operation_description="Retrieve details of a web-based game by ID.",
        responses={
            200: openapi.Response(
                description="Web-based game details retrieved successfully.",
                schema=WebBasedGameBaseSerializer,
            ),
            403: response_403,
            404: openapi.Response(
                description="Web-based game instance not found.",
                examples={
                    "application/json": {
                        "error": ["Webbased game instance not found."]
                    }
                }
            ),
        },
        manual_parameters=[
            openapi.Parameter(
                'game_id',
                openapi.IN_PATH,
                description="ID of the web-based game to retrieve",
                type=openapi.TYPE_STRING,  # Changed to TYPE_STRING for game_id
                required=True
            ),
        ],
    )
    def get(self, request, game_id: str):
        """
        Handle GET requests to retrieve the web-based game details.

        Args:
            request (Request): The incoming HTTP request.
            game_id (str): The ID of the web-based game to retrieve.

        Returns:
            Response: A Response object containing the game data if found,
                      or an error message if the game instance is not found.
        """
        # Attempt to retrieve the web-based game data using the serializer class
        webbased_game_data = self.serializer_class.get_admin(game_id=game_id)

        # Check if the game data was found
        if not webbased_game_data:
            # Return a 404 response if the game instance does not exist
            return Response({"error": ["Webbased game instance not found."]},
                            status=status.HTTP_404_NOT_FOUND)

        # Return the retrieved game data with a 200 OK status
        return Response(webbased_game_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id="update_webbased_game_details",
        operation_description="Update details of a web-based game by ID.",
        request_body=WebBasedGameBaseSerializer,  # Specify the request body schema
        responses={
            200: openapi.Response(
                description="Web-based game details updated successfully.",
                schema=WebBasedGameBaseSerializer,
            ),
            400: openapi.Response(
                description="Validation error with the provided data.",
                examples={
                    "application/json": {
                        "errors": "Validation error details."
                    }
                }
            ),
            403: response_403,
            404: openapi.Response(
                description="Web-based game instance not found.",
                examples={
                    "application/json": {
                        "error": "Webbased game instance not found."
                    }
                }
            ),
        },
        manual_parameters=[
            openapi.Parameter(
                'game_id',
                openapi.IN_PATH,
                description="ID of the web-based game to update",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
    )
    def patch(self, request, game_id: str):
        """
        Handle PATCH requests to update the web-based game details.

        Args:
            request (Request): The incoming HTTP request containing the updated data.
            game_id (str): The ID of the web-based game to update.

        Returns:
            Response: A Response object containing the updated game data if successful,
                      or an error message if the game instance is not found or validation fails.
        """
        # Attempt to retrieve the web-based game data using the serializer class
        webbased_game_data = self.serializer_class.get(game_id=game_id)

        # Check if the game data was found
        if not webbased_game_data:
            # Return a 404 response if the game instance does not exist
            return Response({"error": ["Webbased game instance not found."]},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            # Create a mutable copy of request.data
            request_data = request.data.copy()

            # Update the game data with the provided request data
            updated_data = self.serializer_class().update(game_id, request_data)
            return Response(updated_data, status=status.HTTP_200_OK)
        except serializers.ValidationError as e:
            # Return a 400 response if there are validation errors
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ToggleWebBasedGameApprovalAPIView(APIView):
    """API View to toggle the approval status of a web-based game.

    This view allows an admin user to toggle the approval status of a specified web-based game.
    When the approval status is toggled, it updates the game's record in the database based on
    the presence of a valid URL. If the game does not have a URL, an error will be raised.

    Attributes:
        permission_classes (list): The list of permission classes to be applied to the view.

    Methods:
        post(request, game_id):
            Handles the POST request to toggle the approval status of the game identified by game_id.
    """
    permission_classes = [CustomIsAdmin]

    def post(self, request, game_id):
        """Handles the POST request to toggle the approval status of a web-based game.

        Args:
            request (Request): The HTTP request object containing the admin's request to toggle
                               the approval status.
            game_id (str): The unique identifier of the game whose approval status is to be toggled.

        Returns:
            Response: A Response object containing a success message and the updated game data
                      if the operation is successful, or error details if validation fails.

        Raises:
            ValidationError: If the game does not exist or does not have a URL.
        """
        serializer = ToggleWebBasedGameApprovalSerializer(data={"game_id": game_id})

        if serializer.is_valid():
            try:
                # Call the method to toggle approval status
                updated_game = serializer.toggle_approval_status()
                return Response(
                    {
                        "message": "Approval status updated successfully.",
                        "game": updated_game,
                    },
                    status=status.HTTP_200_OK,
                )
            except ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
