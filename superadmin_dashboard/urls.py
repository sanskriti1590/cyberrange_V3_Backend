
from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import * 

app_name = "superadmin"

urlpatterns = [

    # ======================================================
    # ACTIVE SCENARIOS
    # ======================================================

    path(
        'scenario/active/',
        SuperAdminActiveScenariosView.as_view(),
        name='superadmin-active-scenarios'
    ),

    path(
        'scenario/active/<slug:active_scenario_id>/overview/',
        SuperAdminActiveScenarioOverviewView.as_view(),
        name='superadmin-active-scenario-overview'
    ),

    path(
        'scenario/active/<slug:active_scenario_id>/leaderboard/',
        SuperAdminActiveScenarioLeaderboardView.as_view(),
        name='superadmin-active-scenario-leaderboard'
    ),

    # ======================================================
    # CONFIG ACTIONS
    # ======================================================

    path(
        'scenario/manual-score/',
        SuperAdminManualScoreView.as_view(),
        name='superadmin-manual-score'
    ),

    path(
        'scenario/flag/toggle-lock/',
        SuperAdminToggleFlagLockView.as_view(),
        name='superadmin-flag-lock'
    ),

    path(
        'scenario/milestone/toggle-lock/',
        SuperAdminToggleMilestoneLockView.as_view(),
        name='superadmin-milestone-lock'
    ),

    path(
        'scenario/phase/toggle-lock/',
        SuperAdminTogglePhaseLockView.as_view(),
        name='superadmin-phase-lock'
    ),

        
    path(
        "scenario/console-monitor/",
        SuperAdminScenarioConsoleMonitorView.as_view(),
        name="superadmin-console-monitor"
    ),
]


urlpatterns = format_suffix_patterns(urlpatterns)