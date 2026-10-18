from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-change/', views.password_change_view, name='password_change'),

    # User Management (Super Admin)
    path('admin-panel/users/', views.user_list_view, name='admin_panel_users'),
    path('admin-panel/users/new/', views.user_create_view, name='user_create'),
    path('admin-panel/users/<int:pk>/edit/', views.user_update_view, name='user_update'),
    path('admin-panel/users/<int:pk>/toggle/', views.user_toggle_active_view, name='user_toggle_active'),
    path('admin-panel/users/<int:pk>/reset-password/', views.user_password_reset_view, name='user_password_reset'),
]
