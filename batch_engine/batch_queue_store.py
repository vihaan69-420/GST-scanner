"""
Batch Queue Store

Google Sheets CRUD for the Batch_Queue tab.
Reuses the same authentication pattern as src/sheets/sheets_manager.py
without duplicating auth logic.

Optimized to minimize Google Sheets API calls by:
- Caching row numbers per token during batch processing
- Batching cell updates into single range updates
- Reducing redundant find() lookups
"""
import json
import sys
import os
import time
from datetime import datetime
from typing import Optional, List

import gspread
from oauth2client.service_account import ServiceAccountCredentials

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import config

from batch_engine.batch_config import BATCH_QUEUE_COLUMNS
from batch_engine.batch_models import BatchRecord, BatchStatus

API_CALL_DELAY = 1.0


def _api_pause():
    """Small pause between Sheets API calls to stay within quota."""
    time.sleep(API_CALL_DELAY)


class BatchQueueStore:
    """CRUD operations for the Batch_Queue Google Sheet tab."""

    def __init__(self, sheet_id: str = None):
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
        ]

        creds_path = config.get_credentials_path()
        if creds_path:
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            client = gspread.authorize(creds)
        else:
            import google.auth
            credentials, _ = google.auth.default(scopes=scope)
            client = gspread.authorize(credentials)

        target_sheet_id = sheet_id or config.GOOGLE_SHEET_ID
        self.spreadsheet = client.open_by_key(target_sheet_id)
        self.worksheet = self._ensure_worksheet()
        self._row_cache = {}

    def _ensure_worksheet(self):
        """Get or create the Batch_Queue tab with headers."""
        tab_name = config.BATCH_QUEUE_SHEET_NAME
        try:
            ws = self.spreadsheet.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(
                title=tab_name, rows=1000, cols=len(BATCH_QUEUE_COLUMNS)
            )
            ws.append_row(BATCH_QUEUE_COLUMNS)
        return ws

    def create_batch_row(self, record: BatchRecord) -> None:
        """Append a new batch record row."""
        self.worksheet.append_row(record.to_row())
        self._row_cache.pop(record.token_id, None)

    def fetch_by_token(self, token_id: str) -> Optional[BatchRecord]:
        """Find a batch record by Token_ID. Returns None if not found."""
        try:
            cell = self.worksheet.find(token_id, in_column=1)
            if cell:
                self._row_cache[token_id] = cell.row
                row = self.worksheet.row_values(cell.row)
                _api_pause()
                return BatchRecord.from_row(row)
        except Exception:
            pass
        return None

    def _find_row_number(self, token_id: str) -> Optional[int]:
        """Return the 1-based row number for a token, using cache when available."""
        cached = self._row_cache.get(token_id)
        if cached:
            return cached
        try:
            cell = self.worksheet.find(token_id, in_column=1)
            if cell:
                self._row_cache[token_id] = cell.row
                return cell.row
        except Exception:
            pass
        return None

    def update_status(self, token_id: str, status: BatchStatus, stage: str = '') -> bool:
        """Update Status, Current_Stage, and Last_Update in a single batch call."""
        row_num = self._find_row_number(token_id)
        if not row_num:
            return False
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        batch = [
            {'range': f'F{row_num}', 'values': [[status.value]]},
            {'range': f'L{row_num}', 'values': [[now]]},
        ]
        if stage:
            batch.append({'range': f'K{row_num}', 'values': [[stage]]})
        self.worksheet.batch_update(batch)
        _api_pause()
        return True

    def increment_processed(self, token_id: str) -> bool:
        """Increment the Processed_Count by 1 and update Last_Update in one call."""
        row_num = self._find_row_number(token_id)
        if not row_num:
            return False
        current = self.worksheet.cell(row_num, 8).value or '0'
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.worksheet.batch_update([
            {'range': f'H{row_num}', 'values': [[str(int(current) + 1)]]},
            {'range': f'L{row_num}', 'values': [[now]]},
        ])
        _api_pause()
        return True

    def increment_failed(self, token_id: str) -> bool:
        """Increment the Failed_Count by 1 and update Last_Update in one call."""
        row_num = self._find_row_number(token_id)
        if not row_num:
            return False
        current = self.worksheet.cell(row_num, 9).value or '0'
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.worksheet.batch_update([
            {'range': f'I{row_num}', 'values': [[str(int(current) + 1)]]},
            {'range': f'L{row_num}', 'values': [[now]]},
        ])
        _api_pause()
        return True

    def increment_review(self, token_id: str) -> bool:
        """Increment the Review_Count by 1."""
        row_num = self._find_row_number(token_id)
        if not row_num:
            return False
        current = self.worksheet.cell(row_num, 10).value or '0'
        self.worksheet.update_cell(row_num, 10, str(int(current) + 1))
        _api_pause()
        return True

    def append_error_log(self, token_id: str, error_entry: dict) -> bool:
        """Append an error dict to the Error_Log_JSON column."""
        row_num = self._find_row_number(token_id)
        if not row_num:
            return False
        raw = self.worksheet.cell(row_num, 14).value or '[]'
        try:
            errors = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            errors = []
        errors.append(error_entry)
        self.worksheet.update_cell(row_num, 14, json.dumps(errors))
        _api_pause()
        return True

    def increment_retry(self, token_id: str) -> bool:
        """Increment the Retry_Count by 1."""
        row_num = self._find_row_number(token_id)
        if not row_num:
            return False
        current = self.worksheet.cell(row_num, 15).value or '0'
        self.worksheet.update_cell(row_num, 15, str(int(current) + 1))
        _api_pause()
        return True

    def fetch_by_user(self, user_id: str, outstanding_only: bool = True) -> List[BatchRecord]:
        """Return all batch records for a user, optionally filtered to outstanding only.

        Args:
            user_id: Telegram user ID (compared as string).
            outstanding_only: If True, exclude COMPLETED, CANCELLED, and FAILED batches.

        Returns:
            List of BatchRecord instances (may be empty).
        """
        terminal_statuses = {
            BatchStatus.COMPLETED.value,
            BatchStatus.CANCELLED.value,
            BatchStatus.FAILED.value,
        }
        all_rows = self.worksheet.get_all_values()
        _api_pause()
        results = []
        for row in all_rows[1:]:
            if len(row) >= 3 and str(row[2]) == str(user_id):
                if outstanding_only and len(row) >= 6 and row[5] in terminal_statuses:
                    continue
                results.append(BatchRecord.from_row(row))
        return results

    def fetch_next_queued(self) -> Optional[BatchRecord]:
        """Return the oldest batch with status QUEUED, or None."""
        all_rows = self.worksheet.get_all_values()
        _api_pause()
        for row in all_rows[1:]:
            if len(row) >= 6 and row[5] == BatchStatus.QUEUED.value:
                record = BatchRecord.from_row(row)
                try:
                    cell = self.worksheet.find(record.token_id, in_column=1)
                    if cell:
                        self._row_cache[record.token_id] = cell.row
                except Exception:
                    pass
                return record
        return None

    def mark_completed(self, token_id: str) -> bool:
        """Set status to COMPLETED and record completion time in a single batch call."""
        row_num = self._find_row_number(token_id)
        if not row_num:
            return False
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.worksheet.batch_update([
            {'range': f'F{row_num}', 'values': [[BatchStatus.COMPLETED.value]]},
            {'range': f'K{row_num}', 'values': [['DONE']]},
            {'range': f'L{row_num}', 'values': [[now]]},
            {'range': f'M{row_num}', 'values': [[now]]},
        ])
        _api_pause()
        self._row_cache.pop(token_id, None)
        return True

    def mark_cancelled(self, token_id: str) -> bool:
        """Set status to CANCELLED in a single batch call."""
        row_num = self._find_row_number(token_id)
        if not row_num:
            return False
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.worksheet.batch_update([
            {'range': f'F{row_num}', 'values': [[BatchStatus.CANCELLED.value]]},
            {'range': f'K{row_num}', 'values': [['CANCELLED']]},
            {'range': f'L{row_num}', 'values': [[now]]},
            {'range': f'M{row_num}', 'values': [[now]]},
        ])
        _api_pause()
        self._row_cache.pop(token_id, None)
        return True

    def update_notification_sent(self, token_id: str) -> bool:
        """Update the Notification_Last_Sent timestamp."""
        row_num = self._find_row_number(token_id)
        if not row_num:
            return False
        self.worksheet.update_cell(
            row_num, 16, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        _api_pause()
        return True
