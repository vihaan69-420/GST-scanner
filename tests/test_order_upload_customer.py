"""
Order Upload – Customer Details Extraction & S.N Ordering Tests
===============================================================

Verifies:
- Customer header parsing (phone, Hindi name, English transliteration, date).
- extract_all_from_page returns both customer info and order lines.
- extract_all_from_pages merges customer info across multiple pages.
- Backward compatibility: text without headers still works.
- S.N sorting of output lines.
- PDF generation with customer_info parameter.
"""
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure temp dir exists for PDF output
TEMP_TEST_DIR = os.path.join(PROJECT_ROOT, "temp", "test_pdf_customer")
os.makedirs(TEMP_TEST_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# Sample OCR text fixtures
# ═══════════════════════════════════════════════════════════════

SAMPLE_OCR_WITH_HEADER = """\
PHONE\t7427096261
NAME\tराम कुमार (Ram Kumar)
DATE\t13/12/25
---
88\tTail Form Levo Grey\t2
89\tFull Kit Karizma White\t1
90\tFull Kit BS4 Deo Grey/Orange\t1
"""

SAMPLE_OCR_NO_HEADER = """\
88\tTail Form Levo Grey\t2
89\tFull Kit Karizma White\t1
"""

SAMPLE_OCR_PARTIAL_HEADER = """\
PHONE\t9876543210
NAME\tUNKNOWN
DATE\tUNKNOWN
---
1\tBody Kit Activa 3G Black\t3
"""

SAMPLE_OCR_UNSORTED = """\
PHONE\t1234567890
NAME\tसुरेश (Suresh)
DATE\t01/01/26
---
95\tTail Light Patti Activa 110 White\t5
95\tTail Light Patti Activa 110 Grey\t5
88\tTail Form Levo Grey\t2
100\tTail Panel Dream Yuga Black/Red\t4
90\tFull Kit BS4 Deo Grey/Orange\t1
"""

SAMPLE_OCR_PAGE2_HEADER = """\
PHONE\tUNKNOWN
NAME\tमोहन (Mohan)
DATE\t14/12/25
---
101\tHeadlight Visor Destini Black\t3
"""


class TestExtractCustomerInfo(unittest.TestCase):
    """Test extract_customer_info() function."""

    def test_full_header_extraction(self):
        from src.order_upload_extraction import extract_customer_info

        info = extract_customer_info(SAMPLE_OCR_WITH_HEADER)
        self.assertEqual(info["phone"], "7427096261")
        self.assertEqual(info["name"], "राम कुमार")
        self.assertEqual(info["name_en"], "Ram Kumar")
        self.assertEqual(info["date"], "13/12/25")

    def test_no_header_returns_empty(self):
        from src.order_upload_extraction import extract_customer_info

        info = extract_customer_info(SAMPLE_OCR_NO_HEADER)
        self.assertEqual(info["phone"], "")
        self.assertEqual(info["name"], "")
        self.assertEqual(info["name_en"], "")
        self.assertEqual(info["date"], "")

    def test_unknown_fields_treated_as_empty(self):
        from src.order_upload_extraction import extract_customer_info

        info = extract_customer_info(SAMPLE_OCR_PARTIAL_HEADER)
        self.assertEqual(info["phone"], "9876543210")
        self.assertEqual(info["name"], "")
        self.assertEqual(info["name_en"], "")
        self.assertEqual(info["date"], "")

    def test_empty_text(self):
        from src.order_upload_extraction import extract_customer_info

        info = extract_customer_info("")
        self.assertEqual(info, {"phone": "", "name": "", "name_en": "", "date": ""})

    def test_header_with_hindi_only_name(self):
        """When Gemini returns name without English transliteration."""
        from src.order_upload_extraction import extract_customer_info

        ocr_text = "PHONE\t9999999999\nNAME\tविकास\nDATE\t05/01/26\n---\n1\tPart\t1"
        info = extract_customer_info(ocr_text)
        self.assertEqual(info["name"], "विकास")
        self.assertEqual(info["name_en"], "")


class TestExtractAllFromPage(unittest.TestCase):
    """Test extract_all_from_page() function."""

    def test_returns_customer_info_and_lines(self):
        from src.order_upload_extraction import extract_all_from_page

        info, lines = extract_all_from_page(1, SAMPLE_OCR_WITH_HEADER)
        self.assertEqual(info["phone"], "7427096261")
        self.assertEqual(info["name"], "राम कुमार")
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0].sn, 88)
        self.assertEqual(lines[0].part_name, "Tail Form Levo Grey")
        self.assertEqual(lines[0].qty, 2)

    def test_backward_compat_no_header(self):
        """Text without --- separator should still parse lines correctly."""
        from src.order_upload_extraction import extract_all_from_page

        info, lines = extract_all_from_page(1, SAMPLE_OCR_NO_HEADER)
        # No header → all fields empty
        self.assertEqual(info["phone"], "")
        self.assertEqual(info["name"], "")
        # Lines should still be extracted
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].sn, 88)


