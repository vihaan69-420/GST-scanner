"""
GST Invoice Parser
Extracts structured GST-compliant data from OCR text
"""
import json
import re
from typing import Dict
import google.generativeai as genai
import config
from parsing.line_item_extractor import LineItemExtractor
from parsing.gst_validator import GSTValidator


class GSTParser:
    """Parse OCR text and extract GST-compliant invoice data"""
    
    def __init__(self, metrics_tracker=None, logger=None):
        """Initialize the GST parser with Gemini API"""
        genai.configure(api_key=config.GOOGLE_API_KEY)
        
        # Use Gemini 2.5 Flash for intelligent parsing
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Initialize line item extractor and validator for Tier 1
        self.line_item_extractor = LineItemExtractor()
        self.gst_validator = GSTValidator()
        
        # Monitoring
        self.metrics_tracker = metrics_tracker
        self.logger = logger
        
        # GST extraction prompt
        self.extraction_prompt = """
You are a GST invoice data extraction expert.

Extract ONLY the following fields from the invoice text below. Return VALID JSON ONLY.

FIELD DEFINITIONS:

1. Invoice_No: Invoice number / Bill number (may contain letters and numbers, e.g., B6580, INV-2025-001)
2. Invoice_Date: Invoice date in DD/MM/YYYY format
3. Invoice_Type: Usually "TAX INVOICE" or "SALE BILL"
4. Seller_Name: Name of the company/person selling (usually at top of invoice)
5. Seller_GSTIN: GSTIN of seller
6. Seller_State_Code: First 2 digits of seller GSTIN
7. Buyer_Name: Name from "Billed To" or "Buyer" section
8. Buyer_GSTIN: GSTIN from "Billed To" or "Buyer" section
9. Buyer_State_Code: First 2 digits of buyer GSTIN
10. Ship_To_Name: Name from "Ship To" or "Consignee" section (if different from buyer)
11. Ship_To_State_Code: State code of shipping location
12. Place_Of_Supply: State name or code where supply is made
13. Supply_Type: Usually "INTRA-STATE" or "INTER-STATE"
14. Reverse_Charge: "Y" or "N"
15. Invoice_Value: Total invoice value (final amount)
16. Total_Taxable_Value: Total taxable amount before tax
17. Total_GST: Total GST amount (CGST + SGST + IGST)
18. IGST_Total: Total IGST amount (if inter-state)
19. CGST_Total: Total CGST amount (if intra-state)
20. SGST_Total: Total SGST amount (if intra-state)
21. Eway_Bill_No: E-way bill number (if present)
22. Transporter: Transporter name (if present)
23. Validation_Status: Set to "PENDING"
24. Validation_Remarks: Leave empty

EXTRACTION RULES:
- Extract from invoice-level totals / HSN wise summary / tax summary
- DO NOT use line item values unless no summary exists
- If IGST exists, CGST and SGST must be 0 or empty
- If CGST and SGST exist, IGST must be 0 or empty
- State codes are first 2 digits of GSTIN (e.g., 27 for Maharashtra)
- If a field is not found, use empty string ""
- Numbers should be extracted as-is (with decimals if present)
- Dates must be in DD/MM/YYYY format
- **Invoice numbers can contain letters (A-Z) and numbers (0-9)** - preserve EXACTLY as shown (e.g., B6580 not 86580)
- For ambiguous characters: B vs 8, O vs 0, I vs 1 - check context and prefer letters in invoice numbers

OUTPUT FORMAT:
Return ONLY valid JSON with the exact field names above. No explanations, no markdown, no additional text.

Example output structure:
{
  "Invoice_No": "2025/JW/303",
  "Invoice_Date": "28/11/2025",
  "Invoice_Type": "SALE BILL",
  "Seller_Name": "KESARI AUTOMOTIVES",
  "Seller_GSTIN": "27ADPK6637J1IZN",
  "Seller_State_Code": "27",
  "Buyer_Name": "SAKET MOTORCYCLES",
  "Buyer_GSTIN": "27ADQPP9412L1ZP",
  "Buyer_State_Code": "27",
  "Ship_To_Name": "SAKET MOTORCYCLES",
  "Ship_To_State_Code": "27",
  "Place_Of_Supply": "27-MAHARASHTRA",
  "Supply_Type": "INTRA-STATE",
  "Reverse_Charge": "N",
  "Invoice_Value": "148.00",
  "Total_Taxable_Value": "125.32",
  "Total_GST": "22.56",
  "IGST_Total": "",
  "CGST_Total": "11.28",
  "SGST_Total": "11.28",
  "Eway_Bill_No": "",
  "Transporter": "",
  "Validation_Status": "PENDING",
  "Validation_Remarks": ""
}

Now extract from this invoice text:

"""
    
    def parse_invoice(self, ocr_text: str) -> Dict:
        """
        Parse OCR text and extract GST-compliant invoice data
        
        Args:
            ocr_text: Combined OCR text from all invoice pages
            
        Returns:
            Dictionary with structured GST data
        """
        try:
            # Construct full prompt
            full_prompt = self.extraction_prompt + "\n\n" + ocr_text
            
            # Generate structured data using Gemini (old stable SDK)
            response = self.model.generate_content(full_prompt)
            
            # Record metrics
            if self.metrics_tracker:
                text_length = len(ocr_text)
                self.metrics_tracker.record_parsing_call(text_length)
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Clean up response (remove markdown code blocks if present)
            response_text = re.sub(r'^```json\s*', '', response_text)
            response_text = re.sub(r'^```\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
            response_text = response_text.strip()
            
            # Parse JSON
            invoice_data = json.loads(response_text)
            
            # Validate and clean data
            invoice_data = self._validate_and_clean(invoice_data)
            
            return invoice_data
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON from response: {str(e)}\nResponse: {response_text}")
        except Exception as e:
            error_msg = f"GST parsing failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def _validate_and_clean(self, data: Dict) -> Dict:
        """
        Validate and clean extracted data
        
        Args:
            data: Raw extracted data
            
        Returns:
            Cleaned and validated data
        """
        # Ensure all required fields exist
        required_fields = [
            'Invoice_No', 'Invoice_Date', 'Invoice_Type',
            'Seller_Name', 'Seller_GSTIN', 'Seller_State_Code',
            'Buyer_Name', 'Buyer_GSTIN', 'Buyer_State_Code',
            'Ship_To_Name', 'Ship_To_State_Code',
            'Place_Of_Supply', 'Supply_Type', 'Reverse_Charge',
            'Invoice_Value', 'Total_Taxable_Value', 'Total_GST',
            'IGST_Total', 'CGST_Total', 'SGST_Total',
            'Eway_Bill_No', 'Transporter',
            'Validation_Status', 'Validation_Remarks'
        ]
        
        for field in required_fields:
            if field not in data:
                data[field] = ""
        
        # Convert None to empty string
        for key, value in data.items():
            if value is None or value == "null":
                data[key] = ""
            else:
                data[key] = str(value).strip()
        
        # Date validation: Flag suspicious years for manual review
        from datetime import datetime
        invoice_date = data.get('Invoice_Date', '')
        if invoice_date:
            try:
                parsed_date = datetime.strptime(invoice_date, '%d/%m/%Y')
                current_year = datetime.now().year
                date_year = parsed_date.year
                
                # Flag if date is more than 2 years in the past (likely OCR error)
                if date_year < current_year - 2:
                    warning = f"DATE ERROR: Year {date_year} seems incorrect (OCR may have misread). Please verify manually."
                    existing_remarks = data.get('Validation_Remarks', '')
                    if existing_remarks:
                        data['Validation_Remarks'] = existing_remarks + "; " + warning
                    else:
                        data['Validation_Remarks'] = warning
                    # Set validation status to ERROR so user knows to check
                    data['Validation_Status'] = 'ERROR'
                    print(f"[ERROR] Suspicious date: {invoice_date} - flagged for manual verification")
            except ValueError:
                pass  # Invalid date format, will be caught elsewhere
        
        # GST validation: IGST vs CGST+SGST
        has_igst = data.get('IGST_Total') and float(data['IGST_Total'] or 0) > 0
        has_cgst_sgst = (data.get('CGST_Total') and float(data['CGST_Total'] or 0) > 0) or \
                        (data.get('SGST_Total') and float(data['SGST_Total'] or 0) > 0)
        
        if has_igst and has_cgst_sgst:
            # Both present - this is an error, but let validation catch it
            existing_remarks = data.get('Validation_Remarks', '')
            new_warning = "Warning: Both IGST and CGST/SGST present"
            if existing_remarks:
                data['Validation_Remarks'] = existing_remarks + "; " + new_warning
            else:
                data['Validation_Remarks'] = new_warning
        
        return data
    
    def format_for_sheets(self, data: Dict) -> list:
        """
        Format invoice data as a list matching Google Sheets column order (Tier 1 fields only)
        
        Args:
            data: Structured invoice data
            
        Returns:
            List of values in correct column order (first 24 Tier 1 columns only)
            Tier 2 audit/correction/confidence fields are added separately by sheets_manager
        """
        # Only return Tier 1 fields (first 24 columns)
        # Tier 2 fields (audit, correction, dedup, confidence) are added by sheets_manager
        tier1_columns = config.SHEET_COLUMNS[:24]
        return [data.get(col, "") for col in tier1_columns]
    
    def parse_invoice_with_validation(self, ocr_text: str) -> Dict:
        """
        Complete Tier 1 parsing with line items and validation
        
        This is the main Tier 1 entry point that orchestrates:
        1. Invoice-level extraction
        2. Line-item extraction
        3. GST validation
        
        Args:
            ocr_text: Combined OCR text from all invoice pages
            
        Returns:
            {
                'invoice_data': {...},  # 24 invoice header fields
                'line_items': [{...}, {...}],  # array of line items (15 fields each)
                'validation_result': {...}  # validation status with errors/warnings
            }
        """
        try:
            # Step 1: Extract invoice-level data (existing logic)
            invoice_data = self.parse_invoice(ocr_text)
            
            # Step 2: Extract line items
            invoice_no = invoice_data.get('Invoice_No', '')
            line_items = self.line_item_extractor.extract_items(ocr_text, invoice_no)
            
            # Step 3: Validate invoice with line items
            validation_result = self.gst_validator.validate_invoice(invoice_data, line_items)
            
            # Step 4: Update invoice validation fields based on result
            invoice_data['Validation_Status'] = validation_result['status']
            invoice_data['Validation_Remarks'] = self.gst_validator.format_validation_remarks(validation_result)
            
            return {
                'invoice_data': invoice_data,
                'line_items': line_items,
                'validation_result': validation_result
            }
            
        except Exception as e:
            raise Exception(f"Tier 1 parsing failed: {str(e)}")


if __name__ == "__main__":
    # Test the GST parser
    parser = GSTParser()
    
    # Test with sample OCR text
    sample_text = """
SALE BILL
KESARI AUTOMOTIVES
AUTHORISED DISTRIBUTOR FOR HONDA 2 WHEELER SPARES
SAKET MOTORCYCLES

GSTIN : 27ADPK6637J1IZN UDYAM-MH-13-0030824
Invoice Number : 2025/JW/303
Invoice Date : 28/11/2025

Details of Receiver(Billed to)
SAKET MOTORCYCLES[18KDC00017]
GANESH JINNING
OLD MONDHA
NEAR SANTOSHI MATA MANDIR
JALNA-431203,JALNA(MAHARASHTRA 27)
Mobile Number: 8888802888
GSTIN/PAN : 27ADQPP9412L1ZP

HSN Wise Statistics :
Sr No | HSN/SAC Code | Qty | Taxable Value | SGST/UTGST Tax% | Amount | CGST Tax% | Amount | IGST Tax% | Amount | Total
1 | 87141090 | 1.000 | 125.32 | 9.00 | 11.28 | 9.00 | 11.28 | | | 147.88
Total : 1.000 | 125.32 | | 11.28 | | 11.28 | | | 147.88

Invoice (In Words): Rupees One Hundred Forty Eight Only
Invoice Total : 148.00
"""
    
    print("Testing GST Parser...")
    result = parser.parse_invoice(sample_text)
    print("\n" + "="*80)
    print("EXTRACTED DATA:")
    print("="*80)
    print(json.dumps(result, indent=2))
