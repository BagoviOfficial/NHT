import secrets
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _


class ParcelStatus(models.TextChoices):
    RECEIVED_AT_HQ = 'RECEIVED_AT_HQ', _('Received at Head Office (Nairobi)')
    IN_TRANSIT = 'IN_TRANSIT', _('In Transit')
    ARRIVED_AT_DESTINATION = 'ARRIVED_AT_DESTINATION', _('Arrived at Destination')
    AWAITING_COLLECTION = 'AWAITING_COLLECTION', _('Awaiting Collection')
    COLLECTED = 'COLLECTED', _('Collected')
    CANCELLED = 'CANCELLED', _('Cancelled')


class PaymentStatus(models.TextChoices):
    PAID = 'PAID', _('Paid')
    COD = 'COD', _('Cash on Delivery (Pending)')
    UNPAID = 'UNPAID', _('Unpaid')


class PaymentMethod(models.TextChoices):
    CASH = 'CASH', _('Cash')
    MPESA = 'MPESA', _('M-Pesa')


def generate_tracking_number(prefix: str = 'NHT') -> str:
    """
    Generates a cryptographically random, collision-safe tracking number.
    Format: <PREFIX>-XXXXXXXX (8 uppercase alphanumeric chars, excluding ambiguous 0, O, 1, I).
    """
    alphabet = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
    code = ''.join(secrets.choice(alphabet) for _ in range(8))
    clean_prefix = (prefix or 'NHT').strip().upper()
    return f"{clean_prefix}-{code}"


class Parcel(models.Model):
    """
    Core parcel entity for multi-tenant courier platform.
    Origin is fixed as Head Office (Nairobi/Tenant HQ); Destination is specified by Route.
    Does NOT include weight, as per specification.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='parcels',
        help_text=_("Client organization managing this consignment.")
    )
    tracking_number = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text=_("Unique tracking number in format <PREFIX>-XXXXXXXX.")
    )
    route = models.ForeignKey(
        'routes.Route',
        on_delete=models.PROTECT,
        related_name='parcels',
        help_text=_("Destination route/station.")
    )
    truck_plate_number = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Vehicle registration plate (required upon dispatch).")
    )
    driver_name = models.CharField(
        max_length=150,
        blank=True,
        help_text=_("Driver full name (required upon dispatch).")
    )
    sender_name = models.CharField(max_length=150)
    sender_phone = models.CharField(max_length=30)
    receiver_name = models.CharField(max_length=150)
    receiver_phone = models.CharField(max_length=30)
    receiver_id_number = models.CharField(
        max_length=50,
        help_text=_("National ID or Passport number of recipient.")
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PAID,
        db_index=True
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH
    )
    status = models.CharField(
        max_length=35,
        choices=ParcelStatus.choices,
        default=ParcelStatus.RECEIVED_AT_HQ,
        db_index=True
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text=_("Total shipping charge calculated as sum of shipment items.")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_parcels'
    )
    collected_by_name = models.CharField(
        max_length=150,
        blank=True,
        help_text=_("Full name of individual who claimed/collected the parcel.")
    )
    collected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Timestamp when parcel was formally marked collected.")
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Parcel')
        verbose_name_plural = _('Parcels')
        indexes = [
            models.Index(fields=['tracking_number']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.tracking_number} -> {self.route.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.tenant and hasattr(self, 'route') and self.route and getattr(self.route, 'tenant', None):
            self.tenant = self.route.tenant
        if not self.tracking_number:
            prefix = self.tenant.tracking_prefix if self.tenant and self.tenant.tracking_prefix else 'NHT'
            num = generate_tracking_number(prefix=prefix)
            while Parcel.objects.filter(tracking_number=num).exists():
                num = generate_tracking_number(prefix=prefix)
            self.tracking_number = num
        super().save(*args, **kwargs)

    @property
    def is_editable(self):
        """Standard editing only permitted while parcel is RECEIVED_AT_HQ."""
        return self.status == ParcelStatus.RECEIVED_AT_HQ

    @property
    def is_terminal(self):
        return self.status in [ParcelStatus.COLLECTED, ParcelStatus.CANCELLED]

    @property
    def status_badge_class(self):
        badges = {
            ParcelStatus.RECEIVED_AT_HQ: 'bg-primary text-white',
            ParcelStatus.IN_TRANSIT: 'bg-warning text-dark',
            ParcelStatus.ARRIVED_AT_DESTINATION: 'bg-info text-dark',
            ParcelStatus.AWAITING_COLLECTION: 'bg-secondary text-white',
            ParcelStatus.COLLECTED: 'bg-success text-white',
            ParcelStatus.CANCELLED: 'bg-danger text-white',
        }
        return badges.get(self.status, 'bg-light text-dark')


class ShipmentItem(models.Model):
    """
    Individual item or package within a parcel consignment.
    """
    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.CASCADE,
        related_name='items'
    )
    description = models.CharField(max_length=255, help_text=_("Description of contents"))
    wrap_type = models.CharField(
        max_length=100,
        default='Box',
        help_text=_("Packaging type (e.g. Box, Sack, Carton, Envelope, Bundle)")
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_("Item count (minimum 1)")
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text=_("Charge per item unit")
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        verbose_name = _('Shipment Item')
        verbose_name_plural = _('Shipment Items')

    def __str__(self):
        return f"{self.quantity}x {self.description} ({self.wrap_type})"

    def save(self, *args, **kwargs):
        self.line_total = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)


class ParcelStatusHistory(models.Model):
    """
    Audit log of all parcel status transitions.
    """
    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    old_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    note = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Parcel Status History')
        verbose_name_plural = _('Parcel Status Histories')

    def __str__(self):
        user_str = self.user.username if self.user else 'System'
        return f"{self.parcel.tracking_number}: {self.old_status} -> {self.new_status} by {user_str} at {self.created_at}"
