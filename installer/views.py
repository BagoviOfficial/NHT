import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from .utils import (
    is_system_installed,
    get_system_readiness_checks,
    execute_wordpress_style_installation,
    test_database_connection,
    update_env_database_settings,
)
from .forms import WordPressStyleInstallForm


def installer_view(request):
    """
    WordPress-Like Famous 1-Screen Setup Wizard (/install/ or /setup/).
    Allows fresh deployments to test system readiness, configure database admin,
    and establish the primary courier enterprise in minutes.
    Once installed, this endpoint is permanently locked for security.
    """
    # 1. Lockout check (strictly prevent rerun once system is deployed)
    if is_system_installed():
        return render(request, 'installer/already_installed.html', status=200)

    # 2. System readiness checks
    readiness = get_system_readiness_checks()

    if request.method == 'POST':
        form = WordPressStyleInstallForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            starter_routes_raw = data.get('starter_routes', '')
            starter_routes = [r.strip() for r in starter_routes_raw.split(',') if r.strip()] if starter_routes_raw else None

            try:
                result = execute_wordpress_style_installation(
                    platform_title=data['platform_title'],
                    admin_username=data['admin_username'],
                    admin_password=data['admin_password'],
                    admin_phone=data['admin_phone'],
                    admin_email=data['admin_email'],
                    tenant_name=data['company_name'],
                    tenant_prefix=data['tracking_prefix'],
                    tenant_slug=data.get('slug') or '',
                    head_office=data['head_office'],
                    currency=data['currency'],
                    primary_color=data.get('primary_color', '#0d47a1'),
                    accent_color=data.get('accent_color', '#ff8f00'),
                    starter_routes=starter_routes,
                    request=request
                )

                messages.success(request, "Installation completed successfully! Welcome to your new Parcel Logistics Platform.")
                return render(request, 'installer/step4_finish.html', {
                    'platform_admin': result['platform_admin'],
                    'primary_tenant': result['primary_tenant'],
                    'tenant_admin': result['tenant_admin'],
                    'raw_password': result['raw_password'],
                    'platform_title': data['platform_title'],
                })
            except ValidationError as e:
                msg = e.message if hasattr(e, 'message') else str(e)
                messages.error(request, msg)
            except Exception as e:
                messages.error(request, f"Installation encountered an unexpected error: {e}")
    else:
        form = WordPressStyleInstallForm()

    return render(request, 'installer/step1_welcome_checks.html', {
        'form': form,
        'readiness': readiness,
    })


def installer_health_check_api(request):
    """JSON API endpoint returning live system diagnostics."""
    readiness = get_system_readiness_checks()
    return JsonResponse({
        'installed': is_system_installed(),
        'all_passed': readiness['all_passed'],
        'checks': readiness['checks'],
        'py_version': readiness['py_version'],
        'db_engine': readiness['db_engine'],
    })


def installer_test_db_api(request):
    """
    POST API endpoint for testing database connectivity dynamically
    from the installer wizard (like WordPress wp-config setup test).
    """
    if is_system_installed():
        return JsonResponse({'success': False, 'message': 'System already installed and locked.'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            payload = request.POST.dict()
    except Exception:
        payload = {}

    engine = payload.get('engine', 'postgresql')
    name = payload.get('name', '')
    user = payload.get('user', '')
    password = payload.get('password', '')
    host = payload.get('host', 'localhost')
    port = payload.get('port', '5432')
    save_to_env = payload.get('save_to_env', False) in (True, 'true', '1')

    success, message = test_database_connection(
        engine=engine,
        name=name,
        user=user,
        password=password,
        host=host,
        port=port
    )

    saved = False
    if success and save_to_env:
        saved = update_env_database_settings(
            engine=engine,
            name=name,
            user=user,
            password=password,
            host=host,
            port=port
        )
        if saved:
            message += " Database settings were saved to .env."

    return JsonResponse({
        'success': success,
        'message': message,
        'saved': saved
    })
