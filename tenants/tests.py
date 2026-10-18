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

