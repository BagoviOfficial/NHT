from django.db.models import QuerySet
from accounts.models import Role
from .models import Parcel


def get_parcels_for_user(user, queryset: QuerySet = None, tenant=None) -> QuerySet:
    """
    Returns parcels visible to the user based on Tenant isolation, RBAC,
    and object-level route restrictions.
    Strictly prevents cross-client data leakage.
    """
    if queryset is None:
        queryset = Parcel.objects.select_related('route', 'created_by', 'tenant').prefetch_related('items')

    if not user.is_authenticated:
        return queryset.none()

    # Tenant scoping: if tenant explicit or user assigned to tenant
    target_tenant = tenant or getattr(user, 'tenant', None)
    if target_tenant:
        queryset = queryset.filter(tenant=target_tenant)

    if user.is_superuser or user.role in [Role.SUPER_ADMIN, Role.OPERATIONS_MANAGER, Role.READ_ONLY, Role.COUNTER_STAFF, Role.DISPATCH_STAFF]:
        return queryset

    if user.role == Role.DESTINATION_STAFF:
        if user.assigned_route:
            return queryset.filter(route=user.assigned_route)
        return queryset.none()

    return queryset.none()


def can_user_access_parcel(user, parcel: Parcel) -> bool:
    """
    Validates if user can view/access a specific parcel instance.
    Enforces strict multi-tenant barrier and prevents IDOR/BOLA attacks.
    """
    if not user.is_authenticated or not user.is_active:
        return False

    # Prevent cross-tenant access for non-platform superusers
    if getattr(user, 'tenant_id', None) and getattr(parcel, 'tenant_id', None):
        if user.tenant_id != parcel.tenant_id:
            return False

    if user.is_superuser or user.role in [Role.SUPER_ADMIN, Role.OPERATIONS_MANAGER, Role.READ_ONLY, Role.COUNTER_STAFF, Role.DISPATCH_STAFF]:
        return True

    if user.role == Role.DESTINATION_STAFF:
        return user.assigned_route_id is not None and parcel.route_id == user.assigned_route_id

    return False
