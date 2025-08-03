"""
This module provides functionality to extract information from Power of Attorney (POA) PDF documents.
It contains functions to extract specific fields from the document using a language model (LLM) and vision capabilities.
The end goal is to return a dictionary with the extracted fields and their values.
"""

from __future__ import annotations
import base64
import io
import json
import os
import pathlib
import re
from typing import Dict
from dotenv import load_dotenv
from openai import OpenAI
from pdf2image import convert_from_bytes
from modules.ocr_utils import pdf_to_text

# Fields to populate
POA_FIELDS = {
    "Title": "",
    "Document Date": "",
    "Client Name": "",
    "Governing Law (state)": "",
    "Named agent/attorney-in-law": "",
    "Summary of the document content": "",
    "Number of Pages": "",
}

# Load OPENAI API key from .env file
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# Read the LLM prompt templates
LLM_TEMPLATE = pathlib.Path("prompts/poa_extract_prompt.txt").read_text()
LLM_VISION_TEMPLATE = pathlib.Path("prompts/vision_prompt.txt").read_text()

def llm_search(text: str) -> dict:
    """
    This function sends the text to the LLM and prompts it to look for 
    the required fields in the text, if the LLM can't determine
    something it will leave it empty . It returns a dictionary with the 
    fields and their values.

    Args:
        text (str): text extracted from the PDF document.

    Returns:
        dict: A dictionary with the fields and their values.
    """
    # Prepare the prompt for the LLM, replacing placeholders with actual keys and text
    prompt = (
        LLM_TEMPLATE
        .replace("{key_list}", ", ".join(POA_FIELDS.keys()))
        .replace("{document_text}", text)
    )

    # Call the OpenAI API to get the response from the LLM
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}, # Expecting a JSON object
        temperature=0, # Deterministic output
    )
    # Parse the response and return it as a dictionary
    return json.loads(response.choices[0].message.content)

def search_date(pdf_bytes: bytes) -> str:
    """
    This function serves as backup in case the LLM cannot extract the date from the text,
    As sometimes the date is written by hand (like e-signtaure), and the LLM cannot extract it.
    It uses the vision capabilities of the LLM to extract the date from the PDF document.
    It converts the PDF pages to images, sends them to the LLM, and looks for a date in the response.

    Args:
        pdf_bytes (bytes): Raw bytes of the PDF document.

    Returns:
        str: The extracted date as a string, or an empty string if no date is found.
    """
    # Convert PDF bytes to images
    pages = convert_from_bytes(pdf_bytes, dpi=200)

    # Prepare the vision prompt for the LLM
    vision_prompt = (
        LLM_VISION_TEMPLATE
    )

    # Iterate over each image (page) and send it to the LLM
    for img in pages:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

        # Send the image and prompt to the LLM to look for the date in that page
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            max_tokens=15, 
            temperature=0,
        )
        # Extract the content from the response
        candidate = resp.choices[0].message.content.strip()

        # Use a regex to find a date in the candidate text
        DATE_RE = re.compile(
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}"
        r"|"
        r"\d{1,2}\s*[\/\-\|]\s*\d{1,2}\s*[\/\-\|]\s*\d{2,4}",
        re.I,
)
        # If a date is found, return it
        if m := DATE_RE.search(candidate):
            return m.group().strip()

    return ""


def extract_poa(file) -> Dict[str, str]:
    """
    This function extracts information from a Power of Attorney PDF document.
    It reads the PDF file, extracts the text, and then uses the LLM to search for specific fields.
    In case the first search did not find the date, it uses a vision-based search to find it.

    Args:
        file (_type_): The PDF file or path to the PDF file from which to extract information.

    Returns:
        Dict[str, str]: A dictionary containing the extracted fields and their values.
    """
    # Read the PDF file bytes
    pdf_bytes = (
        file.read() if hasattr(file, "read") else pathlib.Path(file).read_bytes()
    )

    # Extract the text and number of pages using pdf_to_text function from ocr_utils.py
    text, pages = pdf_to_text(pdf_bytes)
    data = POA_FIELDS.copy()
    # LLM search
    data.update(llm_search(text))
    # Add the number of pages to the data dictionary (this is calculated by pdf_to_text)
    data["Number of Pages"] = str(pages)

    # If the document date is empty, try to find it using a vision-based search
    if data["Document Date"] == "":
        data["Document Date"] = search_date(pdf_bytes)

    return data