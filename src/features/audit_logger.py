"""
Audit Logger for Invoice Processing
Generates audit metadata for traceability and compliance
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone


class AuditLogger:
    """Generate audit metadata for invoice processing"""
    
    def __init__(self):
        """Initialize the audit logger"""
        pass
    
    def generate_audit_metadata(
        self,
        user_id: int,
        username: Optional[str],
        images: List[str],
        start_time: datetime,
        end_time: datetime,
        validation_result: Dict,
        corrections: Optional[Dict[str, str]] = None,
        extraction_version: str = "v1.0-tier2",
        model_version: str = "gemini-2.5-flash"
    ) -> Dict:
        """
        Generate complete audit metadata for an invoice
        
        Args:
            user_id: Telegram user ID
            username: Telegram username (optional)
            images: List of image file paths
            start_time: Processing start time
            end_time: Processing end time
            validation_result: Validation result dictionary
            corrections: Dictionary of manual corrections (optional)
            extraction_version: Version identifier for extraction logic
            model_version: AI model version used
            
        Returns:
            Complete audit metadata dictionary
        """
        # Calculate processing time
        processing_time = (end_time - start_time).total_seconds()
        
        # Count pages
        page_count = len(images)
        
        # Determine correction status
        has_corrections = 'Y' if corrections and len(corrections) > 0 else 'N'
        correction_count = len(corrections) if corrections else 0
        
        metadata = {
            'Upload_Timestamp': datetime.now(timezone.utc).isoformat(),
            'Telegram_User_ID': str(user_id),
            'Telegram_Username': username if username else '',
            'Extraction_Version': extraction_version,
            'Model_Version': model_version,
            'Validation_Status': validation_result.get('status', 'UNKNOWN'),
            'Processing_Time_Seconds': round(processing_time, 2),
            'Page_Count': page_count,
            'Has_Corrections': has_corrections,
            'Correction_Count': correction_count
        }
        
        return metadata
    
    def format_for_sheets(
        self,
        audit_metadata: Dict,
        confidence_scores: Optional[Dict[str, float]] = None,
        corrections_metadata: Optional[Dict] = None,
        fingerprint: str = '',
        duplicate_status: str = 'UNIQUE'
    ) -> Dict:
        """
        Format audit metadata for Google Sheets storage
        
        Args:
            audit_metadata: Basic audit metadata
            confidence_scores: Field confidence scores (optional)
            corrections_metadata: Detailed correction metadata (optional)
            fingerprint: Invoice fingerprint for deduplication
            duplicate_status: Duplicate status (UNIQUE or DUPLICATE_OVERRIDE)
            
        Returns:
            Dictionary with all audit fields formatted for sheets
        """
        sheets_data = audit_metadata.copy()
        
        # Add correction details if present
        if corrections_metadata:
            corrected_fields = ', '.join(corrections_metadata.get('corrected_values', {}).keys())
            sheets_data['Corrected_Fields'] = corrected_fields
            
            import json
            sheets_data['Correction_Metadata'] = json.dumps(corrections_metadata)
        else:
            sheets_data['Corrected_Fields'] = ''
            sheets_data['Correction_Metadata'] = ''
        
        # Add deduplication data
        sheets_data['Invoice_Fingerprint'] = fingerprint
        sheets_data['Duplicate_Status'] = duplicate_status
        
        # Add confidence scores if present
        if confidence_scores:
            sheets_data['Invoice_No_Confidence'] = confidence_scores.get('Invoice_No', 0.0)
            sheets_data['Invoice_Date_Confidence'] = confidence_scores.get('Invoice_Date', 0.0)
            sheets_data['Buyer_GSTIN_Confidence'] = confidence_scores.get('Buyer_GSTIN', 0.0)
            sheets_data['Total_Taxable_Value_Confidence'] = confidence_scores.get('Total_Taxable_Value', 0.0)
            sheets_data['Total_GST_Confidence'] = confidence_scores.get('Total_GST', 0.0)
        else:
            sheets_data['Invoice_No_Confidence'] = 0.0
            sheets_data['Invoice_Date_Confidence'] = 0.0
            sheets_data['Buyer_GSTIN_Confidence'] = 0.0
            sheets_data['Total_Taxable_Value_Confidence'] = 0.0
            sheets_data['Total_GST_Confidence'] = 0.0
        
        return sheets_data
    
    def format_audit_summary(self, audit_metadata: Dict) -> str:
        """
        Format audit metadata as a human-readable summary
        
        Args:
            audit_metadata: Audit metadata dictionary
            
        Returns:
            Formatted summary string
        """
        summary = "📋 **Audit Trail**\n\n"
        
        summary += f"• Uploaded: {self._format_timestamp(audit_metadata.get('Upload_Timestamp', ''))}\n"
        summary += f"• User: {audit_metadata.get('Telegram_User_ID', 'Unknown')}"
        
        username = audit_metadata.get('Telegram_Username', '')
        if username:
            summary += f" (@{username})"
        summary += "\n"
        
        summary += f"• Pages: {audit_metadata.get('Page_Count', 0)}\n"
        summary += f"• Processing Time: {audit_metadata.get('Processing_Time_Seconds', 0):.2f}s\n"
        summary += f"• Model: {audit_metadata.get('Model_Version', 'Unknown')}\n"
        summary += f"• Version: {audit_metadata.get('Extraction_Version', 'Unknown')}\n"
        summary += f"• Validation: {audit_metadata.get('Validation_Status', 'Unknown')}\n"
        
        has_corrections = audit_metadata.get('Has_Corrections', 'N')
        if has_corrections == 'Y':
            correction_count = audit_metadata.get('Correction_Count', 0)
            summary += f"• Corrections: {correction_count} field(s) corrected\n"
        
        return summary
    
    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format ISO timestamp to readable format"""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%d/%m/%Y %H:%M UTC')
        except Exception:
            return timestamp_str
    
    def create_audit_log_entry(
        self,
        invoice_no: str,
        action: str,
        user_id: int,
        details: str = ''
    ) -> Dict:
        """
        Create a standalone audit log entry (for future audit log table)
        
        Args:
            invoice_no: Invoice number
            action: Action performed (e.g., 'UPLOADED', 'CORRECTED', 'DUPLICATE_OVERRIDE')
            user_id: Telegram user ID
            details: Additional details
            
        Returns:
            Audit log entry dictionary
        """
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'invoice_no': invoice_no,
            'action': action,
            'user_id': str(user_id),
            'details': details
        }


