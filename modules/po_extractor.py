from __future__ import annotations
import re
import pathlib
import json
from typing import Dict
from modules.ocr_utils import pdf_to_text
from modules.po_constants import POA_FIELDS
from openai import OpenAI
from dotenv import load_dotenv
import os

# Regex patterns for extracting information from Power of Attorney documents
TITLE_RE = re.compile(r"^.*?POWER OF ATTORNEY.*$", re.I | re.M)
DATE_RE  = re.compile(
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}"
    r"|"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
    re.I,
)
GOV_LAW_RE = re.compile(r"(?:State of|laws of)\s+([A-Z][A-Za-z]+)", re.I)
AGENT_RE   = re.compile(r"Agent Name[:\s]+([A-Z][A-Za-z .'-]+)", re.I)
CLIENT_RE  = re.compile(r"\bI,\s*([A-Z][A-Za-z .'-]+?)\s*(?:do|hereby)\s+appoint", re.I)

def regex_pass(txt: str) -> Dict[str, str]:

    data = POA_FIELDS.copy()

        # Title
    if m := TITLE_RE.search(txt):
        data["title"] = m.group().strip()

    # Document date
    if m := DATE_RE.search(txt):
        data["document_date"] = m.group().strip()

    # Governing law
    if m := GOV_LAW_RE.search(txt):
        data["governing_law"] = m.group(1).strip()

    # Agent name
    if m := AGENT_RE.search(txt):
        data["agent_name"] = m.group(1).strip()

    # Client name via primary regex
    if m := CLIENT_RE.search(txt):
        data["client_name"] = m.group(1).strip()
    
    return data

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    api_key=api_key
    )

LLM_TEMPLATE = pathlib.Path("prompts/poa_extract_prompt.txt").read_text()

def llm_pass(text: str, missing: list[str]) -> dict:
    
    prompt = (
        LLM_TEMPLATE
        .replace("{missing_fields}", ", ".join(missing))
        .replace("{document_text}", text)          
    )


    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )

    return json.loads(response.choices[0].message.content)

def extract_poa(file) -> Dict[str, str]:
    """
    Rule-based POA extractor (Milestone 3).
    *file* can be Path, bytes, or a file-like object.
    """
    pdf_bytes = file.read() if hasattr(file, "read") else pathlib.Path(file).read_bytes()
    text, pages = pdf_to_text(pdf_bytes)

    data = POA_FIELDS.copy()
    data.update(regex_pass(text))
    data["num_pages"] = str(pages)

    missing = [k for k, v in data.items() if v == ""]
    if "summary" not in missing:
        missing.append("summary")

    if missing:
        gpt_out = llm_pass(text, missing)
        for k in missing:
            if k in gpt_out:
                data[k] = gpt_out[k]

    return data



