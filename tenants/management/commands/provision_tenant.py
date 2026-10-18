from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from tenants.models import TenantPlan
from tenants.services import provision_tenant


class Command(BaseCommand):
    help = "CLI pipeline to provision an isolated multi-tenant courier organization."

    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, required=True, help="Enterprise / Company Name")
        parser.add_argument('--slug', type=str, required=False, default='', help="URL Slug / Subdomain")
        parser.add_argument('--prefix', type=str, required=True, help="Consignment Tracking Prefix (e.g. NHT, TWK)")
        parser.add_argument('--head-office', type=str, default='Nairobi', help="Head office hub terminal")
        parser.add_argument('--currency', type=str, default='KES', help="Currency ISO code (KES, USD, etc.)")
        parser.add_argument('--support-phone', type=str, default='+254 700 000000', help="Support hotline")
        parser.add_argument('--support-email', type=str, default='', help="Support email")
        parser.add_argument('--primary-color', type=str, default='#0d47a1', help="Primary brand hex color")
        parser.add_argument('--accent-color', type=str, default='#ff8f00', help="Accent brand hex color")
        parser.add_argument('--admin-username', type=str, default='', help="Client Super Admin username")
        parser.add_argument('--admin-phone', type=str, default='', help="Client Super Admin phone number")
        parser.add_argument('--admin-email', type=str, default='', help="Client Super Admin email")
        parser.add_argument('--admin-password', type=str, default='', help="Client Super Admin password (auto-generated if empty)")
        parser.add_argument(
            '--plan',
            type=str,
            default=TenantPlan.PROFESSIONAL,
            choices=[TenantPlan.STARTER, TenantPlan.PROFESSIONAL, TenantPlan.ENTERPRISE],
            help="Subscription tier plan"
        )
        parser.add_argument('--routes', type=str, default='', help="Comma-separated starter routes")

    def handle(self, *args, **options):
        routes_raw = options.get('routes', '')
        starter_routes = [r.strip() for r in routes_raw.split(',') if r.strip()] if routes_raw else None

        self.stdout.write(self.style.NOTICE(f"Provisioning client '{options['name']}'..."))

        try:
            result = provision_tenant(
                name=options['name'],
                slug=options['slug'],
                tracking_prefix=options['prefix'],
                head_office=options['head_office'],
                currency=options['currency'],
                support_phone=options['support_phone'],
                support_email=options['support_email'],
                admin_username=options['admin_username'],
                admin_phone=options['admin_phone'],
                admin_email=options['admin_email'],
                admin_password=options['admin_password'],
                plan=options['plan'],
                primary_color=options['primary_color'],
                accent_color=options['accent_color'],
                starter_routes=starter_routes
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            raise CommandError(f"Provisioning validation failed: {msg}")
        except Exception as e:
            raise CommandError(f"Provisioning failed: {e}")

        tenant = result['tenant']
        admin_user = result['admin_user']
        pwd = result['raw_password']

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(f"Client '{tenant.name}' provisioned successfully!"))
        self.stdout.write(self.style.SUCCESS(f"  Slug:            {tenant.slug}"))
        self.stdout.write(self.style.SUCCESS(f"  Tracking Prefix: {tenant.tracking_prefix}"))
        self.stdout.write(self.style.SUCCESS(f"  Plan:            {tenant.get_plan_display()}"))
        self.stdout.write(self.style.SUCCESS(f"  Max Users:       {tenant.max_users}"))
        self.stdout.write(self.style.SUCCESS(f"  Max Routes:      {tenant.max_routes}"))
        self.stdout.write(self.style.SUCCESS(f"  Admin Username:  {admin_user.username}"))
        self.stdout.write(self.style.SUCCESS(f"  Admin Password:  {pwd}"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
