from typing import Tuple
import io
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract

def pdf_to_text(pdf_bytes: bytes) -> Tuple[str, int]:
    """
    Args:
        pdf_bytes (bytes): Raw bytes of the PDF file

    Returns:
        Tuple[str, int]:
        - str: a single string containing the text extracted from the PDF
        - int: the number of pages in the PDF
    """

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        num_pages = len(pdf.pages)
        page_texts = [
            p.extract_text(x_tolerance=1, y_tolerance=1) or "" for p in pdf.pages
        ]

    plain_text = "\f".join(page_texts).strip()

    return plain_text, num_pages 


def pdf_to_ocr_text(pdf_bytes: bytes, dpi: int = 300) -> Tuple[str, int]:
    """
    Render each page at `dpi`, run pytesseract, return full text + page-count.
    """
    images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="png")     # fast, lossless
    texts  = [pytesseract.image_to_string(img) for img in images]
    return "\n".join(texts), len(images)