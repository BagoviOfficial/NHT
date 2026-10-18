from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .services import log_audit_event


@receiver(user_logged_in)
def audit_user_logged_in(sender, request, user, **kwargs):
    log_audit_event(
        action='LOGIN_SUCCESS',
        actor=user,
        object_type='User',
        object_identifier=str(user.pk),
        reason=f"User {user.username} logged in successfully",
        request=request
    )


@receiver(user_logged_out)
def audit_user_logged_out(sender, request, user, **kwargs):
    if user:
        log_audit_event(
            action='LOGOUT',
            actor=user,
            object_type='User',
            object_identifier=str(user.pk),
            reason=f"User {user.username} logged out",
            request=request
        )


@receiver(user_login_failed)
def audit_user_login_failed(sender, credentials, request, **kwargs):
    username = credentials.get('username', 'UNKNOWN')
    log_audit_event(
        action='LOGIN_FAILED',
        actor=None,
        object_type='User',
        object_identifier=str(username),
        reason=f"Failed login attempt for username: '{username}'",
        request=request
    )
