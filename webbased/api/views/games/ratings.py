from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.permissions import CustomIsAuthenticated
from webbased.api.serializers.ratings import GameRatingBaseSerializer


class GameRatingCreateAPIView(APIView):
    """
    API endpoint for creating a new game rating.
    """
    permission_classes = [CustomIsAuthenticated]

    def post(self, request, game_id):
        """Handles creating a new game rating."""
        # Extract the user_id directly from request
        user_id = request.user.get('user_id')

        # Attach the game_id, user_id, and payed_game_id to the request data
        request.data['user_id'] = user_id
        request.data['game_id'] = game_id

        # Instantiate the serializer with the validated data
        serializer = GameRatingBaseSerializer(data=request.data)

        # Check if the serializer is valid
        if serializer.is_valid():
            try:
                # Create the game rating entry
                created_rating = serializer.create(serializer.validated_data)

                # Return the created rating with a 201 status
                return Response(created_rating, status=status.HTTP_201_CREATED)

            except serializers.ValidationError as e:
                # Return validation error response
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                # Catch any unexpected errors
                return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # If serializer is invalid, return the validation errors
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


