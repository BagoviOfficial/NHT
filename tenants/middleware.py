from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import render
from .models import Tenant, TenantStatus


class TenantMiddleware(MiddlewareMixin):
    """
    Multi-Tenant Resolution Middleware.
    Resolves the active tenant for each incoming HTTP request based on:
    1. Active session override (for Platform SuperAdmins switching clients)
    2. Authenticated user's associated Tenant
    3. Host header subdomain or custom domain
    4. Fallback to primary active tenant
    """

    def process_request(self, request):
        request.tenant = None
        host = request.get_host().split(':')[0].lower()

        # 1. Platform SuperAdmin session switch
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser:
            session_tenant_id = request.session.get('active_tenant_id')
            if session_tenant_id:
                try:
                    request.tenant = Tenant.objects.filter(id=session_tenant_id).first()
                except (ValueError, TypeError):
                    pass

        # 2. Authenticated user's assigned tenant
        if not request.tenant and hasattr(request, 'user') and request.user.is_authenticated:
            if getattr(request.user, 'tenant', None):
                request.tenant = request.user.tenant

        # 3. Domain / Subdomain resolution
        if not request.tenant:
            # Check custom domain
            tenant = Tenant.objects.filter(custom_domain__iexact=host).first()
            if tenant:
                request.tenant = tenant
            else:
                # Check subdomain (e.g. "tawakal.courier.com" -> "tawakal")
                parts = host.split('.')
                if len(parts) >= 3 and parts[0] not in ('www', 'app', 'saas', 'api', 'admin'):
                    subdomain = parts[0]
                    request.tenant = Tenant.objects.filter(subdomain__iexact=subdomain).first()

        # 4. Fallback to primary active tenant if not yet set
        if not request.tenant:
            # Don't force fallback for SaaS master portal paths
            if not request.path.startswith('/saas/'):
                request.tenant = Tenant.objects.filter(is_active=True).first()

        # 5. Check if tenant is suspended (block non-superusers)
        if request.tenant and (request.tenant.status == TenantStatus.SUSPENDED or not request.tenant.is_active):
            # If user is not superuser and accessing tenant routes
            if not (hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser):
                if not request.path.startswith('/static/') and not request.path.startswith('/accounts/logout/'):
                    return render(request, 'errors/tenant_suspended.html', {'tenant': request.tenant}, status=403)
