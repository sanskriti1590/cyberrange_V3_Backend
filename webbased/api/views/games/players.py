from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from jsonschema import ValidationError
from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.permissions import CustomIsAuthenticated
from webbased.api.exceptions.swagger import response_403
from webbased.api.serializers.players import GameStartSerializer, GameEndSerializer, GamePlayersSerializer


class WebbasedGameStartAPIView(APIView):
    """
    API View to start a web-based game.

    This view allows authenticated users to initiate a web-based game by
    providing the necessary game ID and player ID. The player ID is derived
    from the authenticated user.
    """
    serializer_class = GameStartSerializer
    permission_classes = [CustomIsAuthenticated]

    @swagger_auto_schema(
        operation_id="start_webbased_game",
        operation_summary="Start web-based game",
        operation_description="Start a web-based game",
        responses={
            200: openapi.Response(description='Web-based game started', examples={}),
            400: openapi.Response(description="Invalid input", examples={
                "application/json": {
                    "error": "Game ID is invalid | Player ID is invalid | Game is not approved, etc."
                }
            }),
            403: response_403,
            404: openapi.Response(description="Game ID or Player ID not found", examples={
                "application/json": {
                    "error": "Game does not exist | Player does not exist."
                }
            }),
            409: openapi.Response(description='Conflict', examples={
                "application/json": {
                    "error": "This game has already been started by the player. | Game is restricted to premium users."
                }
            }),
        },
        manual_parameters=[
            openapi.Parameter(
                'game_id',
                openapi.IN_PATH,
                description="ID of the web-based game to start",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
    )
    def post(self, request, game_id):
        request.data['game_id'] = game_id
        request.data['player_id'] = request.user.get('user_id')

        serializer = GameStartSerializer(data=request.data)
        if serializer.is_valid():
            new_instance = serializer.create(serializer.validated_data)
            return Response(new_instance, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WebbasedGameEndAPIView(APIView):
    permission_classes = [CustomIsAuthenticated]

    @swagger_auto_schema(
        operation_id="end_webbased_game",
        operation_summary="End web-based game",
        operation_description="End a web-based game",
        responses={
            200: openapi.Response(description='Web-based game ended.', examples={}),
            400: openapi.Response(description="Invalid input", examples={
                "application/json": {
                    "error": "Game ID is invalid | Invalid game active ID | The game has already been completed."
                }
            }),
            403: response_403,
        },
        manual_parameters=[
            openapi.Parameter(
                'game_id',
                openapi.IN_PATH,
                description="ID of the web-based game to end/close",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
    )
    def post(self, request, game_id):
        game_started_id = request.data.get('_id')

        if not game_started_id:
            return Response({"error": "_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        request.data['game_id'] = game_id
        request.data['player_id'] = request.user.get('user_id')

        # Create an instance of the serializer with the incoming data
        serializer = GameEndSerializer(data=request.data)

        if serializer.is_valid():
            try:
                updated_game = serializer.update(game_started_id=game_started_id, validated_data=serializer.validated_data)
                return Response(updated_game, status=status.HTTP_200_OK)
            except serializers.ValidationError as e:
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GetPlayersByGameAPIView(APIView):
    """
    API endpoint to retrieve all players associated with a specific game_id.
    This endpoint filters players by game_id, and can optionally filter by the authenticated user's player_id.
    """
    permission_classes = [CustomIsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve all players associated with a specific game_id. Optionally filter by the authenticated user's player_id.",
        responses={
            200: openapi.Response('A list of players for the game', GamePlayersSerializer(many=True)),
            404: openapi.Response('No players found for the game',
                                  openapi.Schema(type=openapi.TYPE_OBJECT, properties={'message': openapi.Schema(type=openapi.TYPE_STRING)})),
            400: openapi.Response('Bad request due to invalid game_id',
                                  openapi.Schema(type=openapi.TYPE_OBJECT, properties={'error': openapi.Schema(type=openapi.TYPE_STRING)})),
            500: openapi.Response('Internal server error',
                                  openapi.Schema(type=openapi.TYPE_OBJECT, properties={'error': openapi.Schema(type=openapi.TYPE_STRING)})),
        },
        parameters=[
            openapi.Parameter('game_id', openapi.IN_PATH, description="The unique identifier of the game", type=openapi.TYPE_STRING),
        ]
    )
    def get(self, request, game_id):
        """
        Handle GET requests to retrieve players for a specific game_id.
        Optionally filter by the authenticated user's player_id.
        """
        # Extract player_id from the authenticated user's data
        player_id = request.user.get('user_id')

        # Initialize the serializer
        serializer = GamePlayersSerializer()

        # Try to fetch players and handle potential errors
        try:
            # Retrieve players by game_id, and optionally by player_id (for the authenticated user)
            players = serializer.list(game_id=game_id)

            # if not players:
            #     # Return a 404 status if no players found
            #     return Response({"message": "No players found for this game."}, status=status.HTTP_404_NOT_FOUND)

            # Return the list of players with a 200 OK status
            return Response(players, status=status.HTTP_200_OK)

        except ValueError as ve:
            # Return a 400 Bad Request if there is a value error (e.g., missing or invalid game_id)
            return Response({"error": f"Invalid game ID: {str(ve)}"}, status=status.HTTP_400_BAD_REQUEST)

        except ValidationError as ve:
            # Return a 500 Internal Server Error for any validation issues
            return Response({"error": f"Server error: {str(ve)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            # Handle unexpected errors gracefully and log them if necessary
            return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
