from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import HttpResponseRedirect
from accounts.models import User, Role
from parcels.models import Parcel
from routes.models import Route
from audit.services import log_audit_event
from audit.models import AuditLog
from .models import Tenant, TenantPlan, TenantStatus
from .forms import InstallClientForm, TenantEditForm, TenantAdminPasswordResetForm
from .services import provision_tenant


def platform_admin_required(view_func):
    """
    Decorator strictly restricting access to SaaS Platform Owners / Global Super Admins.
    """
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not (request.user.is_superuser and request.user.tenant is None):
            raise PermissionDenied("Access restricted to SaaS Platform Super Administrators.")
        return view_func(request, *args, **kwargs)
    return _wrapped


@platform_admin_required
def saas_dashboard_view(request):
    """
    SaaS Central Control Hub / Master Dashboard.
    Monitor all clients, aggregates platform metrics, and allows 1-click client installation.
    """
    tenants_qs = Tenant.objects.all().order_by('-created_at')

    # Filtering & Search
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    plan_filter = request.GET.get('plan', '').strip()

    if q:
        tenants_qs = tenants_qs.filter(
            Q(name__icontains=q) |
            Q(slug__icontains=q) |
            Q(tracking_prefix__icontains=q) |
            Q(support_phone__icontains=q) |
            Q(head_office__icontains=q)
        )
    if status_filter:
        tenants_qs = tenants_qs.filter(status=status_filter)
    if plan_filter:
        tenants_qs = tenants_qs.filter(plan=plan_filter)

    # Platform-wide Aggregate KPIs
    all_tenants = Tenant.objects.all()
    total_clients = all_tenants.count()
    active_clients = all_tenants.filter(status=TenantStatus.ACTIVE).count()
    trial_clients = all_tenants.filter(status=TenantStatus.TRIAL).count()
    suspended_clients = all_tenants.filter(status=TenantStatus.SUSPENDED).count()

    total_parcels = Parcel.objects.count()
    total_revenue = Parcel.objects.aggregate(total=Sum('price'))['total'] or Decimal('0.00')
    total_staff = User.objects.filter(is_superuser=False).count()

    # Recent Audit Log of SaaS operations
    recent_audits = AuditLog.objects.filter(
        action__in=['TENANT_PROVISION', 'TENANT_UPDATE', 'TENANT_TOGGLE', 'SETTINGS_UPDATE']
    ).order_by('-timestamp')[:10]

    return render(request, 'saas/dashboard.html', {
        'tenants': tenants_qs,
        'total_clients': total_clients,
        'active_clients': active_clients,
        'trial_clients': trial_clients,
        'suspended_clients': suspended_clients,
        'total_parcels': total_parcels,
        'total_revenue': total_revenue,
        'total_staff': total_staff,
        'recent_audits': recent_audits,
        'q': q,
        'status_filter': status_filter,
        'plan_filter': plan_filter,
        'status_choices': TenantStatus.choices,
        'plan_choices': TenantPlan.choices,
    })


@platform_admin_required
def saas_install_client_view(request):
    """
    Dedicated Client Provisioning Wizard.
    Installs a completely isolated multi-tenant organization from one screen.
    """
    if request.method == 'POST':
        form = InstallClientForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            starter_routes_raw = data.get('starter_routes', '')
            starter_routes = [r.strip() for r in starter_routes_raw.split(',') if r.strip()] if starter_routes_raw else None

            try:
                result = provision_tenant(
                    name=data['name'],
                    slug=data['slug'],
                    tracking_prefix=data['tracking_prefix'],
                    head_office=data['head_office'],
                    currency=data['currency'],
                    support_phone=data['support_phone'],
                    support_email=data['support_email'],
                    admin_username=data['admin_username'],
                    admin_first_name=data['admin_first_name'],
                    admin_last_name=data['admin_last_name'],
                    admin_phone=data['admin_phone'],
                    admin_email=data['admin_email'],
                    admin_password=data['admin_password'],
                    plan=data['plan'],
                    primary_color=data.get('primary_color', '#0d47a1'),
                    accent_color=data.get('accent_color', '#ff8f00'),
                    starter_routes=starter_routes,
                    actor=request.user,
                    request=request
                )
                messages.success(request, f"Client '{result['tenant'].name}' installed and provisioned successfully!")
                return render(request, 'saas/install_success.html', {
                    'tenant': result['tenant'],
                    'admin_user': result['admin_user'],
                    'raw_password': result['raw_password'],
                })
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
            except Exception as e:
                messages.error(request, f"Provisioning failed: {e}")
    else:
        form = InstallClientForm()

    return render(request, 'saas/install_client.html', {'form': form})


@platform_admin_required
def saas_client_detail_view(request, slug):
    """Deep dive into a specific client organization."""
    tenant = get_object_or_404(Tenant, slug=slug)
    staff_users = tenant.users.select_related('assigned_route').all().order_by('role', 'username')
    routes = tenant.routes.all().order_by('name')
    recent_parcels = tenant.parcels.select_related('route').order_by('-created_at')[:10]

    return render(request, 'saas/client_detail.html', {
        'tenant': tenant,
        'staff_users': staff_users,
        'routes': routes,
        'recent_parcels': recent_parcels,
    })


