from django.urls import path

from webbased.api.views.games.web_based_game import WebbasedAPIView, ToggleWebBasedGameApprovalAPIView, WebbasedGameDetailAPIView

# Define the app_name for namespacing in URL patterns
app_name = 'webbased_games_api_endpoints'

urlpatterns = [
    path('', WebbasedAPIView.as_view(), name='webbased_games_list_and_create_endpoint'),
    path('<str:game_id>', WebbasedGameDetailAPIView.as_view(), name='webbased_games_get_and_update_endpoint'),
    path('<str:game_id>/toggle-approval/', ToggleWebBasedGameApprovalAPIView.as_view(), name='toggle_webbased_games_approval_endpoint'),

]
