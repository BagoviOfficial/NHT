from django.core.cache import cache
from .models import SiteSettings, FieldConfig, ChoiceConfig


def get_site_settings(tenant=None):
    """Retrieve cached site settings for tenant or global fallback."""
    return SiteSettings.load(tenant=tenant)


def get_field_configs(tenant=None):
    """Retrieve all active field configurations mapped by field_key for tenant."""
    cache_key = f'field_configs_cache_tenant_{tenant.pk}' if tenant else 'field_configs_cache'
    configs = cache.get(cache_key)
    if configs is None:
        qs = FieldConfig.objects.filter(tenant=tenant, is_active=True).order_by('order')
        if not qs.exists() and tenant:
            # Fallback to global defaults if tenant has no specific overrides
            qs = FieldConfig.objects.filter(tenant=None, is_active=True).order_by('order')
        configs = {cfg.field_key: cfg for cfg in qs}
        cache.set(cache_key, configs, timeout=3600)
    return configs


def get_active_choices(category, tenant=None):
    """Retrieve active choices for a specific category as (key, label) tuples."""
    cache_key = f'choice_configs_{tenant.pk}_{category}' if tenant else f'choice_configs_{category}'
    choices = cache.get(cache_key)
    if choices is None:
        qs = ChoiceConfig.objects.filter(tenant=tenant, category=category, is_active=True).order_by('order', 'label')
        if not qs.exists() and tenant:
            # Fallback to global defaults
            qs = ChoiceConfig.objects.filter(tenant=None, category=category, is_active=True).order_by('order', 'label')
        choices = [(c.key, c.label) for c in qs]
        cache.set(cache_key, choices, timeout=3600)
    return choices


def apply_dynamic_field_configs(form, tenant=None):
    """
    Applies configured labels, placeholders, help_text, and required rules
    to form fields dynamically. Never executes arbitrary code.
    """
    configs = get_field_configs(tenant=tenant)
    for field_name, field in form.fields.items():
        if field_name in configs:
            cfg = configs[field_name]
            if cfg.label:
                field.label = cfg.label
            if cfg.placeholder:
                field.widget.attrs['placeholder'] = cfg.placeholder
            if cfg.help_text:
                field.help_text = cfg.help_text
            field.required = cfg.is_required
            if not cfg.is_visible:
                field.widget.attrs['style'] = 'display:none;'
