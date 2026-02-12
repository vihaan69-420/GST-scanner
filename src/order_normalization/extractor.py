"""
Order Extractor
Extracts structured line items from handwritten order notes using OCR + LLM
"""
import json
from datetime import datetime
from typing import Dict, List
import google.generativeai as genai
import config
from ocr.ocr_engine import OCREngine


class OrderExtractor:
    """Extracts line items from handwritten order images"""
    
    def __init__(self):
        """Initialize extractor with OCR engine and LLM"""
        # Reuse existing OCR engine (read-only, no modifications)
        self.ocr_engine = OCREngine()
        
        # Initialize Gemini for structured extraction
        genai.configure(api_key=config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Extraction prompt for handwritten orders
        self.extraction_prompt = """
Extract line items from this handwritten order note. This is a handwritten bill/order for vehicle accessories.

═══════════════════════════════════════════════════
RULE 1: HEADER INFORMATION (TOP OF PAGE)
═══════════════════════════════════════════════════
Extract customer details from the top of the page:
- **Mobile number**: 10-digit number starting with 6/7/8/9 (e.g. 7427096261)
- **Date**: Usually in DD/MM/YY format (e.g. 13/12/25)
- **Customer name**: The name written near the phone number. If in Hindi/Devanagari script, TRANSLITERATE it to English/Roman letters (e.g. "हरे का गोट" → "Hare Ka Got")
- **Location**: City/place name. If in Hindi/Devanagari, TRANSLITERATE to English (e.g. "सोलापूर" → "Solapur")

CRITICAL: Always romanize/transliterate non-English text to English letters. Never return Hindi/Devanagari/other scripts.

═══════════════════════════════════════════════════
RULE 2: DITTO MARKS - MOST IMPORTANT RULE
═══════════════════════════════════════════════════
Ditto marks ("--", "~~", "~", "-~-", "- -", wavy lines, squiggly marks between "Sai" and the rest) mean "SAME PART NAME AS THE MOST RECENT EXPLICITLY WRITTEN PART NAME ABOVE".

The ditto copies the PART NAME (product type like "Visor", "Body Kit"). The ditto chain continues for ALL subsequent lines that have ditto marks, even if there are 20+ lines with dittos.

CRITICAL: "Type 7", "SP", "Type 5", "Pass+", "Pass Pro", "Susp Old", etc. written AFTER ditto marks are NOT the part name. They are variant/model identifiers. The part name is still the ditto value.

FULL EXAMPLE (this exact pattern is common):
  (1) Sai - Body Kit  Stound BL/Grey (2)         → part_name = "Body Kit", model = "Stound"
  (2) Sai - Visor     Activa 3G Blue (5)          → part_name = "Visor", model = "Activa 3G"
  (3) Sai ~~ ~~       iSmart 110 Blue (5)         → DITTO → part_name = "Visor", model = "iSmart 110"
  (4) Sai ~~ ~~       Activa 125 White (5)        → DITTO → part_name = "Visor", model = "Activa 125"
  (5) Sai ~~ ~~       HF Dlx BS4 BL/Grey (10)    → DITTO → part_name = "Visor", model = "HF Dlx BS4"
  (6) Sai ~~ ~~       Susp Old Bh/Blue (5)        → DITTO → part_name = "Visor", model = "Susp Old"
  (7) Sai ~~ ~~       Type 7 Shine Grey/Red (5)   → DITTO → part_name = "Visor", model = "Type 7 Shine"
  (8) Sai ~~ ~~       SP Shine Blue (2)           → DITTO → part_name = "Visor", model = "SP Shine"
  (9) Sai ~~ ~~       Shine Type 5 M/Grey (5)     → DITTO → part_name = "Visor", model = "Shine Type 5"
  (10) Sai ~~ ~~      Type 7 Shine Grey (5)       → DITTO → part_name = "Visor", model = "Type 7 Shine"
  (11) Sai ~~ ~~      Jupiter Blue (5)            → DITTO → part_name = "Visor", model = "Jupiter"
  (12) Sai ~~ ~~      Pass+ Blairek/Orange (5)    → DITTO → part_name = "Visor", model = "Pass+"
  (13) Sai ~~ ~~      Type 5 Shine S/Red (5)      → DITTO → part_name = "Visor", model = "Type 5 Shine"
  (14) Sai ~~ ~~      Activa 5G Silver (3)        → DITTO → part_name = "Visor", model = "Activa 5G"
  (15) Sai ~~ ~~      Pass Pro Old Bl/Red (5)     → DITTO → part_name = "Visor", model = "Pass Pro Old"
  (16) Sai ~~ ~~      X Pro (2018) i3S Bl/Red (4) → DITTO → part_name = "Visor", model = "X Pro i3S"
  (17) Sai ~~ ~~      Access BS6 Lgnt/Green (3)   → DITTO → part_name = "Visor", model = "Access BS6"
  (18) Sai ~~ ~~      Dream Neo S/Red (5)         → DITTO → part_name = "Visor", model = "Dream Neo"
  (19) Sai ~~ ~~      Duet Grey (4), White (4)    → DITTO → part_name = "Visor", model = "Duet"
  (20) Sai ~~ ~~      Redwan Wine/Red (4)         → DITTO → part_name = "Visor", model = "Redwan"
  (21) Sai ~~ ~~      BS6 Shine Grey/Golden (4)   → DITTO → part_name = "Visor", model = "BS6 Shine"

HOW TO DETECT DITTO: Look at the space between "Sai" and the next meaningful text. If there are wavy lines (~~), squiggly marks, or dashes instead of a written-out part name, it is a ditto mark. The ditto chain continues until a NEW product type word is EXPLICITLY written out.

PRODUCT TYPES (these are the ONLY valid part names - actual product categories):
Body Kit, Visor, Head Light Visor, Mudguard, Front Fender, Rear Fender, Handle Bar,
Leg Guard, Crash Guard, Engine Guard, Side Cowl, Rear Cowl, Front Cover,
Tank Pad, Seat Cover, Side Panel, Indicator, Mirror, Grip, Back Plate, Foot Trim

NOT PRODUCT TYPES (these are variant/model identifiers that go in model_raw):
Type 5, Type 7, Type 2, Type 3, Type 8, SP, Pass+, Pass Pro, Passport Plus, Passport Pro,
Susp, Susp Old, Access, Duet, Shine, Jupiter, Dream Neo, Redwan, X Pro, BS6, BS4

═══════════════════════════════════════════════════
RULE 3: LINE FORMAT & ROW COUNT
═══════════════════════════════════════════════════
Format: (Serial) Brand - Part_Name Model Color (Quantity)

- **brand**: Usually "Sai" (vehicle accessories brand)
- **part_name_raw**: The PRODUCT TYPE only (Body Kit, Visor, Mudguard, etc.)
  - If ditto marks present → copy part_name from the most recent explicitly written part_name above
  - "Type 7", "SP", "Pass+", etc. are NOT part names — put them in model_raw
  - NEVER leave part_name_raw empty!
- **model_raw**: The vehicle model + variant info (Activa 3G, Type 7 Shine, SP Shine, Pass+ etc.)
- **color_raw**: Color codes as written (BL/Grey, PA/Grey, Blue, S/Red, etc.)
- **quantity**: Number in parentheses at end of line

CRITICAL ROW COUNT RULE:
- The number of output line_items MUST EXACTLY MATCH the number of serial numbers in the handwritten note
- Each handwritten serial number (1, 2, 3... 21) = exactly ONE line_item in the output
- Do NOT split one handwritten line into multiple output rows
- If a line has multiple colors/quantities like "Grey (4), White (4)":
  → Output as ONE line_item with color_raw="Grey, White" and quantity=8 (sum of quantities)
- If a line mentions two models like "Jupiter Blue (5) old Access White":
  → This is ONE line_item. Include all info: model_raw="Jupiter / Access Old", color_raw="Blue, White", quantity=10

═══════════════════════════════════════════════════
RULE 4: WORD RECOGNITION
═══════════════════════════════════════════════════
Pay special attention to handwriting recognition:
- "Visor" (not "visar", "visor" is correct)
- "Access" (not "Accesss") - refers to Suzuki Access scooter
- "BSG" or "BS6" = BS6 (emission standard variant)
- "HFDlx" = "HF Deluxe" (Hero bike model)
- "Susp" or "Susp Old" = Suspension variant (model identifier, NOT a product type)
- "Pass+" = Passport Plus (model identifier, NOT a product type)
- "Pass Pro" = Passport Pro (model identifier, NOT a product type)
- "xpro" / "X Pro" = TVS XPro
- "i3S" = idle Start Stop System variant
- "Stound" = Stound (a variant name)
- "SP Shine" = SP variant of Shine model
- "Type 5", "Type 7" = style variant identifiers (go in model_raw, NOT part_name)
- "Duet" = Hero Duet scooter model
- "Pednum" or "Platinum" = Bajaj Platina / Hero Pleasure variant

═══════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════
Return ONLY valid JSON (no markdown code blocks):
{
  "order_metadata": {
    "customer_name": "romanized name (English letters only)",
    "mobile_number": "10 digit number or null",
    "order_date": "DD/MM/YY or null",
    "location": "romanized location (English letters only) or null"
  },
  "line_items": [
    {
      "serial_no": 1,
      "brand": "Sai",
      "part_name_raw": "Body Kit",
      "model_raw": "Stound",
      "color_raw": "BL/Grey",
      "quantity": 2
    },
    {
      "serial_no": 2,
      "brand": "Sai",
      "part_name_raw": "Visor",
      "model_raw": "Activa 3G",
      "color_raw": "Blue",
      "quantity": 5
    },
    {
      "serial_no": 3,
      "brand": "Sai",
      "part_name_raw": "Visor",
      "model_raw": "iSmart 110",
      "color_raw": "Blue",
      "quantity": 5
    },
    {
      "serial_no": 7,
      "brand": "Sai",
      "part_name_raw": "Visor",
      "model_raw": "Type 7 Shine",
      "color_raw": "Grey/Red",
      "quantity": 5
    }
  ]
}

CRITICAL REMINDERS:
- ALWAYS romanize Hindi/Devanagari text to English letters
- ALWAYS resolve ditto marks (~~) by copying part_name from previous non-ditto line
- The ditto chain can span 20+ lines — keep copying until a NEW product type is written out
- "Type 7", "SP", "Pass+", "Type 5", "Pass Pro" are NOT product types — they go in model_raw
- NEVER leave part_name_raw empty - if unclear, use the previous line's part name
- Output row count MUST match the handwritten serial numbers (e.g., 21 lines = 21 items)
- Do NOT split one handwritten line into multiple items
"""
    
    def extract_order_lines(self, image_path: str, page_number: int) -> Dict:
        """
        Extract line items from a single order page
        
        Args:
            image_path: Path to order image
            page_number: Page number (for tracking)
            
        Returns:
            Dictionary with extracted data:
            {
                'page_number': int,
                'ocr_text': str,
                'order_metadata': Dict,
                'lines_raw': List[Dict],
                'extraction_timestamp': datetime
            }
        """
        try:
            # Step 1: OCR text extraction (reuse existing engine)
            print(f"[ORDER_EXTRACT] OCR extraction for page {page_number}...")
            ocr_result = self.ocr_engine.extract_text_from_image(image_path)
            ocr_text = ocr_result['text'] if isinstance(ocr_result, dict) else ocr_result
            
            # Step 2: LLM structured extraction with image
            print(f"[ORDER_EXTRACT] LLM extraction for page {page_number}...")
            
            # Load image for better recognition
            import PIL.Image
            image = PIL.Image.open(image_path)
            
            # Send both prompt and image to Gemini
            response = self.model.generate_content([self.extraction_prompt, image])
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Clean markdown if present
            if response_text.startswith('```'):
                # Remove markdown code blocks
                lines = response_text.split('\n')
                response_text = '\n'.join([
                    line for line in lines 
                    if not line.strip().startswith('```') and not line.strip() == 'json'
                ])
            
            extracted_data = json.loads(response_text)
            
            # Handle both old and new format
            if isinstance(extracted_data, dict) and 'line_items' in extracted_data:
                # New format with metadata
                lines_raw = extracted_data.get('line_items', [])
                order_metadata = extracted_data.get('order_metadata', {})
            elif isinstance(extracted_data, list):
                # Old format - just lines
                lines_raw = extracted_data
                order_metadata = {}
            else:
                lines_raw = []
                order_metadata = {}
            
            # Post-process: resolve any remaining ditto marks in part names
            lines_raw = self._resolve_ditto_marks(lines_raw)
            
            # Post-process: sanitize metadata (ensure romanized text)
            order_metadata = self._sanitize_metadata(order_metadata)
            
            print(f"[ORDER_EXTRACT] Extracted {len(lines_raw)} lines from page {page_number}")
            if order_metadata:
                print(f"[ORDER_EXTRACT] Metadata: {order_metadata}")
            
            return {
                'page_number': page_number,
                'ocr_text': ocr_text,
                'order_metadata': order_metadata,
                'lines_raw': lines_raw,
                'extraction_timestamp': datetime.now()
            }
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parsing failed for page {page_number}: {e}")
            print(f"[ERROR] Response text: {response_text[:500]}")
            # Return empty lines on parse failure
            return {
                'page_number': page_number,
                'ocr_text': ocr_text,
                'order_metadata': {},
                'lines_raw': [],
                'extraction_timestamp': datetime.now(),
                'error': f"JSON parse error: {str(e)}"
            }
        
        except Exception as e:
            print(f"[ERROR] Extraction failed for page {page_number}: {e}")
            raise Exception(f"Order extraction failed: {str(e)}")
    
    # DEFINITE product types - these are actual product categories (accessories).
    # ONLY these can break a ditto chain. Everything else is a variant/model identifier.
    KNOWN_PRODUCT_TYPES = {
        'body kit', 'kit', 'visor', 'head light visor', 'mudguard', 'fender',
        'front fender', 'rear fender', 'leg guard', 'crash guard', 'engine guard',
        'side cowl', 'rear cowl', 'front cover', 'nose', 'handle bar',
        'tank pad', 'seat cover', 'side panel', 'indicator', 'mirror', 'grip',
        'tpfc', 'back plate', 'foot trim', 'lower',
    }
    
    # Variant/model identifiers - these look like part names but are actually
    # variant descriptors that should NOT break a ditto chain.
    VARIANT_IDENTIFIERS = {
        'type 2', 'type 3', 'type 5', 'type 7', 'type 8',
        'sp', 'pass+', 'pass pro', 'passport plus', 'passport pro',
        'susp', 'susp old', 'suspension', 'suspension old',
        'access', 'duet', 'jupiter', 'shine', 'dream neo',
        'bs4', 'bs6', 'bs7', 'old', 'new',
    }
    
    def _resolve_ditto_marks(self, lines: List[Dict]) -> List[Dict]:
        """
        Post-process: resolve any remaining ditto marks in extracted lines.
        
        AGGRESSIVE ditto resolution strategy:
        1. If part_name is empty or contains ditto symbols → copy from ditto chain
        2. If part_name is a variant identifier (Type 7, SP, Pass+, etc.) and a ditto
           chain is active → move part_name to model_raw, copy from ditto chain
        3. If part_name looks like a vehicle model/variant and ditto chain is active → copy
        4. ONLY a definite product type (Visor, Body Kit, etc.) can START or BREAK the chain
        """
        if not lines:
            return lines
        
        # The "ditto chain" part name - persists across many lines
        ditto_chain_part_name = ''
        ditto_chain_active = False
        
        for line in lines:
            part_name = (line.get('part_name_raw') or '').strip()
            model = (line.get('model_raw') or '').strip()
            serial = line.get('serial_no', '?')
            
            # Check 1: explicit ditto indicators (empty, ~~, --, etc.)
            ditto_indicators = ['--', '~~', '-~-', '~', '- -', 'ditto', '\u3003', '"']
            is_explicit_ditto = (
                not part_name or 
                any(part_name.strip() in [d, d.strip()] for d in ditto_indicators) or
                part_name.strip() in ['', '-', '~']
            )
            
            if is_explicit_ditto and ditto_chain_part_name:
                print(f"[DITTO_FIX] Line {serial}: Explicit ditto -> copying '{ditto_chain_part_name}'")
                line['part_name_raw'] = ditto_chain_part_name
                ditto_chain_active = True
                continue
            
            # Check 2: Is this a DEFINITE product type? (breaks/starts the chain)
            if self._is_known_product_type(part_name):
                print(f"[DITTO] Line {serial}: New product type '{part_name}' - starting/updating ditto chain")
                ditto_chain_part_name = part_name
                ditto_chain_active = True
                continue
            
            # Check 3: part_name is a VARIANT IDENTIFIER and ditto chain is active
            # e.g., "Type 7" when ditto chain = "Visor" → part_name = "Visor", model = "Type 7 Shine"
            if part_name and ditto_chain_active and ditto_chain_part_name:
                if self._is_variant_identifier(part_name):
                    # Move the variant info to model_raw (prepend it)
                    new_model = f"{part_name} {model}".strip() if model else part_name
                    print(f"[DITTO_FIX] Line {serial}: '{part_name}' is a variant identifier, "
                          f"copying '{ditto_chain_part_name}', model = '{new_model}'")
                    line['part_name_raw'] = ditto_chain_part_name
                    line['model_raw'] = new_model
                    continue
            
            # Check 4: part_name looks like a vehicle model, not a product type
            if part_name and ditto_chain_active and ditto_chain_part_name:
                if self._looks_like_model_not_product(part_name):
                    new_model = f"{part_name} {model}".strip() if model else part_name
                    print(f"[DITTO_FIX] Line {serial}: '{part_name}' looks like model/variant, "
                          f"copying '{ditto_chain_part_name}', model = '{new_model}'")
                    line['part_name_raw'] = ditto_chain_part_name
                    line['model_raw'] = new_model
                    continue
            
            # Check 5: part_name equals model (LLM confused them)
            if part_name and model and part_name.lower() == model.lower() and ditto_chain_part_name:
                print(f"[DITTO_FIX] Line {serial}: '{part_name}' = model, copying '{ditto_chain_part_name}'")
                line['part_name_raw'] = ditto_chain_part_name
                continue
            
            # If we get here, this is an unrecognized part name
            # If ditto chain is active but we can't classify this, still try to use ditto
            if part_name and ditto_chain_active and ditto_chain_part_name:
                if not self._is_known_product_type(part_name):
                    # Fallback: treat as ditto if it doesn't look like a product type
                    new_model = f"{part_name} {model}".strip() if model else part_name
                    print(f"[DITTO_FIX] Line {serial}: '{part_name}' unknown, ditto chain active, "
                          f"copying '{ditto_chain_part_name}', model = '{new_model}'")
                    line['part_name_raw'] = ditto_chain_part_name
                    line['model_raw'] = new_model
                    continue
            
            # No ditto chain active - this might be the first line or a standalone
            if part_name:
                ditto_chain_part_name = part_name
                ditto_chain_active = self._is_known_product_type(part_name)
                if ditto_chain_active:
                    print(f"[DITTO] Line {serial}: Starting ditto chain with '{part_name}'")
        
        return lines
    
    def _is_known_product_type(self, name: str) -> bool:
        """Check if a name is a DEFINITE product type (not a variant/model)"""
        if not name:
            return False
        name_lower = name.lower().strip()
        
        # Direct match against definite product types ONLY
        if name_lower in self.KNOWN_PRODUCT_TYPES:
            return True
        
        # Partial match (e.g., "Body Kit XYZ" starts with "Body Kit")
        for product_type in self.KNOWN_PRODUCT_TYPES:
            if len(product_type) >= 4 and name_lower.startswith(product_type):
                return True
        
        return False
    
    def _is_variant_identifier(self, name: str) -> bool:
        """Check if a name is a variant/style identifier (not a product type)"""
        if not name:
            return False
        name_lower = name.lower().strip()
        
        # Direct match
        if name_lower in self.VARIANT_IDENTIFIERS:
            return True
        
        # Check if it starts with a variant identifier (e.g., "Type 7 Shine")
        for variant in self.VARIANT_IDENTIFIERS:
            if len(variant) >= 3 and name_lower.startswith(variant):
                return True
        
        return False
    
    def _looks_like_model_not_product(self, name: str) -> bool:
        """
        Heuristic: does this name look more like a vehicle model/variant 
        than a product type?
        
        Vehicle models: Activa 3G, iSmart 110, HF Deluxe, etc.
        Product types: Visor, Body Kit, Side Cowl, etc.
        """
        name_lower = name.lower().strip()
        
        # Known vehicle model keywords
        model_keywords = [
            'activa', 'ismart', 'i smart', 'jupiter', 'hf', 'dream', 'splendor',
            'shine', 'cb', 'xpro', 'x pro', 'dio', 'pleasure', 'platina',
            'pulsar', 'glamour', 'passion', 'maestro', 'neo', 'deluxe',
            'suspension', 'susp', 'old', 'new', 'redwan', 'stound',
            'bs4', 'bs6', 'bs7', 'bsg', 'i3s', '3g', '5g', 'xtec',
            'access', 'duet', 'pass+', 'pass pro', 'passport',
            'type 2', 'type 3', 'type 5', 'type 7', 'type 8',
            '100', '110', '125', '160', '150', '180', '200', '220',
        ]
        
        if any(kw in name_lower for kw in model_keywords):
            return True
        
        return False
    
    def _sanitize_metadata(self, metadata: Dict) -> Dict:
        """
        Sanitize metadata to ensure all text is in Roman/ASCII characters.
        Replaces any remaining non-ASCII characters with a placeholder.
        """
        if not metadata:
            return metadata
        
        import re
        
        for key in ['customer_name', 'location']:
            value = metadata.get(key)
            if value and isinstance(value, str):
                # Check if string contains non-ASCII characters (Hindi, etc.)
                if any(ord(c) > 127 for c in value):
                    print(f"[SANITIZE] Warning: '{key}' contains non-ASCII characters: {value}")
                    # Try to keep only ASCII portions
                    ascii_parts = re.findall(r'[a-zA-Z0-9\s\-\.\,\/\(\)]+', value)
                    if ascii_parts:
                        metadata[key] = ' '.join(ascii_parts).strip()
                    else:
                        metadata[key] = None  # Can't salvage, set to null
        
        return metadata
    
    def extract_all_pages(self, pages: List[Dict]) -> List[Dict]:
        """
        Extract line items from all order pages
        
        Args:
            pages: List of page dictionaries with 'image_path' and 'page_number'
            
        Returns:
            List of extraction results (one per page)
        """
        results = []
        
        for page in pages:
            result = self.extract_order_lines(
                page['image_path'],
                page['page_number']
            )
            results.append(result)
        
        return results
