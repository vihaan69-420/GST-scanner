"""
Comprehensive tests for the ERP Bridge module.
Tests cover all modules: schema validation, CSV loading, validation engine,
GST calculation, XML builder, response parser, audit logger, batch processor,
and MCP tool endpoints.
"""

import json
import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from erp_bridge import erp_config as cfg
from erp_bridge.csv_loader_service import CsvLoaderService
from erp_bridge.csv_schema_validator import CsvSchemaValidator
from erp_bridge.erp_audit_logger import ErpAuditLogger
from erp_bridge.erp_batch_processor import ErpBatchProcessor
from erp_bridge.erp_validation_engine import ErpValidationEngine
from erp_bridge.gst_calculation import GSTCalculation
from erp_bridge.models import (
    BatchResult,
    CsvValidationReport,
    InvoiceBundle,
    InvoiceHeader,
    InvoiceResult,
    LineItem,
    TallyConnectionResult,
    TallyResponse,
    ValidationResult,
)
from erp_bridge.tally_response_parser import TallyResponseParser
from erp_bridge.tally_xml_builder import TallyXmlBuilder

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Ensure erp_bridge resolves to the src package, not this test directory
if "erp_bridge" in sys.modules:
    del sys.modules["erp_bridge"]


# ======================================================================
# Test: Models
# ======================================================================


class TestModels(unittest.TestCase):
    """Test dataclass models and their serialization."""

    def test_validation_result_ok(self):
        vr = ValidationResult()
        self.assertTrue(vr.valid)
        self.assertEqual(vr.status, "OK")

    def test_validation_result_error(self):
        vr = ValidationResult()
        vr.add_error("bad field", row=1, column="X")
        self.assertFalse(vr.valid)
        self.assertEqual(vr.status, "ERROR")
        self.assertEqual(len(vr.errors), 1)

    def test_validation_result_warning_only(self):
        vr = ValidationResult()
        vr.add_warning("minor issue")
        self.assertTrue(vr.valid)
        self.assertEqual(vr.status, "WARNING")

    def test_invoice_result_to_dict(self):
        ir = InvoiceResult(
            invoice_no="INV-001",
            voucher_type="Sales",
            status="SUCCESS",
            tally_voucher_id="123",
        )
        d = ir.to_dict()
        self.assertEqual(d["invoice_no"], "INV-001")
        self.assertEqual(d["status"], "SUCCESS")
        self.assertIn("tally_voucher_id", d)

    def test_batch_result_to_dict(self):
        br = BatchResult(total_invoices=1, successful=1)
        d = br.to_dict()
        self.assertTrue(d["success"])
        self.assertIn("summary", d)
        self.assertEqual(d["summary"]["total_invoices"], 1)

    def test_batch_result_error_to_dict(self):
        br = BatchResult(error="something failed", error_code="INTERNAL_ERROR")
        d = br.to_dict()
        self.assertFalse(d["success"])
        self.assertIn("error", d)
        self.assertNotIn("summary", d)

    def test_tally_response_to_dict(self):
        tr = TallyResponse(success=True, created=1, voucher_id="42")
        d = tr.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["created"], 1)

    def test_tally_connection_result_to_dict(self):
        cr = TallyConnectionResult(
            connected=True,
            tally_host="localhost",
            tally_port=9000,
            response_time_ms=50.0,
            companies=["Test Co"],
            target_company="Test Co",
            company_found=True,
        )
        d = cr.to_dict()
        self.assertTrue(d["success"])
        self.assertTrue(d["connected"])


# ======================================================================
# Test: CSV Schema Validator
# ======================================================================


