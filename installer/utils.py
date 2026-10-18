import sys
import os
import platform
import sqlite3
from pathlib import Path
from django.conf import settings
from django.db import connection
from django.core.management import call_command
from django.contrib.auth import get_user_model
from tenants.models import Tenant, TenantPlan
from tenants.services import provision_tenant
from audit.services import log_audit_event

User = get_user_model()


def get_lock_file() -> Path:
    """Returns the Path to the installation lock file."""
    return getattr(settings, 'INSTALLER_LOCK_FILE', settings.BASE_DIR / '.installed')


def is_system_installed() -> bool:
    """
    Checks if the system has already completed the initial installation.
    The system is considered installed if:
    1. The .installed lock file exists, OR
    2. An active superuser and an active tenant already exist in the database.
    """
    lock = get_lock_file()
    if lock.exists():
        return True
    try:
        has_superuser = User.objects.filter(is_superuser=True).exists()
        has_tenant = Tenant.objects.filter(is_active=True).exists()
        if has_superuser and has_tenant:
            # Recreate lock file if missing for consistency
            try:
                lock.write_text("System installed.\n")
            except (IOError, PermissionError):
                pass
            return True
    except Exception:
        # Table might not exist yet before migrations
        return False
    return False


def test_database_connection(engine='postgresql', name='', user='', password='', host='localhost', port='5432') -> tuple[bool, str]:
    """
    Dynamically tests connectivity to a specified database (PostgreSQL or SQLite).
    Returns (success_boolean, status_message).
    """
    engine_lower = (engine or 'postgresql').lower().strip()
    if 'sqlite' in engine_lower:
        db_path = Path(name) if name else settings.BASE_DIR / 'db.sqlite3'
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            conn.close()
            return True, f"SQLite database accessible at '{db_path}'."
        except Exception as e:
            return False, f"SQLite database test failed: {str(e)}"
    else:
        # PostgreSQL
        try:
            import psycopg
            db_name = name or settings.DATABASES['default'].get('NAME', 'parcel_db')
            db_user = user or settings.DATABASES['default'].get('USER', 'postgres')
            db_host = host or settings.DATABASES['default'].get('HOST', 'localhost')
            db_port = port or settings.DATABASES['default'].get('PORT', '5432')
            db_pwd = password if password is not None else settings.DATABASES['default'].get('PASSWORD', '')

            conn_parts = [
                f"dbname={db_name}",
                f"user={db_user}",
                f"host={db_host}",
                f"port={db_port}",
                "connect_timeout=3"
            ]
            if db_pwd:
                conn_parts.append(f"password={db_pwd}")
            conn_info = " ".join(conn_parts)

            with psycopg.connect(conn_info) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return True, f"Successfully connected to PostgreSQL database '{db_name}' on {db_host}:{db_port}."
        except Exception as e:
            return False, f"PostgreSQL connection failed: {str(e)}"


def update_env_database_settings(engine='postgresql', name='', user='', password='', host='localhost', port='5432') -> bool:
    """
    Persists updated database configuration to the project's .env file.
    """
    env_path = settings.BASE_DIR / '.env'
    lines = []
    if env_path.exists():
        try:
            lines = env_path.read_text().splitlines()
        except Exception:
            lines = []

    use_sqlite = 'True' if 'sqlite' in (engine or '').lower() else 'False'
    new_vars = {
        'DB_NAME': name or 'parcel_db',
        'DB_USER': user or 'postgres',
        'DB_PASSWORD': password or '',
        'DB_HOST': host or 'localhost',
        'DB_PORT': str(port or '5432'),
        'USE_SQLITE': use_sqlite,
    }

    found = set()
    updated_lines = []
    for line in lines:
        stripped = line.strip()
        matched = False
        for k, v in new_vars.items():
            if stripped.startswith(f"{k}=") or stripped.startswith(f"export {k}="):
                updated_lines.append(f"{k}={v}")
                found.add(k)
                matched = True
                break
        if not matched:
            updated_lines.append(line)

    for k, v in new_vars.items():
        if k not in found:
            updated_lines.append(f"{k}={v}")

    try:
        env_path.write_text('\n'.join(updated_lines) + '\n')
        return True
    except Exception:
        return False


