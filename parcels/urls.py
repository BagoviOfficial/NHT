from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.home_view, name='home'),
    path('track/', views.public_track_view, name='track_search'),
    path('track/<str:tracking_number>/', views.public_track_view, name='public_track'),

    # Staff Operations
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('shipments/', views.parcel_list_view, name='parcel_list'),
    path('shipments/new/', views.parcel_create_view, name='parcel_create'),
    path('shipments/<str:tracking_number>/', views.parcel_detail_view, name='parcel_detail'),
    path('shipments/<str:tracking_number>/edit/', views.parcel_update_view, name='parcel_update'),
    path('shipments/<str:tracking_number>/dispatch/', views.parcel_dispatch_view, name='parcel_dispatch'),
    path('shipments/<str:tracking_number>/arrive/', views.parcel_mark_arrived_view, name='parcel_arrive'),
    path('shipments/<str:tracking_number>/awaiting/', views.parcel_mark_awaiting_view, name='parcel_awaiting'),
    path('shipments/<str:tracking_number>/collect/', views.parcel_collect_view, name='parcel_collect'),
    path('shipments/<str:tracking_number>/cancel/', views.parcel_cancel_view, name='parcel_cancel'),
    path('shipments/<str:tracking_number>/override/', views.parcel_admin_override_view, name='parcel_override'),
    path('shipments/<str:tracking_number>/receipt/', views.parcel_receipt_view, name='parcel_receipt'),
]
