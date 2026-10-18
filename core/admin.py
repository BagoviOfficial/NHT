from django.contrib import admin
from .models import SiteSettings, FieldConfig, ChoiceConfig


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'currency', 'head_office', 'support_phone', 'updated_at']

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FieldConfig)
class FieldConfigAdmin(admin.ModelAdmin):
    list_display = ['field_key', 'label', 'is_required', 'is_visible', 'order', 'is_active']
    list_filter = ['is_required', 'is_visible', 'is_active']
    search_fields = ['field_key', 'label']


@admin.register(ChoiceConfig)
class ChoiceConfigAdmin(admin.ModelAdmin):
    list_display = ['category', 'key', 'label', 'is_default', 'order', 'is_active']
    list_filter = ['category', 'is_default', 'is_active']
    search_fields = ['category', 'key', 'label']
