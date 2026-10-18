import logging
from .models import AuditLog

logger = logging.getLogger('audit')

SENSITIVE_KEYS = {'password', 'password_hash', 'token', 'secret', 'pin', 'csrfmiddlewaretoken', 'key'}


def get_client_ip(request):
    """Extract client IP safely from request headers."""
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Extract user agent from request."""
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:500]


def sanitize_dict(data):
    """Recursively remove sensitive keys before writing to audit log."""
    if not isinstance(data, dict):
        return data
    sanitized = {}
    for k, v in data.items():
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            sanitized[k] = '[REDACTED]'
        elif isinstance(v, dict):
            sanitized[k] = sanitize_dict(v)
        else:
            # Ensure Decimal or datetime serializability
            sanitized[k] = str(v) if not isinstance(v, (int, float, bool, str, list, type(None))) else v
    return sanitized


def log_audit_event(
    action: str,
    actor=None,
    object_type: str = "",
    object_identifier: str = "",
    old_values: dict = None,
    new_values: dict = None,
    reason: str = "",
    request=None,
    ip_address: str = None,
    user_agent: str = "",
    tenant=None
):
    """
    Central service to record an audit log event with tenant awareness.
    """
    if request:
        if not actor and hasattr(request, 'user') and request.user.is_authenticated:
            actor = request.user
        if not tenant and hasattr(request, 'tenant'):
            tenant = request.tenant
        if not ip_address:
            ip_address = get_client_ip(request)
        if not user_agent:
            user_agent = get_user_agent(request)

    if not tenant and actor and getattr(actor, 'tenant', None):
        tenant = actor.tenant

    cleaned_old = sanitize_dict(old_values or {})
    cleaned_new = sanitize_dict(new_values or {})

    try:
        entry = AuditLog.objects.create(
            actor=actor,
            tenant=tenant,
            action=action,
            object_type=object_type,
            object_identifier=str(object_identifier),
            ip_address=ip_address,
            user_agent=user_agent,
            old_values=cleaned_old,
            new_values=cleaned_new,
            reason=reason or ""
        )
        logger.info(f"AUDIT: {entry}")
        return entry
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        return None