def get_system_readiness_checks() -> dict:
    """
    Performs comprehensive pre-flight health checks (like WordPress Famous 5-minute install checks):
    - Python runtime version
    - Database connectivity & engine
    - Storage writeability
    - Critical Python dependencies
    """
    checks = []
    all_passed = True

    # 1. Python Version Check (>= 3.11 required)
    py_ver = sys.version_info
    py_ver_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    py_ok = py_ver >= (3, 11)
    checks.append({
        'name': 'Python Runtime Environment',
        'required': 'Python 3.11+ (Recommended: Python 3.12+)',
        'current': f"Python {py_ver_str} ({platform.system()} {platform.machine()})",
        'passed': py_ok,
        'badge': 'Pass' if py_ok else 'Fail',
        'details': 'Meets production runtime specifications.' if py_ok else 'Please upgrade Python.'
    })
    if not py_ok:
        all_passed = False

    # 2. Database Connectivity
    db_ok = False
    db_details = ""
    db_engine = settings.DATABASES['default']['ENGINE'].split('.')[-1]
    db_name = settings.DATABASES['default'].get('NAME', 'database')
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row and row[0] == 1:
                db_ok = True
                db_details = f"Successfully connected to {db_engine} database: '{db_name}'"
    except Exception as e:
        db_details = f"Connection failed: {str(e)}"

    checks.append({
        'name': 'Database Connectivity',
        'required': 'PostgreSQL 16+ (or SQLite development mode)',
        'current': f"{db_engine.upper()}",
        'passed': db_ok,
        'badge': 'Pass' if db_ok else 'Fail',
        'details': db_details
    })
    if not db_ok:
        all_passed = False

    # 3. Storage Write Permissions
    storage_ok = False
    test_path = settings.BASE_DIR / '.write_test_tmp'
    try:
        test_path.write_text("ok")
        if test_path.read_text() == "ok":
            storage_ok = True
        test_path.unlink(missing_ok=True)
    except Exception:
        storage_ok = False

    checks.append({
        'name': 'Filesystem Write Permissions',
        'required': 'Writable project directory for logs, cache & receipt QR SVGs',
        'current': f"{settings.BASE_DIR}",
        'passed': storage_ok,
        'badge': 'Pass' if storage_ok else 'Fail',
        'details': 'Application has write permissions to store local data and configurations.' if storage_ok else 'Directory is not writable.'
    })
    if not storage_ok:
        all_passed = False

    # 4. Critical Dependencies Check
    deps = [
        ('django', 'Django Web Framework'),
        ('environ', 'Environment Variable Manager (django-environ)'),
        ('qrcode', 'Vector QR Code Generation'),
        ('fpdf', 'A4 PDF Statement Engine (fpdf2)'),
    ]
    missing_deps = []
    for mod_name, label in deps:
        try:
            __import__(mod_name)
        except ImportError:
            missing_deps.append(label)

    deps_ok = len(missing_deps) == 0
    checks.append({
        'name': 'Required Core Libraries',
        'required': 'Django, django-environ, qrcode, fpdf2',
        'current': 'All present' if deps_ok else f"Missing: {', '.join(missing_deps)}",
        'passed': deps_ok,
        'badge': 'Pass' if deps_ok else 'Fail',
        'details': 'Core libraries installed and verified.' if deps_ok else 'Some packages are missing from requirements.txt.'
    })
    if not deps_ok:
        all_passed = False

    return {
        'checks': checks,
        'all_passed': all_passed,
        'db_engine': db_engine,
        'py_version': py_ver_str
    }


