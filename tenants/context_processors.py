from .models import Tenant


def tenant_context(request):
    """
    Context processor injecting tenant state into all templates:
    - active_tenant: Current resolved tenant
    - all_tenants: List of all active tenants (for Platform Admin switcher)
    - is_platform_admin: Boolean indicating whether current user is a SaaS Platform Super Admin
    """
    tenant = getattr(request, 'tenant', None)
    user = getattr(request, 'user', None)

    is_platform_admin = False
    all_tenants = []

    if user and user.is_authenticated and user.is_superuser:
        is_platform_admin = True
        all_tenants = Tenant.objects.all().order_by('name')

    context = {
        'ACTIVE_TENANT': tenant,
        'IS_PLATFORM_ADMIN': is_platform_admin,
        'ALL_TENANTS': all_tenants,
    }

    if tenant:
        context['COMPANY_NAME'] = tenant.name
        context['CURRENCY'] = tenant.currency
        context['HEAD_OFFICE'] = tenant.head_office
        context['SUPPORT_PHONE'] = tenant.support_phone
        context['SUPPORT_EMAIL'] = tenant.support_email

    return context
