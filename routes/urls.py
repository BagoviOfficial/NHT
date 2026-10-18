from django.urls import path
from . import views

urlpatterns = [
    path('', views.route_list_view, name='route_list'),
    path('new/', views.route_create_view, name='route_create'),
    path('<int:pk>/edit/', views.route_update_view, name='route_update'),
    path('<int:pk>/toggle/', views.route_toggle_view, name='route_toggle'),
    path('<int:pk>/delete/', views.route_delete_view, name='route_delete'),
]
