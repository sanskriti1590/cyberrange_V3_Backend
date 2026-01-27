from django.urls import path

from webbased.api.views.categories.admin import CategoryAPIView, CategoryDetailAPIView

app_name = 'webbased_categories_api_endpoints'  # Define the app_name for namespacing

urlpatterns = [
    path('', CategoryAPIView.as_view(), name='category_list_and_create_endpoint'),
    path('<str:category_id>/', CategoryDetailAPIView.as_view(), name='category_detail_endpoint'),
]
