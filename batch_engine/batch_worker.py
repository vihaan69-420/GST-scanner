#!/usr/bin/env python3
"""
Batch Worker -- Standalone Local Process

Polls the Batch_Queue Google Sheet for QUEUED batches and processes
them using the existing BatchProcessor pipeline.

Usage:
    python batch_engine/batch_worker.py

Run in a separate terminal alongside the Telegram bot.
"""
import json
import os
import shutil
import signal
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
sys.path.insert(0, PROJECT_ROOT)

import config

from batch_engine.batch_config import (
    INTER_INVOICE_DELAY_SECONDS,
    MAX_RETRY_PER_INVOICE,
    NOTIFICATION_EVERY_N_INVOICES,
    RETRY_DELAY_SECONDS,
    WORKER_IDLE_LOG_INTERVAL_SECONDS,
    WORKER_POLL_INTERVAL_SECONDS,
)
from batch_engine.batch_manager import BatchManager
from batch_engine.batch_models import BatchStatus
from batch_engine.batch_queue_store import BatchQueueStore
from batch_engine.notification_engine import NotificationEngine


_shutdown_requested = False


def _handle_signal(signum, frame):
    global _shutdown_requested
    print(f"\n[BatchWorker] Received signal {signum}, shutting down gracefully...")
    _shutdown_requested = True


def _process_batch(
    record,
    store,
    processor,
    notifier,
):
    """Process a single queued batch end-to-end."""
    token_id = record.token_id
    user_id = record.user_id
    username = record.username

    batch_dir = BatchManager.get_batch_dir(token_id)
    if not os.path.isdir(batch_dir):
        store.update_status(token_id, BatchStatus.FAILED, stage='MISSING_FILES')
        store.append_error_log(token_id, {'error': 'Batch directory not found', 'dir': batch_dir})
        notifier.send_failure(user_id, token_id, 'Batch directory not found. Were files uploaded?')
        return

    invoice_files = sorted([
        os.path.join(batch_dir, f) for f in os.listdir(batch_dir) if not f.startswith('.')
    ])
    if not invoice_files:
        store.update_status(token_id, BatchStatus.FAILED, stage='NO_INVOICES')
        store.append_error_log(token_id, {'error': 'No invoice files in batch directory'})
        notifier.send_failure(user_id, token_id, 'No invoice files found in batch.')
        return

    store.update_status(token_id, BatchStatus.PROCESSING, stage='PROCESSING')

    total = len(invoice_files)
    processed = 0
    failed = 0
    errors = []

    for idx, invoice_path in enumerate(invoice_files, 1):
        if _shutdown_requested:
            store.update_status(token_id, BatchStatus.QUEUED, stage='INTERRUPTED')
            print(f"[BatchWorker] Interrupted during {token_id}, re-queued.")
            return

        success = False
        last_error = ''
        for attempt in range(1, MAX_RETRY_PER_INVOICE + 1):
            try:
                store.update_status(
                    token_id, BatchStatus.PROCESSING,
                    stage=f'INVOICE_{idx}_OF_{total}_ATTEMPT_{attempt}',
                )
                result = processor.process_batch(
                    batch_invoices=[[invoice_path]],
                    audit_logger=None,
                    user_id=str(user_id),
                    username=username,
                )
                if result['successful'] > 0:
                    success = True
                    break
                else:
                    inv_result = result['results'][0] if result['results'] else {}
                    last_error = inv_result.get('error', 'Unknown processing error')
                    if inv_result.get('is_duplicate'):
                        break
            except Exception as e:
                last_error = str(e)

            if attempt < MAX_RETRY_PER_INVOICE:
                store.increment_retry(token_id)
                time.sleep(RETRY_DELAY_SECONDS)

        if success:
            processed += 1
            store.increment_processed(token_id)
        else:
            failed += 1
            store.increment_failed(token_id)
            error_entry = {
                'invoice_idx': idx,
                'file': os.path.basename(invoice_path),
                'error': last_error,
            }
            errors.append(error_entry)
            store.append_error_log(token_id, error_entry)

        if idx % NOTIFICATION_EVERY_N_INVOICES == 0:
            notifier.send_progress(user_id, token_id, processed + failed, total)
            store.update_notification_sent(token_id)

        if idx < total:
            time.sleep(INTER_INVOICE_DELAY_SECONDS)

    summary = {
        'total': total,
        'successful': processed,
        'failed': failed,
        'success_rate': (processed / total * 100) if total > 0 else 0,
    }

    if failed == total:
        store.update_status(token_id, BatchStatus.FAILED, stage='ALL_FAILED')
        notifier.send_failure(user_id, token_id, f'All {total} invoices failed.')
    elif failed > 0:
        store.mark_completed(token_id)
        notifier.send_completion(user_id, token_id, summary)
        notifier.send_action_required(
            user_id, token_id,
            f'{failed} of {total} invoices failed. Review the error log.',
        )
    else:
        store.mark_completed(token_id)
        notifier.send_completion(user_id, token_id, summary)

    shutil.rmtree(batch_dir, ignore_errors=True)
    print(f"[BatchWorker] Finished {token_id}: {processed}/{total} OK, {failed} failed.")


