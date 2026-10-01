from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
from parcels.models import (
    Branch, UserProfile, ShippingRate, Parcel,
    ParcelTrackingLog, TransitManifest, PickupRequest, CustomerInquiry
)
from parcels.utils import calculate_shipping_cost, generate_qr_base64, generate_svg_barcode


class ParcelManagementSystemTests(TestCase):

    def setUp(self):
        # 1. Setup Shipping Rates
        self.standard_rate = ShippingRate.objects.create(
            service_type='STANDARD',
            base_price=Decimal('5.00'),
            per_kg_rate=Decimal('2.50'),
            fragile_fee=Decimal('4.00'),
            insurance_rate_pct=Decimal('1.50'),
            tax_pct=Decimal('5.00'),
            delivery_time_frame='3-5 Days'
        )
        self.express_rate = ShippingRate.objects.create(
            service_type='EXPRESS',
            base_price=Decimal('12.00'),
            per_kg_rate=Decimal('4.50'),
            fragile_fee=Decimal('6.00'),
            insurance_rate_pct=Decimal('1.50'),
            tax_pct=Decimal('5.00'),
            delivery_time_frame='1-2 Days'
        )

        # 2. Setup Branches
        self.branch_nyc = Branch.objects.create(
            code='NYC-01',
            name='New York Hub',
            branch_type='MAIN_HUB',
            phone='+1 212 555 0101',
            address='450 7th Ave',
            city='New York',
            state='NY',
            postal_code='10123'
        )
        self.branch_lax = Branch.objects.create(
            code='LAX-01',
            name='Los Angeles Hub',
            branch_type='MAIN_HUB',
            phone='+1 310 555 0182',
            address='5757 W Century Blvd',
            city='Los Angeles',
            state='CA',
            postal_code='90045'
        )

        # 3. Setup Users
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='testpassword',
            first_name='Admin',
            last_name='User',
            is_staff=True,
            is_superuser=True
        )
        UserProfile.objects.create(user=self.admin_user, role='ADMIN', branch=self.branch_nyc)

        self.staff_user = User.objects.create_user(
            username='staff_test',
            password='testpassword',
            first_name='Staff',
            last_name='Member'
        )
        UserProfile.objects.create(user=self.staff_user, role='BRANCH_STAFF', branch=self.branch_nyc)

        self.courier_user = User.objects.create_user(
            username='courier_test',
            password='testpassword',
            first_name='Courier',
            last_name='Rider'
        )
        UserProfile.objects.create(user=self.courier_user, role='COURIER', branch=self.branch_nyc, vehicle_type='Scooter', license_plate='TEST-101')

        self.customer_user = User.objects.create_user(
            username='customer_test',
            password='testpassword',
            first_name='Customer',
            last_name='One'
        )
        UserProfile.objects.create(user=self.customer_user, role='CUSTOMER', phone='1234567890')

        self.client = Client()

    def test_utils_pricing_calculation(self):
        """Test pricing calculator with actual vs volumetric weight and options."""
        result = calculate_shipping_cost(
            service_type='STANDARD',
            weight_kg=2.0,
            length_cm=10,
            width_cm=10,
            height_cm=10,
            is_fragile=False,
            declared_value=0.0
        )
        # base: 5.0, weight: 2.0 * 2.50 = 5.0, subtotal: 10.0, tax 5%: 0.50, total: 10.50
        self.assertEqual(result['base_price'], 5.0)
        self.assertEqual(result['weight_price'], 5.0)
        self.assertEqual(result['total_price'], 10.50)

    def test_qr_and_barcode_generation(self):
        """Test that SVG barcode and base64 QR code strings are generated."""
        barcode = generate_svg_barcode('PRCL-TEST-123')
        self.assertIn('<svg', barcode)
        self.assertIn('PRCL-TEST-123', barcode)

        qr_img = generate_qr_base64('https://swiftparcel.com/track/PRCL-TEST-123')
        self.assertTrue(qr_img.startswith('data:image/svg+xml;base64,'))


    def test_parcel_creation_and_pricing(self):
        """Test parcel model lifecycle, tracking code, OTP and pricing."""
        parcel = Parcel.objects.create(
            sender_name='Alice Smith',
            sender_phone='555-0101',
            sender_address='123 Broadway',
            sender_city='New York',
            receiver_name='Bob Jones',
            receiver_phone='555-0202',
            receiver_address='456 Sunset Blvd',
            receiver_city='Los Angeles',
            origin_branch=self.branch_nyc,
            destination_branch=self.branch_lax,
            service_type='STANDARD',
            category='GENERAL',
            item_description='Books and notebooks',
            weight_kg=Decimal('4.00'),
            length_cm=Decimal('20.0'),
            width_cm=Decimal('20.0'),
            height_cm=Decimal('10.0'),
            is_fragile=True,
            declared_value=Decimal('100.00'),
            created_by=self.staff_user
        )
        parcel.calculate_pricing()
        parcel.save()

        self.assertTrue(parcel.tracking_number.startswith('PRCL-'))
        self.assertEqual(len(parcel.security_otp), 6)
        self.assertTrue(parcel.total_price > 0)
        self.assertEqual(parcel.status, 'BOOKED')
        self.assertEqual(parcel.current_branch, self.branch_nyc)

    def test_transit_manifest_dispatch_and_receive(self):
        """Test linehaul manifest bulk dispatch and receipt."""
        parcel = Parcel.objects.create(
            sender_name='Alice', sender_phone='111', sender_address='NYC', sender_city='New York',
            receiver_name='Bob', receiver_phone='222', receiver_address='LAX', receiver_city='LA',
            origin_branch=self.branch_nyc, destination_branch=self.branch_lax,
            weight_kg=Decimal('2.0'), item_description='Test item', created_by=self.staff_user
        )
        parcel.calculate_pricing()
        parcel.save()

        manifest = TransitManifest.objects.create(
            origin_branch=self.branch_nyc,
            destination_branch=self.branch_lax,
            driver_name='John Hauler',
            driver_phone='555-9999',
            vehicle_plate='TRK-9900',
            created_by=self.staff_user
        )
        manifest.parcels.add(parcel)

        # Log in as staff and trigger dispatch
        self.client.login(username='staff_test', password='testpassword')
        resp = self.client.get(reverse('manifest_dispatch', kwargs={'manifest_number': manifest.manifest_number}))
        self.assertEqual(resp.status_code, 302)

        parcel.refresh_from_db()
        manifest.refresh_from_db()
        self.assertEqual(manifest.status, 'DISPATCHED')
        self.assertEqual(parcel.status, 'IN_TRANSIT')
        self.assertTrue(parcel.tracking_logs.filter(status='IN_TRANSIT').exists())

        # Trigger receive
        resp = self.client.get(reverse('manifest_receive', kwargs={'manifest_number': manifest.manifest_number}))
        self.assertEqual(resp.status_code, 302)

        parcel.refresh_from_db()
        manifest.refresh_from_db()
        self.assertEqual(manifest.status, 'RECEIVED')
        self.assertEqual(parcel.status, 'RECEIVED_AT_DESTINATION')
        self.assertEqual(parcel.current_branch, self.branch_lax)

    def test_courier_delivery_verification_with_otp(self):
        """Test courier delivery with security OTP confirmation."""
        parcel = Parcel.objects.create(
            sender_name='Alice', sender_phone='111', sender_address='NYC', sender_city='New York',
            receiver_name='Bob', receiver_phone='222', receiver_address='LAX', receiver_city='LA',
            origin_branch=self.branch_nyc, destination_branch=self.branch_lax,
            weight_kg=Decimal('1.0'), item_description='Test item',
            status='OUT_FOR_DELIVERY',
            assigned_courier=self.courier_user,
            created_by=self.staff_user
        )

        self.client.login(username='courier_test', password='testpassword')

        # Attempt with wrong OTP
        resp = self.client.post(reverse('courier_delivery_action', kwargs={'tracking_number': parcel.tracking_number}), {
            'action': 'DELIVER',
            'receiver_name': 'Bob Signee',
            'security_otp': '000000', # wrong
            'delivery_notes': 'Left at door'
        })
        parcel.refresh_from_db()
        self.assertNotEqual(parcel.status, 'DELIVERED')

        # Attempt with correct OTP
        resp = self.client.post(reverse('courier_delivery_action', kwargs={'tracking_number': parcel.tracking_number}), {
            'action': 'DELIVER',
            'receiver_name': 'Bob Signee',
            'security_otp': parcel.security_otp, # correct
            'delivery_notes': 'Handed over directly to customer'
        })
        self.assertEqual(resp.status_code, 302)

        parcel.refresh_from_db()
        self.assertEqual(parcel.status, 'DELIVERED')
        self.assertEqual(parcel.received_by_name, 'Bob Signee')
        self.assertIsNotNone(parcel.delivered_at)

    def test_public_track_view(self):
        """Test public tracking view returns 200 and displays parcel details."""
        parcel = Parcel.objects.create(
            sender_name='Alice', sender_phone='111', sender_address='NYC', sender_city='New York',
            receiver_name='Bob', receiver_phone='222', receiver_address='LAX', receiver_city='LA',
            origin_branch=self.branch_nyc, destination_branch=self.branch_lax,
            weight_kg=Decimal('1.0'), item_description='Test item'
        )
        parcel.calculate_pricing()
        parcel.save()

        resp = self.client.get(reverse('track_detail', kwargs={'tracking_number': parcel.tracking_number}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, parcel.tracking_number)
        self.assertContains(resp, 'Bob')

    def test_api_rate_calculator(self):
        """Test JSON rate calculator API."""
        resp = self.client.get(reverse('api_calculate_rate'), {
            'service_type': 'STANDARD',
            'weight_kg': '2.0',
            'length_cm': '10',
            'width_cm': '10',
            'height_cm': '10',
            'is_fragile': 'false',
            'declared_value': '0'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('total_price', data)
        self.assertEqual(data['base_price'], 5.0)
