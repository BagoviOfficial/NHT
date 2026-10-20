from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Parcel, ShipmentItem, ParcelStatusHistory, ParcelStatus, PaymentStatus, PaymentMethod
from audit.services import log_audit_event

ALLOWED_TRANSITIONS = {
    ParcelStatus.RECEIVED_AT_HQ: [ParcelStatus.IN_TRANSIT, ParcelStatus.CANCELLED],
    ParcelStatus.IN_TRANSIT: [ParcelStatus.ARRIVED_AT_DESTINATION, ParcelStatus.CANCELLED],
    ParcelStatus.ARRIVED_AT_DESTINATION: [ParcelStatus.AWAITING_COLLECTION, ParcelStatus.CANCELLED],
    ParcelStatus.AWAITING_COLLECTION: [ParcelStatus.COLLECTED, ParcelStatus.CANCELLED],
    ParcelStatus.COLLECTED: [],
    ParcelStatus.CANCELLED: [],
}


def calculate_parcel_total(parcel: Parcel) -> Decimal:
    """
    Computes total shipping cost from all line items and updates parcel.price.
    Uses exact Decimal arithmetic.
    """
    total = sum((item.line_total for item in parcel.items.all()), Decimal('0.00'))
    parcel.price = total
    parcel.save(update_fields=['price', 'updated_at'])
    return total


@transaction.atomic
def create_parcel(
    route,
    sender_name: str,
    sender_phone: str,
    receiver_name: str,
    receiver_phone: str,
    receiver_id_number: str,
    payment_status: str,
    payment_method: str,
    items_data: list,
    created_by=None,
    request=None,
    tenant=None
) -> Parcel:
    """
    Creates a new parcel along with its shipment items inside an atomic transaction.
    """
    if not items_data:
        raise ValidationError("At least one shipment item must be provided.")

    if not tenant:
        if route and getattr(route, 'tenant', None):
            tenant = route.tenant
        elif created_by and getattr(created_by, 'tenant', None):
            tenant = created_by.tenant
        elif request and getattr(request, 'tenant', None):
            tenant = request.tenant

    if route and getattr(route, 'tenant_id', None) and tenant and getattr(tenant, 'pk', None):
        if route.tenant_id != tenant.pk:
            raise ValidationError("The selected destination route does not belong to this organization.")

    if route and not route.is_active:
        raise ValidationError("Cannot create consignment for an inactive destination route.")

    parcel = Parcel.objects.create(
        tenant=tenant,
        route=route,
        sender_name=sender_name,
        sender_phone=sender_phone,
        receiver_name=receiver_name,
        receiver_phone=receiver_phone,
        receiver_id_number=receiver_id_number,
        payment_status=payment_status,
        payment_method=payment_method,
        status=ParcelStatus.RECEIVED_AT_HQ,
        created_by=created_by,
        price=Decimal('0.00')
    )

    total_price = Decimal('0.00')
    for item in items_data:
        qty = int(item.get('quantity', 1))
        unit_price = Decimal(str(item.get('unit_price', '0.00')))
        desc = item.get('description', '').strip()
        wrap = item.get('wrap_type', 'Box').strip()

        if qty <= 0:
            raise ValidationError("Item quantity must be greater than zero.")
        if qty > 10000:
            raise ValidationError("Item quantity cannot exceed 10,000.")
        if unit_price < Decimal('0.00'):
            raise ValidationError("Unit price cannot be negative.")
        if unit_price > Decimal('10000000.00'):
            raise ValidationError("Unit price exceeds maximum allowable limit (10,000,000.00).")
        if not desc:
            raise ValidationError("Item description cannot be empty.")

        line_total = Decimal(str(qty)) * unit_price
        ShipmentItem.objects.create(
            parcel=parcel,
            description=desc,
            wrap_type=wrap,
            quantity=qty,
            unit_price=unit_price,
            line_total=line_total
        )
        total_price += line_total

    parcel.price = total_price
    parcel.save(update_fields=['price'])

    # Record initial status history
    ParcelStatusHistory.objects.create(
        parcel=parcel,
        old_status='',
        new_status=ParcelStatus.RECEIVED_AT_HQ,
        user=created_by,
        note="Parcel registered at Head Office (Nairobi)"
    )

    log_audit_event(
        action='PARCEL_CREATE',
        actor=created_by,
        object_type='Parcel',
        object_identifier=parcel.tracking_number,
        new_values={
            'tracking_number': parcel.tracking_number,
            'route': parcel.route.name,
            'price': str(parcel.price),
            'payment_status': parcel.payment_status,
            'items_count': len(items_data),
        },
        reason="Registered new consignment",
        request=request
    )

    return parcel


