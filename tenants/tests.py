from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import PermissionDenied, ValidationError
from accounts.models import User, Role
from routes.models import Route
from parcels.models import Parcel, ShipmentItem, ParcelStatus, PaymentStatus, PaymentMethod
from parcels.services import create_parcel
from parcels.selectors import get_parcels_for_user, can_user_access_parcel
from tenants.models import Tenant, TenantPlan, TenantStatus
from tenants.services import provision_tenant


class SaaSMultiTenantTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Platform Super Administrator (No tenant)
        self.platform_admin = User.objects.create_superuser(
            username='platform_owner',
            password='OwnerPassword123!',
            phone='0700000001'
        )

        # 2. Client 1: Northern Highways Transporters
        self.tenant_1, _ = Tenant.objects.get_or_create(
            slug='nht',
            defaults={
                'name': 'Northern Highways Transporters',
                'subdomain': 'nht',
                'tracking_prefix': 'NHT',
                'head_office': 'Nairobi',
                'currency': 'KES',
                'is_active': True
            }
        )
        self.admin_1 = User.objects.create_user(
            username='nht_admin',
            password='Password123!',
            phone='0700000002',
            role=Role.SUPER_ADMIN,
            tenant=self.tenant_1,
            is_staff=True
        )
        self.clerk_1 = User.objects.create_user(
            username='nht_clerk',
            password='Password123!',
            phone='0700000003',
            role=Role.COUNTER_STAFF,
            tenant=self.tenant_1
        )
        self.route_1 = Route.objects.create(
            tenant=self.tenant_1,
            name='Garissa',
            origin='Nairobi',
            is_active=True
        )

        # 3. Client 2: Tawakal Express
        self.tenant_2 = Tenant.objects.create(
            name='Tawakal Express',
            slug='tawakal',
            subdomain='tawakal',
            tracking_prefix='TWK',
            head_office='Mombasa',
            currency='USD',
            is_active=True
        )
        self.admin_2 = User.objects.create_user(
            username='twk_admin',
            password='Password123!',
            phone='0700000004',
            role=Role.SUPER_ADMIN,
            tenant=self.tenant_2,
            is_staff=True
        )
        self.clerk_2 = User.objects.create_user(
            username='twk_clerk',
            password='Password123!',
            phone='0700000005',
            role=Role.COUNTER_STAFF,
            tenant=self.tenant_2
        )
        self.route_2 = Route.objects.create(
            tenant=self.tenant_2,
            name='Lamu',
            origin='Mombasa',
            is_active=True
        )

    def test_tenant_creation_and_properties(self):
        """Test Tenant model properties and defaults."""
        self.assertEqual(str(self.tenant_1), "Northern Highways Transporters [NHT]")
        self.assertEqual(self.tenant_1.total_parcels, 0)
        self.assertEqual(self.tenant_1.total_users, 2)
        self.assertEqual(self.tenant_1.total_routes, 1)

    def test_automated_provisioning_service(self):
        """Test installing a new client via provision_tenant pipeline."""
        result = provision_tenant(
            name="Moyale Fast Cargo",
            slug="moyale",
            tracking_prefix="MOY",
            head_office="Nairobi HQ",
            currency="KES",
            support_phone="0711999888",
            support_email="info@moyale.co.ke",
            admin_username="moyale_super",
            admin_phone="0711999889",
            admin_email="admin@moyale.co.ke",
            starter_routes=["Moyale Town", "Marsabit Branch"]
        )

        tenant = result['tenant']
        admin_user = result['admin_user']
        raw_password = result['raw_password']

        self.assertEqual(tenant.name, "Moyale Fast Cargo")
        self.assertEqual(tenant.slug, "moyale")
        self.assertEqual(tenant.tracking_prefix, "MOY")
        self.assertEqual(admin_user.username, "moyale_super")
        self.assertEqual(admin_user.role, Role.SUPER_ADMIN)
        self.assertEqual(admin_user.tenant, tenant)
        self.assertTrue(admin_user.check_password(raw_password))

        # Check starter routes
        routes = Route.objects.filter(tenant=tenant)
        self.assertEqual(routes.count(), 2)
        self.assertTrue(routes.filter(name="Moyale Town").exists())

    def test_tracking_prefix_per_tenant(self):
        """Verify that parcels inherit the client's distinct tracking prefix."""
        parcel_1 = create_parcel(
            route=self.route_1,
            sender_name="Alice",
            sender_phone="0711000001",
            receiver_name="Bob",
            receiver_phone="0711000002",
            receiver_id_number="12345678",
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Electronics', 'quantity': 1, 'unit_price': '500.00'}],
            created_by=self.clerk_1,
            tenant=self.tenant_1
        )
        self.assertTrue(parcel_1.tracking_number.startswith("NHT-"))
        self.assertEqual(parcel_1.tenant, self.tenant_1)

        parcel_2 = create_parcel(
            route=self.route_2,
            sender_name="Charlie",
            sender_phone="0722000001",
            receiver_name="David",
            receiver_phone="0722000002",
            receiver_id_number="87654321",
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Fragile Goods', 'quantity': 2, 'unit_price': '300.00'}],
            created_by=self.clerk_2,
            tenant=self.tenant_2
        )
        self.assertTrue(parcel_2.tracking_number.startswith("TWK-"))
        self.assertEqual(parcel_2.tenant, self.tenant_2)

    def test_strict_multi_tenant_data_isolation(self):
        """Verify that Client A cannot access or see Client B's parcels."""
        parcel_1 = create_parcel(
            route=self.route_1,
            sender_name="Sender 1",
            sender_phone="0711000001",
            receiver_name="Receiver 1",
            receiver_phone="0711000002",
            receiver_id_number="11111111",
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Box A', 'quantity': 1, 'unit_price': '200.00'}],
            created_by=self.clerk_1,
            tenant=self.tenant_1
        )

        parcel_2 = create_parcel(
            route=self.route_2,
            sender_name="Sender 2",
            sender_phone="0722000001",
            receiver_name="Receiver 2",
            receiver_phone="0722000002",
            receiver_id_number="22222222",
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Box B', 'quantity': 1, 'unit_price': '400.00'}],
            created_by=self.clerk_2,
            tenant=self.tenant_2
        )

        # Clerk 1 (Client 1) sees only Client 1 parcels
        clerk_1_parcels = get_parcels_for_user(self.clerk_1)
        self.assertIn(parcel_1, clerk_1_parcels)
        self.assertNotIn(parcel_2, clerk_1_parcels)

        # Admin 1 (Client 1 Super Admin) sees only Client 1 parcels
        admin_1_parcels = get_parcels_for_user(self.admin_1)
        self.assertIn(parcel_1, admin_1_parcels)
        self.assertNotIn(parcel_2, admin_1_parcels)

        # Clerk 2 (Client 2) sees only Client 2 parcels
        clerk_2_parcels = get_parcels_for_user(self.clerk_2)
        self.assertNotIn(parcel_1, clerk_2_parcels)
        self.assertIn(parcel_2, clerk_2_parcels)

        # IDOR protection: Clerk 1 attempting to access Parcel 2 directly is forbidden
        self.assertTrue(can_user_access_parcel(self.clerk_1, parcel_1))
        self.assertFalse(can_user_access_parcel(self.clerk_1, parcel_2))
        self.assertFalse(can_user_access_parcel(self.admin_1, parcel_2))

    def test_saas_dashboard_authorization(self):
        """Verify that only SaaS Platform Owners can access the SaaS Master Dashboard."""
        # Unauthenticated: redirects to login
        response = self.client.get(reverse('saas_dashboard'))
        self.assertEqual(response.status_code, 302)

        # Client Admin (Non-platform superuser): Forbidden (403)
        self.client.login(username='nht_admin', password='Password123!')
        response = self.client.get(reverse('saas_dashboard'))
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # Platform Super Admin: OK (200)
        self.client.login(username='platform_owner', password='OwnerPassword123!')
        response = self.client.get(reverse('saas_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Platform Client Dashboard")
        self.assertContains(response, "Northern Highways Transporters")
        self.assertContains(response, "Tawakal Express")

    def test_install_client_via_saas_dashboard(self):
        """Test submitting the Install Client form from the SaaS Master Dashboard."""
        self.client.login(username='platform_owner', password='OwnerPassword123!')

        # GET install page
        response = self.client.get(reverse('saas_install_client'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Install & Provision New Client")

        # POST new client
        post_data = {
            'name': 'Coastline Bus Cargo',
            'slug': 'coastline',
            'tracking_prefix': 'CBC',
            'head_office': 'Mombasa Central',
            'currency': 'KES',
            'support_phone': '0711333444',
            'support_email': 'support@coastline.co.ke',
            'plan': TenantPlan.PROFESSIONAL,
            'admin_username': 'coastline_admin',
            'admin_first_name': 'Ali',
            'admin_last_name': 'Bakari',
            'admin_phone': '0711333445',
            'admin_email': 'ali@coastline.co.ke',
            'admin_password': 'CoastPassword123!',
            'starter_routes': 'Kilifi, Malindi, Lamu'
        }
        response = self.client.post(reverse('saas_install_client'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client Installed Successfully!")
        self.assertContains(response, "Coastline Bus Cargo")
        self.assertContains(response, "coastline_admin")

        # Verify tenant exists
        coastline = Tenant.objects.filter(slug='coastline').first()
        self.assertIsNotNone(coastline)
        self.assertEqual(coastline.tracking_prefix, 'CBC')
        self.assertEqual(coastline.routes.count(), 3)

    def test_saas_switch_tenant_workspace(self):
        """Test switching active client workspace session for platform owner."""
        self.client.login(username='platform_owner', password='OwnerPassword123!')

        # Switch to Tenant 2 (Tawakal)
        response = self.client.get(reverse('saas_switch_tenant', args=[self.tenant_2.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['active_tenant_id'], self.tenant_2.id)

        # Visiting dashboard should show Tawakal workspace
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        # Exit workspace
        response = self.client.get(reverse('saas_exit_tenant'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('active_tenant_id', self.client.session)

    def test_tenant_suspension_blocks_access(self):
        """Test that deactivating/suspending a tenant stops non-platform access."""
        self.tenant_2.status = TenantStatus.SUSPENDED
        self.tenant_2.is_active = False
        self.tenant_2.save()

        # Clerk 2 login and access
        self.client.login(username='twk_clerk', password='Password123!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Portal Temporarily Unavailable", status_code=403)

    def test_user_quota_enforcement(self):
        """Verify that staff creation respects the tenant's max_users quota."""
        self.tenant_1.max_users = 2
        self.tenant_1.save()

        # Tenant 1 already has admin_1 and clerk_1 (2 users). Attempting to add a 3rd user must be rejected.
        self.client.login(username='nht_admin', password='Password123!')
        post_data = {
            'username': 'nht_excess_clerk',
            'first_name': 'Excess',
            'last_name': 'Clerk',
            'phone': '0700000099',
            'email': 'excess@nht.co.ke',
            'role': Role.COUNTER_STAFF,
            'password': 'Password123!',
            'is_active': True
        }
        response = self.client.post(reverse('user_create'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff account quota reached")
        self.assertFalse(User.objects.filter(username='nht_excess_clerk').exists())

    def test_route_quota_enforcement(self):
        """Verify that transit route creation respects the tenant's max_routes quota."""
        self.tenant_1.max_routes = 1
        self.tenant_1.save()

        # Tenant 1 already has route_1 (1 route). Attempting to add a 2nd route must be rejected.
        self.client.login(username='nht_admin', password='Password123!')
        post_data = {
            'name': 'Mandera Express Route',
            'origin': 'Nairobi',
            'is_active': True
        }
        response = self.client.post(reverse('route_create'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Route quota reached")
        self.assertFalse(Route.objects.filter(name='Mandera Express Route', tenant=self.tenant_1).exists())

    def test_audit_log_tenant_isolation(self):
        """Ensure Client Super Admins can only view their own organization's audit entries."""
        from audit.models import AuditLog

        log_1 = AuditLog.objects.create(
            actor=self.admin_1,
            tenant=self.tenant_1,
            action='TENANT1_SENSITIVE_OP',
            reason='Tenant 1 Private Event'
        )
        log_2 = AuditLog.objects.create(
            actor=self.admin_2,
            tenant=self.tenant_2,
            action='TENANT2_SENSITIVE_OP',
            reason='Tenant 2 Private Event'
        )

        # Admin 1 views audit log
        self.client.login(username='nht_admin', password='Password123!')
        response = self.client.get(reverse('admin_panel_audit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TENANT1_SENSITIVE_OP')
        self.assertNotContains(response, 'TENANT2_SENSITIVE_OP')
        self.client.logout()

        # Platform Super Admin views audit log (global view sees both)
        self.client.login(username='platform_owner', password='OwnerPassword123!')
        response = self.client.get(reverse('admin_panel_audit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TENANT1_SENSITIVE_OP')
        self.assertContains(response, 'TENANT2_SENSITIVE_OP')

    def test_cross_tenant_idor_prevention(self):
        """Verify strict authorization preventing cross-tenant manipulation of users & parcels."""
        parcel_2 = create_parcel(
            route=self.route_2,
            sender_name="Charlie",
            sender_phone="0722000001",
            receiver_name="David",
            receiver_phone="0722000002",
            receiver_id_number="87654321",
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Electronics', 'quantity': 1, 'unit_price': '500.00'}],
            created_by=self.clerk_2,
            tenant=self.tenant_2
        )

        # 1. Admin 1 cannot toggle active state of Clerk 2 (Tenant 2)
        self.client.login(username='nht_admin', password='Password123!')
        response = self.client.post(reverse('user_toggle_active', args=[self.clerk_2.pk]))
        self.assertEqual(response.status_code, 403)

        # 2. Admin 1 cannot reset password of Clerk 2 (Tenant 2)
        response = self.client.post(reverse('user_password_reset', args=[self.clerk_2.pk]), {
            'new_password': 'HackedPassword123!',
            'confirm_password': 'HackedPassword123!'
        })
        self.assertEqual(response.status_code, 403)

        # 3. Clerk 1 cannot dispatch Parcel 2 (Tenant 2)
        self.client.login(username='nht_clerk', password='Password123!')
        response = self.client.post(reverse('parcel_dispatch', args=[parcel_2.tracking_number]), {
            'truck_plate_number': 'KBZ 123A',
            'driver_name': 'Ali Driver'
        })
        self.assertEqual(response.status_code, 403)

        # 4. Clerk 1 cannot cancel Parcel 2 (Tenant 2)
        self.client.login(username='nht_admin', password='Password123!')
        response = self.client.post(reverse('parcel_cancel', args=[parcel_2.tracking_number]), {
            'reason': 'Cross-tenant cancellation test'
        })
        self.assertEqual(response.status_code, 403)

    def test_saas_client_delete(self):
        """Test deleting a client organization with safety confirmation check."""
        self.client.login(username='platform_owner', password='OwnerPassword123!')

        # Mismatched confirmation name -> fails
        response = self.client.post(reverse('saas_client_delete', args=[self.tenant_2.slug]), {
            'confirm_name': 'Wrong Name'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deletion aborted")
        self.assertTrue(Tenant.objects.filter(slug='tawakal').exists())

        # Exact matching confirmation name -> succeeds
        response = self.client.post(reverse('saas_client_delete', args=[self.tenant_2.slug]), {
            'confirm_name': 'Tawakal Express'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "permanently deleted")
        self.assertFalse(Tenant.objects.filter(slug='tawakal').exists())

    def test_saas_export_tenants_csv(self):
        """Test exporting all installed clients to CSV."""
        self.client.login(username='platform_owner', password='OwnerPassword123!')
        response = self.client.get(reverse('saas_export_tenants_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('Northern Highways Transporters', response.content.decode('utf-8'))
        self.assertIn('Tawakal Express', response.content.decode('utf-8'))

    def test_management_commands_provision_and_admin(self):
        """Test provision_tenant and create_platform_admin CLI management commands."""
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command(
            'provision_tenant',
            name='Sahara Logistics',
            slug='sahara',
            prefix='SAH',
            head_office='Isiolo',
            currency='KES',
            admin_username='sahara_boss',
            admin_phone='0711555666',
            admin_email='boss@sahara.co.ke',
            admin_password='SaharaPassword123!',
            plan=TenantPlan.STARTER,
            primary_color='#2e7d32',
            accent_color='#f57f17',
            stdout=out
        )
        self.assertIn("provisioned successfully", out.getvalue())

        sahara = Tenant.objects.get(slug='sahara')
        self.assertEqual(sahara.tracking_prefix, 'SAH')
        self.assertEqual(sahara.primary_color, '#2e7d32')
        self.assertEqual(sahara.max_users, 10)  # Starter tier default

        # Test create_platform_admin command
        out_admin = StringIO()
        call_command(
            'create_platform_admin',
            username='new_platform_admin',
            password='AdminPassword123!',
            phone='0700999999',
            stdout=out_admin
        )
        self.assertIn("created successfully", out_admin.getvalue())
        new_admin = User.objects.get(username='new_platform_admin')
        self.assertTrue(new_admin.is_superuser)
        self.assertIsNone(new_admin.tenant)

    def test_tenant_branding_colors_in_context(self):
        """Verify that tenant's custom primary and accent colors render into the template."""
        self.tenant_2.primary_color = '#1b5e20'
        self.tenant_2.accent_color = '#ffd600'
        self.tenant_2.save()

        # Switch to Tenant 2
        self.client.login(username='twk_admin', password='Password123!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '#1b5e20')
        self.assertContains(response, '#ffd600')

    def test_tenant_receipt_and_manifest_branding(self):
        """Verify that tenant receipts and A4 manifests display tenant unique branding and headings."""
        # Ensure Tenant 1 (NHT) has settings in the DB first
        from core.models import SiteSettings
        SiteSettings.load(tenant=self.tenant_1)

        self.tenant_2.receipt_header = "TAWAKAL CUSTOM RECEIPT HEADER"
        self.tenant_2.receipt_footer = "TAWAKAL CUSTOM RECEIPT FOOTER"
        self.tenant_2.save()

        # Create parcel for tenant 2
        items = [{'description': 'Spices', 'wrap_type': 'Sack', 'quantity': 2, 'unit_price': Decimal('25.00')}]
        parcel = create_parcel(
            route=self.route_2, sender_name="Fatuma", sender_phone="0711000000",
            receiver_name="Amina", receiver_phone="0722000000", receiver_id_number="87654321",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=items, created_by=self.clerk_2
        )

        self.client.login(username='twk_clerk', password='Password123!')
        res_receipt = self.client.get(reverse('parcel_receipt', args=[parcel.tracking_number]))
        self.assertEqual(res_receipt.status_code, 200)
        content_receipt = res_receipt.content.decode()
        self.assertIn("TAWAKAL CUSTOM RECEIPT HEADER", content_receipt)
        self.assertIn("TAWAKAL CUSTOM RECEIPT FOOTER", content_receipt)
        self.assertIn("Tawakal Express", content_receipt)
        self.assertNotIn("Northern Highways Transporters", content_receipt)

        self.client.login(username='twk_admin', password='Password123!')
        res_manifest = self.client.get(reverse('daily_statement'))
        self.assertEqual(res_manifest.status_code, 200)
        content_manifest = res_manifest.content.decode()
        self.assertIn("Tawakal Express", content_manifest)
        self.assertNotIn("Northern Highways Transporters", content_manifest)

        res_manifest_pdf = self.client.get(reverse('daily_statement_pdf'))
        self.assertEqual(res_manifest_pdf.status_code, 200)
        self.assertTrue(res_manifest_pdf.content.startswith(b'%PDF'))

        # Public tracking page for tenant 2 consignment
        self.client.logout()
        res_track = self.client.get(reverse('public_track', args=[parcel.tracking_number]))
        self.assertEqual(res_track.status_code, 200)
        content_track = res_track.content.decode()
        self.assertIn("Tawakal Express", content_track)
        self.assertNotIn("Northern Highways Transporters", content_track)
        self.assertNotIn("Nairobi Head Office", content_track)

        # Platform Admin impersonating/switching to Tenant 2
        self.client.login(username='platform_owner', password='OwnerPassword123!')
        self.client.get(reverse('saas_switch_tenant', args=[self.tenant_2.pk]))
        res_admin_manifest = self.client.get(reverse('daily_statement'))
        self.assertEqual(res_admin_manifest.status_code, 200)
        admin_manifest_html = res_admin_manifest.content.decode()
        self.assertIn("Tawakal Express", admin_manifest_html)
        # Check printable statement card specifically has Tawakal and not Northern
        sheet_html = admin_manifest_html.split('<!-- Printable Statement Sheet -->')[-1].split('<!-- Signoff block')[0]
        self.assertIn("Tawakal Express", sheet_html)
        self.assertNotIn("Northern Highways Transporters", sheet_html)

    def test_cross_tenant_user_and_route_tampering_blocked(self):
        """Verify tenant admin cannot edit or toggle users/routes of another tenant or platform superuser."""
        self.client.login(username='twk_admin', password='Password123!')

        # Attempt to edit platform owner (tenant_id is None) -> 403
        res = self.client.get(reverse('user_update', args=[self.platform_admin.pk]))
        self.assertEqual(res.status_code, 403)

        # Attempt to toggle platform owner -> 403
        res = self.client.post(reverse('user_toggle_active', args=[self.platform_admin.pk]))
        self.assertEqual(res.status_code, 403)

        # Attempt to edit tenant 1 user -> 403
        res = self.client.get(reverse('user_update', args=[self.admin_1.pk]))
        self.assertEqual(res.status_code, 403)

        # Attempt to edit tenant 1 route -> 403
        res = self.client.get(reverse('route_update', args=[self.route_1.pk]))
        self.assertEqual(res.status_code, 403)

        # Attempt to toggle tenant 1 route -> 403
        res = self.client.post(reverse('route_toggle', args=[self.route_1.pk]))
        self.assertEqual(res.status_code, 403)

        # Attempt to delete tenant 1 route -> 403
        res = self.client.post(reverse('route_delete', args=[self.route_1.pk]))
        self.assertEqual(res.status_code, 403)

    def test_cross_tenant_config_tampering_blocked(self):
        """Verify tenant admin cannot edit or toggle choice/field configs belonging to another tenant."""
        from core.models import ChoiceConfig
        choice_nht = ChoiceConfig.objects.create(
            tenant=self.tenant_1,
            category='wrap_type',
            key='SuperBox',
            label='Super Box',
            is_active=True
        )
        self.client.login(username='twk_admin', password='Password123!')

        # Attempt to edit choice belonging to tenant 1 -> 403
        res = self.client.get(reverse('choice_config_edit', args=[choice_nht.pk]))
        self.assertEqual(res.status_code, 403)

        # Attempt to toggle choice belonging to tenant 1 -> 403
        res = self.client.post(reverse('choice_config_toggle', args=[choice_nht.pk]))
        self.assertEqual(res.status_code, 403)

    def test_admin_override_form_route_scoping(self):
        """Verify AdminOverrideForm scopes route queryset to the parcel's tenant."""
        from parcels.forms import AdminOverrideForm
        parcel = create_parcel(
            route=self.route_1,
            sender_name="Sender", sender_phone="0711000001",
            receiver_name="Receiver", receiver_phone="0711000002", receiver_id_number="12345",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Test Item', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('500.00')}],
            tenant=self.tenant_1
        )
        form = AdminOverrideForm(instance=parcel)
        route_qs = form.fields['route'].queryset
        self.assertIn(self.route_1, route_qs)
        self.assertNotIn(self.route_2, route_qs)

    def test_daily_statement_pdf_with_unicode_characters(self):
        """Verify daily statement PDF generation does not crash on smart quotes, dashes, or unicode."""
        from django.utils import timezone
        from reports.services import generate_daily_statement_pdf_bytes, get_daily_statement_data
        create_parcel(
            route=self.route_1,
            sender_name="Ahmed’s “Super” Shop", sender_phone="0711000001",
            receiver_name="John & Co — Mandera", receiver_phone="0711000002", receiver_id_number="12345",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Cargo with — dash & ‘quotes’', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('500.00')}],
            tenant=self.tenant_1
        )
        data = get_daily_statement_data(timezone.localdate(), tenant=self.tenant_1)
        pdf_bytes = generate_daily_statement_pdf_bytes(data)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_invalid_query_parameters_handled_gracefully(self):
        """Verify non-numeric route parameters do not trigger 500 server error."""
        self.client.login(username='nht_admin', password='Password123!')
        res_list = self.client.get(reverse('parcel_list'), {'route': 'non_numeric_id'})
        self.assertEqual(res_list.status_code, 200)

        res_stmt = self.client.get(reverse('daily_statement'), {'route': 'non_numeric_id'})
        self.assertEqual(res_stmt.status_code, 200)

    def test_suspended_tenant_allows_login_logout(self):
        """Verify that suspended tenant screen allows accessing login and logout endpoints."""
        self.tenant_1.status = TenantStatus.SUSPENDED
        self.tenant_1.is_active = False
        self.tenant_1.save()

        # Logged-in staff of suspended tenant accessing dashboard gets 403 suspended screen
        self.client.login(username='nht_clerk', password='Password123!')
        res_dash = self.client.get(reverse('dashboard'))
        self.assertEqual(res_dash.status_code, 403)
        self.assertIn("Suspended", res_dash.content.decode())

        # Staff can successfully log out without 403
        res_logout = self.client.get(reverse('logout'))
        self.assertIn(res_logout.status_code, [200, 302])

        # Login page is accessible without 403
        res_login = self.client.get(reverse('login'))
        self.assertEqual(res_login.status_code, 200)

    def test_duplicate_route_name_in_same_tenant_validation(self):
        """Verify submitting an existing route name for the same tenant shows a clean form error instead of 500."""
        self.client.login(username='nht_admin', password='Password123!')
        res = self.client.post(reverse('route_create'), {
            'name': self.route_1.name,
            'origin': 'Nairobi',
            'description': 'Duplicate attempt',
            'is_active': True
        })
        self.assertEqual(res.status_code, 200)
        self.assertFormError(res.context['form'], 'name', f"A route named '{self.route_1.name}' already exists.")

    def test_duplicate_choice_config_validation(self):
        """Verify submitting an existing choice config key for the same tenant shows a clean error instead of 500."""
        from core.models import ChoiceConfig
        ChoiceConfig.objects.create(
            tenant=self.tenant_1,
            category='wrap_type',
            key='ExistingBox',
            label='Existing Box',
            is_active=True
        )
        self.client.login(username='nht_admin', password='Password123!')
        res = self.client.post(reverse('choice_config_create'), {
            'category': 'wrap_type',
            'key': 'ExistingBox',
            'label': 'Duplicate Box',
            'is_default': False,
            'is_active': True,
            'order': 1
        })
        self.assertEqual(res.status_code, 200)
        self.assertFormError(res.context['form'], 'key', "A choice with key 'ExistingBox' already exists in this category.")

    def test_field_config_auto_fork_for_tenant(self):
        """Verify tenant admin editing a global default FieldConfig automatically forks a tenant-specific copy."""
        from core.models import FieldConfig
        global_cfg = FieldConfig.objects.create(
            tenant=None,
            field_key='sender_name',
            label='Global Sender',
            is_required=True,
            is_visible=True,
            order=1
        )
        self.client.login(username='twk_admin', password='Password123!')
        # Post updated label
        res = self.client.post(reverse('field_config_edit', args=[global_cfg.pk]), {
            'label': 'Tawakal Custom Sender',
            'placeholder': 'Enter your full name',
            'help_text': '',
            'is_required': True,
            'is_visible': True,
            'order': 1,
            'is_active': True,
        })
        self.assertRedirects(res, reverse('admin_panel_config'))

        # Check that a tenant-specific record was created with the customized label
        twk_cfg = FieldConfig.objects.filter(tenant=self.tenant_2, field_key='sender_name').first()
        self.assertIsNotNone(twk_cfg)
        self.assertEqual(twk_cfg.label, 'Tawakal Custom Sender')
        # Check global config was NOT mutated
        global_cfg.refresh_from_db()
        self.assertEqual(global_cfg.label, 'Global Sender')

    def test_login_open_redirect_protection(self):
        """Verify open redirect with protocol-relative URL is blocked upon login."""
        res = self.client.post(reverse('login') + '?next=//attacker.com/steal-creds', {
            'username': 'nht_clerk',
            'password': 'Password123!'
        })
        self.assertRedirects(res, reverse('dashboard'))

    def test_platform_admin_workspace_switch_scopes_parcels(self):
        """Verify that when platform super admin switches workspace to tenant 1, only tenant 1 parcels appear."""
        from parcels.models import Parcel
        p1 = create_parcel(
            route=self.route_1,
            sender_name="Sender 1", sender_phone="0711000001",
            receiver_name="Receiver 1", receiver_phone="0711000002", receiver_id_number="12345",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Item 1', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('500.00')}],
            tenant=self.tenant_1
        )
        p2 = create_parcel(
            route=self.route_2,
            sender_name="Sender 2", sender_phone="0711000003",
            receiver_name="Receiver 2", receiver_phone="0711000004", receiver_id_number="67890",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Item 2', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('800.00')}],
            tenant=self.tenant_2
        )

        login_ok = self.client.login(username='platform_owner', password='OwnerPassword123!')
        self.assertTrue(login_ok)
        # Switch to tenant 1
        res_switch = self.client.get(reverse('saas_switch_tenant', args=[self.tenant_1.pk]))
        self.assertEqual(res_switch.status_code, 302)

        # Dashboard and parcel list should only show p1
        res_list = self.client.get(reverse('parcel_list'))
        self.assertEqual(res_list.status_code, 200)
        self.assertIn(p1.tracking_number, res_list.content.decode())
        self.assertNotIn(p2.tracking_number, res_list.content.decode())

    def test_create_parcel_cross_tenant_route_blocked(self):
        """Verify create_parcel prevents assigning route of another tenant."""
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            create_parcel(
                route=self.route_2,  # Belongs to tenant 2
                sender_name="Sender", sender_phone="0711000001",
                receiver_name="Receiver", receiver_phone="0711000002", receiver_id_number="12345",
                payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
                items_data=[{'description': 'Test Item', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('500.00')}],
                tenant=self.tenant_1  # Belongs to tenant 1
            )





