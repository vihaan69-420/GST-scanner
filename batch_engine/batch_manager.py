"""
Batch Manager

Orchestrates batch lifecycle: create, submit, cancel, status.
Pure orchestration -- no Telegram imports, no pipeline imports.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import config

from batch_engine.batch_models import BatchRecord, BatchStatus, generate_token
from batch_engine.batch_queue_store import BatchQueueStore


class BatchManager:
    """Manages batch lifecycle operations."""

    def __init__(self, store: BatchQueueStore = None):
        self._store = store

    @property
    def store(self) -> BatchQueueStore:
        if self._store is None:
            self._store = BatchQueueStore()
        return self._store

    def create_batch(
        self,
        user_id: str,
        username: str,
        invoice_paths: List[str],
        business_type: str = 'Purchase',
    ) -> BatchRecord:
        """
        Create a new batch, copy invoices into a batch subfolder, and
        write the initial queue row.

        Returns the BatchRecord (status=QUEUED).
        """
        token_id = generate_token(user_id)

        batch_dir = os.path.join(config.TEMP_FOLDER, f'batch_{token_id}')
        os.makedirs(batch_dir, exist_ok=True)
        copied_paths = []
        for src_path in invoice_paths:
            dst = os.path.join(batch_dir, os.path.basename(src_path))
            shutil.copy2(src_path, dst)
            copied_paths.append(dst)

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        record = BatchRecord(
            token_id=token_id,
            business_type=business_type,
            user_id=str(user_id),
            username=username,
            created_at=now,
            status=BatchStatus.QUEUED.value,
            total_invoices=len(copied_paths),
            last_update=now,
            current_stage='QUEUED',
        )

        self.store.create_batch_row(record)
        return record

    def submit_batch(self, token_id: str) -> Optional[BatchRecord]:
        """
        Confirm submission of a batch.  Sets status to QUEUED if still valid.
        Returns the updated record or None if not found.
        """
        record = self.store.fetch_by_token(token_id)
        if not record:
            return None
        if record.status != BatchStatus.QUEUED.value:
            return record
        self.store.update_status(token_id, BatchStatus.QUEUED, stage='AWAITING_WORKER')
        record.current_stage = 'AWAITING_WORKER'
        return record

    def cancel_batch(self, token_id: str, user_id: str) -> Dict:
        """
        Cancel a batch.  Validates ownership via user_id.
        Returns a dict with 'success' and optional 'error'.
        """
        record = self.store.fetch_by_token(token_id)
        if not record:
            return {'success': False, 'error': 'Batch not found'}
        if str(record.user_id) != str(user_id):
            return {'success': False, 'error': 'You do not own this batch'}
        if record.status in (BatchStatus.COMPLETED.value, BatchStatus.CANCELLED.value):
            return {'success': False, 'error': f'Batch already {record.status}'}

        self.store.mark_cancelled(token_id)

        batch_dir = os.path.join(config.TEMP_FOLDER, f'batch_{token_id}')
        if os.path.isdir(batch_dir):
            shutil.rmtree(batch_dir, ignore_errors=True)

        return {'success': True}

    def get_user_batches(self, user_id: str, outstanding_only: bool = True) -> List[BatchRecord]:
        """Return all batch records for a user.

        Args:
            user_id: Telegram user ID.
            outstanding_only: If True, exclude COMPLETED/CANCELLED/FAILED.

        Returns:
            List of BatchRecord instances.
        """
        return self.store.fetch_by_user(str(user_id), outstanding_only)

    def get_status(self, token_id: str) -> Optional[BatchRecord]:
        """Return the current BatchRecord for a token, or None."""
        return self.store.fetch_by_token(token_id)

    @staticmethod
    def get_batch_dir(token_id: str) -> str:
        """Return the local directory path for a batch's invoice images."""
        return os.path.join(config.TEMP_FOLDER, f'batch_{token_id}')

    @staticmethod
    def list_invoice_files(token_id: str) -> List[str]:
        """Return sorted list of invoice image paths inside the batch dir."""
        batch_dir = os.path.join(config.TEMP_FOLDER, f'batch_{token_id}')
        if not os.path.isdir(batch_dir):
            return []
        files = sorted(os.listdir(batch_dir))
        return [os.path.join(batch_dir, f) for f in files if not f.startswith('.')]
