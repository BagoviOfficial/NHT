from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db.models import Count, Sum, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from accounts.models import Role
from accounts.decorators import role_required, super_admin_required
from core.models import SiteSettings
from routes.models import Route
from audit.services import log_audit_event, get_client_ip
from .models import Parcel, ShipmentItem, ParcelStatus, PaymentStatus, PaymentMethod
from .forms import (
    ParcelForm, ShipmentItemFormSet, DispatchForm, ArrivalForm,
    CollectionForm, CancelForm, AdminOverrideForm
)
from .services import (
    create_parcel, update_parcel, transition_parcel_status,
    collect_parcel, cancel_parcel
)
from .selectors import get_parcels_for_user, can_user_access_parcel
from .utils import generate_tracking_qr_svg


# ==============================================================================
# PUBLIC VIEWS (Section 13)
# ==============================================================================

def home_view(request):
    """Public portal landing page."""
    tenant = getattr(request, 'tenant', None)
    settings = SiteSettings.load(tenant=tenant)
    routes = Route.objects.filter(tenant=tenant, is_active=True).order_by('name') if tenant else Route.objects.filter(is_active=True).order_by('name')
    return render(request, 'parcels/home.html', {
        'settings': settings,
        'routes': routes,
    })


def public_track_view(request, tracking_number=None):
    """
    Public parcel tracking endpoint.
    - Rate-limited to prevent brute-force enumeration.
    - Case-insensitive exact match only.
    - Exposes ONLY safe public tracking information (status, route, public timeline).
    - NEVER leaks financial data, sender/receiver personal IDs or phone numbers.
    """
    initial_tenant = getattr(request, 'tenant', None)
    settings = SiteSettings.load()
    client_ip = get_client_ip(request) or '127.0.0.1'

    # Rate limiting via cache
    cache_key = f"rate_limit_track_{client_ip}"
    request_count = cache.get(cache_key, 0)
    limit = settings.tracking_rate_limit_per_minute

    if request_count >= limit:
        return render(request, 'errors/429.html', {
            'message': 'Rate limit exceeded. Please wait a minute before making more tracking requests.'
        }, status=429)

    cache.set(cache_key, request_count + 1, timeout=60)

    track_code = tracking_number or request.GET.get('tracking_number', '').strip()
    parcel = None
    not_found = False

    if track_code:
        # Case-insensitive exact match
        try:
            parcel = Parcel.objects.select_related('route', 'tenant').prefetch_related('status_history').get(
                tracking_number__iexact=track_code
            )
            if parcel.tenant:
                settings = SiteSettings.load(tenant=parcel.tenant)
        except Parcel.DoesNotExist:
            not_found = True

    tenant = parcel.tenant if parcel else initial_tenant

    return render(request, 'parcels/public_track.html', {
        'parcel': parcel,
        'track_code': track_code,
        'not_found': not_found,
        'settings': settings,
        'SITE_SETTINGS': settings,
        'COMPANY_NAME': tenant.name if tenant else settings.company_name,
        'SUPPORT_PHONE': tenant.support_phone if tenant else settings.support_phone,
        'HEAD_OFFICE': tenant.head_office if tenant else settings.head_office,
        'CURRENCY': tenant.currency if tenant else settings.currency,
        'ACTIVE_TENANT': tenant,
    })


# ==============================================================================
# STAFF DASHBOARD & LIST VIEWS
# ==============================================================================

@login_required
def dashboard_view(request):
    """Staff operational dashboard with role-aware metrics."""
    user = request.user
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    base_qs = get_parcels_for_user(user, tenant=tenant)

    today = timezone.localdate()
    today_count = base_qs.filter(created_at__date=today).count()
    in_transit_count = base_qs.filter(status=ParcelStatus.IN_TRANSIT).count()
    awaiting_count = base_qs.filter(status=ParcelStatus.AWAITING_COLLECTION).count()
    collected_today_count = base_qs.filter(status=ParcelStatus.COLLECTED, collected_at__date=today).count()

    recent_parcels = base_qs.order_by('-created_at')[:10]

    financial_metrics = {}
    if user.can_view_financials:
        today_financials = base_qs.filter(created_at__date=today).aggregate(
            gross_total=Sum('price'),
            paid_total=Sum('price', filter=Q(payment_status=PaymentStatus.PAID)),
            cod_total=Sum('price', filter=Q(payment_status=PaymentStatus.COD)),
            unpaid_total=Sum('price', filter=Q(payment_status=PaymentStatus.UNPAID)),
        )
        financial_metrics = {
            'gross_total': today_financials['gross_total'] or Decimal('0.00'),
            'paid_total': today_financials['paid_total'] or Decimal('0.00'),
            'cod_total': today_financials['cod_total'] or Decimal('0.00'),
            'unpaid_total': today_financials['unpaid_total'] or Decimal('0.00'),
        }

    return render(request, 'parcels/dashboard.html', {
        'today_count': today_count,
        'in_transit_count': in_transit_count,
        'awaiting_count': awaiting_count,
        'collected_today_count': collected_today_count,
        'recent_parcels': recent_parcels,
        'financial_metrics': financial_metrics,
    })


