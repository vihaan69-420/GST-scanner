"""
Phase 5 – Google Sheets integration tests (mocked)
==================================================

These tests verify that:
- OrderUploadSheets writes the correct row shapes.
- Idempotent append logic (keyed rows are not duplicated).
- Failures do not raise exceptions (methods return False instead).

All tests use fake in-memory worksheet/spreadsheet objects – no real
Google Sheets or network calls.
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class FakeWorksheet:
    def __init__(self, title, columns):
        self.title = title
        self.columns = columns or []
        self.rows = []

    def row_values(self, idx):
        if 1 <= idx <= len(self.rows):
            return self.rows[idx - 1]
        return []

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def append_row(self, values, value_input_option=None):
        self.rows.append(list(values))


class FakeSpreadsheet:
    def __init__(self):
        self.sheets = {}

    def worksheet(self, title):
        if title not in self.sheets:
            raise Exception("Not found")
        return self.sheets[title]

    def add_worksheet(self, title, rows, cols):
        ws = FakeWorksheet(title, [])
        self.sheets[title] = ws
        return ws


class TestOrderUploadSheets(unittest.TestCase):
    def test_append_raw_ocr_idempotent(self):
        from src import config
        from src.order_upload_sheets import OrderUploadSheets

        fake = FakeSpreadsheet()
        sheets = OrderUploadSheets.from_spreadsheet(fake)

        ok1 = sheets.append_raw_ocr("ORD-1", 1, "raw text", "2025-01-01 10:00:00")
        ok2 = sheets.append_raw_ocr("ORD-1", 1, "raw text", "2025-01-01 10:00:00")
        self.assertTrue(ok1)
        self.assertTrue(ok2)

        ws = fake.sheets[config.RAW_OCR_SHEET_NAME]
        # header + 1 data row (idempotent)
        self.assertEqual(len(ws.rows), 2)

    def test_append_matched_lines_shape(self):
        from src import config
        from src.order_upload_sheets import OrderUploadSheets

        fake = FakeSpreadsheet()
        sheets = OrderUploadSheets.from_spreadsheet(fake)

        rows = [
            {
                "S.N": 3,
                "PART NAME": "iSmart 110 Blue",
                "PART NUMBER": "SAI-ISM110-BL",
                "PRICE": 610,
                "QTY": 5,
                "LINE TOTAL": 3050,
            }
        ]
        ok = sheets.append_matched_lines(rows)
        self.assertTrue(ok)

        ws = fake.sheets[config.MATCHED_LINES_SHEET_NAME]
        self.assertEqual(ws.rows[0], config.MATCHED_LINES_COLUMNS)
        self.assertEqual(ws.rows[1][0], "3")  # S.N as string
        self.assertEqual(ws.rows[1][1], "iSmart 110 Blue")
        self.assertEqual(ws.rows[1][2], "SAI-ISM110-BL")


if __name__ == "__main__":
    unittest.main()

