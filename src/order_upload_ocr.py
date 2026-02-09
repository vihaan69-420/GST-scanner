"""
Phase 3 – Dev-only OCR runner for Order Upload
=============================================

This module performs OCR for handwritten order images using Gemini Vision.

Guardrails:
- Must only be used when config.ENABLE_ORDER_UPLOAD is True.
- Does NOT modify existing invoice OCR engine (src/ocr/ocr_engine.py).
- Not wired into production Telegram bot yet (dev-only for now).
"""
from __future__ import annotations

from typing import List, Dict
import os

from PIL import Image
import google.generativeai as genai

try:
    from src import config
except ImportError:
    import config


ORDER_OCR_PROMPT = """
You are an expert at reading HANDWRITTEN ORDER LISTS for two-wheeler (motorcycle/scooter) spare parts.

CONTEXT: These are orders for SAI-ABS brand aftermarket parts. Common product types include:
- Body Kit, Side Panel, Front Fender, Rear Fender, Mudguard
- Visor, Nose (front visor), Headlight (written as "HF DLX", "HFDLS", "HFD" etc.)
- Suspension, Side Cowl, Rear Cowl
- Various two-wheeler models: Activa, Shine, Jupiter, Splendor, Passion/Pass, 
  Access, Pleasure, Dream Neo/Yuga, Maestro, Duet, i-Smart, XPro, Pulsar, etc.

INSTRUCTIONS:
1. Read each handwritten line from top to bottom.
2. For each order line, output:
   S.N | Full Part Description | Quantity (from circled number)
3. INTERPRET abbreviations and shorthand into full readable names:
   - "HF DLX" / "HFDLS" / "HFD" → "Headlight Visor" or "Head Light"
   - "susp" / "suspoid" → "Suspension"  
   - "Pass pro" / "Pass+" → "Passion Pro" / "Passion Plus"
   - "SP" → "Splendor"
   - "BSG" / "BS6" / "BS4" → "BS6" (emission standard)
   - "BL" / "Blk" / "Bkh" → "Black"
   - "m/Grey" → "Matt Grey"
   - "S/Red" → "Sports Red" or "Silver Red"
   - "wrey" / "wree" → "Grey" (likely misread)
   - "Bl/Grey" → "Black/Grey" or "Blue/Grey" (use context)
   - "Type S" / "Type 7" / "Type 5" → keep the model type number as part of the name (e.g. "Shine Type 7")
4. When a line has ditto marks (~ or -), carry forward the PRODUCT TYPE from the previous line
   and combine with the new model/color on this line.
5. If a line has MULTIPLE colors with separate circled quantities, output each as a SEPARATE line
   with the same S.N (e.g., "White 3 Red 3 BL 3" → three lines).
6. The quantity is ALWAYS the circled number at the end of each item/color.
7. Numbers that are part of model names (like "110" in "iSmart 110", "125" in "Activa 125",
   "3G" in "Activa 3G", "5G" in "Activa 5G") are NOT quantities.

OUTPUT FORMAT (tab-separated, one line per item):
S.N[TAB]Part Description[TAB]Quantity

Example output:
1	Body Kit Fit For Stereo Black/Grey	2
2	Visor Fit For Activa 3G Blue	5
3	Visor Fit For iSmart 110 Blue	5
4	Side Panel Fit For Activa 125 White	5
5	Headlight Visor Fit For BS6 Black/Grey	10
"""


def _ensure_order_upload_enabled() -> None:
    """Fail fast if the feature flag is not enabled."""
    if not config.ENABLE_ORDER_UPLOAD:
        raise RuntimeError(
            "Order Upload OCR is disabled. Set ENABLE_ORDER_UPLOAD=true in .env to use this module."
        )


class OrderOcrRunner:
    """Dev-only OCR runner for order upload images."""

    def __init__(self) -> None:
        _ensure_order_upload_enabled()
        genai.configure(api_key=config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def ocr_single_image(self, image_path: str) -> str:
        """Run OCR on a single image and return raw text for that page."""
        image = Image.open(image_path)
        response = self.model.generate_content([ORDER_OCR_PROMPT, image])
        return (response.text or "").strip()

    def ocr_images(self, image_paths: List[str]) -> List[Dict]:
        """
        OCR multiple images for a single order.

        Returns:
            List[Dict] with:
                { "page_no": int, "text": str, "image_path": str }
        """
        pages: List[Dict] = []
        for idx, path in enumerate(image_paths, start=1):
            if not os.path.exists(path):
                pages.append({"page_no": idx, "text": "", "image_path": path})
                continue
            try:
                text = self.ocr_single_image(path)
            except Exception as e:
                text = f"[OCR ERROR: {e}]"
            pages.append({"page_no": idx, "text": text, "image_path": path})
        return pages


