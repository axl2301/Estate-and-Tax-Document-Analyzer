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

POA_FIELDS = {
    "Title": "",
    "Document Date": "",
    "Client Name": "",
    "Governing Law (state)": "",
    "Named agent/attorney-in-law": "",
    "Summary of the document content": "",
    "Number of Pages": "",
}

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
LLM_TEMPLATE = pathlib.Path("prompts/poa_extract_prompt.txt").read_text()
LLM_VISION_TEMPLATE = pathlib.Path("prompts/vision_prompt.txt").read_text()

def llm_pass(text: str) -> dict:
    prompt = (
        LLM_TEMPLATE
        .replace("{key_list}", ", ".join(POA_FIELDS.keys()))
        .replace("{document_text}", text)
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)

def _date_via_vision(pdf_bytes: bytes) -> str:
    """
    Crop bottom 35 % of each page, feed to GPT-4o-mini (vision) and return
    first date it reads.
    """
    pages = convert_from_bytes(pdf_bytes, dpi=200)
    vision_prompt = (
        LLM_VISION_TEMPLATE
    )

    for img in pages:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

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
        candidate = resp.choices[0].message.content.strip()

        DATE_RE = re.compile(
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}"
        r"|"
        r"\d{1,2}\s*[\/\-\|]\s*\d{1,2}\s*[\/\-\|]\s*\d{2,4}",
        re.I,
)
        if m := DATE_RE.search(candidate):
            return m.group().strip()

    return ""


def extract_poa(file) -> Dict[str, str]:
    pdf_bytes = (
        file.read() if hasattr(file, "read") else pathlib.Path(file).read_bytes()
    )
    text, pages = pdf_to_text(pdf_bytes)

    # 1️⃣  Todo se lo pedimos al LLM
    data = POA_FIELDS.copy()
    data.update(llm_pass(text))
    data["Number of Pages"] = str(pages)

    # 2️⃣  Respaldo de visión solo para la fecha, si sigue vacía
    if data["Document Date"] == "":
        data["Document Date"] = _date_via_vision(pdf_bytes)

    return data