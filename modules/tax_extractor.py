import re
from modules.ocr_utils import pdf_to_ocr_text

_DIGITS = re.compile(r'[^0-9]')          # strip everything except digits
def _grab(text: str, box_id: str) -> int:
    """
    Look for e.g.  '7 | 10,000'  or  '14| 876'
    • negative look-behind ensures we don’t match the '7' inside '17|'
    • allow arbitrary spaces between id and pipe
    """
    pat = re.compile(rf'(?<!\d){box_id}\s*\|\s*([0-9,\s]+)')
    m   = pat.search(text)
    if not m:
        return 0
    digits = _DIGITS.sub("", m.group(1))
    # if we only captured the id itself (e.g. '15'), treat as missing
    return int(digits) if digits and digits != box_id else 0

def extract_box_values(text: str, box_ids: set[str]) -> dict[str, int]:
    return {bid: _grab(text, bid) for bid in box_ids}

RIGHT_BOXES = {"4", "7", "10", "14", "15", "16", "17"}
LEFT_BOXES  = {"1","3","5a","5b","5c","5d","5e","6",
               "8a","8b","8c","8e","9","11","12","13"}

def blank_schema(keys=None):
    full = (keys or (RIGHT_BOXES | LEFT_BOXES)) | RIGHT_BOXES
    return {k: 0 for k in sorted(full)}

def extract_amounts(pdf_bytes: bytes,
                    include_left: bool = False) -> dict[str, int]:
    txt, _ = pdf_to_ocr_text(pdf_bytes)
    targets = RIGHT_BOXES | (LEFT_BOXES if include_left else set())
    vals    = extract_box_values(txt, targets)
    # Ensure every expected key is present
    out = blank_schema(targets)
    out.update(vals)
    return out