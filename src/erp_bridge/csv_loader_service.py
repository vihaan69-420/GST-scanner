"""
CSV Loader Service
Parses validated CSV files into structured InvoiceBundle objects,
joining Summary rows with their corresponding Line Items.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from .models import (
    InvoiceBundle,
    InvoiceHeader,
    LineItem,
    ValidationError,
)


class CsvLoaderService:
    """Parse validated CSV rows into InvoiceBundle objects."""

    def load(
        self,
        summary_rows: List[Dict[str, str]],
        items_rows: List[Dict[str, str]],
    ) -> Tuple[List[InvoiceBundle], List[ValidationError]]:
        """Build InvoiceBundle list from pre-validated CSV rows.

        Args:
            summary_rows: Rows from the Summary CSV (list of dicts).
            items_rows: Rows from the Line Items CSV (list of dicts).

        Returns:
            (bundles, warnings) - bundles keyed by Invoice_No, plus any
            warnings about orphan items or missing items.
        """
        warnings: List[ValidationError] = []

        # --- Build headers keyed by Invoice_No ---
        headers_map: Dict[str, InvoiceHeader] = {}
        seen_invoice_nos: Dict[str, int] = {}  # track duplicates

        for idx, row in enumerate(summary_rows, start=1):
            inv_no = row.get("Invoice_No", "").strip()
            if inv_no in seen_invoice_nos:
                warnings.append(
                    ValidationError(
                        row=idx,
                        column="Invoice_No",
                        value=inv_no,
                        message=(
                            f"Duplicate Invoice_No '{inv_no}' in Summary CSV "
                            f"(first seen at row {seen_invoice_nos[inv_no]})"
                        ),
                        severity="ERROR",
                        invoice_no=inv_no,
                    )
                )
                continue

            seen_invoice_nos[inv_no] = idx
            headers_map[inv_no] = self._row_to_header(row, idx)

        # --- Build line items grouped by Invoice_No ---
        items_map: Dict[str, List[LineItem]] = defaultdict(list)

        for idx, row in enumerate(items_rows, start=1):
            inv_no = row.get("Invoice_No", "").strip()
            items_map[inv_no].append(self._row_to_item(row, idx))

        # --- Join and produce bundles (maintain Summary order) ---
        bundles: List[InvoiceBundle] = []
        used_item_keys: set = set()

        for inv_no in headers_map:
            header = headers_map[inv_no]
            items = items_map.get(inv_no, [])

            if not items:
                warnings.append(
                    ValidationError(
                        row=header.row_number,
                        column="Invoice_No",
                        value=inv_no,
                        message=f"Invoice '{inv_no}' in Summary has no matching line items",
                        severity="ERROR",
                        invoice_no=inv_no,
                    )
                )

            # Sort items by Line_No
            items.sort(key=lambda li: li.line_no)

            bundles.append(InvoiceBundle(header=header, line_items=items))
            used_item_keys.add(inv_no)

        # --- Detect orphan line items ---
        orphan_keys = set(items_map.keys()) - used_item_keys
        for orphan_inv in sorted(orphan_keys):
            warnings.append(
                ValidationError(
                    column="Invoice_No",
                    value=orphan_inv,
                    message=(
                        f"Line items reference Invoice_No '{orphan_inv}' "
                        "which does not exist in the Summary CSV"
                    ),
                    severity="ERROR",
                    invoice_no=orphan_inv,
                )
            )

        return bundles, warnings

    # ------------------------------------------------------------------
    # Internal converters
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_header(row: Dict[str, str], row_number: int) -> InvoiceHeader:
        """Convert a CSV row dict into an InvoiceHeader dataclass."""
        return InvoiceHeader(
            voucher_type=row.get("Voucher_Type", "").strip(),
            invoice_no=row.get("Invoice_No", "").strip(),
            invoice_date=row.get("Invoice_Date", "").strip(),
            party_name=row.get("Party_Name", "").strip(),
            party_gstin=row.get("Party_GSTIN", "").strip(),
            party_state_code=row.get("Party_State_Code", "").strip(),
            place_of_supply=row.get("Place_Of_Supply", "").strip(),
            sales_ledger=row.get("Sales_Ledger", "").strip(),
            invoice_value=row.get("Invoice_Value", "").strip(),
            total_taxable_value=row.get("Total_Taxable_Value", "").strip(),
            cgst_total=row.get("CGST_Total", "").strip(),
            sgst_total=row.get("SGST_Total", "").strip(),
            igst_total=row.get("IGST_Total", "").strip(),
            cess_total=row.get("Cess_Total", "").strip(),
            round_off=row.get("Round_Off", "").strip(),
            narration=row.get("Narration", "").strip(),
            reference_no=row.get("Reference_No", "").strip(),
            reference_date=row.get("Reference_Date", "").strip(),
            reverse_charge=row.get("Reverse_Charge", "N").strip().upper() or "N",
            company_name=row.get("Company_Name", "").strip(),
            raw_row=dict(row),
            row_number=row_number,
        )

    @staticmethod
    def _row_to_item(row: Dict[str, str], row_number: int) -> LineItem:
        """Convert a CSV row dict into a LineItem dataclass."""
        line_no_raw = row.get("Line_No", "0").strip()
        try:
            line_no = int(line_no_raw)
        except ValueError:
            line_no = 0

        return LineItem(
            invoice_no=row.get("Invoice_No", "").strip(),
            line_no=line_no,
            item_description=row.get("Item_Description", "").strip(),
            hsn_sac=row.get("HSN_SAC", "").strip(),
            qty=row.get("Qty", "").strip(),
            uom=row.get("UOM", "").strip(),
            rate=row.get("Rate", "").strip(),
            discount_percent=row.get("Discount_Percent", "").strip(),
            taxable_value=row.get("Taxable_Value", "").strip(),
            gst_rate=row.get("GST_Rate", "").strip(),
            cgst_rate=row.get("CGST_Rate", "").strip(),
            cgst_amount=row.get("CGST_Amount", "").strip(),
            sgst_rate=row.get("SGST_Rate", "").strip(),
            sgst_amount=row.get("SGST_Amount", "").strip(),
            igst_rate=row.get("IGST_Rate", "").strip(),
            igst_amount=row.get("IGST_Amount", "").strip(),
            cess_amount=row.get("Cess_Amount", "").strip(),
            stock_item_name=row.get("Stock_Item_Name", "").strip(),
            godown=row.get("Godown", "").strip(),
            raw_row=dict(row),
            row_number=row_number,
        )
