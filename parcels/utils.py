import io
import base64
import qrcode
import qrcode.image.svg
from .models import ShippingRate


def generate_qr_base64(data: str) -> str:
    """Generates a base64 encoded SVG data URL for a given string without Pillow dependency."""
    try:
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(data, image_factory=factory, box_size=8, border=2)
        buffered = io.BytesIO()
        img.save(buffered)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/svg+xml;base64,{img_str}"
    except Exception as e:
        return ""



def generate_svg_barcode(code: str) -> str:
    """
    Generates a clean vector SVG barcode (Code 128 style visual representation)
    suitable for high-resolution printing on labels and waybills.
    """
    code_clean = str(code).upper()
    bars = []
    x = 10
    height = 50
    seed = sum(ord(c) for c in code_clean)
    
    # Generate distinct bar widths based on input hash & chars
    pattern = []
    for i, char in enumerate(code_clean):
        val = ord(char) + (seed * (i + 1))
        p1 = (val % 3) + 1
        p2 = ((val >> 2) % 3) + 1
        p3 = ((val >> 4) % 3) + 1
        pattern.extend([p1, p2, p3, 2])
        
    for idx, width in enumerate(pattern):
        # alternate black and white bars
        if idx % 2 == 0:
            bars.append(f'<rect x="{x}" y="5" width="{width * 1.8:.1f}" height="{height}" fill="#111827" />')
        x += width * 1.8 + 1.2

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {int(x + 15)} 75" class="w-full h-auto max-h-16">
        <g>{''.join(bars)}</g>
        <text x="{int(x / 2)}" y="70" text-anchor="middle" font-family="monospace" font-size="12" font-weight="bold" fill="#374151" letter-spacing="3">{code_clean}</text>
    </svg>'''
    return svg


def calculate_shipping_cost(service_type='STANDARD', weight_kg=1.0, length_cm=10, width_cm=10, height_cm=10, is_fragile=False, declared_value=0.0):
    """Calculates granular pricing based on active ShippingRate table."""
    try:
        rate = ShippingRate.objects.get(service_type=service_type)
    except ShippingRate.DoesNotExist:
        # default fallback rates
        rates_map = {
            'STANDARD': (5.00, 2.50, 4.00, 1.5, 5.0),
            'EXPRESS': (12.00, 4.00, 6.00, 1.5, 5.0),
            'SAME_DAY': (25.00, 6.50, 8.00, 1.5, 5.0),
        }
        b, p, f, ins, t = rates_map.get(service_type, (5.0, 2.5, 4.0, 1.5, 5.0))
        base = b
        per_kg = p
        fragile_fee = f if is_fragile else 0.0
        ins_pct = ins / 100.0
        tax_pct = t / 100.0
    else:
        base = float(rate.base_price)
        per_kg = float(rate.per_kg_rate)
        fragile_fee = float(rate.fragile_fee) if is_fragile else 0.0
        ins_pct = float(rate.insurance_rate_pct) / 100.0
        tax_pct = float(rate.tax_pct) / 100.0

    vol_weight = (float(length_cm) * float(width_cm) * float(height_cm)) / 5000.0
    billable_weight = max(float(weight_kg), vol_weight)

    weight_price = round(billable_weight * per_kg, 2)
    insurance_fee = round(float(declared_value) * ins_pct, 2)
    subtotal = round(base + weight_price + fragile_fee + insurance_fee, 2)
    tax_amount = round(subtotal * tax_pct, 2)
    total_price = round(subtotal + tax_amount, 2)

    return {
        'base_price': base,
        'weight_price': weight_price,
        'fragile_fee': fragile_fee,
        'insurance_fee': insurance_fee,
        'tax_amount': tax_amount,
        'subtotal': subtotal,
        'total_price': total_price,
        'billable_weight': round(billable_weight, 2),
        'volumetric_weight': round(vol_weight, 2),
    }