class TestCsvSchemaValidator(unittest.TestCase):
    """Test CSV schema validation."""

    def setUp(self):
        self.validator = CsvSchemaValidator()

    def test_valid_summary_csv(self):
        path = str(FIXTURES_DIR / "valid_summary.csv")
        rows, errors = self.validator.validate_summary_csv(path)
        schema_errors = [e for e in errors if e.severity == "ERROR"]
        self.assertEqual(len(schema_errors), 0, f"Unexpected errors: {[e.message for e in schema_errors]}")
        self.assertEqual(len(rows), 3)

    def test_valid_items_csv(self):
        path = str(FIXTURES_DIR / "valid_items.csv")
        rows, errors = self.validator.validate_items_csv(path)
        schema_errors = [e for e in errors if e.severity == "ERROR"]
        self.assertEqual(len(schema_errors), 0, f"Unexpected errors: {[e.message for e in schema_errors]}")
        self.assertEqual(len(rows), 4)

    def test_bad_summary_csv(self):
        path = str(FIXTURES_DIR / "bad_summary.csv")
        rows, errors = self.validator.validate_summary_csv(path)
        # Should have errors for: invalid voucher type, bad date, bad GSTIN,
        # bad state code, bad boolean
        error_cols = {e.column for e in errors if e.severity == "ERROR"}
        self.assertIn("Voucher_Type", error_cols)
        self.assertIn("Invoice_Date", error_cols)
        self.assertIn("Party_GSTIN", error_cols)
        self.assertIn("Party_State_Code", error_cols)

    def test_bad_items_csv(self):
        path = str(FIXTURES_DIR / "bad_items.csv")
        rows, errors = self.validator.validate_items_csv(path)
        error_cols = {e.column for e in errors if e.severity == "ERROR"}
        self.assertIn("Line_No", error_cols)
        self.assertIn("HSN_SAC", error_cols)
        self.assertIn("GST_Rate", error_cols)
        self.assertIn("UOM", error_cols)

    def test_missing_columns(self):
        path = str(FIXTURES_DIR / "missing_columns_summary.csv")
        rows, errors = self.validator.validate_summary_csv(path)
        self.assertTrue(len(errors) > 0)
        self.assertIn("missing required columns", errors[0].message.lower())

    def test_file_not_found(self):
        ok, errors = self.validator.validate_file_basics(
            "/nonexistent/file.csv", "Test"
        )
        self.assertFalse(ok)
        self.assertIn("not found", errors[0].message.lower())

    def test_non_csv_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            tmp = f.name
        try:
            ok, errors = self.validator.validate_file_basics(tmp, "Test")
            self.assertFalse(ok)
            self.assertIn(".csv", errors[0].message.lower())
        finally:
            os.unlink(tmp)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(
            suffix=".csv", delete=False, mode="w"
        ) as f:
            tmp = f.name
        try:
            ok, errors = self.validator.validate_file_basics(tmp, "Test")
            self.assertFalse(ok)
            self.assertIn("empty", errors[0].message.lower())
        finally:
            os.unlink(tmp)


# ======================================================================
# Test: CSV Loader Service
# ======================================================================


