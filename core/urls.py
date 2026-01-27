from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import (
    CTFForceDeleteGameView,
    MailingListView,
    InstanceEssentialsView,
    ScenarioForceDeleteGameView,
    TotalResourcesView,
    NewsListView,
)

app_name = "core"

urlpatterns = [
    path('game/force/delete/<slug:ctf_game_id>/', CTFForceDeleteGameView.as_view(), name='ctf-force-game-delete'),
    path('scenario/game/force/delete/<slug:scenario_game_id>/', ScenarioForceDeleteGameView.as_view(), name='scenario-force-game-delete'),
    path('mailing-list/', MailingListView.as_view(), name='mailing-list'),
    path('instance/essentials/list/', InstanceEssentialsView.as_view(), name= "instance-essentials"),
    path('total/resources/', TotalResourcesView.as_view(), name= "total-resources"),
    path('news/', NewsListView.as_view(), name= "total-resources")

]

urlpatterns = format_suffix_patterns(urlpatterns)