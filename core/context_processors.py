from .services import get_site_settings


def site_context(request):
    """
    Application-wide context variables for templates.
    Ensures consistent company information and mandatory immutable credit footer.
    Properly scoped to the active tenant when resolved.
    """
    if hasattr(request, 'user') and request.user.is_authenticated and not request.user.is_superuser:
        tenant = getattr(request.user, 'tenant', None)
    else:
        tenant = getattr(request, 'tenant', None)

    settings = get_site_settings(tenant=tenant)

    company_name = (tenant.name if tenant else None) or settings.company_name
    currency = (tenant.currency if tenant else None) or settings.currency
    head_office = (tenant.head_office if tenant else None) or settings.head_office
    support_phone = (tenant.support_phone if tenant else None) or settings.support_phone
    support_email = (tenant.support_email if tenant else None) or settings.support_email

    return {
        'SITE_SETTINGS': settings,
        'COMPANY_NAME': company_name,
        'CURRENCY': currency,
        'HEAD_OFFICE': head_office,
        'SUPPORT_PHONE': support_phone,
        'SUPPORT_EMAIL': support_email,
        'FOOTER_CREDIT': 'Powered by BAGOVI TECHNOLOGIES — https://bagovi.com/',
        'FOOTER_CREDIT_HTML': 'Powered by <a href="https://bagovi.com/" target="_blank" rel="noopener noreferrer" class="text-info fw-bold">BAGOVI TECHNOLOGIES</a> — <a href="https://bagovi.com/" target="_blank" rel="noopener noreferrer" class="text-info">https://bagovi.com/</a>',
    }
