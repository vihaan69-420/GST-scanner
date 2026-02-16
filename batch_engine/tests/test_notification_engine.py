"""
Tests for batch_engine.notification_engine

Covers: message formatting, progress bar, error swallowing.
Telegram Bot API is fully mocked.
"""
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from batch_engine.notification_engine import NotificationEngine


class TestProgressBar(unittest.TestCase):
    def test_zero(self):
        bar = NotificationEngine._progress_bar(0)
        self.assertEqual(bar, '[----------]')

    def test_fifty(self):
        bar = NotificationEngine._progress_bar(50)
        self.assertEqual(bar, '[#####-----]')

    def test_hundred(self):
        bar = NotificationEngine._progress_bar(100)
        self.assertEqual(bar, '[##########]')

    def test_custom_width(self):
        bar = NotificationEngine._progress_bar(50, width=4)
        self.assertEqual(bar, '[##--]')


class TestNotificationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = NotificationEngine(bot_token='FAKE_TOKEN')
        self.mock_bot = MagicMock()
        self.mock_bot.send_message = AsyncMock()
        self.engine._bot = self.mock_bot

    def test_send_progress(self):
        result = self.engine.send_progress('123', 'T1', 5, 10)
        self.assertTrue(result)

    def test_send_completion(self):
        summary = {'total': 10, 'successful': 8, 'failed': 2, 'success_rate': 80.0}
        result = self.engine.send_completion('123', 'T1', summary)
        self.assertTrue(result)

    def test_send_failure(self):
        result = self.engine.send_failure('123', 'T1', 'OCR crashed')
        self.assertTrue(result)

    def test_send_action_required(self):
        result = self.engine.send_action_required('123', 'T1', 'Review needed')
        self.assertTrue(result)

    def test_error_swallowing(self):
        self.mock_bot.send_message = AsyncMock(side_effect=Exception("Network error"))
        result = self.engine.send_progress('123', 'T1', 1, 10)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
