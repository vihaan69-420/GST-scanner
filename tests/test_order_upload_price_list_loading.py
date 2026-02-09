"""
Phase 6 – Price List Loading Integration Test
==============================================

Verify that:
- The configured LOCAL_PRICE_LIST_PATH points to a valid .xlsx file.
- The file can be loaded and parsed into a price list structure.
- Expected columns are present.
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestPriceListLoading(unittest.TestCase):
    def test_local_price_list_path_configured(self):
        """Verify LOCAL_PRICE_LIST_PATH is set in config."""
        from src import config
        self.assertTrue(hasattr(config, 'LOCAL_PRICE_LIST_PATH'))
        self.assertIsNotNone(config.LOCAL_PRICE_LIST_PATH)

    def test_local_price_list_file_exists(self):
        """Verify the configured price list file exists on disk."""
        from src import config
        if not config.LOCAL_PRICE_LIST_PATH:
            self.skipTest("LOCAL_PRICE_LIST_PATH not set; skipping file existence check")
        
        self.assertTrue(
            os.path.exists(config.LOCAL_PRICE_LIST_PATH),
            f"Price list file not found at: {config.LOCAL_PRICE_LIST_PATH}"
        )

    def test_load_price_list_from_xlsx(self):
        """Verify the price list can be loaded and has expected structure."""
        from src import config
        from src.order_upload_price_matcher import PriceListLoader
        
        if not config.LOCAL_PRICE_LIST_PATH:
            self.skipTest("LOCAL_PRICE_LIST_PATH not set; skipping load test")
        
        if not os.path.exists(config.LOCAL_PRICE_LIST_PATH):
            self.skipTest(f"Price list file not found at: {config.LOCAL_PRICE_LIST_PATH}")
        
        price_list = PriceListLoader.load_from_xlsx(config.LOCAL_PRICE_LIST_PATH)
        
        # Verify we got some data
        self.assertGreater(len(price_list), 0, "Price list is empty")
        
        # Verify structure
        for entry in price_list[:5]:  # Check first 5 entries
            self.assertIsInstance(entry, dict)
            # At least one of these should be present
            has_required = (
                entry.get("PART_NUMBER") or 
                entry.get("PART_NAME_CANONICAL") or 
                entry.get("PRICE")
            )
            self.assertTrue(has_required, f"Entry missing required fields: {entry}")
        
        print(f"Successfully loaded {len(price_list)} entries from price list")
        print(f"  Sample entry: {price_list[0] if price_list else 'N/A'}")


if __name__ == "__main__":
    unittest.main()
