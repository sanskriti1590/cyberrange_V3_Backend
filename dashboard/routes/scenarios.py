from django.urls import path

from dashboard.apis.corporate import ScenariosListAPIView, ActiveScenariosListAPIView, ActiveScenarioDetailAPIView, ActiveScenarioConsoleAPIView, StartScenarioAPIView, EndScenarioAPIView, \
    ScenarioDetailAPIView

urlpatterns = [
    path("", ScenariosListAPIView.as_view(), name="get_all_scenarios"),

    path("active", ActiveScenariosListAPIView.as_view(), name="get_all_active_scenarios"),
    path("active/<str:id>", ActiveScenarioDetailAPIView.as_view(), name="get_active_scenario_details"),
    path("active/<str:id>/console", ActiveScenarioConsoleAPIView.as_view(), name="get_active_scenario_console_details"),

    path("<str:scenario_id>", ScenarioDetailAPIView.as_view(), name="get_scenario_details"),
    path("<str:id>/start", StartScenarioAPIView.as_view(), name="start_scenario"),
    path("<str:id>/end", EndScenarioAPIView.as_view(), name="end_scenario"),


]
