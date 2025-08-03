from typing import Tuple, List, Dict
import io
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from pytesseract import Output


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


def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[Image.Image]:
    """Convierte el PDF en imágenes (una por página) a 300 dpi."""
    return convert_from_path(pdf_path, dpi=dpi, fmt="png")

def run_ocr(img: Image.Image, conf=50) -> List[Dict]:
    """Palabras con bbox + metadata básica."""
    d = pytesseract.image_to_data(img, output_type=Output.DICT)
    words = []
    for i, txt in enumerate(d["text"]):
        if txt.strip() and int(d["conf"][i]) >= conf:
            words.append(
                {
                    "text": txt.strip(),
                    "x0": d["left"][i],
                    "y0": d["top"][i],
                    "x1": d["left"][i] + d["width"][i],
                    "y1": d["top"][i] + d["height"][i],
                    "block": d["block_num"][i],
                    "par":   d["par_num"][i],
                    "line":  d["line_num"][i],
                }
            )
    return words

def cluster_lines(words):
    """Agrupa usando (block, par, line) que ya da Tesseract."""
    groups = {}
    for w in words:
        key = (w["block"], w["par"], w["line"])
        groups.setdefault(key, []).append(w)
    # ordenamos las líneas según su posición vertical promedio
    lines = sorted(groups.values(), key=lambda ln: sum(w["y0"] for w in ln)/len(ln))
    # cada línea de izq. a der.
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]
