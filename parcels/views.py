import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator

from .models import (
    Parcel, Branch, ShippingRate, ParcelTrackingLog,
    TransitManifest, PickupRequest, CustomerInquiry, UserProfile
)
from .forms import (
    UserLoginForm, CustomerRegisterForm, ParcelBookingForm,
    ParcelStatusUpdateForm, CourierAssignmentForm,
    CourierDeliveryActionForm, TransitManifestForm,
    PickupRequestForm, CustomerInquiryForm, InquiryReplyForm
)
from .utils import generate_qr_base64, generate_svg_barcode, calculate_shipping_cost


# ==============================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = UserLoginForm()

    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('home')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = CustomerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            UserProfile.objects.create(
                user=user,
                role='CUSTOMER',
                phone=form.cleaned_data['phone'],
                address=form.cleaned_data['address'],
                city=form.cleaned_data['city']
            )
            login(request, user)
            messages.success(request, "Account created successfully! Welcome to SwiftParcel.")
            return redirect('dashboard')
    else:
        form = CustomerRegisterForm()

    return render(request, 'auth/register.html', {'form': form})


# ==============================================================================
# PUBLIC PORTAL VIEWS
# ==============================================================================

def home_view(request):
    rates = ShippingRate.objects.all().order_by('base_price')
    branches = Branch.objects.filter(is_active=True)[:6]
    total_delivered = Parcel.objects.filter(status='DELIVERED').count() + 1250
    active_branches_count = Branch.objects.filter(is_active=True).count()
    return render(request, 'parcels/home.html', {
        'rates': rates,
        'branches': branches,
        'total_delivered': total_delivered,
        'active_branches_count': active_branches_count,
    })


def track_parcel_view(request, tracking_number=None):
    query = tracking_number or request.GET.get('q', '').strip()
    parcel = None
    qr_code_data = None
    barcode_svg = None

    if query:
        parcel = Parcel.objects.filter(tracking_number__iexact=query).first()
        if not parcel:
            messages.error(request, f"Consignment '{query}' not found. Please verify the tracking number.")
        else:
            qr_url = request.build_absolute_uri(f"/track/{parcel.tracking_number}/")
            qr_code_data = generate_qr_base64(qr_url)
            barcode_svg = generate_svg_barcode(parcel.tracking_number)

    return render(request, 'parcels/track.html', {
        'query': query,
        'parcel': parcel,
        'qr_code_data': qr_code_data,
        'barcode_svg': barcode_svg,
    })


def rate_calculator_view(request):
    rates = ShippingRate.objects.all()
    branches = Branch.objects.filter(is_active=True)
    return render(request, 'parcels/rate_calculator.html', {
        'rates': rates,
        'branches': branches,
    })


def branches_view(request):
    branches = Branch.objects.filter(is_active=True)
    return render(request, 'parcels/branches.html', {'branches': branches})


def contact_view(request):
    if request.method == 'POST':
        form = CustomerInquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save()
            messages.success(request, f"Thank you! Your inquiry #{inquiry.ticket_number} has been received. Our team will contact you shortly.")
            return redirect('contact')
    else:
        init_data = {}
        if request.GET.get('tracking'):
            init_data['tracking_number'] = request.GET.get('tracking')
        form = CustomerInquiryForm(initial=init_data)
    return render(request, 'parcels/contact.html', {'form': form})


def request_pickup_public_view(request):
    if request.method == 'POST':
        form = PickupRequestForm(request.POST)
        if form.is_valid():
            pickup = form.save(commit=False)
            # Auto-assign nearest branch if possible
            default_branch = Branch.objects.filter(is_active=True).first()
            pickup.branch = default_branch
            pickup.save()
            messages.success(request, f"Pickup request {pickup.request_number} submitted! A courier will be assigned.")
            return redirect('home')
    else:
        form = PickupRequestForm()
    return render(request, 'parcels/request_pickup.html', {'form': form})


