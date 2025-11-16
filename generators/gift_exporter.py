import io
import pandas as pd


def generate_gift_messages_csv(expanded_df: pd.DataFrame) -> bytes:
    """
    Extract all orders with gift_option == 'YES'
    and return a CSV with:
      Buyer Name (ship_to_name)
      Order ID
      Gift Message
    """
    if expanded_df.empty:
        return b""

    df = expanded_df.copy()
    df = df[df["gift_option"].str.upper() == "YES"]

    if df.empty:
        return b""

    out = df[[
        "ship_to_name",
        "order_id",
        "gift_message"
    ]].rename(columns={
        "ship_to_name": "Buyer Name",
        "order_id": "Order ID",
        "gift_message": "Gift Message",
    })

    buf = io.StringIO()
    out.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
