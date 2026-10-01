import uuid
import random
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Branch(models.Model):
    BRANCH_TYPE_CHOICES = [
        ('MAIN_HUB', 'Main Sorting Hub'),
        ('DISTRIBUTION', 'Regional Distribution Center'),
        ('LOCAL_OFFICE', 'Local Branch / Pickup Station'),
    ]

    code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    branch_type = models.CharField(max_length=30, choices=BRANCH_TYPE_CHOICES, default='LOCAL_OFFICE')
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='United States')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Branches'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.city}"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'HQ Administrator / Manager'),
        ('BRANCH_STAFF', 'Branch Staff / Clerk'),
        ('COURIER', 'Courier / Delivery Rider'),
        ('CUSTOMER', 'Customer / Client'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='CUSTOMER')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_members')
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    vehicle_type = models.CharField(max_length=50, blank=True, null=True)
    license_plate = models.CharField(max_length=30, blank=True, null=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} [{self.get_role_display()}]"

    @property
    def is_admin(self):
        return self.role == 'ADMIN' or self.user.is_superuser

    @property
    def is_staff_member(self):
        return self.role in ['ADMIN', 'BRANCH_STAFF'] or self.user.is_staff

    @property
    def is_courier(self):
        return self.role == 'COURIER'

    @property
    def is_customer(self):
        return self.role == 'CUSTOMER'


class ShippingRate(models.Model):
    SERVICE_CHOICES = [
        ('STANDARD', 'Standard Ground (3-5 Days)'),
        ('EXPRESS', 'Express Air (1-2 Days)'),
        ('SAME_DAY', 'Same-Day Priority (Within 24h)'),
    ]

    service_type = models.CharField(max_length=30, choices=SERVICE_CHOICES, unique=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    per_kg_rate = models.DecimalField(max_digits=10, decimal_places=2, default=2.50)
    fragile_fee = models.DecimalField(max_digits=10, decimal_places=2, default=4.00)
    insurance_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=1.50)
    tax_pct = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    delivery_time_frame = models.CharField(max_length=100, default='3-5 Business Days')

    def __str__(self):
        return f"{self.get_service_type_display()} - Base: ${self.base_price}"


