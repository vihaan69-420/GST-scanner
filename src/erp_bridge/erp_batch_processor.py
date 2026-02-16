"""
ERP Bridge Batch Processor
Processes multiple invoices from CSV with per-invoice error isolation,
duplicate detection, and structured batch result reporting.
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import Callable, Dict, List, Optional, Set

from . import erp_config as cfg
from .erp_audit_logger import ErpAuditLogger
from .erp_validation_engine import ErpValidationEngine
from .models import (
    BatchResult,
    InvoiceBundle,
    InvoiceResult,
    TallyResponse,
    ValidationResult,
)
from .tally_connector import TallyConnector
from .tally_lookup_service import TallyLookupService
from .tally_xml_builder import TallyXmlBuilder


class ErpBatchProcessor:
    """Process InvoiceBundles sequentially with error isolation."""

    def __init__(
        self,
        connector: Optional[TallyConnector] = None,
        xml_builder: Optional[TallyXmlBuilder] = None,
        validator: Optional[ErpValidationEngine] = None,
        audit_logger: Optional[ErpAuditLogger] = None,
        lookup_service: Optional[TallyLookupService] = None,
    ) -> None:
        self.connector = connector or TallyConnector()
        self.xml_builder = xml_builder or TallyXmlBuilder()
        self.validator = validator or ErpValidationEngine()
        self.audit_logger = audit_logger or ErpAuditLogger()
        self.lookup = lookup_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_batch(
        self,
        bundles: List[InvoiceBundle],
        company_name: Optional[str] = None,
        dry_run: bool = False,
        skip_duplicates: bool = True,
        source_file: str = "",
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> BatchResult:
        """Process a list of InvoiceBundles.

        Args:
            bundles: List of InvoiceBundles to process.
            company_name: Tally company name (overrides per-invoice).
            dry_run: If True, validate and generate XML only.
            skip_duplicates: If True, skip duplicate invoices.
            source_file: Name of the source CSV file (for audit).
            progress_callback: Optional (current, total, message) callback.

        Returns:
            BatchResult with per-invoice results.
        """
        batch = BatchResult(dry_run=dry_run)
        batch.total_invoices = len(bundles)
        batch_start = time.time()

        # Track fingerprints within this batch for intra-batch dedup
        seen_fingerprints: Set[str] = set()

        for idx, bundle in enumerate(bundles, start=1):
            inv_no = bundle.header.invoice_no

            if progress_callback:
                progress_callback(
                    idx,
                    len(bundles),
                    f"Processing {inv_no} ({idx}/{len(bundles)})",
                )

            result = self._process_single(
                bundle=bundle,
                company_name=company_name,
                dry_run=dry_run,
                skip_duplicates=skip_duplicates,
                seen_fingerprints=seen_fingerprints,
                source_file=source_file,
                batch_id=batch.batch_id,
            )

            batch.results.append(result)

            if result.status == "SUCCESS":
                batch.successful += 1
            elif result.status == "SKIPPED":
                batch.skipped_duplicates += 1
            elif result.status == "VALID":
                batch.successful += 1  # dry-run valid counts as success
            else:
                batch.failed += 1

            # Throttle between Tally requests
            if not dry_run and idx < len(bundles):
                time.sleep(cfg.TALLY_REQUEST_DELAY_MS / 1000)

        batch.processing_time_seconds = time.time() - batch_start

        # Write audit log
        self.audit_logger.log_batch_summary(batch)
        batch.audit_log_path = self.audit_logger.write_batch_log(batch)

        return batch

    # ------------------------------------------------------------------
    # Single invoice processing
    # ------------------------------------------------------------------

    def _process_single(
        self,
        bundle: InvoiceBundle,
        company_name: Optional[str],
        dry_run: bool,
        skip_duplicates: bool,
        seen_fingerprints: Set[str],
        source_file: str,
        batch_id: str,
    ) -> InvoiceResult:
        """Process a single InvoiceBundle with error isolation."""
        result = InvoiceResult(
            invoice_no=bundle.header.invoice_no,
            voucher_type=bundle.header.voucher_type,
        )
        start = time.time()

        try:
            # Step 1: Intra-batch duplicate check
            fp = self._generate_fingerprint(bundle)
            if skip_duplicates and fp in seen_fingerprints:
                result.status = "SKIPPED"
                result.reason = "Duplicate invoice detected in batch"
                result.processing_time_seconds = time.time() - start
                self._audit_invoice(batch_id, result, source_file, bundle)
                return result
            seen_fingerprints.add(fp)

            # Step 2: Validation
            val_result = self.validator.validate_bundle(bundle)
            result.validation_errors = [e.message for e in val_result.errors]
            result.validation_warnings = [w.message for w in val_result.warnings]

            if not val_result.valid:
                if dry_run:
                    result.status = "INVALID"
                else:
                    result.status = "FAILED"
                    result.error = (
                        "Validation failed: "
                        + "; ".join(result.validation_errors[:3])
                    )
                result.processing_time_seconds = time.time() - start
                self._audit_invoice(batch_id, result, source_file, bundle)
                return result

            # Step 3: Optional Tally lookup
            if (
                cfg.ENABLE_TALLY_LOOKUP
                and self.lookup
                and not dry_run
            ):
                missing = self.lookup.lookup_bundle(bundle, company_name)
                if missing.get("missing_ledgers"):
                    result.status = "FAILED"
                    result.error = (
                        "Missing Tally ledgers: "
                        + ", ".join(missing["missing_ledgers"])
                    )
                    result.processing_time_seconds = time.time() - start
                    self._audit_invoice(batch_id, result, source_file, bundle)
                    return result
                if missing.get("missing_stock_items"):
                    result.status = "FAILED"
                    result.error = (
                        "Missing Tally stock items: "
                        + ", ".join(missing["missing_stock_items"])
                    )
                    result.processing_time_seconds = time.time() - start
                    self._audit_invoice(batch_id, result, source_file, bundle)
                    return result

            # Step 4: Build XML
            xml = self.xml_builder.build_voucher_xml(bundle, company_name)

            if dry_run:
                result.status = "VALID"
                result.xml_preview = xml
                result.processing_time_seconds = time.time() - start
                self._audit_invoice(batch_id, result, source_file, bundle)
                return result

            # Step 5: POST to Tally
            tally_resp = self.connector.post_xml(xml)

            if tally_resp.success:
                result.status = "SUCCESS"
                result.tally_voucher_id = tally_resp.voucher_id
                result.tally_voucher_number = tally_resp.voucher_number
            else:
                result.status = "FAILED"
                result.error = (
                    "Tally error: "
                    + "; ".join(tally_resp.errors[:3])
                    if tally_resp.errors
                    else "Unknown Tally error"
                )

        except Exception as exc:
            result.status = "FAILED"
            result.error = f"Unexpected error: {exc}"

        result.processing_time_seconds = time.time() - start
        self._audit_invoice(batch_id, result, source_file, bundle)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _audit_invoice(
        self,
        batch_id: str,
        result: InvoiceResult,
        source_file: str,
        bundle: InvoiceBundle,
    ) -> None:
        """Write audit log entry for one invoice."""
        self.audit_logger.log_invoice(
            batch_id=batch_id,
            invoice_result=result,
            source_file=source_file,
            validation_errors=result.validation_errors,
            validation_warnings=result.validation_warnings,
            duplicate_check=(
                "DUPLICATE" if result.status == "SKIPPED" else "UNIQUE"
            ),
            party_gstin=bundle.header.party_gstin,
        )

    @staticmethod
    def _generate_fingerprint(bundle: InvoiceBundle) -> str:
        """Generate a dedup fingerprint for an InvoiceBundle.

        Uses Invoice_No + Party_GSTIN + Invoice_Date.
        Replicates the pattern from src/features/dedup_manager.py.
        """
        hdr = bundle.header
        # Normalise components
        inv_no = re.sub(r"\s+", "", hdr.invoice_no.upper())
        gstin = re.sub(r"[^A-Z0-9]", "", hdr.party_gstin.upper())
        date = hdr.invoice_date.strip()

        raw = f"{gstin}|{inv_no}|{date}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
