"""
Tally Connector Service
Handles HTTP communication with Tally ERP, including retry logic
and connection testing.
"""

from __future__ import annotations

import time
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from . import erp_config as cfg
from .models import TallyConnectionResult, TallyResponse
from .tally_response_parser import TallyResponseParser


class TallyConnector:
    """HTTP connector for Tally ERP XML server."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout_connect: Optional[int] = None,
        timeout_read: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self.host = host or cfg.TALLY_HOST
        self.port = port or cfg.TALLY_PORT
        self.timeout_connect = timeout_connect or cfg.TALLY_TIMEOUT_CONNECT
        self.timeout_read = timeout_read or cfg.TALLY_TIMEOUT_READ
        self.max_retries = max_retries or cfg.TALLY_MAX_RETRIES
        self.parser = TallyResponseParser()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post_xml(self, xml_data: str) -> TallyResponse:
        """POST XML to Tally and return parsed response.

        Uses retry with exponential backoff on transient errors.
        """
        last_error: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                raw_response = self._http_post(xml_data)
                return self.parser.parse_import_response(raw_response)
            except ConnectionError as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    delay = 2 ** attempt  # 2, 4, 8 seconds
                    time.sleep(delay)
                continue
            except TimeoutError as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    delay = 2 ** attempt
                    time.sleep(delay)
                continue
            except Exception as exc:
                # Non-transient error, don't retry
                resp = TallyResponse()
                resp.errors.append(f"Unexpected error: {exc}")
                return resp

        # All retries exhausted
        resp = TallyResponse()
        resp.errors.append(
            f"Cannot connect to Tally at {self.base_url} "
            f"after {self.max_retries} retries: {last_error}"
        )
        return resp

    def query_xml(self, xml_data: str) -> str:
        """POST a query XML to Tally and return raw response string.

        Single attempt (no retry for queries).
        """
        try:
            return self._http_post(xml_data)
        except (ConnectionError, TimeoutError, Exception) as exc:
            return ""

    def test_connection(
        self,
        company_name: Optional[str] = None,
    ) -> TallyConnectionResult:
        """Test connectivity to Tally and verify company exists.

        Args:
            company_name: Company name to verify (optional).

        Returns:
            TallyConnectionResult with details.
        """
        from .tally_xml_builder import TallyXmlBuilder

        result = TallyConnectionResult(
            tally_host=self.host,
            tally_port=self.port,
            target_company=company_name or cfg.TALLY_COMPANY_NAME,
        )

        # Step 1: Test basic connectivity with company list query
        start = time.time()
        try:
            company_xml = TallyXmlBuilder.build_company_list_xml()
            raw_response = self._http_post(company_xml)
            elapsed_ms = (time.time() - start) * 1000
            result.response_time_ms = elapsed_ms
            result.connected = True
        except ConnectionError as exc:
            result.error = (
                f"Connection refused: Tally is not running or not "
                f"accepting connections on {self.base_url}"
            )
            result.error_code = "CONNECTION_REFUSED"
            result.troubleshooting = [
                "Ensure Tally is running",
                "Check that Tally's XML server is enabled "
                "(F12 > Advanced > Enable XML Server)",
                "Verify the port number matches Tally's configuration",
            ]
            return result
        except TimeoutError:
            result.error = (
                f"Connection timed out to Tally at {self.base_url}"
            )
            result.error_code = "TALLY_TIMEOUT"
            result.troubleshooting = [
                "Ensure Tally is running and responsive",
                "Check network connectivity to the Tally server",
                f"Current timeout: {self.timeout_connect}s",
            ]
            return result
        except Exception as exc:
            result.error = f"Unexpected error: {exc}"
            result.error_code = "INTERNAL_ERROR"
            return result

        # Step 2: Parse company list
        companies = self.parser.parse_company_list(raw_response)
        result.companies = companies

        # Step 3: Check if target company exists
        target = result.target_company
        if target:
            result.company_found = any(
                c.lower() == target.lower() for c in companies
            )
            if not result.company_found:
                result.error = (
                    f"Company '{target}' not found in Tally"
                )
                result.error_code = "COMPANY_NOT_FOUND"
                result.troubleshooting = [
                    "Verify the company name matches exactly (case-sensitive)",
                    "Ensure the company is loaded in Tally",
                ]
                if companies:
                    result.troubleshooting.append(
                        f"Available companies: {', '.join(companies)}"
                    )
        else:
            result.company_found = len(companies) > 0

        return result

    # ------------------------------------------------------------------
    # Internal HTTP
    # ------------------------------------------------------------------

    def _http_post(self, xml_data: str) -> str:
        """Low-level HTTP POST to Tally.

        Raises ConnectionError or TimeoutError on failure.
        """
        data = xml_data.encode("utf-8")
        req = Request(
            self.base_url,
            data=data,
            headers={
                "Content-Type": "application/xml; charset=utf-8",
                "Content-Length": str(len(data)),
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=self.timeout_read) as response:
                return response.read().decode("utf-8")
        except URLError as exc:
            if "Connection refused" in str(exc) or "Errno 111" in str(exc):
                raise ConnectionError(
                    f"Connection refused to {self.base_url}"
                ) from exc
            if "timed out" in str(exc).lower():
                raise TimeoutError(
                    f"Connection timed out to {self.base_url}"
                ) from exc
            raise ConnectionError(
                f"URL error connecting to {self.base_url}: {exc}"
            ) from exc
        except OSError as exc:
            if "timed out" in str(exc).lower():
                raise TimeoutError(
                    f"Read timed out from {self.base_url}"
                ) from exc
            raise ConnectionError(
                f"OS error connecting to {self.base_url}: {exc}"
            ) from exc
