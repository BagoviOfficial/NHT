import datetime
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from routes.models import Route
from .services import get_daily_statement_data, generate_daily_statement_pdf_bytes


@login_required
def daily_statement_view(request):
    """
    Renders daily A4 statement view for authorized staff.
    """
    if not request.user.can_view_reports:
        raise PermissionDenied("You do not have permission to view financial and daily statements.")

    date_str = request.GET.get('date')
    route_id = request.GET.get('route')

    if date_str:
        try:
            selected_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()

    if hasattr(request.user, 'tenant') and request.user.tenant:
        tenant = request.user.tenant
    elif request.user.is_superuser:
        tenant = getattr(request, 'tenant', None)
    else:
        tenant = getattr(request.user, 'tenant', None)

    data = get_daily_statement_data(selected_date, route_id=route_id, tenant=tenant)
    if tenant:
        routes = Route.objects.filter(tenant=tenant, is_active=True).order_by('name')
    else:
        routes = Route.objects.filter(is_active=True).order_by('name')

    return render(request, 'reports/daily_statement.html', {
        'data': data,
        'selected_date': selected_date,
        'selected_route_id': route_id,
        'routes': routes,
        'tenant': tenant,
        'COMPANY_NAME': data['company_name'],
        'HEAD_OFFICE': data['head_office'],
        'CURRENCY': data['currency'],
    })


@login_required
def daily_statement_pdf_view(request):
    """
    Generates downloadable or printable A4 binary PDF for the daily statement.
    """
    if not request.user.can_view_reports:
        raise PermissionDenied("You do not have permission to generate statements.")

    date_str = request.GET.get('date')
    route_id = request.GET.get('route')

    if date_str:
        try:
            selected_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()

    if hasattr(request.user, 'tenant') and request.user.tenant:
        tenant = request.user.tenant
    elif request.user.is_superuser:
        tenant = getattr(request, 'tenant', None)
    else:
        tenant = getattr(request.user, 'tenant', None)

    data = get_daily_statement_data(selected_date, route_id=route_id, tenant=tenant)
    pdf_bytes = generate_daily_statement_pdf_bytes(data)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"daily_statement_{selected_date.isoformat()}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
