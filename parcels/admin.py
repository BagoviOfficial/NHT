from django.contrib import admin
from .models import Parcel, ShipmentItem, ParcelStatusHistory


class ShipmentItemInline(admin.TabularInline):
    model = ShipmentItem
    extra = 1


class ParcelStatusHistoryInline(admin.TabularInline):
    model = ParcelStatusHistory
    extra = 0
    readonly_fields = ['old_status', 'new_status', 'user', 'note', 'ip_address', 'created_at']
    can_delete = False


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = [
        'tracking_number', 'route', 'sender_name', 'receiver_name',
        'status', 'payment_status', 'price', 'created_at'
    ]
    list_filter = ['status', 'payment_status', 'payment_method', 'route', 'created_at']
    search_fields = [
        'tracking_number', 'sender_name', 'sender_phone',
        'receiver_name', 'receiver_phone', 'receiver_id_number', 'truck_plate_number'
    ]
    inlines = [ShipmentItemInline, ParcelStatusHistoryInline]
    readonly_fields = ['tracking_number', 'created_at', 'updated_at']


@admin.register(ParcelStatusHistory)
class ParcelStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['parcel', 'old_status', 'new_status', 'user', 'created_at']
    list_filter = ['new_status', 'created_at']
    search_fields = ['parcel__tracking_number', 'note']
    readonly_fields = ['parcel', 'old_status', 'new_status', 'user', 'note', 'ip_address', 'created_at']