class TestCsvLoaderService(unittest.TestCase):
    """Test CSV loading and joining."""

    def setUp(self):
        self.loader = CsvLoaderService()
        self.validator = CsvSchemaValidator()

    def test_load_valid_files(self):
        summary_rows, _ = self.validator.validate_summary_csv(
            str(FIXTURES_DIR / "valid_summary.csv")
        )
        items_rows, _ = self.validator.validate_items_csv(
            str(FIXTURES_DIR / "valid_items.csv")
        )
        bundles, warnings = self.loader.load(summary_rows, items_rows)

        self.assertEqual(len(bundles), 3)
        self.assertEqual(bundles[0].header.invoice_no, "INV-2026-001")
        self.assertEqual(len(bundles[0].line_items), 2)
        self.assertEqual(len(bundles[1].line_items), 1)
        self.assertEqual(len(bundles[2].line_items), 1)

    def test_orphan_line_items(self):
        summary_rows = [
            {"Invoice_No": "INV-001", "Voucher_Type": "Sales",
             "Invoice_Date": "01/01/2026", "Party_Name": "Test",
             "Party_State_Code": "29", "Place_Of_Supply": "29",
             "Sales_Ledger": "Sales", "Invoice_Value": "1000",
             "Total_Taxable_Value": "1000"}
        ]
        items_rows = [
            {"Invoice_No": "INV-ORPHAN", "Line_No": "1",
             "Item_Description": "X", "HSN_SAC": "1234",
             "Taxable_Value": "1000", "GST_Rate": "18"}
        ]
        bundles, warnings = self.loader.load(summary_rows, items_rows)
        warning_msgs = [w.message for w in warnings]
        self.assertTrue(
            any("INV-ORPHAN" in m and "does not exist" in m for m in warning_msgs)
        )

    def test_duplicate_invoice_no(self):
        summary_rows = [
            {"Invoice_No": "INV-DUP", "Voucher_Type": "Sales",
             "Invoice_Date": "01/01/2026", "Party_Name": "Test",
             "Party_State_Code": "29", "Place_Of_Supply": "29",
             "Sales_Ledger": "Sales", "Invoice_Value": "1000",
             "Total_Taxable_Value": "1000"},
            {"Invoice_No": "INV-DUP", "Voucher_Type": "Sales",
             "Invoice_Date": "01/01/2026", "Party_Name": "Test2",
             "Party_State_Code": "29", "Place_Of_Supply": "29",
             "Sales_Ledger": "Sales", "Invoice_Value": "2000",
             "Total_Taxable_Value": "2000"},
        ]
        bundles, warnings = self.loader.load(summary_rows, [])
        self.assertEqual(len(bundles), 1)
        self.assertTrue(any("Duplicate" in w.message for w in warnings))


# ======================================================================
# Test: GST Calculation
# ======================================================================


class TestGSTCalculation(unittest.TestCase):
    """Test GST calculation and verification logic."""

    def setUp(self):
        self.gst = GSTCalculation()

    def test_safe_decimal(self):
        self.assertEqual(self.gst.safe_decimal("100.50"), Decimal("100.50"))
        self.assertEqual(self.gst.safe_decimal(""), Decimal("0"))
        self.assertEqual(self.gst.safe_decimal("abc"), Decimal("0"))
        self.assertEqual(self.gst.safe_decimal("1,000.00"), Decimal("1000.00"))

    def test_is_intra_state(self):
        self.assertTrue(self.gst.is_intra_state("29", "29"))
        self.assertFalse(self.gst.is_intra_state("29", "07"))
        self.assertFalse(self.gst.is_intra_state("", "29"))

    def test_expected_cgst_sgst(self):
        cgst, sgst = self.gst.expected_cgst_sgst(Decimal("10000"), Decimal("18"))
        self.assertEqual(cgst, Decimal("900.00"))
        self.assertEqual(sgst, Decimal("900.00"))

    def test_expected_igst(self):
        igst = self.gst.expected_igst(Decimal("5000"), Decimal("12"))
        self.assertEqual(igst, Decimal("600.00"))

    def test_verify_line_item_intra_ok(self):
        errs, warns = self.gst.verify_line_item(
            "10000", "18", "900", "900", "0", True
        )
        self.assertEqual(len(errs), 0)
        self.assertEqual(len(warns), 0)

    def test_verify_line_item_inter_ok(self):
        errs, warns = self.gst.verify_line_item(
            "5000", "12", "0", "0", "600", False
        )
        self.assertEqual(len(errs), 0)
        self.assertEqual(len(warns), 0)

    def test_verify_line_item_wrong_tax_type(self):
        errs, warns = self.gst.verify_line_item(
            "10000", "18", "900", "900", "500", True
        )
        self.assertTrue(len(errs) > 0)

    def test_verify_invoice_value_ok(self):
        errs, warns = self.gst.verify_invoice_value(
            "11800", "10000", "900", "900", "0", "0", "0"
        )
        self.assertEqual(len(errs), 0)

    def test_verify_invoice_value_mismatch(self):
        errs, warns = self.gst.verify_invoice_value(
            "12000", "10000", "900", "900", "0", "0", "0"
        )
        self.assertTrue(len(errs) > 0)

    def test_verify_tax_type_consistency_intra(self):
        errs, warns = self.gst.verify_tax_type_consistency(
            "29", "29", "900", "900", "0"
        )
        self.assertEqual(len(errs), 0)

    def test_verify_tax_type_consistency_both(self):
        errs, warns = self.gst.verify_tax_type_consistency(
            "29", "29", "900", "900", "600"
        )
        self.assertTrue(len(errs) > 0)