@platform_admin_required
def saas_client_edit_view(request, slug):
    """Edit client organization details, subscription, or branding."""
    tenant = get_object_or_404(Tenant, slug=slug)
    if request.method == 'POST':
        form = TenantEditForm(request.POST, instance=tenant)
        if form.is_valid():
            old_vals = {f: form.initial.get(f) for f in form.changed_data}
            form.save()
            new_vals = {f: form.cleaned_data.get(f) for f in form.changed_data}

            log_audit_event(
                actor=request.user,
                action='TENANT_UPDATE',
                object_type='Tenant',
                object_identifier=tenant.slug,
                old_values=old_vals,
                new_values=new_vals,
                reason="Updated client organization settings via SaaS Dashboard",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"Client '{tenant.name}' settings updated successfully.")
            return redirect('saas_client_detail', slug=tenant.slug)
    else:
        form = TenantEditForm(instance=tenant)

    return render(request, 'saas/client_edit.html', {'form': form, 'tenant': tenant})


@platform_admin_required
def saas_client_toggle_status_view(request, slug):
    """Toggle client between ACTIVE and SUSPENDED."""
    tenant = get_object_or_404(Tenant, slug=slug)
    if request.method == 'POST':
        if tenant.status == TenantStatus.ACTIVE:
            tenant.status = TenantStatus.SUSPENDED
            tenant.is_active = False
        else:
            tenant.status = TenantStatus.ACTIVE
            tenant.is_active = True
        tenant.save()

        log_audit_event(
            actor=request.user,
            action='TENANT_TOGGLE',
            object_type='Tenant',
            object_identifier=tenant.slug,
            new_values={'status': tenant.status, 'is_active': tenant.is_active},
            reason=f"Toggled client status to {tenant.status}",
            request=request,
            tenant=tenant
        )
        messages.success(request, f"Client '{tenant.name}' is now {tenant.get_status_display()}.")
    return redirect('saas_dashboard')


@platform_admin_required
def saas_client_reset_password_view(request, slug):
    """Reset the client super admin's password from the master dashboard."""
    tenant = get_object_or_404(Tenant, slug=slug)
    admin_user = tenant.admin_user

    if not admin_user:
        messages.error(request, f"No administrator account found for client '{tenant.name}'.")
        return redirect('saas_client_detail', slug=tenant.slug)

    if request.method == 'POST':
        form = TenantAdminPasswordResetForm(request.POST)
        if form.is_valid():
            new_pwd = form.cleaned_data['new_password']
            admin_user.set_password(new_pwd)
            admin_user.save()

            log_audit_event(
                actor=request.user,
                action='PASSWORD_RESET',
                object_type='User',
                object_identifier=admin_user.username,
                reason=f"Platform Owner reset password for client admin '{admin_user.username}'",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"Password for '{admin_user.username}' ({tenant.name}) has been reset.")
            return redirect('saas_client_detail', slug=tenant.slug)
    else:
        form = TenantAdminPasswordResetForm()

    return render(request, 'saas/client_reset_password.html', {
        'form': form,
        'tenant': tenant,
        'admin_user': admin_user
    })


@platform_admin_required
def saas_switch_tenant_view(request, tenant_id=None):
    """
    Seamless Workspace Switcher for Platform Super Admins.
    Allows testing and managing any client portal from their point of view.
    """
    if tenant_id and tenant_id > 0:
        tenant = get_object_or_404(Tenant, id=tenant_id)
        request.session['active_tenant_id'] = tenant.id
        messages.info(request, f"Switched active workspace to client: {tenant.name}")
        return redirect('dashboard')
    else:
        request.session.pop('active_tenant_id', None)
        messages.info(request, "Exited client workspace back to Global SaaS Platform View.")
        return redirect('saas_dashboard')


@platform_admin_required
def saas_client_delete_view(request, slug):
    """
    Safely delete a client organization. Requires typing the exact company name to confirm.
    """
    tenant = get_object_or_404(Tenant, slug=slug)
    if request.method == 'POST':
        confirm_name = request.POST.get('confirm_name', '').strip()
        if confirm_name != tenant.name:
            messages.error(request, f"Deletion aborted. You must type '{tenant.name}' exactly to confirm.")
            return redirect('saas_client_detail', slug=tenant.slug)

        name = tenant.name
        slug_val = tenant.slug
        if request.session.get('active_tenant_id') == tenant.id:
            request.session.pop('active_tenant_id', None)

        log_audit_event(
            actor=request.user,
            action='TENANT_DELETE',
            object_type='Tenant',
            object_identifier=slug_val,
            reason=f"Platform Owner permanently deleted client organization '{name}'",
            request=request
        )
        tenant.delete()
        messages.success(request, f"Client organization '{name}' has been permanently deleted.")
        return redirect('saas_dashboard')
    return redirect('saas_client_detail', slug=tenant.slug)


@platform_admin_required
def saas_export_tenants_csv_view(request):
    """Export platform clients roster as CSV."""
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="saas_clients_{timezone.localdate().isoformat()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Slug', 'Tracking Prefix', 'Hub', 'Currency',
        'Plan', 'Status', 'Staff Count', 'Max Users',
        'Routes Count', 'Max Routes', 'Parcels Count', 'Revenue', 'Created At'
    ])

    for t in Tenant.objects.all().order_by('name'):
        writer.writerow([
            t.name,
            t.slug,
            t.tracking_prefix,
            t.head_office,
            t.currency,
            t.get_plan_display(),
            t.get_status_display(),
            t.total_users,
            t.max_users,
            t.total_routes,
            t.max_routes,
            t.total_parcels,
            t.total_revenue,
            t.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    return response