class TestExtractAllFromPages(unittest.TestCase):
    """Test extract_all_from_pages() multi-page merge."""

    def test_merge_customer_info_first_wins(self):
        """Customer info from first page with non-empty values wins."""
        from src.order_upload_extraction import extract_all_from_pages

        pages = [
            {"page_no": 1, "text": SAMPLE_OCR_WITH_HEADER},
            {"page_no": 2, "text": SAMPLE_OCR_PAGE2_HEADER},
        ]
        customer_info, lines = extract_all_from_pages(pages)

        # Phone from page 1 (7427096261), not page 2 (UNKNOWN → "")
        self.assertEqual(customer_info["phone"], "7427096261")
        # Name from page 1 (राम कुमार)
        self.assertEqual(customer_info["name"], "राम कुमार")
        self.assertEqual(customer_info["name_en"], "Ram Kumar")
        # Date from page 1 (13/12/25)
        self.assertEqual(customer_info["date"], "13/12/25")

        # Lines from both pages should be present
        self.assertEqual(len(lines), 4)  # 3 from page 1 + 1 from page 2

    def test_merge_fills_from_later_page(self):
        """If page 1 has UNKNOWN phone but page 2 has it, page 2 value is used."""
        from src.order_upload_extraction import extract_all_from_pages

        pages = [
            {"page_no": 1, "text": SAMPLE_OCR_PARTIAL_HEADER},  # phone=9876543210, name=UNKNOWN
            {"page_no": 2, "text": SAMPLE_OCR_PAGE2_HEADER},     # phone=UNKNOWN, name=Mohan
        ]
        customer_info, lines = extract_all_from_pages(pages)

        self.assertEqual(customer_info["phone"], "9876543210")  # from page 1
        self.assertEqual(customer_info["name"], "मोहन")  # from page 2
        self.assertEqual(customer_info["name_en"], "Mohan")  # from page 2
        self.assertEqual(customer_info["date"], "14/12/25")  # from page 2


class TestSNSorting(unittest.TestCase):
    """Test that lines are correctly sorted by S.N."""

    def test_sort_by_sn(self):
        """Lines should be sortable by S.N with same-S.N lines preserved."""
        from src.order_upload_extraction import extract_all_from_pages

        pages = [{"page_no": 1, "text": SAMPLE_OCR_UNSORTED}]
        _, lines = extract_all_from_pages(pages)

        # Sort by S.N (as the orchestrator does)
        sorted_lines = sorted(
            lines, key=lambda x: int(x.get("sn", 0) or 0)
        )

        sns = [l["sn"] for l in sorted_lines]
        self.assertEqual(sns, [88, 90, 95, 95, 100])

    def test_same_sn_preserved(self):
        """Multiple lines with the same S.N should all appear after sorting."""
        from src.order_upload_extraction import extract_all_from_pages

        pages = [{"page_no": 1, "text": SAMPLE_OCR_UNSORTED}]
        _, lines = extract_all_from_pages(pages)

        sorted_lines = sorted(
            lines, key=lambda x: int(x.get("sn", 0) or 0)
        )

        sn95 = [l for l in sorted_lines if l["sn"] == 95]
        self.assertEqual(len(sn95), 2)
        names = {l["part_name"] for l in sn95}
        self.assertIn("Tail Light Patti Activa 110 White", names)
        self.assertIn("Tail Light Patti Activa 110 Grey", names)


