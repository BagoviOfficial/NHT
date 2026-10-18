from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class TenantPlan(models.TextChoices):
    STARTER = 'STARTER', _('Starter (Up to 10 Users)')
    PROFESSIONAL = 'PROFESSIONAL', _('Professional (Up to 50 Users)')
    ENTERPRISE = 'ENTERPRISE', _('Enterprise (Unlimited)')


class TenantStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Active')
    TRIAL = 'TRIAL', _('Trial')
    SUSPENDED = 'SUSPENDED', _('Suspended')
    INACTIVE = 'INACTIVE', _('Inactive')


class Tenant(models.Model):
    """
    Core Tenant (Client Company / Organization) entity for Multi-Tenant SaaS.
    Represents an independent courier/transport enterprise with isolated
    users, routes, parcels, receipts, and settings.
    """
    name = models.CharField(
        max_length=150,
        help_text=_("Company or Business Name, e.g. Northern Highways Transporters")
    )
    slug = models.SlugField(
        max_length=60,
        unique=True,
        db_index=True,
        help_text=_("Unique identifier used for subdomains or path routing (e.g. nht, tawakal)")
    )
    subdomain = models.CharField(
        max_length=60,
        unique=True,
        blank=True,
        db_index=True,
        help_text=_("Custom subdomain (defaults to slug)")
    )
    custom_domain = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text=_("Optional white-label custom domain (e.g. parcels.client.com)")
    )
    tracking_prefix = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        help_text=_("Prefix for consignment tracking codes (e.g. NHT, TWK, MOY)")
    )
    head_office = models.CharField(
        max_length=100,
        default='Nairobi',
        help_text=_("Central origin hub/terminal (e.g. Nairobi, Mombasa)")
    )
    currency = models.CharField(
        max_length=10,
        default='KES',
        help_text=_("ISO Currency Code (e.g. KES, USD, TZS, UGX)")
    )
    support_phone = models.CharField(
        max_length=50,
        blank=True,
        default='+254 700 000000',
        help_text=_("Customer care phone hotline")
    )
    support_email = models.EmailField(
        blank=True,
        default='support@example.com',
        help_text=_("Support contact email")
    )
    receipt_header = models.TextField(
        blank=True,
        help_text=_("Header text printed on 80mm thermal receipts")
    )
    receipt_footer = models.TextField(
        blank=True,
        help_text=_("Footer text and terms printed on 80mm thermal receipts")
    )
    about_text = models.TextField(
        blank=True,
        help_text=_("Public company overview displayed on tracking and portal pages")
    )
    help_text = models.TextField(
        blank=True,
        help_text=_("Customer care and tracking guidance notes")
    )
    plan = models.CharField(
        max_length=30,
        choices=TenantPlan.choices,
        default=TenantPlan.PROFESSIONAL,
        db_index=True
    )
    status = models.CharField(
        max_length=30,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE,
        db_index=True
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Designates whether this client's portal is actively accessible.")
    )
    primary_color = models.CharField(
        max_length=20,
        default='#0d47a1',
        help_text=_("Primary brand color (hex code, e.g. #0d47a1)")
    )
    accent_color = models.CharField(
        max_length=20,
        default='#ff8f00',
        help_text=_("Accent brand color (hex code, e.g. #ff8f00)")
    )
    allow_superuser_edit_after_dispatch = models.BooleanField(
        default=False,
        help_text=_("If enabled, Client Super Admin may edit parcels after dispatch with audit reason.")
    )
    tracking_rate_limit_per_minute = models.PositiveIntegerField(
        default=60,
        help_text=_("Rate limit for public consignment tracking requests.")
    )
    max_users = models.PositiveIntegerField(
        default=50,
        help_text=_("Maximum staff accounts permitted under this tenant's tier.")
    )
    max_routes = models.PositiveIntegerField(
        default=50,
        help_text=_("Maximum destination routes permitted.")
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Tenant / Client')
        verbose_name_plural = _('Tenants / Clients')

    def __str__(self):
        return f"{self.name} [{self.tracking_prefix}]"

    def clean(self):
        if self.tracking_prefix:
            self.tracking_prefix = self.tracking_prefix.strip().upper()
        if self.slug:
            self.slug = slugify(self.slug)
        if not self.subdomain and self.slug:
            self.subdomain = self.slug
        if self.primary_color:
            self.primary_color = self.primary_color.strip()
        if self.accent_color:
            self.accent_color = self.accent_color.strip()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.subdomain:
            self.subdomain = self.slug
        if self.tracking_prefix:
            self.tracking_prefix = self.tracking_prefix.strip().upper()
        if not self.receipt_header:
            self.receipt_header = f"{self.name.upper()}\nParcel & Cargo Logistics Express\nHead Office: {self.head_office}"
        if not self.receipt_footer:
            self.receipt_footer = f"Thank you for choosing {self.name}.\nGoods received in good condition.\nLuggage stored at owner's risk after 48 hours."
        
        # Default quotas by tier if not custom set
        if not self.pk:
            if self.plan == TenantPlan.STARTER and self.max_users == 50:
                self.max_users = 10
                self.max_routes = 10
            elif self.plan == TenantPlan.ENTERPRISE and self.max_users == 50:
                self.max_users = 500
                self.max_routes = 500

        super().save(*args, **kwargs)

    @property
    def admin_user(self):
        """Returns the primary Super Admin user for this tenant."""
        return self.users.filter(role='SUPER_ADMIN').first() or self.users.first()

    @property
    def total_parcels(self):
        return self.parcels.count()

    @property
    def total_revenue(self):
        from django.db.models import Sum
        val = self.parcels.aggregate(total=Sum('price'))['total']
        return val or Decimal('0.00')

    @property
    def total_users(self):
        return self.users.count()

    @property
    def total_routes(self):
        return self.routes.count()

    @property
    def user_quota_pct(self):
        """Percentage of user quota consumed."""
        if not self.max_users:
            return 0
        return min(100, int((self.total_users / self.max_users) * 100))

    @property
    def route_quota_pct(self):
        """Percentage of route quota consumed."""
        if not self.max_routes:
            return 0
        return min(100, int((self.total_routes / self.max_routes) * 100))

    @property
    def is_user_quota_reached(self):
        return self.total_users >= self.max_users

    @property
    def is_route_quota_reached(self):
        return self.total_routes >= self.max_routes
