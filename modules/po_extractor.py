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

# ---------------------------------------------------------------------
# 🔧  Constants
# ---------------------------------------------------------------------
POA_FIELDS = {
    "title": "",
    "document_date": "",
    "client_name": "",
    "governing_law": "",
    "agent_name": "",
    "summary": "",
    "num_pages": "",
}

TITLE_RE = re.compile(r"^.*?POWER OF ATTORNEY.*$", re.I | re.M)

# → Loosened to allow OCR-inserted spaces/bars around the separators
DATE_RE = re.compile(
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}"
    r"|"
    r"\d{1,2}\s*[\/\-\|]\s*\d{1,2}\s*[\/\-\|]\s*\d{2,4}",
    re.I,
)

GOV_LAW_RE = re.compile(r"(?:State of|laws of)\s+([A-Z][A-Za-z]+)", re.I)
AGENT_RE = re.compile(r"Agent Name[:\s]+([A-Z][A-Za-z .'-]+)", re.I)
CLIENT_RE = re.compile(
    r"\bI,\s*([A-Z][A-Za-z .'-]+?)\s*(?:do|hereby)\s+appoint", re.I
)

# ---------------------------------------------------------------------
# 🔧  Environment / OpenAI client
# ---------------------------------------------------------------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
LLM_TEMPLATE = pathlib.Path("prompts/poa_extract_prompt.txt").read_text()
LLM_VISION_TEMPLATE = pathlib.Path("prompts/vision_prompt.txt").read_text()

# ---------------------------------------------------------------------
# 🔧  Regex-only pass
# ---------------------------------------------------------------------
def regex_pass(txt: str) -> Dict[str, str]:
    data = POA_FIELDS.copy()
    if m := TITLE_RE.search(txt):
        data["title"] = m.group().strip()
    if m := DATE_RE.search(txt):
        data["document_date"] = m.group().strip()
    if m := GOV_LAW_RE.search(txt):
        data["governing_law"] = m.group(1).strip()
    if m := AGENT_RE.search(txt):
        data["agent_name"] = m.group(1).strip()
    if m := CLIENT_RE.search(txt):
        data["client_name"] = m.group(1).strip()

    return data


# ---------------------------------------------------------------------
# 🔧  LLM pass (text-only)
# ---------------------------------------------------------------------
def llm_pass(text: str, missing: list[str]) -> dict:
    prompt = (
        LLM_TEMPLATE.replace("{missing_fields}", ", ".join(missing))
        .replace("{document_text}", text)
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)

# ---------------- GPT-4-Vision fallback ------------------------------
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
        if m := DATE_RE.search(candidate):
            return m.group().strip()

    return ""


# ---------------------------------------------------------------------
# 🔧  Main extractor
# ---------------------------------------------------------------------
def extract_poa(file) -> Dict[str, str]:
    """
    Rule-based POA extractor.
    *file* can be a Path, bytes, or a file-like object.
    """
    pdf_bytes = (
        file.read() if hasattr(file, "read") else pathlib.Path(file).read_bytes()
    )
    text, pages = pdf_to_text(pdf_bytes)

    # 1️⃣  Regex pass over raw text
    data = POA_FIELDS.copy()
    data.update(regex_pass(text))
    data["num_pages"] = str(pages)

    # 2️⃣  Text-LLM for any still-missing fields (fast, cheap)
    missing = [k for k, v in data.items() if v == ""]
    if "summary" not in missing:
        missing.append("summary")
    if missing:
        gpt_out = llm_pass(text, missing)
        for k in missing:
            data[k] = gpt_out.get(k, data[k])

    if data["document_date"] == "":
        data["document_date"] = _date_via_vision(pdf_bytes)

    return data