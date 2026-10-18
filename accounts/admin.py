from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'phone', 'first_name', 'last_name', 'role', 'assigned_route', 'is_active', 'is_staff']
    list_filter = ['role', 'is_active', 'is_staff', 'assigned_route']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Operational Role & Location', {
            'fields': ('phone', 'role', 'assigned_route')
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Operational Role & Location', {
            'fields': ('phone', 'role', 'assigned_route')
        }),
    )
    search_fields = ['username', 'first_name', 'last_name', 'phone', 'email']