# ==============================================================================
# DASHBOARD ROUTER
# ==============================================================================

@login_required
def dashboard_view(request):
    try:
        role = request.user.profile.role
    except Exception:
        role = 'ADMIN' if request.user.is_superuser else 'CUSTOMER'

    if role in ['ADMIN', 'BRANCH_STAFF'] or request.user.is_superuser or request.user.is_staff:
        return staff_dashboard_view(request)
    elif role == 'COURIER':
        return courier_dashboard_view(request)
    else:
        return customer_dashboard_view(request)


def staff_dashboard_view(request):
    # Overall KPIs
    total_parcels = Parcel.objects.count()
    in_transit_count = Parcel.objects.filter(status='IN_TRANSIT').count()
    out_for_delivery_count = Parcel.objects.filter(status='OUT_FOR_DELIVERY').count()
    delivered_count = Parcel.objects.filter(status='DELIVERED').count()
    pending_count = Parcel.objects.filter(status__in=['BOOKED', 'RECEIVED_AT_ORIGIN', 'IN_SORTING']).count()
    
    total_revenue = Parcel.objects.filter(payment_status='PAID').aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')

    # Status counts for chart
    status_counts = dict(
        Parcel.objects.values_list('status').annotate(c=Count('id'))
    )
    status_labels = [label for key, label in Parcel.STATUS_CHOICES]
    status_values = [status_counts.get(key, 0) for key, label in Parcel.STATUS_CHOICES]

    # Category breakdown
    category_counts = dict(
        Parcel.objects.values_list('category').annotate(c=Count('id'))
    )
    cat_labels = [label for key, label in Parcel.CATEGORY_CHOICES]
    cat_values = [category_counts.get(key, 0) for key, label in Parcel.CATEGORY_CHOICES]

    recent_parcels = Parcel.objects.select_related('origin_branch', 'destination_branch', 'assigned_courier')[:8]
    recent_manifests = TransitManifest.objects.select_related('origin_branch', 'destination_branch')[:5]
    pending_pickups = PickupRequest.objects.filter(status__in=['PENDING', 'ASSIGNED'])[:5]

    return render(request, 'parcels/dashboard_staff.html', {
        'total_parcels': total_parcels,
        'in_transit_count': in_transit_count,
        'out_for_delivery_count': out_for_delivery_count,
        'delivered_count': delivered_count,
        'pending_count': pending_count,
        'total_revenue': total_revenue,
        'status_labels': json.dumps(status_labels),
        'status_values': json.dumps(status_values),
        'cat_labels': json.dumps(cat_labels),
        'cat_values': json.dumps(cat_values),
        'recent_parcels': recent_parcels,
        'recent_manifests': recent_manifests,
        'pending_pickups': pending_pickups,
    })


def courier_dashboard_view(request):
    courier = request.user
    assigned_parcels = Parcel.objects.filter(
        assigned_courier=courier
    ).exclude(status__in=['DELIVERED', 'RETURNED', 'CANCELLED']).order_by('-updated_at')

    completed_today = Parcel.objects.filter(
        assigned_courier=courier,
        status='DELIVERED',
        delivered_at__date=timezone.now().date()
    ).count()

    assigned_pickups = PickupRequest.objects.filter(
        assigned_courier=courier,
        status='ASSIGNED'
    ).order_by('preferred_date')

    return render(request, 'courier/dashboard.html', {
        'assigned_parcels': assigned_parcels,
        'completed_today': completed_today,
        'assigned_pickups': assigned_pickups,
    })


def customer_dashboard_view(request):
    user = request.user
    my_sent = Parcel.objects.filter(Q(sender_user=user) | Q(sender_email=user.email)).order_by('-created_at')
    my_received = Parcel.objects.filter(Q(receiver_user=user) | Q(receiver_email=user.email)).order_by('-created_at')
    my_pickups = PickupRequest.objects.filter(customer_email=user.email).order_by('-created_at')
    my_tickets = CustomerInquiry.objects.filter(email=user.email).order_by('-created_at')

    return render(request, 'customer/dashboard.html', {
        'my_sent': my_sent,
        'my_received': my_received,
        'my_pickups': my_pickups,
        'my_tickets': my_tickets,
    })


