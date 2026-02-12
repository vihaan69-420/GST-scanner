"""
Line Item Extractor
Extracts individual line items from GST invoice OCR text using Google Gemini
"""
import json
import re
from typing import List, Dict
import google.generativeai as genai
import config


class LineItemExtractor:
    """Extract line items from GST invoice OCR text"""
    
    def __init__(self):
        """Initialize the line item extractor with Gemini API"""
        genai.configure(api_key=config.GOOGLE_API_KEY)
        
        # Use Gemini 2.5 Flash for line item extraction
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Line item extraction prompt
        self.extraction_prompt = """
You are extracting line items from a GST invoice.

Extract EVERY line item row from the invoice item table/product table.

For each line item, extract these 19 fields:
1. Invoice_No: Invoice number (extract from invoice header)
2. Line_No: Sequential line number (1, 2, 3, ...)
3. Item_Code: Product/item code (if shown)
4. Item_Description: Product/service description
5. HSN: HSN or SAC code
6. Qty: Quantity value
7. UOM: Unit of Measure (PCS, KG, NOS, etc.)
8. Rate: Unit rate/price
9. Discount_Percent: Discount percentage (if shown)
10. Taxable_Value: Taxable value before GST
11. GST_Rate: GST rate percentage (5, 12, 18, 28, etc.)
12. CGST_Rate: CGST rate percentage (usually half of GST_Rate for intra-state)
13. CGST_Amount: CGST amount
14. SGST_Rate: SGST rate percentage (usually half of GST_Rate for intra-state)
15. SGST_Amount: SGST amount
16. IGST_Rate: IGST rate percentage (equals GST_Rate for inter-state)
17. IGST_Amount: IGST amount
18. Cess_Amount: Cess amount (if applicable)
19. Line_Total: Total amount for this line

CRITICAL RULES:
- Extract EXACTLY as printed in the invoice
- Do NOT calculate any missing values
- Do NOT skip any rows
- Do NOT summarize multiple items
- Preserve exact order from invoice
- If a field is missing/not visible, use empty string ""
- Multi-page invoices: extract items from ALL pages as one continuous list
- Do NOT include header rows, footer rows, or subtotal rows - only actual line items
- Line_No should be sequential starting from 1

OUTPUT FORMAT:
Return ONLY a valid JSON array of line items. No explanations, no markdown.

Example output:
[
  {
    "Invoice_No": "2025/JW/303",
    "Line_No": "1",
    "Item_Code": "80151-KWP-900ZA",
    "Item_Description": "COVERCENTER NHI",
    "HSN": "87141090",
    "Qty": "1.000",
    "UOM": "NOS",
    "Rate": "186.00",
    "Discount_Percent": "20.50",
    "Taxable_Value": "125.32",
    "GST_Rate": "18",
    "CGST_Rate": "9",
    "CGST_Amount": "11.28",
    "SGST_Rate": "9",
    "SGST_Amount": "11.28",
    "IGST_Rate": "",
    "IGST_Amount": "",
    "Cess_Amount": "",
    "Line_Total": "147.88"
  }
]

Now extract line items from this invoice:

"""
    
    def extract_items(self, ocr_text: str, invoice_no: str = "") -> List[Dict]:
        """
        Extract line items from OCR text
        
        Args:
            ocr_text: Combined OCR text from all invoice pages
            invoice_no: Invoice number to link items (optional, will extract if not provided)
            
        Returns:
            List of dictionaries, one per line item
        """
        try:
            # Construct full prompt
            full_prompt = self.extraction_prompt + "\n\n" + ocr_text
            
            # Generate structured data using Gemini
            response = self.model.generate_content(full_prompt)
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Clean up response (remove markdown code blocks if present)
            response_text = re.sub(r'^```json\s*', '', response_text)
            response_text = re.sub(r'^```\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
            response_text = response_text.strip()
            
            # Parse JSON array
            line_items = json.loads(response_text)
            
            # Validate it's a list
            if not isinstance(line_items, list):
                raise ValueError("Expected JSON array of line items")
            
            # Clean and validate each item
            cleaned_items = []
            for idx, item in enumerate(line_items, 1):
                cleaned_item = self._validate_and_clean_item(item, idx, invoice_no)
                cleaned_items.append(cleaned_item)
            
            return cleaned_items
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON from line items response: {str(e)}\nResponse: {response_text}")
        except Exception as e:
            raise Exception(f"Line item extraction failed: {str(e)}")
    
    def _validate_and_clean_item(self, item: Dict, line_no: int, invoice_no: str) -> Dict:
        """
        Validate and clean a single line item
        
        Args:
            item: Raw line item dictionary
            line_no: Sequential line number
            invoice_no: Invoice number for foreign key
            
        Returns:
            Cleaned line item dictionary
        """
        # Define required fields (matching Google Sheet structure)
        required_fields = [
            'Invoice_No',
            'Line_No',
            'Item_Code',
            'Item_Description',
            'HSN',
            'Qty',
            'UOM',
            'Rate',
            'Discount_Percent',
            'Taxable_Value',
            'GST_Rate',
            'CGST_Rate',
            'CGST_Amount',
            'SGST_Rate',
            'SGST_Amount',
            'IGST_Rate',
            'IGST_Amount',
            'Cess_Amount',
            'Line_Total'
        ]
        
        # Ensure all fields exist
        for field in required_fields:
            if field not in item:
                item[field] = ""
        
        # Override Invoice_No if provided
        if invoice_no:
            item['Invoice_No'] = invoice_no
        
        # Ensure Line_No is sequential
        if not item.get('Line_No') or item['Line_No'] == "":
            item['Line_No'] = str(line_no)
        
        # Convert None to empty string and strip whitespace
        for key, value in item.items():
            if value is None or value == "null":
                item[key] = ""
            else:
                item[key] = str(value).strip()
        
        return item
    
    def format_items_for_sheets(self, line_items: List[Dict]) -> List[List]:
        """
        Format line items as lists matching Google Sheets column order
        
        Args:
            line_items: List of line item dictionaries
            
        Returns:
            List of lists, each inner list is a row for sheets
        """
        rows = []
        for item in line_items:
            row = [item.get(col, "") for col in config.LINE_ITEM_COLUMNS]
            rows.append(row)
        return rows


if __name__ == "__main__":
    # Test the line item extractor
    extractor = LineItemExtractor()
    
    # Test with sample OCR text
    sample_text = """
SALE BILL
KESARI AUTOMOTIVES
GSTIN : 27ADPK6637J1IZN
Invoice Number : 2025/JW/303
Invoice Date : 28/11/2025

Line Items:
Sr No | Description of Goods | HSN/SAC Code | Qty. | MRP | Disc Perc | Disc Count | Taxable Value | GST Rate | GST Amount | Amount
1 | COVERCENTER"NHI"(80151-KWP-900ZA) | 87141090 | 1.000 | 186.00 | 20.50 | 32.31 | 125.32 | 18.00 | 22.56 | 147.88

HSN Wise Statistics :
Sr No | HSN/SAC Code | Qty | Taxable Value | SGST/UTGST Tax% | Amount | CGST Tax% | Amount | IGST Tax% | Amount | Total
1 | 87141090 | 1.000 | 125.32 | 9.00 | 11.28 | 9.00 | 11.28 | | | 147.88
"""
    
    print("Testing Line Item Extractor...")
    try:
        items = extractor.extract_items(sample_text, "2025/JW/303")
        print(f"\n[OK] Extracted {len(items)} line item(s)")
        print("\n" + "="*80)
        print("EXTRACTED LINE ITEMS:")
        print("="*80)
        print(json.dumps(items, indent=2))
    except Exception as e:
        print(f"[FAIL] {e}")
