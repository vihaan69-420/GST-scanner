"""
Phase 3 – Extraction tests (OCR text → structured lines)
========================================================

These tests operate on *text fixtures* only – they do not call Gemini or
touch images. They enforce:
- Golden S.N 3 behaviour: "iSmart 110 Blue" with qty 5.
- Multi-colour splitting (e.g., Duet Grey / Duet White).
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


GOLDEN_PAGE_TEXT = """
1 Sai- Activa 3G B1/wree 2
2 Sai- ~ Blue 1
3 Sai- iSmart 110 Blue 5
11 Sai- Jupiter Blewerk 5 old Access white 5
19 Sai- Duet Grey 4 White 4
"""


class TestOrderUploadExtraction(unittest.TestCase):
    def test_sn3_ismart_110_blue_qty5(self):
        from src.order_upload_extraction import extract_lines_from_pages

        pages = [{"page_no": 1, "text": GOLDEN_PAGE_TEXT}]
        lines = extract_lines_from_pages(pages)

        # Find S.N 3
        sn3 = [l for l in lines if l.get("sn") == 3]
        self.assertEqual(len(sn3), 1, "Expected exactly one line with S.N 3")
        row = sn3[0]
        self.assertEqual(row["part_name"], "iSmart 110 Blue")
        self.assertEqual(row["qty"], 5)
        self.assertEqual(row["source_page"], 1)

    def test_multi_colour_splitting_for_duet(self):
        from src.order_upload_extraction import extract_lines_from_pages

        pages = [{"page_no": 1, "text": GOLDEN_PAGE_TEXT}]
        lines = extract_lines_from_pages(pages)

        duet = [l for l in lines if l.get("sn") == 19]
        # Expect two lines: Duet Grey (4) and Duet White (4)
        self.assertEqual(len(duet), 2, "Expected two lines for S.N 19 (multi-colour)")

        names = {l["part_name"]: l["qty"] for l in duet}
        # Allow minor case differences in part names
        # but quantities must be exact (4 each)
        grey_key = next(k for k in names.keys() if "duet" in k.lower() and "grey" in k.lower())
        white_key = next(k for k in names.keys() if "duet" in k.lower() and "white" in k.lower())
        self.assertEqual(names[grey_key], 4)
        self.assertEqual(names[white_key], 4)


if __name__ == "__main__":
    unittest.main()

