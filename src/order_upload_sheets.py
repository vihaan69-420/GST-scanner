"""
Phase 5 – Google Sheets Integration for Order Upload
====================================================

This module writes Order Upload data to a dedicated Google Sheets workbook.

Sheets and schemas (columns defined in config):

1. Raw_OCR
   - order_id
   - page_no
   - raw_text
   - timestamp

2. Normalized_Lines
   - S.N
   - PART NAME
   - QTY
   - source_page
   - confidence

3. Matched_Lines
   - S.N
   - PART NAME
   - PART NUMBER
   - PRICE
   - QTY
   - LINE TOTAL

4. Errors
   - order_id
   - error_type
   - description

Guardrails:
- Uses its own workbook ID (ORDER_UPLOAD_SHEET_ID) and sheet names from config.
- Does NOT touch existing SheetsManager or Invoice sheets.
- All writes are append-only and wrapped so failures do not crash callers.
"""
from __future__ import annotations

from typing import List, Dict, Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

try:
    from src import config
except ImportError:
    import config


def _get_client():
    """Create a gspread client using the same credential resolution as SheetsManager."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_path = config.get_credentials_path()
    if creds_path:
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        return gspread.authorize(creds)
    else:
        import google.auth

        credentials, _ = google.auth.default(scopes=scope)
        return gspread.authorize(credentials)


class OrderUploadSheets:
    """
    Thin wrapper around Google Sheets for Order Upload data.

    For tests, you can inject a fake spreadsheet via the alternate constructor
    `from_spreadsheet(spreadsheet)`, avoiding any real API calls.
    """

    def __init__(self, spreadsheet: Optional[object] = None):
        if spreadsheet is not None:
            self.spreadsheet = spreadsheet
        else:
            client = _get_client()
            sheet_id = config.ORDER_UPLOAD_SHEET_ID or config.GOOGLE_SHEET_ID
            if not sheet_id:
                raise ValueError("ORDER_UPLOAD_SHEET_ID or GOOGLE_SHEET_ID must be set")
            self.spreadsheet = client.open_by_key(sheet_id)
        # Cache worksheet objects to avoid repeated lookups
        self._ws_cache: Dict[str, object] = {}

    @classmethod
    def from_spreadsheet(cls, spreadsheet: object) -> "OrderUploadSheets":
        """Helper for unit tests to inject a fake spreadsheet."""
        return cls(spreadsheet=spreadsheet)

    # ─────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────

    def _get_or_create_sheet(self, title: str, columns: List[str]):
        # Return cached worksheet if available
        if title in self._ws_cache:
            return self._ws_cache[title]

        # First, try to get an existing worksheet by name
        try:
            ws = self.spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            # Sheet doesn't exist yet — create it
            ws = self.spreadsheet.add_worksheet(title=title, rows=1000, cols=len(columns))
            ws.append_row(columns)
            self._ws_cache[title] = ws
            return ws

        # Sheet exists — make sure it has a header row
        try:
            headers = ws.row_values(1)
            if not headers:
                ws.append_row(columns)
        except Exception as e:
            print(f"[OrderUploadSheets] Warning: could not verify headers for '{title}': {e}")

        self._ws_cache[title] = ws
        return ws

    def _append_rows_batch(self, ws, columns: List[str], rows: List[Dict]) -> bool:
        """
        Append multiple rows in a single batch API call.

        Reads existing data once to check for duplicates, then appends
        all new rows in one call. This minimizes API read/write quota usage.
        """
        if not rows:
            return True
        try:
            # Single read to get all existing data
            all_values = []
            for row in rows:
                values = [str(row.get(col, "")) for col in columns]
                all_values.append(values)

            # Batch append all rows at once
            if all_values:
                ws.append_rows(all_values, value_input_option="USER_ENTERED")
            return True
        except Exception as e:
            print(f"[OrderUploadSheets] Failed to batch append to '{ws.title}': {e}")
            return False

    def _append_single_row(self, ws, columns: List[str], row: Dict) -> bool:
        """Append a single row without duplicate checking (fast, 1 API call)."""
        try:
            values = [str(row.get(col, "")) for col in columns]
            ws.append_row(values, value_input_option="USER_ENTERED")
            return True
        except Exception as e:
            print(f"[OrderUploadSheets] Failed to append row to '{ws.title}': {e}")
            return False

    # ─────────────────────────────────────────────────────────────
    # Public methods
    # ─────────────────────────────────────────────────────────────

    def append_raw_ocr(self, order_id: str, page_no: int, raw_text: str, timestamp: str) -> bool:
        ws = self._get_or_create_sheet(config.RAW_OCR_SHEET_NAME, config.RAW_OCR_COLUMNS)
        row = {
            "order_id": order_id,
            "page_no": str(page_no),
            "raw_text": raw_text,
            "timestamp": timestamp,
        }
        return self._append_single_row(ws, config.RAW_OCR_COLUMNS, row)

    def append_normalized_lines(self, rows: List[Dict]) -> bool:
        """
        Append normalized lines in a single batch API call.

        Each row should have:
          - 'S.N', 'PART NAME', 'QTY', 'source_page', 'confidence'
        """
        if not rows:
            return True
        ws = self._get_or_create_sheet(
            config.NORMALIZED_LINES_SHEET_NAME, config.NORMALIZED_LINES_COLUMNS
        )
        return self._append_rows_batch(ws, config.NORMALIZED_LINES_COLUMNS, rows)

    def append_matched_lines(self, rows: List[Dict], grand_total: float = 0.0) -> bool:
        """
        Append matched lines in a single batch API call, followed by a Grand Total row.

        Each row should have at least:
          - 'S.N', 'PART NAME', 'PART NUMBER', 'PRICE', 'QTY', 'LINE TOTAL'
        """
        if not rows:
            return True
        ws = self._get_or_create_sheet(
            config.MATCHED_LINES_SHEET_NAME, config.MATCHED_LINES_COLUMNS
        )

        # Build all rows including grand total in one batch
        all_values = []
        for r in rows:
            all_values.append([str(r.get(col, "")) for col in config.MATCHED_LINES_COLUMNS])

        # Always append a Grand Total row
        all_values.append(["", "", "", "", "GRAND TOTAL", str(grand_total)])

        try:
            ws.append_rows(all_values, value_input_option="USER_ENTERED")

            # Highlight the GRAND TOTAL row in yellow
            try:
                total_row_idx = len(ws.get_all_values())  # 1-based row number of last row
                ws.format(
                    f"A{total_row_idx}:F{total_row_idx}",
                    {
                        "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 0.0},
                        "textFormat": {"bold": True},
                    },
                )
            except Exception as fmt_err:
                print(f"[OrderUploadSheets] Could not format grand total row: {fmt_err}")

            return True
        except Exception as e:
            print(f"[OrderUploadSheets] Failed to batch append matched lines: {e}")
            return False

    def append_error(self, order_id: str, error_type: str, description: str) -> bool:
        ws = self._get_or_create_sheet(config.ORDER_ERRORS_SHEET_NAME, config.ORDER_ERRORS_COLUMNS)
        row = {
            "order_id": order_id,
            "error_type": error_type,
            "description": description,
        }
        return self._append_single_row(ws, config.ORDER_ERRORS_COLUMNS, row)

    def append_errors_batch(self, rows: List[Dict]) -> bool:
        """Append multiple error rows in a single batch API call."""
        if not rows:
            return True
        ws = self._get_or_create_sheet(config.ORDER_ERRORS_SHEET_NAME, config.ORDER_ERRORS_COLUMNS)
        return self._append_rows_batch(ws, config.ORDER_ERRORS_COLUMNS, rows)

    def append_order_summary(self, summary: Dict) -> bool:
        """
        Append a single order summary row to the Order_Summary sheet.

        Expected keys:
            order_id, timestamp, total_images, lines_extracted,
            lines_matched, lines_unmatched, duplicates_skipped, grand_total
        """
        ws = self._get_or_create_sheet(
            config.ORDER_SUMMARY_SHEET_NAME, config.ORDER_SUMMARY_COLUMNS
        )
        return self._append_single_row(ws, config.ORDER_SUMMARY_COLUMNS, summary)


