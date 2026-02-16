"""
Tests for batch_engine.batch_models

Covers: TokenID generation, BatchStatus enum, BatchRecord serialization.
"""
import re
import unittest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from batch_engine.batch_models import BatchRecord, BatchStatus, generate_token


class TestBatchStatus(unittest.TestCase):
    def test_all_statuses_exist(self):
        expected = {'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED',
                    'ACTION_REQUIRED', 'CANCELLED'}
        actual = {s.value for s in BatchStatus}
        self.assertEqual(expected, actual)

    def test_status_values_are_strings(self):
        for s in BatchStatus:
            self.assertIsInstance(s.value, str)


class TestGenerateToken(unittest.TestCase):
    TOKEN_PATTERN = re.compile(r'^BATCH-\d{8}-\d+-[A-Z0-9]{6}$')

    def test_format(self):
        token = generate_token(12345)
        self.assertRegex(token, self.TOKEN_PATTERN)

    def test_contains_user_id(self):
        token = generate_token(99999)
        self.assertIn('99999', token)

    def test_uniqueness(self):
        tokens = {generate_token(1) for _ in range(100)}
        self.assertEqual(len(tokens), 100)


class TestBatchRecord(unittest.TestCase):
    def _make_record(self):
        return BatchRecord(
            token_id='BATCH-20260216-1-ABC123',
            business_type='Purchase',
            user_id='1',
            username='testuser',
            created_at='2026-02-16 10:00:00',
        )

    def test_to_row_length(self):
        row = self._make_record().to_row()
        self.assertEqual(len(row), 16)

    def test_to_row_types(self):
        row = self._make_record().to_row()
        for item in row:
            self.assertIsInstance(item, str)

    def test_from_row_roundtrip(self):
        original = self._make_record()
        row = original.to_row()
        restored = BatchRecord.from_row(row)
        self.assertEqual(original.token_id, restored.token_id)
        self.assertEqual(original.status, restored.status)
        self.assertEqual(original.total_invoices, restored.total_invoices)

    def test_from_row_short_row(self):
        row = ['TOKEN', 'Purchase', '1', 'user', '2026-01-01']
        record = BatchRecord.from_row(row)
        self.assertEqual(record.token_id, 'TOKEN')
        self.assertEqual(record.status, BatchStatus.QUEUED.value)

    def test_defaults(self):
        record = self._make_record()
        self.assertEqual(record.status, 'QUEUED')
        self.assertEqual(record.processed_count, 0)
        self.assertEqual(record.failed_count, 0)
        self.assertEqual(record.error_log_json, '[]')


if __name__ == '__main__':
    unittest.main()