# ======================================================================
# Test: ERP Validation Engine
# ======================================================================


class TestErpValidationEngine(unittest.TestCase):
    """Test business rule validation on InvoiceBundles."""

    def setUp(self):
        self.engine = ErpValidationEngine()

    def _make_bundle(self, **hdr_overrides) -> InvoiceBundle:
        hdr_defaults = {
            "voucher_type": "Sales",
            "invoice_no": "INV-001",
            "invoice_date": "14/02/2026",
            "party_name": "Test Co",
            "party_gstin": "29AABCU9603R1ZP",
            "party_state_code": "29",
            "place_of_supply": "29",
            "sales_ledger": "Sales - 18%",
            "invoice_value": "11800",
            "total_taxable_value": "10000",
            "cgst_total": "900",
            "sgst_total": "900",
            "igst_total": "0",
            "cess_total": "0",
            "round_off": "0",
        }
        hdr_defaults.update(hdr_overrides)
        header = InvoiceHeader(**hdr_defaults)
        items = [
            LineItem(
                invoice_no="INV-001",
                line_no=1,
                item_description="Widget",
                hsn_sac="84714190",
                qty="100",
                uom="PCS",
                rate="100",
                taxable_value="10000",
                gst_rate="18",
                cgst_rate="9",
                cgst_amount="900",
                sgst_rate="9",
                sgst_amount="900",
                igst_rate="0",
                igst_amount="0",
            )
        ]
        return InvoiceBundle(header=header, line_items=items)

    def test_valid_bundle(self):
        bundle = self._make_bundle()
        result = self.engine.validate_bundle(bundle)
        self.assertTrue(result.valid, f"Errors: {[e.message for e in result.errors]}")

    def test_invoice_value_mismatch(self):
        bundle = self._make_bundle(invoice_value="99999")
        result = self.engine.validate_bundle(bundle)
        self.assertFalse(result.valid)
        self.assertTrue(
            any("Invoice value mismatch" in e.message for e in result.errors)
        )

    def test_taxable_value_mismatch(self):
        bundle = self._make_bundle(total_taxable_value="5000")
        result = self.engine.validate_bundle(bundle)
        self.assertFalse(result.valid)

    def test_tax_type_intra_with_igst(self):
        bundle = self._make_bundle(igst_total="500")
        result = self.engine.validate_bundle(bundle)
        self.assertFalse(result.valid)

    def test_negative_invoice_value(self):
        bundle = self._make_bundle(invoice_value="-100")
        result = self.engine.validate_bundle(bundle)
        self.assertFalse(result.valid)

    def test_sales_order_missing_stock_item(self):
        bundle = self._make_bundle(voucher_type="Sales Order")
        # Items don't have stock_item_name
        result = self.engine.validate_bundle(bundle)
        self.assertFalse(result.valid)
        self.assertTrue(
            any("Stock_Item_Name" in e.message for e in result.errors)
        )


# ======================================================================
# Test: Tally XML Builder
# ======================================================================


