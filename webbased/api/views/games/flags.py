from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.permissions import CustomIsAuthenticated
from webbased.api.serializers.flags import GameFlagSubmitSerializer


class WebbasedGameFlagSubmitAPIView(APIView):
    permission_classes = [CustomIsAuthenticated]

    def post(self, request, game_id):
        # Extract the user_id directly from request
        user_id = request.user.get('user_id')

        # Attach the game_id, user_id, and payed_game_id to the request data
        request.data['user_id'] = user_id
        request.data['game_id'] = game_id

        serializer = GameFlagSubmitSerializer(data=request.data)
        if serializer.is_valid():
            try:
                result = serializer.create(validated_data=serializer.validated_data)
                return Response(result, status=status.HTTP_200_OK)
            except ValidationError as e:
                # If a ValidationError occurs, we return a custom error response
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                # Catch any unexpected errors
                return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



