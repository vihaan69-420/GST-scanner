"""
Tests for feature flag behavior

Verifies that when ENABLE_BATCH_MODE=false, no batch behavior is active.
"""
import unittest
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestFeatureFlagOff(unittest.TestCase):
    """When ENABLE_BATCH_MODE is false, batch imports and behavior must be inert."""

    @patch.dict(os.environ, {'ENABLE_BATCH_MODE': 'false'}, clear=False)
    def test_config_flag_false(self):
        import importlib
        import config
        importlib.reload(config)
        self.assertFalse(config.ENABLE_BATCH_MODE)

    @patch.dict(os.environ, {'ENABLE_BATCH_MODE': 'true'}, clear=False)
    def test_config_flag_true(self):
        import importlib
        import config
        importlib.reload(config)
        self.assertTrue(config.ENABLE_BATCH_MODE)

    @patch.dict(os.environ, {}, clear=False)
    def test_config_flag_default(self):
        os.environ.pop('ENABLE_BATCH_MODE', None)
        import importlib
        import config
        importlib.reload(config)
        self.assertFalse(config.ENABLE_BATCH_MODE)

    def test_batch_models_importable_regardless_of_flag(self):
        from batch_engine.batch_models import BatchStatus, generate_token
        self.assertIsNotNone(BatchStatus.QUEUED)

    def test_batch_config_importable_regardless_of_flag(self):
        from batch_engine.batch_config import WORKER_POLL_INTERVAL_SECONDS
        self.assertIsInstance(WORKER_POLL_INTERVAL_SECONDS, int)


if __name__ == '__main__':
    unittest.main()
