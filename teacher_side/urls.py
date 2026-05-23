from django.urls import path
from . import views

app_name = "teacher_side"

urlpatterns = [
    path('', views.index, name='index'),
    path('download/', views.download_csv, name='download_csv'),
    path('download/<int:generation_id>/', views.download_historical_csv, name='download_historical_csv'),
    path('dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
]