@login_required
def parcel_list_view(request):
    """Search and filter parcels with pagination and object-level permissions."""
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    qs = get_parcels_for_user(request.user, tenant=tenant)

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    route_filter = request.GET.get('route', '').strip()
    payment_status_filter = request.GET.get('payment_status', '').strip()

    if q:
        qs = qs.filter(
            Q(tracking_number__icontains=q) |
            Q(sender_name__icontains=q) |
            Q(sender_phone__icontains=q) |
            Q(receiver_name__icontains=q) |
            Q(receiver_phone__icontains=q) |
            Q(truck_plate_number__icontains=q)
        )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if route_filter and route_filter.isdigit():
        qs = qs.filter(route_id=int(route_filter))
    if payment_status_filter and request.user.can_view_financials:
        qs = qs.filter(payment_status=payment_status_filter)

    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if tenant:
        routes = Route.objects.filter(tenant=tenant, is_active=True).order_by('name')
    else:
        routes = Route.objects.filter(is_active=True).order_by('name')
    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'parcels/parcel_list.html', {
        'page_obj': page_obj,
        'routes': routes,
        'statuses': ParcelStatus.choices,
        'payment_statuses': PaymentStatus.choices,
        'q': q,
        'status_filter': status_filter,
        'route_filter': route_filter,
        'payment_status_filter': payment_status_filter,
    })


@login_required
def parcel_detail_view(request, tracking_number):
    """Detailed shipment view including items and transition history."""
    parcel = get_object_or_404(
        Parcel.objects.select_related('route', 'created_by').prefetch_related('items', 'status_history__user'),
        tracking_number=tracking_number
    )

    if not can_user_access_parcel(request.user, parcel):
        raise PermissionDenied("You do not have permission to view parcels assigned to this destination route.")

    return render(request, 'parcels/parcel_detail.html', {
        'parcel': parcel,
        'items': parcel.items.all(),
        'history': parcel.status_history.all(),
    })


# ==============================================================================
# BOOKING & EDITING VIEWS
# ==============================================================================

@login_required
def parcel_create_view(request):
    """Register a new parcel consignment with line items."""
    if not request.user.can_create_parcel:
        raise PermissionDenied("You do not have permission to register parcels.")

    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if request.method == 'POST':
        form = ParcelForm(request.POST, tenant=tenant)
        formset = ShipmentItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            items_data = []
            for item_form in formset.cleaned_data:
                if item_form and not item_form.get('DELETE', False):
                    items_data.append({
                        'description': item_form['description'],
                        'wrap_type': item_form['wrap_type'],
                        'quantity': item_form['quantity'],
                        'unit_price': item_form['unit_price'],
                    })

            if not items_data:
                messages.error(request, "A parcel must contain at least one shipment item.")
            else:
                try:
                    parcel = create_parcel(
                        route=form.cleaned_data['route'],
                        sender_name=form.cleaned_data['sender_name'],
                        sender_phone=form.cleaned_data['sender_phone'],
                        receiver_name=form.cleaned_data['receiver_name'],
                        receiver_phone=form.cleaned_data['receiver_phone'],
                        receiver_id_number=form.cleaned_data['receiver_id_number'],
                        payment_status=form.cleaned_data['payment_status'],
                        payment_method=form.cleaned_data['payment_method'],
                        items_data=items_data,
                        created_by=request.user,
                        request=request,
                        tenant=tenant
                    )
                    messages.success(request, f"Parcel {parcel.tracking_number} registered successfully!")
                    return redirect('parcel_receipt', tracking_number=parcel.tracking_number)
                except ValidationError as e:
                    messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = ParcelForm(tenant=tenant)
        formset = ShipmentItemFormSet()

    return render(request, 'parcels/parcel_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Register New Consignment',
    })


