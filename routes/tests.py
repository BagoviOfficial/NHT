from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Role
from parcels.models import Parcel, ShipmentItem
from .models import Route


class RouteManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.super_admin = User.objects.create_user(
            username="admin_route",
            phone="0711000001",
            password="Password123!",
            role=Role.SUPER_ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.clerk = User.objects.create_user(
            username="clerk_route",
            phone="0711000002",
            password="Password123!",
            role=Role.COUNTER_STAFF,
            is_staff=True
        )

    def test_route_slug_auto_generation(self):
        r = Route.objects.create(name="Wajir Central")
        self.assertEqual(r.slug, "wajir-central")

    def test_non_admin_cannot_access_routes_management(self):
        self.client.login(username="clerk_route", password="Password123!")
        response = self.client.get(reverse('route_list'))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_route(self):
        self.client.login(username="admin_route", password="Password123!")
        response = self.client.post(reverse('route_create'), {
            'name': 'Moyale',
            'origin': 'Nairobi',
            'description': 'Northern border crossing',
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Route.objects.filter(name='Moyale').exists())

    def test_route_referenced_by_parcel_cannot_be_deleted(self):
        r = Route.objects.create(name="Elwak")
        p = Parcel.objects.create(
            route=r,
            sender_name="Sender",
            sender_phone="0700000000",
            receiver_name="Receiver",
            receiver_phone="0700000001",
            receiver_id_number="12345678"
        )
        self.assertFalse(r.can_be_deleted())

        self.client.login(username="admin_route", password="Password123!")
        response = self.client.post(reverse('route_delete', args=[r.pk]), follow=True)
        self.assertTrue(Route.objects.filter(pk=r.pk).exists())
        self.assertContains(response, "Cannot delete")
