"""QR code generator with logo overlay for referral links."""

import io
from pathlib import Path
import qrcode
from PIL import Image


async def generate_qr_with_logo(referral_url: str, logo_path: str = None) -> io.BytesIO:
    """Generate QR code with optional logo overlay.

    Args:
        referral_url: The URL to encode in QR code
        logo_path: Optional path to logo image for overlay

    Returns:
        BytesIO object containing PNG image
    """
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(referral_url)
    qr.make(fit=True)

    # Generate image
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.convert("RGB")

    # Add logo if provided
    if logo_path and Path(logo_path).exists():
        try:
            logo = Image.open(logo_path)

            # Calculate logo size (10% of QR code)
            qr_width, qr_height = img.size
            logo_size = min(qr_width, qr_height) // 10

            # Resize logo
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

            # Create white background for logo
            logo_bg = Image.new("RGB", (logo_size + 20, logo_size + 20), "white")
            logo_bg.paste(logo, (10, 10))

            # Calculate position (center)
            pos_x = (qr_width - logo_size) // 2
            pos_y = (qr_height - logo_size) // 2

            # Paste logo
            img.paste(logo_bg, (pos_x - 10, pos_y - 10))
        except Exception:
            pass

    # Save to BytesIO
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)

    return output


async def generate_qr_simple(referral_url: str) -> io.BytesIO:
    """Generate simple QR code without logo.

    Args:
        referral_url: The URL to encode in QR code

    Returns:
        BytesIO object containing PNG image
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(referral_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)

    return output
