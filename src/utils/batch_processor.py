"""
Batch Processor
Handles processing of multiple invoices with error isolation

Key features:
- Process multiple invoices sequentially
- Isolate failures - one invoice error doesn't block others
- Progress tracking and reporting
- Detailed error collection
"""
from typing import List, Dict, Callable
import os
import time

import config


class BatchProcessor:
    """Process multiple invoices in batch with error isolation"""
    
    def __init__(self, ocr_engine, gst_parser, validator, sheets_manager):
        """
        Initialize batch processor
        
        Args:
            ocr_engine: OCREngine instance
            gst_parser: GSTParser instance
            validator: GSTValidator instance
            sheets_manager: SheetsManager instance
        """
        self.ocr_engine = ocr_engine
        self.gst_parser = gst_parser
        self.validator = validator
        self.sheets_manager = sheets_manager
    
    def process_batch(
        self, 
        batch_invoices: List[List[str]], 
        progress_callback: Callable[[int, int, str], None] = None,
        audit_logger = None,
        user_id: str = None,
        username: str = None
    ) -> Dict:
        """
        Process list of invoice image sets
        
        Args:
            batch_invoices: List of image path lists, each list is one invoice
            progress_callback: Optional function to call with progress (current, total, status_message)
            audit_logger: Optional AuditLogger instance for Tier 2 features
            user_id: Telegram user ID for audit trail
            username: Telegram username for audit trail
            
        Returns:
            {
                'total': int,
                'successful': int,
                'failed': int,
                'results': [list of result dicts per invoice]
            }
        """
        total = len(batch_invoices)
        successful = 0
        failed = 0
        results = []
        
        for idx, invoice_images in enumerate(batch_invoices, 1):
            result = {
                'invoice_number': idx,
                'image_count': len(invoice_images),
                'success': False,
                'invoice_no': None,
                'error': None,
                'processing_time': 0
            }
            
            start_time = time.time()
            
            try:
                # Send progress update
                if progress_callback:
                    progress_callback(idx, total, f"Processing invoice {idx}/{total}...")
                
                # Process this invoice
                invoice_result = self._process_single_invoice(
                    invoice_images,
                    audit_logger,
                    user_id,
                    username
                )
                
                result.update(invoice_result)
                
                if invoice_result['success']:
                    successful += 1
                else:
                    failed += 1
                
            except Exception as e:
                # Catch any unexpected errors and continue
                result['error'] = f"Unexpected error: {str(e)}"
                result['success'] = False
                failed += 1
            
            finally:
                result['processing_time'] = time.time() - start_time
                results.append(result)
        
        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'results': results,
            'success_rate': (successful / total * 100) if total > 0 else 0
        }
    
    def _process_single_invoice(
        self,
        invoice_images: List[str],
        audit_logger,
        user_id: str,
        username: str
    ) -> Dict:
        """
        Process a single invoice with all steps
        
        Returns:
            Dictionary with processing result
        """
        try:
            # Step 1: OCR - Extract text from images
            ocr_result = self.ocr_engine.extract_text_from_images(invoice_images)
            ocr_text = ocr_result['text'] if isinstance(ocr_result, dict) else ocr_result
            
            if not ocr_text:
                return {
                    'success': False,
                    'error': 'OCR failed - could not extract text from images',
                    'step_failed': 'OCR'
                }
            
            # Step 2: Parse invoice with validation (Tier 1)
            parse_result = self.gst_parser.parse_invoice_with_validation(ocr_text)
            
            if not parse_result or 'invoice_data' not in parse_result:
                return {
                    'success': False,
                    'error': 'Parsing failed - could not extract invoice data',
                    'step_failed': 'Parsing'
                }
            
            invoice_data = parse_result['invoice_data']
            line_items = parse_result.get('line_items', [])
            validation_result = parse_result.get('validation_result', {
                'status': 'OK',
                'errors': [],
                'warnings': []
            })
            
            # Get invoice number
            invoice_no = invoice_data.get('Invoice_No', 'UNKNOWN')
            
            # Step 3: Check for duplicates (skipped when BATCH_SUPPRESS_VALIDATION is true)
            if not config.BATCH_SUPPRESS_VALIDATION:
                is_duplicate = self.sheets_manager.check_duplicate(invoice_no)
                
                if is_duplicate:
                    if user_id:
                        self.sheets_manager.log_duplicate_attempt(user_id, invoice_no, 'BATCH_REJECTED')
                    
                    return {
                        'success': False,
                        'error': f'Duplicate invoice: {invoice_no} already exists',
                        'step_failed': 'Duplicate Check',
                        'invoice_no': invoice_no,
                        'is_duplicate': True
                    }
            
            # Step 4: Format for sheets
            invoice_row = self.gst_parser.format_for_sheets(invoice_data)
            line_items_rows = self.gst_parser.line_item_extractor.format_items_for_sheets(
                line_items
            )
            
            # Step 5: Append to Google Sheets
            if audit_logger:
                # Tier 2 mode - with audit trail
                audit_data = audit_logger.create_audit_record(
                    user_id=user_id,
                    username=username,
                    page_count=len(invoice_images)
                )
                
                # Check for Tier 2 features
                from datetime import datetime
                import hashlib
                import json
                
                # Generate fingerprint for deduplication
                fingerprint_data = f"{invoice_no}_{invoice_data.get('Invoice_Date', '')}_{invoice_data.get('Total_Taxable_Value', '')}"
                fingerprint = hashlib.md5(fingerprint_data.encode()).hexdigest()
                
                # Append with audit trail
                self.sheets_manager.append_invoice_with_audit(
                    invoice_row,
                    line_items_rows,
                    validation_result,
                    audit_data,
                    fingerprint=fingerprint,
                    duplicate_status='UNIQUE'
                )
            else:
                # Tier 1 mode - basic
                self.sheets_manager.append_invoice_with_items(
                    invoice_row,
                    line_items_rows,
                    validation_result
                )
            
            # Step 6: Update master data (Tier 3 feature, skipped when suppressing validation)
            if not config.BATCH_SUPPRESS_VALIDATION:
                self._update_master_data(invoice_data, line_items)
            
            return {
                'success': True,
                'invoice_no': invoice_no,
                'validation_status': validation_result['status'],
                'line_item_count': len(line_items),
                'has_warnings': len(validation_result.get('warnings', [])) > 0,
                'has_errors': len(validation_result.get('errors', [])) > 0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'step_failed': 'Unknown'
            }
    
    def _update_master_data(self, invoice_data: Dict, line_items: List[Dict]):
        """
        Update customer and HSN master data (auto-learning)
        
        Args:
            invoice_data: Parsed invoice data
            line_items: Parsed line items
        """
        from datetime import datetime
        
        try:
            # Update customer master
            buyer_gstin = invoice_data.get('Buyer_GSTIN', '').strip()
            if buyer_gstin:
                customer_data = {
                    'GSTIN': buyer_gstin,
                    'Legal_Name': invoice_data.get('Buyer_Name', ''),
                    'Trade_Name': '',
                    'State_Code': invoice_data.get('Buyer_State_Code', ''),
                    'Default_Place_Of_Supply': invoice_data.get('Place_Of_Supply', ''),
                    'Last_Updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Usage_Count': '1'
                }
                self.sheets_manager.update_customer_master(buyer_gstin, customer_data)
            
            # Update HSN master
            for item in line_items:
                hsn_code = item.get('HSN', '').strip()
                if hsn_code:
                    hsn_data = {
                        'HSN_SAC_Code': hsn_code,
                        'Description': item.get('Item_Description', '')[:100],
                        'Default_GST_Rate': item.get('GST_Rate', ''),
                        'UQC': item.get('UOM', ''),
                        'Category': '',
                        'Last_Updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'Usage_Count': '1'
                    }
                    self.sheets_manager.update_hsn_master(hsn_code, hsn_data)
                    
        except Exception as e:
            # Don't fail the invoice processing if master data update fails
            print(f"Warning: Could not update master data: {str(e)}")
    
    def generate_batch_report(self, batch_result: Dict, output_path: str = None) -> str:
        """
        Generate formatted batch processing report
        
        Args:
            batch_result: Result from process_batch()
            output_path: Optional path to save report
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("BATCH PROCESSING REPORT")
        lines.append("=" * 80)
        lines.append(f"Total Invoices: {batch_result['total']}")
        lines.append(f"Successful: {batch_result['successful']} ({batch_result['success_rate']:.1f}%)")
        lines.append(f"Failed: {batch_result['failed']}")
        lines.append("")
        
        # Successful invoices
        if batch_result['successful'] > 0:
            lines.append("-" * 80)
            lines.append("SUCCESSFUL INVOICES:")
            lines.append("-" * 80)
            
            for result in batch_result['results']:
                if result['success']:
                    status_indicator = "⚠️" if result.get('has_warnings') or result.get('has_errors') else "✅"
                    lines.append(
                        f"{status_indicator} Invoice #{result['invoice_number']}: "
                        f"{result.get('invoice_no', 'N/A')} "
                        f"({result.get('line_item_count', 0)} items, "
                        f"{result['processing_time']:.1f}s) "
                        f"- {result.get('validation_status', 'OK')}"
                    )
            lines.append("")
        
        # Failed invoices
        if batch_result['failed'] > 0:
            lines.append("-" * 80)
            lines.append("FAILED INVOICES:")
            lines.append("-" * 80)
            
            for result in batch_result['results']:
                if not result['success']:
                    lines.append(
                        f"❌ Invoice #{result['invoice_number']}: "
                        f"FAILED at {result.get('step_failed', 'Unknown')} step"
                    )
                    if result.get('error'):
                        lines.append(f"   Error: {result['error']}")
                    if result.get('is_duplicate'):
                        lines.append(f"   (Duplicate of existing invoice: {result.get('invoice_no', 'N/A')})")
            lines.append("")
        
        # Summary statistics
        lines.append("-" * 80)
        lines.append("STATISTICS:")
        lines.append("-" * 80)
        
        total_time = sum(r['processing_time'] for r in batch_result['results'])
        avg_time = total_time / batch_result['total'] if batch_result['total'] > 0 else 0
        
        lines.append(f"Total Processing Time: {total_time:.1f}s")
        lines.append(f"Average Time per Invoice: {avg_time:.1f}s")
        
        # Count by validation status
        ok_count = sum(1 for r in batch_result['results'] if r.get('validation_status') == 'OK')
        warning_count = sum(1 for r in batch_result['results'] if r.get('validation_status') == 'WARNING')
        error_count = sum(1 for r in batch_result['results'] if r.get('validation_status') == 'ERROR')
        
        lines.append(f"\nValidation Status Breakdown:")
        lines.append(f"  OK: {ok_count}")
        lines.append(f"  WARNING: {warning_count}")
        lines.append(f"  ERROR: {error_count}")
        
        lines.append("")
        lines.append("=" * 80)
        
        report_text = '\n'.join(lines)
        
        # Save to file if path provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
        
        return report_text


if __name__ == "__main__":
    # Test batch processor
    print("Batch Processor Module")
    print("=" * 80)
    print("This module is designed to be used by the Telegram bot.")
    print("It processes multiple invoices sequentially with error isolation.")
    print("")
    print("Key features:")
    print("  • Process multiple invoices in one batch")
    print("  • One failure doesn't block other invoices")
    print("  • Progress tracking via callback")
    print("  • Detailed success/failure reporting")
    print("  • Automatic master data updates")
    print("")
    print("Usage: Import and use from telegram_bot.py")
    print("=" * 80)
