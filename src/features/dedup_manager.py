"""
Deduplication Manager for Invoice Fingerprinting
Prevents duplicate invoice uploads using fingerprint-based detection
"""
import hashlib
import re
from typing import Dict, Optional, Tuple
from datetime import datetime


class DeduplicationManager:
    """Manage invoice deduplication using fingerprinting"""
    
    def __init__(self):
        """Initialize the deduplication manager"""
        pass
    
    def generate_fingerprint(self, invoice_data: Dict) -> str:
        """
        Generate a deterministic fingerprint for an invoice
        
        Uses:
        - Seller GSTIN (normalized)
        - Invoice Number (normalized)
        - Invoice Date (normalized to YYYYMMDD)
        
        Args:
            invoice_data: Invoice header data dictionary
            
        Returns:
            16-character hexadecimal fingerprint
        """
        seller_gstin = self._normalize_gstin(invoice_data.get('Seller_GSTIN', ''))
        invoice_no = self._normalize_invoice_no(invoice_data.get('Invoice_No', ''))
        invoice_date = self._normalize_date(invoice_data.get('Invoice_Date', ''))
        
        # Create fingerprint string
        fingerprint_str = f"{seller_gstin}|{invoice_no}|{invoice_date}"
        
        # Generate SHA256 hash and take first 16 characters
        hash_obj = hashlib.sha256(fingerprint_str.encode('utf-8'))
        fingerprint = hash_obj.hexdigest()[:16]
        
        return fingerprint
    
    def _normalize_gstin(self, gstin: str) -> str:
        """
        Normalize GSTIN for consistent fingerprinting
        
        Args:
            gstin: GSTIN string
            
        Returns:
            Normalized GSTIN (uppercase, no spaces/special chars)
        """
        if not gstin:
            return ''
        
        # Remove spaces, hyphens, and special characters
        normalized = re.sub(r'[^A-Z0-9]', '', gstin.upper())
        
        return normalized
    
    def _normalize_invoice_no(self, invoice_no: str) -> str:
        """
        Normalize invoice number for consistent fingerprinting
        
        Args:
            invoice_no: Invoice number string
            
        Returns:
            Normalized invoice number (uppercase, trimmed)
        """
        if not invoice_no:
            return ''
        
        # Trim whitespace and convert to uppercase
        normalized = invoice_no.strip().upper()
        
        # Remove common prefixes and normalize separators
        # Keep the core identifier consistent
        normalized = re.sub(r'\s+', '', normalized)  # Remove all spaces
        normalized = re.sub(r'[-_/]+', '-', normalized)  # Normalize separators
        
        return normalized
    
    def _normalize_date(self, date_str: str) -> str:
        """
        Normalize date to YYYYMMDD format for consistent fingerprinting
        
        Args:
            date_str: Date string (expected format: DD/MM/YYYY)
            
        Returns:
            Normalized date in YYYYMMDD format, or empty string if invalid
        """
        if not date_str:
            return ''
        
        try:
            # Try DD/MM/YYYY format
            if '/' in date_str:
                parts = date_str.strip().split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    # Validate and format
                    day = day.zfill(2)
                    month = month.zfill(2)
                    year = year.zfill(4)
                    
                    # Basic validation
                    if len(year) == 4 and len(month) == 2 and len(day) == 2:
                        return f"{year}{month}{day}"
            
            # Try other common formats
            # YYYY-MM-DD
            if '-' in date_str and len(date_str) >= 10:
                parts = date_str.strip().split('-')
                if len(parts) == 3 and len(parts[0]) == 4:
                    year, month, day = parts
                    return f"{year.zfill(4)}{month.zfill(2)}{day.zfill(2)}"
            
            return ''
        
        except Exception:
            return ''
    
    def format_duplicate_warning(
        self,
        new_invoice_data: Dict,
        existing_invoice_data: Dict
    ) -> str:
        """
        Format a duplicate warning message for Telegram (without Markdown to avoid parsing errors)
        
        Args:
            new_invoice_data: Newly extracted invoice data
            existing_invoice_data: Existing invoice data from sheets
            
        Returns:
            Formatted warning message
        """
        message = "⚠️ DUPLICATE INVOICE DETECTED\n\n"
        message += "This invoice appears to be already uploaded:\n\n"
        
        message += "Existing Record:\n"
        message += f"• Invoice No: {existing_invoice_data.get('Invoice_No', 'N/A')}\n"
        message += f"• Date: {existing_invoice_data.get('Invoice_Date', 'N/A')}\n"
        message += f"• Seller: {existing_invoice_data.get('Seller_Name', 'N/A')}"
        
        seller_gstin = existing_invoice_data.get('Seller_GSTIN', '')
        if seller_gstin:
            message += f" ({seller_gstin})"
        message += "\n"
        
        upload_timestamp = existing_invoice_data.get('Upload_Timestamp', '')
        if upload_timestamp:
            message += f"• Uploaded: {self._format_timestamp(upload_timestamp)}\n"
        
        user_id = existing_invoice_data.get('Telegram_User_ID', '')
        if user_id:
            message += f"• Uploaded by: User {user_id}\n"
        
        message += "\nCurrent Upload:\n"
        message += f"• Invoice No: {new_invoice_data.get('Invoice_No', 'N/A')}\n"
        message += f"• Date: {new_invoice_data.get('Invoice_Date', 'N/A')}\n"
        message += f"• Seller: {new_invoice_data.get('Seller_Name', 'N/A')}"
        
        new_seller_gstin = new_invoice_data.get('Seller_GSTIN', '')
        if new_seller_gstin:
            message += f" ({new_seller_gstin})"
        message += "\n"
        
        message += "\nActions:\n"
        message += "/override - Save anyway (will be marked as duplicate)\n"
        message += "/cancel - Discard this upload"
        
        return message
    
    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format ISO timestamp to readable format"""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%d/%m/%Y %H:%M UTC')
        except Exception:
            return timestamp_str
    
    def get_duplicate_status(self, is_override: bool) -> str:
        """
        Get duplicate status value for sheets
        
        Args:
            is_override: Whether this is a duplicate override
            
        Returns:
            Status string: 'UNIQUE' or 'DUPLICATE_OVERRIDE'
        """
        return 'DUPLICATE_OVERRIDE' if is_override else 'UNIQUE'


if __name__ == "__main__":
    # Test the deduplication manager
    manager = DeduplicationManager()
    
    print("Testing Deduplication Manager...")
    print("=" * 80)
    
    # Test case 1: Same invoice with identical data
    invoice1 = {
        'Seller_GSTIN': '24PQRST5678G1Z3',
        'Invoice_No': 'INV-2024-001',
        'Invoice_Date': '15/01/2024'
    }
    
    invoice2 = {
        'Seller_GSTIN': '24PQRST5678G1Z3',
        'Invoice_No': 'INV-2024-001',
        'Invoice_Date': '15/01/2024'
    }
    
    fp1 = manager.generate_fingerprint(invoice1)
    fp2 = manager.generate_fingerprint(invoice2)
    
    print(f"\nTest 1: Identical invoices")
    print(f"  Invoice 1 fingerprint: {fp1}")
    print(f"  Invoice 2 fingerprint: {fp2}")
    print(f"  Are duplicates: {fp1 == fp2}")
    
    # Test case 2: Same invoice with different formatting
    invoice3 = {
        'Seller_GSTIN': '24 PQRST 5678 G 1Z3',  # Spaces
        'Invoice_No': 'INV 2024 001',  # Different format
        'Invoice_Date': '15/01/2024'
    }
    
    fp3 = manager.generate_fingerprint(invoice3)
    
    print(f"\nTest 2: Same invoice, different formatting")
    print(f"  Invoice 1 fingerprint: {fp1}")
    print(f"  Invoice 3 fingerprint: {fp3}")
    print(f"  Are duplicates: {fp1 == fp3}")
    
    # Test case 3: Different invoice
    invoice4 = {
        'Seller_GSTIN': '24PQRST5678G1Z3',
        'Invoice_No': 'INV-2024-002',  # Different number
        'Invoice_Date': '15/01/2024'
    }
    
    fp4 = manager.generate_fingerprint(invoice4)
    
    print(f"\nTest 3: Different invoice number")
    print(f"  Invoice 1 fingerprint: {fp1}")
    print(f"  Invoice 4 fingerprint: {fp4}")
    print(f"  Are duplicates: {fp1 == fp4}")
    
    # Test normalization
    print(f"\nTest 4: Normalization")
    print(f"  GSTIN '24 PQRST 5678 G 1Z3' → '{manager._normalize_gstin('24 PQRST 5678 G 1Z3')}'")
    print(f"  Invoice 'INV 2024 001' → '{manager._normalize_invoice_no('INV 2024 001')}'")
    print(f"  Date '15/01/2024' → '{manager._normalize_date('15/01/2024')}'")
    print(f"  Date '2024-01-15' → '{manager._normalize_date('2024-01-15')}'")
    
    # Test duplicate warning message
    print(f"\nTest 5: Duplicate Warning Message")
    existing = {
        'Invoice_No': 'INV-2024-001',
        'Invoice_Date': '15/01/2024',
        'Seller_Name': 'XYZ Ltd',
        'Seller_GSTIN': '24PQRST5678G1Z3',
        'Upload_Timestamp': '2024-01-20T10:30:00Z',
        'Telegram_User_ID': '12345'
    }
    
    new = {
        'Invoice_No': 'INV-2024-001',
        'Invoice_Date': '15/01/2024',
        'Seller_Name': 'XYZ Ltd',
        'Seller_GSTIN': '24PQRST5678G1Z3'
    }
    
    print(manager.format_duplicate_warning(new, existing))