# ==============================================================================
# PARCEL OPERATIONS (STAFF / ADMIN)
# ==============================================================================

@login_required
def parcel_list_view(request):
    queryset = Parcel.objects.select_related('origin_branch', 'destination_branch', 'assigned_courier')

    # Filters
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    branch_id = request.GET.get('branch', '').strip()
    service = request.GET.get('service', '').strip()
    payment = request.GET.get('payment', '').strip()

    if search:
        queryset = queryset.filter(
            Q(tracking_number__icontains=search) |
            Q(sender_name__icontains=search) |
            Q(receiver_name__icontains=search) |
            Q(receiver_phone__icontains=search) |
            Q(sender_phone__icontains=search)
        )
    if status:
        queryset = queryset.filter(status=status)
    if branch_id:
        queryset = queryset.filter(Q(origin_branch_id=branch_id) | Q(destination_branch_id=branch_id))
    if service:
        queryset = queryset.filter(service_type=service)
    if payment:
        queryset = queryset.filter(payment_status=payment)

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    branches = Branch.objects.filter(is_active=True)
    status_choices = Parcel.STATUS_CHOICES
    service_choices = ShippingRate.SERVICE_CHOICES
    payment_choices = Parcel.PAYMENT_STATUS_CHOICES

    return render(request, 'parcels/parcel_list.html', {
        'page_obj': page_obj,
        'branches': branches,
        'status_choices': status_choices,
        'service_choices': service_choices,
        'payment_choices': payment_choices,
        'search': search,
        'selected_status': status,
        'selected_branch': branch_id,
        'selected_service': service,
        'selected_payment': payment,
        'total_count': queryset.count(),
    })


@login_required
def parcel_create_view(request):
    if request.method == 'POST':
        form = ParcelBookingForm(request.POST)
        if form.is_valid():
            parcel = form.save(commit=False)
            parcel.created_by = request.user
            parcel.calculate_pricing()
            parcel.save()

            # Record initial tracking log
            ParcelTrackingLog.objects.create(
                parcel=parcel,
                status=parcel.status,
                branch=parcel.origin_branch,
                location_name=f"{parcel.origin_branch.name}, {parcel.origin_branch.city}",
                activity=f"Consignment booked and registered by {request.user.get_full_name() or request.user.username}",
                notes="Initial booking scan completed.",
                updated_by=request.user
            )

            messages.success(request, f"Parcel #{parcel.tracking_number} created successfully!")
            return redirect('parcel_detail', tracking_number=parcel.tracking_number)
    else:
        # Prepopulate origin branch from staff user profile if available
        init = {}
        if hasattr(request.user, 'profile') and request.user.profile.branch:
            init['origin_branch'] = request.user.profile.branch
        form = ParcelBookingForm(initial=init)

    branches = Branch.objects.filter(is_active=True)
    rates = ShippingRate.objects.all()
    return render(request, 'parcels/parcel_form.html', {
        'form': form,
        'branches': branches,
        'rates': rates,
    })


@login_required
def parcel_detail_view(request, tracking_number):
    parcel = get_object_or_404(
        Parcel.objects.select_related('origin_branch', 'destination_branch', 'current_branch', 'assigned_courier'),
        tracking_number=tracking_number
    )
    logs = parcel.tracking_logs.select_related('branch', 'updated_by').order_by('-created_at')
    status_form = ParcelStatusUpdateForm(initial={
        'status': parcel.status,
        'branch': parcel.current_branch or parcel.destination_branch,
        'location_name': f"{parcel.current_branch.name if parcel.current_branch else ''}"
    })
    courier_form = CourierAssignmentForm(initial={'courier': parcel.assigned_courier})

    qr_url = request.build_absolute_uri(f"/track/{parcel.tracking_number}/")
    qr_code_data = generate_qr_base64(qr_url)
    barcode_svg = generate_svg_barcode(parcel.tracking_number)

    return render(request, 'parcels/parcel_detail.html', {
        'parcel': parcel,
        'logs': logs,
        'status_form': status_form,
        'courier_form': courier_form,
        'qr_code_data': qr_code_data,
        'barcode_svg': barcode_svg,
    })


