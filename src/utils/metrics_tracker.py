"""
Metrics Tracker for GST Scanner
Tracks API usage, token consumption, processing performance, and errors
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from threading import Lock
import time


class MetricsTracker:
    """Track and persist operational metrics"""
    
    def __init__(self, metrics_file="logs/metrics.json"):
        """Initialize metrics tracker"""
        self.metrics_file = Path(metrics_file)
        self.lock = Lock()
        self.start_time = datetime.now(timezone.utc)
        
        # Initialize metrics structure
        self.metrics = {
            "start_time": self.start_time.isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": 0,
            "invoices": {
                "total": 0,
                "success": 0,
                "failed": 0,
                "today": 0,
                "last_24h": 0
            },
            "api_calls": {
                "ocr": {
                    "count": 0,
                    "estimated_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "avg_tokens_per_call": 0
                },
                "parsing": {
                    "count": 0,
                    "estimated_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "avg_tokens_per_call": 0
                },
                "total_cost_usd": 0.0
            },
            "performance": {
                "avg_processing_time_seconds": 0.0,
                "min_processing_time_seconds": 0.0,
                "max_processing_time_seconds": 0.0,
                "total_processing_time_seconds": 0.0,
                "active_sessions": 0
            },
            "errors": {
                "total": 0,
                "by_type": {},
                "last_error": None
            },
            "integrations": {
                "telegram_connected": True,
                "sheets_accessible": True,
                "gemini_api_available": True,
                "last_health_check": None
            }
        }
        
        # Load existing metrics if available
        self._load_metrics()
    
    def _load_metrics(self):
        """Load metrics from file if exists"""
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    saved_metrics = json.load(f)
                    # Merge saved metrics with current structure
                    self.metrics.update(saved_metrics)
                    # Update uptime
                    self._update_uptime()
        except Exception as e:
            print(f"[WARNING] Could not load metrics: {e}")
    
    def _save_metrics(self):
        """Save metrics to file"""
        try:
            with self.lock:
                self._update_uptime()
                self.metrics['last_updated'] = datetime.now(timezone.utc).isoformat()
                
                # Ensure directory exists
                self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(self.metrics_file, 'w', encoding='utf-8') as f:
                    json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Could not save metrics: {e}")
    
    def _update_uptime(self):
        """Update uptime calculation"""
        uptime = (datetime.now(timezone.utc) - datetime.fromisoformat(self.metrics['start_time'])).total_seconds()
        self.metrics['uptime_seconds'] = int(uptime)
    
    def record_ocr_call(self, image_size_bytes: int, estimated_tokens: Optional[int] = None):
        """
        Record an OCR API call
        
        Args:
            image_size_bytes: Size of image in bytes
            estimated_tokens: Estimated tokens (or auto-calculate)
        """
        with self.lock:
            # Estimate tokens based on image size if not provided
            # Rough estimate: 1KB image ~ 100 tokens
            if estimated_tokens is None:
                estimated_tokens = max(1000, int((image_size_bytes / 1024) * 100))
            
            # Gemini Flash pricing: $0.0001875 per 1K tokens for vision
            cost = (estimated_tokens / 1000) * 0.0001875
            
            self.metrics['api_calls']['ocr']['count'] += 1
            self.metrics['api_calls']['ocr']['estimated_tokens'] += estimated_tokens
            self.metrics['api_calls']['ocr']['estimated_cost_usd'] += cost
            
            # Update average
            ocr = self.metrics['api_calls']['ocr']
            if ocr['count'] > 0:
                ocr['avg_tokens_per_call'] = ocr['estimated_tokens'] // ocr['count']
            
            # Update total cost
            self.metrics['api_calls']['total_cost_usd'] = (
                self.metrics['api_calls']['ocr']['estimated_cost_usd'] +
                self.metrics['api_calls']['parsing']['estimated_cost_usd']
            )
            
            self._save_metrics()
    
    def record_parsing_call(self, text_length: int, estimated_tokens: Optional[int] = None):
        """
        Record a parsing API call
        
        Args:
            text_length: Length of input text
            estimated_tokens: Estimated tokens (or auto-calculate)
        """
        with self.lock:
            # Estimate tokens: ~0.75 tokens per character
            if estimated_tokens is None:
                estimated_tokens = max(500, int(text_length * 0.75))
            
            # Gemini Flash pricing: $0.000075 per 1K tokens for text
            cost = (estimated_tokens / 1000) * 0.000075
            
            self.metrics['api_calls']['parsing']['count'] += 1
            self.metrics['api_calls']['parsing']['estimated_tokens'] += estimated_tokens
            self.metrics['api_calls']['parsing']['estimated_cost_usd'] += cost
            
            # Update average
            parsing = self.metrics['api_calls']['parsing']
            if parsing['count'] > 0:
                parsing['avg_tokens_per_call'] = parsing['estimated_tokens'] // parsing['count']
            
            # Update total cost
            self.metrics['api_calls']['total_cost_usd'] = (
                self.metrics['api_calls']['ocr']['estimated_cost_usd'] +
                self.metrics['api_calls']['parsing']['estimated_cost_usd']
            )
            
            self._save_metrics()
    
    def record_invoice_complete(self, success: bool, processing_time_seconds: float):
        """
        Record invoice processing completion
        
        Args:
            success: Whether processing was successful
            processing_time_seconds: Time taken to process
        """
        with self.lock:
            self.metrics['invoices']['total'] += 1
            
            if success:
                self.metrics['invoices']['success'] += 1
            else:
                self.metrics['invoices']['failed'] += 1
            
            # Update processing time stats
            perf = self.metrics['performance']
            perf['total_processing_time_seconds'] += processing_time_seconds
            
            if perf['min_processing_time_seconds'] == 0:
                perf['min_processing_time_seconds'] = processing_time_seconds
            else:
                perf['min_processing_time_seconds'] = min(
                    perf['min_processing_time_seconds'],
                    processing_time_seconds
                )
            
            perf['max_processing_time_seconds'] = max(
                perf['max_processing_time_seconds'],
                processing_time_seconds
            )
            
            if self.metrics['invoices']['success'] > 0:
                perf['avg_processing_time_seconds'] = (
                    perf['total_processing_time_seconds'] / self.metrics['invoices']['success']
                )
            
            self._save_metrics()
    
    def record_error(self, error_type: str, error_message: str, invoice_id: Optional[str] = None):
        """
        Record an error
        
        Args:
            error_type: Type of error (e.g., OCRError, ValidationError)
            error_message: Error message
            invoice_id: Related invoice ID if applicable
        """
        with self.lock:
            self.metrics['errors']['total'] += 1
            
            # Update by type
            if error_type not in self.metrics['errors']['by_type']:
                self.metrics['errors']['by_type'][error_type] = 0
            self.metrics['errors']['by_type'][error_type] += 1
            
            # Store last error
            self.metrics['errors']['last_error'] = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'type': error_type,
                'message': error_message,
                'invoice_id': invoice_id
            }
            
            self._save_metrics()
    
    def set_active_sessions(self, count: int):
        """Update active session count"""
        with self.lock:
            self.metrics['performance']['active_sessions'] = count
            self._save_metrics()
    
    def update_integration_status(self, integration: str, status: bool):
        """
        Update integration health status
        
        Args:
            integration: Name (telegram_connected, sheets_accessible, gemini_api_available)
            status: Whether integration is healthy
        """
        with self.lock:
            if integration in self.metrics['integrations']:
                self.metrics['integrations'][integration] = status
                self.metrics['integrations']['last_health_check'] = datetime.now(timezone.utc).isoformat()
                self._save_metrics()
    
    def get_metrics(self) -> Dict:
        """Get current metrics snapshot"""
        with self.lock:
            self._update_uptime()
            return self.metrics.copy()
    
    def get_summary(self) -> str:
        """Get human-readable metrics summary"""
        with self.lock:
            self._update_uptime()
            
            uptime_hours = self.metrics['uptime_seconds'] / 3600
            inv = self.metrics['invoices']
            api = self.metrics['api_calls']
            perf = self.metrics['performance']
            err = self.metrics['errors']
            
            success_rate = (inv['success'] / inv['total'] * 100) if inv['total'] > 0 else 0
            
            summary = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          GST SCANNER - METRICS                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

📊 INVOICES
   Total:        {inv['total']}
   Success:      {inv['success']} ({success_rate:.1f}%)
   Failed:       {inv['failed']}
   Today:        {inv['today']}

🔌 API USAGE
   OCR Calls:    {api['ocr']['count']} (Est. {api['ocr']['estimated_tokens']:,} tokens)
   Parse Calls:  {api['parsing']['count']} (Est. {api['parsing']['estimated_tokens']:,} tokens)
   Total Cost:   ${api['total_cost_usd']:.4f} USD

⚡ PERFORMANCE
   Avg Time:     {perf['avg_processing_time_seconds']:.2f}s per invoice
   Active:       {perf['active_sessions']} session(s)

⚠️  ERRORS
   Total:        {err['total']}

⏱️  UPTIME
   Duration:     {uptime_hours:.1f} hours

╚══════════════════════════════════════════════════════════════════════════════╝
"""
            return summary


# Global metrics instance
_global_metrics = None

def get_metrics_tracker():
    """Get or create global metrics tracker instance"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsTracker()
    return _global_metrics


if __name__ == "__main__":
    # Test the metrics tracker
    tracker = get_metrics_tracker()
    
    print("\n" + "="*80)
    print("Testing Metrics Tracker")
    print("="*80 + "\n")
    
    # Simulate some activity
    print("Recording test metrics...\n")
    
    tracker.record_ocr_call(85000, 2000)  # 85KB image
    tracker.record_parsing_call(1500, 1125)  # 1500 char text
    tracker.record_invoice_complete(True, 12.5)
    
    tracker.record_ocr_call(77000, 1800)
    tracker.record_parsing_call(1350, 1012)
    tracker.record_invoice_complete(True, 10.8)
    
    tracker.record_error("ValidationError", "GST total mismatch", "INV-001")
    
    # Print summary
    print(tracker.get_summary())
    
    print(f"\n[OK] Metrics saved to: {tracker.metrics_file}")
