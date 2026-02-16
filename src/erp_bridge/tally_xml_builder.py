"""
Tally XML Builder
Generates Tally-compatible XML vouchers from InvoiceBundle data.
Supports Sales Invoice, Purchase Invoice, and Sales Order.

All XML is built using xml.etree.ElementTree for proper escaping.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional

from . import erp_config as cfg
from .gst_calculation import GSTCalculation
from .models import InvoiceBundle, LineItem


class TallyXmlBuilder:
    """Build Tally XML import envelopes for voucher creation."""

    def __init__(self) -> None:
        self.gst = GSTCalculation()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_voucher_xml(
        self,
        bundle: InvoiceBundle,
        company_name: Optional[str] = None,
    ) -> str:
        """Build complete Tally XML envelope for one invoice.

        Args:
            bundle: InvoiceBundle containing header + line items.
            company_name: Tally company name override.

        Returns:
            XML string ready for HTTP POST to Tally.
        """
        company = company_name or bundle.header.company_name or cfg.TALLY_COMPANY_NAME
        vtype = bundle.header.voucher_type

        envelope = self._build_envelope(company)
        request_data = envelope.find(".//REQUESTDATA")
        tally_msg = ET.SubElement(request_data, "TALLYMESSAGE")
        tally_msg.set("xmlns:UDF", "TallyUDF")

        if vtype == "Sales":
            self._build_sales_voucher(tally_msg, bundle)
        elif vtype == "Purchase":
            self._build_purchase_voucher(tally_msg, bundle)
        elif vtype == "Sales Order":
            self._build_sales_order_voucher(tally_msg, bundle)
        else:
            raise ValueError(f"Unsupported voucher type: {vtype}")

        return self._to_xml_string(envelope)

    # ------------------------------------------------------------------
    # Envelope
    # ------------------------------------------------------------------

    @staticmethod
    def _build_envelope(company_name: str) -> ET.Element:
        envelope = ET.Element("ENVELOPE")

        header = ET.SubElement(envelope, "HEADER")
        ET.SubElement(header, "TALLYREQUEST").text = "Import Data"

        body = ET.SubElement(envelope, "BODY")
        import_data = ET.SubElement(body, "IMPORTDATA")

        req_desc = ET.SubElement(import_data, "REQUESTDESC")
        ET.SubElement(req_desc, "REPORTNAME").text = "Vouchers"

        static_vars = ET.SubElement(req_desc, "STATICVARIABLES")
        ET.SubElement(static_vars, "SVCURRENTCOMPANY").text = company_name

        ET.SubElement(import_data, "REQUESTDATA")

        return envelope

    # ------------------------------------------------------------------
    # Sales Invoice
    # ------------------------------------------------------------------

    def _build_sales_voucher(
        self, parent: ET.Element, bundle: InvoiceBundle
    ) -> None:
        hdr = bundle.header
        voucher = ET.SubElement(parent, "VOUCHER")
        voucher.set("VCHTYPE", "Sales")
        voucher.set("ACTION", "Create")
        voucher.set("OBJVIEW", "Invoice Voucher View")

        self._add_common_header(voucher, hdr, "Sales")

        inv_val = self.gst.safe_decimal(hdr.invoice_value)

        # Party ledger (Debit)
        self._add_ledger_entry(
            voucher,
            ledger_name=hdr.party_name,
            amount=-inv_val,
            is_deemed_positive=True,
        )

        # Sales ledger (Credit)
        taxable = self.gst.safe_decimal(hdr.total_taxable_value)
        sales_entry = self._add_ledger_entry(
            voucher,
            ledger_name=hdr.sales_ledger,
            amount=taxable,
            is_deemed_positive=False,
        )
        self._add_gst_override(sales_entry, bundle, hdr.reverse_charge)

        # Tax ledger entries
        self._add_sales_tax_entries(voucher, hdr)

        # Round off
        self._add_round_off(voucher, hdr.round_off, is_deemed_positive=False)

    # ------------------------------------------------------------------
    # Purchase Invoice
    # ------------------------------------------------------------------

    def _build_purchase_voucher(
        self, parent: ET.Element, bundle: InvoiceBundle
    ) -> None:
        hdr = bundle.header
        voucher = ET.SubElement(parent, "VOUCHER")
        voucher.set("VCHTYPE", "Purchase")
        voucher.set("ACTION", "Create")
        voucher.set("OBJVIEW", "Invoice Voucher View")

        self._add_common_header(voucher, hdr, "Purchase")

        inv_val = self.gst.safe_decimal(hdr.invoice_value)

        # Party ledger (Credit — we owe supplier)
        self._add_ledger_entry(
            voucher,
            ledger_name=hdr.party_name,
            amount=inv_val,
            is_deemed_positive=False,
        )

        # Purchase ledger (Debit — expense/asset)
        taxable = self.gst.safe_decimal(hdr.total_taxable_value)
        purchase_entry = self._add_ledger_entry(
            voucher,
            ledger_name=hdr.sales_ledger,  # "Sales_Ledger" column doubles as Purchase ledger
            amount=-taxable,
            is_deemed_positive=True,
        )
        self._add_gst_override(purchase_entry, bundle, hdr.reverse_charge)

        # Input tax ledger entries (Debit)
        self._add_purchase_tax_entries(voucher, hdr)

        # Round off
        self._add_round_off(voucher, hdr.round_off, is_deemed_positive=True)

    # ------------------------------------------------------------------
    # Sales Order
    # ------------------------------------------------------------------

    def _build_sales_order_voucher(
        self, parent: ET.Element, bundle: InvoiceBundle
    ) -> None:
        hdr = bundle.header
        voucher = ET.SubElement(parent, "VOUCHER")
        voucher.set("VCHTYPE", "Sales Order")
        voucher.set("ACTION", "Create")
        voucher.set("OBJVIEW", "Invoice Voucher View")

        self._add_common_header(voucher, hdr, "Sales Order")
        ET.SubElement(voucher, "ISINVOICE").text = "No"

        inv_val = self.gst.safe_decimal(hdr.invoice_value)

        # Party ledger
        self._add_ledger_entry(
            voucher,
            ledger_name=hdr.party_name,
            amount=-inv_val,
            is_deemed_positive=True,
        )

        # Sales ledger
        taxable = self.gst.safe_decimal(hdr.total_taxable_value)
        self._add_ledger_entry(
            voucher,
            ledger_name=hdr.sales_ledger,
            amount=taxable,
            is_deemed_positive=False,
        )

        # Inventory entries (one per line item)
        for li in bundle.line_items:
            self._add_inventory_entry(voucher, li, hdr.sales_ledger)

        # Tax ledger entries
        self._add_sales_tax_entries(voucher, hdr)

        # Round off
        self._add_round_off(voucher, hdr.round_off, is_deemed_positive=False)

    # ------------------------------------------------------------------
    # Shared building blocks
    # ------------------------------------------------------------------

    def _add_common_header(
        self,
        voucher: ET.Element,
        hdr,
        voucher_type_name: str,
    ) -> None:
        """Add common voucher header elements."""
        tally_date = self._date_to_tally(hdr.invoice_date)

        ET.SubElement(voucher, "DATE").text = tally_date
        ET.SubElement(voucher, "VOUCHERTYPENAME").text = voucher_type_name
        ET.SubElement(voucher, "VOUCHERNUMBER").text = hdr.invoice_no
        ET.SubElement(voucher, "REFERENCE").text = (
            hdr.reference_no or hdr.invoice_no
        )
        ET.SubElement(voucher, "PARTYLEDGERNAME").text = hdr.party_name
        ET.SubElement(voucher, "BASICBASEPARTYNAME").text = hdr.party_name
        ET.SubElement(voucher, "PERSISTEDVIEW").text = "Invoice Voucher View"

        if voucher_type_name != "Sales Order":
            ET.SubElement(voucher, "ISINVOICE").text = "Yes"

        if hdr.narration:
            ET.SubElement(voucher, "NARRATION").text = hdr.narration

        if hdr.party_gstin:
            ET.SubElement(voucher, "PARTYGSTIN").text = hdr.party_gstin

        pos_name = cfg.STATE_CODE_TO_NAME.get(hdr.place_of_supply, "")
        if pos_name:
            ET.SubElement(voucher, "PLACEOFSUPPLY").text = pos_name

        # Buyer address list
        addr_list = ET.SubElement(voucher, "BASICBUYERADDRESS.LIST")
        ET.SubElement(addr_list, "BASICBUYERADDRESS").text = hdr.party_name

    @staticmethod
    def _add_ledger_entry(
        voucher: ET.Element,
        ledger_name: str,
        amount: Decimal,
        is_deemed_positive: bool,
    ) -> ET.Element:
        """Add an ALLLEDGERENTRIES.LIST element."""
        entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(entry, "LEDGERNAME").text = ledger_name
        ET.SubElement(entry, "ISDEEMEDPOSITIVE").text = (
            "Yes" if is_deemed_positive else "No"
        )
        ET.SubElement(entry, "AMOUNT").text = str(amount)
        return entry

    def _add_gst_override(
        self,
        ledger_entry: ET.Element,
        bundle: InvoiceBundle,
        reverse_charge: str,
    ) -> None:
        """Add GSTOVRDNALLEDGER.LIST with HSN details."""
        rc = "Yes" if reverse_charge.upper() == "Y" else "No"
        ET.SubElement(ledger_entry, "GSTOVRDNISREVCHARGEAPPL").text = rc

        gst_list = ET.SubElement(ledger_entry, "GSTOVRDNALLEDGER.LIST")

        # Group line items by HSN
        hsn_groups: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for li in bundle.line_items:
            hsn = li.hsn_sac or "0000"
            hsn_groups[hsn] += self.gst.safe_decimal(li.taxable_value)

        for hsn, taxable in hsn_groups.items():
            hsn_detail = ET.SubElement(gst_list, "GSTOVRDNHSNDETAILS.LIST")
            ET.SubElement(hsn_detail, "HSNCODE").text = hsn
            ET.SubElement(hsn_detail, "TAXABLEAMOUNT").text = str(taxable)

    def _add_sales_tax_entries(self, voucher: ET.Element, hdr) -> None:
        """Add output GST ledger entries for Sales / Sales Order."""
        cgst = self.gst.safe_decimal(hdr.cgst_total)
        sgst = self.gst.safe_decimal(hdr.sgst_total)
        igst = self.gst.safe_decimal(hdr.igst_total)

        if cgst > 0:
            self._add_ledger_entry(voucher, "CGST", cgst, False)
        if sgst > 0:
            self._add_ledger_entry(voucher, "SGST", sgst, False)
        if igst > 0:
            self._add_ledger_entry(voucher, "IGST", igst, False)

    def _add_purchase_tax_entries(self, voucher: ET.Element, hdr) -> None:
        """Add input GST ledger entries for Purchase."""
        cgst = self.gst.safe_decimal(hdr.cgst_total)
        sgst = self.gst.safe_decimal(hdr.sgst_total)
        igst = self.gst.safe_decimal(hdr.igst_total)

        if cgst > 0:
            self._add_ledger_entry(voucher, "Input CGST", -cgst, True)
        if sgst > 0:
            self._add_ledger_entry(voucher, "Input SGST", -sgst, True)
        if igst > 0:
            self._add_ledger_entry(voucher, "Input IGST", -igst, True)

    def _add_round_off(
        self,
        voucher: ET.Element,
        round_off: str,
        is_deemed_positive: bool,
    ) -> None:
        """Add Round Off ledger entry if non-zero."""
        ro = self.gst.safe_decimal(round_off)
        if ro != 0:
            amount = -ro if is_deemed_positive else ro
            self._add_ledger_entry(
                voucher, "Round Off", amount, is_deemed_positive
            )

    def _add_inventory_entry(
        self,
        voucher: ET.Element,
        li: LineItem,
        sales_ledger: str,
    ) -> None:
        """Add ALLINVENTORYENTRIES.LIST for a Sales Order line item."""
        inv_entry = ET.SubElement(voucher, "ALLINVENTORYENTRIES.LIST")
        ET.SubElement(inv_entry, "STOCKITEMNAME").text = li.stock_item_name
        ET.SubElement(inv_entry, "ISDEEMEDPOSITIVE").text = "No"

        rate_val = self.gst.safe_decimal(li.rate)
        uom = li.uom or "NOS"
        ET.SubElement(inv_entry, "RATE").text = f"{rate_val}/{uom}"

        taxable = self.gst.safe_decimal(li.taxable_value)
        ET.SubElement(inv_entry, "AMOUNT").text = str(taxable)

        qty = self.gst.safe_decimal(li.qty)
        qty_str = f"{qty} {uom}"
        ET.SubElement(inv_entry, "ACTUALQTY").text = qty_str
        ET.SubElement(inv_entry, "BILLEDQTY").text = qty_str

        # Batch allocations
        if li.godown:
            batch = ET.SubElement(inv_entry, "BATCHALLOCATIONS.LIST")
            ET.SubElement(batch, "GODOWNNAME").text = li.godown
            ET.SubElement(batch, "BATCHNAME").text = "Primary Batch"
            ET.SubElement(batch, "AMOUNT").text = str(taxable)
            ET.SubElement(batch, "ACTUALQTY").text = qty_str
            ET.SubElement(batch, "BILLEDQTY").text = qty_str

        # Accounting allocations
        acct = ET.SubElement(inv_entry, "ACCOUNTINGALLOCATIONS.LIST")
        ET.SubElement(acct, "LEDGERNAME").text = sales_ledger
        ET.SubElement(acct, "AMOUNT").text = str(taxable)

    # ------------------------------------------------------------------
    # Query XML builders (for Tally Lookup Service)
    # ------------------------------------------------------------------

    @staticmethod
    def build_company_list_xml() -> str:
        """Build XML to query list of companies from Tally."""
        envelope = ET.Element("ENVELOPE")
        header = ET.SubElement(envelope, "HEADER")
        ET.SubElement(header, "TALLYREQUEST").text = "Export Data"
        body = ET.SubElement(envelope, "BODY")
        export = ET.SubElement(body, "EXPORTDATA")
        req = ET.SubElement(export, "REQUESTDESC")
        ET.SubElement(req, "REPORTNAME").text = "List of Companies"
        return TallyXmlBuilder._to_xml_string(envelope)

    @staticmethod
    def build_ledger_list_xml(company_name: str) -> str:
        """Build XML to query list of ledgers from Tally."""
        envelope = ET.Element("ENVELOPE")
        header = ET.SubElement(envelope, "HEADER")
        ET.SubElement(header, "TALLYREQUEST").text = "Export Data"
        body = ET.SubElement(envelope, "BODY")
        export = ET.SubElement(body, "EXPORTDATA")
        req = ET.SubElement(export, "REQUESTDESC")
        static = ET.SubElement(req, "STATICVARIABLES")
        ET.SubElement(static, "SVCURRENTCOMPANY").text = company_name
        ET.SubElement(req, "REPORTNAME").text = "List of Ledgers"
        return TallyXmlBuilder._to_xml_string(envelope)

    @staticmethod
    def build_stock_item_list_xml(company_name: str) -> str:
        """Build XML to query list of stock items from Tally."""
        envelope = ET.Element("ENVELOPE")
        header = ET.SubElement(envelope, "HEADER")
        ET.SubElement(header, "TALLYREQUEST").text = "Export Data"
        body = ET.SubElement(envelope, "BODY")
        export = ET.SubElement(body, "EXPORTDATA")
        req = ET.SubElement(export, "REQUESTDESC")
        static = ET.SubElement(req, "STATICVARIABLES")
        ET.SubElement(static, "SVCURRENTCOMPANY").text = company_name
        ET.SubElement(req, "REPORTNAME").text = "List of Stock Items"
        return TallyXmlBuilder._to_xml_string(envelope)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _date_to_tally(date_str: str) -> str:
        """Convert DD/MM/YYYY to YYYYMMDD for Tally."""
        if not date_str:
            return ""
        parts = date_str.strip().split("/")
        if len(parts) == 3:
            day, month, year = parts
            return f"{year.zfill(4)}{month.zfill(2)}{day.zfill(2)}"
        return date_str

    @staticmethod
    def _to_xml_string(element: ET.Element) -> str:
        """Serialize an ElementTree element to an XML string."""
        raw = ET.tostring(element, encoding="unicode", xml_declaration=False)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + raw
