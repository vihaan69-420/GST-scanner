"""
Tests for batch_engine.batch_manager

Covers: batch lifecycle -- create, submit, cancel, status, ownership.
Uses mocked BatchQueueStore (no real Google Sheets).
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from batch_engine.batch_models import BatchRecord, BatchStatus
from batch_engine.batch_manager import BatchManager


class TestBatchManager(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='batch_engine_tests_')
        self.mock_store = MagicMock()
        self.manager = BatchManager(store=self.mock_store)

        self._orig_temp = None
        import config
        self._orig_temp = config.TEMP_FOLDER
        config.TEMP_FOLDER = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        import config
        config.TEMP_FOLDER = self._orig_temp

    def _create_fake_images(self, count=3):
        paths = []
        for i in range(count):
            p = os.path.join(self.tmp_dir, f'invoice_{i}.jpg')
            with open(p, 'w') as f:
                f.write(f'fake image {i}')
            paths.append(p)
        return paths

    def test_create_batch_returns_record(self):
        images = self._create_fake_images(2)
        record = self.manager.create_batch(
            user_id='123', username='alice',
            invoice_paths=images, business_type='Purchase',
        )
        self.assertIsInstance(record, BatchRecord)
        self.assertEqual(record.total_invoices, 2)
        self.assertEqual(record.status, BatchStatus.QUEUED.value)
        self.assertIn('123', record.token_id)
        self.mock_store.create_batch_row.assert_called_once()

    def test_create_batch_copies_files(self):
        images = self._create_fake_images(2)
        record = self.manager.create_batch(
            user_id='1', username='u', invoice_paths=images,
        )
        batch_dir = os.path.join(self.tmp_dir, f'batch_{record.token_id}')
        self.assertTrue(os.path.isdir(batch_dir))
        self.assertEqual(len(os.listdir(batch_dir)), 2)

    def test_submit_batch_found(self):
        fake_record = BatchRecord(
            token_id='T1', business_type='Purchase', user_id='1',
            username='u', created_at='now', status=BatchStatus.QUEUED.value,
        )
        self.mock_store.fetch_by_token.return_value = fake_record
        result = self.manager.submit_batch('T1')
        self.assertIsNotNone(result)
        self.mock_store.update_status.assert_called_once()

    def test_submit_batch_not_found(self):
        self.mock_store.fetch_by_token.return_value = None
        result = self.manager.submit_batch('NONEXIST')
        self.assertIsNone(result)

    def test_cancel_batch_success(self):
        fake_record = BatchRecord(
            token_id='T1', business_type='Purchase', user_id='10',
            username='u', created_at='now', status=BatchStatus.QUEUED.value,
        )
        self.mock_store.fetch_by_token.return_value = fake_record
        result = self.manager.cancel_batch('T1', '10')
        self.assertTrue(result['success'])
        self.mock_store.mark_cancelled.assert_called_once_with('T1')

    def test_cancel_batch_wrong_owner(self):
        fake_record = BatchRecord(
            token_id='T1', business_type='Purchase', user_id='10',
            username='u', created_at='now', status=BatchStatus.QUEUED.value,
        )
        self.mock_store.fetch_by_token.return_value = fake_record
        result = self.manager.cancel_batch('T1', '99')
        self.assertFalse(result['success'])
        self.assertIn('own', result['error'].lower())

    def test_cancel_already_completed(self):
        fake_record = BatchRecord(
            token_id='T1', business_type='Purchase', user_id='10',
            username='u', created_at='now', status=BatchStatus.COMPLETED.value,
        )
        self.mock_store.fetch_by_token.return_value = fake_record
        result = self.manager.cancel_batch('T1', '10')
        self.assertFalse(result['success'])

    def test_get_status(self):
        fake_record = BatchRecord(
            token_id='T1', business_type='Purchase', user_id='1',
            username='u', created_at='now',
        )
        self.mock_store.fetch_by_token.return_value = fake_record
        result = self.manager.get_status('T1')
        self.assertEqual(result.token_id, 'T1')

    def test_list_invoice_files_empty_dir(self):
        files = BatchManager.list_invoice_files('NONEXIST')
        self.assertEqual(files, [])

    def test_get_user_batches_delegates_to_store(self):
        fake_records = [
            BatchRecord(
                token_id='T1', business_type='Purchase', user_id='42',
                username='u', created_at='now', status=BatchStatus.QUEUED.value,
            ),
        ]
        self.mock_store.fetch_by_user.return_value = fake_records
        result = self.manager.get_user_batches('42', outstanding_only=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].token_id, 'T1')
        self.mock_store.fetch_by_user.assert_called_once_with('42', True)

    def test_get_user_batches_empty(self):
        self.mock_store.fetch_by_user.return_value = []
        result = self.manager.get_user_batches('999')
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
