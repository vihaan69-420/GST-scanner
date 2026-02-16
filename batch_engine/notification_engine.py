"""
Notification Engine

Generic, reusable Telegram notification sender.
Uses the telegram.Bot API directly -- no bot framework dependency.
Stateless and safe to call from any process (bot or worker).
"""
import asyncio
import sys
import os
from typing import Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import config


class NotificationEngine:
    """Send Telegram notifications for batch processing events."""

    def __init__(self, bot_token: str = None):
        self._bot_token = bot_token or config.TELEGRAM_BOT_TOKEN
        self._bot = None

    @property
    def bot(self):
        if self._bot is None:
            from telegram import Bot
            self._bot = Bot(token=self._bot_token)
        return self._bot

    async def _send(self, chat_id, text: str) -> bool:
        """Low-level send with error swallowing so worker never crashes on notify."""
        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            return True
        except Exception as e:
            print(f"[NotificationEngine] Failed to send to {chat_id}: {e}")
            return False

    def _send_sync(self, chat_id, text: str) -> bool:
        """Synchronous wrapper for use in the standalone worker."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._send(chat_id, text))
                return True
        except RuntimeError:
            pass
        return asyncio.run(self._send(chat_id, text))

    def send_progress(
        self, user_id, token_id: str, processed: int, total: int
    ) -> bool:
        """Notify user of batch processing progress."""
        pct = int((processed / total) * 100) if total > 0 else 0
        bar = self._progress_bar(pct)
        text = (
            f"Batch Progress: {token_id}\n\n"
            f"{bar} {pct}%\n"
            f"Processed: {processed}/{total}"
        )
        return self._send_sync(user_id, text)

    def send_completion(
        self, user_id, token_id: str, summary: Dict
    ) -> bool:
        """Notify user that batch processing completed."""
        text = (
            f"Batch Complete: {token_id}\n\n"
            f"Total: {summary.get('total', 0)}\n"
            f"Successful: {summary.get('successful', 0)}\n"
            f"Failed: {summary.get('failed', 0)}\n"
            f"Success rate: {summary.get('success_rate', 0):.1f}%"
        )
        return self._send_sync(user_id, text)

    def send_failure(
        self, user_id, token_id: str, error_info: str
    ) -> bool:
        """Notify user that the batch failed."""
        text = (
            f"Batch Failed: {token_id}\n\n"
            f"Error: {error_info}\n\n"
            f"Use /batch_status {token_id} for details."
        )
        return self._send_sync(user_id, text)

    def send_action_required(
        self, user_id, token_id: str, details: str
    ) -> bool:
        """Notify user that manual action is needed."""
        text = (
            f"Action Required: {token_id}\n\n"
            f"{details}\n\n"
            f"Use /batch_status {token_id} for details."
        )
        return self._send_sync(user_id, text)

    @staticmethod
    def _progress_bar(pct: int, width: int = 10) -> str:
        filled = int(width * pct / 100)
        empty = width - filled
        return '[' + '#' * filled + '-' * empty + ']'
