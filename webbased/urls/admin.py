from django.urls import path, include

app_name = 'admin_webbased_categories_api'
urlpatterns = [
    path('categories/', include('webbased.api.urls.categories'), name='webbased_categories_api_endpoints'),
    path('games/', include('webbased.api.urls.web_based_game'), name='webbased_games_api_endpoints'),
]