def _process_order_batch(record, store, orchestrator, notifier):
    """Process a Sales Order batch -- all files are pages of one order."""
    token_id = record.token_id
    user_id = record.user_id
    username = record.username

    batch_dir = BatchManager.get_batch_dir(token_id)
    if not os.path.isdir(batch_dir):
        store.update_status(token_id, BatchStatus.FAILED, stage='MISSING_FILES')
        store.append_error_log(token_id, {'error': 'Batch directory not found', 'dir': batch_dir})
        notifier.send_failure(user_id, token_id, 'Batch directory not found. Were files uploaded?')
        return

    page_files = sorted([
        os.path.join(batch_dir, f) for f in os.listdir(batch_dir) if not f.startswith('.')
    ])
    if not page_files:
        store.update_status(token_id, BatchStatus.FAILED, stage='NO_INVOICES')
        store.append_error_log(token_id, {'error': 'No order page files in batch directory'})
        notifier.send_failure(user_id, token_id, 'No order page files found in batch.')
        return

    store.update_status(token_id, BatchStatus.PROCESSING, stage='PROCESSING_ORDER')

    from datetime import datetime
    pages = [
        {'page_number': i, 'image_path': path, 'uploaded_at': datetime.now()}
        for i, path in enumerate(page_files, 1)
    ]

    print(f"[BatchWorker] Processing Sales Order: {len(pages)} pages as one order")

    try:
        result = orchestrator.process_order_headless(
            pages=pages,
            user_id=str(user_id),
            username=username,
        )
    except Exception as e:
        store.update_status(token_id, BatchStatus.FAILED, stage='ORDER_PROCESSING_ERROR')
        store.append_error_log(token_id, {'error': str(e)})
        notifier.send_failure(user_id, token_id, str(e))
        shutil.rmtree(batch_dir, ignore_errors=True)
        print(f"[BatchWorker] Sales Order {token_id} failed: {e}")
        return

    if result['success']:
        store.increment_processed(token_id)
        store.mark_completed(token_id)
        summary = {
            'total': 1,
            'successful': 1,
            'failed': 0,
            'success_rate': 100,
            'order_id': result.get('order_id', ''),
        }
        notifier.send_completion(user_id, token_id, summary)
        print(f"[BatchWorker] Sales Order {token_id} completed: order {result.get('order_id')}")
    else:
        store.increment_failed(token_id)
        store.update_status(token_id, BatchStatus.FAILED, stage='ORDER_FAILED')
        store.append_error_log(token_id, {'error': result.get('error', 'Unknown error')})
        notifier.send_failure(user_id, token_id, result.get('error', 'Order processing failed'))
        print(f"[BatchWorker] Sales Order {token_id} failed: {result.get('error')}")

    shutil.rmtree(batch_dir, ignore_errors=True)


def _build_pipeline():
    """Instantiate the existing processing pipeline components."""
    from ocr.ocr_engine import OCREngine
    from parsing.gst_parser import GSTParser
    from sheets.sheets_manager import SheetsManager
    from utils.batch_processor import BatchProcessor

    print("[BatchWorker] Initializing invoice pipeline...")
    ocr = OCREngine()
    parser = GSTParser()
    sheets = SheetsManager()
    processor = BatchProcessor(ocr, parser, parser.gst_validator, sheets)
    print("[BatchWorker] Invoice pipeline ready.")
    return processor


def _build_order_pipeline():
    """Instantiate the order normalization pipeline."""
    from order_normalization.orchestrator import OrderNormalizationOrchestrator

    print("[BatchWorker] Initializing order pipeline...")
    orchestrator = OrderNormalizationOrchestrator()
    print("[BatchWorker] Order pipeline ready.")
    return orchestrator


def main():
    if not config.ENABLE_BATCH_MODE:
        print("[BatchWorker] ENABLE_BATCH_MODE is false. Exiting.")
        return

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    print("=" * 60)
    print("BATCH WORKER STARTED (local mode)")
    print("=" * 60)

    processor = _build_pipeline()
    orchestrator = _build_order_pipeline() if config.FEATURE_ORDER_UPLOAD_NORMALIZATION else None
    store = BatchQueueStore()
    notifier = NotificationEngine()

    last_idle_log = 0

    while not _shutdown_requested:
        try:
            record = store.fetch_next_queued()
        except Exception as e:
            print(f"[BatchWorker] Error polling queue: {e}")
            time.sleep(WORKER_POLL_INTERVAL_SECONDS)
            continue

        if record:
            btype = record.business_type
            print(f"[BatchWorker] Picked up batch {record.token_id} "
                  f"(type={btype}, {record.total_invoices} items)")
            try:
                if btype == 'Sales' and orchestrator:
                    _process_order_batch(record, store, orchestrator, notifier)
                else:
                    _process_batch(record, store, processor, notifier)
            except Exception as e:
                print(f"[BatchWorker] Unhandled error processing {record.token_id}: {e}")
                store.update_status(record.token_id, BatchStatus.FAILED, stage='WORKER_ERROR')
                store.append_error_log(record.token_id, {'error': str(e)})
                notifier.send_failure(record.user_id, record.token_id, str(e))
        else:
            now = time.time()
            if now - last_idle_log >= WORKER_IDLE_LOG_INTERVAL_SECONDS:
                print("[BatchWorker] Idle -- no queued batches.")
                last_idle_log = now

        time.sleep(WORKER_POLL_INTERVAL_SECONDS)

    print("[BatchWorker] Shutdown complete.")


if __name__ == '__main__':
    main()
