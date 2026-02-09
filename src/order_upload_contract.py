"""
Order Upload & OCR – Golden Fixture Contract (Phase 2)
======================================================

This module captures the *contract* for the future Order Upload & OCR
feature, without implementing OCR, parsing, or Google Sheets writes yet.

Key points:
- Does NOT modify or import existing GST invoice logic.
- Used only by dev/tests to enforce invariants.
- All future Order Upload code must honour this contract.
"""

from typing import List, Dict, Final

# Mandatory output table structure for every extracted order line
MANDATORY_COLUMNS: Final[List[str]] = [
    "S.N",
    "PART NAME",
    "PART NUMBER",
    "PRICE",
    "QTY",
    "LINE TOTAL",
]


def is_valid_output_row(row: Dict) -> bool:
    """
    Validate that a row conforms to the mandatory schema.

    This is intentionally strict and small: it checks *shape* only.
    Future phases will add richer validation (duplicates, matching, etc.).
    """
    if not isinstance(row, dict):
        return False
    for col in MANDATORY_COLUMNS:
        if col not in row:
            return False
    return True


# Golden fixture expectations for the handwritten sample image
# ------------------------------------------------------------
#
# The previously provided handwritten order image is the authoritative
# reference. For Phase 2 we only lock in the *known-truth* line:
#
#   S.N 3  →  "iSmart 110 Blue"  →  QTY = 5 (from circled number only)
#
# Notes:
# - Quantity comes ONLY from circled numbers.
# - Do NOT infer quantity from parentheses or inline digits.
# - Do NOT hallucinate colours/models not present in the text.

GOLDEN_SN3_SN: Final[int] = 3
GOLDEN_SN3_PART_NAME: Final[str] = "iSmart 110 Blue"
GOLDEN_SN3_QTY: Final[int] = 5


def golden_sn3_row_template() -> Dict:
    """
    Template row for S.N 3 based on the golden fixture.

    Price / part-number / line total will be filled in later phases
    (price list matching and calculations).
    """
    return {
        "S.N": GOLDEN_SN3_SN,
        "PART NAME": GOLDEN_SN3_PART_NAME,
        "PART NUMBER": None,
        "PRICE": None,
        "QTY": GOLDEN_SN3_QTY,
        "LINE TOTAL": None,
    }


