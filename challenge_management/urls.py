from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import (GameChallengedListView,
                    GameChallengeView,
                    GameChallengeDeleteView,
                    )

app_name = "challenge-management"

urlpatterns = [
    path('game/challenged/list/<slug:game_type>/',GameChallengedListView.as_view(), name='game-challenge'),
    path('game/create/', GameChallengeView.as_view(), name='game-challenge-create'),
    path('game/delete/<slug:ctf_or_scenario_id>/',GameChallengeDeleteView.as_view(),name='game-challenge-delete'),

]


urlpatterns = format_suffix_patterns(urlpatterns)
