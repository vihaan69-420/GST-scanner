"""
Tally Response Parser
Parse XML responses from Tally and convert to structured TallyResponse objects.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List, Optional

from .models import TallyResponse, TallyConnectionResult


class TallyResponseParser:
    """Parse Tally XML responses into structured objects."""

    # ------------------------------------------------------------------
    # Voucher import response
    # ------------------------------------------------------------------

    def parse_import_response(self, raw_xml: str) -> TallyResponse:
        """Parse a Tally voucher import response.

        Args:
            raw_xml: Raw XML string from Tally HTTP response.

        Returns:
            TallyResponse with success/failure details.
        """
        resp = TallyResponse(raw_response=raw_xml)

        if not raw_xml or not raw_xml.strip():
            resp.errors.append("Empty response from Tally")
            return resp

        try:
            root = ET.fromstring(raw_xml.strip())
        except ET.ParseError as exc:
            resp.errors.append(f"Malformed XML response: {exc}")
            return resp

        # Look for RESPONSE element (may be root or nested)
        response_el = root if root.tag == "RESPONSE" else root.find(".//RESPONSE")

        if response_el is None:
            # Some Tally versions return ENVELOPE > BODY > DATA > IMPORTRESULT
            import_result = root.find(".//IMPORTRESULT")
            if import_result is not None:
                response_el = import_result

        if response_el is None:
            # Try to extract any error info from the raw text
            self._extract_errors_from_text(raw_xml, resp)
            if not resp.errors:
                resp.errors.append(
                    "No RESPONSE element found in Tally reply"
                )
            return resp

        # Parse counts
        resp.created = self._int_text(response_el, "CREATED")
        resp.altered = self._int_text(response_el, "ALTERED")
        resp.deleted = self._int_text(response_el, "DELETED")

        # Parse voucher ID / number
        resp.voucher_id = self._text(response_el, "LASTVCHID")
        resp.voucher_number = self._text(response_el, "LASTVCHNUMBER")

        # Parse errors
        for tag in ("LINEERROR", "ERRORS", "ERROR"):
            for el in response_el.iter(tag):
                if el.text and el.text.strip():
                    resp.errors.append(el.text.strip())

        resp.success = resp.created >= 1 and len(resp.errors) == 0
        return resp

    # ------------------------------------------------------------------
    # Company list response
    # ------------------------------------------------------------------

    def parse_company_list(self, raw_xml: str) -> List[str]:
        """Extract company names from a Tally 'List of Companies' response."""
        companies: List[str] = []
        if not raw_xml:
            return companies

        try:
            root = ET.fromstring(raw_xml.strip())
        except ET.ParseError:
            return companies

        # Tally typically returns <ENVELOPE><BODY><DATA><COLLECTION>
        #   <COMPANY><NAME>...</NAME></COMPANY> ...
        for name_el in root.iter("NAME"):
            if name_el.text and name_el.text.strip():
                companies.append(name_el.text.strip())

        # Also try SVCURRENTCOMPANY or COMPANYNAME patterns
        if not companies:
            for tag in ("COMPANYNAME", "SVCURRENTCOMPANY"):
                for el in root.iter(tag):
                    if el.text and el.text.strip():
                        companies.append(el.text.strip())

        return companies

    # ------------------------------------------------------------------
    # Ledger / stock item list response
    # ------------------------------------------------------------------

    def parse_name_list(self, raw_xml: str) -> List[str]:
        """Extract names from a Tally list export (ledgers, stock items, etc.)."""
        names: List[str] = []
        if not raw_xml:
            return names

        try:
            root = ET.fromstring(raw_xml.strip())
        except ET.ParseError:
            return names

        # Tally list exports typically contain NAME elements
        for name_el in root.iter("NAME"):
            if name_el.text and name_el.text.strip():
                names.append(name_el.text.strip())

        # Also check for LEDGERNAME / STOCKITEMNAME patterns
        for tag in ("LEDGERNAME", "STOCKITEMNAME", "NAMEOFLEDGER"):
            for el in root.iter(tag):
                if el.text and el.text.strip():
                    names.append(el.text.strip())

        return list(dict.fromkeys(names))  # deduplicate preserving order

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _text(parent: ET.Element, tag: str) -> str:
        el = parent.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        return ""

    @staticmethod
    def _int_text(parent: ET.Element, tag: str) -> int:
        el = parent.find(tag)
        if el is not None and el.text:
            try:
                return int(el.text.strip())
            except ValueError:
                pass
        return 0

    @staticmethod
    def _extract_errors_from_text(raw: str, resp: TallyResponse) -> None:
        """Try to extract error messages from raw text when XML parsing fails."""
        # Look for common Tally error patterns
        patterns = [
            r"Ledger\s+\"[^\"]+\"\s+is not defined",
            r"Voucher number\s+\S+\s+already exists",
            r"Cannot\s+.*",
            r"Error\s*:\s*.*",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, raw, re.IGNORECASE)
            for m in matches:
                resp.errors.append(m.strip())
