from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import *

app_name = "corporate-management"

urlpatterns = [
    path('scenario/create/', CorporateScenarioCreateView.as_view(), name='corporate-scenario-create'),
    path("scenario/phases/", CorporateScenarioPhaseCreateView.as_view()),
    path("scenario/flags/", CorporateScenarioFlagCreateView.as_view()),
    path("scenario/milestones/", CorporateScenarioMilestoneCreateView.as_view()),
    path('scenario/add-infra/', CorporateScenarioInfraView.as_view(), name='corporate-scenario-add-infra'),
    path('scenario/list/', CorporateScenarioListView.as_view(), name='corporate-scenario-list'),
    path('scenario/start/', CorporateScenarioStartView.as_view(), name='corporate-scenario-start'),
    path('scenario/submit-flag/', CorporateScenarioSubmitFlagView.as_view(), name='corporate-scenario-submit-flag'),
    path('scenario/achieve-milestone/', CorporateScenarioAchieveMilestoneView.as_view(), name='corporate-scenario-achieve-milestone'),
    path('scenario/approve-milestone/', CorporateScenarioApproveMilestoneView.as_view(), name='corporate-scenario-approve-milestone'),
    path('scenario/reject-milestone/', CorporateScenarioRejectMilestoneView.as_view(), name='corporate-scenario-reject-milestone'),
    path('scenario/show-hint/', CorporateScenarioShowHintView.as_view(), name='corporate-scenario-show-hint'),
    path('scenario/active/', CorporateActiveScenarioView.as_view(), name='corporate-active-scenario'),
    path('scenario/moderator/', CorporateScenarioModeratorView.as_view(), name='corporate-scenario-moderator'),
    path('scenario/moderator-console/', CorporateScenarioModeratorConsoleView.as_view(), name='corporate-scenario-moderator-console'),
    path('scenario/moderator-console/detail/', CorporateScenarioModeratorConsoleDetailView.as_view(), name='moderator-console-detail'),

    path('scenario/detail/<slug:scenario_id>/', CorporateScenarioDetailView.as_view(), name='corporate-scenario-detail'),
    path('scenario/achivers/<slug:scenario_id>/', CorporateScenarioAchiversView.as_view(), name='corporate-scenario-achivers'),
    path('scenario/<slug:active_scenario_id>/get-ips', ActiveCorporateScenarioGetipView.as_view(), name='active-corporate-scenario-ips-list'),
    path('scenario/console/<slug:active_scenario_id>/', CorporateScenarioConsoleView.as_view(), name='corporate-scenario-console'),
    path('scenario/delete/<slug:active_scenario_id>/', CorporateActiveScenarioDeleteView.as_view(), name='corporate-active-scenario-delete'),

    path('game/based-on-category/<slug:category_id>/', CorporateByCategoryIdView.as_view(), name='corporate-game-list'),

    path('scenario/generate-report/<slug:active_scenario_id>/<slug:user_id>/', CorporateGenerateScenarioReportView.as_view(), name='corporate-report-generate'),
    path('scenario/show-reports/<slug:user_id>/',CorporateUserReportView.as_view(), name='corporate-user-report'),
    path('scenario/report/<slug:participant_id>/<slug:user_id>/',CorporateUserReportApi.as_view(), name='corporate-report'),
    path("scenario/active_participants/<slug:active_scenario_id>/",ActiveParticipantView.as_view(),name="active_participants"), 

    path("scenario/flag-status/<slug:participant_id>/<slug:flag_id>/",FlagStatusView.as_view(),name="flag_status"), 
    path('game/topology/<slug:scenario_id>/',CorporateTopologyView.as_view(), name= "topology-view"),
    path("scenario/infra/<slug:infra_id>/",CorporateScenarioInfraDetailView.as_view(), name="infra-view"),
    path("corporate/scenario/console/switch-machine/",CorporateScenarioSwitchMachineView.as_view(),name="switch-console" ),
    path("corporate/scenario/admin/flag/toggle-lock/", CorporateScenarioAdminToggleFlagLockView.as_view(), name="flag-lock" ),
    path("corporate/scenario/admin/milestone/toggle-lock/", CorporateScenarioAdminToggleMilestoneLockView.as_view(),name="milestone-lock"),
    path( "corporate/scenario/admin/phase/toggle-lock/", CorporateScenarioAdminTogglePhaseLockView.as_view(),name="phase-locl" ),
    path( "corporate/scenario/scenario/walkthroughs/", CorporateScenarioWalkthroughListView.as_view(),name="corporate-scenario-walkthrough-list")

]

urlpatterns = format_suffix_patterns(urlpatterns)