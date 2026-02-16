"""
ERP Bridge Data Models
Dataclasses for structured data passing between ERP Bridge components.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Invoice data models
# ---------------------------------------------------------------------------

@dataclass
class LineItem:
    """A single line item from the Line Items CSV."""
    invoice_no: str = ""
    line_no: int = 0
    item_description: str = ""
    hsn_sac: str = ""
    qty: str = ""
    uom: str = ""
    rate: str = ""
    discount_percent: str = ""
    taxable_value: str = ""
    gst_rate: str = ""
    cgst_rate: str = ""
    cgst_amount: str = ""
    sgst_rate: str = ""
    sgst_amount: str = ""
    igst_rate: str = ""
    igst_amount: str = ""
    cess_amount: str = ""
    stock_item_name: str = ""
    godown: str = ""

    # Metadata (not from CSV)
    raw_row: Dict[str, str] = field(default_factory=dict)
    row_number: int = 0  # 1-based row in CSV file


@dataclass
class InvoiceHeader:
    """Header-level invoice data from the Summary CSV."""
    voucher_type: str = ""
    invoice_no: str = ""
    invoice_date: str = ""
    party_name: str = ""
    party_gstin: str = ""
    party_state_code: str = ""
    place_of_supply: str = ""
    sales_ledger: str = ""
    invoice_value: str = ""
    total_taxable_value: str = ""
    cgst_total: str = ""
    sgst_total: str = ""
    igst_total: str = ""
    cess_total: str = ""
    round_off: str = ""
    narration: str = ""
    reference_no: str = ""
    reference_date: str = ""
    reverse_charge: str = "N"
    company_name: str = ""

    # Metadata (not from CSV)
    raw_row: Dict[str, str] = field(default_factory=dict)
    row_number: int = 0  # 1-based row in CSV file


@dataclass
class InvoiceBundle:
    """An invoice header paired with its line items."""
    header: InvoiceHeader = field(default_factory=InvoiceHeader)
    line_items: List[LineItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation models
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    """A single validation error or warning."""
    row: int = 0
    column: str = ""
    value: str = ""
    message: str = ""
    severity: str = "ERROR"  # ERROR or WARNING
    invoice_no: str = ""


@dataclass
class ValidationResult:
    """Aggregated validation result for one or more invoices."""
    valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    def add_error(
        self,
        message: str,
        row: int = 0,
        column: str = "",
        value: str = "",
        invoice_no: str = "",
    ) -> None:
        self.valid = False
        self.errors.append(
            ValidationError(
                row=row,
                column=column,
                value=value,
                message=message,
                severity="ERROR",
                invoice_no=invoice_no,
            )
        )

    def add_warning(
        self,
        message: str,
        row: int = 0,
        column: str = "",
        value: str = "",
        invoice_no: str = "",
    ) -> None:
        self.warnings.append(
            ValidationError(
                row=row,
                column=column,
                value=value,
                message=message,
                severity="WARNING",
                invoice_no=invoice_no,
            )
        )

    @property
    def status(self) -> str:
        if self.errors:
            return "ERROR"
        if self.warnings:
            return "WARNING"
        return "OK"


# ---------------------------------------------------------------------------
# Processing result models
# ---------------------------------------------------------------------------

@dataclass
class InvoiceResult:
    """Result of processing a single invoice."""
    invoice_no: str = ""
    voucher_type: str = ""
    status: str = "PENDING"  # SUCCESS, FAILED, SKIPPED, VALID, INVALID
    tally_voucher_id: str = ""
    tally_voucher_number: str = ""
    error: str = ""
    reason: str = ""
    processing_time_seconds: float = 0.0
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    xml_preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "invoice_no": self.invoice_no,
            "voucher_type": self.voucher_type,
            "status": self.status,
            "processing_time_seconds": round(self.processing_time_seconds, 2),
        }
        if self.tally_voucher_id:
            d["tally_voucher_id"] = self.tally_voucher_id
        if self.tally_voucher_number:
            d["tally_voucher_number"] = self.tally_voucher_number
        if self.error:
            d["error"] = self.error
        if self.reason:
            d["reason"] = self.reason
        if self.validation_errors:
            d["validation_errors"] = self.validation_errors
        if self.validation_warnings:
            d["validation_warnings"] = self.validation_warnings
        if self.xml_preview:
            d["xml_preview"] = self.xml_preview
        return d


@dataclass
class BatchResult:
    """Result of a batch processing run."""
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    dry_run: bool = False
    total_invoices: int = 0
    successful: int = 0
    failed: int = 0
    skipped_duplicates: int = 0
    processing_time_seconds: float = 0.0
    results: List[InvoiceResult] = field(default_factory=list)
    audit_log_path: str = ""
    error: str = ""
    error_code: str = ""

    @property
    def success(self) -> bool:
        return not self.error_code

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "success": self.success,
            "batch_id": self.batch_id,
            "dry_run": self.dry_run,
            "timestamp": self.timestamp,
        }
        if self.error:
            d["error"] = self.error
            d["error_code"] = self.error_code
        else:
            d["summary"] = {
                "total_invoices": self.total_invoices,
                "successful": self.successful,
                "failed": self.failed,
                "skipped_duplicates": self.skipped_duplicates,
                "processing_time_seconds": round(self.processing_time_seconds, 2),
            }
            d["results"] = [r.to_dict() for r in self.results]
            if self.audit_log_path:
                d["audit_log_path"] = self.audit_log_path
        return d


# ---------------------------------------------------------------------------
# Tally response models
# ---------------------------------------------------------------------------

@dataclass
class TallyResponse:
    """Parsed response from a Tally HTTP request."""
    success: bool = False
    created: int = 0
    altered: int = 0
    deleted: int = 0
    voucher_id: str = ""
    voucher_number: str = ""
    errors: List[str] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "created": self.created,
            "altered": self.altered,
            "deleted": self.deleted,
            "voucher_id": self.voucher_id,
            "voucher_number": self.voucher_number,
            "errors": self.errors,
        }


@dataclass
class TallyConnectionResult:
    """Result of a Tally connection test."""
    connected: bool = False
    tally_host: str = ""
    tally_port: int = 0
    response_time_ms: float = 0.0
    tally_version: str = ""
    companies: List[str] = field(default_factory=list)
    target_company: str = ""
    company_found: bool = False
    error: str = ""
    error_code: str = ""
    troubleshooting: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.error_code

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "success": self.success,
            "connected": self.connected,
            "tally_host": self.tally_host,
            "tally_port": self.tally_port,
        }
        if self.connected:
            d["response_time_ms"] = round(self.response_time_ms, 1)
            if self.tally_version:
                d["tally_version"] = self.tally_version
            d["companies"] = self.companies
            d["target_company"] = self.target_company
            d["company_found"] = self.company_found
        if self.error:
            d["error"] = self.error
            d["error_code"] = self.error_code
        if self.troubleshooting:
            d["troubleshooting"] = self.troubleshooting
        return d


# ---------------------------------------------------------------------------
# CSV validation report models
# ---------------------------------------------------------------------------

@dataclass
class FileValidationReport:
    """Validation report for a single CSV file."""
    path: str = ""
    rows: int = 0
    valid_rows: int = 0
    schema_errors: List[Dict[str, Any]] = field(default_factory=list)
    voucher_type_breakdown: Dict[str, int] = field(default_factory=dict)


@dataclass
class CsvValidationReport:
    """Full validation report for a CSV pair."""
    valid: bool = True
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    summary_file: FileValidationReport = field(default_factory=FileValidationReport)
    items_file: FileValidationReport = field(default_factory=FileValidationReport)
    business_rules: Dict[str, List[Dict[str, str]]] = field(
        default_factory=lambda: {"errors": [], "warnings": []}
    )
    cross_file_checks: Dict[str, List[Any]] = field(
        default_factory=lambda: {
            "orphan_line_items": [],
            "invoices_without_items": [],
            "taxable_value_mismatches": [],
            "gst_amount_mismatches": [],
        }
    )
    error: str = ""
    error_code: str = ""

    @property
    def success(self) -> bool:
        return not self.error_code

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"success": self.success}
        if self.error:
            d["error"] = self.error
            d["error_code"] = self.error_code
            return d
        d["valid"] = self.valid
        d["timestamp"] = self.timestamp
        d["summary_file"] = {
            "path": self.summary_file.path,
            "rows": self.summary_file.rows,
            "valid_rows": self.summary_file.valid_rows,
            "schema_errors": self.summary_file.schema_errors,
        }
        if self.summary_file.voucher_type_breakdown:
            d["summary_file"]["voucher_type_breakdown"] = (
                self.summary_file.voucher_type_breakdown
            )
        d["items_file"] = {
            "path": self.items_file.path,
            "rows": self.items_file.rows,
            "valid_rows": self.items_file.valid_rows,
            "schema_errors": self.items_file.schema_errors,
        }
        d["business_rules"] = self.business_rules
        d["cross_file_checks"] = self.cross_file_checks
        return d
