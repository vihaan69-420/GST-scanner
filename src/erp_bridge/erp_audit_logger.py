"""
ERP Bridge Audit Logger
Logs complete audit trail for every invoice processed through the ERP Bridge.
Structured JSON log format with file rotation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import erp_config as cfg
from .models import BatchResult, InvoiceResult


class ErpAuditLogger:
    """Per-invoice and per-batch audit logging for the ERP Bridge."""

    def __init__(
        self,
        log_dir: Optional[str] = None,
        max_mb: Optional[int] = None,
        backup_count: Optional[int] = None,
    ) -> None:
        self.log_dir = log_dir or cfg.AUDIT_LOG_DIR
        self.max_mb = max_mb or cfg.AUDIT_LOG_MAX_MB
        self.backup_count = backup_count or cfg.AUDIT_LOG_BACKUP_COUNT

        Path(self.log_dir).mkdir(parents=True, exist_ok=True)

        # Structured JSON logger
        self._logger = self._create_logger()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_invoice(
        self,
        batch_id: str,
        invoice_result: InvoiceResult,
        source_file: str = "",
        validation_errors: Optional[List[str]] = None,
        validation_warnings: Optional[List[str]] = None,
        tally_errors: Optional[List[str]] = None,
        duplicate_check: str = "UNIQUE",
        party_gstin: str = "",
    ) -> None:
        """Log a single invoice processing result."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO" if invoice_result.status == "SUCCESS" else "ERROR",
            "batch_id": batch_id,
            "invoice_no": invoice_result.invoice_no,
            "voucher_type": invoice_result.voucher_type,
            "source_file": source_file,
            "status": invoice_result.status,
            "validation_errors": validation_errors or [],
            "validation_warnings": validation_warnings or [],
            "tally_status": invoice_result.status,
            "tally_voucher_id": invoice_result.tally_voucher_id,
            "tally_errors": tally_errors or [],
            "processing_time_seconds": round(
                invoice_result.processing_time_seconds, 2
            ),
            "duplicate_check": duplicate_check,
            "party_gstin_masked": self._mask_gstin(party_gstin),
        }

        if invoice_result.error:
            entry["error"] = invoice_result.error
        if invoice_result.reason:
            entry["reason"] = invoice_result.reason

        self._logger.info(json.dumps(entry, ensure_ascii=False))

    def log_batch_summary(self, batch_result: BatchResult) -> None:
        """Log the batch-level summary."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "type": "BATCH_SUMMARY",
            "batch_id": batch_result.batch_id,
            "dry_run": batch_result.dry_run,
            "total_invoices": batch_result.total_invoices,
            "successful": batch_result.successful,
            "failed": batch_result.failed,
            "skipped_duplicates": batch_result.skipped_duplicates,
            "processing_time_seconds": round(
                batch_result.processing_time_seconds, 2
            ),
        }
        self._logger.info(json.dumps(entry, ensure_ascii=False))

    def log_error(
        self,
        batch_id: str,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a system-level error."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "type": "SYSTEM_ERROR",
            "batch_id": batch_id,
            "error_code": error_code,
            "message": message,
        }
        if details:
            entry["details"] = details
        self._logger.error(json.dumps(entry, ensure_ascii=False))

    def get_batch_log_path(self, batch_id: str) -> str:
        """Return the path to the per-batch JSON log file."""
        return os.path.join(self.log_dir, f"batch_{batch_id[:8]}.json")

    def write_batch_log(self, batch_result: BatchResult) -> str:
        """Write a complete batch log file and return its path."""
        path = self.get_batch_log_path(batch_result.batch_id)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(batch_result.to_dict(), fh, indent=2, ensure_ascii=False)
        return path

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _create_logger(self) -> logging.Logger:
        """Create a structured rotating-file logger."""
        logger = logging.getLogger(f"erp_bridge_audit_{id(self)}")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        log_file = os.path.join(self.log_dir, "erp_bridge_audit.log")
        handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_mb * 1024 * 1024,
            backupCount=self.backup_count,
            encoding="utf-8",
        )
        handler.setLevel(logging.DEBUG)
        # No extra formatting — entries are already structured JSON
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

        return logger

    @staticmethod
    def _mask_gstin(gstin: str) -> str:
        """Mask the middle portion of a GSTIN for privacy.

        Example: 29AABCU9603R1ZP -> 29AABC****R1ZP
        """
        if not gstin or len(gstin) < 10:
            return gstin
        return gstin[:6] + "****" + gstin[10:]
