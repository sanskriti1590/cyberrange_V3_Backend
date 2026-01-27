from django.urls import path, include

app_name = 'dashboard_api'

urlpatterns = [
    path('users/', include('dashboard.routes.users'), name="dashboard_user_apis"),
    path('scenarios/', include('dashboard.routes.scenarios'), name="dashboard_scenarios_apis"),
    path('analytics/', include('dashboard.routes.analytics'), name="dashboard_analytics_apis"),

]
