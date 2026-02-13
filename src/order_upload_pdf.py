"""
Order Upload – PDF Generator
=============================

Generates a clean, invoice-style PDF from matched order lines.

Output table: S.N | PART NAME | PART NUMBER | PRICE | QTY | LINE TOTAL
Followed by a highlighted GRAND TOTAL row.

Optionally renders a customer header (Hindi/Devanagari name, phone, date)
above the table when customer_info is provided.

Guardrails:
- New file, does NOT modify any existing PDF/invoice logic.
- Only active when config.ENABLE_ORDER_UPLOAD is True.
- Writes to temp folder only; caller is responsible for cleanup.
"""
from __future__ import annotations

import os
from typing import List, Dict, Optional
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    from src import config
except ImportError:
    import config


# ── Devanagari / Unicode font registration ─────────────────────
# We attempt to register a TTF font that supports Devanagari script.
# Windows ships with Nirmala UI; Linux/macOS may have Noto Sans Devanagari.
# If none are found, we fall back to Helvetica (Hindi text will render as
# boxes, but the PDF is still valid and English fields still display).

_DEVANAGARI_FONT_NAME: Optional[str] = None

_CANDIDATE_FONTS = [
    # (font name to register, file path)
    ("NirmalaUI", os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "Nirmala.ttf")),
    ("NirmalaUI", os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "nirmala.ttf")),
    ("NotoSansDevanagari", "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
    ("NotoSansDevanagari", "/usr/share/fonts/noto/NotoSansDevanagari-Regular.ttf"),
    ("Mangal", os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "mangal.ttf")),
]

for _font_name, _font_path in _CANDIDATE_FONTS:
    if os.path.exists(_font_path):
        try:
            pdfmetrics.registerFont(TTFont(_font_name, _font_path))
            _DEVANAGARI_FONT_NAME = _font_name
            break
        except Exception:
            continue


def _ensure_order_upload_enabled() -> None:
    if not config.ENABLE_ORDER_UPLOAD:
        raise RuntimeError("Order Upload PDF is disabled. Set ENABLE_ORDER_UPLOAD=true.")


