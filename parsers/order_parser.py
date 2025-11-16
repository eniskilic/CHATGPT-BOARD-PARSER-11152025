import io
import re
from typing import List

import pdfplumber
import pandas as pd

from utils.helpers import (
    safe_strip,
    normalize_board_type,
    parse_order_date,
    extract_city_state_zip,
)


def _split_segments(full_text: str) -> List[str]:
    """
    Split the whole PDF text into segments per order using the 'Order ID' anchor.
    """
    # Split but keep the 'Order ID:' marker at the beginning of each segment
    parts = re.split(r"(?=Order ID:\s*\d{3}-\d{7}-\d{7})", full_text)
    segments = [p for p in parts if "Order ID:" in p]
    return segments


def _extract_shipping_block(lines: List[str]):
    """
    Extract Ship To name and address from a list of lines that belong to an order.
    """
    ship_to_name = ""
    address_line1 = ""
    city = state = zipcode = country = ""

    # Find "Ship To" line
    idx = None
    for i, line in enumerate(lines):
        if "ship to:" in line.lower() or "ship to" == line.strip().lower():
            idx = i
            break

    if idx is not None:
        # Amazon usually:
        # Ship To:
        # Name
        # Address line 1
        # [Address line 2 (optional)]
        # City, ST ZIP
        # Country
        # -> We'll try to parse with some flexibility.
        block = [l.strip() for l in lines[idx + 1: idx + 7] if l.strip()]

        if block:
            ship_to_name = block[0]
        if len(block) >= 2:
            address_line1 = block[1]

        # find city/state/zip line (contains 5-digit zip)
        csz_line = ""
        for l in block[1:]:
            if re.search(r"\b\d{5}(?:-\d{4})?\b", l):
                csz_line = l
                break

        if csz_line:
            city, state, zipcode = extract_city_state_zip(csz_line)

        # Country is often last line
        if block:
            country_candidate = block[-1]
            if re.search(r"united states|usa|canada|mexico", country_candidate.lower()):
                country = country_candidate

    return ship_to_name, address_line1, city, state, zipcode, country


def _extract_order_info(segment: str):
    order_id = ""
    order_item_id = ""
    order_date_raw = ""
    sku = ""
    asin = ""
    quantity = 1
    product_title = ""

    # Order ID
    m = re.search(r"Order ID:\s*([\d-]+)", segment)
    if m:
        order_id = m.group(1).strip()

    # Order Item ID
    m = re.search(r"Order Item ID:\s*([A-Z0-9]+)", segment)
    if m:
        order_item_id = m.group(1).strip()

    # Order Date
    m = re.search(r"Order Date:\s*(.+)", segment)
    if m:
        order_date_raw = m.group(1).strip()

    # SKU
    m = re.search(r"SKU:\s*([A-Z0-9\-]+)", segment)
    if m:
        sku = m.group(1).strip()

    # ASIN
    m = re.search(r"ASIN:\s*([A-Z0-9]+)", segment)
    if m:
        asin = m.group(1).strip()

    # Quantity
    m = re.search(r"(Qty|Quantity):\s*(\d+)", segment)
    if m:
        try:
            quantity = int(m.group(2))
        except ValueError:
            quantity = 1

    # Product title - often on a line starting with the ASIN or SKU
    # Fallback: grab line after ASIN or SKU
    product_title = ""
    lines = segment.splitlines()
    for i, line in enumerate(lines):
        if "ASIN:" in line:
            # Next non-empty line is usually the product title
            for j in range(i + 1, min(len(lines), i + 5)):
                if lines[j].strip():
                    product_title = lines[j].strip()
                    break
            break

    return {
        "order_id": order_id,
        "order_item_id": order_item_id,
        "order_date_raw": order_date_raw,
        "sku": sku,
        "asin": asin,
        "quantity": quantity,
        "product_title": product_title,
    }


