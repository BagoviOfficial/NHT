from django.contrib import admin
from .models import (
    Branch, UserProfile, ShippingRate, Parcel,
    ParcelTrackingLog, TransitManifest, PickupRequest, CustomerInquiry
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'branch_type', 'city', 'phone', 'is_active')
    list_filter = ('branch_type', 'is_active', 'state')
    search_fields = ('code', 'name', 'city', 'address')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'branch', 'phone', 'is_available')
    list_filter = ('role', 'is_available', 'branch')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = ('service_type', 'base_price', 'per_kg_rate', 'fragile_fee', 'insurance_rate_pct', 'delivery_time_frame')


class ParcelTrackingLogInline(admin.TabularInline):
    model = ParcelTrackingLog
    extra = 1
    readonly_fields = ('created_at',)


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = (
        'tracking_number', 'sender_name', 'receiver_name',
        'origin_branch', 'destination_branch', 'status',
        'service_type', 'total_price', 'payment_status', 'created_at'
    )
    list_filter = ('status', 'payment_status', 'service_type', 'delivery_type', 'category', 'origin_branch', 'destination_branch')
    search_fields = ('tracking_number', 'sender_name', 'receiver_name', 'sender_phone', 'receiver_phone')
    inlines = [ParcelTrackingLogInline]
    readonly_fields = ('tracking_number', 'security_otp', 'created_at', 'updated_at')


@admin.register(ParcelTrackingLog)
class ParcelTrackingLogAdmin(admin.ModelAdmin):
    list_display = ('parcel', 'status', 'location_name', 'activity', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('parcel__tracking_number', 'location_name', 'activity')


@admin.register(TransitManifest)
class TransitManifestAdmin(admin.ModelAdmin):
    list_display = ('manifest_number', 'origin_branch', 'destination_branch', 'driver_name', 'vehicle_plate', 'status', 'created_at')
    list_filter = ('status', 'origin_branch', 'destination_branch')
    search_fields = ('manifest_number', 'driver_name', 'vehicle_plate')
    filter_horizontal = ('parcels',)


@admin.register(PickupRequest)
class PickupRequestAdmin(admin.ModelAdmin):
    list_display = ('request_number', 'customer_name', 'customer_phone', 'pickup_city', 'preferred_date', 'status', 'assigned_courier')
    list_filter = ('status', 'preferred_time_slot', 'branch')
    search_fields = ('request_number', 'customer_name', 'customer_phone', 'pickup_city')


@admin.register(CustomerInquiry)
class CustomerInquiryAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'name', 'subject', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('ticket_number', 'name', 'email', 'subject')
