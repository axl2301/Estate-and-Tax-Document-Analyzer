"""
This module provides functionality to extract specific amounts from a PDF document.
It contains functions to convert the PDF to images, run OCR on those images,
and extract amounts based on defined field IDs.
The end goal is to return a dictionary with the extracted amounts
"""

import re
from modules.ocr_utils import pdf_to_images, run_ocr, cluster_lines
from typing import List, Dict


# ID's to look for in the PDF
FIELDS   = ["4","7","10","14","15","16","17"]
# Regex to match numbers, including commas and decimal points
NUMTOK   = re.compile(r"^[\d,.\-]+$")
# Thresholds for position of tokens in the line
POS_TH   = 0.60 # threshold for the right side of the line
LEFT_TH  = 0.40 # threshold for the left side of the line


def normal(txt: str) -> str:
    """
    Normalize a string by converting it to lowercase and removing trailing
    Args:
        txt (str): Text to normalize.

    Returns:
        str: Normalized text.
    """
    return re.sub(r"[|,.\]\)\(:;{}\s]+$", "", txt.lower())

def extract_amounts_from_lines(lines: List[List[Dict]]) -> Dict[str, int]:
    """
    This function extracts amounts from lines of text in a PDF document.
    It looks for specific fields (IDs) and extracts the corresponding amounts
    by searching for numbers that look like proper amounts to the right of those fields.

    Args:
        lines (List[List[Dict]]): List of lines, each containing a list of words with their bounding box and position data.

    Returns:
        Dict[str, int]: A dictionary mapping field IDs to their extracted amounts.
    """

    # Initialize result dictionary with field IDs set to 0
    res    = {fid: 0 for fid in FIELDS}
    # Calculate the maximum width of the page based on the words bounding boxes
    page_w = max(w["x1"] for ln in lines for w in ln)

    # Iterate through each line of words
    for i, ln in enumerate(lines):
        # Look for a valid ID token in the line and validate its position
        id_tok = next(
            (w for w in ln
             if normal(w["text"]) in FIELDS
             and w["x0"] <= LEFT_TH * page_w),
            None
        )
        # If no valid ID token is found, skip to the next line
        if not id_tok:
            continue
        fid = normal(id_tok["text"])
        # In case the ID was already found in a previous line, skip it
        if res[fid] != 0:
            continue  

        # Select words to the right of the ID token
        tail = [w for w in ln if w["x0"] > id_tok["x1"]]
        nums = []
        # Iterate through the words to the right of the ID token (in reverse)
        for w in reversed(tail):
            # Stop if the word is too far to the left
            if w["x0"] <= POS_TH * page_w:
                if nums: 
                    break
                continue
            # Check if the word matches the number token regex
            if not NUMTOK.match(w["text"]):
                if nums: 
                    break
                continue
            # Accepts if the number checks out
            digits = re.sub(r"\D", "", w["text"])
            if nums or "," in w["text"] or len(digits) >= 3:
                nums.insert(0, w)

        # Look-ahead in case the ID token was not followed by a number
        # It will look on the next lines until it finds a valid number or other ID token
        if not nums:
            for j in range(i+1, len(lines)):
                # If the next line has an ID token, stop looking
                if any(
                    normal(x["text"]) in FIELDS
                    and x["x0"] <= LEFT_TH * page_w
                    for x in lines[j]
                ):
                    break
                # Otherwise, look for numbers in the next line the same way as before
                for w in reversed(lines[j]):
                    if w["x0"] <= POS_TH * page_w:
                        if nums: 
                            break
                        continue
                    if not NUMTOK.match(w["text"]):
                        if nums: 
                            break
                        continue
                    digits = re.sub(r"\D", "", w["text"])
                    if nums or "," in w["text"] or len(digits) >= 3:
                        nums.insert(0, w)
                if nums:
                    break

        # concatenate the text of the found numbers and clean it up
        raw   = "".join(w["text"] for w in nums)
        clean = re.sub(r"[^\d\-]", "", raw)
        res[fid] = int(clean) if clean else 0

    return res

def extract_tax(pdf_path: str) -> Dict[str, int]:
    """
    This function extracts amounts from a PDF document.
    It first converts the PDF to images, then runs OCR
    to extract words, clusters the words into lines, and finally
    extracts amounts from those lines based on specific field IDs.

    Args:
        pdf_path (str): Path to the PDF file from which to extract amounts.

    Returns:
        Dict[str, int]: A dictionary mapping field IDs to their extracted amounts.
    """
    # Convert the first page of the PDF to an image
    # In this case there is only one page, but a loop could be used to process multiple pages 
    img   = pdf_to_images(pdf_path)[0]
    # Run OCR on the image to extract words with their location 
    words = run_ocr(img)
    # Cluster the words into lines based on their spatial arrangement
    lines = cluster_lines(words)
    # Extract amounts from the clustered lines based on the defined field IDs
    return extract_amounts_from_lines(lines)
