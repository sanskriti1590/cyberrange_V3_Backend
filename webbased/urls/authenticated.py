from django.urls import path

from webbased.api.views.categories.authenticated import CategoryAPIView
from webbased.api.views.games.authenticated import WebbasedGamesAPIView, WebbasedGameDetailAPIView
from webbased.api.views.games.console_pages import ConsolePageDetailAPIView
from webbased.api.views.games.flags import WebbasedGameFlagSubmitAPIView
from webbased.api.views.games.players import WebbasedGameStartAPIView, WebbasedGameEndAPIView, GetPlayersByGameAPIView
from webbased.api.views.games.ratings import GameRatingCreateAPIView

app_name = 'authenticated_webbased_categories_api'
urlpatterns = [
    path('categories', CategoryAPIView.as_view(), name='webbased_categories_list_api_endpoints'),
    path('games_playgroud/<str:_id>', ConsolePageDetailAPIView.as_view(), name='webbased_console_page_detail_endpoints'),

    path('games', WebbasedGamesAPIView.as_view(), name='webbased_game_list_endpoints'),
    path('games/<str:game_id>', WebbasedGameDetailAPIView.as_view(), name='webbased_game_detail_endpoints'),
    path('games/<str:game_id>/start', WebbasedGameStartAPIView.as_view(), name='webbased_game_start_endpoints'),
    path('games/<str:game_id>/end', WebbasedGameEndAPIView.as_view(), name='webbased_game_end_endpoints'),
    path('games/<str:game_id>/players', GetPlayersByGameAPIView.as_view(), name='webbased_game_players_endpoints'),
    path('games/<str:game_id>/ratings', GameRatingCreateAPIView.as_view(), name='webbased_game_ratings_endpoints'),
    path('games/<str:game_id>/flags_submit', WebbasedGameFlagSubmitAPIView.as_view(), name='webbased_game_flags_submit_endpoints'),
]
