import io
from typing import Dict

import pandas as pd

from utils.helpers import file_friendly_name, safe_strip


def expand_by_quantity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create one row per physical board using the quantity column.
    """
    if df.empty:
        return df

    df = df.copy()
    df["quantity"] = df["quantity"].fillna(1).astype(int)
    expanded = df.loc[df.index.repeat(df["quantity"])].copy()
    expanded.reset_index(drop=True, inplace=True)
    return expanded


def generate_design_csvs(expanded_df: pd.DataFrame) -> Dict[int, bytes]:
    """
    For each design number 1-9, create a CSV in the LightBurn format:
    csvbuyer_name,design,line1,line2,line3,initial,order_id,order_item_id,
    board_type,gift_note,gift_message
    Returns a dict: {design_number: csv_bytes}
    """
    design_csvs = {}

    if expanded_df.empty:
        return design_csvs

    df = expanded_df.copy()
    df = df[df["design_number"].notna()]

    for design in sorted(df["design_number"].dropna().unique()):
        d = df[df["design_number"] == design].copy()

        rows = []
        for _, row in d.iterrows():
            buyer_file_name = file_friendly_name(
                f"{row.get('buyer_name', '')} {row.get('ship_to_name', '')}"
            )
            rows.append({
                "csvbuyer_name": buyer_file_name,
                "design": int(design),
                "line1": safe_strip(row.get("board_customization_note", "")),
                "line2": "",
                "line3": "",
                "initial": safe_strip(row.get("engraving_letter", "")),
                "order_id": safe_strip(row.get("order_id", "")),
                "order_item_id": safe_strip(row.get("order_item_id", "")),
                "board_type": safe_strip(row.get("order_option", "")),
                "gift_note": safe_strip(row.get("gift_option", "")),
                "gift_message": safe_strip(row.get("gift_message", "")),
            })

        design_df = pd.DataFrame(rows, columns=[
            "csvbuyer_name",
            "design",
            "line1",
            "line2",
            "line3",
            "initial",
            "order_id",
            "order_item_id",
            "board_type",
            "gift_note",
            "gift_message",
        ])

        buffer = io.StringIO()
        design_df.to_csv(buffer, index=False)
        design_csvs[int(design)] = buffer.getvalue().encode("utf-8")

    return design_csvs
