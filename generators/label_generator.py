from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import inch, landscape
from reportlab.lib import colors


# ============================================================
#   MANUFACTURING LABELS (4×6) — Charcuterie Boards
# ============================================================
def generate_manufacturing_labels_pdf(df):
    """
    Generate a 4×6 manufacturing labels PDF for charcuterie boards.
    One label per physical board (after quantity expansion).
    """

    if df.empty:
        return None

    buf = BytesIO()
    page_size = landscape((4 * inch, 6 * inch))
    c = canvas.Canvas(buf, pagesize=page_size)
    W, H = page_size

    left = 0.3 * inch
    right = W - 0.3 * inch
    top = H - 0.3 * inch

    for _, row in df.iterrows():
        y = top

        # Order ID + Quantity
        c.setFont("Helvetica-Bold", 14)
        c.drawString(left, y, f"Order ID: {row.get('order_id', '')}")
        c.drawRightString(right, y, f"Qty: {row.get('quantity', 1)}")
        y -= 0.28 * inch

        # Buyer + Date
        c.setFont("Helvetica", 13)
        c.drawString(left, y, f"Buyer: {row.get('buyer_name', '')}")
        c.drawRightString(right, y, f"Date: {row.get('order_date', '')}")
        y -= 0.32 * inch

        # Engraving box
        box_h = 0.9 * inch
        box_y = y - box_h
        c.setLineWidth(2)
        c.rect(left, box_y, right - left, box_h, stroke=1, fill=0)

        c.setFont("Helvetica-Bold", 16)
        c.drawString(left + 0.15 * inch, box_y + box_h - 0.30 * inch,
                     f"Design: {row.get('design_number', '')}")

        note = row.get("board_customization_note", "")
        c.setFont("Helvetica-Bold", 14)
        c.drawString(left + 0.15 * inch,
                     box_y + box_h - 0.65 * inch,
                     f"Note: {note}")

        y = box_y - 0.4 * inch

        # Engraving letter (if exists)
        engraving_letter = str(row.get("engraving_letter", "")).strip()
        if engraving_letter:
            c.setFont("Helvetica-Bold", 28)
            c.drawString(left, y, f"Letter: {engraving_letter}")
            y -= 0.35 * inch

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue()


# ============================================================
#   GIFT MESSAGE LABELS (4×6) — Same style as Blanket App
# ============================================================
def generate_gift_message_labels_pdf(df):
    """
    Generate a single merged 4×6 landscape PDF with ONE gift message per page.
    Uses same layout, font, borders, and wrapping rules as blanket gift labels.

    Expected column: "gift_message" (string).
    """

    # Column safety check
    if "gift_message" not in df.columns:
        return None

    # Filter only non-empty messages
    gift_df = df[
        df["gift_message"].notna()
        & df["gift_message"].astype(str).str.strip().ne("")
    ]
    if gift_df.empty:
        return None

    buf = BytesIO()
    page_size = landscape((4 * inch, 6 * inch))
    c = canvas.Canvas(buf, pagesize=page_size)
    W, H = page_size

    for _, row in gift_df.iterrows():
        message = str(row["gift_message"]).strip()

        # Outer border (same as blanket)
        c.setStrokeColor(colors.black)
        c.setLineWidth(3)
        c.rect(0.4 * inch, 0.4 * inch, W - 0.8 * inch, H - 0.8 * inch, stroke=1, fill=0)

        # Message font (same style)
        c.setFont("Times-BoldItalic", 18)

        # Word wrap manually (same as blanket)
        words = message.split()
        lines = []
        current_line = []
        max_width = W - 1.2 * inch

        for word in words:
            test = " ".join(current_line + [word])
            if c.stringWidth(test, "Times-BoldItalic", 18) < max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        # Vertical centering
        line_h = 0.30 * inch
        total_h = len(lines) * line_h
        y = (H + total_h) / 2

        # Draw lines
        for line in lines:
            c.drawCentredString(W / 2, y, line)
            y -= line_h

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue()
