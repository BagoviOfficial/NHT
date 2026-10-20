from .models import Parcel, ParcelStatus


def global_context(request):
    """Provides application-wide contextual variables for templates with tenant scoping."""
    context = {}
    if request.user.is_authenticated and request.user.is_staff:
        tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
        qs = Parcel.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        context['in_transit_count'] = qs.filter(status=ParcelStatus.IN_TRANSIT).count()
        context['awaiting_collection_count'] = qs.filter(status=ParcelStatus.AWAITING_COLLECTION).count()
    return context


