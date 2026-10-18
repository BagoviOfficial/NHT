import io
import qrcode
import qrcode.image.svg


def generate_tracking_qr_svg(tracking_url: str) -> str:
    """
    Generates a server-side SVG QR code pointing strictly to the public tracking URL.
    Does NOT contain sensitive internal IDs, prices, or payment info.
    """
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
        image_factory=factory
    )
    qr.add_data(tracking_url)
    qr.make(fit=True)

    img = qr.make_image()
    stream = io.BytesIO()
    img.save(stream)
    return stream.getvalue().decode('utf-8')