@login_required
def parcel_update_status_view(request, tracking_number):
    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)
    if request.method == 'POST':
        form = ParcelStatusUpdateForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            branch = form.cleaned_data['branch']
            location_name = form.cleaned_data['location_name']
            activity = form.cleaned_data['activity']
            notes = form.cleaned_data['notes']

            parcel.status = new_status
            if branch:
                parcel.current_branch = branch
            if new_status == 'DELIVERED':
                parcel.delivered_at = timezone.now()
                if not parcel.payment_status == 'PAID':
                    parcel.payment_status = 'PAID'
            parcel.save()

            ParcelTrackingLog.objects.create(
                parcel=parcel,
                status=new_status,
                branch=branch,
                location_name=location_name,
                activity=activity,
                notes=notes,
                updated_by=request.user
            )

            messages.success(request, f"Parcel status updated to '{parcel.get_status_display()}'.")
    return redirect('parcel_detail', tracking_number=parcel.tracking_number)


@login_required
def parcel_assign_courier_view(request, tracking_number):
    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)
    if request.method == 'POST':
        form = CourierAssignmentForm(request.POST)
        if form.is_valid():
            courier = form.cleaned_data['courier']
            notes = form.cleaned_data['delivery_notes']
            parcel.assigned_courier = courier
            parcel.delivery_notes = notes
            if parcel.status in ['RECEIVED_AT_DESTINATION', 'READY_FOR_PICKUP', 'BOOKED']:
                parcel.status = 'OUT_FOR_DELIVERY'

            parcel.save()

            ParcelTrackingLog.objects.create(
                parcel=parcel,
                status=parcel.status,
                branch=parcel.current_branch,
                location_name=f"{courier.get_full_name() or courier.username} (Courier)",
                activity=f"Handed over to courier {courier.get_full_name() or courier.username} for final delivery.",
                notes=notes,
                updated_by=request.user
            )
            messages.success(request, f"Assigned to courier {courier.get_full_name() or courier.username}.")
    return redirect('parcel_detail', tracking_number=parcel.tracking_number)


@login_required
def parcel_waybill_view(request, tracking_number):
    parcel = get_object_or_404(
        Parcel.objects.select_related('origin_branch', 'destination_branch'),
        tracking_number=tracking_number
    )
    qr_url = request.build_absolute_uri(f"/track/{parcel.tracking_number}/")
    qr_code_data = generate_qr_base64(qr_url)
    barcode_svg = generate_svg_barcode(parcel.tracking_number)

    return render(request, 'parcels/print_waybill.html', {
        'parcel': parcel,
        'qr_code_data': qr_code_data,
        'barcode_svg': barcode_svg,
    })


@login_required
def parcel_invoice_view(request, tracking_number):
    parcel = get_object_or_404(
        Parcel.objects.select_related('origin_branch', 'destination_branch'),
        tracking_number=tracking_number
    )
    barcode_svg = generate_svg_barcode(parcel.tracking_number)
    return render(request, 'parcels/print_invoice.html', {
        'parcel': parcel,
        'barcode_svg': barcode_svg,
    })


# ==============================================================================
# TRANSIT MANIFEST (LINEHAUL / BAGGING)
# ==============================================================================

