"""
Correction Manager for Manual Invoice Corrections
Handles user corrections via Telegram interface
"""
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone
import json


class CorrectionManager:
    """Manage manual corrections for invoice data"""
    
    # Define correctable fields and their display names
    CORRECTABLE_FIELDS = {
        'invoice_no': 'Invoice_No',
        'invoice_date': 'Invoice_Date',
        'buyer_name': 'Buyer_Name',
        'buyer_gstin': 'Buyer_GSTIN',
        'seller_name': 'Seller_Name',
        'seller_gstin': 'Seller_GSTIN',
        'total_taxable_value': 'Total_Taxable_Value',
        'cgst_total': 'CGST_Total',
        'sgst_total': 'SGST_Total',
        'igst_total': 'IGST_Total',
        'total_gst': 'Total_GST'
    }
    
    def __init__(self):
        """Initialize the correction manager"""
        pass
    
    def needs_review(
        self,
        confidence_scores: Dict[str, float],
        validation_result: Dict,
        confidence_threshold: float = 0.7
    ) -> bool:
        """
        Determine if invoice needs manual review
        
        Args:
            confidence_scores: Dictionary of field confidence scores
            validation_result: Result from GSTValidator
            confidence_threshold: Minimum acceptable confidence
            
        Returns:
            True if review is needed, False otherwise
        """
        # Check for validation errors
        if validation_result.get('errors', []):
            return True
        
        # Check for low confidence fields
        for field, confidence in confidence_scores.items():
            if confidence < confidence_threshold:
                return True
        
        return False
    
    def generate_review_message(
        self,
        invoice_data: Dict,
        confidence_scores: Dict[str, float],
        validation_result: Dict,
        confidence_threshold: float = 0.7
    ) -> str:
        """
        Generate a review prompt message for Telegram
        
        Args:
            invoice_data: Extracted invoice data
            confidence_scores: Field confidence scores
            validation_result: Validation result
            confidence_threshold: Minimum acceptable confidence
            
        Returns:
            Formatted review message (without Markdown to avoid parsing errors)
        """
        # Build basic invoice details (no Markdown to avoid parsing issues)
        invoice_no = invoice_data.get('Invoice_No', 'N/A')
        invoice_date = invoice_data.get('Invoice_Date', 'N/A')
        seller_name = invoice_data.get('Seller_Name', 'N/A')
        buyer_name = invoice_data.get('Buyer_Name', 'N/A')
        buyer_gstin = invoice_data.get('Buyer_GSTIN', 'N/A')
        total_taxable = invoice_data.get('Total_Taxable_Value', 'N/A')
        total_gst = invoice_data.get('Total_GST', 'N/A')
        
        message = "📄 Here's what I extracted:\n\n"
        message += "─────────────────────\n"
        message += f"  Invoice No:   {invoice_no}\n"
        message += f"  Date:         {invoice_date}\n"
        message += f"  Seller:       {seller_name}\n"
        message += f"  Buyer:        {buyer_name}\n"
        message += f"  Buyer GSTIN:  {buyer_gstin}\n"
        message += f"  Taxable:      Rs.{total_taxable}\n"
        message += f"  Total GST:    Rs.{total_gst}\n"
        message += "─────────────────────\n\n"
        
        # Add validation summary
        validation_summary = self._format_validation_summary(validation_result)
        if validation_summary:
            message += validation_summary + "\n"
        
        # Add low confidence fields
        low_conf_fields = self._identify_review_fields(
            invoice_data,
            confidence_scores,
            validation_result,
            confidence_threshold
        )
        
        if low_conf_fields:
            message += f"🔍 {len(low_conf_fields)} field(s) may need a closer look:\n"
            for field_name, field_value, reason, confidence in low_conf_fields:
                if confidence is not None:
                    conf_pct = int(confidence * 100)
                    message += f"  • {field_name} ({conf_pct}% sure) = \"{field_value}\"\n"
                else:
                    message += f"  • {field_name} ({reason}) = \"{field_value}\"\n"
            message += "\n"
        
        # Note: action buttons are added by the bot via InlineKeyboardMarkup
        message += "Looks good? Save it, or make corrections below."
        
        return message
    
    def _format_validation_summary(self, validation_result: Dict) -> str:
        """Format validation errors/warnings into a summary (without Markdown)"""
        status = validation_result.get('status', 'UNKNOWN')
        errors = validation_result.get('errors', [])
        warnings = validation_result.get('warnings', [])
        
        summary = ""
        
        if status == 'OK':
            summary = "✅ All validation checks passed\n"
        elif status == 'WARNING':
            summary = "⚠️ A few things to double-check:\n"
            for warning in warnings[:3]:  # Show first 3 warnings
                summary += f"  • {warning}\n"
            if len(warnings) > 3:
                summary += f"  • ... and {len(warnings) - 3} more\n"
        elif status == 'ERROR':
            summary = "❌ Some issues found:\n"
            for error in errors[:3]:  # Show first 3 errors
                summary += f"  • {error}\n"
            if len(errors) > 3:
                summary += f"  • ... and {len(errors) - 3} more\n"
        
        return summary
    
    def _identify_review_fields(
        self,
        invoice_data: Dict,
        confidence_scores: Dict[str, float],
        validation_result: Dict,
        confidence_threshold: float
    ) -> List[Tuple[str, str, str, Optional[float]]]:
        """
        Identify fields that need review
        
        Returns:
            List of tuples: (field_display_name, value, reason, confidence_score)
        """
        review_fields = []
        
        # Check for low confidence fields
        for field_name, confidence in confidence_scores.items():
            if confidence < confidence_threshold:
                field_value = invoice_data.get(field_name, '')
                review_fields.append((
                    field_name,
                    field_value,
                    'low confidence',
                    confidence
                ))
        
        # Check for validation error fields (if not already in list)
        error_field_names = set(item[0] for item in review_fields)
        
        errors = validation_result.get('errors', [])
        for error in errors:
            # Try to extract field name from error message
            field_candidates = [
                'Invoice_No', 'Total_Taxable_Value', 'Total_GST',
                'CGST_Total', 'SGST_Total', 'IGST_Total',
                'Buyer_GSTIN', 'Seller_GSTIN'
            ]
            
            for field in field_candidates:
                if field.lower().replace('_', ' ') in error.lower():
                    if field not in error_field_names:
                        field_value = invoice_data.get(field, '')
                        review_fields.append((
                            field,
                            field_value,
                            'validation error',
                            None
                        ))
                        error_field_names.add(field)
                    break
        
        return review_fields
    
    def generate_correction_instructions(self) -> str:
        """Generate instructions for making corrections (without Markdown)"""
        message = "✏️ Correction Mode\n\n"
        message += "To fix a field, type:\n"
        message += "  field_name = new_value\n\n"
        message += "─────────────────────\n"
        message += "Available fields:\n"
        
        for short_name, full_name in self.CORRECTABLE_FIELDS.items():
            message += f"  • {short_name}\n"
        
        message += "─────────────────────\n"
        message += "\nExample:\n"
        message += "  buyer_gstin = 29AAAAA0000A1Z5\n\n"
        # Note: action buttons are added by the bot via InlineKeyboardMarkup
        message += "Tap a button below when you're done."
        
        return message
    
    def parse_correction_input(self, user_message: str) -> Optional[Tuple[str, str]]:
        """
        Parse user correction input
        
        Args:
            user_message: User's message text
            
        Returns:
            Tuple of (field_name, new_value) or None if invalid format
        """
        # Pattern: field_name = value
        pattern = r'^(\w+)\s*=\s*(.+)$'
        match = re.match(pattern, user_message.strip())
        
        if not match:
            return None
        
        field_name = match.group(1).lower().strip()
        new_value = match.group(2).strip()
        
        # Check if field is correctable
        if field_name not in self.CORRECTABLE_FIELDS:
            return None
        
        # Map to actual field name
        actual_field_name = self.CORRECTABLE_FIELDS[field_name]
        
        return (actual_field_name, new_value)
    
    def apply_corrections(
        self,
        invoice_data: Dict,
        corrections: Dict[str, str]
    ) -> Dict:
        """
        Apply corrections to invoice data
        
        Args:
            invoice_data: Original invoice data
            corrections: Dictionary of field corrections {field_name: new_value}
            
        Returns:
            New invoice data dictionary with corrections applied
        """
        # Create a copy to avoid modifying original
        corrected_data = invoice_data.copy()
        
        # Apply each correction
        for field_name, new_value in corrections.items():
            corrected_data[field_name] = new_value
        
        return corrected_data
    
    def format_correction_summary(
        self,
        original_data: Dict,
        corrections: Dict[str, str]
    ) -> str:
        """
        Format a summary of corrections made
        
        Args:
            original_data: Original invoice data
            corrections: Dictionary of corrections applied
            
        Returns:
            Formatted summary message
        """
        if not corrections:
            return "No corrections were made."
        
        message = f"✅ Saved with {len(corrections)} correction(s):\n\n"
        
        for field_name, new_value in corrections.items():
            old_value = original_data.get(field_name, '')
            message += f"  {field_name}\n"
            message += f"    was: {old_value}\n"
            message += f"    now: {new_value}\n\n"
        
        message += "Changes logged for audit."
        
        return message
    
    def create_correction_metadata(
        self,
        original_data: Dict,
        corrections: Dict[str, str],
        user_id: int
    ) -> Dict:
        """
        Create correction metadata for audit trail
        
        Args:
            original_data: Original invoice data
            corrections: Dictionary of corrections
            user_id: Telegram user ID who made corrections
            
        Returns:
            Correction metadata dictionary
        """
        metadata = {
            'original_values': {
                field: original_data.get(field, '')
                for field in corrections.keys()
            },
            'corrected_values': corrections.copy(),
            'correction_timestamp': datetime.now(timezone.utc).isoformat(),
            'corrected_by': user_id,
            'correction_reason': 'manual_review',
            'correction_count': len(corrections)
        }
        
        return metadata
    
    def format_correction_metadata_for_sheets(self, metadata: Dict) -> Tuple[str, str, str]:
        """
        Format correction metadata for Google Sheets storage
        
        Args:
            metadata: Correction metadata dictionary
            
        Returns:
            Tuple of (has_corrections, corrected_fields, correction_metadata_json)
        """
        has_corrections = 'Y' if metadata.get('correction_count', 0) > 0 else 'N'
        
        corrected_fields = ', '.join(metadata.get('corrected_values', {}).keys())
        
        correction_metadata_json = json.dumps(metadata)
        
        return (has_corrections, corrected_fields, correction_metadata_json)


