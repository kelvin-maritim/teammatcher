from django.urls import path
from . import views

urlpatterns = [
    path("team-sets/", views.TeamSetListCreateView.as_view(), name="teamset-list-create"),
    path("team-sets/<int:pk>/", views.TeamSetDetailView.as_view(), name="teamset-detail"),
    path("teams/", views.TeamListCreateView.as_view(), name="team-list-create"),
    path("teams/<int:pk>/", views.TeamDetailView.as_view(), name="team-detail"),
    path("assignments/", views.TeamAssignmentListCreateView.as_view(), name="assignment-list-create"),
    path("assignments/<int:pk>/", views.TeamAssignmentUpdateView.as_view(), name="assignment-update"),
]
