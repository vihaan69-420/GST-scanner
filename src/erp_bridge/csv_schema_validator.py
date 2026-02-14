"""
CSV Schema Validator
Validates that uploaded CSV files conform to the expected column schema
and basic data-type rules before any business logic runs.
"""

from __future__ import annotations

import csv
import io
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from . import erp_config as cfg
from .models import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
_HSN_RE = re.compile(r"^\d{4}(\d{2})?(\d{2})?$")


def _is_decimal(value: str) -> bool:
    """Return True if value can be interpreted as a decimal number."""
    if not value:
        return True  # empty treated as 0
    try:
        float(value.replace(",", ""))
        return True
    except ValueError:
        return False


def _is_integer(value: str) -> bool:
    if not value:
        return True
    try:
        int(value)
        return True
    except ValueError:
        return False


def _is_date(value: str) -> bool:
    if not value:
        return True
    if not _DATE_RE.match(value):
        return False
    parts = value.split("/")
    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    if month < 1 or month > 12:
        return False
    if day < 1 or day > 31:
        return False
    return True


def _is_boolean(value: str) -> bool:
    return value.upper() in ("Y", "N", "")


# ---------------------------------------------------------------------------
# Column rule definitions
# ---------------------------------------------------------------------------

# Each rule is a dict:  { "type": str, "required": bool }
# type is one of: string, decimal, integer, date, boolean, gstin, state_code,
#                  voucher_type, gst_rate, hsn, uom

SUMMARY_COLUMN_RULES: List[Dict[str, Any]] = [
    {"name": "Voucher_Type",       "type": "voucher_type", "required": True},
    {"name": "Invoice_No",         "type": "string",       "required": True,  "max_len": 50},
    {"name": "Invoice_Date",       "type": "date",         "required": True},
    {"name": "Party_Name",         "type": "string",       "required": True,  "max_len": 200},
    {"name": "Party_GSTIN",        "type": "gstin",        "required": False},
    {"name": "Party_State_Code",   "type": "state_code",   "required": True},
    {"name": "Place_Of_Supply",    "type": "state_code",   "required": True},
    {"name": "Sales_Ledger",       "type": "string",       "required": True,  "max_len": 200},
    {"name": "Invoice_Value",      "type": "decimal",      "required": True},
    {"name": "Total_Taxable_Value","type": "decimal",      "required": True},
    {"name": "CGST_Total",         "type": "decimal",      "required": False},
    {"name": "SGST_Total",         "type": "decimal",      "required": False},
    {"name": "IGST_Total",         "type": "decimal",      "required": False},
    {"name": "Cess_Total",         "type": "decimal",      "required": False},
    {"name": "Round_Off",          "type": "decimal",      "required": False},
    {"name": "Narration",          "type": "string",       "required": False, "max_len": 500},
    {"name": "Reference_No",       "type": "string",       "required": False, "max_len": 50},
    {"name": "Reference_Date",     "type": "date",         "required": False},
    {"name": "Reverse_Charge",     "type": "boolean",      "required": False},
    {"name": "Company_Name",       "type": "string",       "required": False, "max_len": 200},
]

