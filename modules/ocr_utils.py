"""
This module provides utility functions for Optical Character Recognition (OCR) on PDF files.
    - pdf_to_text is used for extracting text from PDF files, it is used by poa_extractor.py

    - pdf_to_images converts PDF pages to images, run_ocr performs OCR on those images, 
      and cluster_lines groups words into lines based on their spatial arrangement.
      these functions are used by tax_extractor.py
"""

from typing import Tuple, List, Dict
import io
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from pytesseract import Output


def pdf_to_text(pdf_bytes: bytes) -> Tuple[str, int]:
    """
    Extracts text from a PDF file given its raw bytes.
    This function uses pdfplumber to read the PDF and extract text from each page.

    Args:
        pdf_bytes (bytes): Raw bytes of the PDF file

    Returns:
        Tuple[str, int]:
        - str: a single string containing the text extracted from the PDF
        - int: the number of pages in the PDF
    """

    # Open the PDF file using pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        # Get the number of pages in the PDF
        num_pages = len(pdf.pages)
        # Extract text from each page
        page_texts = [
            p.extract_text(x_tolerance=1, y_tolerance=1) or "" for p in pdf.pages 
        ]
    # Join the text from all pages
    plain_text = "\f".join(page_texts).strip()

    return plain_text, num_pages 


def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[Image.Image]:
    """
    Converts a PDF file to a list of images, one for each page.

    Args:
        pdf_path (str): Path to the PDF file.
        dpi (int): Dots per inch for the conversion.

    Returns:
        List[Image.Image]: A list of PIL Image objects, each representing a page of the PDF.
    """
    return convert_from_path(pdf_path, dpi=dpi, fmt="png")

def run_ocr(img: Image.Image, conf=50) -> List[Dict]:
    """
    This function runs OCR on a given image using Tesseract.
    It will extract each word from the text along with its location.
    Its location contains:
        - Bounding Box:
            - x0: left coordinate
            - y0: top coordinate
            - x1: right coordinate
            - y1: bottom coordinate
        - Position in the document:
            - block: block number
            - par: paragraph number
            - line: line number

    Args:
        img (Image.Image): The image to run OCR on.
        conf (int, optional): Confidence threshold for word recognition. 

    Returns:
        List[Dict]: A list of dictionaries, each containing the text and its location
    """

    # run OCR on the image
    d = pytesseract.image_to_data(img, output_type=Output.DICT)
    words = []
    # iterate over the words and filter by confidence
    for i, txt in enumerate(d["text"]):
        # skip empty words or those below the confidence threshold
        if txt.strip() and int(d["conf"][i]) >= conf:
            # append the word and its location box to the list
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

def cluster_lines(words: List[Dict]) -> List[List[Dict]]:
    """
Groups words into lines using their block, paragraph, 
and line numbers, ordering lines top-to-bottom and words left-to-right.

    Args:
        words (List[Dict]): List of words with their bounding box and position data.

    Returns:
        List[List[Dict]]: A list of lines, where each line is a list of words.
    """

    groups = {}
    # Group words by their block, paragraph, and line numbers
    for w in words:
        key = (w["block"], w["par"], w["line"])
        groups.setdefault(key, []).append(w)
    # Sort words within each line by their x0 position
    lines = sorted(groups.values(), key=lambda ln: sum(w["y0"] for w in ln)/len(ln))
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]
