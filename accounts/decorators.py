from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from .models import Role


def role_required(*allowed_roles):
    """
    Decorator requiring the logged-in user to have one of the specified roles or be a superuser.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if not request.user.is_active:
                raise PermissionDenied("Your user account has been deactivated.")
            if request.user.is_superuser or request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "Access denied: You do not have permission to view or perform this action.")
            raise PermissionDenied("You do not have the required operational role.")
        return _wrapped_view
    return decorator


def super_admin_required(view_func):
    """Decorator requiring the user to be a Super Admin."""
    return role_required(Role.SUPER_ADMIN)(view_func)


def operations_or_admin_required(view_func):
    """Decorator requiring the user to be Super Admin or Operations Manager."""
    return role_required(Role.SUPER_ADMIN, Role.OPERATIONS_MANAGER)(view_func)
