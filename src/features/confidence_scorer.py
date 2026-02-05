"""
Confidence Scorer for GST Invoice Fields
Analyzes extracted invoice data to assign confidence scores to critical fields
"""
import re
from typing import Dict, List
from datetime import datetime


class ConfidenceScorer:
    """Calculate confidence scores for extracted invoice fields"""
    
    def __init__(self, confidence_threshold: float = 0.7):
        """
        Initialize the confidence scorer
        
        Args:
            confidence_threshold: Minimum confidence to consider field reliable (default: 0.7)
        """
        self.confidence_threshold = confidence_threshold
        
        # Define critical fields that need confidence scoring
        self.critical_fields = [
            'Invoice_No',
            'Invoice_Date',
            'Buyer_Name',
            'Buyer_GSTIN',
            'Seller_Name',
            'Seller_GSTIN',
            'Total_Taxable_Value',
            'Total_GST',
            'CGST_Total',
            'SGST_Total',
            'IGST_Total'
        ]
    
    def score_fields(
        self,
        invoice_data: Dict,
        line_items: List[Dict],
        validation_result: Dict,
        ocr_text: str
    ) -> Dict[str, float]:
        """
        Calculate confidence scores for all critical fields
        
        Args:
            invoice_data: Extracted invoice header data
            line_items: List of extracted line items
            validation_result: Result from GSTValidator
            ocr_text: Original OCR text
            
        Returns:
            Dictionary mapping field names to confidence scores (0.0 to 1.0)
        """
        confidence_scores = {}
        
        # Score each critical field
        for field_name in self.critical_fields:
            field_value = invoice_data.get(field_name, '')
            confidence = self._calculate_field_confidence(
                field_name,
                field_value,
                invoice_data,
                validation_result,
                ocr_text
            )
            confidence_scores[field_name] = confidence
        
        return confidence_scores
    
    def _calculate_field_confidence(
        self,
        field_name: str,
        field_value: str,
        invoice_data: Dict,
        validation_result: Dict,
        ocr_text: str
    ) -> float:
        """
        Calculate confidence score for a single field
        
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence: 0.8 for populated fields, 0.0 for empty
        if not field_value or field_value.strip() == '':
            return 0.0
        
        confidence = 0.8
        
        # Check if field causes validation errors (penalty: -0.3)
        if self._field_has_validation_error(field_name, validation_result):
            confidence -= 0.3
        
        # Check if field causes validation warnings (penalty: -0.2)
        elif self._field_has_validation_warning(field_name, validation_result):
            confidence -= 0.2
        
        # Format validation boost/penalty
        format_valid = self._validate_field_format(field_name, field_value)
        if format_valid:
            confidence += 0.1
        else:
            confidence -= 0.1
        
        # Cross-field consistency check
        if self._check_cross_field_consistency(field_name, field_value, invoice_data):
            confidence += 0.05
        
        # Ensure confidence is within bounds [0.0, 1.0]
        return max(0.0, min(1.0, confidence))
    
    def _field_has_validation_error(self, field_name: str, validation_result: Dict) -> bool:
        """Check if field is mentioned in validation errors"""
        errors = validation_result.get('errors', [])
        
        # Map field names to keywords that might appear in error messages
        field_keywords = {
            'Invoice_No': ['invoice'],
            'Total_Taxable_Value': ['taxable value', 'taxable'],
            'Total_GST': ['gst total', 'gst'],
            'CGST_Total': ['cgst'],
            'SGST_Total': ['sgst'],
            'IGST_Total': ['igst'],
            'Buyer_GSTIN': ['buyer', 'gstin'],
            'Seller_GSTIN': ['seller', 'gstin']
        }
        
        keywords = field_keywords.get(field_name, [field_name.lower()])
        
        for error in errors:
            error_lower = error.lower()
            if any(keyword in error_lower for keyword in keywords):
                return True
        
        return False
    
    def _field_has_validation_warning(self, field_name: str, validation_result: Dict) -> bool:
        """Check if field is mentioned in validation warnings"""
        warnings = validation_result.get('warnings', [])
        
        # Map field names to keywords
        field_keywords = {
            'Invoice_No': ['invoice'],
            'Total_Taxable_Value': ['taxable value', 'taxable'],
            'Total_GST': ['gst total', 'gst'],
            'CGST_Total': ['cgst'],
            'SGST_Total': ['sgst'],
            'IGST_Total': ['igst'],
            'Buyer_GSTIN': ['buyer', 'gstin'],
            'Seller_GSTIN': ['seller', 'gstin']
        }
        
        keywords = field_keywords.get(field_name, [field_name.lower()])
        
        for warning in warnings:
            warning_lower = warning.lower()
            if any(keyword in warning_lower for keyword in keywords):
                return True
        
        return False
    
    def _validate_field_format(self, field_name: str, field_value: str) -> bool:
        """
        Validate field format based on expected patterns
        
        Returns:
            True if format is valid, False otherwise
        """
        if not field_value or field_value.strip() == '':
            return False
        
        # GSTIN format: 15 characters, specific pattern
        if 'GSTIN' in field_name:
            return self._validate_gstin_format(field_value)
        
        # Date format: DD/MM/YYYY
        elif 'Date' in field_name:
            return self._validate_date_format(field_value)
        
        # Numeric fields
        elif any(x in field_name for x in ['Total', 'Value', 'Amount']):
            return self._validate_numeric_format(field_value)
        
        # Invoice number should not be empty and reasonable length
        elif field_name == 'Invoice_No':
            return len(field_value.strip()) >= 3 and len(field_value.strip()) <= 50
        
        # Name fields should have reasonable length
        elif 'Name' in field_name:
            return len(field_value.strip()) >= 2 and len(field_value.strip()) <= 200
        
        return True  # Default to valid for other fields
    
    def _validate_gstin_format(self, gstin: str) -> bool:
        """
        Validate GSTIN format: 15 alphanumeric characters
        Pattern: 2 digits (state) + 10 chars (PAN) + 1 char + 1 digit + 1 char
        """
        if not gstin or len(gstin) != 15:
            return False
        
        # Basic pattern check
        pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}[Z]{1}[0-9A-Z]{1}$'
        return bool(re.match(pattern, gstin.upper()))
    
    def _validate_date_format(self, date_str: str) -> bool:
        """Validate date format DD/MM/YYYY"""
        try:
            datetime.strptime(date_str, '%d/%m/%Y')
            return True
        except ValueError:
            return False
    
    def _validate_numeric_format(self, value: str) -> bool:
        """Validate numeric format (allows commas and currency symbols)"""
        try:
            # Remove currency symbols and commas
            cleaned = value.replace('₹', '').replace(',', '').strip()
            float(cleaned)
            return True
        except ValueError:
            return False
    
    def _check_cross_field_consistency(
        self,
        field_name: str,
        field_value: str,
        invoice_data: Dict
    ) -> bool:
        """
        Check if field is consistent with related fields
        
        Returns:
            True if consistent, False otherwise
        """
        # Check if state code in GSTIN matches State_Code field
        if field_name == 'Buyer_GSTIN':
            buyer_state_code = invoice_data.get('Buyer_State_Code', '')
            if buyer_state_code and len(field_value) >= 2:
                gstin_state_code = field_value[:2]
                return gstin_state_code == buyer_state_code
        
        elif field_name == 'Seller_GSTIN':
            seller_state_code = invoice_data.get('Seller_State_Code', '')
            if seller_state_code and len(field_value) >= 2:
                gstin_state_code = field_value[:2]
                return gstin_state_code == seller_state_code
        
        # Check if Buyer_State_Code matches GSTIN
        elif field_name == 'Buyer_State_Code':
            buyer_gstin = invoice_data.get('Buyer_GSTIN', '')
            if buyer_gstin and len(buyer_gstin) >= 2:
                return field_value == buyer_gstin[:2]
        
        # Check if Seller_State_Code matches GSTIN
        elif field_name == 'Seller_State_Code':
            seller_gstin = invoice_data.get('Seller_GSTIN', '')
            if seller_gstin and len(seller_gstin) >= 2:
                return field_value == seller_gstin[:2]
        
        return True  # Default to consistent for other fields
    
    def identify_low_confidence_fields(
        self,
        confidence_scores: Dict[str, float]
    ) -> List[tuple]:
        """
        Identify fields with confidence below threshold
        
        Args:
            confidence_scores: Dictionary of field confidence scores
            
        Returns:
            List of tuples: (field_name, confidence_score)
        """
        low_confidence = []
        
        for field_name, confidence in confidence_scores.items():
            if confidence < self.confidence_threshold:
                low_confidence.append((field_name, confidence))
        
        # Sort by confidence (lowest first)
        low_confidence.sort(key=lambda x: x[1])
        
        return low_confidence
    
    def format_confidence_summary(self, confidence_scores: Dict[str, float]) -> str:
        """
        Format confidence scores as a summary string for Google Sheets
        
        Args:
            confidence_scores: Dictionary of field confidence scores
            
        Returns:
            Summary string (can be stored in a single cell or as JSON)
        """
        import json
        
        # Round scores to 2 decimal places
        rounded_scores = {
            field: round(score, 2)
            for field, score in confidence_scores.items()
        }
        
        return json.dumps(rounded_scores)


if __name__ == "__main__":
    # Test the confidence scorer
    scorer = ConfidenceScorer()
    
    # Test data
    invoice_data = {
        'Invoice_No': 'INV-2024-001',
        'Invoice_Date': '15/01/2024',
        'Buyer_Name': 'ABC Corporation',
        'Buyer_GSTIN': '29ABCDE1234F1Z5',
        'Buyer_State_Code': '29',
        'Seller_Name': 'XYZ Ltd',
        'Seller_GSTIN': '24PQRST5678G1Z3',
        'Seller_State_Code': '24',
        'Total_Taxable_Value': '50000.00',
        'Total_GST': '9000.00',
        'CGST_Total': '4500.00',
        'SGST_Total': '4500.00',
        'IGST_Total': ''
    }
    
    line_items = []
    
    validation_result = {
        'status': 'OK',
        'errors': [],
        'warnings': []
    }
    
    ocr_text = "Sample OCR text"
    
    print("Testing Confidence Scorer...")
    print("=" * 80)
    
    scores = scorer.score_fields(invoice_data, line_items, validation_result, ocr_text)
    
    print("\nConfidence Scores:")
    for field, score in scores.items():
        print(f"  {field}: {score:.2f}")
    
    print("\nLow Confidence Fields:")
    low_conf = scorer.identify_low_confidence_fields(scores)
    if low_conf:
        for field, score in low_conf:
            print(f"  {field}: {score:.2f}")
    else:
        print("  None - all fields have acceptable confidence")
    
    print("\nConfidence Summary JSON:")
    print(scorer.format_confidence_summary(scores))
