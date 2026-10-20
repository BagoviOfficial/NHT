from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from accounts.decorators import super_admin_required
from audit.services import log_audit_event
from .models import Route
from .forms import RouteForm


@super_admin_required
def route_list_view(request):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if tenant:
        routes = Route.objects.filter(tenant=tenant).order_by('name')
    else:
        routes = Route.objects.all().order_by('name')
    return render(request, 'routes/route_list.html', {'routes': routes})


@super_admin_required
def route_create_view(request):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if tenant and tenant.routes.count() >= tenant.max_routes:
        messages.error(
            request,
            f"Route quota reached ({tenant.max_routes} max for {tenant.get_plan_display()} plan). Please contact the platform owner to upgrade your subscription."
        )
        return redirect('route_list')

    if request.method == 'POST':
        form = RouteForm(request.POST, tenant=tenant)
        if form.is_valid():
            route = form.save(commit=False)
            route.tenant = tenant
            route.save()
            log_audit_event(
                action='ROUTE_CREATE',
                actor=request.user,
                object_type='Route',
                object_identifier=str(route.name),
                new_values={'name': route.name, 'origin': route.origin, 'is_active': route.is_active},
                reason="Created new transit route",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"Route '{route}' created successfully.")
            return redirect('route_list')
    else:
        initial = {}
        if tenant:
            initial['origin'] = tenant.head_office
        form = RouteForm(initial=initial, tenant=tenant)
    return render(request, 'routes/route_form.html', {'form': form, 'title': 'Add Transit Route'})


@super_admin_required
def route_update_view(request, pk):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    route = get_object_or_404(Route, pk=pk)
    if request.user.tenant and route.tenant_id != request.user.tenant_id:
        raise PermissionDenied("Access denied to this route.")
    elif tenant and not request.user.is_superuser and route.tenant_id != tenant.id:
        raise PermissionDenied("Access denied to this route.")

    if request.method == 'POST':
        form = RouteForm(request.POST, instance=route, tenant=tenant)
        if form.is_valid():
            old_vals = {f: form.initial.get(f) for f in form.changed_data}
            route = form.save()
            new_vals = {f: getattr(route, f) for f in form.changed_data}
            log_audit_event(
                action='ROUTE_UPDATE',
                actor=request.user,
                object_type='Route',
                object_identifier=str(route.name),
                old_values=old_vals,
                new_values=new_vals,
                reason="Updated transit route",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"Route '{route}' updated successfully.")
            return redirect('route_list')
    else:
        form = RouteForm(instance=route, tenant=tenant)
    return render(request, 'routes/route_form.html', {'form': form, 'route': route, 'title': f'Edit Route {route.name}'})


@super_admin_required
def route_toggle_view(request, pk):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if request.method == 'POST':
        route = get_object_or_404(Route, pk=pk)
        if request.user.tenant and route.tenant_id != request.user.tenant_id:
            raise PermissionDenied("Access denied to this route.")
        elif tenant and not request.user.is_superuser and route.tenant_id != tenant.id:
            raise PermissionDenied("Access denied to this route.")
        route.is_active = not route.is_active
        route.save()
        log_audit_event(
            action='ROUTE_TOGGLE',
            actor=request.user,
            object_type='Route',
            object_identifier=str(route.name),
            new_values={'is_active': route.is_active},
            reason="Toggled route active state",
            request=request,
            tenant=tenant
        )
        status_text = "activated" if route.is_active else "deactivated"
        messages.success(request, f"Route '{route.name}' {status_text}.")
    return redirect('route_list')


@super_admin_required
def route_delete_view(request, pk):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    route = get_object_or_404(Route, pk=pk)
    if request.user.tenant and route.tenant_id != request.user.tenant_id:
        raise PermissionDenied("Access denied to this route.")
    elif tenant and not request.user.is_superuser and route.tenant_id != tenant.id:
        raise PermissionDenied("Access denied to this route.")

    if request.method == 'POST':
        if not route.can_be_deleted():
            messages.error(request, f"Cannot delete '{route.name}' because shipments or staff reference it. Deactivate the route instead.")
            return redirect('route_list')
        name = route.name
        route.delete()
        log_audit_event(
            action='ROUTE_DELETE',
            actor=request.user,
            object_type='Route',
            object_identifier=name,
            reason="Deleted unused route",
            request=request,
            tenant=tenant
        )
        messages.success(request, f"Route '{name}' deleted.")
    return redirect('route_list')