@login_required
def manifest_list_view(request):
    manifests = TransitManifest.objects.select_related('origin_branch', 'destination_branch', 'created_by').annotate(
        parcel_count=Count('parcels')
    )
    return render(request, 'parcels/manifest_list.html', {'manifests': manifests})


@login_required
def manifest_create_view(request):
    if request.method == 'POST':
        form = TransitManifestForm(request.POST)
        parcel_ids = request.POST.getlist('selected_parcels')
        if form.is_valid():
            manifest = form.save(commit=False)
            manifest.created_by = request.user
            manifest.save()

            if parcel_ids:
                parcels_to_load = Parcel.objects.filter(id__in=parcel_ids)
                manifest.parcels.set(parcels_to_load)

            messages.success(request, f"Manifest #{manifest.manifest_number} created with {len(parcel_ids)} parcels loaded.")
            return redirect('manifest_detail', manifest_number=manifest.manifest_number)
    else:
        init = {}
        if hasattr(request.user, 'profile') and request.user.profile.branch:
            init['origin_branch'] = request.user.profile.branch
        form = TransitManifestForm(initial=init)

    # Parcels eligible for manifest loading: not delivered, booked or accepted
    available_parcels = Parcel.objects.filter(
        status__in=['RECEIVED_AT_ORIGIN', 'IN_SORTING', 'BOOKED']
    ).select_related('origin_branch', 'destination_branch')

    return render(request, 'parcels/manifest_form.html', {
        'form': form,
        'available_parcels': available_parcels,
    })


@login_required
def manifest_detail_view(request, manifest_number):
    manifest = get_object_or_404(
        TransitManifest.objects.select_related('origin_branch', 'destination_branch', 'created_by'),
        manifest_number=manifest_number
    )
    parcels = manifest.parcels.select_related('origin_branch', 'destination_branch')
    barcode_svg = generate_svg_barcode(manifest.manifest_number)

    return render(request, 'parcels/manifest_detail.html', {
        'manifest': manifest,
        'parcels': parcels,
        'barcode_svg': barcode_svg,
    })


@login_required
def manifest_dispatch_view(request, manifest_number):
    manifest = get_object_or_404(TransitManifest, manifest_number=manifest_number)
    if manifest.status != 'DISPATCHED':
        manifest.status = 'DISPATCHED'
        manifest.dispatched_at = timezone.now()
        manifest.save()

        # Update all attached parcels to IN_TRANSIT
        for p in manifest.parcels.all():
            p.status = 'IN_TRANSIT'
            p.save()
            ParcelTrackingLog.objects.create(
                parcel=p,
                status='IN_TRANSIT',
                branch=manifest.origin_branch,
                location_name=f"Linehaul Route {manifest.origin_branch.code} -> {manifest.destination_branch.code}",
                activity=f"Dispatched via Vehicle {manifest.vehicle_plate} (Driver: {manifest.driver_name}) under Manifest #{manifest.manifest_number}",
                notes="Consignment in transit between logistics hubs.",
                updated_by=request.user
            )

        messages.success(request, f"Manifest #{manifest.manifest_number} dispatched! All {manifest.parcels.count()} parcels are now IN TRANSIT.")
    return redirect('manifest_detail', manifest_number=manifest.manifest_number)


@login_required
def manifest_receive_view(request, manifest_number):
    manifest = get_object_or_404(TransitManifest, manifest_number=manifest_number)
    if manifest.status == 'DISPATCHED':
        manifest.status = 'RECEIVED'
        manifest.received_at = timezone.now()
        manifest.save()

        # Update all attached parcels to RECEIVED_AT_DESTINATION
        for p in manifest.parcels.all():
            p.status = 'RECEIVED_AT_DESTINATION'
            p.current_branch = manifest.destination_branch
            p.save()
            ParcelTrackingLog.objects.create(
                parcel=p,
                status='RECEIVED_AT_DESTINATION',
                branch=manifest.destination_branch,
                location_name=f"{manifest.destination_branch.name}, {manifest.destination_branch.city}",
                activity=f"Arrived and unloaded from Vehicle {manifest.vehicle_plate}. Manifest #{manifest.manifest_number} verified.",
                notes="Checked into destination hub inventory.",
                updated_by=request.user
            )

        messages.success(request, f"Manifest #{manifest.manifest_number} marked as ARRIVED & RECEIVED! Inventory updated.")
    return redirect('manifest_detail', manifest_number=manifest.manifest_number)