class TestPdfWithCustomerInfo(unittest.TestCase):
    """Test PDF generation with customer_info parameter."""

    def setUp(self):
        for f in os.listdir(TEMP_TEST_DIR):
            if f.endswith(".pdf"):
                os.remove(os.path.join(TEMP_TEST_DIR, f))

    @patch("src.config.ENABLE_ORDER_UPLOAD", True)
    def test_pdf_with_customer_info(self):
        """PDF should be generated successfully with customer_info."""
        from src.order_upload_pdf import generate_order_pdf

        lines = [
            {"sn": "88", "part_name": "Tail Form Levo Grey", "part_number": "TF-001",
             "price": "150", "qty": "2", "line_total": "300", "match_type": "exact"},
            {"sn": "89", "part_name": "Full Kit Karizma White", "part_number": "FK-001",
             "price": "500", "qty": "1", "line_total": "500", "match_type": "fuzzy"},
        ]
        customer_info = {
            "phone": "7427096261",
            "name": "राम कुमार",
            "name_en": "Ram Kumar",
            "date": "13/12/25",
        }

        pdf_path = generate_order_pdf(
            matched_lines=lines,
            grand_total=800.0,
            order_id="CUST_TEST_001",
            output_dir=TEMP_TEST_DIR,
            customer_info=customer_info,
        )
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 500)

    @patch("src.config.ENABLE_ORDER_UPLOAD", True)
    def test_pdf_without_customer_info(self):
        """PDF should still work when customer_info is None (backward compat)."""
        from src.order_upload_pdf import generate_order_pdf

        lines = [
            {"sn": "1", "part_name": "Test Part", "part_number": "TP-001",
             "price": "100", "qty": "2", "line_total": "200", "match_type": "exact"},
        ]

        pdf_path = generate_order_pdf(
            matched_lines=lines,
            grand_total=200.0,
            order_id="NO_CUST",
            output_dir=TEMP_TEST_DIR,
        )
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 500)

    @patch("src.config.ENABLE_ORDER_UPLOAD", True)
    def test_pdf_with_empty_customer_info(self):
        """PDF should handle customer_info with all empty fields gracefully."""
        from src.order_upload_pdf import generate_order_pdf

        lines = [
            {"sn": "1", "part_name": "Test Part", "part_number": "TP-001",
             "price": "100", "qty": "2", "line_total": "200", "match_type": "exact"},
        ]
        customer_info = {"phone": "", "name": "", "name_en": "", "date": ""}

        pdf_path = generate_order_pdf(
            matched_lines=lines,
            grand_total=200.0,
            order_id="EMPTY_CUST",
            output_dir=TEMP_TEST_DIR,
            customer_info=customer_info,
        )
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 500)

    @patch("src.config.ENABLE_ORDER_UPLOAD", True)
    def test_pdf_with_partial_customer_info(self):
        """PDF should handle customer_info with only some fields populated."""
        from src.order_upload_pdf import generate_order_pdf

        lines = [
            {"sn": "1", "part_name": "Test Part", "part_number": "TP-001",
             "price": "100", "qty": "2", "line_total": "200", "match_type": "exact"},
        ]
        customer_info = {"phone": "9999999999", "name": "", "name_en": "", "date": "01/01/26"}

        pdf_path = generate_order_pdf(
            matched_lines=lines,
            grand_total=200.0,
            order_id="PARTIAL_CUST",
            output_dir=TEMP_TEST_DIR,
            customer_info=customer_info,
        )
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 500)


class TestConfigCustomerColumns(unittest.TestCase):
    """Verify customer columns are present in ORDER_SUMMARY_COLUMNS."""

    def test_customer_name_column(self):
        from src import config
        self.assertIn("customer_name", config.ORDER_SUMMARY_COLUMNS)

    def test_customer_phone_column(self):
        from src import config
        self.assertIn("customer_phone", config.ORDER_SUMMARY_COLUMNS)

    def test_order_date_column(self):
        from src import config
        self.assertIn("order_date", config.ORDER_SUMMARY_COLUMNS)

    def test_columns_order(self):
        """customer_name, customer_phone, order_date should come after timestamp."""
        from src import config
        cols = config.ORDER_SUMMARY_COLUMNS
        ts_idx = cols.index("timestamp")
        cn_idx = cols.index("customer_name")
        cp_idx = cols.index("customer_phone")
        od_idx = cols.index("order_date")
        self.assertGreater(cn_idx, ts_idx)
        self.assertGreater(cp_idx, ts_idx)
        self.assertGreater(od_idx, ts_idx)


if __name__ == "__main__":
    unittest.main()
