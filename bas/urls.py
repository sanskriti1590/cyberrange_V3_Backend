from django.urls import path

from .views import (
    AssetsView,
    ChainsView,
    ExecutionsView,
    ExecutionReportView,
    ExecuteChainView,
)

urlpatterns = [
    path("assets/", AssetsView.as_view(), name="get_all_assets"),
    path("chains/", ChainsView.as_view(), name="get_chains_list"),
    path("chains/<str:chain_id>/", ExecuteChainView.as_view(), name="execute_chain"),
    path("executions/", ExecutionsView.as_view(), name="get_executions"),
    path("executions/<str:execution_id>/", ExecutionReportView.as_view(), name="get_execution_report"),
]