# ==============================================================================
# COURIER ACTIONS
# ==============================================================================

@login_required
def courier_delivery_action_view(request, tracking_number):
    parcel = get_object_or_404(Parcel, tracking_number=tracking_number)
    
    # Courier verification: only assigned rider or admin/staff can update
    is_courier = (request.user == parcel.assigned_courier)
    is_staff = request.user.is_staff or (hasattr(request.user, 'profile') and request.user.profile.is_staff_member)
    if not (is_courier or is_staff):
        messages.error(request, "Permission denied. You are not assigned to deliver this consignment.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = CourierDeliveryActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            recv_name = form.cleaned_data['receiver_name']
            otp = form.cleaned_data['security_otp']
            notes = form.cleaned_data['delivery_notes']

            if action == 'DELIVER':
                # Verify OTP if recipient provided one
                if otp and parcel.security_otp and otp.strip() != parcel.security_otp.strip():
                    messages.error(request, "Incorrect Security OTP! Delivery cannot be confirmed without valid recipient OTP.")
                    return render(request, 'courier/delivery_action.html', {'parcel': parcel, 'form': form})

                parcel.status = 'DELIVERED'
                parcel.delivered_at = timezone.now()
                parcel.received_by_name = recv_name or parcel.receiver_name
                parcel.delivery_notes = notes
                if parcel.payment_status in ['PENDING', 'COD']:
                    parcel.payment_status = 'PAID'
                parcel.save()

                ParcelTrackingLog.objects.create(
                    parcel=parcel,
                    status='DELIVERED',
                    branch=parcel.current_branch,
                    location_name=f"{parcel.receiver_address}, {parcel.receiver_city}",
                    activity=f"Successfully delivered to {parcel.received_by_name}. Verified by OTP confirmation.",
                    notes=notes,
                    updated_by=request.user
                )
                messages.success(request, f"Parcel #{parcel.tracking_number} marked as DELIVERED!")
                return redirect('dashboard')

            elif action == 'FAILED':
                parcel.delivery_attempts += 1
                parcel.status = 'FAILED_ATTEMPT'
                parcel.delivery_notes = notes
                parcel.save()

                ParcelTrackingLog.objects.create(
                    parcel=parcel,
                    status='FAILED_ATTEMPT',
                    branch=parcel.current_branch,
                    location_name=f"{parcel.receiver_address}, {parcel.receiver_city}",
                    activity=f"Delivery attempt #{parcel.delivery_attempts} failed. Reason: {notes or 'Customer not available'}",
                    notes=notes,
                    updated_by=request.user
                )
                messages.warning(request, f"Delivery attempt recorded as failed for #{parcel.tracking_number}.")
                return redirect('dashboard')
    else:
        form = CourierDeliveryActionForm(initial={'receiver_name': parcel.receiver_name})

    return render(request, 'courier/delivery_action.html', {
        'parcel': parcel,
        'form': form,
    })


# ==============================================================================
# PICKUP REQUEST MANAGEMENT
# ==============================================================================

@login_required
def pickup_list_view(request):
    pickups = PickupRequest.objects.select_related('branch', 'assigned_courier').order_by('-created_at')
    couriers = User.objects.filter(profile__role='COURIER')
    return render(request, 'parcels/pickup_list.html', {
        'pickups': pickups,
        'couriers': couriers,
    })


@login_required
def pickup_assign_view(request, request_number):
    pickup = get_object_or_404(PickupRequest, request_number=request_number)
    if request.method == 'POST':
        courier_id = request.POST.get('courier_id')
        if courier_id:
            courier = get_object_or_404(User, id=courier_id)
            pickup.assigned_courier = courier
            pickup.status = 'ASSIGNED'
            pickup.save()
            messages.success(request, f"Pickup #{pickup.request_number} assigned to {courier.get_full_name() or courier.username}.")
    return redirect('pickup_list')


@login_required
def pickup_convert_view(request, request_number):
    pickup = get_object_or_404(PickupRequest, request_number=request_number)
    if request.method == 'POST':
        # Prepopulate booking form from pickup
        return redirect(f"/parcels/create/?sender_name={pickup.customer_name}&sender_phone={pickup.customer_phone}&sender_email={pickup.customer_email}&sender_address={pickup.pickup_address}&sender_city={pickup.pickup_city}&item_desc={pickup.package_description}&weight={pickup.estimated_weight_kg}")
    return redirect('pickup_list')


# ==============================================================================
# CUSTOMER INQUIRIES & TICKETS
# ==============================================================================

@login_required
def inquiry_list_view(request):
    inquiries = CustomerInquiry.objects.select_related('replied_by').order_by('-created_at')
    return render(request, 'parcels/inquiry_list.html', {'inquiries': inquiries})


@login_required
def inquiry_detail_view(request, ticket_number):
    inquiry = get_object_or_404(CustomerInquiry, ticket_number=ticket_number)
    if request.method == 'POST':
        form = InquiryReplyForm(request.POST)
        if form.is_valid():
            inquiry.status = form.cleaned_data['status']
            inquiry.staff_reply = form.cleaned_data['staff_reply']
            inquiry.replied_by = request.user
            inquiry.save()
            messages.success(request, f"Reply saved for ticket #{inquiry.ticket_number}.")
            return redirect('inquiry_list')
    else:
        form = InquiryReplyForm(initial={
            'status': inquiry.status,
            'staff_reply': inquiry.staff_reply
        })
    return render(request, 'parcels/inquiry_detail.html', {
        'inquiry': inquiry,
        'form': form,
    })


# ==============================================================================
# JSON ASYNCHRONOUS APIS
# ==============================================================================

def api_calculate_rate(request):
    """Calculates shipping rate on the fly."""
    service_type = request.GET.get('service_type', 'STANDARD')
    try:
        weight_kg = float(request.GET.get('weight_kg', 1.0))
        length_cm = float(request.GET.get('length_cm', 10.0))
        width_cm = float(request.GET.get('width_cm', 10.0))
        height_cm = float(request.GET.get('height_cm', 10.0))
        is_fragile = request.GET.get('is_fragile', 'false').lower() in ['true', '1', 'yes']
        declared_value = float(request.GET.get('declared_value', 0.0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid numerical inputs'}, status=400)

    pricing = calculate_shipping_cost(
        service_type=service_type,
        weight_kg=weight_kg,
        length_cm=length_cm,
        width_cm=width_cm,
        height_cm=height_cm,
        is_fragile=is_fragile,
        declared_value=declared_value
    )
    return JsonResponse(pricing)


def api_quick_track(request, tracking_number):
    parcel = Parcel.objects.filter(tracking_number__iexact=tracking_number).first()
    if not parcel:
        return JsonResponse({'found': False, 'message': 'Tracking number not found'}, status=404)

    return JsonResponse({
        'found': True,
        'tracking_number': parcel.tracking_number,
        'status': parcel.status,
        'status_display': parcel.get_status_display(),
        'origin': parcel.origin_branch.city,
        'destination': parcel.destination_branch.city,
        'current_location': parcel.current_branch.name if parcel.current_branch else 'In Transit',
        'progress': parcel.progress_percentage,
        'recipient': parcel.receiver_name,
        'updated_at': parcel.updated_at.strftime('%Y-%m-%d %H:%M'),
    })