class TestTallyXmlBuilder(unittest.TestCase):
    """Test Tally XML generation."""

    def setUp(self):
        self.builder = TallyXmlBuilder()

    def _make_bundle(self, voucher_type="Sales") -> InvoiceBundle:
        header = InvoiceHeader(
            voucher_type=voucher_type,
            invoice_no="INV-TEST-001",
            invoice_date="14/02/2026",
            party_name="ABC Trading Co",
            party_gstin="29AABCU9603R1ZP",
            party_state_code="29",
            place_of_supply="29",
            sales_ledger="Sales - GST 18%",
            invoice_value="11800",
            total_taxable_value="10000",
            cgst_total="900",
            sgst_total="900",
            igst_total="0",
            cess_total="0",
            round_off="0",
            narration="Test invoice",
            company_name="Test Company",
        )
        items = [
            LineItem(
                invoice_no="INV-TEST-001",
                line_no=1,
                item_description="Widget",
                hsn_sac="84714190",
                qty="100",
                uom="PCS",
                rate="100",
                taxable_value="10000",
                gst_rate="18",
                cgst_rate="9",
                cgst_amount="900",
                sgst_rate="9",
                sgst_amount="900",
                stock_item_name="Widget" if voucher_type == "Sales Order" else "",
                godown="Main Godown" if voucher_type == "Sales Order" else "",
            )
        ]
        return InvoiceBundle(header=header, line_items=items)

    def test_sales_invoice_xml(self):
        bundle = self._make_bundle("Sales")
        xml = self.builder.build_voucher_xml(bundle)
        self.assertIn('VCHTYPE="Sales"', xml)
        self.assertIn("ACTION=\"Create\"", xml)
        self.assertIn("<VOUCHERNUMBER>INV-TEST-001</VOUCHERNUMBER>", xml)
        self.assertIn("<PARTYLEDGERNAME>ABC Trading Co</PARTYLEDGERNAME>", xml)
        self.assertIn("<ISINVOICE>Yes</ISINVOICE>", xml)
        self.assertIn("<LEDGERNAME>CGST</LEDGERNAME>", xml)
        self.assertIn("<LEDGERNAME>SGST</LEDGERNAME>", xml)
        self.assertIn("<DATE>20260214</DATE>", xml)
        self.assertIn("<HSNCODE>84714190</HSNCODE>", xml)

    def test_purchase_invoice_xml(self):
        bundle = self._make_bundle("Purchase")
        xml = self.builder.build_voucher_xml(bundle)
        self.assertIn('VCHTYPE="Purchase"', xml)
        self.assertIn("<LEDGERNAME>Input CGST</LEDGERNAME>", xml)
        self.assertIn("<LEDGERNAME>Input SGST</LEDGERNAME>", xml)

    def test_sales_order_xml(self):
        bundle = self._make_bundle("Sales Order")
        xml = self.builder.build_voucher_xml(bundle)
        self.assertIn('VCHTYPE="Sales Order"', xml)
        self.assertIn("<ISINVOICE>No</ISINVOICE>", xml)
        self.assertIn("<STOCKITEMNAME>Widget</STOCKITEMNAME>", xml)
        self.assertIn("ALLINVENTORYENTRIES.LIST", xml)

    def test_xml_escaping(self):
        bundle = self._make_bundle("Sales")
        bundle.header.party_name = "A & B <Corp>"
        xml = self.builder.build_voucher_xml(bundle)
        self.assertIn("A &amp; B &lt;Corp&gt;", xml)

    def test_date_conversion(self):
        self.assertEqual(
            TallyXmlBuilder._date_to_tally("14/02/2026"), "20260214"
        )
        self.assertEqual(
            TallyXmlBuilder._date_to_tally("01/01/2025"), "20250101"
        )
        self.assertEqual(TallyXmlBuilder._date_to_tally(""), "")

    def test_unsupported_voucher_type(self):
        bundle = self._make_bundle("Sales")
        bundle.header.voucher_type = "Credit Note"
        with self.assertRaises(ValueError):
            self.builder.build_voucher_xml(bundle)

    def test_company_list_xml(self):
        xml = TallyXmlBuilder.build_company_list_xml()
        self.assertIn("List of Companies", xml)
        self.assertIn("Export Data", xml)

    def test_ledger_list_xml(self):
        xml = TallyXmlBuilder.build_ledger_list_xml("My Co")
        self.assertIn("List of Ledgers", xml)
        self.assertIn("<SVCURRENTCOMPANY>My Co</SVCURRENTCOMPANY>", xml)


