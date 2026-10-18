import sys
from django.core.management.base import BaseCommand, CommandError
from installer.utils import (
    is_system_installed,
    get_system_readiness_checks,
    execute_wordpress_style_installation,
    get_lock_file,
)
from tenants.models import TenantPlan


class Command(BaseCommand):
    help = "WordPress-Style Automated System Installer (WP-CLI Core Install Equivalent)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--platform-title',
            default="Northern Highways Transporters — Cloud PMS",
            help="Global Platform Installation Title"
        )
        parser.add_argument(
            '--admin-username',
            default="platform_admin",
            help="Global Platform Super Admin Username"
        )
        parser.add_argument(
            '--admin-password',
            default="Admin@NHT2026!",
            help="Global Platform Super Admin Password"
        )
        parser.add_argument(
            '--admin-phone',
            default="0700000001",
            help="Global Super Admin Phone Number"
        )
        parser.add_argument(
            '--admin-email',
            default="admin@northernhighways.co.ke",
            help="Global Super Admin Email Address"
        )
        parser.add_argument(
            '--company-name',
            default="Northern Highways Transporters",
            help="Primary Client Courier Organization Name"
        )
        parser.add_argument(
            '--tracking-prefix',
            default="NHT",
            help="Primary Tracking Number Prefix (2-10 letters)"
        )
        parser.add_argument(
            '--slug',
            default="nht",
            help="Primary Organization Subdomain / Slug"
        )
        parser.add_argument(
            '--head-office',
            default="Nairobi",
            help="Central Origin Terminal Hub"
        )
        parser.add_argument(
            '--currency',
            default="KES",
            help="Operating Currency ISO code"
        )
        parser.add_argument(
            '--primary-color',
            default="#0d47a1",
            help="Brand Primary Color Hex"
        )
        parser.add_argument(
            '--accent-color',
            default="#ff8f00",
            help="Brand Accent Color Hex"
        )
        parser.add_argument(
            '--starter-routes',
            default="Garissa, Wajir, Kotulo Drop-off, Elwak, Rhamu, Lafey, Arabia, Mandera",
            help="Comma-separated starter route network"
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help="Force installation even if lock file or records exist"
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 68))
        self.stdout.write(self.style.MIGRATE_HEADING("  PARCEL MANAGEMENT SYSTEM — WORDPRESS-STYLE INSTALLER"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 68))

        # Check existing installation lock
        if is_system_installed() and not options['force']:
            self.stdout.write(self.style.WARNING(
                "\n[!] System is already installed. The installer is locked for security.\n"
                "    To re-run the setup pipeline, pass the --force flag."
            ))
            return

        if options['force']:
            lock = get_lock_file()
            if lock.exists():
                try:
                    lock.unlink()
                    self.stdout.write(self.style.NOTICE("[*] Existing .installed lock file cleared (--force active)."))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"[!] Warning: Could not remove lock file: {e}"))

        # Pre-flight diagnostics
        if not options['skip_checks']:
            self.stdout.write("\nRunning pre-flight environment diagnostics...")
            readiness = get_system_readiness_checks()
            for c in readiness['checks']:
                status = self.style.SUCCESS("[PASS]") if c['passed'] else self.style.ERROR("[FAIL]")
                self.stdout.write(f"  {status} {c['name']}: {c['current']}")
            if not readiness['all_passed'] and not options['force']:
                raise CommandError(
                    "Pre-flight environment diagnostics failed. Please resolve the issues above or run with --force."
                )

        # Parse starter routes
        routes_raw = options['starter_routes']
        starter_routes = [r.strip() for r in routes_raw.split(',') if r.strip()] if routes_raw else None

        self.stdout.write("\nApplying database migrations and provisioning platform...")
        try:
            result = execute_wordpress_style_installation(
                platform_title=options['platform_title'],
                admin_username=options['admin_username'],
                admin_password=options['admin_password'],
                admin_phone=options['admin_phone'],
                admin_email=options['admin_email'],
                tenant_name=options['company_name'],
                tenant_prefix=options['tracking_prefix'],
                tenant_slug=options['slug'],
                head_office=options['head_office'],
                currency=options['currency'],
                primary_color=options['primary_color'],
                accent_color=options['accent_color'],
                starter_routes=starter_routes,
            )
        except Exception as e:
            raise CommandError(f"Installation failed: {e}")

        # Summary
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 68))
        self.stdout.write(self.style.SUCCESS("  SUCCESS! INSTALLATION COMPLETE"))
        self.stdout.write(self.style.SUCCESS("=" * 68))
        self.stdout.write(f"  Platform Title:   {options['platform_title']}")
        self.stdout.write(f"  Global Superuser: {result['platform_admin'].username}")
        self.stdout.write(f"  Password:         {result['raw_password']}")
        self.stdout.write(f"  Email:            {result['platform_admin'].email}")
        self.stdout.write(f"  Phone:            {result['platform_admin'].phone}")
        self.stdout.write("-" * 68)
        self.stdout.write(f"  Primary Tenant:   {result['primary_tenant'].name}")
        self.stdout.write(f"  Prefix:           {result['primary_tenant'].tracking_prefix}")
        self.stdout.write(f"  Tenant Admin:     {result['tenant_admin'].username}")
        self.stdout.write(f"  Head Office:      {result['primary_tenant'].head_office}")
        self.stdout.write(f"  Currency:         {result['primary_tenant'].currency}")
        self.stdout.write("=" * 68)
        self.stdout.write(self.style.NOTICE("Security lock file (.installed) engaged. Web installer locked.\n"))
