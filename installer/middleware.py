from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from .utils import is_system_installed


class InstallationRedirectMiddleware:
    """
    WordPress-Style Installation Redirect Middleware.
    When the system has not yet been installed:
    - Any incoming request to any non-installer page is automatically redirected
      to the setup wizard (/install/).
    - Whitelisted endpoints:
      - /install/ and /setup/ (wizard and health check endpoints)
      - /static/ and /media/ (assets)
      - /favicon.ico
    Once the system is installed, this middleware immediately passes through
    with zero disk I/O and zero database queries thanks to in-memory caching.
    """
    _installed_cached = False

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not InstallationRedirectMiddleware._installed_cached:
            if is_system_installed():
                InstallationRedirectMiddleware._installed_cached = True
            else:
                path = request.path_info
                # Allowed paths during pre-installation state
                is_exempt = (
                    path.startswith('/install/') or
                    path.startswith('/setup/') or
                    path.startswith('/static/') or
                    path.startswith('/media/') or
                    path == '/favicon.ico'
                )
                if not is_exempt:
                    return redirect('installer')

        return self.get_response(request)

    @classmethod
    def reset_installed_cache(cls):
        """Resets the cached installed status (used during installation and in tests)."""
        cls._installed_cached = False
