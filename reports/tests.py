from decimal import Decimal
import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, Role
from routes.models import Route
from parcels.models import Parcel, PaymentStatus, PaymentMethod
from parcels.services import create_parcel
from .services import get_daily_statement_data, generate_daily_statement_pdf_bytes


class DailyStatementAndReportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.route_garissa = Route.objects.create(name="Garissa", origin="Nairobi")
        self.route_wajir = Route.objects.create(name="Wajir", origin="Nairobi")

        self.ops_mgr = User.objects.create_user(
            username="ops_rep", phone="0744000001", password="Password123!",
            role=Role.OPERATIONS_MANAGER, is_staff=True
        )
        self.clerk = User.objects.create_user(
            username="clerk_rep", phone="0744000002", password="Password123!",
            role=Role.COUNTER_STAFF, is_staff=True
        )

        today = timezone.localdate()
        # Parcel 1: PAID KES 1,000 (Garissa)
        create_parcel(
            route=self.route_garissa, sender_name="S1", sender_phone="07001",
            receiver_name="R1", receiver_phone="07002", receiver_id_number="111",
            payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.MPESA,
            items_data=[{'description': 'Item 1', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('1000.00')}],
            created_by=self.clerk
        )
        # Parcel 2: COD KES 2,500 (Garissa)
        create_parcel(
            route=self.route_garissa, sender_name="S2", sender_phone="07003",
            receiver_name="R2", receiver_phone="07004", receiver_id_number="222",
            payment_status=PaymentStatus.COD, payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Item 2', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('2500.00')}],
            created_by=self.clerk
        )
        # Parcel 3: UNPAID KES 500 (Wajir)
        create_parcel(
            route=self.route_wajir, sender_name="S3", sender_phone="07005",
            receiver_name="R3", receiver_phone="07006", receiver_id_number="333",
            payment_status=PaymentStatus.UNPAID, payment_method=PaymentMethod.CASH,
            items_data=[{'description': 'Item 3', 'wrap_type': 'Box', 'quantity': 1, 'unit_price': Decimal('500.00')}],
            created_by=self.clerk
        )

    def test_daily_statement_aggregations(self):
        data = get_daily_statement_data(timezone.localdate())
        self.assertEqual(data['total_shipments'], 3)
        self.assertEqual(data['gross_total'], Decimal('4000.00'))
        self.assertEqual(data['paid_total'], Decimal('1000.00'))
        self.assertEqual(data['cod_total'], Decimal('2500.00'))
        self.assertEqual(data['unpaid_total'], Decimal('500.00'))

        # Check route breakdown
        self.assertIn('Garissa', data['routes_summary'])
        self.assertEqual(data['routes_summary']['Garissa']['count'], 2)
        self.assertEqual(data['routes_summary']['Garissa']['subtotal'], Decimal('3500.00'))

        self.assertIn('Wajir', data['routes_summary'])
        self.assertEqual(data['routes_summary']['Wajir']['count'], 1)
        self.assertEqual(data['routes_summary']['Wajir']['subtotal'], Decimal('500.00'))

    def test_daily_statement_pdf_generation(self):
        data = get_daily_statement_data(timezone.localdate())
        pdf_bytes = generate_daily_statement_pdf_bytes(data)
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))
        self.assertGreater(len(pdf_bytes), 500)

    def test_statement_access_permissions(self):
        # Clerk cannot view financial statements
        self.client.login(username="clerk_rep", password="Password123!")
        res = self.client.get(reverse('daily_statement'))
        self.assertEqual(res.status_code, 403)

        # Operations Manager can view
        self.client.login(username="ops_rep", password="Password123!")
        res = self.client.get(reverse('daily_statement'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "4,000.00")

    def test_daily_statement_date_and_route_filtering(self):
        self.client.login(username="ops_rep", password="Password123!")
        # Filter by yesterday - should have 0 shipments
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        res = self.client.get(reverse('daily_statement'), {'date': yesterday.isoformat()})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "No shipments registered for this date")

        # Filter by Garissa route
        res = self.client.get(reverse('daily_statement'), {'date': timezone.localdate().isoformat(), 'route': self.route_garissa.pk})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "3,500.00")

        # Download PDF with route filter
        res_pdf = self.client.get(reverse('daily_statement_pdf'), {'date': timezone.localdate().isoformat(), 'route': self.route_garissa.pk})
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')

