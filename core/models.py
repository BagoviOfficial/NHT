from django.db import models
from django.core.cache import cache
from django.core.exceptions import ValidationError

ALLOWED_FIELD_KEYS = [
    ('sender_name', 'Sender Full Name'),
    ('sender_phone', 'Sender Phone Number'),
    ('receiver_name', 'Receiver Full Name'),
    ('receiver_phone', 'Receiver Phone Number'),
    ('receiver_id_number', 'Receiver ID / Passport Number'),
    ('truck_plate_number', 'Truck Registration Plate'),
    ('driver_name', 'Driver Full Name'),
    ('item_description', 'Item Description'),
    ('wrap_type', 'Wrap / Packaging Type'),
    ('quantity', 'Quantity'),
    ('unit_price', 'Unit Price'),
]

ALLOWED_CHOICE_CATEGORIES = [
    ('wrap_type', 'Wrap / Package Types'),
    ('payment_method', 'Payment Methods'),
    ('payment_status', 'Payment Statuses'),
]


class SiteSettings(models.Model):
    """
    Tenant-specific or Global company and operational configuration.
    """
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='site_settings'
    )
    company_name = models.CharField(max_length=150, default='Northern Highways Transporters')
    currency = models.CharField(max_length=10, default='KES', help_text="ISO Currency Code (e.g. KES, USD)")
    head_office = models.CharField(max_length=100, default='Nairobi', help_text="Central origin terminal")
    support_phone = models.CharField(max_length=50, default='+254 700 000000')
    support_email = models.EmailField(default='support@northernhighways.co.ke')
    receipt_header = models.TextField(
        default="NORTHERN HIGHWAYS TRANSPORTERS\nParcel & Courier Express Services\nHead Office: Nairobi, Kenya",
        help_text="Header lines printed at top of thermal receipt"
    )
    receipt_footer = models.TextField(
        default="Thank you for choosing Northern Highways Transporters.\nGoods received in good order.\nLuggage stored at owner's risk after 48 hours.",
        help_text="Terms and footer printed at bottom of receipt"
    )
    about_text = models.TextField(
        default="Northern Highways Transporters provides safe, fast, and dependable bus parcel and cargo logistics between Nairobi and Northern Kenya routes including Garissa, Wajir, Kotulo, Elwak, Rhamu, Lafey, Arabia, and Mandera.",
        help_text="Public company overview"
    )
    help_text = models.TextField(
        default="For customer care, rate inquiries, or parcel tracking assistance, please call our 24/7 hotline or visit any of our branch booking offices.",
        help_text="Support guidance shown on tracking and help pages"
    )
    allow_superuser_edit_after_dispatch = models.BooleanField(
        default=False,
        help_text="If enabled, Super Admin may modify parcel data after dispatch with mandatory audit reason."
    )
    tracking_rate_limit_per_minute = models.PositiveIntegerField(
        default=30,
        help_text="Maximum public tracking requests allowed per minute per IP address."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f"{self.company_name} ({self.tenant.slug if self.tenant else 'Global'})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.tenant_id:
            cache.delete(f'site_settings_tenant_{self.tenant_id}')
        cache.delete('site_settings_cache')

    @classmethod
    def load(cls, tenant=None):
        if tenant:
            cache_key = f'site_settings_tenant_{tenant.pk}'
            obj = cache.get(cache_key)
            if obj is None:
                obj = cls.objects.filter(tenant=tenant).first()
                if not obj:
                    obj, _ = cls.objects.get_or_create(
                        tenant=tenant,
                        defaults={
                            'company_name': tenant.name,
                            'currency': tenant.currency,
                            'head_office': tenant.head_office,
                            'support_phone': tenant.support_phone,
                            'support_email': tenant.support_email,
                            'receipt_header': tenant.receipt_header,
                            'receipt_footer': tenant.receipt_footer,
                            'about_text': tenant.about_text,
                            'help_text': tenant.help_text,
                            'allow_superuser_edit_after_dispatch': tenant.allow_superuser_edit_after_dispatch,
                            'tracking_rate_limit_per_minute': tenant.tracking_rate_limit_per_minute,
                        }
                    )
                cache.set(cache_key, obj, timeout=3600)
            return obj
        else:
            obj = cache.get('site_settings_cache')
            if obj is None:
                obj = cls.objects.filter(tenant=None).first() or cls.objects.first()
                if not obj:
                    obj = cls.objects.create()
                cache.set('site_settings_cache', obj, timeout=3600)
            return obj


class FieldConfig(models.Model):
    """
    Configurable form field metadata per Tenant. Strictly maps to safe whitelisted keys.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='field_configs'
    )
    field_key = models.CharField(
        max_length=50,
        choices=ALLOWED_FIELD_KEYS,
        help_text="Predefined system field key."
    )
    label = models.CharField(max_length=100)
    placeholder = models.CharField(max_length=150, blank=True)
    help_text = models.CharField(max_length=255, blank=True)
    is_required = models.BooleanField(default=True)
    is_visible = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'field_key']
        verbose_name = 'Field Configuration'
        verbose_name_plural = 'Field Configurations'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'field_key'], name='unique_tenant_field_config')
        ]

    def __str__(self):
        return f"{self.get_field_key_display()} ({self.label})"

    def clean(self):
        valid_keys = [k[0] for k in ALLOWED_FIELD_KEYS]
        if self.field_key not in valid_keys:
            raise ValidationError({'field_key': f"Field key '{self.field_key}' is not allowed."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if self.tenant_id:
            cache.delete(f'field_configs_cache_tenant_{self.tenant_id}')
        cache.delete('field_configs_cache')


class ChoiceConfig(models.Model):
    """
    Configurable choices for select/dropdown fields per Tenant.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='choice_configs'
    )
    category = models.CharField(
        max_length=50,
        choices=ALLOWED_CHOICE_CATEGORIES,
        db_index=True,
        help_text="Choice category."
    )
    key = models.CharField(max_length=50, help_text="Internal value stored in database.")
    label = models.CharField(max_length=100, help_text="User-facing label displayed in forms.")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['category', 'order', 'label']
        verbose_name = 'Choice Configuration'
        verbose_name_plural = 'Choice Configurations'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'category', 'key'], name='unique_tenant_choice_config')
        ]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.label} ({self.key})"

    def clean(self):
        valid_cats = [c[0] for c in ALLOWED_CHOICE_CATEGORIES]
        if self.category not in valid_cats:
            raise ValidationError({'category': f"Category '{self.category}' is not allowed."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_default:
            ChoiceConfig.objects.filter(
                tenant=self.tenant,
                category=self.category,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
        if self.tenant_id:
            cache.delete(f'choice_configs_{self.tenant_id}_{self.category}')
        cache.delete(f'choice_configs_{self.category}')
