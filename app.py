import io
import zipfile

import pandas as pd
import streamlit as st

from parsers.order_parser import parse_order_details_pdfs
from parsers.shipping_parser import parse_shipping_label_pdfs
from parsers.label_matcher import match_orders_to_labels
from generators.csv_generator import expand_by_quantity, generate_design_csvs
from generators.gift_exporter import generate_gift_messages_csv
from generators.label_generator import generate_manufacturing_labels_pdf


st.set_page_config(
    page_title="Charcuterie Board Order Parser",
    layout="wide"
)


st.title("Charcuterie Board Order Parser")

st.markdown(
    """
This app parses **Amazon Order Details PDFs** for charcuterie boards,
extracts customization fields, generates **LightBurn CSVs** per design,
exports **gift messages**, and creates **4×6 manufacturing labels**.

It also attempts to match **shipping labels by buyer name + address + ZIP**
instead of page order.
"""
)

st.sidebar.header("Upload PDFs")

order_files = st.sidebar.file_uploader(
    "Order Details PDFs (charcuterie boards)",
    type=["pdf"],
    accept_multiple_files=True,
)

shipping_files = st.sidebar.file_uploader(
    "Shipping Label PDFs (optional but recommended)",
    type=["pdf"],
    accept_multiple_files=True,
)

run_btn = st.sidebar.button("Parse & Generate")


if run_btn:
    if not order_files:
        st.error("Please upload at least one order details PDF.")
        st.stop()

    with st.spinner("Parsing order details..."):
        orders_df = parse_order_details_pdfs(order_files)

    if orders_df.empty:
        st.error("No orders were parsed. Please check your PDFs.")
        st.stop()

    # Parse shipping labels (optional)
    if shipping_files:
        with st.spinner("Parsing shipping labels..."):
            labels_df = parse_shipping_label_pdfs(shipping_files)
        with st.spinner("Matching shipping labels to orders..."):
            orders_df = match_orders_to_labels(orders_df, labels_df)
    else:
        orders_df["shipping_label_status"] = "⚠️ Missing"
        orders_df["matched_label_id"] = ""

    # For UI filtering we use the non-expanded table
    st.subheader("Parsed Orders (Before Quantity Expansion)")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        date_min = orders_df["order_date"].min()
        date_max = orders_df["order_date"].max()
        date_filter = st.date_input(
            "Filter by Order Date",
            value=(pd.to_datetime(date_min).date()
                   if pd.notnull(date_min) else None,
                   pd.to_datetime(date_max).date()
                   if pd.notnull(date_max) else None),
        )

    with col2:
        design_filter = st.multiselect(
            "Design #",
            sorted(orders_df["design_number"].dropna().unique().tolist()),
            default=sorted(orders_df["design_number"].dropna().unique().tolist()),
        )

    with col3:
        sku_filter = st.multiselect(
            "SKU",
            sorted(orders_df["sku"].dropna().unique().tolist()),
            default=sorted(orders_df["sku"].dropna().unique().tolist()),
        )

    with col4:
        buyer_search = st.text_input("Search Buyer Name", "")

    filtered = orders_df.copy()

    # Date range filter
    if isinstance(date_filter, tuple) and len(date_filter) == 2:
        start_date, end_date = date_filter
        if start_date and end_date:
            mask = (pd.to_datetime(filtered["order_date"], errors="coerce").dt.date
                    .between(start_date, end_date))
            filtered = filtered[mask]

    # Design filter
    if design_filter:
        filtered = filtered[filtered["design_number"].isin(design_filter)]

    # SKU filter
    if sku_filter:
        filtered = filtered[filtered["sku"].isin(sku_filter)]

    # Buyer name search
    if buyer_search:
        filtered = filtered[
            filtered["buyer_name"].str.contains(buyer_search, case=False, na=False)
            | filtered["ship_to_name"].str.contains(buyer_search, case=False, na=False)
        ]

    display_cols = [
        "buyer_name",
        "ship_to_name",
        "order_id",
        "order_date",
        "sku",
        "design_number",
        "board_customization_note",
        "engraving_letter",
        "quantity",
        "order_option",
        "gift_option",
        "shipping_label_status",
    ]

    st.dataframe(filtered[display_cols], use_container_width=True)

    # Expanded DF for manufacturing labels and LightBurn
    expanded_df = expand_by_quantity(filtered)

    st.markdown("---")
    st.subheader("Downloads")

    # 1) Design-specific LightBurn CSVs
    design_csvs = generate_design_csvs(expanded_df)

    if design_csvs:
        st.markdown("### LightBurn CSVs (per design)")

        # Individual design CSV buttons
        for design in sorted(design_csvs.keys()):
            st.download_button(
                label=f"Download design_{design}.csv",
                file_name=f"design_{design}.csv",
                mime="text/csv",
                data=design_csvs[design],
                key=f"dl_design_{design}",
            )

        # All CSVs as ZIP
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for design, csv_bytes in design_csvs.items():
                zf.writestr(f"design_{design}.csv", csv_bytes)
        zip_buf.seek(0)

        st.download_button(
            label="Download All Design CSVs (ZIP)",
            file_name="all_design_csvs.zip",
            mime="application/zip",
            data=zip_buf.getvalue(),
            key="dl_all_designs_zip",
        )
    else:
        st.info("No design CSVs generated (no valid design numbers found).")

    # 2) Gift messages
    st.markdown("### Gift Messages")

    gift_csv_bytes = generate_gift_messages_csv(expanded_df)
    if gift_csv_bytes:
        st.download_button(
            label="Download All Gift Messages (CSV)",
            file_name="gift_messages.csv",
            mime="text/csv",
            data=gift_csv_bytes,
            key="dl_gift_messages",
        )
    else:
        st.info("No gift messages found (gift_note: YES).")

    # 3) Manufacturing labels PDF
    st.markdown("### Manufacturing Labels (4×6 PDF)")

    labels_pdf = generate_manufacturing_labels_pdf(expanded_df)
    if labels_pdf:
        st.download_button(
            label="Download Manufacturing Labels PDF",
            file_name="manufacturing_labels.pdf",
            mime="application/pdf",
            data=labels_pdf,
            key="dl_labels_pdf",
        )
    else:
        st.info("No labels generated (no orders after filters).")

    st.markdown("---")
    st.caption(
        "Shipping labels are matched by buyer name + address + ZIP. "
        "Orders without a matching label are flagged as '⚠️ Missing' "
        "but still get manufacturing labels."
    )
else:
    st.info("Upload your PDFs in the sidebar and click **Parse & Generate** to start.")
