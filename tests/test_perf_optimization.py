"""
Unit tests for bot performance optimization.

Tests:
1. TenantManager TTL data cache (Layer 2)
2. Async method signatures in telegram_bot.py (Layer 1)
3. asyncio.to_thread wrapping in tier3_commands.py (Layer 1)

All external services (Google Sheets, Telegram, OCR) are mocked.
No files written outside /tmp. Cleanup runs even on failure.
"""
import asyncio
import time
import sys
import os
import ast
import inspect
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

# ---------------------------------------------------------------------------
# Add src/ to path so we can import project modules
# ---------------------------------------------------------------------------
SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, os.path.abspath(SRC_DIR))


# ═══════════════════════════════════════════════════════════════════════════
# Layer 2: TenantManager TTL data-cache tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTenantManagerTTLCache:
    """Test the TTL-based in-memory data cache added to TenantManager."""

    @pytest.fixture(autouse=True)
    def _patch_tenant_manager(self):
        """Create a TenantManager with fully mocked Google Sheets."""
        with patch('utils.tenant_manager.gspread') as mock_gspread, \
             patch('utils.tenant_manager.ServiceAccountCredentials') as mock_creds, \
             patch('utils.tenant_manager.config') as mock_config:

            mock_config.get_credentials_path.return_value = '/fake/creds.json'
            mock_config.GOOGLE_SHEET_ID = 'fake-sheet-id'
            mock_config.TENANT_INFO_SHEET = 'Tenant_Info'
            mock_config.DEFAULT_SUBSCRIPTION_TIER = 'free'
            mock_config.FEATURE_TENANT_SHEET_ISOLATION = False

            mock_ws = MagicMock()
            mock_ws.get_all_values.return_value = [
                ['Tenant ID', 'Tenant Name', 'Email ID', 'User ID', 'User Name',
                 'Invoice Count', 'Order Count', 'Enrollment', 'Billing',
                 'Sub Type', 'Sheet_ID', 'Sub_Plan', 'Expires', 'Razorpay'],
                ['T001', 'Alice', 'alice@test.com', '12345', 'alice_tg',
                 '5', '2', '2025-01-01', '', 'Free', '', 'free', '', ''],
            ]
            mock_ws.row_values.return_value = [
                'T001', 'Alice', 'alice@test.com', '12345', 'alice_tg',
                '5', '2', '2025-01-01', '', 'Free', '', 'free', '', ''
            ]

            mock_spreadsheet = MagicMock()
            mock_spreadsheet.worksheet.return_value = mock_ws
            mock_client = MagicMock()
            mock_client.open_by_key.return_value = mock_spreadsheet
            mock_gspread.authorize.return_value = mock_client

            from utils.tenant_manager import TenantManager
            self.tm = TenantManager()
            self.mock_ws = mock_ws
            yield

    def test_cache_hit_skips_sheets_call(self):
        """Second get_tenant within TTL must NOT call Google Sheets."""
        tenant1 = self.tm.get_tenant(12345)
        assert tenant1 is not None
        assert tenant1['tenant_name'] == 'Alice'

        self.mock_ws.row_values.reset_mock()
        self.mock_ws.get_all_values.reset_mock()

        tenant2 = self.tm.get_tenant(12345)
        assert tenant2 == tenant1
        self.mock_ws.row_values.assert_not_called()
        self.mock_ws.get_all_values.assert_not_called()

    def test_cache_expires_after_ttl(self):
        """After TTL expires, get_tenant must hit Sheets again."""
        from utils.tenant_manager import TENANT_CACHE_TTL_SECONDS

        self.tm.get_tenant(12345)
        self.mock_ws.row_values.reset_mock()

        self.tm._data_cache[12345] = (
            self.tm._data_cache[12345][0],
            time.monotonic() - TENANT_CACHE_TTL_SECONDS - 1
        )

        self.tm.get_tenant(12345)
        self.mock_ws.row_values.assert_called_once()

    def test_invalidate_cache_clears_entry(self):
        """invalidate_cache must remove the user's entry."""
        self.tm.get_tenant(12345)
        assert 12345 in self.tm._data_cache

        self.tm.invalidate_cache(12345)
        assert 12345 not in self.tm._data_cache

    def test_increment_invalidates_cache(self):
        """Incrementing a counter must invalidate the data cache."""
        self.tm.get_tenant(12345)
        assert 12345 in self.tm._data_cache

        self.mock_ws.cell.return_value = MagicMock(value='5')
        self.tm.increment_invoice_counter(12345)
        assert 12345 not in self.tm._data_cache

    def test_unknown_user_returns_none(self):
        """Querying a non-existent user returns None, no crash."""
        self.mock_ws.get_all_values.return_value = [
            ['Tenant ID', 'Tenant Name', 'Email ID', 'User ID', 'User Name',
             'Invoice Count', 'Order Count', 'Enrollment', 'Billing',
             'Sub Type', 'Sheet_ID', 'Sub_Plan', 'Expires', 'Razorpay'],
        ]
        result = self.tm.get_tenant(99999)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Layer 1: Verify async method signatures (AST-level check)
