from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.permissions import CustomIsAuthenticated
from webbased.api.serializers.players import ActiveGameSerializer
from webbased.api.serializers.web_based_game import (
    WebBasedGameBaseSerializer,
    WebBasedGameListSerializer,
)


class WebbasedGamesAPIView(APIView):
    """API endpoint for managing web-based game operations.

    This API provides endpoints to retrieve and create web-based games.
    It requires the user to be authenticated.
    """

    serializer_class = WebBasedGameBaseSerializer
    permission_classes = [CustomIsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Retrieve all web-based games",
        responses={
            200: openapi.Response('List of web-based games', WebBasedGameListSerializer(many=True)),
        }
    )
    def get(self, request):
        """Retrieve all approved web-based games.

        This method fetches approved web-based games from the database and returns them
        in the response. If no games are found, an empty list is returned.

        Args:
            request: The HTTP request object.

        Returns:
            Response: A response object containing the serialized data of the approved web-based games.
        """
        # Get the 'category' query parameter from the request, if provided
        category = request.GET.get('category', None)
        types = request.GET.get('types', None)

        if types == 'active':
            # Use the serializer to get the serialized data for active games with player details
            serialized_data = ActiveGameSerializer.get_serialized_data(request=request)

            # Return the serialized data in the response
            return Response(serialized_data, status=status.HTTP_200_OK)

        # Retrieve approved web-based games, filtering by category if provided
        webbased_data = WebBasedGameListSerializer().get_all_approved_games(category_id=category)

        # Return an empty array if no web-based games are found
        if not webbased_data:
            return Response([], status=status.HTTP_200_OK)  # Return an empty list if no games are found

        return Response(webbased_data, status=status.HTTP_200_OK)  # Return serialized data with 200 OK status


class WebbasedGameDetailAPIView(APIView):
    """
    API view to retrieve details of a specific web-based game.

    This view handles GET requests to fetch the details of a web-based game
    based on the provided game ID. Only authenticated users have permission to
    access this endpoint.

    Attributes:
        serializer_class (WebBasedGameBaseSerializer): The serializer used
            to validate and serialize web-based game data.
        permission_classes (list): List of permission classes that define
            the access control for this view.
    """

    serializer_class = WebBasedGameBaseSerializer
    permission_classes = [CustomIsAuthenticated]

    @swagger_auto_schema(
        operation_id="get_webbased_game_details",
        operation_description="Retrieve details of a web-based game by ID.",
        responses={
            200: openapi.Response(
                description="Web-based game details retrieved successfully.",
                schema=WebBasedGameBaseSerializer,  # Replace with the appropriate response schema
            ),
            403: openapi.Response(
                description="Authentication credentials were not provide.",
                examples={
                    "application/json": {
                        "exception": "An error of type NotAuthenticated occurred: Authentication credentials were not provided."
                    }
                }
            ),
            404: openapi.Response(
                description="Web-based game instance not found or not approved.",
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
                description="ID of the web-based game to retrieve",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
    )
    def get(self, request, game_id):
        """
        Handle GET requests to retrieve the web-based game details.

        Args:
            request (Request): The incoming HTTP request.
            game_id (str): The ID of the web-based game to retrieve.

        Returns:
            Response: A Response object containing the game data if found,
                      or an error message if the game instance is not found or not approved.
        """
        # Attempt to retrieve the web-based game data using the serializer class
        webbased_game_data = self.serializer_class.get(game_id=game_id, player_id=request.user.get('user_id'))

        # Check if the game data was found and is approved
        if not webbased_game_data or not webbased_game_data.get('is_approved'):
            # Return a 404 response if the game instance does not exist or is not approved
            return Response({"error": ["Webbased game instance not found."]},
                            status=status.HTTP_404_NOT_FOUND)

        # Return the retrieved game data with a 200 OK status
        return Response(webbased_game_data, status=status.HTTP_200_OK)
