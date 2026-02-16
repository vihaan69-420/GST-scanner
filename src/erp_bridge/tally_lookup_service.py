"""
Tally Lookup Service
Optionally verifies that referenced master data (ledgers, stock items)
exists in the target Tally company before voucher creation.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from . import erp_config as cfg
from .models import InvoiceBundle
from .tally_connector import TallyConnector
from .tally_xml_builder import TallyXmlBuilder


class TallyLookupService:
    """Query Tally for ledger and stock item existence.

    Results are cached per session to minimise round-trips.
    """

    def __init__(self, connector: Optional[TallyConnector] = None) -> None:
        self.connector = connector or TallyConnector()
        self._ledger_cache: Optional[Set[str]] = None
        self._stock_cache: Optional[Set[str]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup_bundle(
        self,
        bundle: InvoiceBundle,
        company_name: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Check that all ledgers and stock items in the bundle exist.

        Returns:
            {
                "missing_ledgers": [...],
                "missing_stock_items": [...],
            }
        """
        company = (
            company_name
            or bundle.header.company_name
            or cfg.TALLY_COMPANY_NAME
        )

        needed_ledgers = self._extract_ledger_names(bundle)
        needed_stocks = self._extract_stock_names(bundle)

        missing_ledgers: List[str] = []
        missing_stocks: List[str] = []

        if needed_ledgers:
            existing = self._get_ledgers(company)
            lower_existing = {n.lower() for n in existing}
            for name in needed_ledgers:
                if name.lower() not in lower_existing:
                    missing_ledgers.append(name)

        if needed_stocks:
            existing = self._get_stock_items(company)
            lower_existing = {n.lower() for n in existing}
            for name in needed_stocks:
                if name.lower() not in lower_existing:
                    missing_stocks.append(name)

        return {
            "missing_ledgers": missing_ledgers,
            "missing_stock_items": missing_stocks,
        }

    def clear_cache(self) -> None:
        """Clear cached lookup data."""
        self._ledger_cache = None
        self._stock_cache = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_ledgers(self, company: str) -> Set[str]:
        if self._ledger_cache is not None:
            return self._ledger_cache
        xml = TallyXmlBuilder.build_ledger_list_xml(company)
        raw = self.connector.query_xml(xml)
        from .tally_response_parser import TallyResponseParser
        parser = TallyResponseParser()
        names = parser.parse_name_list(raw)
        self._ledger_cache = set(names)
        return self._ledger_cache

    def _get_stock_items(self, company: str) -> Set[str]:
        if self._stock_cache is not None:
            return self._stock_cache
        xml = TallyXmlBuilder.build_stock_item_list_xml(company)
        raw = self.connector.query_xml(xml)
        from .tally_response_parser import TallyResponseParser
        parser = TallyResponseParser()
        names = parser.parse_name_list(raw)
        self._stock_cache = set(names)
        return self._stock_cache

    @staticmethod
    def _extract_ledger_names(bundle: InvoiceBundle) -> List[str]:
        """Extract all ledger names referenced in the bundle."""
        names: List[str] = []
        hdr = bundle.header

        if hdr.party_name:
            names.append(hdr.party_name)
        if hdr.sales_ledger:
            names.append(hdr.sales_ledger)

        # Tax ledgers depend on voucher type
        from .gst_calculation import GSTCalculation
        gst = GSTCalculation()

        cgst = gst.safe_decimal(hdr.cgst_total)
        sgst = gst.safe_decimal(hdr.sgst_total)
        igst = gst.safe_decimal(hdr.igst_total)

        if hdr.voucher_type == "Purchase":
            if cgst > 0:
                names.append("Input CGST")
            if sgst > 0:
                names.append("Input SGST")
            if igst > 0:
                names.append("Input IGST")
        else:
            if cgst > 0:
                names.append("CGST")
            if sgst > 0:
                names.append("SGST")
            if igst > 0:
                names.append("IGST")

        ro = gst.safe_decimal(hdr.round_off)
        if ro != 0:
            names.append("Round Off")

        return list(dict.fromkeys(names))  # deduplicate

    @staticmethod
    def _extract_stock_names(bundle: InvoiceBundle) -> List[str]:
        """Extract stock item names (only for Sales Order)."""
        if bundle.header.voucher_type != "Sales Order":
            return []
        names: List[str] = []
        for li in bundle.line_items:
            if li.stock_item_name:
                names.append(li.stock_item_name)
        return list(dict.fromkeys(names))