# ═══════════════════════════════════════════════════════════════════════════

class TestAsyncMethodSignatures:
    """Verify that key methods in telegram_bot.py are async."""

    @pytest.fixture(autouse=True)
    def _parse_bot(self):
        bot_path = os.path.join(SRC_DIR, 'bot', 'telegram_bot.py')
        with open(bot_path, encoding='utf-8') as f:
            self.tree = ast.parse(f.read())
        self.class_node = None
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == 'GSTScannerBot':
                self.class_node = node
                break
        assert self.class_node is not None, 'GSTScannerBot class not found'
        yield

    def _get_method(self, name):
        for item in self.class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name:
                return item
        return None

    @pytest.mark.parametrize('method_name', [
        '_ensure_tenant_manager',
        '_get_main_menu_text',
        '_get_tenant_sheet_id',
        '_check_tier_limit',
    ])
    def test_method_is_async(self, method_name):
        method = self._get_method(method_name)
        assert method is not None, f'{method_name} not found'
        assert isinstance(method, ast.AsyncFunctionDef), (
            f'{method_name} must be async def, got plain def'
        )

    def test_no_double_awaits(self):
        bot_path = os.path.join(SRC_DIR, 'bot', 'telegram_bot.py')
        with open(bot_path, encoding='utf-8') as f:
            content = f.read()
        assert 'await await' not in content, 'Found double-await bug'


# ═══════════════════════════════════════════════════════════════════════════
# Layer 1: Verify asyncio.to_thread usage in tier3_commands.py
# ═══════════════════════════════════════════════════════════════════════════

class TestTier3AsyncWrapping:
    """Verify that blocking calls in tier3_commands.py are wrapped."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = os.path.join(SRC_DIR, 'commands', 'tier3_commands.py')
        with open(path, encoding='utf-8') as f:
            self.source = f.read()
        yield

    @pytest.mark.parametrize('method_call', [
        'self.reporter.generate_processing_stats',
        'self.gstr1_exporter.export_all',
        'self.gstr1_exporter.export_b2b',
        'self.gstr1_exporter.export_b2c_small',
        'self.gstr1_exporter.export_hsn_summary',
        'self.gstr3b_generator.generate_summary',
        'self.gstr3b_generator.generate_formatted_report',
        'self.reporter.generate_gst_summary',
        'self.reporter.generate_duplicate_report',
        'self.reporter.generate_correction_analysis',
        'self.reporter.generate_comprehensive_report',
        'self.batch_processor.process_batch',
    ])
    def test_call_is_in_to_thread(self, method_call):
        """Every blocking Sheets call must appear inside asyncio.to_thread."""
        occurrences = self.source.count(method_call)
        assert occurrences > 0, f'{method_call} not found in source'

        lines = self.source.split('\n')
        for i, line in enumerate(lines):
            if method_call in line:
                context = '\n'.join(lines[max(0, i-2):i+1])
                assert 'asyncio.to_thread' in context, (
                    f'{method_call} at line {i+1} is NOT inside asyncio.to_thread:\n{context}'
                )
