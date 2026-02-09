"""
Phase 2 – Golden Fixture & Schema Tests
======================================

These tests enforce:
- The mandatory output table structure for Order Upload lines.
- The golden fixture expectation for S.N 3 from the handwritten sample:
  S.N 3 → "iSmart 110 Blue" → QTY 5.

No OCR, parsing, or Google Sheets access is performed here.
"""
import os
import sys
import unittest

# Ensure src/ is importable when running tests from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestOrderUploadContract(unittest.TestCase):
    def test_mandatory_columns_and_row_shape(self):
        from src.order_upload_contract import MANDATORY_COLUMNS, is_valid_output_row

        # Expected columns in the exact order
        self.assertEqual(
            MANDATORY_COLUMNS,
            ["S.N", "PART NAME", "PART NUMBER", "PRICE", "QTY", "LINE TOTAL"],
        )

        # A minimal valid row must have all mandatory keys
        sample_row = {
            "S.N": 1,
            "PART NAME": "Activa 3G B1/Grey",
            "PART NUMBER": None,
            "PRICE": None,
            "QTY": 2,
            "LINE TOTAL": None,
        }
        self.assertTrue(is_valid_output_row(sample_row))

        # Missing any column -> invalid
        bad_row = {"S.N": 1, "PART NAME": "Missing fields"}
        self.assertFalse(is_valid_output_row(bad_row))

    def test_golden_sn3_expectations(self):
        from src.order_upload_contract import (
            GOLDEN_SN3_SN,
            GOLDEN_SN3_PART_NAME,
            GOLDEN_SN3_QTY,
            golden_sn3_row_template,
            is_valid_output_row,
        )

        # Ground truth from the handwritten image
        self.assertEqual(GOLDEN_SN3_SN, 3)
        self.assertEqual(GOLDEN_SN3_PART_NAME, "iSmart 110 Blue")
        self.assertEqual(GOLDEN_SN3_QTY, 5)

        row = golden_sn3_row_template()
        self.assertTrue(is_valid_output_row(row))
        self.assertEqual(row["S.N"], 3)
        self.assertEqual(row["PART NAME"], "iSmart 110 Blue")
        self.assertEqual(row["QTY"], 5)

        # Price / part-number / line total are intentionally unset in Phase 2
        self.assertIsNone(row["PART NUMBER"])
        self.assertIsNone(row["PRICE"])
        self.assertIsNone(row["LINE TOTAL"])


if __name__ == "__main__":
    unittest.main()