def _extract_customization(segment: str):
    """
    Pull Surface 1 customization details from the segment.
    Skip Surface 2 entirely.
    """
    # Limit to Customizations / Surface 1 block
    # We grab text from "Customizations:" until "Surface 2" or end
    m = re.search(
        r"Customizations:(.*?)(?:Surface 2:|$)",
        segment,
        flags=re.DOTALL | re.IGNORECASE,
    )
    block = m.group(1) if m else segment

    # Board type: Select Your Order
    m = re.search(
        r"Select Your Order:\s*(.+)",
        block,
        flags=re.IGNORECASE,
    )
    order_option_raw = m.group(1).strip() if m else ""

    # Design number
    design_number = None
    m = re.search(
        r"Choose Your Design\s*#?:\s*Design\s*(\d+)",
        block,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"Design\s*#?\s*[:\-]?\s*(\d+)",
            block,
            flags=re.IGNORECASE,
        )
    if m:
        try:
            design_number = int(m.group(1))
        except ValueError:
            design_number = None

    # Board Customization Note
    m = re.search(
        r"Board Customization Note:\s*(.+)",
        block,
        flags=re.IGNORECASE,
    )
    board_customization_note = m.group(1).strip() if m else ""

    # Engraving Letter
    m = re.search(
        r"Engraving Letter for Cheese Knife Handles:\s*(.+)",
        block,
        flags=re.IGNORECASE,
    )
    engraving_letter = m.group(1).strip() if m else ""
    # DO NOT derive from customization note – if it's blank, keep blank

    # Gift note & gift bag + message
    gift_option = "NO"
    gift_message = ""

    m = re.search(
        r"Gift Note\s*&\s*Gift Bag:\s*(.*?)(?:Please CHECK for mistakes and spellings\.?:|$)",
        block,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        raw_gift_block = m.group(1).strip()
        # If contains 'no' as main answer -> NO
        if re.match(r"\s*no\b", raw_gift_block, flags=re.IGNORECASE):
            gift_option = "NO"
            gift_message = ""
        else:
            gift_option = "YES"
            gift_message = re.sub(r"\s+", " ", raw_gift_block).strip()

    # Spelling confirmation
    spelling_confirmation = ""
    m = re.search(
        r"Please CHECK for mistakes and spellings\.?:\s*(.+)",
        block,
        flags=re.IGNORECASE,
    )
    if m:
        spelling_confirmation = m.group(1).strip()

    return {
        "order_option_raw": order_option_raw,
        "design_number": design_number,
        "board_customization_note": board_customization_note,
        "engraving_letter": engraving_letter,
        "gift_option": gift_option,
        "gift_message": gift_message,
        "spelling_confirmation": spelling_confirmation,
    }


def parse_order_details_pdfs(uploaded_files) -> pd.DataFrame:
    """
    Main entrypoint: parse a list of uploaded Amazon 'Order Details' PDFs
    for charcuterie boards. Returns a DataFrame with one row per order
    (before quantity expansion).
    """
    records = []

    for uploaded in uploaded_files:
        try:
            file_bytes = uploaded.read()
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                full_text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )
        except Exception as e:
            # Fail-safe: skip this PDF
            print(f"Error reading PDF {uploaded.name}: {e}")
            continue

        segments = _split_segments(full_text)
        for seg in segments:
            seg_lines = seg.splitlines()

            # Shipping info
            ship_to_name, address_line1, city, state, zipcode, country = \
                _extract_shipping_block(seg_lines)

            # Order / product info
            info = _extract_order_info(seg)

            # Customization
            cust = _extract_customization(seg)

            # Only keep if this looks like a board order
            if "CSTMBRD" not in info["sku"]:
                # You can relax/adjust this if needed
                pass

            buyer_short_name = ""
            if ship_to_name:
                buyer_short_name = ship_to_name.split()[0]

            record = {
                "buyer_name": buyer_short_name,
                "ship_to_name": ship_to_name,
                "address_line1": address_line1,
                "city": city,
                "state": state,
                "zip": zipcode,
                "country": country,
                "order_id": info["order_id"],
                "order_item_id": info["order_item_id"],
                "order_date": parse_order_date(info["order_date_raw"]),
                "product_title": info["product_title"],
                "sku": info["sku"],
                "asin": info["asin"],
                "quantity": info["quantity"],
                "order_option": normalize_board_type(
                    cust["order_option_raw"]
                ),
                "design_number": cust["design_number"],
                "board_customization_note": cust["board_customization_note"],
                "engraving_letter": cust["engraving_letter"],
                "gift_option": cust["gift_option"],
                "gift_message": cust["gift_message"],
                "spelling_confirmation": cust["spelling_confirmation"],
            }

            records.append(record)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Ensure types
    if "design_number" in df.columns:
        df["design_number"] = pd.to_numeric(
            df["design_number"], errors="coerce"
        ).astype("Int64")

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).astype(int)

    return df
