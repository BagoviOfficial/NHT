from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from django.core.exceptions import ValidationError
from accounts.models import User, Role
from routes.models import Route
from core.models import SiteSettings
from .models import Parcel, ShipmentItem, ParcelStatusHistory, ParcelStatus, PaymentStatus, PaymentMethod
from .forms import ParcelForm
from .services import (
    create_parcel, update_parcel, transition_parcel_status,
    collect_parcel, cancel_parcel
)
from .utils import generate_tracking_qr_svg


class ParcelLifecycleAndSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.settings = SiteSettings.load()

        self.route_garissa = Route.objects.create(name="Garissa", origin="Nairobi")
        self.route_mandera = Route.objects.create(name="Mandera", origin="Nairobi")

        self.admin = User.objects.create_user(
            username="admin_p", phone="0733000001", password="Password123!",
            role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True
        )
        self.ops_mgr = User.objects.create_user(
            username="ops_p", phone="0733000002", password="Password123!",
            role=Role.OPERATIONS_MANAGER, is_staff=True
        )
        self.counter_clerk = User.objects.create_user(
            username="clerk_p", phone="0733000003", password="Password123!",
            role=Role.COUNTER_STAFF, is_staff=True
        )
        self.dest_garissa = User.objects.create_user(
            username="garissa_staff", phone="0733000004", password="Password123!",
            role=Role.DESTINATION_STAFF, assigned_route=self.route_garissa, is_staff=True
        )
        self.dest_mandera = User.objects.create_user(
            username="mandera_staff", phone="0733000005", password="Password123!",
            role=Role.DESTINATION_STAFF, assigned_route=self.route_mandera, is_staff=True
        )

    def test_tracking_number_format(self):
        p = Parcel.objects.create(
            route=self.route_garissa,
            sender_name="Alice", sender_phone="0711111111",
            receiver_name="Bob", receiver_phone="0722222222",
            receiver_id_number="12345678"
        )
        self.assertTrue(p.tracking_number.startswith("NHT-"))
        self.assertEqual(len(p.tracking_number), 12)  # NHT- (4) + 8 chars = 12

    def test_multi_item_parcel_creation_and_exact_decimal_totals(self):
        items = [
            {'description': 'Solar Panel', 'wrap_type': 'Box', 'quantity': 2, 'unit_price': Decimal('2500.50')},
            {'description': 'Battery Cable', 'wrap_type': 'Bundle', 'quantity': 3, 'unit_price': Decimal('350.25')},
        ]
        parcel = create_parcel(
            route=self.route_garissa,
            sender_name="Alice", sender_phone="0711111111",
            receiver_name="Bob", receiver_phone="0722222222",
            receiver_id_number="12345678",
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.MPESA,
            items_data=items,
            created_by=self.counter_clerk
        )
        # 2 * 2500.50 = 5001.00; 3 * 350.25 = 1050.75; Total = 6051.75
        expected_total = Decimal('6051.75')
        self.assertEqual(parcel.price, expected_total)
        self.assertEqual(parcel.items.count(), 2)
        self.assertEqual(parcel.status, ParcelStatus.RECEIVED_AT_HQ)

    def test_editing_blocked_after_dispatch(self):
        items = [{'description': 'Box of books', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('500.00')}]
        parcel = create_parcel(
            route=self.route_garissa, sender_name="Alice", sender_phone="0711111111",
            receiver_name="Bob", receiver_phone="0722222222", receiver_id_number="12345678",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=items, created_by=self.counter_clerk
        )
        transition_parcel_status(
            parcel_id=parcel.pk,
            new_status=ParcelStatus.IN_TRANSIT,
            user=self.ops_mgr,
            truck_plate_number="KBB 123X",
            driver_name="Farah Noor"
        )
        parcel.refresh_from_db()
        self.assertFalse(parcel.is_editable)

        # Attempt to edit should raise ValidationError
        with self.assertRaises(ValidationError):
            update_parcel(
                parcel_id=parcel.pk,
                route=self.route_mandera,
                sender_name="New Sender", sender_phone="0700000000",
                receiver_name="New Recv", receiver_phone="0700000000",
                receiver_id_number="99999999",
                payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
                items_data=items, user=self.counter_clerk
            )

    def test_status_machine_transitions(self):
        items = [{'description': 'Medicine', 'wrap_type': 'Carton', 'quantity': 1, 'unit_price': Decimal('800.00')}]
        p = create_parcel(
            route=self.route_garissa, sender_name="Dr. Ali", sender_phone="0711111111",
            receiver_name="Clinic", receiver_phone="0722222222", receiver_id_number="12345678",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.MPESA,
            items_data=items, created_by=self.counter_clerk
        )

        # Dispatch requires truck and driver
        with self.assertRaises(ValidationError):
            transition_parcel_status(p.pk, ParcelStatus.IN_TRANSIT, user=self.ops_mgr, truck_plate_number="", driver_name="")

        # Valid Dispatch
        transition_parcel_status(p.pk, ParcelStatus.IN_TRANSIT, user=self.ops_mgr, truck_plate_number="KDA 555A", driver_name="Ali Driver")
        p.refresh_from_db()
        self.assertEqual(p.status, ParcelStatus.IN_TRANSIT)

        # Illegal skip to COLLECTED
        with self.assertRaises(ValidationError):
            transition_parcel_status(p.pk, ParcelStatus.COLLECTED, user=self.dest_garissa)

        # Valid Arrival
        transition_parcel_status(p.pk, ParcelStatus.ARRIVED_AT_DESTINATION, user=self.dest_garissa)
        p.refresh_from_db()
        self.assertEqual(p.status, ParcelStatus.ARRIVED_AT_DESTINATION)

        # Valid Stage for Collection
        transition_parcel_status(p.pk, ParcelStatus.AWAITING_COLLECTION, user=self.dest_garissa)
        p.refresh_from_db()
        self.assertEqual(p.status, ParcelStatus.AWAITING_COLLECTION)

        # Valid Collection
        collect_parcel(p.pk, collected_by_name="Clinic Nurse", user=self.dest_garissa)
        p.refresh_from_db()
        self.assertEqual(p.status, ParcelStatus.COLLECTED)
        self.assertEqual(p.collected_by_name, "Clinic Nurse")
        self.assertIsNotNone(p.collected_at)

        # Cannot collect twice (Idempotency)
        with self.assertRaises(ValidationError):
            collect_parcel(p.pk, collected_by_name="Another Person", user=self.dest_garissa)

        # Terminal state cannot be changed or cancelled
        with self.assertRaises(ValidationError):
            cancel_parcel(p.pk, reason="Mistake", user=self.admin)

    def test_object_level_branch_authorisation(self):
        """Destination staff must ONLY access parcels destined for their assigned station."""
        items = [{'description': 'Package', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('500.00')}]
        p_mandera = create_parcel(
            route=self.route_mandera, sender_name="Sender", sender_phone="0711111111",
            receiver_name="Recv", receiver_phone="0722222222", receiver_id_number="12345678",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=items, created_by=self.counter_clerk
        )

        # Garissa clerk attempts to view Mandera parcel
        self.client.login(username="garissa_staff", password="Password123!")
        response = self.client.get(reverse('parcel_detail', args=[p_mandera.tracking_number]))
        self.assertEqual(response.status_code, 403)

        # Mandera clerk can view Mandera parcel
        self.client.login(username="mandera_staff", password="Password123!")
        response = self.client.get(reverse('parcel_detail', args=[p_mandera.tracking_number]))
        self.assertEqual(response.status_code, 200)

    def test_public_tracking_privacy(self):
        """Public tracking must NEVER expose price, payment status, receiver ID or driver phone."""
        items = [{'description': 'Confidential Hardware', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('12500.00')}]
        parcel = create_parcel(
            route=self.route_garissa, sender_name="Confidential Sender", sender_phone="0711111111",
            receiver_name="Confidential Receiver", receiver_phone="0722222222", receiver_id_number="87654321_PRIVATE_ID",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.MPESA,
            items_data=items, created_by=self.counter_clerk
        )

        response = self.client.get(reverse('public_track', args=[parcel.tracking_number]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, parcel.tracking_number)
        self.assertContains(response, parcel.route.name)

        # Sensitive info must NOT be in public HTML
        self.assertNotContains(response, "12500.00")
        self.assertNotContains(response, "87654321_PRIVATE_ID")
        self.assertNotContains(response, "MPESA")
        self.assertNotContains(response, "PAID")

    def test_public_tracking_rate_limiting(self):
        cache.clear()
        self.settings.tracking_rate_limit_per_minute = 5
        self.settings.save()

        for _ in range(5):
            res = self.client.get(reverse('track_search'), {'tracking_number': 'NHT-NONEXIST'})
            self.assertEqual(res.status_code, 200)

        # 6th request triggers 429
        res = self.client.get(reverse('track_search'), {'tracking_number': 'NHT-NONEXIST'})
        self.assertEqual(res.status_code, 429)

    def test_80mm_thermal_receipt_rendering_and_qr_code(self):
        items = [{'description': 'Motor Spare', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('1500.00')}]
        parcel = create_parcel(
            route=self.route_garissa, sender_name="Ali", sender_phone="0711111111",
            receiver_name="Hassan", receiver_phone="0722222222", receiver_id_number="12345678",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=items, created_by=self.counter_clerk
        )
        self.client.login(username="clerk_p", password="Password123!")
        response = self.client.get(reverse('parcel_receipt', args=[parcel.tracking_number]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "80mm")
        self.assertContains(response, parcel.tracking_number)
        self.assertContains(response, "Powered by BAGOVI TECHNOLOGIES")
        # QR SVG present in output
        self.assertContains(response, "<svg")

    def test_counter_clerk_cannot_cancel_parcel(self):
        items = [{'description': 'Books', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('100.00')}]
        p = create_parcel(
            route=self.route_garissa, sender_name="A", sender_phone="071",
            receiver_name="B", receiver_phone="072", receiver_id_number="123",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=items, created_by=self.counter_clerk
        )
        self.client.login(username="clerk_p", password="Password123!")
        res = self.client.post(reverse('parcel_cancel', args=[p.tracking_number]), {'reason': 'Clerk cancel'})
        self.assertEqual(res.status_code, 403)

    def test_destination_staff_cannot_mark_arrival_for_other_route(self):
        items = [{'description': 'Cargo', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('200.00')}]
        p_mandera = create_parcel(
            route=self.route_mandera, sender_name="A", sender_phone="071",
            receiver_name="B", receiver_phone="072", receiver_id_number="123",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=items, created_by=self.counter_clerk
        )
        transition_parcel_status(p_mandera.pk, ParcelStatus.IN_TRANSIT, self.ops_mgr, "Dispatched", "KAA 111A", "Driver")

        # Garissa staff attempts to mark arrival on Mandera parcel
        self.client.login(username="garissa_staff", password="Password123!")
        res = self.client.post(reverse('parcel_arrive', args=[p_mandera.tracking_number]), {'note': 'Wrong depot arrival'})
        self.assertEqual(res.status_code, 403)

    def test_read_only_staff_cannot_dispatch_or_collect(self):
        read_only = User.objects.create_user(
            username="ro_p", phone="0733999999", password="Password123!",
            role=Role.READ_ONLY, is_staff=True
        )
        items = [{'description': 'Tools', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('300.00')}]
        p = create_parcel(
            route=self.route_garissa, sender_name="A", sender_phone="071",
            receiver_name="B", receiver_phone="072", receiver_id_number="123",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=items, created_by=self.counter_clerk
        )
        self.client.login(username="ro_p", password="Password123!")
        res = self.client.post(reverse('parcel_dispatch', args=[p.tracking_number]), {
            'truck_plate_number': 'KCC 123A',
            'driver_name': 'Driver Ali'
        })
        self.assertEqual(res.status_code, 403)

    def test_maximum_sensible_values_rejected(self):
        # Quantity > 10,000
        with self.assertRaises(ValidationError):
            create_parcel(
                route=self.route_garissa, sender_name="A", sender_phone="071",
                receiver_name="B", receiver_phone="072", receiver_id_number="123",
                payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
                items_data=[{'description': 'Massive', 'wrap_type': 'Box', 'quantity': 50000, 'unit_price': Decimal('10.00')}],
                created_by=self.counter_clerk
            )

        # Price > 10,000,000
        with self.assertRaises(ValidationError):
            create_parcel(
                route=self.route_garissa, sender_name="A", sender_phone="071",
                receiver_name="B", receiver_phone="072", receiver_id_number="123",
                payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
                items_data=[{'description': 'Super Expensive', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('99999999.00')}],
                created_by=self.counter_clerk
            )

    def test_admin_override_post_dispatch(self):
        from audit.models import AuditLog
        items = [{'description': 'Solar Inverter', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('8500.00')}]
        p = create_parcel(
            route=self.route_garissa, sender_name="Original Sender", sender_phone="0711111111",
            receiver_name="Original Recv", receiver_phone="0722222222", receiver_id_number="12345678",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
            items_data=items, created_by=self.counter_clerk
        )
        transition_parcel_status(p.pk, ParcelStatus.IN_TRANSIT, self.ops_mgr, "Dispatched", "KAA 111A", "Driver Ali")

        self.client.login(username="admin_p", password="Password123!")

        # 1. When setting is False -> override blocked
        self.settings.allow_superuser_edit_after_dispatch = False
        self.settings.save()
        res = self.client.get(reverse('parcel_override', args=[p.tracking_number]))
        self.assertEqual(res.status_code, 302)

        # 2. When setting is True -> override allowed with reason and audit log
        self.settings.allow_superuser_edit_after_dispatch = True
        self.settings.save()
        res = self.client.post(reverse('parcel_override', args=[p.tracking_number]), {
            'route': self.route_garissa.pk,
            'truck_plate_number': 'KAA 111A',
            'driver_name': 'Driver Ali',
            'sender_name': 'Corrected Sender Name',
            'sender_phone': '0711111111',
            'receiver_name': 'Original Recv',
            'receiver_phone': '0722222222',
            'receiver_id_number': '12345678',
            'payment_status': PaymentStatus.PAID,
            'payment_method': PaymentMethod.CASH,
            'price': '8500.00',
            'reason': 'Customer requested correction of spelling mistake in sender name'
        })
        self.assertEqual(res.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.sender_name, 'Corrected Sender Name')
        self.assertTrue(AuditLog.objects.filter(action='ADMIN_OVERRIDE', object_identifier=p.tracking_number).exists())

    def test_csrf_protection_enforced(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username="clerk_p", password="Password123!")
        # POST without CSRF token should return 403 Forbidden
        response = csrf_client.post(reverse('parcel_create'), {
            'sender_name': 'Attacker',
        })
        self.assertEqual(response.status_code, 403)

    def test_inactive_route_not_in_parcel_form(self):
        inactive_route = Route.objects.create(name="Inactive Station", is_active=False)
        form = ParcelForm()
        available_routes = list(form.fields['route'].queryset)
        self.assertNotIn(inactive_route, available_routes)
        self.assertIn(self.route_garissa, available_routes)

    def test_qr_code_contains_only_public_tracking_url(self):
        tracking_url = f"https://northernhighways.co.ke/track/NHT-12345678/"
        svg_output = generate_tracking_qr_svg(tracking_url)
        self.assertTrue(svg_output.startswith("<svg") or "<svg" in svg_output)
        # Verify it does not embed sensitive strings
        self.assertNotIn("KES", svg_output)
        self.assertNotIn("PAID", svg_output)
        self.assertNotIn("MPESA", svg_output)

    def test_create_shipment_form_renders_single_item_form(self):
        self.client.login(username="clerk_p", password="Password123!")
        res = self.client.get(reverse('parcel_create'))
        self.assertEqual(res.status_code, 200)
        formset = res.context['formset']
        # Must show exactly 1 item form by default instead of multiple compulsory forms
        self.assertEqual(len(formset.forms), 1)
        self.assertEqual(formset.total_form_count(), 1)


