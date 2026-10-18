from django.contrib import admin
from .models import Route


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ['name', 'origin', 'is_active', 'created_at']
    list_filter = ['is_active', 'origin']
    search_fields = ['name', 'origin', 'description']
    prepopulated_fields = {'slug': ('name',)}
