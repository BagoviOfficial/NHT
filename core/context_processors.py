from .services import get_site_settings


def site_context(request):
    """
    Application-wide context variables for templates.
    Ensures consistent company information and mandatory immutable credit footer.
    """
    settings = get_site_settings()
    return {
        'SITE_SETTINGS': settings,
        'COMPANY_NAME': settings.company_name,
        'CURRENCY': settings.currency,
        'HEAD_OFFICE': settings.head_office,
        'SUPPORT_PHONE': settings.support_phone,
        'SUPPORT_EMAIL': settings.support_email,
        'FOOTER_CREDIT': 'Powered by BAGOVI TECHNOLOGIES — https://bagovi.com/',
        'FOOTER_CREDIT_HTML': 'Powered by <a href="https://bagovi.com/" target="_blank" rel="noopener noreferrer" class="text-info fw-bold">BAGOVI TECHNOLOGIES</a> — <a href="https://bagovi.com/" target="_blank" rel="noopener noreferrer" class="text-info">https://bagovi.com/</a>',
    }
