from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'action', 'actor', 'object_type', 'object_identifier', 'ip_address']
    list_filter = ['action', 'object_type', 'timestamp']
    search_fields = ['action', 'object_identifier', 'actor__username', 'reason', 'ip_address']
    readonly_fields = [
        'actor', 'action', 'object_type', 'object_identifier',
        'ip_address', 'user_agent', 'old_values', 'new_values', 'reason', 'timestamp'
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
