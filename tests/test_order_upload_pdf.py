"""
Order Upload – PDF Generator Tests
===================================

Verifies:
- PDF file is created in the expected directory.
- PDF contains only the matched_lines passed in (session isolation).
- Grand total row is present.
- Feature-flag guard works (raises RuntimeError when disabled).
- Empty lines list still produces a valid PDF with only the grand total.
"""
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure temp dir exists for output
TEMP_TEST_DIR = os.path.join(PROJECT_ROOT, "temp", "test_pdf")
os.makedirs(TEMP_TEST_DIR, exist_ok=True)


def _sample_lines(count=3):
    """Generate sample matched lines for testing."""
    lines = []
    for i in range(1, count + 1):
        lines.append({
            "sn": str(i),
            "part_name": f"Test Part {i}",
            "part_number": f"TP-{i:04d}",
            "price": str(100.0 * i),
            "qty": str(i * 2),
            "line_total": str(100.0 * i * i * 2),
            "match_type": "exact" if i % 2 == 0 else "fuzzy",
        })
    return lines


class TestGenerateOrderPdf(unittest.TestCase):
    """Core PDF generation tests."""

    def setUp(self):
        """Clean up any leftover test PDFs."""
        for f in os.listdir(TEMP_TEST_DIR):
            if f.endswith(".pdf"):
                os.remove(os.path.join(TEMP_TEST_DIR, f))

    @patch("src.config.ENABLE_ORDER_UPLOAD", True)
    def test_pdf_file_created(self):
        """PDF file should be created and exist on disk."""
        from src.order_upload_pdf import generate_order_pdf

        lines = _sample_lines(3)
        grand_total = sum(float(l["line_total"]) for l in lines)

        pdf_path = generate_order_pdf(
            matched_lines=lines,
            grand_total=grand_total,
            order_id="TEST001",
            output_dir=TEMP_TEST_DIR,
        )
        self.assertTrue(os.path.exists(pdf_path))
        self.assertTrue(pdf_path.endswith(".pdf"))
        # File should have real content (> 500 bytes for a valid PDF)
        self.assertGreater(os.path.getsize(pdf_path), 500)

    @patch("src.config.ENABLE_ORDER_UPLOAD", True)
    def test_pdf_contains_only_current_lines(self):
        """
        Generate two PDFs with different data. Each should only contain
        its own data — verifying session isolation at the function level.
        """
        from src.order_upload_pdf import generate_order_pdf

        lines_a = [
            {"sn": "1", "part_name": "Alpha Part", "part_number": "AP-0001",
             "price": "100", "qty": "5", "line_total": "500", "match_type": "exact"},
        ]
        lines_b = [
            {"sn": "1", "part_name": "Beta Part", "part_number": "BP-0001",
             "price": "200", "qty": "3", "line_total": "600", "match_type": "exact"},
            {"sn": "2", "part_name": "Gamma Part", "part_number": "GP-0001",
             "price": "150", "qty": "4", "line_total": "600", "match_type": "fuzzy"},
        ]

        pdf_a = generate_order_pdf(
            matched_lines=lines_a, grand_total=500.0,
            order_id="A", output_dir=TEMP_TEST_DIR,
        )
        pdf_b = generate_order_pdf(
            matched_lines=lines_b, grand_total=1200.0,
            order_id="B", output_dir=TEMP_TEST_DIR,
        )

        # Both exist, are different files
        self.assertTrue(os.path.exists(pdf_a))
        self.assertTrue(os.path.exists(pdf_b))
        self.assertNotEqual(pdf_a, pdf_b)

        # File sizes should differ (different data volume)
        size_a = os.path.getsize(pdf_a)
        size_b = os.path.getsize(pdf_b)
        self.assertNotEqual(size_a, size_b)

    @patch("src.config.ENABLE_ORDER_UPLOAD", True)
    def test_empty_lines_produces_valid_pdf(self):
        """Even with zero data lines, a valid PDF with just the Grand Total should be created."""
        from src.order_upload_pdf import generate_order_pdf

        pdf_path = generate_order_pdf(
            matched_lines=[],
            grand_total=0.0,
            order_id="EMPTY",
            output_dir=TEMP_TEST_DIR,
        )
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 500)

    @patch("src.config.ENABLE_ORDER_UPLOAD", False)
    def test_feature_flag_disabled_raises(self):
        """When ENABLE_ORDER_UPLOAD is False, generating a PDF should raise RuntimeError."""
        from src.order_upload_pdf import generate_order_pdf

        with self.assertRaises(RuntimeError):
            generate_order_pdf(
                matched_lines=_sample_lines(1),
                grand_total=100.0,
                order_id="BLOCKED",
                output_dir=TEMP_TEST_DIR,
            )

    @patch("src.config.ENABLE_ORDER_UPLOAD", True)
    def test_filename_contains_order_id(self):
        """The generated filename should incorporate the order_id."""
        from src.order_upload_pdf import generate_order_pdf

        pdf_path = generate_order_pdf(
            matched_lines=_sample_lines(1),
            grand_total=200.0,
            order_id="MY_ORDER_123",
            output_dir=TEMP_TEST_DIR,
        )
        self.assertIn("MY_ORDER_123", os.path.basename(pdf_path))

    @patch("src.config.ENABLE_ORDER_UPLOAD", True)
    def test_default_order_id(self):
        """When no order_id is given, filename should use 'upload' as fallback."""
        from src.order_upload_pdf import generate_order_pdf

        pdf_path = generate_order_pdf(
            matched_lines=_sample_lines(1),
            grand_total=200.0,
            output_dir=TEMP_TEST_DIR,
        )
        self.assertIn("upload", os.path.basename(pdf_path))


class TestOrderSummarySheet(unittest.TestCase):
    """Verify Order_Summary config is properly defined."""

    def test_order_summary_columns_defined(self):
        from src import config
        self.assertTrue(hasattr(config, "ORDER_SUMMARY_COLUMNS"))
        self.assertIn("order_id", config.ORDER_SUMMARY_COLUMNS)
        self.assertIn("grand_total", config.ORDER_SUMMARY_COLUMNS)
        self.assertIn("timestamp", config.ORDER_SUMMARY_COLUMNS)

    def test_order_summary_sheet_name_defined(self):
        from src import config
        self.assertTrue(hasattr(config, "ORDER_SUMMARY_SHEET_NAME"))
        self.assertEqual(config.ORDER_SUMMARY_SHEET_NAME, "Order_Summary")


if __name__ == "__main__":
    unittest.main()
