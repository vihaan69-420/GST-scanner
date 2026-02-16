"""
Batch Engine Data Models

Pure definitions -- no side effects, no imports of external services.
"""
import random
import string
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class BatchStatus(Enum):
    """Lifecycle states for a batch job."""
    QUEUED = 'QUEUED'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    ACTION_REQUIRED = 'ACTION_REQUIRED'
    CANCELLED = 'CANCELLED'


@dataclass
class BatchRecord:
    """Represents a single row in the Batch_Queue Google Sheet tab."""
    token_id: str
    business_type: str
    user_id: str
    username: str
    created_at: str
    status: str = BatchStatus.QUEUED.value
    total_invoices: int = 0
    processed_count: int = 0
    failed_count: int = 0
    review_count: int = 0
    current_stage: str = ''
    last_update: str = ''
    completion_time: str = ''
    error_log_json: str = '[]'
    retry_count: int = 0
    notification_last_sent: str = ''

    def to_row(self):
        """Convert to a list matching BATCH_QUEUE_COLUMNS order."""
        return [
            self.token_id,
            self.business_type,
            str(self.user_id),
            self.username,
            self.created_at,
            self.status,
            str(self.total_invoices),
            str(self.processed_count),
            str(self.failed_count),
            str(self.review_count),
            self.current_stage,
            self.last_update,
            self.completion_time,
            self.error_log_json,
            str(self.retry_count),
            self.notification_last_sent,
        ]

    @classmethod
    def from_row(cls, row: list) -> 'BatchRecord':
        """Create a BatchRecord from a sheet row (list of strings)."""
        def _safe(idx, default=''):
            return row[idx] if idx < len(row) and row[idx] else default

        return cls(
            token_id=_safe(0),
            business_type=_safe(1),
            user_id=_safe(2),
            username=_safe(3),
            created_at=_safe(4),
            status=_safe(5, BatchStatus.QUEUED.value),
            total_invoices=int(_safe(6, '0')),
            processed_count=int(_safe(7, '0')),
            failed_count=int(_safe(8, '0')),
            review_count=int(_safe(9, '0')),
            current_stage=_safe(10),
            last_update=_safe(11),
            completion_time=_safe(12),
            error_log_json=_safe(13, '[]'),
            retry_count=int(_safe(14, '0')),
            notification_last_sent=_safe(15),
        )


def generate_token(user_id) -> str:
    """
    Generate a unique batch token.

    Format: BATCH-{YYYYMMDD}-{USERID}-{RANDOM6}
    Example: BATCH-20260216-51829483-A7F92K
    """
    date_part = datetime.now().strftime('%Y%m%d')
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BATCH-{date_part}-{user_id}-{random_part}"
