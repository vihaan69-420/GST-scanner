"""
Structured Logging System for GST Scanner
Provides rotating file logs with immediate flush for real-time monitoring
"""
import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


class GSTLogger:
    """Centralized logging for GST Scanner with rotation and formatting"""
    
    def __init__(self, name="GST-Scanner", log_dir="logs", log_level="INFO"):
        """
        Initialize logger with rotating file handlers
        
        Args:
            name: Logger name
            log_dir: Directory for log files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level))
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Create logs directory if it doesn't exist
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Define log format with timestamp, level, component, and message
        log_format = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 1. Main rotating file handler (10MB per file, keep 5 files)
        main_log_file = log_path / 'gst_scanner.log'
        main_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(log_format)
        self.logger.addHandler(main_handler)
        
        # 2. Error-only log file (5MB per file, keep 3 files)
        error_log_file = log_path / 'errors.log'
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(log_format)
        self.logger.addHandler(error_handler)
        
        # 3. Console handler with color-coded output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)
        self.logger.addHandler(console_handler)
        
        # Force immediate flush for all handlers
        for handler in self.logger.handlers:
            handler.flush()
    
    def debug(self, message, component=""):
        """Log debug message"""
        self._log(logging.DEBUG, message, component)
    
    def info(self, message, component=""):
        """Log info message"""
        self._log(logging.INFO, message, component)
    
    def warning(self, message, component=""):
        """Log warning message"""
        self._log(logging.WARNING, message, component)
    
    def error(self, message, component="", exc_info=False):
        """Log error message"""
        self._log(logging.ERROR, message, component, exc_info=exc_info)
    
    def critical(self, message, component="", exc_info=False):
        """Log critical message"""
        self._log(logging.CRITICAL, message, component, exc_info=exc_info)
    
    def _log(self, level, message, component="", exc_info=False):
        """Internal logging method with component prefix"""
        if component:
            message = f"[{component}] {message}"
        
        self.logger.log(level, message, exc_info=exc_info)
        
        # Force immediate flush
        for handler in self.logger.handlers:
            handler.flush()
    
    def log_invoice_start(self, invoice_id, user_id, image_count):
        """Log invoice processing start"""
        self.info(
            f"Invoice {invoice_id} - Started processing {image_count} image(s) for user {user_id}",
            component="InvoiceProcessor"
        )
    
    def log_invoice_complete(self, invoice_id, invoice_no, processing_time, status):
        """Log invoice processing completion"""
        self.info(
            f"Invoice {invoice_id} - Completed as '{invoice_no}' in {processing_time:.2f}s - Status: {status}",
            component="InvoiceProcessor"
        )
    
    def log_ocr_call(self, invoice_id, image_num, image_size_kb):
        """Log OCR API call"""
        self.info(
            f"Invoice {invoice_id} - OCR call for image {image_num} ({image_size_kb}KB)",
            component="OCR"
        )
    
    def log_parsing_call(self, invoice_id, text_length):
        """Log GST parsing API call"""
        self.info(
            f"Invoice {invoice_id} - Parsing {text_length} chars of OCR text",
            component="Parser"
        )
    
    def log_sheets_update(self, invoice_no, row_num, line_items_count):
        """Log Google Sheets update"""
        self.info(
            f"Invoice {invoice_no} - Updated sheet row {row_num} with {line_items_count} line items",
            component="Sheets"
        )
    
    def log_error(self, invoice_id, error_type, error_message):
        """Log error with context"""
        self.error(
            f"Invoice {invoice_id} - {error_type}: {error_message}",
            component="Error"
        )


# Global logger instance
_global_logger = None

def get_logger(log_level="INFO"):
    """Get or create global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = GSTLogger(log_level=log_level)
    return _global_logger


if __name__ == "__main__":
    # Test the logger
    logger = get_logger("DEBUG")
    
    print("\n" + "="*80)
    print("Testing GST Logger")
    print("="*80 + "\n")
    
    logger.info("Logger initialized successfully")
    logger.debug("This is a debug message", component="Test")
    logger.info("This is an info message", component="Test")
    logger.warning("This is a warning message", component="Test")
    logger.error("This is an error message", component="Test")
    
    # Test invoice logging
    logger.log_invoice_start("TEST-001", 12345, 2)
    logger.log_ocr_call("TEST-001", 1, 85)
    logger.log_parsing_call("TEST-001", 1250)
    logger.log_sheets_update("INV-2024-001", 45, 5)
    logger.log_invoice_complete("TEST-001", "INV-2024-001", 12.5, "SUCCESS")
    
    print("\n[OK] Logs written to logs/ folder")
    print("Check logs/gst_scanner.log for all logs")
    print("Check logs/errors.log for errors only")
