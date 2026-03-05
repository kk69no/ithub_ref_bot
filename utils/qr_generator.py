"""
Генерация QR-кодов с логотипом IThub.
"""
import io
import os
import qrcode
from qrcode.image.styledpil import StyledPilImage
from PIL import Image

from config import QR_SIZE, QR_LOGO_PATH


def generate_qr(data: str) -> io.BytesIO:
    """
    Сгенерировать QR-код PNG с логотипом по центру (если файл есть).
    Возвращает BytesIO с изображением.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # высокая коррекция для логотипа
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)

    # Наложить логотип, если файл существует
    if os.path.exists(QR_LOGO_PATH):
        try:
            logo = Image.open(QR_LOGO_PATH).convert("RGBA")
            logo_max = QR_SIZE // 5  # ~20% от QR
            logo.thumbnail((logo_max, logo_max), Image.LANCZOS)
            pos = ((QR_SIZE - logo.size[0]) // 2, (QR_SIZE - logo.size[1]) // 2)
            img.paste(logo, pos, mask=logo)
        except Exception:
            pass  # если логотип битый — просто без него

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
