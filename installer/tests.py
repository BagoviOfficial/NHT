import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from tenants.models import Tenant, TenantPlan
from audit.models import AuditLog
from installer.utils import (
    is_system_installed,
    get_system_readiness_checks,
    execute_wordpress_style_installation,
    test_database_connection,
    update_env_database_settings,
    get_lock_file,
)
from installer.middleware import InstallationRedirectMiddleware

User = get_user_model()


class InstallerUtilsTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_file = Path(self.temp_dir.name) / '.installed'
        InstallationRedirectMiddleware.reset_installed_cache()

    def tearDown(self):
        self.temp_dir.cleanup()
        InstallationRedirectMiddleware.reset_installed_cache()

    def test_is_system_installed_with_lock_file(self):
        self.lock_file.write_text("Installed")
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            self.assertTrue(is_system_installed())

    def test_is_system_installed_false_empty_system(self):
        # When neither lock file nor superuser exists
        User.objects.filter(is_superuser=True).delete()
        Tenant.objects.all().delete()
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            self.assertFalse(is_system_installed())

    def test_is_system_installed_true_from_db_records(self):
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            User.objects.create_superuser(
                username='sysadmin',
                phone='0711000001',
                email='sysadmin@example.com',
                password='Password123!'
            )
            Tenant.objects.create(
                name='Test Tenant',
                slug='test-tenant',
                subdomain='test-tenant',
                tracking_prefix='TTN',
                is_active=True
            )
            self.assertTrue(is_system_installed())
            # Verifies lock file was recreated
            self.assertTrue(self.lock_file.exists())

    def test_get_system_readiness_checks(self):
        readiness = get_system_readiness_checks()
        self.assertIn('checks', readiness)
        self.assertIn('all_passed', readiness)
        self.assertIn('db_engine', readiness)
        self.assertIn('py_version', readiness)
        self.assertIsInstance(readiness['checks'], list)
        self.assertGreaterEqual(len(readiness['checks']), 3)

    def test_test_database_connection_sqlite(self):
        ok, msg = test_database_connection(engine='sqlite', name='')
        self.assertTrue(ok)
        self.assertIn("SQLite database accessible", msg)

    def test_update_env_database_settings(self):
        with override_settings(BASE_DIR=Path(self.temp_dir.name)):
            saved = update_env_database_settings(
                engine='postgresql',
                name='test_db',
                user='test_user',
                password='test_password',
                host='127.0.0.1',
                port='5432'
            )
            self.assertTrue(saved)
            env_file = Path(self.temp_dir.name) / '.env'
            self.assertTrue(env_file.exists())
            content = env_file.read_text()
            self.assertIn("DB_NAME=test_db", content)
            self.assertIn("DB_USER=test_user", content)

    def test_execute_wordpress_style_installation(self):
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file, BASE_DIR=Path(self.temp_dir.name)):
            result = execute_wordpress_style_installation(
                platform_title="Test PMS Setup",
                admin_username="test_superadmin",
                admin_password="SuperPassword2026!",
                admin_phone="0711999999",
                admin_email="superadmin@pms.co.ke",
                tenant_name="Safari Express Couriers",
                tenant_prefix="SEC",
                tenant_slug="safari",
                head_office="Nairobi Hub",
                currency="KES",
                starter_routes=["Garissa", "Wajir"]
            )

            self.assertIsNotNone(result['platform_admin'])
            self.assertEqual(result['platform_admin'].username, "test_superadmin")
            self.assertTrue(result['platform_admin'].is_superuser)
            self.assertIsNone(result['platform_admin'].tenant)

            self.assertEqual(result['primary_tenant'].name, "Safari Express Couriers")
            self.assertEqual(result['primary_tenant'].tracking_prefix, "SEC")
            self.assertEqual(result['primary_tenant'].slug, "safari")

            # Verify routes created
            self.assertEqual(result['primary_tenant'].routes.count(), 2)

            # Verify audit log
            self.assertTrue(AuditLog.objects.filter(action='SYSTEM_INSTALLATION').exists())

            # Verify lock file
            self.assertTrue(self.lock_file.exists())


class InstallerMiddlewareTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_file = Path(self.temp_dir.name) / '.installed'
        InstallationRedirectMiddleware.reset_installed_cache()

    def tearDown(self):
        self.temp_dir.cleanup()
        InstallationRedirectMiddleware.reset_installed_cache()

    def test_middleware_redirects_uninstalled_request(self):
        # Force uninstalled state
        User.objects.filter(is_superuser=True).delete()
        Tenant.objects.all().delete()
        InstallationRedirectMiddleware.reset_installed_cache()

        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            response = self.client.get(reverse('login'))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse('installer')))

    def test_middleware_allows_exempt_installer_paths(self):
        User.objects.filter(is_superuser=True).delete()
        Tenant.objects.all().delete()
        InstallationRedirectMiddleware.reset_installed_cache()

        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            response = self.client.get(reverse('installer'))
            self.assertEqual(response.status_code, 200)

            response_health = self.client.get(reverse('installer_health_check'))
            self.assertEqual(response_health.status_code, 200)

    def test_middleware_passes_through_when_installed(self):
        self.lock_file.write_text("Installed")
        InstallationRedirectMiddleware.reset_installed_cache()

        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            # Create a tenant for public home
            Tenant.objects.create(
                name='Default Tenant',
                slug='default',
                subdomain='default',
                tracking_prefix='DFT',
                is_active=True
            )
            response = self.client.get(reverse('login'))
            self.assertEqual(response.status_code, 200)


class InstallerViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_file = Path(self.temp_dir.name) / '.installed'
        InstallationRedirectMiddleware.reset_installed_cache()

    def tearDown(self):
        self.temp_dir.cleanup()
        InstallationRedirectMiddleware.reset_installed_cache()

    def test_installer_wizard_get(self):
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            response = self.client.get(reverse('installer'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Welcome to the 5-Minute Installation")
            self.assertContains(response, "Pre-Flight Environment Diagnostics")

    def test_installer_health_check_json(self):
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            response = self.client.get(reverse('installer_health_check'))
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('checks', data)
            self.assertIn('all_passed', data)

    def test_installer_test_db_api(self):
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            response = self.client.post(
                reverse('installer_test_db'),
                data=json.dumps({'engine': 'sqlite', 'name': '', 'save_to_env': False}),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])

    def test_installer_post_form_validation_mismatch_passwords(self):
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file):
            payload = {
                'platform_title': 'My PMS',
                'admin_username': 'my_admin',
                'admin_password': 'Password123!',
                'confirm_password': 'MismatchedPassword123!',
                'admin_phone': '0700000009',
                'admin_email': 'myadmin@test.com',
                'company_name': 'New Courier',
                'tracking_prefix': 'NCX',
                'slug': 'ncx',
                'head_office': 'Nairobi',
                'currency': 'KES',
            }
            response = self.client.post(reverse('installer'), data=payload)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Passwords do not match.")

    def test_installer_post_success(self):
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file, BASE_DIR=Path(self.temp_dir.name)):
            payload = {
                'platform_title': 'Fast Logistics Cloud',
                'admin_username': 'fast_admin',
                'admin_password': 'SecretPassword2026!',
                'confirm_password': 'SecretPassword2026!',
                'admin_phone': '0722123456',
                'admin_email': 'fast_admin@logistics.com',
                'company_name': 'Fast Logistics Express',
                'tracking_prefix': 'FLE',
                'slug': 'fast-logistics',
                'head_office': 'Nairobi Central',
                'currency': 'KES',
                'starter_routes': 'Garissa, Wajir, Mandera'
            }
            response = self.client.post(reverse('installer'), data=payload)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Success!")
            self.assertContains(response, "Fast Logistics Cloud has been successfully installed")
            self.assertContains(response, "fast_admin")
            self.assertContains(response, "Fast Logistics Express")

            # Check lockout engaged
            self.assertTrue(self.lock_file.exists())
            response_locked = self.client.get(reverse('installer'))
            self.assertEqual(response_locked.status_code, 200)
            self.assertContains(response_locked, "Already Installed")


class InstallerManagementCommandsTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_file = Path(self.temp_dir.name) / '.installed'
        InstallationRedirectMiddleware.reset_installed_cache()

    def tearDown(self):
        self.temp_dir.cleanup()
        InstallationRedirectMiddleware.reset_installed_cache()

    def test_install_system_command_and_reset(self):
        with override_settings(INSTALLER_LOCK_FILE=self.lock_file, BASE_DIR=Path(self.temp_dir.name)):
            # 1. Run install_system CLI command
            call_command(
                'install_system',
                platform_title='CLI Test PMS',
                admin_username='cli_admin',
                admin_password='Clipassword2026!',
                admin_phone='0711223344',
                admin_email='cli@pms.co.ke',
                company_name='CLI Transporters',
                tracking_prefix='CLT',
                slug='cli-transporters',
                skip_checks=True,
                force=True
            )

            self.assertTrue(self.lock_file.exists())
            self.assertTrue(User.objects.filter(username='cli_admin').exists())
            self.assertTrue(Tenant.objects.filter(slug='cli-transporters').exists())

            # 2. Re-running without --force exits cleanly
            call_command('install_system', skip_checks=True)

            # 3. Reset installation command without confirm raises CommandError
            with self.assertRaises(CommandError):
                call_command('reset_installation')

            # 4. Reset installation with confirm deletes lock
            call_command('reset_installation', confirm=True)
            self.assertFalse(self.lock_file.exists())