if __name__ == "__main__":
    # Test the audit logger
    logger = AuditLogger()
    
    print("Testing Audit Logger...")
    print("=" * 80)
    
    # Test data
    user_id = 12345
    username = "testuser"
    images = ["invoice_12345_1.jpg", "invoice_12345_2.jpg"]
    start_time = datetime.now(timezone.utc)
    
    # Simulate processing delay
    import time
    time.sleep(0.1)
    
    end_time = datetime.now(timezone.utc)
    
    validation_result = {
        'status': 'WARNING',
        'errors': [],
        'warnings': ['Minor GST total difference: Rs.0.50']
    }
    
    corrections = {
        'Buyer_GSTIN': '29AAAAA0000A1Z5'
    }
    
    # Generate audit metadata
    print("\nGenerating audit metadata...")
    audit_metadata = logger.generate_audit_metadata(
        user_id=user_id,
        username=username,
        images=images,
        start_time=start_time,
        end_time=end_time,
        validation_result=validation_result,
        corrections=corrections
    )
    
    print("\nAudit Metadata:")
    for key, value in audit_metadata.items():
        print(f"  {key}: {value}")
    
    # Test confidence scores
    confidence_scores = {
        'Invoice_No': 0.95,
        'Invoice_Date': 0.90,
        'Buyer_GSTIN': 0.75,
        'Total_Taxable_Value': 0.88,
        'Total_GST': 0.85
    }
    
    corrections_metadata = {
        'original_values': {'Buyer_GSTIN': '29ABCDE1234F1Z5'},
        'corrected_values': {'Buyer_GSTIN': '29AAAAA0000A1Z5'},
        'correction_timestamp': datetime.now(timezone.utc).isoformat(),
        'corrected_by': user_id,
        'correction_reason': 'manual_review',
        'correction_count': 1
    }
    
    # Format for sheets
    print("\nFormatting for Google Sheets...")
    sheets_data = logger.format_for_sheets(
        audit_metadata=audit_metadata,
        confidence_scores=confidence_scores,
        corrections_metadata=corrections_metadata,
        fingerprint='abc123def456',
        duplicate_status='UNIQUE'
    )
    
    print("\nSheets Data:")
    for key, value in sheets_data.items():
        if key == 'Correction_Metadata':
            print(f"  {key}: [JSON data]")
        else:
            print(f"  {key}: {value}")
    
    # Test audit summary
    print("\n" + "=" * 80)
    print(logger.format_audit_summary(audit_metadata))
    
    # Test audit log entry
    print("\n" + "=" * 80)
    print("\nAudit Log Entry:")
    log_entry = logger.create_audit_log_entry(
        invoice_no='INV-2024-001',
        action='CORRECTED',
        user_id=user_id,
        details='Corrected Buyer_GSTIN field'
    )
    
    for key, value in log_entry.items():
        print(f"  {key}: {value}")