@login_required
def parcel_update_view(request, tracking_number):
    """Edit parcel data prior to dispatch."""
    if not request.user.can_edit_parcel:
        raise PermissionDenied("You do not have permission to edit parcels.")

    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)

    if not can_user_access_parcel(request.user, parcel):
        raise PermissionDenied("Access denied.")

    if not parcel.is_editable:
        messages.error(request, "This parcel has already been dispatched and cannot be edited by normal staff.")
        return redirect('parcel_detail', tracking_number=parcel.tracking_number)

    if request.method == 'POST':
        form = ParcelForm(request.POST, instance=parcel, tenant=parcel.tenant)
        formset = ShipmentItemFormSet(request.POST, instance=parcel)

        if form.is_valid() and formset.is_valid():
            items_data = []
            for item_form in formset.cleaned_data:
                if item_form and not item_form.get('DELETE', False):
                    items_data.append({
                        'description': item_form['description'],
                        'wrap_type': item_form['wrap_type'],
                        'quantity': item_form['quantity'],
                        'unit_price': item_form['unit_price'],
                    })

            if not items_data:
                messages.error(request, "A parcel must contain at least one shipment item.")
            else:
                try:
                    update_parcel(
                        parcel_id=parcel.pk,
                        route=form.cleaned_data['route'],
                        sender_name=form.cleaned_data['sender_name'],
                        sender_phone=form.cleaned_data['sender_phone'],
                        receiver_name=form.cleaned_data['receiver_name'],
                        receiver_phone=form.cleaned_data['receiver_phone'],
                        receiver_id_number=form.cleaned_data['receiver_id_number'],
                        payment_status=form.cleaned_data['payment_status'],
                        payment_method=form.cleaned_data['payment_method'],
                        items_data=items_data,
                        user=request.user,
                        request=request
                    )
                    messages.success(request, f"Parcel {parcel.tracking_number} updated successfully.")
                    return redirect('parcel_detail', tracking_number=parcel.tracking_number)
                except ValidationError as e:
                    messages.error(request, str(e))
    else:
        form = ParcelForm(instance=parcel, tenant=parcel.tenant)
        formset = ShipmentItemFormSet(instance=parcel)

    return render(request, 'parcels/parcel_form.html', {
        'form': form,
        'formset': formset,
        'parcel': parcel,
        'title': f'Edit Parcel {parcel.tracking_number}',
    })


# ==============================================================================
# OPERATIONAL ACTIONS (DISPATCH, ARRIVAL, COLLECTION, CANCELLATION)
# ==============================================================================

@login_required
def parcel_dispatch_view(request, tracking_number):
    """Dispatch parcel (RECEIVED_AT_HQ -> IN_TRANSIT). Requires truck & driver."""
    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)

    if not can_user_access_parcel(request.user, parcel):
        raise PermissionDenied("Access denied.")

    if not request.user.can_dispatch_parcel:
        raise PermissionDenied("You do not have dispatch permissions.")

    if parcel.status != ParcelStatus.RECEIVED_AT_HQ:
        messages.error(request, f"Parcel cannot be dispatched from current status: {parcel.get_status_display()}")
        return redirect('parcel_detail', tracking_number=parcel.tracking_number)

    if request.method == 'POST':
        form = DispatchForm(request.POST)
        if form.is_valid():
            try:
                transition_parcel_status(
                    parcel_id=parcel.pk,
                    new_status=ParcelStatus.IN_TRANSIT,
                    user=request.user,
                    note=form.cleaned_data['note'],
                    truck_plate_number=form.cleaned_data['truck_plate_number'],
                    driver_name=form.cleaned_data['driver_name'],
                    request=request
                )
                messages.success(request, f"Parcel {parcel.tracking_number} dispatched successfully!")
                return redirect('parcel_detail', tracking_number=parcel.tracking_number)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = DispatchForm(initial={
            'truck_plate_number': parcel.truck_plate_number,
            'driver_name': parcel.driver_name,
        })

    return render(request, 'parcels/action_dispatch.html', {'parcel': parcel, 'form': form})


