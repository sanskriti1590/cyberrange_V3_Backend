from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import (
    ScenarioCategoryListView,
    ScenarioCreateView,
    ScenarioGameDraftView,
    ScenarioInfraCreateView,
    ScenarioListView,
    ScenarioGameStartView,
    ScenarioAcceptInvitationView,
    ScenarioDenyInvitationView,
    ScenarioGameConsoleView,
    ScenarioActiveGameListView,
    ScenarioGameDetailView,
    ScenarioGameDeleteView,
    ScenarioSubmitFlagView,
    ScenariosByCategoryIdView,
    ScenarioTopologyView,
    ScenarioUserEmailStatusView,
    ScenarioIPListView,
)

app_name = "scenario-management"

urlpatterns = [
    path('category/list/', ScenarioCategoryListView.as_view(), name='scenario-category-list'),

    path('create/', ScenarioCreateView.as_view(), name='scenario-create'),
    path('draft/list/', ScenarioGameDraftView.as_view(), name='scenario-draft-list'),
    path('infra/create/', ScenarioInfraCreateView.as_view(), name='scenario-infra-create'),
    path('list/', ScenarioListView.as_view(), name='scenario-list'),

    path('game/start/', ScenarioGameStartView.as_view(), name='scenario-game-start'),
    path('game/flag/submit/', ScenarioSubmitFlagView.as_view(), name='scenario-flag-submit'),
    path('game/delete/<slug:scenario_game_id>/', ScenarioGameDeleteView.as_view(), name='scenario-game-delete'),
    path('invitation/accept/<slug:invitation_id>/', ScenarioAcceptInvitationView.as_view(), name='scenario-accept-invitation'),
    path('invitation/deny/<slug:invitation_id>/', ScenarioDenyInvitationView.as_view(), name='scenario-deny-invitation'),

    path('game/console/<slug:scenario_game_id>/', ScenarioGameConsoleView.as_view(), name='scenario-game-console'),
    path('game/ips/<slug:scenario_game_id>/', ScenarioIPListView.as_view(), name='scenario-game-ips'),
    path('game/topology/<slug:scenario_id>/',ScenarioTopologyView.as_view(), name= "topology-view"),
    path('game/based-on-category/<slug:category_id>/', ScenariosByCategoryIdView.as_view(), name='scenario-game-list'),
    path('game/user-status/<str:email>/',ScenarioUserEmailStatusView.as_view(), name= "user-email-status"),
    path('active/game/', ScenarioActiveGameListView.as_view(), name='scenario-active-games'),
    path('game/<slug:scenario_id>/', ScenarioGameDetailView.as_view(), name='scenario-game-detail'),
]


urlpatterns = format_suffix_patterns(urlpatterns)