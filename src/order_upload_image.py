"""
Order Upload – Invoice Image Generator
========================================

Renders the order summary as a PNG image for sending via Telegram's sendPhoto.
Used as a workaround when corporate firewalls (e.g. Zscaler IPS) block
Telegram's sendDocument API but allow sendPhoto.

Mirrors the PDF layout: title, customer info, table, grand total.

Guardrails:
- New file, does NOT modify any existing logic.
- Only active when config.ENABLE_ORDER_UPLOAD is True.
"""
from __future__ import annotations

import os
from typing import List, Dict, Optional
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

try:
    from src import config
except ImportError:
    import config


# ── Font resolution ──────────────────────────────────────────────
_FONT_DIR = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a system font. Tries Segoe UI (Windows), then falls back."""
    candidates = [
        os.path.join(_FONT_DIR, "segoeuib.ttf" if bold else "segoeui.ttf"),
        os.path.join(_FONT_DIR, "arialbd.ttf" if bold else "arial.ttf"),
        os.path.join(_FONT_DIR, "calibrib.ttf" if bold else "calibri.ttf"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# Pre-load fonts
_FONT_TITLE = _load_font(22, bold=True)
_FONT_SUBTITLE = _load_font(13)
_FONT_HEADER = _load_font(12, bold=True)
_FONT_CELL = _load_font(11)
_FONT_CELL_BOLD = _load_font(11, bold=True)
_FONT_FOOTER = _load_font(10)

# Colours
_BG_COLOR = (255, 255, 255)
_HEADER_BG = (26, 26, 46)       # dark navy
_HEADER_FG = (255, 255, 255)
_ALT_ROW_BG = (245, 245, 245)
_TOTAL_BG = (255, 241, 118)     # yellow highlight
_GRID_COLOR = (200, 200, 200)
_TEXT_COLOR = (30, 30, 30)
_SUBTITLE_COLOR = (100, 100, 100)
_FOOTER_COLOR = (160, 160, 160)
_UNMATCHED_BG = (255, 235, 235)


def generate_order_image(
    matched_lines: List[Dict],
    grand_total: float = 0.0,
    order_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    customer_info: Optional[Dict] = None,
) -> str:
    """
    Generate a PNG image of the order invoice table.

    Args:
        matched_lines: List of dicts (sn, part_name, part_number, price, qty, line_total, match_type).
        grand_total: Pre-computed grand total.
        order_id: Optional order ID for filename/header.
        output_dir: Directory for the image. Defaults to config.TEMP_FOLDER.
        customer_info: Optional dict (phone, name, name_en, date).

    Returns:
        Absolute path to the generated PNG file.
    """
    # Column definitions: (header, width_px, align)
    columns = [
        ("S.N",          45,  "center"),
        ("PART NAME",   320,  "left"),
        ("PART #",      100,  "left"),
        ("PRICE",        75,  "right"),
        ("QTY",          40,  "center"),
        ("TOTAL",        85,  "right"),
    ]

    col_widths = [c[1] for c in columns]
    table_width = sum(col_widths)
    padding_x = 30
    img_width = table_width + padding_x * 2

    row_height = 28
    header_row_height = 32

    # Calculate image height
    y_cursor = 20  # top margin
    y_cursor += 30  # title
    y_cursor += 20  # subtitle
    if customer_info and any(customer_info.get(k) for k in ("name", "name_en", "phone", "date")):
        y_cursor += 22  # customer line
    y_cursor += 15  # spacing before table
    y_cursor += header_row_height  # table header
    y_cursor += row_height * len(matched_lines)  # data rows
    y_cursor += row_height  # grand total row
    y_cursor += 30  # footer
    y_cursor += 20  # bottom margin

    img_height = y_cursor

    # Create image
    img = Image.new("RGB", (img_width, img_height), _BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = 20

    # ── Title ────────────────────────────────────────────────────
    title = "SAI-ABS Order Summary"
    bbox = draw.textbbox((0, 0), title, font=_FONT_TITLE)
    tw = bbox[2] - bbox[0]
    draw.text(((img_width - tw) / 2, y), title, fill=_HEADER_BG, font=_FONT_TITLE)
    y += 32

    # ── Subtitle ─────────────────────────────────────────────────
    sub_parts = []
    if order_id:
        sub_parts.append(f"Order: {order_id}")
    sub_parts.append(f"Date: {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    sub_parts.append(f"Items: {len(matched_lines)}")
    subtitle = " | ".join(sub_parts)
    bbox = draw.textbbox((0, 0), subtitle, font=_FONT_SUBTITLE)
    sw = bbox[2] - bbox[0]
    draw.text(((img_width - sw) / 2, y), subtitle, fill=_SUBTITLE_COLOR, font=_FONT_SUBTITLE)
    y += 20

    # ── Customer Info ────────────────────────────────────────────
    if customer_info and any(customer_info.get(k) for k in ("name", "name_en", "phone", "date")):
        cust_parts = []
        name_display = customer_info.get("name_en") or customer_info.get("name", "")
        if name_display:
            cust_parts.append(f"Customer: {name_display}")
        if customer_info.get("phone"):
            cust_parts.append(f"Phone: {customer_info['phone']}")
        if customer_info.get("date"):
            cust_parts.append(f"Date: {customer_info['date']}")
        cust_text = " | ".join(cust_parts)
        bbox = draw.textbbox((0, 0), cust_text, font=_FONT_SUBTITLE)
        cw = bbox[2] - bbox[0]
        draw.text(((img_width - cw) / 2, y), cust_text, fill=_TEXT_COLOR, font=_FONT_SUBTITLE)
        y += 22

    y += 15  # spacing

    # ── Table Header ─────────────────────────────────────────────
    x = padding_x
    draw.rectangle([x, y, x + table_width, y + header_row_height], fill=_HEADER_BG)
    for i, (header, width, align) in enumerate(columns):
        cell_x = x
        bbox = draw.textbbox((0, 0), header, font=_FONT_HEADER)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if align == "center":
            tx = cell_x + (width - text_w) / 2
        elif align == "right":
            tx = cell_x + width - text_w - 6
        else:
            tx = cell_x + 6
        ty = y + (header_row_height - text_h) / 2
        draw.text((tx, ty), header, fill=_HEADER_FG, font=_FONT_HEADER)
        x += width
    y += header_row_height

    # ── Data Rows ────────────────────────────────────────────────
    for row_idx, line in enumerate(matched_lines):
        # Format values
        price_val = line.get("price", "")
        lt_val = line.get("line_total", "")
        try:
            price_val = f"{float(price_val):,.2f}" if price_val else ""
        except (ValueError, TypeError):
            price_val = str(price_val)
        try:
            lt_val = f"{float(lt_val):,.2f}" if lt_val else ""
        except (ValueError, TypeError):
            lt_val = str(lt_val)

        cells = [
            str(line.get("sn", "")),
            str(line.get("part_name", "")),
            str(line.get("part_number", "")),
            str(price_val),
            str(line.get("qty", "")),
            str(lt_val),
        ]

        # Row background
        is_unmatched = line.get("match_type") == "UNMATCHED"
        if is_unmatched:
            bg = _UNMATCHED_BG
        elif row_idx % 2 == 1:
            bg = _ALT_ROW_BG
        else:
            bg = _BG_COLOR

        x = padding_x
        draw.rectangle([x, y, x + table_width, y + row_height], fill=bg)

        for i, (_, width, align) in enumerate(columns):
            text = cells[i]
            # Truncate long part names
            if i == 1 and len(text) > 42:
                text = text[:40] + ".."
            font = _FONT_CELL
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            if align == "center":
                tx = x + (width - text_w) / 2
            elif align == "right":
                tx = x + width - text_w - 6
            else:
                tx = x + 6
            ty = y + (row_height - text_h) / 2
            draw.text((tx, ty), text, fill=_TEXT_COLOR, font=font)
            x += width

        # Grid lines
        draw.line([padding_x, y + row_height, padding_x + table_width, y + row_height], fill=_GRID_COLOR, width=1)
        y += row_height

    # ── Grand Total Row ──────────────────────────────────────────
    x = padding_x
    draw.rectangle([x, y, x + table_width, y + row_height], fill=_TOTAL_BG)
    # Draw "GRAND TOTAL" in the QTY column area
    gt_label = "GRAND TOTAL"
    gt_value = f"{grand_total:,.2f}"
    # Label spans columns 0-4
    label_width = sum(col_widths[:5])
    bbox = draw.textbbox((0, 0), gt_label, font=_FONT_CELL_BOLD)
    text_h = bbox[3] - bbox[1]
    text_w = bbox[2] - bbox[0]
    draw.text(
        (x + label_width - text_w - 6, y + (row_height - text_h) / 2),
        gt_label, fill=_TEXT_COLOR, font=_FONT_CELL_BOLD
    )
    # Value in last column
    bbox = draw.textbbox((0, 0), gt_value, font=_FONT_CELL_BOLD)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(
        (x + table_width - text_w - 6, y + (row_height - text_h) / 2),
        gt_value, fill=_TEXT_COLOR, font=_FONT_CELL_BOLD
    )
    # Top border for total row
    draw.line([padding_x, y, padding_x + table_width, y], fill=_HEADER_BG, width=2)
    draw.line([padding_x, y + row_height, padding_x + table_width, y + row_height], fill=_HEADER_BG, width=2)
    y += row_height

    # ── Vertical grid lines ──────────────────────────────────────
    table_top = y - row_height * (len(matched_lines) + 1) - header_row_height
    table_bottom = y
    gx = padding_x
    for w in col_widths:
        draw.line([gx, table_top, gx, table_bottom], fill=_GRID_COLOR, width=1)
        gx += w
    draw.line([gx, table_top, gx, table_bottom], fill=_GRID_COLOR, width=1)

    # ── Footer ───────────────────────────────────────────────────
    y += 12
    footer = f"Generated by SAI-ABS Order Scanner | {datetime.now().strftime('%d %b %Y %H:%M')}"
    bbox = draw.textbbox((0, 0), footer, font=_FONT_FOOTER)
    fw = bbox[2] - bbox[0]
    draw.text(((img_width - fw) / 2, y), footer, fill=_FOOTER_COLOR, font=_FONT_FOOTER)

    # ── Save ─────────────────────────────────────────────────────
    out_dir = output_dir or config.TEMP_FOLDER or "temp"
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"order_{order_id or 'upload'}_{timestamp}.png"
    img_path = os.path.join(out_dir, filename)
    img.save(img_path, "PNG", optimize=True)
    return os.path.abspath(img_path)
