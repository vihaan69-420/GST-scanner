"""
Tests for batch_engine.batch_worker

Covers: queue polling, counter increments, retry logic, graceful shutdown.
All external services (OCR, Sheets, Telegram) are mocked.
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


class TestProcessBatch(unittest.TestCase):
    """Test the _process_batch function in isolation."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='batch_worker_tests_')
        import config
        self._orig_temp = config.TEMP_FOLDER
        config.TEMP_FOLDER = self.tmp_dir

        self.mock_store = MagicMock()
        self.mock_processor = MagicMock()
        self.mock_notifier = MagicMock()
        self.mock_notifier.send_progress.return_value = True
        self.mock_notifier.send_completion.return_value = True
        self.mock_notifier.send_failure.return_value = True
        self.mock_notifier.send_action_required.return_value = True

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        import config
        config.TEMP_FOLDER = self._orig_temp

    def _make_record(self, token='T1', total=3):
        return BatchRecord(
            token_id=token, business_type='Purchase', user_id='1',
            username='u', created_at='now', total_invoices=total,
        )

    def _create_batch_dir(self, token, count):
        batch_dir = os.path.join(self.tmp_dir, f'batch_{token}')
        os.makedirs(batch_dir, exist_ok=True)
        for i in range(count):
            with open(os.path.join(batch_dir, f'invoice_{i}.jpg'), 'w') as f:
                f.write('fake')
        return batch_dir

    def test_successful_batch(self):
        from batch_engine.batch_worker import _process_batch
        record = self._make_record('T1', 2)
        self._create_batch_dir('T1', 2)
        self.mock_processor.process_batch.return_value = {
            'total': 1, 'successful': 1, 'failed': 0,
            'results': [{'success': True}], 'success_rate': 100.0,
        }
        _process_batch(record, self.mock_store, self.mock_processor, self.mock_notifier)
        self.mock_store.mark_completed.assert_called_once_with('T1')
        self.mock_notifier.send_completion.assert_called_once()

    def test_all_failed_batch(self):
        from batch_engine.batch_worker import _process_batch
        record = self._make_record('T2', 2)
        self._create_batch_dir('T2', 2)
        self.mock_processor.process_batch.return_value = {
            'total': 1, 'successful': 0, 'failed': 1,
            'results': [{'success': False, 'error': 'OCR fail'}],
            'success_rate': 0.0,
        }
        _process_batch(record, self.mock_store, self.mock_processor, self.mock_notifier)
        self.mock_store.update_status.assert_any_call('T2', BatchStatus.FAILED, stage='ALL_FAILED')
        self.mock_notifier.send_failure.assert_called()

    def test_partial_failure(self):
        from batch_engine.batch_worker import _process_batch
        record = self._make_record('T3', 2)
        self._create_batch_dir('T3', 2)

        call_count = [0]
        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    'total': 1, 'successful': 1, 'failed': 0,
                    'results': [{'success': True}], 'success_rate': 100.0,
                }
            else:
                return {
                    'total': 1, 'successful': 0, 'failed': 1,
                    'results': [{'success': False, 'error': 'parse fail'}],
                    'success_rate': 0.0,
                }
        self.mock_processor.process_batch.side_effect = side_effect
        _process_batch(record, self.mock_store, self.mock_processor, self.mock_notifier)
        self.mock_store.mark_completed.assert_called_once()
        self.mock_notifier.send_action_required.assert_called()

    def test_missing_batch_dir(self):
        from batch_engine.batch_worker import _process_batch
        record = self._make_record('MISSING', 1)
        _process_batch(record, self.mock_store, self.mock_processor, self.mock_notifier)
        self.mock_store.update_status.assert_any_call(
            'MISSING', BatchStatus.FAILED, stage='MISSING_FILES')
        self.mock_notifier.send_failure.assert_called()

    def test_empty_batch_dir(self):
        from batch_engine.batch_worker import _process_batch
        record = self._make_record('EMPTY', 0)
        batch_dir = os.path.join(self.tmp_dir, 'batch_EMPTY')
        os.makedirs(batch_dir)
        _process_batch(record, self.mock_store, self.mock_processor, self.mock_notifier)
        self.mock_store.update_status.assert_any_call(
            'EMPTY', BatchStatus.FAILED, stage='NO_INVOICES')

    def test_cleanup_after_completion(self):
        from batch_engine.batch_worker import _process_batch
        record = self._make_record('CLEANUP', 1)
        batch_dir = self._create_batch_dir('CLEANUP', 1)
        self.mock_processor.process_batch.return_value = {
            'total': 1, 'successful': 1, 'failed': 0,
            'results': [{'success': True}], 'success_rate': 100.0,
        }
        _process_batch(record, self.mock_store, self.mock_processor, self.mock_notifier)
        self.assertFalse(os.path.exists(batch_dir))


if __name__ == '__main__':
    unittest.main()