@transaction.atomic
def update_parcel(
    parcel_id: int,
    route,
    sender_name: str,
    sender_phone: str,
    receiver_name: str,
    receiver_phone: str,
    receiver_id_number: str,
    payment_status: str,
    payment_method: str,
    items_data: list,
    user=None,
    request=None
) -> Parcel:
    """
    Updates core shipment data before dispatch.
    """
    parcel = Parcel.objects.select_for_update().get(pk=parcel_id)

    if not parcel.is_editable:
        raise ValidationError("Shipments cannot be edited once dispatched.")

    if route and getattr(route, 'tenant_id', None) and parcel.tenant_id:
        if route.tenant_id != parcel.tenant_id:
            raise ValidationError("The selected destination route does not belong to this organization.")

    if route and not route.is_active and route != parcel.route:
        raise ValidationError("Cannot assign shipment to an inactive destination route.")

    old_vals = {
        'sender_name': parcel.sender_name,
        'receiver_name': parcel.receiver_name,
        'price': str(parcel.price),
        'payment_status': parcel.payment_status,
        'route': parcel.route.name,
    }

    parcel.route = route
    parcel.sender_name = sender_name
    parcel.sender_phone = sender_phone
    parcel.receiver_name = receiver_name
    parcel.receiver_phone = receiver_phone
    parcel.receiver_id_number = receiver_id_number
    parcel.payment_status = payment_status
    parcel.payment_method = payment_method

    # Replace items
    parcel.items.all().delete()
    total_price = Decimal('0.00')
    for item in items_data:
        qty = int(item.get('quantity', 1))
        unit_price = Decimal(str(item.get('unit_price', '0.00')))
        desc = item.get('description', '').strip()
        wrap = item.get('wrap_type', 'Box').strip()

        if qty <= 0:
            raise ValidationError("Item quantity must be greater than zero.")
        if qty > 10000:
            raise ValidationError("Item quantity cannot exceed 10,000.")
        if unit_price < Decimal('0.00'):
            raise ValidationError("Unit price cannot be negative.")
        if unit_price > Decimal('10000000.00'):
            raise ValidationError("Unit price exceeds maximum allowable limit (10,000,000.00).")
        if not desc:
            raise ValidationError("Item description cannot be empty.")

        line_total = Decimal(str(qty)) * unit_price
        ShipmentItem.objects.create(
            parcel=parcel,
            description=desc,
            wrap_type=wrap,
            quantity=qty,
            unit_price=unit_price,
            line_total=line_total
        )
        total_price += line_total

    parcel.price = total_price
    parcel.save()

    log_audit_event(
        action='PARCEL_EDIT',
        actor=user,
        object_type='Parcel',
        object_identifier=parcel.tracking_number,
        old_values=old_vals,
        new_values={
            'sender_name': parcel.sender_name,
            'receiver_name': parcel.receiver_name,
            'price': str(parcel.price),
            'payment_status': parcel.payment_status,
            'route': parcel.route.name,
        },
        reason="Updated parcel consignment data before dispatch",
        request=request
    )

    return parcel


