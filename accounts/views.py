from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.utils.http import url_has_allowed_host_and_scheme
from audit.services import log_audit_event, get_client_ip
from .models import User, Role
from .forms import LoginForm, UserCreateForm, UserUpdateForm, AdminPasswordResetForm
from .decorators import super_admin_required


# ==============================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def login_view(request):
    # Support destination redirection from both POST body and GET query string
    next_url = request.POST.get('next') or request.GET.get('next')
    if request.user.is_authenticated:
        # If user is already authenticated, redirect directly to safe target or dashboard
        if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)
        return redirect('dashboard')

    client_ip = get_client_ip(request) or '127.0.0.1'
    fail_cache_key = f"login_failures_{client_ip}"
    failed_attempts = cache.get(fail_cache_key, 0)

    # Brute-force protection: block after 5 failed attempts within 15 minutes
    if failed_attempts >= 5:
        messages.error(
            request,
            "Too many failed login attempts. For security reasons, please wait 15 minutes before trying again."
        )
        return render(request, 'auth/login.html', {'form': LoginForm(), 'locked': True})

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                if not user.is_active:
                    messages.error(request, "Your account has been deactivated. Please contact an administrator.")
                    return render(request, 'auth/login.html', {'form': form})

                login(request, user)
                cache.delete(fail_cache_key)
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                    return redirect(next_url)
                return redirect('dashboard')
            else:
                try:
                    candidate = User.objects.get_by_natural_key(username)
                    if candidate.check_password(password) and not candidate.is_active:
                        messages.error(request, "Your account has been deactivated. Please contact an administrator.")
                        return render(request, 'auth/login.html', {'form': form})
                except User.DoesNotExist:
                    pass

                cache.set(fail_cache_key, failed_attempts + 1, timeout=900)
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    return render(request, 'auth/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('home')


@login_required
def password_change_view(request):
    """
    Self-service password change for authenticated staff members.
    Enforces password validators, updates session auth hash, and logs audit event.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            log_audit_event(
                action='PASSWORD_CHANGE',
                actor=request.user,
                object_type='User',
                object_identifier=str(request.user.username),
                reason="User changed their account password",
                request=request
            )
            messages.success(request, "Your password has been changed successfully.")
            return redirect('dashboard')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'auth/password_change.html', {'form': form})


# ==============================================================================
# USER MANAGEMENT VIEWS (Super Admin only - Section 28)
# ==============================================================================

@super_admin_required
def user_list_view(request):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if tenant:
        users = User.objects.filter(tenant=tenant).select_related('assigned_route').order_by('-is_active', 'role', 'username')
    else:
        users = User.objects.select_related('assigned_route').all().order_by('-is_active', 'role', 'username')
    return render(request, 'admin_panel/user_list.html', {'users': users})


@super_admin_required
def user_create_view(request):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if tenant and tenant.users.count() >= tenant.max_users:
        messages.error(
            request,
            f"Staff account quota reached ({tenant.max_users} max for {tenant.get_plan_display()} plan). Please contact the platform owner to upgrade your subscription."
        )
        return redirect('admin_panel_users')

    if request.method == 'POST':
        form = UserCreateForm(request.POST, tenant=tenant)
        if form.is_valid():
            user = form.save(commit=False)
            user.tenant = tenant
            user.save()
            log_audit_event(
                action='USER_CREATE',
                actor=request.user,
                object_type='User',
                object_identifier=str(user.username),
                new_values={'username': user.username, 'role': user.role, 'phone': user.phone},
                reason=f"Created staff account {user.username}",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"Staff user '{user.username}' created successfully.")
            return redirect('admin_panel_users')
    else:
        form = UserCreateForm(tenant=tenant)
    return render(request, 'admin_panel/user_form.html', {'form': form, 'title': 'Create Staff Account'})


@super_admin_required
def user_update_view(request, pk):
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    target_user = get_object_or_404(User, pk=pk)
    if request.user.tenant and target_user.tenant_id != request.user.tenant_id:
        raise PermissionDenied("Access denied to this user account.")
    elif tenant and not request.user.is_superuser and target_user.tenant_id != tenant.id:
        raise PermissionDenied("Access denied to this user account.")

    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=target_user, tenant=tenant)
        if form.is_valid():
            new_role = form.cleaned_data.get('role')
            new_is_active = form.cleaned_data.get('is_active')
            # Protect platform and tenant integrity: prevent demoting or deactivating the sole remaining active Super Admin
            if target_user.is_superuser and (new_role != Role.SUPER_ADMIN or not new_is_active):
                active_superusers = User.objects.filter(is_superuser=True, is_active=True).exclude(pk=target_user.pk).count()
                if active_superusers == 0:
                    messages.error(request, "Cannot demote or deactivate the only remaining active Super Admin.")
                    return render(request, 'admin_panel/user_form.html', {'form': form, 'target_user': target_user, 'title': f'Edit User {target_user.username}'})

            old_vals = {'role': form.initial.get('role'), 'is_active': form.initial.get('is_active')}
            form.save()
            new_vals = {'role': form.cleaned_data.get('role'), 'is_active': form.cleaned_data.get('is_active')}
            log_audit_event(
                action='USER_UPDATE',
                actor=request.user,
                object_type='User',
                object_identifier=str(target_user.username),
                old_values=old_vals,
                new_values=new_vals,
                reason="Updated staff user record",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"User '{target_user.username}' updated.")
            return redirect('admin_panel_users')
    else:
        form = UserUpdateForm(instance=target_user, tenant=tenant)

    return render(request, 'admin_panel/user_form.html', {'form': form, 'target_user': target_user, 'title': f'Edit User {target_user.username}'})


@super_admin_required
def user_toggle_active_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if request.user.tenant and target_user.tenant_id != request.user.tenant_id:
        raise PermissionDenied("Access denied to this user account.")
    elif tenant and not request.user.is_superuser and target_user.tenant_id != tenant.id:
        raise PermissionDenied("Access denied to this user account.")

    if request.method == 'POST':
        if target_user.pk == request.user.pk:
            messages.error(request, "You cannot deactivate your own administrative account.")
            return redirect('admin_panel_users')

        if target_user.is_superuser and target_user.is_active:
            active_superusers = User.objects.filter(is_superuser=True, is_active=True).exclude(pk=target_user.pk).count()
            if active_superusers == 0:
                messages.error(request, "Cannot deactivate the only active Super Admin.")
                return redirect('admin_panel_users')

        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=['is_active'])

        log_audit_event(
            action='USER_TOGGLE_ACTIVE',
            actor=request.user,
            object_type='User',
            object_identifier=str(target_user.username),
            new_values={'is_active': target_user.is_active},
            reason="Toggled user active state",
            request=request,
            tenant=tenant
        )
        status_text = "activated" if target_user.is_active else "deactivated"
        messages.success(request, f"User '{target_user.username}' {status_text}.")
    return redirect('admin_panel_users')


@super_admin_required
def user_password_reset_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
    if request.user.tenant and target_user.tenant_id != request.user.tenant_id:
        raise PermissionDenied("Access denied to this user account.")
    elif tenant and not request.user.is_superuser and target_user.tenant_id != tenant.id:
        raise PermissionDenied("Access denied to this user account.")

    if request.method == 'POST':
        form = AdminPasswordResetForm(request.POST)
        if form.is_valid():
            target_user.set_password(form.cleaned_data['new_password'])
            target_user.save()
            log_audit_event(
                action='PASSWORD_RESET',
                actor=request.user,
                object_type='User',
                object_identifier=str(target_user.username),
                reason=f"Administrator reset password for {target_user.username}",
                request=request,
                tenant=tenant
            )
            messages.success(request, f"Password for '{target_user.username}' has been successfully reset.")
            return redirect('admin_panel_users')
    else:
        form = AdminPasswordResetForm()

    return render(request, 'admin_panel/password_reset.html', {'form': form, 'target_user': target_user})
