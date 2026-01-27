from django.urls import path, include

app_name = 'webbased_api'

urlpatterns = [
    path('admin/web-based/', include('webbased.urls.admin'), name='admin_webbased_api'),
    path('web-based/', include('webbased.urls.authenticated'), name='admin_webbased_api'),
    path('bas/', include('bas.urls'), name="bas_api"),
    path('dashboard/', include('dashboard.api_endpoints'), name="dashboard_apis"),

]