def generate_order_pdf(
    matched_lines: List[Dict],
    grand_total: float = 0.0,
    order_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    customer_info: Optional[Dict] = None,
) -> str:
    """
    Generate an invoice-style PDF from matched order lines.

    Args:
        matched_lines: List of dicts with keys:
            sn, part_name, part_number, price, qty, line_total, match_type
        grand_total: Pre-computed grand total value.
        order_id: Optional order identifier for the filename and header.
        output_dir: Directory for the PDF. Defaults to config.TEMP_FOLDER.
        customer_info: Optional dict with keys: phone, name, name_en, date.
            When provided, a customer details line is rendered below the title.

    Returns:
        Absolute path to the generated PDF file.
    """
    _ensure_order_upload_enabled()

    # Output path
    out_dir = output_dir or config.TEMP_FOLDER or "temp"
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"order_{order_id or 'upload'}_{timestamp}.pdf"
    pdf_path = os.path.join(out_dir, filename)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ── Header ──────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "OrderTitle",
        parent=styles["Heading1"],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=4,
        textColor=colors.HexColor("#1a1a2e"),
    )
    subtitle_style = ParagraphStyle(
        "OrderSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
        spaceAfter=12,
    )

    # Style for customer info line — uses Devanagari font if available
    customer_font = _DEVANAGARI_FONT_NAME or "Helvetica"
    customer_style = ParagraphStyle(
        "CustomerInfo",
        parent=styles["Normal"],
        fontName=customer_font,
        fontSize=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#333333"),
        spaceAfter=8,
    )

    elements.append(Paragraph("SAI-ABS Order Summary", title_style))

    sub_parts = []
    if order_id:
        sub_parts.append(f"Order: {order_id}")
    sub_parts.append(f"Date: {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    sub_parts.append(f"Items: {len(matched_lines)}")
    elements.append(Paragraph(" | ".join(sub_parts), subtitle_style))

    # ── Customer Details (optional) ─────────────────────────────
    if customer_info and any(customer_info.get(k) for k in ("name", "name_en", "phone", "date")):
        cust_parts = []
        # Build name display: Hindi (English)
        name_display = ""
        if customer_info.get("name"):
            name_display = customer_info["name"]
            if customer_info.get("name_en"):
                name_display += f" ({customer_info['name_en']})"
        elif customer_info.get("name_en"):
            name_display = customer_info["name_en"]
        if name_display:
            cust_parts.append(f"Customer: {name_display}")
        if customer_info.get("phone"):
            cust_parts.append(f"Phone: {customer_info['phone']}")
        if customer_info.get("date"):
            cust_parts.append(f"Date: {customer_info['date']}")
        if cust_parts:
            elements.append(Paragraph(" | ".join(cust_parts), customer_style))

    elements.append(Spacer(1, 4 * mm))

    # ── Table ───────────────────────────────────────────────────
    col_headers = ["S.N", "PART NAME", "PART NUMBER", "PRICE", "QTY", "LINE TOTAL"]
    table_data = [col_headers]

    for line in matched_lines:
        price_val = line.get("price", "")
        lt_val = line.get("line_total", "")
        # Format numbers nicely
        try:
            price_val = f"{float(price_val):,.2f}" if price_val else ""
        except (ValueError, TypeError):
            pass
        try:
            lt_val = f"{float(lt_val):,.2f}" if lt_val else ""
        except (ValueError, TypeError):
            pass

        table_data.append([
            str(line.get("sn", "")),
            str(line.get("part_name", "")),
            str(line.get("part_number", "")),
            str(price_val),
            str(line.get("qty", "")),
            str(lt_val),
        ])

    # Grand total row
    table_data.append(["", "", "", "", "GRAND TOTAL", f"{grand_total:,.2f}"])

    # Column widths (A4 = 210mm, minus 30mm margins = 180mm usable)
    col_widths = [12 * mm, 62 * mm, 28 * mm, 22 * mm, 14 * mm, 28 * mm]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Styling
    num_data_rows = len(matched_lines)
    total_row_idx = num_data_rows + 1  # 0=header, 1..N=data, N+1=total

    style_commands = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),

        # Data rows
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -2), 8),
        ("TOPPADDING", (0, 1), (-1, -2), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -2), 4),

        # Align numbers right
        ("ALIGN", (0, 1), (0, -1), "CENTER"),    # S.N center
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),     # PRICE right
        ("ALIGN", (4, 1), (4, -1), "CENTER"),    # QTY center
        ("ALIGN", (5, 1), (5, -1), "RIGHT"),     # LINE TOTAL right

        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.HexColor("#1a1a2e")),

        # Grand Total row – yellow highlight, bold
        ("BACKGROUND", (0, total_row_idx), (-1, total_row_idx), colors.HexColor("#FFF176")),
        ("FONTNAME", (0, total_row_idx), (-1, total_row_idx), "Helvetica-Bold"),
        ("FONTSIZE", (0, total_row_idx), (-1, total_row_idx), 10),
        ("TOPPADDING", (0, total_row_idx), (-1, total_row_idx), 6),
        ("BOTTOMPADDING", (0, total_row_idx), (-1, total_row_idx), 6),
        ("LINEABOVE", (0, total_row_idx), (-1, total_row_idx), 1.5, colors.HexColor("#1a1a2e")),
    ]

    # Alternating row colours for readability
    for i in range(1, num_data_rows + 1):
        if i % 2 == 0:
            style_commands.append(
                ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f5f5"))
            )

    table.setStyle(TableStyle(style_commands))
    elements.append(table)

    # ── Footer ──────────────────────────────────────────────────
    elements.append(Spacer(1, 6 * mm))
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=7,
        textColor=colors.HexColor("#999999"),
        alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        f"Generated by SAI-ABS Order Scanner | {datetime.now().strftime('%d %b %Y %H:%M')}",
        footer_style,
    ))

    # Build
    doc.build(elements)
    return os.path.abspath(pdf_path)
