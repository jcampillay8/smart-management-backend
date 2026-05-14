import os
import re
from typing import Tuple, Optional
from datetime import datetime

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS


def get_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return "image"
    elif ext in ALLOWED_PDF_EXTENSIONS:
        return "pdf"
    raise ValueError(f"Tipo de archivo no permitido: {ext}")


def validate_file_extension(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def clean_rut(rut: str) -> Optional[str]:
    if not rut:
        return None
    cleaned = str(rut).replace(".", "").strip().upper()
    if re.match(r"^\d{7,8}-[\dK]$", cleaned):
        return cleaned
    just_alphanum = re.sub(r"[^0-9kK]", "", cleaned)
    if len(just_alphanum) > 1:
        body = just_alphanum[:-1]
        dv = just_alphanum[-1].upper()
        if len(body) >= 7 and len(body) <= 8:
            return f"{body}-{dv}"
    return None


def parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def clean_number(value) -> Optional[float]:
    if value is None:
        return None
    cleaned = str(value).replace("$", "").replace(",", "").replace(".", "").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def safe_filename(filename: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    return f"{timestamp}_{filename}"