def execute_wordpress_style_installation(
    platform_title: str,
    admin_username: str,
    admin_password: str,
    admin_phone: str,
    admin_email: str,
    tenant_name: str,
    tenant_prefix: str,
    tenant_slug: str = '',
    head_office: str = 'Nairobi',
    currency: str = 'KES',
    support_phone: str = '',
    support_email: str = '',
    primary_color: str = '#0d47a1',
    accent_color: str = '#ff8f00',
    starter_routes: list = None,
    plan: str = TenantPlan.PROFESSIONAL,
    request=None
) -> dict:
    """
    Executes the full automated setup pipeline:
    1. Runs database migrations (idempotent).
    2. Creates or elevates Global SaaS Platform Owner.
    3. Provisions primary client organization with starter routes and categories.
    4. Writes .installed lock file to permanently secure the installer.
    5. Records SYSTEM_INSTALLATION audit log.
    """
    # 1. Apply migrations if any are unapplied
    call_command('migrate', interactive=False)

    # 2. Create Global Platform Super Admin (No tenant, is_superuser=True)
    platform_admin = User.objects.filter(username=admin_username).first()
    if platform_admin:
        platform_admin.set_password(admin_password)
        platform_admin.phone = admin_phone
        platform_admin.email = admin_email
        platform_admin.role = 'SUPER_ADMIN'
        platform_admin.is_superuser = True
        platform_admin.is_staff = True
        platform_admin.is_active = True
        platform_admin.tenant = None
        platform_admin.save()
    else:
        platform_admin = User.objects.create_superuser(
            username=admin_username,
            password=admin_password,
            phone=admin_phone,
            email=admin_email,
            role='SUPER_ADMIN',
            tenant=None
        )

    # 3. Provision Primary Tenant Enterprise
    if starter_routes is None:
        starter_routes = [
            'Garissa', 'Wajir', 'Kotulo Drop-off',
            'Elwak', 'Rhamu', 'Lafey', 'Arabia', 'Mandera'
        ]

    # Ensure tenant admin phone is unique and doesn't conflict with platform admin phone
    tenant_admin_phone = support_phone or ''
    if not tenant_admin_phone or tenant_admin_phone == admin_phone or User.objects.filter(phone=tenant_admin_phone).exists():
        candidate_prefix = "079"
        candidate = f"{candidate_prefix}{admin_phone[-7:]}" if len(admin_phone) >= 7 else "0799999999"
        if candidate == admin_phone or User.objects.filter(phone=candidate).exists():
            for i in range(2, 1000):
                alt = f"078800{i:04d}"
                if not User.objects.filter(phone=alt).exists():
                    candidate = alt
                    break
        tenant_admin_phone = candidate

    tenant_result = provision_tenant(
        name=tenant_name,
        slug=tenant_slug or None,
        tracking_prefix=tenant_prefix,
        head_office=head_office,
        currency=currency,
        support_phone=support_phone or admin_phone,
        support_email=support_email or admin_email,
        admin_username=f"{tenant_slug or 'primary'}_admin",
        admin_phone=tenant_admin_phone,
        admin_email=f"admin@{tenant_slug or 'client'}.co.ke",
        admin_password=admin_password,  # Initial tenant admin uses the same password for convenience
        plan=plan,
        primary_color=primary_color,
        accent_color=accent_color,
        starter_routes=starter_routes,
        actor=platform_admin,
        request=request
    )

    primary_tenant = tenant_result['tenant']

    # 4. Lock the installer
    lock = get_lock_file()
    try:
        lock.write_text(
            f"Installed on {platform.node()} by {admin_username} for {tenant_name}.\n"
        )
    except Exception:
        pass

    # Reset in-memory cache on redirect middleware so normal routes are immediately unlocked
    try:
        from .middleware import InstallationRedirectMiddleware
        InstallationRedirectMiddleware.reset_installed_cache()
    except Exception:
        pass

    # 5. Log System Installation Audit Event
    log_audit_event(
        actor=platform_admin,
        action='SYSTEM_INSTALLATION',
        object_type='System',
        object_identifier='Global',
        new_values={
            'platform_title': platform_title,
            'platform_admin': platform_admin.username,
            'primary_tenant': primary_tenant.name,
            'tracking_prefix': primary_tenant.tracking_prefix,
            'plan': primary_tenant.plan,
        },
        reason="Initial system deployment completed via WordPress-Style Web Installer",
        request=request,
        tenant=primary_tenant
    )

    return {
        'platform_admin': platform_admin,
        'primary_tenant': primary_tenant,
        'tenant_admin': tenant_result['admin_user'],
        'raw_password': admin_password,
    }
