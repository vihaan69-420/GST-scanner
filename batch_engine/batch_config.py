"""
Batch Engine Configuration

Batch-specific constants and tunables.
Separated from src/config.py to keep the batch engine self-contained.
"""

WORKER_POLL_INTERVAL_SECONDS = 30

NOTIFICATION_EVERY_N_INVOICES = 5

MAX_RETRY_PER_INVOICE = 2

RETRY_DELAY_SECONDS = 3

WORKER_IDLE_LOG_INTERVAL_SECONDS = 60

INTER_INVOICE_DELAY_SECONDS = 60

BATCH_QUEUE_COLUMNS = [
    'Token_ID',
    'Business_Type',
    'User_ID',
    'Username',
    'Created_At',
    'Status',
    'Total_Invoices',
    'Processed_Count',
    'Failed_Count',
    'Review_Count',
    'Current_Stage',
    'Last_Update',
    'Completion_Time',
    'Error_Log_JSON',
    'Retry_Count',
    'Notification_Last_Sent',
]
