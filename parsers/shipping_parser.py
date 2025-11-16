import io
import re
from typing import List

import pdfplumber
import pandas as pd

from utils.helpers import safe_strip, extract_city_state_zip


def _extract_label_from_page(text: str, page_index: int):
    """
    Very generic shipping label parser:
    - Tries to grab first few non-empty lines as:
      name, address line 1, city/state/zip
    """
    lines = [safe_strip(l) for l in text.splitlines()]
    non_empty = [l for l in lines if l]

    if len(non_empty) < 3:
        return None

    # Heuristic: first non-empty is name, second is addr1,
    # city/state/zip somewhere in first 10 lines
    recipient_name = non_empty[0]
    address_line1 = non_empty[1]

    csz_line = ""
    for l in non_empty[:10]:
        if re.search(r"\b\d{5}(?:-\d{4})?\b", l):
            csz_line = l
            break

    city, state, zipcode = extract_city_state_zip(csz_line)

    if not zipcode:  # This probably isn't a valid label page
        return None

    return {
        "recipient_name": recipient_name,
        "address_line1": address_line1,
        "city": city,
        "state": state,
        "zip": zipcode,
    }


def parse_shipping_label_pdfs(uploaded_files) -> pd.DataFrame:
    """
    Parse shipping label PDFs into a DataFrame with one row per label.
    Does NOT depend on manifest pages.

    Adds:
      - label_id           -> "pdf{file_idx}_page_{page_idx}"
      - source_file_index  -> index within uploaded_files
      - source_file_name   -> original PDF file name
      - page_index         -> 0-based page index
    """
    labels = []

    for file_idx, uploaded in enumerate(uploaded_files):
        try:
            # Reset file pointer in case it was read before
            uploaded.seek(0)
            file_bytes = uploaded.read()
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text() or ""
                        label_core = _extract_label_from_page(text, page_idx)
                        if label_core:
                            label_core["label_id"] = f"pdf{file_idx}_page_{page_idx}"
                            label_core["source_file_index"] = file_idx
                            label_core["source_file_name"] = uploaded.name
                            label_core["page_index"] = page_idx
                            labels.append(label_core)
                    except Exception:
                        continue
        except Exception as e:
            print(f"Error reading shipping PDF {uploaded.name}: {e}")
            continue

    if not labels:
        return pd.DataFrame()

    df = pd.DataFrame(labels)
    return df
