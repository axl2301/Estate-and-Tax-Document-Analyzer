# modules/tax_extractor.py
import re
from modules.ocr_utils import pdf_to_images, run_ocr, cluster_lines

# ─────────── Configuración ───────────
# Solo campos obligatorios de la columna derecha
FIELDS   = ["4","7","10","14","15","16","17"]
NUMTOK   = re.compile(r"^[\d,.\-]+$")
POS_TH   = 0.60   # umbral para la columna de montos (60% del ancho)
LEFT_TH  = 0.40   # umbral para la columna de IDs    (40% del ancho)

def _normal(txt: str) -> str:
    """Minúsculas y sin puntuación de borde."""
    return re.sub(r"[|,.\]\)\(:;{}\s]+$", "", txt.lower())

def extract_amounts_from_lines(lines):
    res    = {fid: 0 for fid in FIELDS}
    page_w = max(w["x1"] for ln in lines for w in ln)

    for i, ln in enumerate(lines):
        # 1) detectar ID dentro de la banda izquierda
        id_tok = next(
            (w for w in ln
             if _normal(w["text"]) in FIELDS
             and w["x0"] <= LEFT_TH * page_w),
            None
        )
        if not id_tok:
            continue
        fid = _normal(id_tok["text"])
        if res[fid] != 0:
            continue  # ya extraído

        # 2) buscar la última racha de números grandes a la derecha
        tail = [w for w in ln if w["x0"] > id_tok["x1"]]
        nums = []
        for w in reversed(tail):
            if w["x0"] <= POS_TH * page_w:
                if nums: break
                continue
            if not NUMTOK.match(w["text"]):
                if nums: break
                continue
            digits = re.sub(r"\D", "", w["text"])
            if nums or "," in w["text"] or len(digits) >= 3:
                nums.insert(0, w)

        # 3) look-ahead si no hay en la misma línea
        if not nums:
            for j in range(i+1, len(lines)):
                # parar al encontrar otro ID
                if any(
                    _normal(x["text"]) in FIELDS
                    and x["x0"] <= LEFT_TH * page_w
                    for x in lines[j]
                ):
                    break
                for w in reversed(lines[j]):
                    if w["x0"] <= POS_TH * page_w:
                        if nums: break
                        continue
                    if not NUMTOK.match(w["text"]):
                        if nums: break
                        continue
                    digits = re.sub(r"\D", "", w["text"])
                    if nums or "," in w["text"] or len(digits) >= 3:
                        nums.insert(0, w)
                if nums:
                    break

        # 4) concatenar y convertir
        raw   = "".join(w["text"] for w in nums)
        clean = re.sub(r"[^\d\-]", "", raw)
        res[fid] = int(clean) if clean else 0

    return res

def extract_from_pdf(pdf_path: str):
    img   = pdf_to_images(pdf_path)[0]   # primera página
    words = run_ocr(img)
    lines = cluster_lines(words)
    return extract_amounts_from_lines(lines)
