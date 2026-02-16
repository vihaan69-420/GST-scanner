"""
Tests for batch_engine.batch_queue_store

Covers: CRUD operations with a fully mocked gspread client.
No real Google Sheets are touched.
"""
import json
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from batch_engine.batch_models import BatchRecord, BatchStatus
from batch_engine.batch_config import BATCH_QUEUE_COLUMNS


class TestBatchQueueStore(unittest.TestCase):
    """Test BatchQueueStore methods with a mocked worksheet."""

    def setUp(self):
        patcher_creds = patch('batch_engine.batch_queue_store.config.get_credentials_path',
                              return_value='/fake/path.json')
        patcher_sa = patch('batch_engine.batch_queue_store.ServiceAccountCredentials.from_json_keyfile_name')
        patcher_gspread = patch('batch_engine.batch_queue_store.gspread.authorize')
        patcher_sheet_id = patch('batch_engine.batch_queue_store.config.GOOGLE_SHEET_ID', 'fake_id')
        patcher_tab = patch('batch_engine.batch_queue_store.config.BATCH_QUEUE_SHEET_NAME', 'Batch_Queue')

        self.mock_creds_path = patcher_creds.start()
        self.mock_sa = patcher_sa.start()
        self.mock_gspread = patcher_gspread.start()
        patcher_sheet_id.start()
        patcher_tab.start()

        self.mock_ws = MagicMock()
        self.mock_spreadsheet = MagicMock()
        self.mock_spreadsheet.worksheet.return_value = self.mock_ws
        self.mock_gspread.return_value.open_by_key.return_value = self.mock_spreadsheet

        self.addCleanup(patch.stopall)

        from batch_engine.batch_queue_store import BatchQueueStore
        self.store = BatchQueueStore()

    def _make_record(self, token='T1', status='QUEUED'):
        return BatchRecord(
            token_id=token, business_type='Purchase', user_id='1',
            username='u', created_at='2026-01-01', status=status,
        )

    def test_create_batch_row_appends(self):
        record = self._make_record()
        self.store.create_batch_row(record)
        self.mock_ws.append_row.assert_called_once()
        row = self.mock_ws.append_row.call_args[0][0]
        self.assertEqual(len(row), 16)
        self.assertEqual(row[0], 'T1')

    def test_fetch_by_token_found(self):
        cell = MagicMock()
        cell.row = 2
        self.mock_ws.find.return_value = cell
        self.mock_ws.row_values.return_value = self._make_record().to_row()
        result = self.store.fetch_by_token('T1')
        self.assertIsNotNone(result)
        self.assertEqual(result.token_id, 'T1')

    def test_fetch_by_token_not_found(self):
        self.mock_ws.find.return_value = None
        result = self.store.fetch_by_token('MISSING')
        self.assertIsNone(result)

    def test_update_status(self):
        cell = MagicMock()
        cell.row = 3
        self.mock_ws.find.return_value = cell
        ok = self.store.update_status('T1', BatchStatus.PROCESSING, stage='OCR')
        self.assertTrue(ok)
        self.mock_ws.update_cell.assert_any_call(3, 6, 'PROCESSING')
        self.mock_ws.update_cell.assert_any_call(3, 11, 'OCR')

    def test_increment_processed(self):
        cell = MagicMock()
        cell.row = 2
        self.mock_ws.find.return_value = cell
        self.mock_ws.cell.return_value.value = '5'
        ok = self.store.increment_processed('T1')
        self.assertTrue(ok)
        self.mock_ws.update_cell.assert_any_call(2, 8, '6')

    def test_increment_failed(self):
        cell = MagicMock()
        cell.row = 2
        self.mock_ws.find.return_value = cell
        self.mock_ws.cell.return_value.value = '2'
        ok = self.store.increment_failed('T1')
        self.assertTrue(ok)
        self.mock_ws.update_cell.assert_any_call(2, 9, '3')

    def test_append_error_log(self):
        cell = MagicMock()
        cell.row = 2
        self.mock_ws.find.return_value = cell
        self.mock_ws.cell.return_value.value = '[]'
        ok = self.store.append_error_log('T1', {'err': 'test'})
        self.assertTrue(ok)
        written = self.mock_ws.update_cell.call_args_list[-1][0][2]
        errors = json.loads(written)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['err'], 'test')

    def test_fetch_next_queued(self):
        header = BATCH_QUEUE_COLUMNS
        row1 = self._make_record('T1', 'COMPLETED').to_row()
        row2 = self._make_record('T2', 'QUEUED').to_row()
        self.mock_ws.get_all_values.return_value = [header, row1, row2]
        result = self.store.fetch_next_queued()
        self.assertIsNotNone(result)
        self.assertEqual(result.token_id, 'T2')

    def test_fetch_next_queued_none(self):
        header = BATCH_QUEUE_COLUMNS
        row1 = self._make_record('T1', 'COMPLETED').to_row()
        self.mock_ws.get_all_values.return_value = [header, row1]
        result = self.store.fetch_next_queued()
        self.assertIsNone(result)

    def test_mark_completed(self):
        cell = MagicMock()
        cell.row = 2
        self.mock_ws.find.return_value = cell
        ok = self.store.mark_completed('T1')
        self.assertTrue(ok)
        self.mock_ws.update_cell.assert_any_call(2, 6, 'COMPLETED')

    def test_mark_cancelled(self):
        cell = MagicMock()
        cell.row = 2
        self.mock_ws.find.return_value = cell
        ok = self.store.mark_cancelled('T1')
        self.assertTrue(ok)
        self.mock_ws.update_cell.assert_any_call(2, 6, 'CANCELLED')

    # ── fetch_by_user tests ──────────────────────────────────────────

    def _make_record_for_user(self, token, user_id, status='QUEUED'):
        return BatchRecord(
            token_id=token, business_type='Purchase', user_id=str(user_id),
            username='u', created_at='2026-01-01', status=status,
        )

    def test_fetch_by_user_outstanding_only(self):
        header = BATCH_QUEUE_COLUMNS
        row1 = self._make_record_for_user('T1', '100', 'QUEUED').to_row()
        row2 = self._make_record_for_user('T2', '100', 'COMPLETED').to_row()
        row3 = self._make_record_for_user('T3', '100', 'PROCESSING').to_row()
        row4 = self._make_record_for_user('T4', '200', 'QUEUED').to_row()
        self.mock_ws.get_all_values.return_value = [header, row1, row2, row3, row4]
        results = self.store.fetch_by_user('100', outstanding_only=True)
        self.assertEqual(len(results), 2)
        tokens = [r.token_id for r in results]
        self.assertIn('T1', tokens)
        self.assertIn('T3', tokens)
        self.assertNotIn('T2', tokens)
        self.assertNotIn('T4', tokens)

    def test_fetch_by_user_all(self):
        header = BATCH_QUEUE_COLUMNS
        row1 = self._make_record_for_user('T1', '100', 'QUEUED').to_row()
        row2 = self._make_record_for_user('T2', '100', 'COMPLETED').to_row()
        row3 = self._make_record_for_user('T3', '200', 'QUEUED').to_row()
        self.mock_ws.get_all_values.return_value = [header, row1, row2, row3]
        results = self.store.fetch_by_user('100', outstanding_only=False)
        self.assertEqual(len(results), 2)
        tokens = [r.token_id for r in results]
        self.assertIn('T1', tokens)
        self.assertIn('T2', tokens)

    def test_fetch_by_user_no_batches(self):
        header = BATCH_QUEUE_COLUMNS
        row1 = self._make_record_for_user('T1', '200', 'QUEUED').to_row()
        self.mock_ws.get_all_values.return_value = [header, row1]
        results = self.store.fetch_by_user('999', outstanding_only=True)
        self.assertEqual(results, [])

    def test_fetch_by_user_excludes_cancelled_and_failed(self):
        header = BATCH_QUEUE_COLUMNS
        row1 = self._make_record_for_user('T1', '100', 'CANCELLED').to_row()
        row2 = self._make_record_for_user('T2', '100', 'FAILED').to_row()
        row3 = self._make_record_for_user('T3', '100', 'ACTION_REQUIRED').to_row()
        self.mock_ws.get_all_values.return_value = [header, row1, row2, row3]
        results = self.store.fetch_by_user('100', outstanding_only=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].token_id, 'T3')


if __name__ == '__main__':
    unittest.main()
