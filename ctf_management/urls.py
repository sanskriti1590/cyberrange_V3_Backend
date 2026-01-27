from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import (
    CTFCategoryListView,
    CTFGameView,
    CTFGameDraftView,
    CTFGameMachineView,
    CTFGameDetailView,
    CTFStartGameView,
    CTFGameConsoleView,
    CTFGameExtendTimeView,
    CTFSubmitFlagView,
    CTFActiveGameListView,
    CTFDeleteGameView,
    CTFRatedSeverityView,
    CTFGameListView,
    CTFTargetIPView,
    CTFLMSListView,
    CTFGetScoreByGameIdView
)

app_name = "ctf-management"

urlpatterns = [
    path('category/list/', CTFCategoryListView.as_view(), name='ctf-category-list'),

    path('game/create/', CTFGameView.as_view(), name='ctf-game-create'),
    path('game/draft/list/', CTFGameDraftView.as_view(), name='ctf-draft-list'),
    path('game/create/target/upload/', CTFGameMachineView.as_view(), name='ctf-target-upload'),

    path('game/start/', CTFStartGameView.as_view(), name='ctf-game-start'),
    path('game/severity/rate/', CTFRatedSeverityView.as_view(), name='ctf-rate-severity'),
    path('game/extend-time/', CTFGameExtendTimeView.as_view(), name='ctf-extend-time'),
    path('game/flag/submit/', CTFSubmitFlagView.as_view(), name='ctf-flag-submit'),
    path('game/active/list/', CTFActiveGameListView.as_view(), name='ctf-active-games'),
    path('game/console/<slug:ctf_game_id>/', CTFGameConsoleView.as_view(), name='ctf-game-console'),
    path('game/delete/<slug:ctf_game_id>/', CTFDeleteGameView.as_view(), name='ctf-game-delete'),
    path('game/ip/<slug:ctf_game_id>/', CTFTargetIPView.as_view(), name='ctf-target-ip'),
    path('game/based-on-category/<slug:category_id>/', CTFGameListView.as_view(), name='ctf-game-list'),
    path('game/ctf_list/', CTFLMSListView.as_view(), name='ctf-list'),
    path('game/score_by_id/', CTFGetScoreByGameIdView.as_view(), name='ctf-score-by-id'),
    path('game/<slug:ctf_id>/', CTFGameDetailView.as_view(), name='ctf-game-detail'),
   
]


urlpatterns = format_suffix_patterns(urlpatterns)
