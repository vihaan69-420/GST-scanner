"""
Phase 3 – OCR Extraction Logic (text → structured lines)
========================================================

This module holds the *parsing* logic for handwritten order OCR text.
It does NOT:
- touch existing GST invoice parsing,
- write to Google Sheets,
- or integrate with Telegram yet.

All usage of this module must be guarded by config.ENABLE_ORDER_UPLOAD.

Intermediate JSON shape per extracted line:
{
    "sn": int,             # serial number from the page
    "part_name": str,      # part description text
    "qty": int,            # quantity from circled number ONLY
    "source_page": int,    # 1-based page index
}

Customer info shape (from page header):
{
    "phone": str,          # 10-digit phone or ""
    "name": str,           # Hindi/Devanagari name or ""
    "name_en": str,        # English transliteration or ""
    "date": str,           # date as written on paper or ""
}
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
import re


@dataclass
class OrderLine:
    sn: int
    part_name: str
    qty: int
    source_page: int

    def to_dict(self) -> Dict:
        return asdict(self)


def _split_multi_segments(sn: int, base_text: str, page_no: int) -> List[OrderLine]:
    """
    Split a single OCR line that may contain multiple colour/variant + qty pairs.

    Heuristic:
    - We look for repeated "(some words) <number>" patterns.
    - Each pattern becomes one OrderLine with the same S.N.

    Example (simplified OCR text):
        "11 Sai- Jupiter Blewerk 5 old Access white 5"
    -> [
         (sn=11, part_name="Jupiter Blewerk", qty=5),
         (sn=11, part_name="old Access white", qty=5),
       ]
    """
    text = base_text.strip()
    if not text:
        return []

    # Remove common dealer prefix if present
    text = re.sub(r"^\s*Sai[-\s]+", "", text, flags=re.IGNORECASE)

    # Find candidate quantity tokens:
    # - We treat ONLY 1–2 digit numbers as quantities (per problem statement:
    #   quantities are single- or double-digit circled numbers).
    # - Longer numbers (e.g. "110" in "iSmart 110 Blue") are treated as
    #   part of the description, not as quantities.
    segments: List[OrderLine] = []
    pattern = re.compile(r"(\d+)(?:\s+|$)")
    last_end = 0
    for match in pattern.finditer(text):
        num = match.group(1)
        # Ignore 3+ digit numbers – they are almost certainly model codes
        # (e.g. 110) rather than quantities.
        if len(num) > 2:
            continue
        qty = int(num)
        seg_text = text[last_end : match.start()].strip()
        if seg_text:
            # Clean duplicate whitespace and commas around segment
            seg_text = re.sub(r"\s+", " ", seg_text).strip(" ,")
            segments.append(
                OrderLine(sn=sn, part_name=seg_text, qty=qty, source_page=page_no)
            )
        last_end = match.end()

    # If no numeric segments were found, treat whole line as one item with qty=0
    if not segments:
        cleaned = re.sub(r"\s+", " ", text).strip(" ,")
        if cleaned:
            segments.append(OrderLine(sn=sn, part_name=cleaned, qty=0, source_page=page_no))

    return segments


def _apply_ditto(previous_part: str, part_text: str) -> str:
    """
    Apply ditto (~) semantics conservatively.

    Rules:
    - If part_text starts with '~', inherit the previous_part and append the
      remaining explicit text.
    - Do NOT invent words not present in either previous_part or part_text.
    """
    text = part_text.strip()
    if not text.startswith("~"):
        return text
    suffix = text[1:].strip()
    if not previous_part:
        return suffix
    # Simple inheritance: carry forward previous full description, append suffix.
    return f"{previous_part} {suffix}".strip()


def _is_tab_separated(ocr_text: str) -> bool:
    """Check if OCR output uses the new tab-separated structured format."""
    lines = [l for l in ocr_text.splitlines() if l.strip()]
    if not lines:
        return False
    tab_lines = sum(1 for l in lines if "\t" in l)
    return tab_lines >= len(lines) * 0.5  # at least 50% of lines have tabs


def _extract_structured(page_no: int, ocr_text: str) -> List[OrderLine]:
    """
    Parse tab-separated structured OCR output.
    Format: S.N[TAB]Part Description[TAB]Quantity
    """
    lines: List[OrderLine] = []
    for raw_line in ocr_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            try:
                sn = int(re.sub(r"[^\d]", "", parts[0]) or "0")
            except ValueError:
                continue
            part_name = parts[1].strip()
            # Remove "Sai-" or "Sai " prefix if present
            part_name = re.sub(r"^\s*Sai[-\s]+", "", part_name, flags=re.IGNORECASE).strip()
            try:
                qty = int(re.sub(r"[^\d]", "", parts[2]) or "0")
            except ValueError:
                qty = 0
            if part_name:
                lines.append(OrderLine(sn=sn, part_name=part_name, qty=qty, source_page=page_no))
        elif len(parts) == 2:
            # S.N + rest, try to extract qty from end
            try:
                sn = int(re.sub(r"[^\d]", "", parts[0]) or "0")
            except ValueError:
                continue
            rest = parts[1].strip()
            rest = re.sub(r"^\s*Sai[-\s]+", "", rest, flags=re.IGNORECASE).strip()
            qty_match = re.search(r"\s+(\d{1,2})\s*$", rest)
            if qty_match:
                qty = int(qty_match.group(1))
                part_name = rest[:qty_match.start()].strip()
            else:
                qty = 0
                part_name = rest
            if part_name:
                lines.append(OrderLine(sn=sn, part_name=part_name, qty=qty, source_page=page_no))
    return lines


def extract_lines_from_page(page_no: int, ocr_text: str) -> List[OrderLine]:
    """
    Parse OCR text from a single page into structured order lines.

    Supports two formats:
    1. New structured tab-separated format (from improved OCR prompt)
    2. Legacy free-text format (fallback)
    """
    # Try structured format first
    if _is_tab_separated(ocr_text):
        return _extract_structured(page_no, ocr_text)

    # Fallback: legacy free-text parsing
    lines: List[OrderLine] = []
    prev_part_name = ""

    for raw_line in ocr_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Extract leading serial number (S.N)
        sn_match = re.match(r"^(\d+)[\.\)]?\s+(.*)$", line)
        if not sn_match:
            continue

        sn = int(sn_match.group(1))
        rest = sn_match.group(2).strip()

        # Apply ditto (~) at line level before splitting into segments
        rest = _apply_ditto(prev_part_name, rest)

        # Split into one or more segments with their own qty
        segments = _split_multi_segments(sn, rest, page_no)
        if not segments:
            continue

        # Propagate base model name to colour-only segments
        if len(segments) > 1 and segments[0].part_name:
            base_tokens = segments[0].part_name.split()
            base_model = base_tokens[0] if base_tokens else ""
            if base_model:
                for seg in segments[1:]:
                    if base_model.lower() not in seg.part_name.lower():
                        seg.part_name = f"{base_model} {seg.part_name}".strip()

        if segments[0].part_name:
            prev_part_name = segments[0].part_name

        lines.extend(segments)

    return lines


def _split_header_and_body(ocr_text: str) -> Tuple[str, str]:
    """
    Split OCR text into header section and body (line items) section.

    The header is separated from the body by a line containing only '---'.
    If no separator is found, the entire text is treated as body (backward compat).

    Returns:
        (header_text, body_text)
    """
    # Look for the --- separator
    separator_pattern = re.compile(r"^-{3,}\s*$", re.MULTILINE)
    match = separator_pattern.search(ocr_text)
    if match:
        header = ocr_text[: match.start()].strip()
        body = ocr_text[match.end() :].strip()
        return header, body
    # No separator → entire text is body (backward compatibility)
    return "", ocr_text


def extract_customer_info(ocr_text: str) -> Dict:
    """
    Extract customer header info from OCR text.

    Expected header format (before the '---' separator):
        PHONE[TAB]<phone>
        NAME[TAB]<Hindi name> (<English transliteration>)
        DATE[TAB]<date>

    Returns:
        Dict with keys: phone, name, name_en, date (all str, empty if not found)
    """
    result = {"phone": "", "name": "", "name_en": "", "date": ""}
    header, _ = _split_header_and_body(ocr_text)
    if not header:
        return result

    for raw_line in header.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Try tab-separated key-value first
        if "\t" in line:
            key, _, value = line.partition("\t")
        else:
            # Fallback: first word is the key, rest is value
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            key, value = parts[0], parts[1]

        key = key.strip().upper()
        value = value.strip()

        if key == "PHONE":
            # Extract digits – accept 10-digit Indian mobile numbers
            phone_digits = re.sub(r"[^\d]", "", value)
            if len(phone_digits) >= 10:
                phone_digits = phone_digits[-10:]  # last 10 digits
            result["phone"] = phone_digits if phone_digits and phone_digits != "UNKNOWN" else ""
            # Handle literal UNKNOWN
            if "UNKNOWN" in value.upper():
                result["phone"] = ""

        elif key == "NAME":
            if "UNKNOWN" in value.upper():
                continue
            # Parse "Hindi (English)" pattern
            paren_match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", value)
            if paren_match:
                result["name"] = paren_match.group(1).strip()
                result["name_en"] = paren_match.group(2).strip()
            else:
                result["name"] = value
                result["name_en"] = ""

        elif key == "DATE":
            if "UNKNOWN" in value.upper():
                continue
            result["date"] = value

    return result


def extract_all_from_page(page_no: int, ocr_text: str) -> Tuple[Dict, List[OrderLine]]:
    """
    Extract both customer info and order lines from a single page's OCR text.

    This is the unified entry point that handles the new header format while
    preserving full backward compatibility (text without headers still works).

    Returns:
        (customer_info_dict, list_of_OrderLine)
    """
    customer_info = extract_customer_info(ocr_text)
    _, body = _split_header_and_body(ocr_text)
    lines = extract_lines_from_page(page_no, body)
    return customer_info, lines


def extract_lines_from_pages(pages: List[Dict]) -> List[Dict]:
    """
    High-level helper: given a list of pages:
        [{\"page_no\": 1, \"text\": \"...\"}, ...]
    return a flat list of line dicts suitable for Phase 3 intermediate JSON.
    """
    results: List[Dict] = []
    for page in pages:
        page_no = int(page.get("page_no", 1))
        text = page.get("text", "") or ""
        for line in extract_lines_from_page(page_no, text):
            results.append(line.to_dict())
    return results


def extract_all_from_pages(pages: List[Dict]) -> Tuple[Dict, List[Dict]]:
    """
    High-level helper that extracts both customer info and order lines from
    all pages. Customer info is merged: first page with non-empty values wins
    for each field.

    Returns:
        (merged_customer_info, flat_list_of_line_dicts)
    """
    merged_customer: Dict = {"phone": "", "name": "", "name_en": "", "date": ""}
    all_lines: List[Dict] = []

    for page in pages:
        page_no = int(page.get("page_no", 1))
        text = page.get("text", "") or ""
        customer_info, lines = extract_all_from_page(page_no, text)

        # Merge: first non-empty value wins for each field
        for key in ("phone", "name", "name_en", "date"):
            if not merged_customer[key] and customer_info.get(key):
                merged_customer[key] = customer_info[key]

        for line in lines:
            all_lines.append(line.to_dict())

    return merged_customer, all_lines


