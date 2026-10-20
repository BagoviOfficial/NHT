from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from accounts.decorators import super_admin_required
from .models import SiteSettings, FieldConfig, ChoiceConfig, ALLOWED_FIELD_KEYS, ALLOWED_CHOICE_CATEGORIES
from .forms import SiteSettingsForm, FieldConfigForm, ChoiceConfigForm
from audit.services import log_audit_event


# ==============================================================================
# HTTP ERROR HANDLERS (Section 30)
# ==============================================================================

def bad_request_view(request, exception=None):
    return render(request, 'errors/400.html', status=400)


def permission_denied_view(request, exception=None):
    return render(request, 'errors/403.html', {'message': str(exception) if exception else None}, status=403)


def not_found_view(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def server_error_view(request):
    return render(request, 'errors/500.html', status=500)


# ==============================================================================
# ADMIN CONFIGURATION VIEWS (Section 20 & 27)
# ==============================================================================

@super_admin_required
def admin_panel_view(request):
    """Main administrative control hub."""
    return render(request, 'admin_panel/dashboard.html')


@super_admin_required
def settings_update_view(request):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    settings = SiteSettings.load(tenant=tenant)
    if request.method == 'POST':
        form = SiteSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            old_vals = {f: form.initial.get(f) for f in form.changed_data}
            form.save()
            new_vals = {f: form.cleaned_data.get(f) for f in form.changed_data}
            log_audit_event(
                actor=request.user,
                action='SETTINGS_UPDATE',
                object_type='SiteSettings',
                object_identifier=str(settings.pk),
                old_values=old_vals,
                new_values=new_vals,
                reason="Updated company settings via Admin Panel",
                request=request,
                tenant=tenant
            )
            messages.success(request, "Company and system settings updated successfully.")
            return redirect('admin_panel_settings')
    else:
        form = SiteSettingsForm(instance=settings)

    return render(request, 'admin_panel/settings.html', {'form': form, 'settings': settings})


@super_admin_required
def config_list_view(request):
    """List form field configurations and choice configurations."""
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    field_configs = FieldConfig.objects.filter(tenant=tenant).order_by('order', 'field_key')
    if not field_configs.exists() and tenant:
        field_configs = FieldConfig.objects.filter(tenant=None).order_by('order', 'field_key')

    choice_configs = ChoiceConfig.objects.filter(tenant=tenant).order_by('category', 'order', 'label')
    if not choice_configs.exists() and tenant:
        choice_configs = ChoiceConfig.objects.filter(tenant=None).order_by('category', 'order', 'label')

    return render(request, 'admin_panel/config_list.html', {
        'field_configs': field_configs,
        'choice_configs': choice_configs,
    })


@super_admin_required
def field_config_edit_view(request, pk):
    cfg = get_object_or_404(FieldConfig, pk=pk)
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if request.user.tenant and cfg.tenant_id != request.user.tenant_id:
        if cfg.tenant_id is None:
            cfg, _ = FieldConfig.objects.get_or_create(
                tenant=request.user.tenant,
                field_key=cfg.field_key,
                defaults={
                    'label': cfg.label,
                    'placeholder': cfg.placeholder,
                    'help_text': cfg.help_text,
                    'is_required': cfg.is_required,
                    'is_visible': cfg.is_visible,
                    'order': cfg.order,
                    'is_active': cfg.is_active,
                }
            )
        else:
            raise PermissionDenied("Access denied to this configuration.")
    elif tenant and not request.user.is_superuser and cfg.tenant_id != tenant.id:
        if cfg.tenant_id is None:
            cfg, _ = FieldConfig.objects.get_or_create(
                tenant=tenant,
                field_key=cfg.field_key,
                defaults={
                    'label': cfg.label,
                    'placeholder': cfg.placeholder,
                    'help_text': cfg.help_text,
                    'is_required': cfg.is_required,
                    'is_visible': cfg.is_visible,
                    'order': cfg.order,
                    'is_active': cfg.is_active,
                }
            )
        else:
            raise PermissionDenied("Access denied to this configuration.")
    if request.method == 'POST':
        form = FieldConfigForm(request.POST, instance=cfg)
        if form.is_valid():
            form.save()
            log_audit_event(
                actor=request.user,
                action='FIELD_CONFIG_UPDATE',
                object_type='FieldConfig',
                object_identifier=str(cfg.field_key),
                new_values={'label': cfg.label, 'is_required': cfg.is_required, 'is_visible': cfg.is_visible},
                reason="Updated field configuration",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"Configuration for field '{cfg.label}' updated.")
            return redirect('admin_panel_config')
    else:
        form = FieldConfigForm(instance=cfg)
    return render(request, 'admin_panel/field_config_form.html', {'form': form, 'config': cfg})


@super_admin_required
def choice_config_create_view(request):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if request.method == 'POST':
        form = ChoiceConfigForm(request.POST, tenant=tenant)
        if form.is_valid():
            choice = form.save(commit=False)
            choice.tenant = tenant
            choice.save()
            log_audit_event(
                actor=request.user,
                action='CHOICE_CONFIG_CREATE',
                object_type='ChoiceConfig',
                object_identifier=f"{choice.category}:{choice.key}",
                new_values={'category': choice.category, 'key': choice.key, 'label': choice.label},
                reason="Created dropdown choice",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"Choice '{choice.label}' created successfully.")
            return redirect('admin_panel_config')
    else:
        form = ChoiceConfigForm(tenant=tenant)
    return render(request, 'admin_panel/choice_config_form.html', {'form': form, 'title': 'Add New Dropdown Choice'})


@super_admin_required
def choice_config_edit_view(request, pk):
    choice = get_object_or_404(ChoiceConfig, pk=pk)
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if request.user.tenant and choice.tenant_id != request.user.tenant_id:
        if choice.tenant_id is None:
            choice, _ = ChoiceConfig.objects.get_or_create(
                tenant=request.user.tenant,
                category=choice.category,
                key=choice.key,
                defaults={
                    'label': choice.label,
                    'is_default': choice.is_default,
                    'is_active': choice.is_active,
                    'order': choice.order,
                }
            )
        else:
            raise PermissionDenied("Access denied to this configuration.")
    elif tenant and not request.user.is_superuser and choice.tenant_id != tenant.id:
        if choice.tenant_id is None:
            choice, _ = ChoiceConfig.objects.get_or_create(
                tenant=tenant,
                category=choice.category,
                key=choice.key,
                defaults={
                    'label': choice.label,
                    'is_default': choice.is_default,
                    'is_active': choice.is_active,
                    'order': choice.order,
                }
            )
        else:
            raise PermissionDenied("Access denied to this configuration.")
    if request.method == 'POST':
        form = ChoiceConfigForm(request.POST, instance=choice, tenant=tenant)
        if form.is_valid():
            form.save()
            log_audit_event(
                actor=request.user,
                action='CHOICE_CONFIG_UPDATE',
                object_type='ChoiceConfig',
                object_identifier=f"{choice.category}:{choice.key}",
                new_values={'label': choice.label, 'is_active': choice.is_active},
                reason="Updated dropdown choice",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"Choice '{choice.label}' updated.")
            return redirect('admin_panel_config')
    else:
        form = ChoiceConfigForm(instance=choice, tenant=tenant)
    return render(request, 'admin_panel/choice_config_form.html', {'form': form, 'choice': choice, 'title': 'Edit Dropdown Choice'})


@super_admin_required
def choice_config_toggle_view(request, pk):
    if request.method == 'POST':
        choice = get_object_or_404(ChoiceConfig, pk=pk)
        tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
        if request.user.tenant and choice.tenant_id != request.user.tenant_id:
            if choice.tenant_id is None:
                choice, _ = ChoiceConfig.objects.get_or_create(
                    tenant=request.user.tenant,
                    category=choice.category,
                    key=choice.key,
                    defaults={
                        'label': choice.label,
                        'is_default': choice.is_default,
                        'is_active': choice.is_active,
                        'order': choice.order,
                    }
                )
            else:
                raise PermissionDenied("Access denied to this configuration.")
        elif tenant and not request.user.is_superuser and choice.tenant_id != tenant.id:
            if choice.tenant_id is None:
                choice, _ = ChoiceConfig.objects.get_or_create(
                    tenant=tenant,
                    category=choice.category,
                    key=choice.key,
                    defaults={
                        'label': choice.label,
                        'is_default': choice.is_default,
                        'is_active': choice.is_active,
                        'order': choice.order,
                    }
                )
            else:
                raise PermissionDenied("Access denied to this configuration.")
        choice.is_active = not choice.is_active
        choice.save()
        log_audit_event(
            actor=request.user,
            action='CHOICE_CONFIG_TOGGLE',
            object_type='ChoiceConfig',
            object_identifier=f"{choice.category}:{choice.key}",
            new_values={'is_active': choice.is_active},
            reason="Toggled choice active status",
            request=request,
            tenant=tenant
        )
        status_text = "activated" if choice.is_active else "deactivated"
        messages.success(request, f"Choice '{choice.label}' {status_text}.")
    return redirect('admin_panel_config')
