from .models import Parcel, PickupRequest, CustomerInquiry

def global_context(request):
    """Provides application-wide contextual variables for templates."""
    context = {
        'APP_NAME': 'SwiftParcel Express',
        'APP_TAGLINE': 'Fast, Reliable, Global Parcel & Logistics Management',
        'SUPPORT_PHONE': '+1 (800) 555-PARCEL',
        'SUPPORT_EMAIL': 'support@swiftparcel.com',
    }
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            context['user_profile'] = profile
        except Exception:
            context['user_profile'] = None

        if request.user.is_staff or (hasattr(request.user, 'profile') and request.user.profile.is_staff_member):
            context['pending_pickups_count'] = PickupRequest.objects.filter(status='PENDING').count()
            context['open_tickets_count'] = CustomerInquiry.objects.filter(status='OPEN').count()
            context['active_parcels_count'] = Parcel.objects.exclude(status__in=['DELIVERED', 'CANCELLED', 'RETURNED']).count()
    return context