class Parcel(models.Model):
    STATUS_CHOICES = [
        ('BOOKED', 'Order Placed / Registered'),
        ('RECEIVED_AT_ORIGIN', 'Accepted at Origin Branch'),
        ('IN_SORTING', 'Sorting Facility / Hub'),
        ('IN_TRANSIT', 'In Transit / Dispatched'),
        ('RECEIVED_AT_DESTINATION', 'Arrived at Destination Hub'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('READY_FOR_PICKUP', 'Ready for Branch Pickup'),
        ('DELIVERED', 'Delivered Successfully'),
        ('FAILED_ATTEMPT', 'Delivery Attempt Failed'),
        ('RETURNED', 'Returned to Sender'),
        ('CANCELLED', 'Cancelled'),
    ]

    DELIVERY_TYPE_CHOICES = [
        ('DOORSTEP', 'Doorstep Delivery'),
        ('BRANCH_PICKUP', 'Branch Pickup Station'),
    ]

    CATEGORY_CHOICES = [
        ('DOCUMENT', 'Documents & Letters'),
        ('ELECTRONICS', 'Electronics & Gadgets'),
        ('APPAREL', 'Clothing & Apparel'),
        ('FRAGILE', 'Fragile & Glassware'),
        ('PERISHABLE', 'Food & Perishables'),
        ('HEAVY_FREIGHT', 'Heavy Cargo / Freight'),
        ('GENERAL', 'General Merchandise'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('PAID', 'Paid in Full'),
        ('PENDING', 'Payment Pending'),
        ('COD', 'Cash on Delivery (Pending)'),
        ('REFUNDED', 'Refunded'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CARD', 'Credit / Debit Card'),
        ('MOBILE_MONEY', 'Mobile Money / Digital Wallet'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('COD', 'Cash on Delivery'),
    ]

    tracking_number = models.CharField(max_length=32, unique=True, db_index=True)
    security_otp = models.CharField(max_length=6, blank=True)

    # Sender Information
    sender_name = models.CharField(max_length=150)
    sender_phone = models.CharField(max_length=30)
    sender_email = models.EmailField(blank=True)
    sender_address = models.TextField()
    sender_city = models.CharField(max_length=100)
    sender_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_parcels')

    # Receiver Information
    receiver_name = models.CharField(max_length=150)
    receiver_phone = models.CharField(max_length=30)
    receiver_email = models.EmailField(blank=True)
    receiver_address = models.TextField()
    receiver_city = models.CharField(max_length=100)
    receiver_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_parcels')

    # Routing
    origin_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='origin_parcels')
    destination_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='destination_parcels')
    current_branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='current_parcels')

    # Specifications
    delivery_type = models.CharField(max_length=30, choices=DELIVERY_TYPE_CHOICES, default='DOORSTEP')
    service_type = models.CharField(max_length=30, choices=ShippingRate.SERVICE_CHOICES, default='STANDARD')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='GENERAL')
    item_description = models.TextField(help_text="Detailed description of goods inside")
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2, default=1.00)
    length_cm = models.DecimalField(max_digits=8, decimal_places=1, default=10.0)
    width_cm = models.DecimalField(max_digits=8, decimal_places=1, default=10.0)
    height_cm = models.DecimalField(max_digits=8, decimal_places=1, default=10.0)
    is_fragile = models.BooleanField(default=False)
    declared_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Status & Logistics
    status = models.CharField(max_length=35, choices=STATUS_CHOICES, default='BOOKED', db_index=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='CASH')

    # Pricing Breakdown
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    weight_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fragile_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    insurance_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)

    # Courier & Delivery Execution
    assigned_courier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_deliveries')
    delivery_attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True, blank=True)
    received_by_name = models.CharField(max_length=150, blank=True)
    delivery_notes = models.TextField(blank=True)

    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_parcels')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tracking_number} - {self.receiver_name} ({self.get_status_display()})"

    @staticmethod
    def generate_tracking_number():
        """Generates a professional tracking code like PRCL-202610-8B9X"""
        date_str = timezone.now().strftime('%Y%m')
        rand_str = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=6))
        return f"PRCL-{date_str}-{rand_str}"

    @staticmethod
    def generate_otp():
        return f"{random.randint(100000, 999999)}"

    def calculate_pricing(self):
        """Calculates accurate shipping charges based on weight, rates, fragile, and value"""
        try:
            rate_obj = ShippingRate.objects.get(service_type=self.service_type)
        except ShippingRate.DoesNotExist:
            rate_obj = None

        base = rate_obj.base_price if rate_obj else 5.00
        per_kg = rate_obj.per_kg_rate if rate_obj else 2.50
        fragile_cost = rate_obj.fragile_fee if (rate_obj and self.is_fragile) else (4.00 if self.is_fragile else 0.00)
        ins_pct = (rate_obj.insurance_rate_pct if rate_obj else 1.5) / 100
        tax_pct = (rate_obj.tax_pct if rate_obj else 5.0) / 100

        # volumetric weight: (L * W * H) / 5000
        vol_weight = (float(self.length_cm) * float(self.width_cm) * float(self.height_cm)) / 5000.0
        billable_weight = max(float(self.weight_kg), vol_weight)

        weight_cost = round(billable_weight * float(per_kg), 2)
        ins_cost = round(float(self.declared_value) * float(ins_pct), 2)
        subtotal = float(base) + weight_cost + float(fragile_cost) + ins_cost
        tax = round(subtotal * float(tax_pct), 2)
        total = round(subtotal + tax, 2)

        self.base_price = base
        self.weight_price = weight_cost
        self.fragile_fee = fragile_cost
        self.insurance_fee = ins_cost
        self.tax_amount = tax
        self.total_price = total

    def save(self, *args, **kwargs):
        if not self.tracking_number:
            self.tracking_number = self.generate_tracking_number()
        if not self.security_otp:
            self.security_otp = self.generate_otp()
        if not self.current_branch and self.origin_branch:
            self.current_branch = self.origin_branch
        super().save(*args, **kwargs)

    @property
    def status_badge_class(self):
        classes = {
            'BOOKED': 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
            'RECEIVED_AT_ORIGIN': 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300',
            'IN_SORTING': 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
            'IN_TRANSIT': 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
            'RECEIVED_AT_DESTINATION': 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300',
            'OUT_FOR_DELIVERY': 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
            'READY_FOR_PICKUP': 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300',
            'DELIVERED': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
            'FAILED_ATTEMPT': 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300',
            'RETURNED': 'bg-gray-200 text-gray-800 dark:bg-gray-800 dark:text-gray-300',
            'CANCELLED': 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
        }
        return classes.get(self.status, 'bg-gray-100 text-gray-800')

    @property
    def progress_percentage(self):
        mapping = {
            'BOOKED': 15,
            'RECEIVED_AT_ORIGIN': 30,
            'IN_SORTING': 45,
            'IN_TRANSIT': 60,
            'RECEIVED_AT_DESTINATION': 75,
            'OUT_FOR_DELIVERY': 90,
            'READY_FOR_PICKUP': 90,
            'DELIVERED': 100,
            'FAILED_ATTEMPT': 85,
            'RETURNED': 100,
            'CANCELLED': 100,
        }
        return mapping.get(self.status, 10)