@transaction.atomic
def transition_parcel_status(
    parcel_id: int,
    new_status: str,
    user=None,
    note: str = "",
    truck_plate_number: str = None,
    driver_name: str = None,
    request=None
) -> Parcel:
    """
    Central state transition engine with database locking and audit history.
    """
    parcel = Parcel.objects.select_for_update().get(pk=parcel_id)
    current_status = parcel.status

    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise ValidationError(
            f"Invalid status transition from '{parcel.get_status_display()}' to '{new_status}'."
        )

    # Dispatch requirements validation
    if new_status == ParcelStatus.IN_TRANSIT:
        truck = (truck_plate_number or parcel.truck_plate_number or '').strip()
        driver = (driver_name or parcel.driver_name or '').strip()
        if not truck or not driver:
            raise ValidationError(
                "Dispatch to IN_TRANSIT requires a valid truck plate number and driver name."
            )
        parcel.truck_plate_number = truck
        parcel.driver_name = driver

    old_status = parcel.status
    parcel.status = new_status
    parcel.save()

    # Create history entry
    ip_addr = None
    if request:
        from audit.services import get_client_ip
        ip_addr = get_client_ip(request)

    ParcelStatusHistory.objects.create(
        parcel=parcel,
        old_status=old_status,
        new_status=new_status,
        user=user,
        note=note or "",
        ip_address=ip_addr
    )

    log_audit_event(
        action='STATUS_CHANGE',
        actor=user,
        object_type='Parcel',
        object_identifier=parcel.tracking_number,
        old_values={'status': old_status},
        new_values={'status': new_status, 'truck': parcel.truck_plate_number, 'driver': parcel.driver_name},
        reason=note or f"Transitioned parcel to {new_status}",
        request=request
    )

    return parcel


@transaction.atomic
def collect_parcel(
    parcel_id: int,
    collected_by_name: str,
    user=None,
    note: str = "",
    request=None
) -> Parcel:
    """
    Marks parcel COLLECTED. Ensures idempotent collection and records recipient details.
    """
    parcel = Parcel.objects.select_for_update().get(pk=parcel_id)

    if parcel.status == ParcelStatus.COLLECTED:
        raise ValidationError("This parcel has already been collected and cannot be collected again.")

    if parcel.status != ParcelStatus.AWAITING_COLLECTION:
        raise ValidationError(
            f"Parcels must be marked '{ParcelStatus.AWAITING_COLLECTION.label}' before collection. Current status: '{parcel.get_status_display()}'."
        )

    collector = (collected_by_name or '').strip()
    if not collector:
        raise ValidationError("Collector full name is mandatory.")

    old_status = parcel.status
    parcel.status = ParcelStatus.COLLECTED
    parcel.collected_by_name = collector
    parcel.collected_at = timezone.now()
    parcel.save()

    ip_addr = None
    if request:
        from audit.services import get_client_ip
        ip_addr = get_client_ip(request)

    ParcelStatusHistory.objects.create(
        parcel=parcel,
        old_status=old_status,
        new_status=ParcelStatus.COLLECTED,
        user=user,
        note=f"Collected by: {collector}. {note}".strip(),
        ip_address=ip_addr
    )

    log_audit_event(
        action='COLLECTION',
        actor=user,
        object_type='Parcel',
        object_identifier=parcel.tracking_number,
        old_values={'status': old_status},
        new_values={'status': ParcelStatus.COLLECTED, 'collected_by': collector},
        reason=f"Parcel collected by {collector}",
        request=request
    )

    return parcel


@transaction.atomic
def cancel_parcel(
    parcel_id: int,
    reason: str,
    user=None,
    request=None
) -> Parcel:
    """
    Cancels a parcel with mandatory reason.
    """
    parcel = Parcel.objects.select_for_update().get(pk=parcel_id)

    if parcel.is_terminal:
        raise ValidationError(f"Cannot cancel parcel that is already in terminal state '{parcel.get_status_display()}'.")

    clean_reason = (reason or '').strip()
    if not clean_reason:
        raise ValidationError("A reason must be stated when cancelling a shipment.")

    old_status = parcel.status
    parcel.status = ParcelStatus.CANCELLED
    parcel.save()

    ip_addr = None
    if request:
        from audit.services import get_client_ip
        ip_addr = get_client_ip(request)

    ParcelStatusHistory.objects.create(
        parcel=parcel,
        old_status=old_status,
        new_status=ParcelStatus.CANCELLED,
        user=user,
        note=f"Cancellation reason: {clean_reason}",
        ip_address=ip_addr
    )

    log_audit_event(
        action='CANCELLATION',
        actor=user,
        object_type='Parcel',
        object_identifier=parcel.tracking_number,
        old_values={'status': old_status},
        new_values={'status': ParcelStatus.CANCELLED},
        reason=clean_reason,
        request=request
    )

    return parcel
