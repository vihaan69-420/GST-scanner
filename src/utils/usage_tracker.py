"""
Usage Tracker for GST Scanner
Three-level tracking: OCR calls, Invoice usage, Customer aggregation
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from threading import Lock
import config
from utils.pricing_calculator import get_pricing_calculator


class UsageTracker:
    """Track usage at three levels: OCR, Invoice, Customer"""
    
    def __init__(self, logs_dir: str = "logs"):
        """
        Initialize usage tracker
        
        Args:
            logs_dir: Directory for log files
        """
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        self.pricing_calc = get_pricing_calculator()
        self.lock = Lock()
        
        # File paths
        self.ocr_calls_file = self.logs_dir / "ocr_calls.jsonl"
        self.invoice_usage_file = self.logs_dir / "invoice_usage.jsonl"
        self.customer_summary_file = self.logs_dir / "customer_usage_summary.json"
        self.daily_summaries_file = self.logs_dir / "daily_summaries.jsonl"
        self.monthly_summaries_file = self.logs_dir / "monthly_summaries.jsonl"
        self.order_usage_file = self.logs_dir / "order_usage.jsonl"
    
    def record_ocr_call(
        self,
        invoice_id: str,
        page_number: int,
        model_name: str,
        prompt_tokens: int,
        output_tokens: int,
        processing_time_ms: int,
        image_size_bytes: int,
        customer_id: str,
        telegram_user_id: int,
        status: str = "success"
    ) -> Dict:
        """
        Record an individual OCR API call (Level 1)
        
        Args:
            invoice_id: Invoice identifier
            page_number: Page number (1-indexed)
            model_name: Gemini model used
            prompt_tokens: Input tokens
            output_tokens: Output tokens
            processing_time_ms: API call duration in milliseconds
            image_size_bytes: Original image size
            customer_id: Customer identifier
            telegram_user_id: Telegram user ID
            status: success or error
        
        Returns:
            OCR call record dict
        """
        if not config.ENABLE_USAGE_TRACKING or not config.ENABLE_OCR_LEVEL_TRACKING:
            return {}
        
        try:
            with self.lock:
                timestamp = datetime.now(timezone.utc).isoformat()
                call_id = f"ocr_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{page_number:03d}"
                total_tokens = prompt_tokens + output_tokens
                
                record = {
                    "call_id": call_id,
                    "invoice_id": invoice_id,
                    "page_number": page_number,
                    "timestamp": timestamp,
                    "model_name": model_name,
                    "prompt_tokens": prompt_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "processing_time_ms": processing_time_ms,
                    "image_size_bytes": image_size_bytes,
                    "customer_id": customer_id,
                    "telegram_user_id": telegram_user_id,
                    "status": status
                }
                
                # Append to JSONL file
                with open(self.ocr_calls_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
                
                return record
        except Exception as e:
            print(f"[BACKGROUND] OCR call tracking failed: {e}")
            return {}
    
    def record_invoice_usage(
        self,
        invoice_id: str,
        customer_id: str,
        telegram_user_id: int,
        telegram_username: str,
        page_count: int,
        total_ocr_calls: int,
        total_parsing_calls: int,
        ocr_tokens: Dict[str, int],
        parsing_tokens: Dict[str, int],
        processing_time_seconds: float,
        ocr_time_seconds: float,
        parsing_time_seconds: float,
        sheets_time_seconds: float,
        validation_status: str,
        confidence_avg: float,
        had_corrections: bool,
        ocr_call_ids: List[str]
    ) -> Dict:
        """
        Record invoice-level usage (Level 2)
        
        Args:
            invoice_id: Invoice identifier
            customer_id: Customer identifier
            telegram_user_id: Telegram user ID
            telegram_username: Telegram username
            page_count: Number of pages
            total_ocr_calls: Number of OCR API calls
            total_parsing_calls: Number of parsing API calls
            ocr_tokens: Dict with prompt, output, total keys
            parsing_tokens: Dict with prompt, output, total keys
            processing_time_seconds: Total processing time
            ocr_time_seconds: OCR time
            parsing_time_seconds: Parsing time
            sheets_time_seconds: Sheets write time
            validation_status: ok, warning, error, corrected
            confidence_avg: Average confidence score
            had_corrections: Whether manual corrections were made
            ocr_call_ids: List of OCR call IDs
        
        Returns:
            Invoice usage record dict
        """
        if not config.ENABLE_USAGE_TRACKING or not config.ENABLE_INVOICE_LEVEL_TRACKING:
            return {}
        
        try:
            with self.lock:
                timestamp = datetime.now(timezone.utc).isoformat()
                total_tokens = ocr_tokens['total'] + parsing_tokens['total']
                
                # Calculate costs
                costs = self.pricing_calc.calculate_invoice_cost(
                    ocr_tokens=ocr_tokens['total'],
                    parsing_tokens=parsing_tokens['total']
                )
                
                record = {
                    "invoice_id": invoice_id,
                    "customer_id": customer_id,
                    "telegram_user_id": telegram_user_id,
                    "telegram_username": telegram_username,
                    "timestamp": timestamp,
                    "page_count": page_count,
                    "total_ocr_calls": total_ocr_calls,
                    "total_parsing_calls": total_parsing_calls,
                    "ocr_tokens": ocr_tokens,
                    "parsing_tokens": parsing_tokens,
                    "total_tokens": total_tokens,
                    "ocr_cost_usd": costs['ocr_cost_usd'],
                    "parsing_cost_usd": costs['parsing_cost_usd'],
                    "total_cost_usd": costs['total_cost_usd'],
                    "processing_time_seconds": processing_time_seconds,
                    "ocr_time_seconds": ocr_time_seconds,
                    "parsing_time_seconds": parsing_time_seconds,
                    "sheets_time_seconds": sheets_time_seconds,
                    "validation_status": validation_status,
                    "confidence_avg": confidence_avg,
                    "had_corrections": had_corrections,
                    "ocr_call_ids": ocr_call_ids
                }
                
                # Append to JSONL file
                with open(self.invoice_usage_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
                
                return record
        except Exception as e:
            print(f"[BACKGROUND] Invoice usage tracking failed: {e}")
            return {}
    
    def update_customer_summary(self, invoice_usage: Dict) -> Dict:
        """
        Update customer-level aggregation (Level 3)
        
        Args:
            invoice_usage: Invoice usage record
        
        Returns:
            Updated customer summary
        """
        if not config.ENABLE_USAGE_TRACKING or not config.ENABLE_CUSTOMER_AGGREGATION:
            return {}
        
        try:
            with self.lock:
                customer_id = invoice_usage['customer_id']
                
                # Load existing summary or create new
                if self.customer_summary_file.exists():
                    with open(self.customer_summary_file, 'r', encoding='utf-8') as f:
                        summary = json.load(f)
                else:
                    summary = {
                        "customer_id": customer_id,
                        "customer_name": config.DEFAULT_CUSTOMER_NAME,
                        "period_start": invoice_usage['timestamp'],
                        "total_invoices": 0,
                        "total_pages": 0,
                        "total_ocr_calls": 0,
                        "total_parsing_calls": 0,
                        "total_ocr_tokens": 0,
                        "total_parsing_tokens": 0,
                        "total_tokens": 0,
                        "total_ocr_cost_usd": 0.0,
                        "total_parsing_cost_usd": 0.0,
                        "total_cost_usd": 0.0,
                        "success_count": 0,
                        "total_confidence": 0.0,
                        "correction_count": 0
                    }
                
                # Update aggregates
                summary['last_updated'] = datetime.now(timezone.utc).isoformat()
                summary['period_end'] = invoice_usage['timestamp']
                summary['total_invoices'] += 1
                summary['total_pages'] += invoice_usage['page_count']
                summary['total_ocr_calls'] += invoice_usage['total_ocr_calls']
                summary['total_parsing_calls'] += invoice_usage['total_parsing_calls']
                summary['total_ocr_tokens'] += invoice_usage['ocr_tokens']['total']
                summary['total_parsing_tokens'] += invoice_usage['parsing_tokens']['total']
                summary['total_tokens'] += invoice_usage['total_tokens']
                summary['total_ocr_cost_usd'] += invoice_usage['ocr_cost_usd']
                summary['total_parsing_cost_usd'] += invoice_usage['parsing_cost_usd']
                summary['total_cost_usd'] += invoice_usage['total_cost_usd']
                
                # Track quality metrics
                if invoice_usage['validation_status'] == 'ok':
                    summary['success_count'] += 1
                if invoice_usage['confidence_avg'] > 0:
                    summary['total_confidence'] += invoice_usage['confidence_avg']
                if invoice_usage['had_corrections']:
                    summary['correction_count'] += 1
                
                # Calculate averages
                summary['avg_cost_per_invoice'] = round(
                    summary['total_cost_usd'] / summary['total_invoices'], 6
                )
                summary['avg_tokens_per_invoice'] = round(
                    summary['total_tokens'] / summary['total_invoices'], 0
                )
                summary['avg_pages_per_invoice'] = round(
                    summary['total_pages'] / summary['total_invoices'], 2
                )
                summary['success_rate'] = round(
                    summary['success_count'] / summary['total_invoices'], 3
                )
                summary['avg_confidence'] = round(
                    summary['total_confidence'] / summary['total_invoices'], 3
                ) if summary['total_invoices'] > 0 else 0.0
                summary['correction_rate'] = round(
                    summary['correction_count'] / summary['total_invoices'], 3
                )
                
                # Save updated summary
                with open(self.customer_summary_file, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, indent=2, ensure_ascii=False)
                
                return summary
        except Exception as e:
            print(f"[BACKGROUND] Customer summary update failed: {e}")
            return {}
    
    def record_order_usage(
        self,
        order_id: str,
        customer_id: str,
        telegram_user_id: int,
        telegram_username: str,
        page_count: int,
        total_items: int,
        total_quantity: int,
        matched_count: int,
        unmatched_count: int,
        subtotal: float,
        processing_time_seconds: float,
        status: str,
        customer_name: str = "",
        pdf_size_bytes: int = 0
    ) -> Dict:
        """
        Record order upload usage (Level 2 - Order)
        
        Args:
            order_id: Order identifier
            customer_id: Customer identifier
            telegram_user_id: Telegram user ID
            telegram_username: Telegram username
            page_count: Number of pages uploaded
            total_items: Number of line items extracted
            total_quantity: Sum of all quantities
            matched_count: Items matched with pricing
            unmatched_count: Items without pricing match
            subtotal: Total order value
            processing_time_seconds: Total processing time
            status: completed, failed, review_required
            customer_name: Customer name from order
            pdf_size_bytes: Size of generated PDF
        
        Returns:
            Order usage record dict
        """
        if not config.ENABLE_USAGE_TRACKING or not config.ENABLE_ORDER_TRACKING:
            return {}
        
        try:
            with self.lock:
                timestamp = datetime.now(timezone.utc).isoformat()
                
                match_rate = (matched_count / total_items * 100) if total_items > 0 else 0.0
                
                record = {
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "telegram_user_id": telegram_user_id,
                    "telegram_username": telegram_username,
                    "customer_name": customer_name,
                    "timestamp": timestamp,
                    "page_count": page_count,
                    "total_items": total_items,
                    "total_quantity": total_quantity,
                    "matched_count": matched_count,
                    "unmatched_count": unmatched_count,
                    "match_rate": round(match_rate, 1),
                    "subtotal": subtotal,
                    "processing_time_seconds": round(processing_time_seconds, 2),
                    "status": status,
                    "pdf_size_bytes": pdf_size_bytes
                }
                
                # Append to JSONL file
                with open(self.order_usage_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
                
                return record
        except Exception as e:
            print(f"[BACKGROUND] Order usage tracking failed: {e}")
            return {}
    
    def get_order_usage_records(self, limit: int = 20) -> List[Dict]:
        """Get recent order usage records"""
        try:
            if not self.order_usage_file.exists():
                return []
            
            with open(self.order_usage_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            records = []
            for line in lines[-limit:]:
                try:
                    records.append(json.loads(line))
                except:
                    continue
            
            records.reverse()  # Most recent first
            return records
        except Exception as e:
            print(f"[WARNING] Could not load order usage records: {e}")
            return []
    
    def get_order_summary(self) -> Dict:
        """Get aggregated order summary stats"""
        try:
            records = self.get_order_usage_records(limit=1000)
            if not records:
                return {}
            
            total_orders = len(records)
            total_items = sum(r.get('total_items', 0) for r in records)
            total_quantity = sum(r.get('total_quantity', 0) for r in records)
            total_subtotal = sum(r.get('subtotal', 0) for r in records)
            total_matched = sum(r.get('matched_count', 0) for r in records)
            total_unmatched = sum(r.get('unmatched_count', 0) for r in records)
            completed = sum(1 for r in records if r.get('status') == 'completed')
            avg_processing = sum(r.get('processing_time_seconds', 0) for r in records) / total_orders
            
            return {
                "total_orders": total_orders,
                "total_items": total_items,
                "total_quantity": total_quantity,
                "total_subtotal": round(total_subtotal, 2),
                "total_matched": total_matched,
                "total_unmatched": total_unmatched,
                "overall_match_rate": round(total_matched / (total_matched + total_unmatched) * 100, 1) if (total_matched + total_unmatched) > 0 else 0,
                "completed_count": completed,
                "success_rate": round(completed / total_orders * 100, 1) if total_orders > 0 else 0,
                "avg_processing_seconds": round(avg_processing, 2),
                "last_updated": records[0].get('timestamp') if records else None
            }
        except Exception as e:
            print(f"[WARNING] Could not compute order summary: {e}")
            return {}
    
    def get_customer_summary(self, customer_id: str = None) -> Dict:
        """Get customer summary"""
        if customer_id is None:
            customer_id = config.DEFAULT_CUSTOMER_ID
        
        try:
            if self.customer_summary_file.exists():
                with open(self.customer_summary_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[WARNING] Could not load customer summary: {e}")
        
        return {}


# Global instance
_usage_tracker = None

def get_usage_tracker() -> UsageTracker:
    """Get or create global usage tracker instance"""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker


if __name__ == "__main__":
    # Test the usage tracker
    tracker = get_usage_tracker()
    
    print("\n" + "="*80)
    print("Testing Usage Tracker")
    print("="*80 + "\n")
    
    # Simulate OCR call tracking
    ocr_record = tracker.record_ocr_call(
        invoice_id="TEST-INV-001",
        page_number=1,
        model_name="gemini-2.5-flash",
        prompt_tokens=1245,
        output_tokens=856,
        processing_time_ms=1234,
        image_size_bytes=85000,
        customer_id="CUST001",
        telegram_user_id=7332697107,
        status="success"
    )
    print(f"[OK] OCR call recorded: {ocr_record.get('call_id', 'disabled')}")
    
    # Simulate invoice usage tracking
    invoice_record = tracker.record_invoice_usage(
        invoice_id="TEST-INV-001",
        customer_id="CUST001",
        telegram_user_id=7332697107,
        telegram_username="test_user",
        page_count=3,
        total_ocr_calls=3,
        total_parsing_calls=2,
        ocr_tokens={'prompt': 3456, 'output': 2345, 'total': 5801},
        parsing_tokens={'prompt': 1200, 'output': 450, 'total': 1650},
        processing_time_seconds=12.5,
        ocr_time_seconds=3.7,
        parsing_time_seconds=2.1,
        sheets_time_seconds=6.7,
        validation_status="ok",
        confidence_avg=0.92,
        had_corrections=False,
        ocr_call_ids=[ocr_record.get('call_id', 'test')]
    )
    print(f"[OK] Invoice usage recorded: {invoice_record.get('invoice_id', 'disabled')}")
    
    # Update customer summary
    if invoice_record:
        summary = tracker.update_customer_summary(invoice_record)
        print(f"[OK] Customer summary updated")
        print(f"     Total invoices: {summary.get('total_invoices', 0)}")
        print(f"     Total cost: ${summary.get('total_cost_usd', 0):.6f}")
    
    print("\n" + "="*80)
