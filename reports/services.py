from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from parcels.models import Parcel, PaymentStatus
from routes.models import Route
from core.models import SiteSettings


def get_daily_statement_data(statement_date=None, route_id=None, tenant=None):
    """
    Computes daily shipment statement figures exclusively server-side with tenant scoping.
    """
    if statement_date is None:
        statement_date = timezone.localdate()

    settings = SiteSettings.load(tenant=tenant)
    qs = Parcel.objects.filter(created_at__date=statement_date).select_related('route', 'created_by').prefetch_related('items')

    if tenant:
        qs = qs.filter(tenant=tenant)

    if route_id:
        try:
            qs = qs.filter(route_id=int(route_id))
        except (ValueError, TypeError):
            pass

    shipments = list(qs.order_by('route__name', 'created_at'))

    # Overall totals
    total_shipments = len(shipments)
    gross_total = sum((p.price for p in shipments), Decimal('0.00'))
    paid_total = sum((p.price for p in shipments if p.payment_status == PaymentStatus.PAID), Decimal('0.00'))
    cod_total = sum((p.price for p in shipments if p.payment_status == PaymentStatus.COD), Decimal('0.00'))
    unpaid_total = sum((p.price for p in shipments if p.payment_status == PaymentStatus.UNPAID), Decimal('0.00'))

    # Group by route with subtotals
    routes_summary = {}
    for p in shipments:
        r_name = p.route.name
        if r_name not in routes_summary:
            routes_summary[r_name] = {
                'route': p.route,
                'parcels': [],
                'count': 0,
                'subtotal': Decimal('0.00'),
                'paid_subtotal': Decimal('0.00'),
                'cod_subtotal': Decimal('0.00'),
                'unpaid_subtotal': Decimal('0.00'),
            }
        routes_summary[r_name]['parcels'].append(p)
        routes_summary[r_name]['count'] += 1
        routes_summary[r_name]['subtotal'] += p.price
        if p.payment_status == PaymentStatus.PAID:
            routes_summary[r_name]['paid_subtotal'] += p.price
        elif p.payment_status == PaymentStatus.COD:
            routes_summary[r_name]['cod_subtotal'] += p.price
        elif p.payment_status == PaymentStatus.UNPAID:
            routes_summary[r_name]['unpaid_subtotal'] += p.price

    company_name = (tenant.name if tenant else None) or settings.company_name
    currency = (tenant.currency if tenant else None) or settings.currency
    head_office = (tenant.head_office if tenant else None) or settings.head_office
    primary_color = (tenant.primary_color if tenant else None) or '#0d47a1'
    accent_color = (tenant.accent_color if tenant else None) or '#ff8f00'

    return {
        'statement_date': statement_date,
        'shipments': shipments,
        'routes_summary': routes_summary,
        'total_shipments': total_shipments,
        'gross_total': gross_total,
        'paid_total': paid_total,
        'cod_total': cod_total,
        'unpaid_total': unpaid_total,
        'currency': currency,
        'company_name': company_name,
        'head_office': head_office,
        'primary_color': primary_color,
        'accent_color': accent_color,
        'tenant': tenant,
    }


def clean_pdf_text(text: str) -> str:
    """Sanitize text for standard fpdf2 Helvetica font (Latin-1) to avoid FPDFUnicodeEncodingException."""
    if not text:
        return ''
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '-', '\u2026': '...', '\u00a0': ' ',
        '\u2022': '*',
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    return text.encode('latin-1', errors='replace').decode('latin-1')


def generate_daily_statement_pdf_bytes(data: dict) -> bytes:
    """
    Renders an A4 PDF document using fpdf2 with tenant dynamic branding and headings.
    """
    from fpdf import FPDF

    primary_rgb = (13, 71, 161)
    if data.get('primary_color'):
        try:
            hex_c = data['primary_color'].lstrip('#')
            if len(hex_c) == 6:
                primary_rgb = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            pass

    class StatementPDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 14)
            self.set_text_color(*primary_rgb)
            self.cell(0, 7, clean_pdf_text(data['company_name'].upper()), new_x="LMARGIN", new_y="NEXT", align='C')
            self.set_font('Helvetica', 'B', 10)
            self.set_text_color(100, 116, 139)
            self.cell(0, 5, "DAILY PARCEL WAYBILL & CONSIGNMENT STATEMENT - A4", new_x="LMARGIN", new_y="NEXT", align='C')
            self.set_font('Helvetica', '', 9)
            self.set_text_color(51, 65, 85)
            self.cell(0, 5, clean_pdf_text(f"Date: {data['statement_date']} | Origin: {data['head_office']}"), new_x="LMARGIN", new_y="NEXT", align='C')
            self.set_text_color(0, 0, 0)
            self.ln(3)

        def footer(self):
            self.set_y(-12)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, f"Page {self.page_no()}/{{nb}} | Powered by BAGOVI TECHNOLOGIES - https://bagovi.com/", align='C')

    pdf = StatementPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Column widths for landscape A4 (approx 277mm usable width)
    # Track(30), Route(25), Sender(35), Receiver(35), Items(15), Truck(25), Driver(35), PayStatus(25), Amount(25) = 250mm
    col_w = [32, 28, 38, 38, 14, 25, 35, 25, 25]

    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(240, 244, 250)
    pdf.set_text_color(15, 23, 42)
    headers = ['Tracking #', 'Route', 'Sender', 'Receiver', 'Items', 'Truck', 'Driver', 'Status', f"Price ({data['currency']})"]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 6, clean_pdf_text(h), border=1, fill=True, align='C')
    pdf.ln()

    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(0, 0, 0)
    for p in data['shipments']:
        item_count = p.items.count()
        pdf.cell(col_w[0], 5, clean_pdf_text(p.tracking_number), border=1)
        pdf.cell(col_w[1], 5, clean_pdf_text(p.route.name[:14]), border=1)
        pdf.cell(col_w[2], 5, clean_pdf_text(p.sender_name[:18]), border=1)
        pdf.cell(col_w[3], 5, clean_pdf_text(p.receiver_name[:18]), border=1)
        pdf.cell(col_w[4], 5, str(item_count), border=1, align='C')
        pdf.cell(col_w[5], 5, clean_pdf_text((p.truck_plate_number or '-')[:12]), border=1)
        pdf.cell(col_w[6], 5, clean_pdf_text((p.driver_name or '-')[:16]), border=1)
        pdf.cell(col_w[7], 5, clean_pdf_text(str(p.payment_status)), border=1, align='C')
        pdf.cell(col_w[8], 5, f"{p.price:,.2f}", border=1, align='R')
        pdf.ln()

    # Summary box
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 6, "CONSOLIDATED FINANCIAL SUMMARY", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', '', 9)
    cur = data['currency']
    summary_text = (
        f"Total Shipments: {data['total_shipments']}  |  "
        f"Gross Total: {cur} {data['gross_total']:,.2f}  |  "
        f"PAID: {cur} {data['paid_total']:,.2f}  |  "
        f"COD Outstanding: {cur} {data['cod_total']:,.2f}  |  "
        f"UNPAID: {cur} {data['unpaid_total']:,.2f}"
    )
    pdf.cell(0, 6, clean_pdf_text(summary_text), border=1, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
