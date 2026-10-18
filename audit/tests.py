from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Role
from .models import AuditLog
from .services import log_audit_event, sanitize_dict


class AuditLoggingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="audit_tester",
            phone="0722000001",
            password="Password123!",
            role=Role.SUPER_ADMIN
        )

    def test_log_audit_event_creation(self):
        entry = log_audit_event(
            action="TEST_ACTION",
            actor=self.user,
            object_type="TestModel",
            object_identifier="123",
            reason="Testing audit creation"
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.action, "TEST_ACTION")
        self.assertEqual(entry.actor, self.user)

    def test_sensitive_keys_redacted(self):
        raw_data = {
            'username': 'john',
            'password': 'secret_password_123',
            'token': 'xyz_abc_secret',
            'nested': {
                'pin': '1234',
                'amount': 500
            }
        }
        cleaned = sanitize_dict(raw_data)
        self.assertEqual(cleaned['password'], '[REDACTED]')
        self.assertEqual(cleaned['token'], '[REDACTED]')
        self.assertEqual(cleaned['nested']['pin'], '[REDACTED]')
        self.assertEqual(cleaned['nested']['amount'], 500)

    def test_login_and_logout_triggers_audit_entry(self):
        self.client.post(reverse('login'), {
            'username': 'audit_tester',
            'password': 'Password123!'
        })
        self.assertTrue(AuditLog.objects.filter(action='LOGIN_SUCCESS', actor=self.user).exists())

        self.client.post(reverse('logout'))
        self.assertTrue(AuditLog.objects.filter(action='LOGOUT', actor=self.user).exists())

    def test_failed_login_triggers_audit_entry(self):
        self.client.post(reverse('login'), {
            'username': 'audit_tester',
            'password': 'BadPassword'
        })
        self.assertTrue(AuditLog.objects.filter(action='LOGIN_FAILED').exists())
