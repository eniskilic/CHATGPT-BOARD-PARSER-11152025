import re
from datetime import datetime
from dateutil import parser as date_parser
from difflib import SequenceMatcher


def safe_strip(text):
    if text is None:
        return ""
    return str(text).strip()


def normalize_board_type(raw: str) -> str:
    raw = safe_strip(raw)
    lower = raw.lower()

    if not raw:
        return ""

    if "no engraving" in lower:
        return "No Engraving"

    # Board only (no utensils)
    if "board only" in lower and "utensil" not in lower:
        return "Board Only"

    # Board + utensil engraving variants
    if any(k in lower for k in [
        "board+utensils",
        "board + utensils",
        "board & utensils",
        "board and utensils",
        "board + cheese knife",
        "board+cheese knife",
        "board & knife",
        "board and knife"
    ]):
        return "Board+Utensils Engraving"

    # Fallback – return as-is if we can't map
    return raw


def parse_order_date(raw: str):
    raw = safe_strip(raw)
    if not raw:
        return ""

    # Typical Amazon: "Sat, Nov 15, 2025"
    for fmt in ["%a, %b %d, %Y", "%b %d, %Y", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.date().isoformat()
        except ValueError:
            continue

    # Last resort: dateutil
    try:
        dt = date_parser.parse(raw)
        return dt.date().isoformat()
    except Exception:
        return raw  # keep original if parsing fails


def file_friendly_name(name: str) -> str:
    name = safe_strip(name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_]+", "", name)
    return name


def normalize_for_match(text: str) -> str:
    text = safe_strip(text).lower()
    text = re.sub(r"[^a-z0-9]", "", text)
    return text


def fuzzy_equal(a: str, b: str, threshold: float = 0.8) -> bool:
    a_norm = normalize_for_match(a)
    b_norm = normalize_for_match(b)
    if not a_norm or not b_norm:
        return False
    ratio = SequenceMatcher(None, a_norm, b_norm).ratio()
    return ratio >= threshold


def extract_city_state_zip(line: str):
    """
    Parse "City, ST 12345" or "City ST 12345-6789".
    Returns (city, state, zip) or ("", "", "") on failure.
    """
    line = safe_strip(line)
    # Try with comma first
    m = re.search(r"^(.*?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\b", line)
    if not m:
        # Without comma
        m = re.search(r"^(.*?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\b", line)
    if not m:
        return "", "", ""
    city, state, zipcode = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    return city, state, zipcode