# ======================================================================
# Test: Tally Response Parser
# ======================================================================


class TestTallyResponseParser(unittest.TestCase):
    """Test Tally XML response parsing."""

    def setUp(self):
        self.parser = TallyResponseParser()

    def test_parse_success(self):
        xml = """
        <RESPONSE>
            <CREATED>1</CREATED>
            <ALTERED>0</ALTERED>
            <DELETED>0</DELETED>
            <LASTVCHID>12345</LASTVCHID>
            <LASTVCHNUMBER>INV-001</LASTVCHNUMBER>
        </RESPONSE>
        """
        resp = self.parser.parse_import_response(xml)
        self.assertTrue(resp.success)
        self.assertEqual(resp.created, 1)
        self.assertEqual(resp.voucher_id, "12345")
        self.assertEqual(resp.voucher_number, "INV-001")

    def test_parse_error(self):
        xml = """
        <RESPONSE>
            <CREATED>0</CREATED>
            <LINEERROR>Ledger "XYZ" is not defined</LINEERROR>
        </RESPONSE>
        """
        resp = self.parser.parse_import_response(xml)
        self.assertFalse(resp.success)
        self.assertEqual(resp.created, 0)
        self.assertTrue(len(resp.errors) > 0)
        self.assertIn("not defined", resp.errors[0])

    def test_parse_empty(self):
        resp = self.parser.parse_import_response("")
        self.assertFalse(resp.success)
        self.assertTrue(len(resp.errors) > 0)

    def test_parse_malformed_xml(self):
        resp = self.parser.parse_import_response("<broken>xml")
        self.assertFalse(resp.success)

    def test_parse_company_list(self):
        xml = """
        <ENVELOPE>
            <BODY><DATA><COLLECTION>
                <COMPANY><NAME>Company A</NAME></COMPANY>
                <COMPANY><NAME>Company B</NAME></COMPANY>
            </COLLECTION></DATA></BODY>
        </ENVELOPE>
        """
        companies = self.parser.parse_company_list(xml)
        self.assertIn("Company A", companies)
        self.assertIn("Company B", companies)

    def test_parse_name_list(self):
        xml = """
        <ENVELOPE>
            <BODY><DATA><COLLECTION>
                <LEDGER><NAME>Sales</NAME></LEDGER>
                <LEDGER><NAME>CGST</NAME></LEDGER>
            </COLLECTION></DATA></BODY>
        </ENVELOPE>
        """
        names = self.parser.parse_name_list(xml)
        self.assertIn("Sales", names)
        self.assertIn("CGST", names)


# ======================================================================
# Test: Audit Logger
# ======================================================================


class TestErpAuditLogger(unittest.TestCase):
    """Test audit logging."""

    def test_mask_gstin(self):
        # Mask replaces indices 6-9 (4 chars) with ****
        # 29AABCU9603R1ZP -> 29AABC****3R1ZP
        self.assertEqual(
            ErpAuditLogger._mask_gstin("29AABCU9603R1ZP"),
            "29AABC****3R1ZP",
        )
        self.assertEqual(ErpAuditLogger._mask_gstin(""), "")
        self.assertEqual(ErpAuditLogger._mask_gstin("SHORT"), "SHORT")

    def test_log_invoice_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ErpAuditLogger(log_dir=tmpdir)
            result = InvoiceResult(
                invoice_no="INV-001",
                voucher_type="Sales",
                status="SUCCESS",
                processing_time_seconds=1.5,
            )
            logger.log_invoice(
                batch_id="test-batch",
                invoice_result=result,
                source_file="test.csv",
                party_gstin="29AABCU9603R1ZP",
            )

            # Check log file was created
            log_file = os.path.join(tmpdir, "erp_bridge_audit.log")
            self.assertTrue(os.path.exists(log_file))
            with open(log_file) as f:
                content = f.read()
            self.assertIn("INV-001", content)
            self.assertIn("29AABC****3R1ZP", content)

    def test_write_batch_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ErpAuditLogger(log_dir=tmpdir)
            batch = BatchResult(
                total_invoices=1,
                successful=1,
            )
            path = logger.write_batch_log(batch)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                data = json.load(f)
            self.assertTrue(data["success"])