if __name__ == "__main__":
    # Test the correction manager
    manager = CorrectionManager()
    
    # Test data
    invoice_data = {
        'Invoice_No': 'INV-2024-001',
        'Invoice_Date': '15/01/2024',
        'Buyer_Name': 'ABC Corp',
        'Buyer_GSTIN': '29ABCDE1234F1Z5',
        'Total_Taxable_Value': '50000.00',
        'Total_GST': '9000.00'
    }
    
    confidence_scores = {
        'Invoice_No': 0.95,
        'Invoice_Date': 0.90,
        'Buyer_Name': 0.85,
        'Buyer_GSTIN': 0.65,  # Low confidence
        'Total_Taxable_Value': 0.88,
        'Total_GST': 0.75
    }
    
    validation_result = {
        'status': 'WARNING',
        'errors': [],
        'warnings': ['Minor GST total difference: Rs.0.50 (likely rounding)']
    }
    
    print("Testing Correction Manager...")
    print("=" * 80)
    
    # Test needs_review
    needs_review = manager.needs_review(confidence_scores, validation_result)
    print(f"\nNeeds Review: {needs_review}")
    
    # Test generate_review_message
    if needs_review:
        print("\nReview Message:")
        print(manager.generate_review_message(invoice_data, confidence_scores, validation_result))
    
    # Test parse_correction_input
    print("\n\nTesting correction parsing:")
    test_inputs = [
        "buyer_gstin = 29AAAAA0000A1Z5",
        "invoice_date = 20/01/2024",
        "invalid format",
        "unknown_field = value"
    ]
    
    for test_input in test_inputs:
        result = manager.parse_correction_input(test_input)
        print(f"  Input: '{test_input}' → {result}")
    
    # Test apply_corrections
    print("\n\nTesting apply corrections:")
    corrections = {
        'Buyer_GSTIN': '29AAAAA0000A1Z5',
        'Invoice_Date': '20/01/2024'
    }
    
    corrected_data = manager.apply_corrections(invoice_data, corrections)
    print(f"  Original GSTIN: {invoice_data['Buyer_GSTIN']}")
    print(f"  Corrected GSTIN: {corrected_data['Buyer_GSTIN']}")
    
    # Test correction summary
    print("\n\nCorrection Summary:")
    print(manager.format_correction_summary(invoice_data, corrections))
