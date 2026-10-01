from django.urls import path
from . import views

urlpatterns = [
    # Public pages
    path('', views.home_view, name='home'),
    path('track/', views.track_parcel_view, name='track_search'),
    path('track/<str:tracking_number>/', views.track_parcel_view, name='track_detail'),
    path('calculator/', views.rate_calculator_view, name='rate_calculator'),
    path('branches/', views.branches_view, name='branches'),
    path('contact/', views.contact_view, name='contact'),
    path('request-pickup/', views.request_pickup_public_view, name='request_pickup_public'),

    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Parcels management (Staff / Admin)
    path('parcels/', views.parcel_list_view, name='parcel_list'),
    path('parcels/create/', views.parcel_create_view, name='parcel_create'),
    path('parcels/<str:tracking_number>/', views.parcel_detail_view, name='parcel_detail'),
    path('parcels/<str:tracking_number>/update-status/', views.parcel_update_status_view, name='parcel_update_status'),
    path('parcels/<str:tracking_number>/assign-courier/', views.parcel_assign_courier_view, name='parcel_assign_courier'),
    path('parcels/<str:tracking_number>/waybill/', views.parcel_waybill_view, name='parcel_waybill'),
    path('parcels/<str:tracking_number>/invoice/', views.parcel_invoice_view, name='parcel_invoice'),

    # Linehaul & Transit Manifests
    path('manifests/', views.manifest_list_view, name='manifest_list'),
    path('manifests/create/', views.manifest_create_view, name='manifest_create'),
    path('manifests/<str:manifest_number>/', views.manifest_detail_view, name='manifest_detail'),
    path('manifests/<str:manifest_number>/dispatch/', views.manifest_dispatch_view, name='manifest_dispatch'),
    path('manifests/<str:manifest_number>/receive/', views.manifest_receive_view, name='manifest_receive'),

    # Courier Delivery Actions
    path('courier/deliveries/<str:tracking_number>/action/', views.courier_delivery_action_view, name='courier_delivery_action'),

    # Pickup Requests
    path('pickups/', views.pickup_list_view, name='pickup_list'),
    path('pickups/<str:request_number>/assign/', views.pickup_assign_view, name='pickup_assign'),
    path('pickups/<str:request_number>/convert/', views.pickup_convert_view, name='pickup_convert'),

    # Support / Inquiries
    path('inquiries/', views.inquiry_list_view, name='inquiry_list'),
    path('inquiries/<str:ticket_number>/', views.inquiry_detail_view, name='inquiry_detail'),

    # APIs
    path('api/calculate-rate/', views.api_calculate_rate, name='api_calculate_rate'),
    path('api/quick-track/<str:tracking_number>/', views.api_quick_track, name='api_quick_track'),
]
