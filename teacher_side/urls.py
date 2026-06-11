from django.urls import path
from . import views

app_name = "teacher_side"

urlpatterns = [
    path('', views.index, name='index'),
    path('download/', views.download_csv, name='download_csv'),
    path('download/<int:generation_id>/', views.download_historical_csv, name='download_historical_csv'),
    path('dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/api/load/', views.dashboard_api_load, name='dashboard_api_load'),
    path('dashboard/api/export/', views.dashboard_api_export, name='dashboard_api_export'),
    path('dashboard/api/mismatch/', views.dashboard_api_mismatch, name='dashboard_api_mismatch'),
]