# ======================================================================
# Test: Batch Processor (with mocked Tally)
# ======================================================================


class TestErpBatchProcessor(unittest.TestCase):
    """Test batch processing with mocked Tally connector."""

    def _make_bundle(self) -> InvoiceBundle:
        header = InvoiceHeader(
            voucher_type="Sales",
            invoice_no="INV-BATCH-001",
            invoice_date="14/02/2026",
            party_name="Test Co",
            party_gstin="29AABCU9603R1ZP",
            party_state_code="29",
            place_of_supply="29",
            sales_ledger="Sales",
            invoice_value="11800",
            total_taxable_value="10000",
            cgst_total="900",
            sgst_total="900",
            igst_total="0",
            cess_total="0",
            round_off="0",
        )
        items = [
            LineItem(
                invoice_no="INV-BATCH-001",
                line_no=1,
                item_description="Widget",
                hsn_sac="84714190",
                qty="100",
                uom="PCS",
                rate="100",
                taxable_value="10000",
                gst_rate="18",
                cgst_rate="9",
                cgst_amount="900",
                sgst_rate="9",
                sgst_amount="900",
            )
        ]
        return InvoiceBundle(header=header, line_items=items)

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = ErpAuditLogger(log_dir=tmpdir)
            processor = ErpBatchProcessor(audit_logger=audit)
            bundles = [self._make_bundle()]
            result = processor.process_batch(
                bundles, dry_run=True, source_file="test.csv"
            )
            self.assertEqual(result.total_invoices, 1)
            self.assertEqual(result.successful, 1)
            self.assertEqual(result.results[0].status, "VALID")
            self.assertIn("VOUCHER", result.results[0].xml_preview)

    def test_intra_batch_dedup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = ErpAuditLogger(log_dir=tmpdir)
            processor = ErpBatchProcessor(audit_logger=audit)
            bundle1 = self._make_bundle()
            bundle2 = self._make_bundle()  # same invoice
            result = processor.process_batch(
                [bundle1, bundle2],
                dry_run=True,
                skip_duplicates=True,
                source_file="test.csv",
            )
            self.assertEqual(result.total_invoices, 2)
            self.assertEqual(result.skipped_duplicates, 1)

    def test_validation_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = ErpAuditLogger(log_dir=tmpdir)
            processor = ErpBatchProcessor(audit_logger=audit)
            bundle = self._make_bundle()
            bundle.header.invoice_value = "99999"  # mismatch
            result = processor.process_batch(
                [bundle], dry_run=True, source_file="test.csv"
            )
            self.assertEqual(result.failed, 1)
            self.assertIn("INVALID", result.results[0].status)

    @patch("erp_bridge.erp_batch_processor.cfg")
    def test_progress_callback(self, mock_cfg):
        mock_cfg.ENABLE_TALLY_LOOKUP = False
        mock_cfg.TALLY_REQUEST_DELAY_MS = 0
        mock_cfg.ROUNDING_TOLERANCE = "0.50"
        mock_cfg.INVOICE_VALUE_TOLERANCE = "1.00"

        with tempfile.TemporaryDirectory() as tmpdir:
            audit = ErpAuditLogger(log_dir=tmpdir)
            processor = ErpBatchProcessor(audit_logger=audit)
            calls = []

            def cb(current, total, msg):
                calls.append((current, total, msg))

            bundle = self._make_bundle()
            processor.process_batch(
                [bundle], dry_run=True, progress_callback=cb, source_file="test.csv"
            )
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], 1)
            self.assertEqual(calls[0][1], 1)


