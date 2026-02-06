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
Extract line items from this handwritten order note. This is a handwritten bill format.

CRITICAL RULES FOR HANDWRITTEN BILLS:
1. **Ditto marks ("--", "~~", "-~-", "~", "- -")**: These mean "same as above" - copy the previous word/brand name
   Example: If line 1 has "Sai - Body Kit" and line 2 has "-- Visor", then line 2 is "Sai - Visor"
   IMPORTANT: Look carefully at lines starting with dashes or wavy lines - they are continuation marks!
   
2. **Brand prefix**: Preserve brand names like "Sai -", "Honda -", etc. EXACTLY as written
   When you see ditto marks, ALWAYS copy the brand from the line directly above.

3. **Header information**: Extract customer name, mobile number, and date from the top of the page
   - Look for mobile numbers (10 digits starting with 7/8/9)
   - Look for dates in DD/MM/YY format
   - Look for location names (cities/places)

4. **Line format**: (Serial) Brand - Part_Name Model Color/Variant (Quantity)
   Example: (1) Sai - Body Kit Stound PA/Grey (2)
   Example with ditto: (2) -- Visor Activa 3G Blue (5) → means "Sai - Visor Activa 3G Blue (5)"
   
5. **Color codes**: Keep color abbreviations intact:
   - BL/Grey, PA/Grey, S/Red, etc. = Keep as-is
   - White, Blue, Red, etc. = Full color names

6. **Word Recognition**: Pay special attention to:
   - "Visor" (not "visar" or missing)
   - "Access" (not "Accesss")
   - Model numbers like "BS4", "i3S", "3G", "5G"

IMPORTANT: 
- Count ONLY actual numbered line items visible on the page
- Don't count header information as line items
- Look at the ENTIRE line, including parts after dashes/wavy lines

Output format:
{
  "order_metadata": {
    "customer_name": "extracted name or null",
    "mobile_number": "extracted mobile or null", 
    "order_date": "DD/MM/YY format or null",
    "location": "extracted location or null"
  },
  "line_items": [
    {
      "serial_no": 1,
      "brand": "Sai",
      "part_name_raw": "Body Kit",
      "model_raw": "Stound",
      "color_raw": "PA/Grey",
      "quantity": 2
    },
    {
      "serial_no": 2,
      "brand": "Sai",
      "part_name_raw": "Visor",
      "model_raw": "Activa 3G", 
      "color_raw": "Blue",
      "quantity": 5
    }
  ]
}

CRITICAL: 
- When you see ditto marks/dashes at the start of a line, copy the BRAND from the previous line
- Extract EXACT count of numbered items visible
- Preserve all abbreviations and color codes
- Look carefully for words after ditto marks (like "Visor")
- Return ONLY valid JSON, no markdown code blocks
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
