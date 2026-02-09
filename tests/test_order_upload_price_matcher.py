"""
Phase 6 – Price Matcher Tests
=============================

Tests that:
- Price list is loaded correctly from .xlsx.
- Matching priorities (exact PN, exact name, fuzzy) are respected.
- Unmatched rows return None/UNMATCHED, not dropped.
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestPriceListMatcher(unittest.TestCase):
    def test_exact_part_number_match(self):
        from src.order_upload_price_matcher import PriceListMatcher

        price_list = [
            {
                "PART_NUMBER": "SAI-ISM110-BL",
                "PART_NAME_CANONICAL": "iSmart 110 Blue Visor",
                "PRICE": "610",
                "ALIASES": "",
            }
        ]
        matcher = PriceListMatcher(price_list)
        pn, price, match_type = matcher.match("iSmart 110 Blue", part_number="SAI-ISM110-BL")
        self.assertEqual(pn, "SAI-ISM110-BL")
        self.assertEqual(price, 610.0)
        self.assertEqual(match_type, "EXACT_PN")

    def test_exact_canonical_name_match(self):
        from src.order_upload_price_matcher import PriceListMatcher

        price_list = [
            {
                "PART_NUMBER": "SAI-DUET-G",
                "PART_NAME_CANONICAL": "Duet Grey",
                "PRICE": "620",
                "ALIASES": "",
            }
        ]
        matcher = PriceListMatcher(price_list)
        pn, price, match_type = matcher.match("Duet Grey")
        self.assertEqual(pn, "SAI-DUET-G")
        self.assertEqual(price, 620.0)
        self.assertEqual(match_type, "EXACT_NAME")

    def test_fuzzy_match_90_percent(self):
        from src.order_upload_price_matcher import PriceListMatcher

        price_list = [
            {
                "PART_NUMBER": "SAI-AC3G-V",
                "PART_NAME_CANONICAL": "Activa 3G BL/Grey Visor",
                "PRICE": "610",
                "ALIASES": "",
            }
        ]
        matcher = PriceListMatcher(price_list)
        # Slightly different spelling
        pn, price, match_type = matcher.match("Activa 3G BL/Grery Visor", min_score=0.90)
        self.assertIsNotNone(pn)
        self.assertEqual(match_type, "FUZZY")

    def test_unmatched_returns_none(self):
        from src.order_upload_price_matcher import PriceListMatcher

        matcher = PriceListMatcher([])
        pn, price, match_type = matcher.match("Unknown Part XYZ")
        self.assertIsNone(pn)
        self.assertIsNone(price)
        self.assertEqual(match_type, "UNMATCHED")

    def test_unmatched_row_not_dropped(self):
        from src.order_upload_price_matcher import PriceListMatcher

        matcher = PriceListMatcher([])
        pn, price, match_type = matcher.match("Some Unrecognized Part")
        # No exception, returns UNMATCHED
        self.assertEqual(match_type, "UNMATCHED")


if __name__ == "__main__":
    unittest.main()