class ParcelTrackingLog(models.Model):
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='tracking_logs')
    status = models.CharField(max_length=35, choices=Parcel.STATUS_CHOICES)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    location_name = models.CharField(max_length=150)
    activity = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.parcel.tracking_number} - {self.get_status_display()} at {self.created_at}"


class TransitManifest(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Preparing / Loading'),
        ('DISPATCHED', 'Dispatched / In Transit'),
        ('RECEIVED', 'Arrived & Received'),
        ('CANCELLED', 'Cancelled'),
    ]

    manifest_number = models.CharField(max_length=32, unique=True, db_index=True)
    origin_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='outgoing_manifests')
    destination_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='incoming_manifests')
    driver_name = models.CharField(max_length=150)
    driver_phone = models.CharField(max_length=30)
    vehicle_plate = models.CharField(max_length=50)
    parcels = models.ManyToManyField(Parcel, related_name='manifests', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Manifest {self.manifest_number} ({self.origin_branch.code} -> {self.destination_branch.code})"

    @staticmethod
    def generate_manifest_number():
        date_str = timezone.now().strftime('%Y%m')
        rand_str = ''.join(random.choices('0123456789', k=5))
        return f"MNF-{date_str}-{rand_str}"

    def save(self, *args, **kwargs):
        if not self.manifest_number:
            self.manifest_number = self.generate_manifest_number()
        super().save(*args, **kwargs)


class PickupRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Assignment'),
        ('ASSIGNED', 'Courier Assigned'),
        ('PICKED_UP', 'Picked Up Successfully'),
        ('COMPLETED', 'Converted to Parcel'),
        ('CANCELLED', 'Cancelled'),
    ]

    TIME_SLOT_CHOICES = [
        ('MORNING', 'Morning (09:00 AM - 12:00 PM)'),
        ('AFTERNOON', 'Afternoon (12:00 PM - 04:00 PM)'),
        ('EVENING', 'Evening (04:00 PM - 07:00 PM)'),
    ]

    request_number = models.CharField(max_length=32, unique=True, db_index=True)
    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=30)
    customer_email = models.EmailField()
    pickup_address = models.TextField()
    pickup_city = models.CharField(max_length=100)
    preferred_date = models.DateField()
    preferred_time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES, default='MORNING')
    estimated_weight_kg = models.DecimalField(max_digits=6, decimal_places=2, default=1.0)
    package_description = models.TextField()
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='pickup_requests')
    assigned_courier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='courier_pickups')
    converted_parcel = models.OneToOneField(Parcel, on_delete=models.SET_NULL, null=True, blank=True, related_name='pickup_source')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Pickup {self.request_number} - {self.customer_name} ({self.get_status_display()})"

    @staticmethod
    def generate_request_number():
        date_str = timezone.now().strftime('%Y%m')
        rand_str = ''.join(random.choices('0123456789', k=4))
        return f"REQ-{date_str}-{rand_str}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self.generate_request_number()
        super().save(*args, **kwargs)


class CustomerInquiry(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]

    ticket_number = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    tracking_number = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    staff_reply = models.TextField(blank=True)
    replied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiry_replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Customer Inquiries'
        ordering = ['-created_at']

    def __str__(self):
        return f"Ticket {self.ticket_number} - {self.subject} ({self.get_status_display()})"

    @staticmethod
    def generate_ticket_number():
        rand_str = ''.join(random.choices('0123456789', k=6))
        return f"TCK-{rand_str}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        super().save(*args, **kwargs)