@login_required
def parcel_mark_arrived_view(request, tracking_number):
    """Record arrival at destination (IN_TRANSIT -> ARRIVED_AT_DESTINATION)."""
    if not request.user.can_mark_arrival:
        raise PermissionDenied("You do not have permission to mark parcel arrival.")

    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)

    if not can_user_access_parcel(request.user, parcel):
        raise PermissionDenied("You do not have permission to mark arrival for this destination.")

    if request.user.role == Role.DESTINATION_STAFF and parcel.route_id != request.user.assigned_route_id:
        raise PermissionDenied("You can only mark arrival for parcels destined to your assigned route.")

    if parcel.status != ParcelStatus.IN_TRANSIT:
        messages.error(request, f"Cannot record arrival: Parcel is currently '{parcel.get_status_display()}'.")
        return redirect('parcel_detail', tracking_number=parcel.tracking_number)

    if request.method == 'POST':
        form = ArrivalForm(request.POST)
        if form.is_valid():
            try:
                transition_parcel_status(
                    parcel_id=parcel.pk,
                    new_status=ParcelStatus.ARRIVED_AT_DESTINATION,
                    user=request.user,
                    note=form.cleaned_data['note'] or "Arrived at destination terminal",
                    request=request
                )
                messages.success(request, f"Parcel {parcel.tracking_number} marked as Arrived at Destination.")
                return redirect('parcel_detail', tracking_number=parcel.tracking_number)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = ArrivalForm()

    return render(request, 'parcels/action_arrived.html', {'parcel': parcel, 'form': form})


@login_required
def parcel_mark_awaiting_view(request, tracking_number):
    """Move parcel to AWAITING_COLLECTION (ARRIVED_AT_DESTINATION -> AWAITING_COLLECTION)."""
    if not request.user.can_mark_awaiting:
        raise PermissionDenied("You do not have permission to stage parcels for collection.")

    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)

    if not can_user_access_parcel(request.user, parcel):
        raise PermissionDenied("Access denied.")

    if request.user.role == Role.DESTINATION_STAFF and parcel.route_id != request.user.assigned_route_id:
        raise PermissionDenied("You can only stage parcels destined to your assigned route.")

    if parcel.status != ParcelStatus.ARRIVED_AT_DESTINATION:
        messages.error(request, f"Invalid state transition from '{parcel.get_status_display()}'.")
        return redirect('parcel_detail', tracking_number=parcel.tracking_number)

    if request.method == 'POST':
        try:
            transition_parcel_status(
                parcel_id=parcel.pk,
                new_status=ParcelStatus.AWAITING_COLLECTION,
                user=request.user,
                note="Sorted and staged for client collection",
                request=request
            )
            messages.success(request, f"Parcel {parcel.tracking_number} is now Awaiting Collection.")
        except ValidationError as e:
            messages.error(request, str(e))
    return redirect('parcel_detail', tracking_number=parcel.tracking_number)


@login_required
def parcel_collect_view(request, tracking_number):
    """Complete collection and record collector info (AWAITING_COLLECTION -> COLLECTED)."""
    if not request.user.can_manage_collection:
        raise PermissionDenied("You do not have permission to collect parcels.")

    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)

    if not can_user_access_parcel(request.user, parcel):
        raise PermissionDenied("Access denied.")

    if request.user.role == Role.DESTINATION_STAFF and parcel.route_id != request.user.assigned_route_id:
        raise PermissionDenied("You can only collect parcels destined to your assigned route.")

    if parcel.status != ParcelStatus.AWAITING_COLLECTION:
        messages.error(request, f"Parcels must be marked Awaiting Collection before releasing. Current status: '{parcel.get_status_display()}'.")
        return redirect('parcel_detail', tracking_number=parcel.tracking_number)

    if request.method == 'POST':
        form = CollectionForm(request.POST)
        if form.is_valid():
            try:
                collect_parcel(
                    parcel_id=parcel.pk,
                    collected_by_name=form.cleaned_data['collected_by_name'],
                    user=request.user,
                    note=form.cleaned_data['note'],
                    request=request
                )
                messages.success(request, f"Parcel {parcel.tracking_number} formally marked as COLLECTED.")
                return redirect('parcel_detail', tracking_number=parcel.tracking_number)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = CollectionForm(initial={'collected_by_name': parcel.receiver_name})

    return render(request, 'parcels/action_collect.html', {'parcel': parcel, 'form': form})


