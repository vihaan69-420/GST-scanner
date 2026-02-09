"""
Phase 4 – Duplicate & Validation Tests
======================================

These tests enforce the dedupe rules:
- Same S.N + same normalized PART NAME → skipped.
- Same normalized PART NAME (any S.N) → skipped.
- Same PART NUMBER → skipped.
- Same model, different colour → allowed.
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestOrderUploadDedupe(unittest.TestCase):
    def test_same_sn_and_name_skipped(self):
        from src.order_upload_dedupe import dedupe_lines

        lines = [
            {"sn": 3, "part_name": "iSmart 110 Blue", "qty": 5, "source_page": 1},
            {"sn": 3, "part_name": "iSmart 110 Blue", "qty": 5, "source_page": 1},
        ]
        kept, skipped = dedupe_lines(lines)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(skipped), 1)
        self.assertIn("DUP_SN", skipped[0]["dup_reasons"])

    def test_same_name_different_sn_skipped(self):
        from src.order_upload_dedupe import dedupe_lines

        lines = [
            {"sn": 5, "part_name": "Activa 3G Blue", "qty": 2, "source_page": 1},
            {"sn": 6, "part_name": "Activa 3G Blue", "qty": 1, "source_page": 1},
        ]
        kept, skipped = dedupe_lines(lines)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(skipped), 1)
        self.assertIn("DUP_PART_NAME", skipped[0]["dup_reasons"])

    def test_same_part_number_skipped(self):
        from src.order_upload_dedupe import dedupe_lines

        lines = [
            {
                "sn": 10,
                "part_name": "Shine BS6 BL/Red Visor",
                "qty": 5,
                "source_page": 1,
                "part_number": "SAI-SH-BS6-V",
            },
            {
                "sn": 11,
                "part_name": "Shine BS6 BL/Red Visor (duplicate)",
                "qty": 3,
                "source_page": 1,
                "part_number": "SAI-SH-BS6-V",
            },
        ]
        kept, skipped = dedupe_lines(lines)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(skipped), 1)
        self.assertIn("DUP_PART_NUMBER", skipped[0]["dup_reasons"])

    def test_same_model_different_colour_allowed(self):
        from src.order_upload_dedupe import dedupe_lines

        lines = [
            {"sn": 19, "part_name": "Duet Grey", "qty": 4, "source_page": 1},
            {"sn": 19, "part_name": "Duet White", "qty": 4, "source_page": 1},
        ]
        kept, skipped = dedupe_lines(lines)
        # Both colours should be kept (different PART NAMEs)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(skipped), 0)


if __name__ == "__main__":
    unittest.main()

