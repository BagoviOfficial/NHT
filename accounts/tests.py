from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from routes.models import Route
from .models import User, Role


class AuthenticationAndRBACTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.route_garissa = Route.objects.create(name="Garissa", origin="Nairobi")
        self.route_mandera = Route.objects.create(name="Mandera", origin="Nairobi")

        # Create users for all roles
        self.super_admin = User.objects.create_user(
            username="admin_user",
            phone="0700000001",
            password="Password123!",
            role=Role.SUPER_ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.ops_manager = User.objects.create_user(
            username="ops_user",
            phone="0700000002",
            password="Password123!",
            role=Role.OPERATIONS_MANAGER,
            is_staff=True
        )
        self.counter_clerk = User.objects.create_user(
            username="counter_user",
            phone="0700000003",
            password="Password123!",
            role=Role.COUNTER_STAFF,
            is_staff=True
        )
        self.dispatch_staff = User.objects.create_user(
            username="dispatch_user",
            phone="0700000004",
            password="Password123!",
            role=Role.DISPATCH_STAFF,
            is_staff=True
        )
        self.dest_garissa = User.objects.create_user(
            username="garissa_clerk",
            phone="0700000005",
            password="Password123!",
            role=Role.DESTINATION_STAFF,
            assigned_route=self.route_garissa,
            is_staff=True
        )
        self.read_only_user = User.objects.create_user(
            username="readonly_user",
            phone="0700000006",
            password="Password123!",
            role=Role.READ_ONLY,
            is_staff=True
        )

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_valid_login_succeeds(self):
        response = self.client.post(reverse('login'), {
            'username': 'counter_user',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

    def test_invalid_login_rejected(self):
        response = self.client.post(reverse('login'), {
            'username': 'counter_user',
            'password': 'WrongPassword!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_deactivated_user_cannot_login(self):
        self.counter_clerk.is_active = False
        self.counter_clerk.save()
        response = self.client.post(reverse('login'), {
            'username': 'counter_user',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "deactivated")

    def test_login_brute_force_lockout(self):
        for _ in range(5):
            self.client.post(reverse('login'), {
                'username': 'counter_user',
                'password': 'WrongPassword!'
            })
        response = self.client.post(reverse('login'), {
            'username': 'counter_user',
            'password': 'Password123!'
        })
        self.assertContains(response, "Too many failed login attempts")

    def test_counter_staff_cannot_access_admin_panel(self):
        self.client.login(username='counter_user', password='Password123!')
        response = self.client.get(reverse('admin_panel'))
        self.assertEqual(response.status_code, 403)

    def test_operations_manager_cannot_access_user_management(self):
        self.client.login(username='ops_user', password='Password123!')
        response = self.client.get(reverse('admin_panel_users'))
        self.assertEqual(response.status_code, 403)

    def test_super_admin_can_access_admin_panel(self):
        self.client.login(username='admin_user', password='Password123!')
        response = self.client.get(reverse('admin_panel'))
        self.assertEqual(response.status_code, 200)

    def test_super_admin_cannot_deactivate_self(self):
        self.client.login(username='admin_user', password='Password123!')
        response = self.client.post(reverse('user_toggle_active', args=[self.super_admin.pk]), follow=True)
        self.super_admin.refresh_from_db()
        self.assertTrue(self.super_admin.is_active)
        self.assertContains(response, "You cannot deactivate your own administrative account")

    def test_password_change_requires_authentication(self):
        response = self.client.get(reverse('password_change'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_password_change_success_and_audit(self):
        from audit.models import AuditLog
        self.client.login(username='counter_user', password='Password123!')
        response = self.client.post(reverse('password_change'), {
            'old_password': 'Password123!',
            'new_password1': 'NewSecurePass2026!',
            'new_password2': 'NewSecurePass2026!'
        })
        self.assertEqual(response.status_code, 302)
        self.counter_clerk.refresh_from_db()
        self.assertTrue(self.counter_clerk.check_password('NewSecurePass2026!'))
        self.assertTrue(AuditLog.objects.filter(action='PASSWORD_CHANGE', actor=self.counter_clerk).exists())

    def test_super_admin_can_create_user(self):
        from audit.models import AuditLog
        self.client.login(username='admin_user', password='Password123!')
        response = self.client.post(reverse('user_create'), {
            'username': 'new_staff_member',
            'first_name': 'New',
            'last_name': 'Staff',
            'phone': '0700999888',
            'email': 'newstaff@northernhighways.co.ke',
            'password': 'Password123!',
            'role': Role.COUNTER_STAFF,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='new_staff_member').exists())
        self.assertTrue(AuditLog.objects.filter(action='USER_CREATE', object_identifier='new_staff_member').exists())

    def test_non_admin_cannot_create_user(self):
        self.client.login(username='counter_user', password='Password123!')
        response = self.client.get(reverse('user_create'))
        self.assertEqual(response.status_code, 403)

    def test_duplicate_phone_rejected_in_user_form(self):
        from accounts.forms import UserCreateForm
        form = UserCreateForm(data={
            'username': 'unique_user',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '0700000001',  # already used by admin_user
            'email': 'unique@northernhighways.co.ke',
            'password': 'Password123!',
            'role': Role.COUNTER_STAFF,
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

