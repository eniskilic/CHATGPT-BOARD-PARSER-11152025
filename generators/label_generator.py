import io

import pandas as pd
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas

from utils.helpers import safe_strip


def generate_manufacturing_labels_pdf(expanded_df: pd.DataFrame) -> bytes:
    """
    Generate a 4x6 inch PDF with one page per board.
    Layout:

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━
        DESIGN #7
        BOARD+UTENSILS ENGRAVING
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Engraving Text:
    The Conine Family

    Engraving Letter: C

    Order: 111-...
    Buyer: Melissa

    Gift Note: NO

    ✓ Double Checked!
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    if expanded_df.empty:
        return b""

    buf = io.BytesIO()

    # 4x6 inches, portrait
    page_width, page_height = (4 * inch, 6 * inch)
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    for _, row in expanded_df.iterrows():
        design = safe_strip(row.get("design_number", ""))
        board_type = safe_strip(row.get("order_option", ""))
        engr_text = safe_strip(row.get("board_customization_note", ""))
        engr_letter = safe_strip(row.get("engraving_letter", ""))
        order_id = safe_strip(row.get("order_id", ""))
        buyer_name = safe_strip(row.get("buyer_name", "")) or safe_strip(
            row.get("ship_to_name", "")
        )
        gift_option = safe_strip(row.get("gift_option", "NO")).upper()
        if not engr_letter:
            engr_letter_display = "N/A"
        else:
            engr_letter_display = engr_letter

        top_y = page_height - 20
        left_margin = 20

        # Header lines
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left_margin, top_y, "━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        c.drawCentredString(
            page_width / 2,
            top_y - 18,
            f"DESIGN #{design}",
        )
        c.drawCentredString(
            page_width / 2,
            top_y - 34,
            board_type or "BOARD",
        )
        c.drawString(left_margin, top_y - 50, "━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Engraving text block
        y = top_y - 70
        c.setFont("Helvetica", 9)
        c.drawString(left_margin, y, "Engraving Text:")

        # Auto-wrap engraving text
        max_width = page_width - 2 * left_margin
        y -= 14
        c.setFont("Helvetica", 9)

        def wrap_text(text, font_name="Helvetica", font_size=9, max_w=max_width):
            from reportlab.pdfbase.pdfmetrics import stringWidth

            words = text.split()
            lines = []
            current = ""
            for w in words:
                trial = (current + " " + w).strip()
                if stringWidth(trial, font_name, font_size) <= max_w:
                    current = trial
                else:
                    if current:
                        lines.append(current)
                    current = w
            if current:
                lines.append(current)
            if not lines:
                lines = [""]
            return lines

        lines = wrap_text(engr_text)
        for line in lines:
            c.drawString(left_margin, y, line)
            y -= 12

        # Engraving letter
        y -= 8
        c.setFont("Helvetica", 9)
        c.drawString(left_margin, y, f"Engraving Letter: {engr_letter_display}")
        y -= 14

        # Order + buyer
        c.drawString(left_margin, y, f"Order: {order_id}")
        y -= 14
        c.drawString(left_margin, y, f"Buyer: {buyer_name}")
        y -= 14

        # Gift
        c.drawString(left_margin, y, f"Gift Note: {gift_option}")
        y -= 18

        # Spelling confirmation checkmark
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left_margin, y, "✓ Double Checked!")
        y -= 18

        c.setFont("Helvetica", 10)
        c.drawString(left_margin, y, "━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue()
