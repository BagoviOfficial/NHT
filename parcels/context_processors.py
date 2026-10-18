from .models import Parcel, ParcelStatus


def global_context(request):
    """Provides application-wide contextual variables for templates."""
    context = {}
    if request.user.is_authenticated and request.user.is_staff:
        context['in_transit_count'] = Parcel.objects.filter(status=ParcelStatus.IN_TRANSIT).count()
        context['awaiting_collection_count'] = Parcel.objects.filter(status=ParcelStatus.AWAITING_COLLECTION).count()
    return context

