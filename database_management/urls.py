from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

app_name = "database-management"

urlpatterns = [
    # path('admin/users/<slug:pk>/', UpdateUserAdminView.as_view(), name='update-user'),
]


urlpatterns = format_suffix_patterns(urlpatterns)
