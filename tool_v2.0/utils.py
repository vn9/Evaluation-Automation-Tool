import io
import os
import sys
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, BooleanObject, DictionaryObject
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


# PDF field names from the existing fillable forms.
pdf_info_field = "info"
pdf_repairs_field = "repair"
pdf_notes_field = "notes"


def resource_path(relative_path):
    """
    Return a file path that works both while developing
    and after packaging with PyInstaller.
    """

    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent

    return os.path.join(
        base_path,
        relative_path,
    )


def set_need_appearances(writer):
    """
    Tell PDF readers to display the updated form field values.
    """

    if "/AcroForm" in writer._root_object:
        writer._root_object[
            "/AcroForm"
        ].update(
            {
                NameObject("/NeedAppearances"):
                BooleanObject(True)
            }
        )

    else:
        writer._root_object.update(
            {
                NameObject("/AcroForm"):
                DictionaryObject(
                    {
                        NameObject("/NeedAppearances"):
                        BooleanObject(True)
                    }
                )
            }
        )


def fill_pdf_fields(
    source_pdf,
    data,
):
    """
    Open a fillable PDF and update its form fields.

    Returns a PdfWriter so gui.py can decide where to save it.
    """

    reader = PdfReader(
        str(source_pdf)
    )

    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(
            page
        )

    if (
        "/AcroForm"
        in reader.trailer["/Root"]
    ):
        writer._root_object.update(
            {
                NameObject("/AcroForm"):
                reader.trailer[
                    "/Root"
                ][
                    "/AcroForm"
                ]
            }
        )

    set_need_appearances(
        writer
    )

    for page in writer.pages:
        writer.update_page_form_field_values(
            page,
            data,
        )

    return writer


def generate_qr_image(data):
    """
    Create a QR code image in memory.

    This helper is kept from the older tool even though
    QR overlay is not currently enabled.
    """

    parts = data.split(
        "\t"
    )

    file_name = (
        parts[0].strip()
        if parts
        else "QR"
    )

    if not file_name:
        file_name = "QR"

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )

    qr.add_data(
        data
    )

    qr.make(
        fit=True
    )

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    ).convert(
        "RGB"
    )

    font = ImageFont.load_default()

    draw = ImageDraw.Draw(
        image
    )

    text_box = draw.textbbox(
        (0, 0),
        file_name,
        font=font,
    )

    text_width = (
        text_box[2]
        - text_box[0]
    )

    text_height = (
        text_box[3]
        - text_box[1]
    )

    final_image = Image.new(
        "RGB",
        (
            image.width,
            image.height
            + text_height
            + 10,
        ),
        "white",
    )

    final_image.paste(
        image,
        (0, 0),
    )

    draw = ImageDraw.Draw(
        final_image
    )

    x_position = (
        final_image.width
        - text_width
    ) // 2

    y_position = (
        image.height
        + 5
    )

    draw.text(
        (
            x_position,
            y_position,
        ),
        file_name,
        font=font,
        fill="black",
    )

    output = io.BytesIO()

    final_image.save(
        output,
        format="PNG",
    )

    output.seek(
        0
    )

    return output


def add_qr_to_existing_pdf(
    writer,
    qr_bytes,
):
    """
    Create a QR overlay for the first page.

    The final merge line remains disabled to match the older project.
    """

    if not writer.pages:
        raise ValueError(
            "No pages in PDF writer to overlay QR on."
        )

    page = writer.pages[0]

    page_width = float(
        page.mediabox.width
    )

    page_height = float(
        page.mediabox.height
    )

    qr_size = 30
    x_offset = 410
    y_offset = 684

    packet = io.BytesIO()

    pdf_canvas = canvas.Canvas(
        packet,
        pagesize=(
            page_width,
            page_height,
        ),
    )

    pdf_canvas.drawImage(
        ImageReader(
            qr_bytes
        ),
        x_offset,
        y_offset,
        width=qr_size,
        height=qr_size,
        mask="auto",
    )

    pdf_canvas.save()

    packet.seek(
        0
    )

    overlay_pdf = PdfReader(
        packet
    )

    overlay_page = (
        overlay_pdf.pages[0]
    )

    # Enable this later if QR placement is needed:
    # writer.pages[0].merge_page(overlay_page)

    return writer
