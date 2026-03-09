import os, sys
import io
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, BooleanObject, DictionaryObject
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from PIL import Image, ImageDraw, ImageFont

# ------------------------ QR CODE FUNCTION ------------------------

def generate_qr_image(data: str) -> io.BytesIO:
    parts = data.split("\t")
    filename = parts[0].strip() or "QR"

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    font = ImageFont.load_default()
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), filename, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    new_img = Image.new("RGB", (img.width, img.height + text_height + 10), "white")
    new_img.paste(img, (0, 0))

    draw = ImageDraw.Draw(new_img)
    x = (new_img.width - text_width) // 2
    y = img.height + 5
    draw.text((x, y), filename, font=font, fill="black")

    out = io.BytesIO()
    new_img.save(out, format="PNG")
    out.seek(0)
    return out

# ----------------------------- CONFIG -----------------------------

PDF_INFO_FIELD = "info"
PDF_REPAIRS_FIELD = "repair"
PDF_ITEMS_FIELD = "notes"


def resource_path(relative_path: str) -> str:
    """Get bundled resource path (works with PyInstaller)."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent
    return os.path.join(base_path, relative_path)


# --------------------------- PDF FUNCTIONS ---------------------------

def set_need_appearances(writer: PdfWriter):
    if "/AcroForm" in writer._root_object:
        writer._root_object["/AcroForm"].update(
            {NameObject("/NeedAppearances"): BooleanObject(True)}
        )
    else:
        writer._root_object.update({
            NameObject("/AcroForm"): DictionaryObject({
                NameObject("/NeedAppearances"): BooleanObject(True)
            })
        })


def fill_pdf_fields(src_pdf: Path, data: dict):
    reader = PdfReader(str(src_pdf))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    if "/AcroForm" in reader.trailer["/Root"]:
        writer._root_object.update({
            NameObject("/AcroForm"): reader.trailer["/Root"]["/AcroForm"]
        })

    set_need_appearances(writer)

    for page in writer.pages:
        writer.update_page_form_field_values(page, data)

    #with open(dst_pdf, "wb") as f:
        #writer.write(f)
    return writer


def add_qr_to_existing_pdf(writer: PdfWriter, qr_bytes: io.BytesIO):
    """Overlay QR code onto existing filled PDF."""

    if not writer.pages:
        raise ValueError("No pages in PDF writer to overlay QR on.")

    # page coordinate info
    page = writer.pages[0]
    media_box = page.mediabox
    page_width = float(media_box.width)
    page_height = float(media_box.height)

    qr_size = 30
    x_offset = 410
    y_offset = 684

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
    can.drawImage(
        ImageReader(qr_bytes), x_offset, y_offset,
        width=qr_size, height=qr_size, mask='auto'
    )
    can.save()
    packet.seek(0)

    overlay_pdf = PdfReader(packet)
    overlay_page = overlay_pdf.pages[0]
    #writer.pages[0].merge_page(overlay_page)

    #with open(pdf_path, "wb") as f:
        #writer.write(f)

    return writer
