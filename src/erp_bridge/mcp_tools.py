"""
MCP Tool Endpoints for the ERP Bridge
Defines the three MCP tools: csv_to_tally, validate_csv, tally_connection_test.

These functions are the public API of the ERP Bridge module.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from . import erp_config as cfg
from .csv_loader_service import CsvLoaderService
from .csv_schema_validator import CsvSchemaValidator
from .erp_audit_logger import ErpAuditLogger
from .erp_batch_processor import ErpBatchProcessor
from .erp_validation_engine import ErpValidationEngine
from .models import (
    BatchResult,
    CsvValidationReport,
    FileValidationReport,
    TallyConnectionResult,
    ValidationError,
)
from .tally_connector import TallyConnector
from .tally_lookup_service import TallyLookupService
from .tally_xml_builder import TallyXmlBuilder


# ======================================================================
# Helpers
# ======================================================================

def _feature_guard() -> Optional[Dict[str, Any]]:
    """Return an error dict if the ERP Bridge feature is disabled."""
    if not cfg.ENABLE_ERP_BRIDGE:
        return {
            "success": False,
            "error": (
                "ERP Bridge feature is disabled. "
                "Set ENABLE_ERP_BRIDGE=true to enable."
            ),
            "error_code": "FEATURE_DISABLED",
        }
    return None


def _file_checks(
    summary_path: str,
    items_path: str,
    validator: CsvSchemaValidator,
) -> Optional[Dict[str, Any]]:
    """Run file-level checks and return an error dict on failure."""
    for label, path in [("Summary", summary_path), ("Line Items", items_path)]:
        ok, errs = validator.validate_file_basics(path, label)
        if not ok:
            return {
                "success": False,
                "error": errs[0].message if errs else f"{label} file error",
                "error_code": (
                    "FILE_NOT_FOUND"
                    if "not found" in (errs[0].message if errs else "")
                    else "FILE_TOO_LARGE"
                    if "exceeds" in (errs[0].message if errs else "")
                    else "FILE_INVALID_TYPE"
                ),
            }
    return None


def _validation_errors_to_dicts(
    errors: List[ValidationError],
) -> List[Dict[str, Any]]:
    return [
        {
            "row": e.row,
            "column": e.column,
            "value": e.value,
            "message": e.message,
            "severity": e.severity,
        }
        for e in errors
    ]


# ======================================================================
# Tool 1: csv_to_tally
# ======================================================================

def csv_to_tally(
    summary_csv_path: str,
    items_csv_path: str,
    tally_company: Optional[str] = None,
    dry_run: bool = False,
    skip_duplicates: bool = True,
) -> Dict[str, Any]:
    """Process CSV invoice files and create vouchers in Tally ERP.

    Args:
        summary_csv_path: Path to the Summary/Header CSV file.
        items_csv_path: Path to the Line Items CSV file.
        tally_company: Tally company name (overrides env default).
        dry_run: If True, validate and generate XML but do not post.
        skip_duplicates: If True, skip invoices that already exist.

    Returns:
        Structured result dict.
    """
    # Feature flag guard
    guard = _feature_guard()
    if guard:
        return guard

    schema_validator = CsvSchemaValidator()

    # File-level checks
    file_err = _file_checks(summary_csv_path, items_csv_path, schema_validator)
    if file_err:
        return file_err

    # Schema validation - Summary
    summary_rows, summary_errors = schema_validator.validate_summary_csv(
        summary_csv_path
    )
    if summary_errors:
        has_errors = any(e.severity == "ERROR" for e in summary_errors)
        if has_errors:
            return {
                "success": False,
                "error": "CSV schema validation failed",
                "error_code": "SCHEMA_INVALID",
                "details": {
                    "summary_file_errors": _validation_errors_to_dicts(
                        summary_errors
                    ),
                    "items_file_errors": [],
                },
            }

    # Schema validation - Items
    items_rows, items_errors = schema_validator.validate_items_csv(items_csv_path)
    if items_errors:
        has_errors = any(e.severity == "ERROR" for e in items_errors)
        if has_errors:
            return {
                "success": False,
                "error": "CSV schema validation failed",
                "error_code": "SCHEMA_INVALID",
                "details": {
                    "summary_file_errors": _validation_errors_to_dicts(
                        summary_errors
                    ),
                    "items_file_errors": _validation_errors_to_dicts(
                        items_errors
                    ),
                },
            }

    # Load and join
    loader = CsvLoaderService()
    bundles, load_warnings = loader.load(summary_rows, items_rows)

    if load_warnings:
        has_errors = any(w.severity == "ERROR" for w in load_warnings)
        if has_errors:
            return {
                "success": False,
                "error": "CSV cross-file validation failed",
                "error_code": "VALIDATION_FAILED",
                "details": {
                    "cross_file_errors": _validation_errors_to_dicts(
                        load_warnings
                    ),
                },
            }

    if not bundles:
        return {
            "success": False,
            "error": "No valid invoices found in CSV files",
            "error_code": "VALIDATION_FAILED",
        }

    # Batch size check
    if len(bundles) > cfg.MAX_BATCH_SIZE:
        return {
            "success": False,
            "error": (
                f"Batch size {len(bundles)} exceeds maximum of "
                f"{cfg.MAX_BATCH_SIZE}"
            ),
            "error_code": "VALIDATION_FAILED",
        }

    # Build processor components
    connector = TallyConnector()
    xml_builder = TallyXmlBuilder()
    validator = ErpValidationEngine()
    audit_logger = ErpAuditLogger()
    lookup = (
        TallyLookupService(connector)
        if cfg.ENABLE_TALLY_LOOKUP
        else None
    )

    processor = ErpBatchProcessor(
        connector=connector,
        xml_builder=xml_builder,
        validator=validator,
        audit_logger=audit_logger,
        lookup_service=lookup,
    )

    # If not dry run, test Tally connectivity first
    if not dry_run:
        company = tally_company or cfg.TALLY_COMPANY_NAME
        conn_result = connector.test_connection(company)
        if not conn_result.connected:
            return {
                "success": False,
                "error": conn_result.error,
                "error_code": conn_result.error_code or "TALLY_CONNECTION_FAILED",
            }
        if company and not conn_result.company_found:
            return {
                "success": False,
                "error": conn_result.error,
                "error_code": "COMPANY_NOT_FOUND",
            }

    # Run batch
    source_file = os.path.basename(summary_csv_path)
    batch_result = processor.process_batch(
        bundles=bundles,
        company_name=tally_company,
        dry_run=dry_run,
        skip_duplicates=skip_duplicates,
        source_file=source_file,
    )

    return batch_result.to_dict()


# ======================================================================
# Tool 2: validate_csv
# ======================================================================

def validate_csv(
    summary_csv_path: str,
    items_csv_path: str,
) -> Dict[str, Any]:
    """Validate CSV files without processing.

    Returns a comprehensive validation report.
    """
    # Feature flag guard
    guard = _feature_guard()
    if guard:
        return guard

    report = CsvValidationReport()
    schema_validator = CsvSchemaValidator()

    # File-level checks
    for label, path, file_report in [
        ("Summary", summary_csv_path, report.summary_file),
        ("Line Items", items_csv_path, report.items_file),
    ]:
        file_report.path = os.path.basename(path)
        ok, errs = schema_validator.validate_file_basics(path, label)
        if not ok:
            report.valid = False
            report.error = errs[0].message if errs else f"{label} file error"
            report.error_code = "FILE_NOT_FOUND"
            return report.to_dict()

    # Schema validation
    summary_rows, summary_errors = schema_validator.validate_summary_csv(
        summary_csv_path
    )
    report.summary_file.rows = len(summary_rows)
    summary_error_rows = {e.row for e in summary_errors if e.severity == "ERROR"}
    report.summary_file.valid_rows = len(summary_rows) - len(summary_error_rows)
    report.summary_file.schema_errors = _validation_errors_to_dicts(summary_errors)

    # Voucher type breakdown
    vt_counts: Dict[str, int] = {}
    for row in summary_rows:
        vt = row.get("Voucher_Type", "Unknown")
        vt_counts[vt] = vt_counts.get(vt, 0) + 1
    report.summary_file.voucher_type_breakdown = vt_counts

    items_rows, items_errors = schema_validator.validate_items_csv(items_csv_path)
    report.items_file.rows = len(items_rows)
    items_error_rows = {e.row for e in items_errors if e.severity == "ERROR"}
    report.items_file.valid_rows = len(items_rows) - len(items_error_rows)
    report.items_file.schema_errors = _validation_errors_to_dicts(items_errors)

    if summary_errors or items_errors:
        has_any_error = any(
            e.severity == "ERROR" for e in summary_errors + items_errors
        )
        if has_any_error:
            report.valid = False

    # Load and join (for cross-file checks)
    loader = CsvLoaderService()
    bundles, load_warnings = loader.load(summary_rows, items_rows)

    for w in load_warnings:
        if "no matching line items" in w.message:
            report.cross_file_checks["invoices_without_items"].append(
                w.invoice_no
            )
        elif "does not exist in the Summary" in w.message:
            report.cross_file_checks["orphan_line_items"].append(w.invoice_no)

    if load_warnings:
        has_errors = any(w.severity == "ERROR" for w in load_warnings)
        if has_errors:
            report.valid = False

    # Business rule validation per bundle
    validator = ErpValidationEngine()
    from .gst_calculation import GSTCalculation
    gst = GSTCalculation()

    for bundle in bundles:
        val = validator.validate_bundle(bundle)
        for e in val.errors:
            report.business_rules["errors"].append(
                {"invoice_no": e.invoice_no or bundle.header.invoice_no,
                 "message": e.message}
            )
            report.valid = False
        for w in val.warnings:
            report.business_rules["warnings"].append(
                {"invoice_no": w.invoice_no or bundle.header.invoice_no,
                 "message": w.message}
            )

        # Cross-file reconciliation details
        hdr = bundle.header
        items_taxable = sum(
            gst.safe_decimal(li.taxable_value) for li in bundle.line_items
        )
        hdr_taxable = gst.safe_decimal(hdr.total_taxable_value)
        diff = abs(hdr_taxable - items_taxable)
        if diff > gst.rounding_tolerance:
            report.cross_file_checks["taxable_value_mismatches"].append({
                "invoice_no": hdr.invoice_no,
                "header_value": str(hdr_taxable),
                "items_sum": str(items_taxable),
                "difference": str(diff),
            })

        # GST amount mismatches
        for label_key, hdr_val, items_vals in [
            ("CGST", hdr.cgst_total,
             [li.cgst_amount for li in bundle.line_items]),
            ("SGST", hdr.sgst_total,
             [li.sgst_amount for li in bundle.line_items]),
            ("IGST", hdr.igst_total,
             [li.igst_amount for li in bundle.line_items]),
        ]:
            h = gst.safe_decimal(hdr_val)
            s = sum(gst.safe_decimal(v) for v in items_vals)
            d = abs(h - s)
            if d > gst.rounding_tolerance:
                report.cross_file_checks["gst_amount_mismatches"].append({
                    "invoice_no": hdr.invoice_no,
                    "tax_type": label_key,
                    "header_value": str(h),
                    "items_sum": str(s),
                    "difference": str(d),
                })

    return report.to_dict()


# ======================================================================
# Tool 3: tally_connection_test
# ======================================================================

def tally_connection_test(
    tally_host: Optional[str] = None,
    tally_port: Optional[int] = None,
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Test connectivity to Tally ERP.

    Returns structured connection test result.
    """
    # Feature flag guard
    guard = _feature_guard()
    if guard:
        return guard

    connector = TallyConnector(
        host=tally_host or cfg.TALLY_HOST,
        port=tally_port or cfg.TALLY_PORT,
    )

    result = connector.test_connection(
        company_name=company_name or cfg.TALLY_COMPANY_NAME
    )
    return result.to_dict()
