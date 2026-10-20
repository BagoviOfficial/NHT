import secrets
import string
from decimal import Decimal
from django.db import transaction
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from audit.services import log_audit_event
from .models import Tenant, TenantPlan, TenantStatus

User = get_user_model()


def generate_secure_password(length: int = 12) -> str:
    """Generates a secure, human-manageable temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in pwd)
                and any(c.isupper() for c in pwd)
                and any(c.isdigit() for c in pwd)
                and any(c in "!@#$%^&*" for c in pwd)):
            return pwd


@transaction.atomic
def provision_tenant(
    name: str,
    slug: str,
    tracking_prefix: str,
    head_office: str = 'Nairobi',
    currency: str = 'KES',
    support_phone: str = '',
    support_email: str = '',
    admin_username: str = '',
    admin_first_name: str = '',
    admin_last_name: str = '',
    admin_phone: str = '',
    admin_email: str = '',
    admin_password: str = None,
    plan: str = TenantPlan.PROFESSIONAL,
    primary_color: str = '#0d47a1',
    accent_color: str = '#ff8f00',
    max_users: int = None,
    max_routes: int = None,
    starter_routes: list = None,
    actor=None,
    request=None
) -> dict:
    """
    Automated Tenant Provisioning Pipeline.
    Installs an isolated tenant company with administrative credentials,
    dynamic settings, default package categories, and optional routes.
    """
    # 1. Validation & normalization
    clean_name = name.strip()
    clean_slug = slugify(slug.strip()) if slug else slugify(clean_name)
    clean_prefix = tracking_prefix.strip().upper()

    if not clean_name:
        raise ValidationError("Company name is required.")
    if not clean_slug:
        raise ValidationError("A valid URL slug is required.")
    if not clean_prefix or len(clean_prefix) < 2 or len(clean_prefix) > 10:
        raise ValidationError("Tracking prefix must be between 2 and 10 uppercase characters (e.g. NHT, TWK).")

    if Tenant.objects.filter(slug=clean_slug).exists():
        raise ValidationError(f"A client with slug '{clean_slug}' is already installed.")
    if Tenant.objects.filter(tracking_prefix=clean_prefix).exists():
        raise ValidationError(f"A client with tracking prefix '{clean_prefix}' is already installed.")

    # Calculate default quotas by plan if not specified
    if max_users is None:
        if plan == TenantPlan.STARTER:
            max_users = 10
        elif plan == TenantPlan.ENTERPRISE:
            max_users = 500
        else:
            max_users = 50

    if max_routes is None:
        if plan == TenantPlan.STARTER:
            max_routes = 10
        elif plan == TenantPlan.ENTERPRISE:
            max_routes = 500
        else:
            max_routes = 50

    # 2. Create Tenant
    tenant = Tenant.objects.create(
        name=clean_name,
        slug=clean_slug,
        subdomain=clean_slug,
        tracking_prefix=clean_prefix,
        head_office=head_office.strip() or 'Nairobi',
        currency=currency.strip().upper() or 'KES',
        support_phone=support_phone.strip() or '+254 700 000000',
        support_email=support_email.strip() or f"info@{clean_slug}.co.ke",
        primary_color=primary_color.strip() or '#0d47a1',
        accent_color=accent_color.strip() or '#ff8f00',
        max_users=max_users,
        max_routes=max_routes,
        plan=plan,
        status=TenantStatus.ACTIVE,
        is_active=True
    )

    # 3. Create Client Super Admin
    if not admin_username:
        admin_username = f"{clean_slug}_admin"
    if not admin_phone:
        admin_phone = f"07{secrets.randbelow(89999999) + 10000000}"
    if not admin_email:
        admin_email = f"admin@{clean_slug}.co.ke"

    raw_password = admin_password.strip() if admin_password else generate_secure_password(12)

    # Ensure collision-free unique administrator username and phone
    while User.objects.filter(username=admin_username).exists():
        admin_username = f"{admin_username}_{secrets.randbelow(999)}"

    while User.objects.filter(phone=admin_phone).exists():
        admin_phone = f"07{secrets.randbelow(89999999) + 10000000}"

    from accounts.models import Role
    admin_user = User(
        username=admin_username,
        first_name=admin_first_name.strip() or 'Company',
        last_name=admin_last_name.strip() or 'Admin',
        phone=admin_phone.strip(),
        email=admin_email.strip(),
        role=Role.SUPER_ADMIN,
        tenant=tenant,
        is_staff=True,
        is_superuser=False
    )
    admin_user.set_password(raw_password)
    admin_user.save()

    # 4. Provision Starter Routes if provided
    from routes.models import Route
    if starter_routes is None:
        starter_routes = [
            f"{clean_name} Branch 1",
            f"{clean_name} Branch 2"
        ]

    for route_name in starter_routes:
        r_name = route_name.strip()
        if r_name:
            Route.objects.create(
                tenant=tenant,
                name=r_name,
                origin=tenant.head_office,
                description=f"Initial route for {tenant.name}",
                is_active=True
            )

    # 5. Provision Choice & Field Configurations for Tenant
    from core.models import ChoiceConfig, FieldConfig
    default_choices = [
        ('wrap_type', 'Box', 'Box', True, 1),
        ('wrap_type', 'Sack', 'Sack', False, 2),
        ('wrap_type', 'Carton', 'Carton', False, 3),
        ('wrap_type', 'Envelope', 'Envelope', False, 4),
        ('wrap_type', 'Bundle', 'Bundle', False, 5),
        ('wrap_type', 'Crate', 'Crate', False, 6),
        ('wrap_type', 'Drum', 'Drum', False, 7),
        ('payment_method', 'CASH', 'Cash', True, 1),
        ('payment_method', 'MPESA', 'M-Pesa', False, 2),
        ('payment_status', 'PAID', 'Paid', True, 1),
        ('payment_status', 'COD', 'Cash on Delivery (Pending)', False, 2),
        ('payment_status', 'UNPAID', 'Unpaid', False, 3),
    ]
    for cat, k, lbl, is_def, ord_n in default_choices:
        ChoiceConfig.objects.create(
            tenant=tenant,
            category=cat,
            key=k,
            label=lbl,
            is_default=is_def,
            order=ord_n,
            is_active=True
        )

    default_fields = [
        ('sender_name', 'Sender Full Name', 'Enter sender full name', '', True, True, 1),
        ('sender_phone', 'Sender Phone Number', '+254 7...', 'Kenyan mobile phone number', True, True, 2),
        ('receiver_name', 'Receiver Full Name', 'Enter receiver full name', '', True, True, 3),
        ('receiver_phone', 'Receiver Phone Number', '+254 7...', 'Kenyan mobile phone number', True, True, 4),
        ('receiver_id_number', 'Receiver ID / Passport', 'National ID Number', 'Required for collection verification', True, True, 5),
        ('truck_plate_number', 'Bus / Truck Plate Number', 'e.g. KDC 123A', 'Assigned vehicle upon dispatch', False, True, 6),
        ('driver_name', 'Driver Full Name', 'Full name of driver', 'Assigned driver upon dispatch', False, True, 7),
        ('item_description', 'Item Description', 'Describe contents of parcel', '', True, True, 8),
        ('wrap_type', 'Wrap / Package Type', '', 'Select or specify packaging', True, True, 9),
        ('quantity', 'Quantity', '1', 'Number of units', True, True, 10),
        ('unit_price', f'Unit Price ({tenant.currency})', '0.00', 'Charge per item unit', True, True, 11),
    ]
    for key, lbl, ph, hlp, req, vis, ord_n in default_fields:
        FieldConfig.objects.create(
            tenant=tenant,
            field_key=key,
            label=lbl,
            placeholder=ph,
            help_text=hlp,
            is_required=req,
            is_visible=vis,
            order=ord_n,
            is_active=True
        )

    # 6. Audit Logging
    log_audit_event(
        actor=actor,
        action='TENANT_PROVISION',
        object_type='Tenant',
        object_identifier=str(tenant.slug),
        new_values={
            'tenant_name': tenant.name,
            'slug': tenant.slug,
            'tracking_prefix': tenant.tracking_prefix,
            'admin_username': admin_user.username,
            'plan': tenant.plan
        },
        reason=f"Installed new client '{tenant.name}' via SaaS Master Dashboard",
        request=request,
        tenant=tenant
    )

    return {
        'tenant': tenant,
        'admin_user': admin_user,
        'raw_password': raw_password
    }
