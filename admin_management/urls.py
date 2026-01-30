from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import (
    UserUpdateAdminView, 
    UserRegisterAdminView,
    UserListAdminView,
    UserRetrieveAdminView,
    UserRemoveAdminView,

    CTFCategoryListView,
    CTFCategoryCreateView,
    CTFCategoryUpdateView,
    CTFUnmappedGameView,
    CTFMappedGameView,
    CTFGameMappingView,
    CTFMappingDeleteView,
    CTFGameListView,
    CTFGameUpdateView,

    ScenarioCategoryListView,
    ScenarioCategoryCreateView,
    ScenarioCategoryUpdateView,
    ScenarioApproveView,
    ScenarioUnapproveView,
    ScenarioGameListView,
    ScenarioGameUpdateView,
    ScenarioGameDocumentRemoveView,
    ImageValidateView,

    GetCTFScenarioView,
    AddCTFForUserView,
    AddScenarioForUserView,
    AddCorporateForUserView,
    RemoveCTFScenarioForUserView,
    GetCTFScenarioForUserSpecificView,

    CorporateApproveCreateView,
    CorporateApproveListView,
    CorporateUnapproveView,
    CorporateInfraReviewSaveView,
    CorporateInfraReviewGetView,
    AdminCorporateScenarioUpdateView,
    AdminCorporateScenarioPhaseUpdateView,
    AdminCorporateScenarioFlagUpdateView,
    AdminCorporateScenarioMilestoneUpdateView,
    AdminCorporateScenarioDetailView,
)


app_name = "admin"

urlpatterns = [
    path('user/list/', UserListAdminView.as_view(), name='user-list'),
    path('user/register/', UserRegisterAdminView.as_view(), name='user-register'),
    path('user/<slug:user_id>/', UserRetrieveAdminView.as_view(), name='user-retrieve'),
    path('user/update/<slug:user_id>/', UserUpdateAdminView.as_view(), name='user-update'),
    path('user/remove/<slug:pk>/', UserRemoveAdminView.as_view(), name='remove-user'),

    path('ctf/category/list/', CTFCategoryListView.as_view(), name='ctf-category-list'),
    path('ctf/category/create/', CTFCategoryCreateView.as_view(), name='ctf-category-create'),
    path('ctf/category/update/<slug:ctf_category_id>/', CTFCategoryUpdateView.as_view(), name='ctf-category-update'),
    path('ctf/unmapped-game/list/', CTFUnmappedGameView.as_view(), name='ctf-unmapped-list'),
    path('ctf/mapped-game/', CTFMappedGameView.as_view(), name='ctf-map-game'),
    path('ctf/map-game/', CTFGameMappingView.as_view(), name='ctf-map-game'),
    path('ctf/mapping/delete/<slug:mapping_id>/', CTFMappingDeleteView.as_view(), name='ctf-delete-mapping'),
    path('ctf/game/list/', CTFGameListView.as_view(), name='ctf-game-list'),
    path('ctf/game/update/<slug:ctf_id>/', CTFGameUpdateView.as_view(), name='ctf-game-update'),

    path('scenario/category/list/', ScenarioCategoryListView.as_view(), name='scenario-category-list'),
    path('scenario/category/create/', ScenarioCategoryCreateView.as_view(), name='scenario-category-create'),
    path('scenario/category/update/<slug:scenario_category_id>/', ScenarioCategoryUpdateView.as_view(), name='scenario-category-update'),
    path('scenario/game-approve/', ScenarioApproveView.as_view(), name='scenario-approve'),
    path('scenario/game-unapprove/', ScenarioUnapproveView.as_view(), name='scenario-unapprove'),
    path('scenario/game/list/', ScenarioGameListView.as_view(), name='scenario-game-list'),
    path('scenario/game/update/<slug:scenario_id>/', ScenarioGameUpdateView.as_view(), name='scenario-game-update'),
    path('scenario/game/document/remove/',ScenarioGameDocumentRemoveView.as_view(), name='scenario-game-document-remove'),

    path('image_credential/create/', ImageValidateView.as_view(), name='image-credit-creation'),

    path('user-specific/<slug:keyword>/<slug:user_id>/', GetCTFScenarioView.as_view(), name='user-specific-ctf-scenario'),
    path('user/ctfs/<slug:user_id>/', AddCTFForUserView.as_view(), name='add-user-specific-ctf'),
    path('user/scenarios/<slug:user_id>/', AddScenarioForUserView.as_view(), name='add-user-specific-scenario'),
    path('user/corporates/<slug:user_id>/', AddCorporateForUserView.as_view(), name='add-user-specific-corporate'),
    path('user-specific/<slug:keyword>/<slug:user_id>/<slug:item_id>/', RemoveCTFScenarioForUserView.as_view(), name='remove-user-specific-ctf-scenario'),
    path('game/based-on-category/<slug:game_type>/<slug:category_id>/<slug:user_id>/', GetCTFScenarioForUserSpecificView.as_view(), name='get-based-on-category-user-ctf-scenario'),

    path("corporate/game-approve/", CorporateApproveListView.as_view(), name="corporate-approve-list"),
    path("corporate/game-approve/submit/", CorporateApproveCreateView.as_view(), name="corporate-approve-submit"),
    path('corporate/game-unapprove/', CorporateUnapproveView.as_view(), name='corporate-unapprove'),
    path("corporate/infra-review/", CorporateInfraReviewGetView.as_view(), name="corporate-infra-review"),
    path("corporate/infra-review/save/", CorporateInfraReviewSaveView.as_view(),  name="corporate-infra-review-save"),
    path("corporate/scenario/update-basic/", AdminCorporateScenarioUpdateView.as_view(), name="corporate-scenario-update-basic"),
    path("corporate/scenario/update-phases/", AdminCorporateScenarioPhaseUpdateView.as_view(), name="corporate-scenario-update-phases"),
    path("corporate/scenario/update-flags/", AdminCorporateScenarioFlagUpdateView.as_view(), name="corporate-scenario-update-flags"),
    path("corporate/scenario/update-milestones/", AdminCorporateScenarioMilestoneUpdateView.as_view(), name="corporate-scenario-update-milestones"),
    path("corporate/scenario/detail/<str:scenario_id>/",AdminCorporateScenarioDetailView.as_view(),name="admin-corporate-scenario-detail",),
]

urlpatterns = format_suffix_patterns(urlpatterns)
