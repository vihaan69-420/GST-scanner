"""
GST Calculation Adapter
Isolated GST calculation and cross-verification logic for the ERP Bridge.

Replicates the validation patterns from the existing GST Scanner's
GSTValidator (src/parsing/gst_validator.py) without importing from it.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple


class GSTCalculation:
    """GST calculation utilities and cross-verification."""

    def __init__(
        self,
        rounding_tolerance: str = "0.50",
        critical_percentage: str = "1.0",
    ):
        self.rounding_tolerance = Decimal(rounding_tolerance)
        self.critical_percentage = Decimal(critical_percentage)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def safe_decimal(value: str) -> Decimal:
        """Convert a string to Decimal, returning 0 on failure."""
        if not value or not value.strip():
            return Decimal("0")
        try:
            cleaned = value.replace(",", "").replace("\u20b9", "").strip()
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return Decimal("0")

    @staticmethod
    def is_intra_state(party_state_code: str, place_of_supply: str) -> bool:
        """Return True when supply is intra-state."""
        return (
            bool(party_state_code)
            and bool(place_of_supply)
            and party_state_code.strip() == place_of_supply.strip()
        )

    def expected_cgst_sgst(
        self, taxable_value: Decimal, gst_rate: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Calculate expected CGST and SGST from taxable value and GST rate."""
        half_rate = gst_rate / 2
        amount = (taxable_value * half_rate / 100).quantize(Decimal("0.01"))
        return amount, amount

    def expected_igst(
        self, taxable_value: Decimal, gst_rate: Decimal
    ) -> Decimal:
        """Calculate expected IGST from taxable value and GST rate."""
        return (taxable_value * gst_rate / 100).quantize(Decimal("0.01"))

    # ------------------------------------------------------------------
    # Line-item level cross-verification
    # ------------------------------------------------------------------

    def verify_line_item(
        self,
        taxable_value: str,
        gst_rate: str,
        cgst_amount: str,
        sgst_amount: str,
        igst_amount: str,
        is_intra: bool,
    ) -> Tuple[List[str], List[str]]:
        """Verify GST amounts on a single line item.

        Returns (errors, warnings).
        """
        errors: List[str] = []
        warnings: List[str] = []

        tv = self.safe_decimal(taxable_value)
        rate = self.safe_decimal(gst_rate)
        cgst = self.safe_decimal(cgst_amount)
        sgst = self.safe_decimal(sgst_amount)
        igst = self.safe_decimal(igst_amount)

        if tv == 0 or rate == 0:
            return errors, warnings

        if is_intra:
            exp_half = (tv * rate / 200).quantize(Decimal("0.01"))
            cgst_diff = abs(cgst - exp_half)
            sgst_diff = abs(sgst - exp_half)

            if cgst_diff > self.rounding_tolerance:
                warnings.append(
                    f"CGST mismatch: expected {exp_half}, got {cgst} "
                    f"(diff {cgst_diff})"
                )
            if sgst_diff > self.rounding_tolerance:
                warnings.append(
                    f"SGST mismatch: expected {exp_half}, got {sgst} "
                    f"(diff {sgst_diff})"
                )
            if igst > 0:
                errors.append(
                    f"Intra-state line has IGST={igst}; expected 0"
                )
        else:
            exp_igst = (tv * rate / 100).quantize(Decimal("0.01"))
            igst_diff = abs(igst - exp_igst)

            if igst_diff > self.rounding_tolerance:
                warnings.append(
                    f"IGST mismatch: expected {exp_igst}, got {igst} "
                    f"(diff {igst_diff})"
                )
            if cgst > 0 or sgst > 0:
                errors.append(
                    f"Inter-state line has CGST={cgst}/SGST={sgst}; expected 0"
                )

        return errors, warnings

    # ------------------------------------------------------------------
    # Header-level reconciliation
    # ------------------------------------------------------------------

    def verify_taxable_total(
        self,
        header_total: str,
        line_items_sum: Decimal,
    ) -> Tuple[List[str], List[str]]:
        """Verify header taxable total equals sum of line item taxable values."""
        errors: List[str] = []
        warnings: List[str] = []

        header = self.safe_decimal(header_total)
        diff = abs(header - line_items_sum)

        if diff > self.rounding_tolerance:
            pct = (diff / header * 100) if header > 0 else Decimal("0")
            if pct > self.critical_percentage:
                errors.append(
                    f"Taxable value mismatch: header={header}, "
                    f"line items sum={line_items_sum} (diff={diff}, {pct:.2f}%)"
                )
            else:
                warnings.append(
                    f"Minor taxable value difference: {diff} (likely rounding)"
                )

        return errors, warnings

    def verify_gst_totals(
        self,
        header_cgst: str,
        header_sgst: str,
        header_igst: str,
        items_cgst_sum: Decimal,
        items_sgst_sum: Decimal,
        items_igst_sum: Decimal,
    ) -> Tuple[List[str], List[str]]:
        """Verify header GST totals equal line item GST sums."""
        errors: List[str] = []
        warnings: List[str] = []

        for label, header_val, items_sum in [
            ("CGST", header_cgst, items_cgst_sum),
            ("SGST", header_sgst, items_sgst_sum),
            ("IGST", header_igst, items_igst_sum),
        ]:
            h = self.safe_decimal(header_val)
            diff = abs(h - items_sum)
            if diff > self.rounding_tolerance:
                pct = (diff / h * 100) if h > 0 else Decimal("0")
                if pct > self.critical_percentage:
                    errors.append(
                        f"{label} total mismatch: header={h}, "
                        f"line items sum={items_sum} (diff={diff})"
                    )
                else:
                    warnings.append(
                        f"Minor {label} total difference: {diff} (likely rounding)"
                    )

        return errors, warnings

    def verify_invoice_value(
        self,
        invoice_value: str,
        total_taxable: str,
        cgst_total: str,
        sgst_total: str,
        igst_total: str,
        cess_total: str,
        round_off: str,
        tolerance: str = "1.00",
    ) -> Tuple[List[str], List[str]]:
        """Verify Invoice_Value = Taxable + GST + Cess + RoundOff."""
        errors: List[str] = []
        warnings: List[str] = []

        inv_val = self.safe_decimal(invoice_value)
        expected = (
            self.safe_decimal(total_taxable)
            + self.safe_decimal(cgst_total)
            + self.safe_decimal(sgst_total)
            + self.safe_decimal(igst_total)
            + self.safe_decimal(cess_total)
            + self.safe_decimal(round_off)
        )
        diff = abs(inv_val - expected)
        tol = Decimal(tolerance)

        if diff > tol:
            errors.append(
                f"Invoice value mismatch: stated={inv_val}, "
                f"calculated={expected} (diff={diff})"
            )
        elif diff > Decimal("0"):
            warnings.append(
                f"Minor invoice value difference: {diff} (within tolerance)"
            )

        return errors, warnings

    def verify_tax_type_consistency(
        self,
        party_state_code: str,
        place_of_supply: str,
        cgst_total: str,
        sgst_total: str,
        igst_total: str,
    ) -> Tuple[List[str], List[str]]:
        """Verify tax type matches supply type (intra vs inter)."""
        errors: List[str] = []
        warnings: List[str] = []

        intra = self.is_intra_state(party_state_code, place_of_supply)
        cgst = self.safe_decimal(cgst_total)
        sgst = self.safe_decimal(sgst_total)
        igst = self.safe_decimal(igst_total)

        if intra:
            if igst > 0:
                errors.append(
                    f"Intra-state supply (state {party_state_code}) "
                    f"should not have IGST ({igst})"
                )
            if cgst == 0 and sgst == 0 and igst == 0:
                # Could be exempt / nil rated – just warn
                pass
        else:
            if cgst > 0 or sgst > 0:
                errors.append(
                    f"Inter-state supply ({party_state_code} → {place_of_supply}) "
                    f"should not have CGST ({cgst}) / SGST ({sgst})"
                )

        # Both IGST and CGST+SGST at the same time is always wrong
        if igst > 0 and (cgst > 0 or sgst > 0):
            errors.append(
                f"Invoice has both IGST ({igst}) and CGST/SGST "
                f"({cgst}/{sgst}) — invalid"
            )

        return errors, warnings