# ======================================================================
# Test: MCP Tools
# ======================================================================


class TestMcpTools(unittest.TestCase):
    """Test MCP tool endpoints."""

    @patch("erp_bridge.mcp_tools.cfg")
    def test_feature_disabled(self, mock_cfg):
        mock_cfg.ENABLE_ERP_BRIDGE = False
        from erp_bridge.mcp_tools import csv_to_tally, validate_csv, tally_connection_test

        result = csv_to_tally("a.csv", "b.csv")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "FEATURE_DISABLED")

        result = validate_csv("a.csv", "b.csv")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "FEATURE_DISABLED")

        result = tally_connection_test()
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "FEATURE_DISABLED")

    @patch("erp_bridge.mcp_tools.cfg")
    def test_csv_to_tally_file_not_found(self, mock_cfg):
        mock_cfg.ENABLE_ERP_BRIDGE = True
        mock_cfg.MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
        mock_cfg.MAX_FILE_SIZE_MB = 5
        from erp_bridge.mcp_tools import csv_to_tally

        result = csv_to_tally("/nonexistent/summary.csv", "/nonexistent/items.csv")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"].lower())

    def test_validate_csv_valid(self):
        """Test validate_csv with valid CSV files using real config."""
        # Temporarily enable the feature flag
        original = cfg.ENABLE_ERP_BRIDGE
        cfg.ENABLE_ERP_BRIDGE = True
        try:
            # Need to also patch the cfg reference inside mcp_tools
            import erp_bridge.mcp_tools as mcp_mod
            original_mcp = mcp_mod.cfg.ENABLE_ERP_BRIDGE
            mcp_mod.cfg.ENABLE_ERP_BRIDGE = True

            result = mcp_mod.validate_csv(
                str(FIXTURES_DIR / "valid_summary.csv"),
                str(FIXTURES_DIR / "valid_items.csv"),
            )
            self.assertTrue(result["success"])
            self.assertTrue(result["valid"])
            self.assertEqual(result["summary_file"]["rows"], 3)
            self.assertEqual(result["items_file"]["rows"], 4)
        finally:
            cfg.ENABLE_ERP_BRIDGE = original
            mcp_mod.cfg.ENABLE_ERP_BRIDGE = original


# ======================================================================
# Test: No regression on existing modules
# ======================================================================


class TestNoRegression(unittest.TestCase):
    """Verify that the ERP Bridge has zero imports from existing modules."""

    def test_no_imports_from_existing_src(self):
        """Ensure no erp_bridge module imports from src.parsing, src.features, etc."""
        import importlib
        import pkgutil

        erp_bridge_dir = PROJECT_ROOT / "src" / "erp_bridge"
        forbidden_prefixes = ("parsing.", "features.", "bot.", "ocr.", "sheets.",
                              "commands.", "utils.")

        for _, module_name, _ in pkgutil.iter_modules([str(erp_bridge_dir)]):
            full_name = f"erp_bridge.{module_name}"
            try:
                mod = importlib.import_module(full_name)
            except Exception:
                continue

            source_file = getattr(mod, "__file__", "")
            if not source_file:
                continue

            with open(source_file) as f:
                source = f.read()

            for prefix in forbidden_prefixes:
                self.assertNotIn(
                    f"from {prefix}",
                    source,
                    f"{full_name} imports from forbidden module {prefix}",
                )
                self.assertNotIn(
                    f"import {prefix}",
                    source,
                    f"{full_name} imports from forbidden module {prefix}",
                )


if __name__ == "__main__":
    unittest.main()
