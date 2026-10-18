from django.urls import path
from . import views

urlpatterns = [
    path('saas/', views.saas_dashboard_view, name='saas_dashboard'),
    path('saas/install/', views.saas_install_client_view, name='saas_install_client'),
    path('saas/clients/<slug:slug>/', views.saas_client_detail_view, name='saas_client_detail'),
    path('saas/clients/<slug:slug>/edit/', views.saas_client_edit_view, name='saas_client_edit'),
    path('saas/clients/<slug:slug>/toggle/', views.saas_client_toggle_status_view, name='saas_client_toggle_status'),
    path('saas/clients/<slug:slug>/reset-password/', views.saas_client_reset_password_view, name='saas_client_reset_password'),
    path('saas/clients/<slug:slug>/delete/', views.saas_client_delete_view, name='saas_client_delete'),
    path('saas/export/csv/', views.saas_export_tenants_csv_view, name='saas_export_tenants_csv'),
    path('saas/switch/<int:tenant_id>/', views.saas_switch_tenant_view, name='saas_switch_tenant'),
    path('saas/switch/exit/', views.saas_switch_tenant_view, {'tenant_id': 0}, name='saas_exit_tenant'),
]
