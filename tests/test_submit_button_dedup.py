"""
Tests for submit button deduplication and batch status UX.

Covers:
- OrderSession.last_button_message_id tracking (edit-in-place support)
- Batch session last_button_message_id tracking (edit-in-place support)
- _format_batch_detail static helper
- _build_batch_action_buttons static helper
- Edge cases: first upload (no previous message), missing key
"""
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from order_normalization.order_session import OrderSession, OrderStatus
from bot.telegram_bot import GSTScannerBot


class TestOrderSessionButtonTracking(unittest.TestCase):
    """Verify OrderSession tracks last_button_message_id for edit-in-place."""

    def test_initial_last_button_message_id_is_none(self):
        session = OrderSession(user_id=123, username='testuser')
        self.assertIsNone(session.last_button_message_id)

    def test_last_button_message_id_can_be_set(self):
        session = OrderSession(user_id=123)
        session.last_button_message_id = 42
        self.assertEqual(session.last_button_message_id, 42)

    def test_message_id_persists_across_page_adds(self):
        session = OrderSession(user_id=123)
        session.last_button_message_id = 100
        session.add_page('/tmp/fake_page1.jpg')
        self.assertEqual(session.last_button_message_id, 100)
        session.add_page('/tmp/fake_page2.jpg')
        self.assertEqual(session.last_button_message_id, 100)

    def test_message_id_can_be_overwritten(self):
        session = OrderSession(user_id=123)
        session.last_button_message_id = 100
        session.last_button_message_id = 200
        self.assertEqual(session.last_button_message_id, 200)


class TestBatchSessionButtonTracking(unittest.TestCase):
    """Verify batch session dict tracks last_button_message_id for edit-in-place."""

    def _make_batch_session(self):
        return {
            'images': [],
            'business_type': 'Purchase',
            'last_button_message_id': None,
        }

    def test_initial_last_button_message_id_is_none(self):
        session = self._make_batch_session()
        self.assertIsNone(session['last_button_message_id'])

    def test_message_id_persists_across_image_adds(self):
        session = self._make_batch_session()
        session['last_button_message_id'] = 101
        session['images'].append('/tmp/inv1.jpg')
        session['images'].append('/tmp/inv2.jpg')
        self.assertEqual(session['last_button_message_id'], 101)
        self.assertEqual(len(session['images']), 2)

    def test_get_returns_none_for_missing_key(self):
        session = {'images': [], 'business_type': 'Purchase'}
        self.assertIsNone(session.get('last_button_message_id'))


def _make_mock_record(**overrides):
    """Create a mock BatchRecord with sensible defaults."""
    defaults = {
        'token_id': 'BATCH-20260216-123-ABC123',
        'status': 'PROCESSING',
        'current_stage': 'INVOICE_2_OF_5',
        'total_invoices': 5,
        'processed_count': 1,
        'failed_count': 0,
        'review_count': 0,
        'created_at': '2026-02-16 10:00:00',
        'last_update': '2026-02-16 10:05:00',
    }
    defaults.update(overrides)
    rec = MagicMock()
    for k, v in defaults.items():
        setattr(rec, k, v)
    return rec


class TestFormatBatchDetail(unittest.TestCase):
    """Test the _format_batch_detail static helper."""

    def test_basic_format(self):
        rec = _make_mock_record()
        text = GSTScannerBot._format_batch_detail(rec)
        self.assertIn('BATCH-20260216-123-ABC123', text)
        self.assertIn('PROCESSING', text)
        self.assertIn('1/5 processed', text)
        self.assertIn('2026-02-16 10:00:00', text)

    def test_with_index(self):
        rec = _make_mock_record()
        text = GSTScannerBot._format_batch_detail(rec, index=1)
        self.assertTrue(text.startswith('1. '))

    def test_without_index(self):
        rec = _make_mock_record()
        text = GSTScannerBot._format_batch_detail(rec)
        self.assertFalse(text.startswith('1. '))

    def test_shows_failed_count(self):
        rec = _make_mock_record(failed_count=2)
        text = GSTScannerBot._format_batch_detail(rec)
        self.assertIn('2 failed', text)

    def test_shows_review_count(self):
        rec = _make_mock_record(review_count=3)
        text = GSTScannerBot._format_batch_detail(rec)
        self.assertIn('3 review', text)

    def test_missing_last_update(self):
        rec = _make_mock_record(last_update='')
        text = GSTScannerBot._format_batch_detail(rec)
        self.assertIn('—', text)

    def test_shows_last_update_when_present(self):
        rec = _make_mock_record(last_update='2026-02-16 10:05:00')
        text = GSTScannerBot._format_batch_detail(rec)
        self.assertIn('2026-02-16 10:05:00', text)


class TestBuildBatchActionButtons(unittest.TestCase):
    """Test the _build_batch_action_buttons static helper."""

    def test_single_batch_returns_correct_rows(self):
        batches = [_make_mock_record(token_id='BATCH-20260216-123-ABC123')]
        rows = GSTScannerBot._build_batch_action_buttons(batches)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), 2)
        self.assertEqual(rows[0][0].callback_data, 'bst_BATCH-20260216-123-ABC123')
        self.assertEqual(rows[0][1].callback_data, 'bca_BATCH-20260216-123-ABC123')
        self.assertEqual(rows[-1][0].callback_data, 'menu_main')

    def test_multiple_batches(self):
        batches = [
            _make_mock_record(token_id='BATCH-1'),
            _make_mock_record(token_id='BATCH-2'),
        ]
        rows = GSTScannerBot._build_batch_action_buttons(batches)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0].callback_data, 'bst_BATCH-1')
        self.assertEqual(rows[1][0].callback_data, 'bst_BATCH-2')

    def test_back_button_always_last(self):
        batches = [_make_mock_record(token_id='T1')]
        rows = GSTScannerBot._build_batch_action_buttons(batches)
        self.assertEqual(rows[-1][0].callback_data, 'menu_main')

    def test_button_labels_contain_token_suffix(self):
        batches = [_make_mock_record(token_id='BATCH-20260216-123-ABC123')]
        rows = GSTScannerBot._build_batch_action_buttons(batches)
        self.assertIn('ABC123', rows[0][0].text)
        self.assertIn('ABC123', rows[0][1].text)


if __name__ == '__main__':
    unittest.main()