@login_required
def parcel_cancel_view(request, tracking_number):
    """Cancel shipment with mandatory reason."""
    if not request.user.can_cancel_parcel:
        raise PermissionDenied("You do not have cancellation permissions.")

    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)

    if not can_user_access_parcel(request.user, parcel):
        raise PermissionDenied("Access denied.")

    if parcel.is_terminal:
        messages.error(request, f"Cannot cancel parcel already in '{parcel.get_status_display()}' state.")
        return redirect('parcel_detail', tracking_number=parcel.tracking_number)

    if request.method == 'POST':
        form = CancelForm(request.POST)
        if form.is_valid():
            try:
                cancel_parcel(
                    parcel_id=parcel.pk,
                    reason=form.cleaned_data['reason'],
                    user=request.user,
                    request=request
                )
                messages.success(request, f"Parcel {parcel.tracking_number} has been CANCELLED.")
                return redirect('parcel_detail', tracking_number=parcel.tracking_number)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = CancelForm()

    return render(request, 'parcels/action_cancel.html', {'parcel': parcel, 'form': form})


@super_admin_required
def parcel_admin_override_view(request, tracking_number):
    """Super Admin override for post-dispatch modifications (Section 11)."""
    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)

    if not can_user_access_parcel(request.user, parcel):
        raise PermissionDenied("Access denied.")

    settings = SiteSettings.load(tenant=parcel.tenant)
    if not settings.allow_superuser_edit_after_dispatch:
        messages.error(request, "Administrative post-dispatch editing is currently disabled in Site Settings.")
        return redirect('parcel_detail', tracking_number=tracking_number)

    if request.method == 'POST':
        form = AdminOverrideForm(request.POST, instance=parcel)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            old_vals = {f: form.initial.get(f) for f in form.changed_data if f != 'reason'}
            form.save()
            new_vals = {f: form.cleaned_data.get(f) for f in form.changed_data if f != 'reason'}

            log_audit_event(
                action='ADMIN_OVERRIDE',
                actor=request.user,
                object_type='Parcel',
                object_identifier=parcel.tracking_number,
                old_values=old_vals,
                new_values=new_vals,
                reason=reason,
                request=request
            )
            messages.success(request, f"Administrative override executed for parcel {parcel.tracking_number}.")
            return redirect('parcel_detail', tracking_number=parcel.tracking_number)
    else:
        form = AdminOverrideForm(instance=parcel)

    return render(request, 'parcels/action_override.html', {'parcel': parcel, 'form': form})


# ==============================================================================
# RECEIPT VIEW (Section 23)
# ==============================================================================

@login_required
def parcel_receipt_view(request, tracking_number):
    """
    Dedicated 80mm thermal receipt view.
    Generates server-side QR code linking exclusively to the public tracking URL.
    Scoped strictly to the parcel's owning tenant for accurate branding.
    """
    parcel = get_object_or_404(
        Parcel.objects.select_related('route', 'created_by', 'tenant').prefetch_related('items'),
        tracking_number=tracking_number
    )

    if not can_user_access_parcel(request.user, parcel):
        raise PermissionDenied("Access denied.")

    tenant = parcel.tenant or getattr(request, 'tenant', None)
    settings = SiteSettings.load(tenant=tenant)
    tracking_url = request.build_absolute_uri(f"/track/{parcel.tracking_number}/")
    qr_svg = generate_tracking_qr_svg(tracking_url)

    company_name = (tenant.name if tenant else None) or settings.company_name
    currency = (tenant.currency if tenant else None) or settings.currency
    head_office = (tenant.head_office if tenant else None) or settings.head_office
    support_phone = (tenant.support_phone if tenant else None) or settings.support_phone
    receipt_header = (tenant.receipt_header if tenant and tenant.receipt_header else None) or settings.receipt_header
    receipt_footer = (tenant.receipt_footer if tenant and tenant.receipt_footer else None) or settings.receipt_footer

    return render(request, 'parcels/receipt_80mm.html', {
        'parcel': parcel,
        'items': parcel.items.all(),
        'settings': settings,
        'SITE_SETTINGS': settings,
        'COMPANY_NAME': company_name,
        'CURRENCY': currency,
        'HEAD_OFFICE': head_office,
        'SUPPORT_PHONE': support_phone,
        'RECEIPT_HEADER': receipt_header,
        'RECEIPT_FOOTER': receipt_footer,
        'tenant': tenant,
        'tracking_url': tracking_url,
        'qr_svg': qr_svg,
    })
