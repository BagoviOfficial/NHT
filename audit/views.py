from django.shortcuts import render
from django.core.paginator import Paginator
from accounts.decorators import super_admin_required
from .models import AuditLog


@super_admin_required
def audit_log_list_view(request):
    """
    Search and filter audit logs. Accessible exclusively to Super Admin.
    Tenant Super Admins only see their tenant's logs.
    Platform Super Admins see all logs across all tenants.
    """
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    qs = AuditLog.objects.select_related('actor', 'tenant').all()

    # Scope to tenant unless global platform superadmin
    if not (request.user.is_superuser and request.user.tenant is None and not request.session.get('active_tenant_id')):
        if tenant:
            qs = qs.filter(tenant=tenant)

    action_filter = request.GET.get('action')
    actor_filter = request.GET.get('actor')
    search_query = request.GET.get('q')

    if action_filter:
        qs = qs.filter(action=action_filter)
    if actor_filter:
        qs = qs.filter(actor__username__icontains=actor_filter)
    if search_query:
        qs = qs.filter(object_identifier__icontains=search_query)

    distinct_actions = qs.values_list('action', flat=True).distinct()

    paginator = Paginator(qs, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'admin_panel/audit_list.html', {
        'page_obj': page_obj,
        'distinct_actions': distinct_actions,
        'action_filter': action_filter,
        'actor_filter': actor_filter,
        'search_query': search_query,
    })
