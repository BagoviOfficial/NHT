"""
URL configuration for Northern Highways Transporters Parcel Management System.
"""

from django.contrib import admin
from django.urls import path, include
from core import views as core_views
from audit import views as audit_views

urlpatterns = [
    # WordPress-Style Web Installer Wizard
    path('', include('installer.urls')),

    # SaaS Multi-Tenant Platform Master URLs
    path('', include('tenants.urls')),

    # Secondary Django Admin
    path('admin/', admin.site.urls),

    # Custom Super Admin Panel (Section 27)
    path('admin-panel/', core_views.admin_panel_view, name='admin_panel'),
    path('admin-panel/settings/', core_views.settings_update_view, name='admin_panel_settings'),
    path('admin-panel/config/', core_views.config_list_view, name='admin_panel_config'),
    path('admin-panel/config/fields/<int:pk>/edit/', core_views.field_config_edit_view, name='field_config_edit'),
    path('admin-panel/config/choices/new/', core_views.choice_config_create_view, name='choice_config_create'),
    path('admin-panel/config/choices/<int:pk>/edit/', core_views.choice_config_edit_view, name='choice_config_edit'),
    path('admin-panel/config/choices/<int:pk>/toggle/', core_views.choice_config_toggle_view, name='choice_config_toggle'),
    path('admin-panel/audit/', audit_views.audit_log_list_view, name='admin_panel_audit'),

    # Routes Management
    path('routes/', include('routes.urls')),

    # Accounts & User Management
    path('', include('accounts.urls')),

    # Reports & Statements
    path('', include('reports.urls')),

    # Parcels, Public Home & Tracking (root match)
    path('', include('parcels.urls')),
]

# Custom HTTP Error Handlers (Section 30)
handler400 = 'core.views.bad_request_view'
handler403 = 'core.views.permission_denied_view'
handler404 = 'core.views.not_found_view'
handler500 = 'core.views.server_error_view'
