from django.urls import path
from . import views

urlpatterns = [
    path('install/', views.installer_view, name='installer'),
    path('setup/', views.installer_view, name='installer_setup'),
    path('install/health/', views.installer_health_check_api, name='installer_health_check'),
    path('install/test-db/', views.installer_test_db_api, name='installer_test_db'),
]
