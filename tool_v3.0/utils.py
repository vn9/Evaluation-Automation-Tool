import os
import sys
from pathlib import Path

from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, BooleanObject, DictionaryObject


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

    return os.path.join(base_path, relative_path)


def set_need_appearances(writer):
    """
    Tell PDF readers to display the updated form field values.
    """

    need_appearances = {NameObject("/NeedAppearances"): BooleanObject(True)}

    if "/AcroForm" in writer._root_object:
        writer._root_object["/AcroForm"].update(need_appearances)
    else:
        writer._root_object[NameObject("/AcroForm")] = DictionaryObject(need_appearances)


def fill_pdf_fields(source_pdf, data):
    """
    Open a fillable PDF and update its form fields.

    Returns a PdfWriter so gui.py can decide where to save it.
    """

    reader = PdfReader(str(source_pdf))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    root = reader.trailer["/Root"]

    if "/AcroForm" in root:
        writer._root_object[NameObject("/AcroForm")] = root["/AcroForm"]

    set_need_appearances(writer)

    for page in writer.pages:
        writer.update_page_form_field_values(page, data)

    return writer
