"""
ERP Bridge Validation Engine
Applies business rules and GST compliance checks to parsed InvoiceBundles.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Tuple

from . import erp_config as cfg
from .gst_calculation import GSTCalculation
from .models import InvoiceBundle, ValidationResult


class ErpValidationEngine:
    """Validate InvoiceBundles against business rules and GST logic."""

    def __init__(self) -> None:
        self.gst = GSTCalculation(
            rounding_tolerance=cfg.ROUNDING_TOLERANCE,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_bundle(self, bundle: InvoiceBundle) -> ValidationResult:
        """Run all validations on a single InvoiceBundle.

        Returns a ValidationResult with errors and warnings.
        """
        result = ValidationResult()
        hdr = bundle.header
        items = bundle.line_items
        inv = hdr.invoice_no

        # 1. Mandatory header fields (beyond schema)
        self._check_header_mandatory(hdr, result)

        # 2. Tax type consistency
        errs, warns = self.gst.verify_tax_type_consistency(
            hdr.party_state_code,
            hdr.place_of_supply,
            hdr.cgst_total,
            hdr.sgst_total,
            hdr.igst_total,
        )
        for e in errs:
            result.add_error(e, invoice_no=inv)
        for w in warns:
            result.add_warning(w, invoice_no=inv)

        # 3. Invoice value reconciliation
        errs, warns = self.gst.verify_invoice_value(
            hdr.invoice_value,
            hdr.total_taxable_value,
            hdr.cgst_total,
            hdr.sgst_total,
            hdr.igst_total,
            hdr.cess_total,
            hdr.round_off,
            tolerance=cfg.INVOICE_VALUE_TOLERANCE,
        )
        for e in errs:
            result.add_error(e, invoice_no=inv)
        for w in warns:
            result.add_warning(w, invoice_no=inv)

        # 4. Taxable value reconciliation (header vs line items sum)
        items_taxable = sum(
            self.gst.safe_decimal(li.taxable_value) for li in items
        )
        errs, warns = self.gst.verify_taxable_total(
            hdr.total_taxable_value,
            items_taxable,
        )
        for e in errs:
            result.add_error(e, invoice_no=inv)
        for w in warns:
            result.add_warning(w, invoice_no=inv)

        # 5. GST totals reconciliation
        items_cgst = sum(self.gst.safe_decimal(li.cgst_amount) for li in items)
        items_sgst = sum(self.gst.safe_decimal(li.sgst_amount) for li in items)
        items_igst = sum(self.gst.safe_decimal(li.igst_amount) for li in items)

        errs, warns = self.gst.verify_gst_totals(
            hdr.cgst_total,
            hdr.sgst_total,
            hdr.igst_total,
            items_cgst,
            items_sgst,
            items_igst,
        )
        for e in errs:
            result.add_error(e, invoice_no=inv)
        for w in warns:
            result.add_warning(w, invoice_no=inv)

        # 6. Per-line-item GST math verification
        is_intra = self.gst.is_intra_state(
            hdr.party_state_code, hdr.place_of_supply
        )
        for li in items:
            errs, warns = self.gst.verify_line_item(
                li.taxable_value,
                li.gst_rate,
                li.cgst_amount,
                li.sgst_amount,
                li.igst_amount,
                is_intra,
            )
            for e in errs:
                result.add_error(
                    f"Line {li.line_no}: {e}", invoice_no=inv
                )
            for w in warns:
                result.add_warning(
                    f"Line {li.line_no}: {w}", invoice_no=inv
                )

        # 7. Line-item tax type consistency with each other
        self._check_line_tax_consistency(items, is_intra, inv, result)

        # 8. Sales Order specific checks
        if hdr.voucher_type == "Sales Order":
            self._check_sales_order(items, inv, result)

        # 9. Line number sequence check
        self._check_line_sequence(items, inv, result)

        # 10. Positive amount checks
        self._check_positive_amounts(hdr, items, inv, result)

        return result

    def validate_bundles(
        self, bundles: List[InvoiceBundle]
    ) -> List[Tuple[InvoiceBundle, ValidationResult]]:
        """Validate a list of bundles and return paired results."""
        return [(b, self.validate_bundle(b)) for b in bundles]

    # ------------------------------------------------------------------
    # Private checks
    # ------------------------------------------------------------------

    def _check_header_mandatory(
        self,
        hdr,
        result: ValidationResult,
    ) -> None:
        """Additional mandatory field checks beyond schema validation."""
        inv = hdr.invoice_no

        # Conditional: intra-state needs CGST+SGST
        is_intra = self.gst.is_intra_state(
            hdr.party_state_code, hdr.place_of_supply
        )
        cgst = self.gst.safe_decimal(hdr.cgst_total)
        sgst = self.gst.safe_decimal(hdr.sgst_total)
        igst = self.gst.safe_decimal(hdr.igst_total)
        taxable = self.gst.safe_decimal(hdr.total_taxable_value)

        # If taxable value is > 0, at least some GST should be present
        # (unless exempt / nil rated — we just warn)
        if taxable > 0 and cgst == 0 and sgst == 0 and igst == 0:
            result.add_warning(
                "Taxable value > 0 but all GST amounts are zero "
                "(nil-rated or exempt?)",
                invoice_no=inv,
            )

    def _check_line_tax_consistency(
        self,
        items,
        is_intra: bool,
        inv: str,
        result: ValidationResult,
    ) -> None:
        """All line items should use the same tax type."""
        has_cgst_sgst = False
        has_igst = False

        for li in items:
            cgst = self.gst.safe_decimal(li.cgst_amount)
            sgst = self.gst.safe_decimal(li.sgst_amount)
            igst = self.gst.safe_decimal(li.igst_amount)

            if cgst > 0 or sgst > 0:
                has_cgst_sgst = True
            if igst > 0:
                has_igst = True

        if has_cgst_sgst and has_igst:
            result.add_error(
                "Line items mix CGST/SGST and IGST within the same invoice",
                invoice_no=inv,
            )

    def _check_sales_order(
        self,
        items,
        inv: str,
        result: ValidationResult,
    ) -> None:
        """Sales Order requires Stock_Item_Name on each line."""
        for li in items:
            if not li.stock_item_name:
                result.add_error(
                    f"Line {li.line_no}: Sales Order requires Stock_Item_Name",
                    invoice_no=inv,
                )

    def _check_line_sequence(
        self,
        items,
        inv: str,
        result: ValidationResult,
    ) -> None:
        """Line numbers should be sequential starting from 1."""
        if not items:
            return
        for idx, li in enumerate(items, start=1):
            if li.line_no != idx:
                result.add_warning(
                    f"Line_No sequence gap: expected {idx}, got {li.line_no}",
                    invoice_no=inv,
                )
                break  # one warning is enough

    def _check_positive_amounts(
        self,
        hdr,
        items,
        inv: str,
        result: ValidationResult,
    ) -> None:
        """Taxable values and invoice value should be positive."""
        inv_val = self.gst.safe_decimal(hdr.invoice_value)
        if inv_val <= 0:
            result.add_error(
                f"Invoice_Value must be positive, got {inv_val}",
                invoice_no=inv,
            )

        taxable = self.gst.safe_decimal(hdr.total_taxable_value)
        if taxable <= 0:
            result.add_error(
                f"Total_Taxable_Value must be positive, got {taxable}",
                invoice_no=inv,
            )

        for li in items:
            tv = self.gst.safe_decimal(li.taxable_value)
            if tv <= 0:
                result.add_warning(
                    f"Line {li.line_no}: Taxable_Value is {tv}",
                    invoice_no=inv,
                )
