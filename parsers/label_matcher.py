import pandas as pd

from utils.helpers import normalize_for_match, fuzzy_equal


def match_orders_to_labels(orders_df: pd.DataFrame,
                           labels_df: pd.DataFrame) -> pd.DataFrame:
    """
    Match each board order to a shipping label using:
    - ZIP (exact)
    - Address line 1 (normalized)
    - Recipient name (fuzzy)
    """
    if orders_df.empty or labels_df.empty:
        orders_df = orders_df.copy()
        orders_df["shipping_label_status"] = "⚠️ Missing"
        orders_df["matched_label_id"] = ""
        return orders_df

    labels_df = labels_df.copy()
    labels_df["norm_addr1"] = labels_df["address_line1"].fillna("").apply(
        normalize_for_match
    )
    labels_df["norm_zip"] = labels_df["zip"].fillna("").astype(str)

    orders_df = orders_df.copy()
    orders_df["norm_addr1"] = orders_df["address_line1"].fillna("").apply(
        normalize_for_match
    )
    orders_df["norm_zip"] = orders_df["zip"].fillna("").astype(str)

    label_map = []

    for idx, row in orders_df.iterrows():
        best_label_id = ""
        status = "⚠️ Missing"

        for _, lab in labels_df.iterrows():
            if row["norm_zip"] and row["norm_zip"] == lab["norm_zip"]:
                # Address must match strongly
                if row["norm_addr1"] and row["norm_addr1"] == lab["norm_addr1"]:
                    # Names fuzzy match (ship_to_name vs recipient_name)
                    if fuzzy_equal(
                        row.get("ship_to_name", ""),
                        lab.get("recipient_name", "")
                    ):
                        best_label_id = lab["label_id"]
                        status = "✓ Matched"
                        break

        label_map.append((best_label_id, status))

    orders_df["matched_label_id"] = [m[0] for m in label_map]
    orders_df["shipping_label_status"] = [m[1] for m in label_map]

    # Clean up helper columns
    orders_df = orders_df.drop(columns=["norm_addr1", "norm_zip"], errors="ignore")
    return orders_df