ITEMS_COLUMN_RULES: List[Dict[str, Any]] = [
    {"name": "Invoice_No",         "type": "string",   "required": True,  "max_len": 50},
    {"name": "Line_No",            "type": "integer",  "required": True},
    {"name": "Item_Description",   "type": "string",   "required": True,  "max_len": 500},
    {"name": "HSN_SAC",            "type": "hsn",      "required": True},
    {"name": "Qty",                "type": "decimal",  "required": False},
    {"name": "UOM",                "type": "uom",      "required": False},
    {"name": "Rate",               "type": "decimal",  "required": False},
    {"name": "Discount_Percent",   "type": "decimal",  "required": False},
    {"name": "Taxable_Value",      "type": "decimal",  "required": True},
    {"name": "GST_Rate",           "type": "gst_rate", "required": True},
    {"name": "CGST_Rate",          "type": "decimal",  "required": False},
    {"name": "CGST_Amount",        "type": "decimal",  "required": False},
    {"name": "SGST_Rate",          "type": "decimal",  "required": False},
    {"name": "SGST_Amount",        "type": "decimal",  "required": False},
    {"name": "IGST_Rate",          "type": "decimal",  "required": False},
    {"name": "IGST_Amount",        "type": "decimal",  "required": False},
    {"name": "Cess_Amount",        "type": "decimal",  "required": False},
    {"name": "Stock_Item_Name",    "type": "string",   "required": False, "max_len": 200},
    {"name": "Godown",             "type": "string",   "required": False, "max_len": 200},
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class CsvSchemaValidator:
    """Validate CSV file structure and field data types."""

    def validate_file_basics(
        self,
        file_path: str,
        label: str = "CSV",
    ) -> Tuple[bool, List[ValidationError]]:
        """Check file existence, extension, and size.

        Returns (ok, errors).
        """
        errors: List[ValidationError] = []

        if not os.path.exists(file_path):
            errors.append(
                ValidationError(
                    message=f"{label} file not found: {file_path}",
                    severity="ERROR",
                )
            )
            return False, errors

        if not file_path.lower().endswith(".csv"):
            errors.append(
                ValidationError(
                    message=f"{label} file must be a .csv file, got: {os.path.basename(file_path)}",
                    severity="ERROR",
                )
            )
            return False, errors

        file_size = os.path.getsize(file_path)
        if file_size > cfg.MAX_FILE_SIZE_BYTES:
            size_mb = round(file_size / (1024 * 1024), 1)
            errors.append(
                ValidationError(
                    message=(
                        f"{label} file exceeds maximum size of "
                        f"{cfg.MAX_FILE_SIZE_MB} MB: {os.path.basename(file_path)} "
                        f"({size_mb} MB)"
                    ),
                    severity="ERROR",
                )
            )
            return False, errors

        if file_size == 0:
            errors.append(
                ValidationError(
                    message=f"{label} file is empty: {file_path}",
                    severity="ERROR",
                )
            )
            return False, errors

        return True, errors

    # ------------------------------------------------------------------

    def validate_summary_csv(
        self,
        file_path: str,
    ) -> Tuple[List[Dict[str, str]], List[ValidationError]]:
        """Parse and validate the Summary CSV.

        Returns (rows, errors).  *rows* is a list of ordered-dicts if the
        file is structurally valid; otherwise an empty list.
        """
        return self._validate_csv(
            file_path,
            expected_columns=cfg.SUMMARY_CSV_COLUMNS,
            column_rules=SUMMARY_COLUMN_RULES,
            label="Summary",
        )

    def validate_items_csv(
        self,
        file_path: str,
    ) -> Tuple[List[Dict[str, str]], List[ValidationError]]:
        """Parse and validate the Line Items CSV.

        Returns (rows, errors).
        """
        return self._validate_csv(
            file_path,
            expected_columns=cfg.ITEMS_CSV_COLUMNS,
            column_rules=ITEMS_COLUMN_RULES,
            label="Line Items",
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate_csv(
        self,
        file_path: str,
        expected_columns: List[str],
        column_rules: List[Dict[str, Any]],
        label: str,
    ) -> Tuple[List[Dict[str, str]], List[ValidationError]]:
        errors: List[ValidationError] = []
        rows: List[Dict[str, str]] = []

        try:
            raw = self._read_file(file_path)
        except Exception as exc:
            errors.append(
                ValidationError(message=f"Cannot read {label} file: {exc}")
            )
            return rows, errors

        reader = csv.DictReader(io.StringIO(raw))
        if reader.fieldnames is None:
            errors.append(
                ValidationError(message=f"{label} CSV has no header row")
            )
            return rows, errors

        # Normalise header names
        actual_headers = [h.strip() for h in reader.fieldnames]

        # Check required columns present
        missing = [c for c in expected_columns if c not in actual_headers]
        if missing:
            errors.append(
                ValidationError(
                    message=(
                        f"{label} CSV missing required columns: "
                        + ", ".join(missing)
                    ),
                )
            )
            return rows, errors

        # Read data rows
        row_count = 0
        for raw_row in reader:
            row_count += 1
            if row_count > cfg.MAX_ROWS:
                errors.append(
                    ValidationError(
                        row=row_count,
                        message=f"{label} CSV exceeds maximum of {cfg.MAX_ROWS} rows",
                    )
                )
                break

            # Strip values
            row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items()}

            # Skip completely empty rows
            if all(v == "" for v in row.values()):
                continue

            # Per-field validation
            for rule in column_rules:
                col = rule["name"]
                value = row.get(col, "")
                field_errors = self._validate_field(value, rule, row_count, label)
                errors.extend(field_errors)

            rows.append(row)

        if not rows and not errors:
            errors.append(
                ValidationError(message=f"{label} CSV contains no data rows")
            )

        return rows, errors

    # ------------------------------------------------------------------

    def _validate_field(
        self,
        value: str,
        rule: Dict[str, Any],
        row: int,
        file_label: str,
    ) -> List[ValidationError]:
        """Validate a single field value against its rule."""
        col = rule["name"]
        errors: List[ValidationError] = []

        # Required check
        if rule.get("required") and not value:
            errors.append(
                ValidationError(
                    row=row,
                    column=col,
                    value=value,
                    message=f"Required field '{col}' is empty",
                    severity="ERROR",
                )
            )
            return errors

        # If empty and not required, skip type checks
        if not value:
            return errors

        ftype = rule.get("type", "string")

        if ftype == "decimal":
            if not _is_decimal(value):
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=f"'{col}' must be a decimal number, got: {value}",
                    )
                )

        elif ftype == "integer":
            if not _is_integer(value):
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=f"'{col}' must be an integer, got: {value}",
                    )
                )

        elif ftype == "date":
            if not _is_date(value):
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=f"'{col}' must be in DD/MM/YYYY format, got: {value}",
                    )
                )

        elif ftype == "boolean":
            if not _is_boolean(value):
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=f"'{col}' must be Y or N, got: {value}",
                    )
                )

        elif ftype == "gstin":
            if not _GSTIN_RE.match(value.upper()):
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=f"Invalid GSTIN format: must be 15 characters, got: {value}",
                    )
                )

        elif ftype == "state_code":
            if value not in cfg.VALID_STATE_CODES:
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=f"Invalid state code '{value}' in '{col}'",
                    )
                )

        elif ftype == "voucher_type":
            if value not in cfg.VALID_VOUCHER_TYPES:
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=(
                            f"Invalid voucher type '{value}'; "
                            f"must be one of: {', '.join(sorted(cfg.VALID_VOUCHER_TYPES))}"
                        ),
                    )
                )

        elif ftype == "gst_rate":
            if not _is_decimal(value):
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=f"'{col}' must be a decimal number, got: {value}",
                    )
                )
            else:
                # Normalise to check against known rates
                try:
                    nval = str(float(value))
                    # Allow the numeric value if it matches any known rate
                    known = {float(r) for r in cfg.VALID_GST_RATES}
                    if float(value) not in known:
                        errors.append(
                            ValidationError(
                                row=row, column=col, value=value,
                                message=(
                                    f"Invalid GST rate '{value}'; "
                                    "must be one of: 0, 0.25, 3, 5, 12, 18, 28"
                                ),
                            )
                        )
                except ValueError:
                    pass  # already caught above

        elif ftype == "hsn":
            if not _HSN_RE.match(value):
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=f"Invalid HSN/SAC code '{value}': must be 4, 6, or 8 digits",
                    )
                )

        elif ftype == "uom":
            if value.upper() not in cfg.VALID_UOM_CODES:
                errors.append(
                    ValidationError(
                        row=row, column=col, value=value,
                        message=f"Invalid UOM code '{value}' in '{col}'",
                    )
                )

        # Max length check for strings
        max_len = rule.get("max_len")
        if max_len and len(value) > max_len:
            errors.append(
                ValidationError(
                    row=row, column=col, value=value[:30] + "...",
                    message=f"'{col}' exceeds max length of {max_len} characters",
                    severity="WARNING",
                )
            )

        return errors

    # ------------------------------------------------------------------

    @staticmethod
    def _read_file(file_path: str) -> str:
        """Read file content, handling BOM."""
        with open(file_path, "r", encoding="utf-8-sig") as fh:
            return fh.read()
