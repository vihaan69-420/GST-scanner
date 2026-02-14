# ERP Bridge - Tally XML Reference

**Version:** 0.1.0 (Planning Phase)
**Created:** February 14, 2026
**Parent Document:** [EPIC_PLAN.md](EPIC_PLAN.md)

---

## Overview

This document defines the Tally XML structures that the ERP Bridge will generate for importing vouchers into Tally ERP (Tally Prime / Tally ERP 9). All XML is sent via HTTP POST to Tally's XML server endpoint.

---

## 1. XML Envelope Structure (Common)

Every request to Tally follows this envelope structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Vouchers</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <!-- One or more VOUCHER elements -->
          <VOUCHER VCHTYPE="{voucher_type}" ACTION="Create" OBJVIEW="{view_name}">
            <!-- Voucher content -->
          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>
```

### Key Points

- One `<TALLYMESSAGE>` per request
- Each `<VOUCHER>` is a single voucher (invoice/order)
- For batch processing, send one voucher per HTTP request (sequential)
- `ACTION="Create"` for new vouchers; never use `ACTION="Alter"` in this module
- `OBJVIEW` determines how Tally interprets the voucher

---

## 2. Sales Invoice XML

### Voucher Attributes

| Attribute | Value |
|-----------|-------|
| VCHTYPE | `Sales` |
| ACTION | `Create` |
| OBJVIEW | `Invoice Voucher View` |

### Complete Template

```xml
<VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Invoice Voucher View">

  <!-- === Voucher Header === -->
  <DATE>{date_YYYYMMDD}</DATE>
  <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
  <VOUCHERNUMBER>{invoice_no}</VOUCHERNUMBER>
  <REFERENCE>{invoice_no}</REFERENCE>
  <PARTYLEDGERNAME>{party_name}</PARTYLEDGERNAME>
  <BASICBASEPARTYNAME>{party_name}</BASICBASEPARTYNAME>
  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
  <ISINVOICE>Yes</ISINVOICE>
  <NARRATION>{narration}</NARRATION>

  <!-- === Reference (optional) === -->
  <BASICBUYERADDRESS.LIST>
    <BASICBUYERADDRESS>{party_name}</BASICBUYERADDRESS>
  </BASICBUYERADDRESS.LIST>

  <!-- === GST Registration Details === -->
  <PARTYGSTIN>{party_gstin}</PARTYGSTIN>
  <PLACEOFSUPPLY>{place_of_supply_name}</PLACEOFSUPPLY>

  <!-- === Ledger Entry: Party (Debit - receives payment) === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>{party_name}</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-{invoice_value}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Ledger Entry: Sales (Credit - revenue) === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>{sales_ledger}</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{total_taxable_value}</AMOUNT>
    <GSTOVRDNISREVCHARGEAPPL>No</GSTOVRDNISREVCHARGEAPPL>
    <GSTOVRDNALLEDGER.LIST>
      <!-- Repeat for each HSN group -->
      <GSTOVRDNHSNDETAILS.LIST>
        <HSNCODE>{hsn_code}</HSNCODE>
        <TAXABLEAMOUNT>{taxable_amount_for_hsn}</TAXABLEAMOUNT>
      </GSTOVRDNHSNDETAILS.LIST>
    </GSTOVRDNALLEDGER.LIST>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Ledger Entry: CGST (Intra-State) === -->
  <!-- Include only when Party_State_Code == Place_Of_Supply -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>CGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{cgst_total}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Ledger Entry: SGST (Intra-State) === -->
  <!-- Include only when Party_State_Code == Place_Of_Supply -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>SGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{sgst_total}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Ledger Entry: IGST (Inter-State) === -->
  <!-- Include only when Party_State_Code != Place_Of_Supply -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>IGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{igst_total}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Ledger Entry: Round Off (optional) === -->
  <!-- Include only when round_off != 0 -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>Round Off</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{round_off}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

</VOUCHER>
```

### Accounting Entry Logic (Sales Invoice)

| Entry | Ledger | Debit/Credit | Amount | ISDEEMEDPOSITIVE |
|-------|--------|-------------|--------|-------------------|
| Party | Party_Name | Debit | Invoice_Value | Yes |
| Revenue | Sales_Ledger | Credit | Total_Taxable_Value | No |
| CGST | CGST Ledger | Credit | CGST_Total | No |
| SGST | SGST Ledger | Credit | SGST_Total | No |
| IGST | IGST Ledger | Credit | IGST_Total | No |
| Round Off | Round Off Ledger | Credit/Debit | Round_Off | No |

**Tally Amount Sign Convention:**
- Negative amount (`-11800.00`) = Debit entry
- Positive amount (`10000.00`) = Credit entry
- `ISDEEMEDPOSITIVE=Yes` = amount is naturally debit
- `ISDEEMEDPOSITIVE=No` = amount is naturally credit

---

## 3. Purchase Invoice XML

### Voucher Attributes

| Attribute | Value |
|-----------|-------|
| VCHTYPE | `Purchase` |
| ACTION | `Create` |
| OBJVIEW | `Invoice Voucher View` |

### Template (Differences from Sales)

```xml
<VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">

  <DATE>{date_YYYYMMDD}</DATE>
  <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
  <VOUCHERNUMBER>{invoice_no}</VOUCHERNUMBER>
  <REFERENCE>{invoice_no}</REFERENCE>
  <PARTYLEDGERNAME>{party_name}</PARTYLEDGERNAME>
  <BASICBASEPARTYNAME>{party_name}</BASICBASEPARTYNAME>
  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
  <ISINVOICE>Yes</ISINVOICE>
  <NARRATION>{narration}</NARRATION>

  <PARTYGSTIN>{party_gstin}</PARTYGSTIN>
  <PLACEOFSUPPLY>{place_of_supply_name}</PLACEOFSUPPLY>

  <!-- === Party Ledger (Credit - we owe supplier) === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>{party_name}</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{invoice_value}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Purchase Ledger (Debit - expense/asset) === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>{purchase_ledger}</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-{total_taxable_value}</AMOUNT>
    <GSTOVRDNISREVCHARGEAPPL>{reverse_charge_yn}</GSTOVRDNISREVCHARGEAPPL>
    <GSTOVRDNALLEDGER.LIST>
      <GSTOVRDNHSNDETAILS.LIST>
        <HSNCODE>{hsn_code}</HSNCODE>
        <TAXABLEAMOUNT>{taxable_amount_for_hsn}</TAXABLEAMOUNT>
      </GSTOVRDNHSNDETAILS.LIST>
    </GSTOVRDNALLEDGER.LIST>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Input CGST (Debit - tax credit) === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>Input CGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-{cgst_total}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Input SGST (Debit - tax credit) === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>Input SGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-{sgst_total}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Input IGST (Debit - tax credit, inter-state) === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>Input IGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-{igst_total}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Round Off (optional) === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>Round Off</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-{round_off}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

</VOUCHER>
```

### Accounting Entry Logic (Purchase Invoice)

| Entry | Ledger | Debit/Credit | Amount | ISDEEMEDPOSITIVE |
|-------|--------|-------------|--------|-------------------|
| Party | Party_Name | Credit | Invoice_Value | No |
| Expense | Purchase_Ledger | Debit | Total_Taxable_Value | Yes |
| Input CGST | Input CGST Ledger | Debit | CGST_Total | Yes |
| Input SGST | Input SGST Ledger | Debit | SGST_Total | Yes |
| Input IGST | Input IGST Ledger | Debit | IGST_Total | Yes |
| Round Off | Round Off Ledger | Debit/Credit | Round_Off | Yes |

### Reverse Charge Handling

When `Reverse_Charge = Y`:
- Set `<GSTOVRDNISREVCHARGEAPPL>Yes</GSTOVRDNISREVCHARGEAPPL>` on the purchase ledger entry
- GST ledger names may differ (e.g., `Output CGST` instead of `Input CGST` for reverse charge liability)
- Implementation detail to be finalized during development

---

## 4. Sales Order XML

### Voucher Attributes

| Attribute | Value |
|-----------|-------|
| VCHTYPE | `Sales Order` |
| ACTION | `Create` |
| OBJVIEW | `Invoice Voucher View` |

### Template

```xml
<VOUCHER VCHTYPE="Sales Order" ACTION="Create" OBJVIEW="Invoice Voucher View">

  <DATE>{date_YYYYMMDD}</DATE>
  <VOUCHERTYPENAME>Sales Order</VOUCHERTYPENAME>
  <VOUCHERNUMBER>{order_no}</VOUCHERNUMBER>
  <REFERENCE>{reference_no}</REFERENCE>
  <PARTYLEDGERNAME>{party_name}</PARTYLEDGERNAME>
  <BASICBASEPARTYNAME>{party_name}</BASICBASEPARTYNAME>
  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
  <ISINVOICE>No</ISINVOICE>
  <NARRATION>{narration}</NARRATION>

  <PARTYGSTIN>{party_gstin}</PARTYGSTIN>
  <PLACEOFSUPPLY>{place_of_supply_name}</PLACEOFSUPPLY>

  <!-- === Party Ledger Entry === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>{party_name}</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-{invoice_value}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Sales Ledger Entry === -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>{sales_ledger}</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{total_taxable_value}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <!-- === Inventory Entries (one per line item) === -->
  <ALLINVENTORYENTRIES.LIST>
    <STOCKITEMNAME>{stock_item_name}</STOCKITEMNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <RATE>{rate}/{uom}</RATE>
    <AMOUNT>{taxable_value}</AMOUNT>
    <ACTUALQTY>{qty} {uom}</ACTUALQTY>
    <BILLEDQTY>{qty} {uom}</BILLEDQTY>
    <BATCHALLOCATIONS.LIST>
      <GODOWNNAME>{godown}</GODOWNNAME>
      <BATCHNAME>Primary Batch</BATCHNAME>
      <AMOUNT>{taxable_value}</AMOUNT>
      <ACTUALQTY>{qty} {uom}</ACTUALQTY>
      <BILLEDQTY>{qty} {uom}</BILLEDQTY>
    </BATCHALLOCATIONS.LIST>
    <ACCOUNTINGALLOCATIONS.LIST>
      <LEDGERNAME>{sales_ledger}</LEDGERNAME>
      <AMOUNT>{taxable_value}</AMOUNT>
    </ACCOUNTINGALLOCATIONS.LIST>
  </ALLINVENTORYENTRIES.LIST>

  <!-- === Tax Ledger Entries (CGST/SGST or IGST) === -->
  <!-- Same pattern as Sales Invoice -->
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>CGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{cgst_total}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>SGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{sgst_total}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>

</VOUCHER>
```

### Key Differences from Sales Invoice

| Aspect | Sales Invoice | Sales Order |
|--------|--------------|-------------|
| ISINVOICE | Yes | No |
| Inventory entries | Not included (ledger-only) | Required (`ALLINVENTORYENTRIES.LIST`) |
| Stock_Item_Name | Not used | Required per line item |
| Godown | Not used | Optional per line item |
| Effect on books | Creates accounting entries | Creates order tracking only |

---

## 5. Tally Response XML

### Success Response

```xml
<RESPONSE>
  <CREATED>1</CREATED>
  <ALTERED>0</ALTERED>
  <DELETED>0</DELETED>
  <LASTVCHID>12345</LASTVCHID>
  <LASTVCHNUMBER>INV-2026-001</LASTVCHNUMBER>
</RESPONSE>
```

**Parse logic:** `CREATED >= 1` indicates success.

### Error Response

```xml
<RESPONSE>
  <CREATED>0</CREATED>
  <ALTERED>0</ALTERED>
  <DELETED>0</DELETED>
  <LINEERROR>
    Ledger "ABC Trading Co" is not defined
  </LINEERROR>
</RESPONSE>
```

**Parse logic:** `CREATED == 0` and presence of `LINEERROR` indicates failure.

### Duplicate Voucher Response

```xml
<RESPONSE>
  <CREATED>0</CREATED>
  <LINEERROR>
    Voucher number INV-2026-001 already exists
  </LINEERROR>
</RESPONSE>
```

### Connection Error Scenarios

| Scenario | HTTP Status | Handling |
|----------|------------|---------|
| Tally not running | Connection refused | Retry with backoff; report as connectivity error |
| Tally busy | Timeout | Retry with backoff; report as timeout error |
| Invalid XML sent | 200 + error XML | Parse error from response; report as XML generation error |
| Network error | N/A | Retry with backoff; report as network error |
| Malformed response | 200 + invalid XML | Report as parse error; include raw response in audit log |

---

## 6. Tally Query XML (for Lookup Service)

### Check if Company Exists

```xml
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>List of Companies</REPORTNAME>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>
```

### Check if Ledger Exists

```xml
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
        <REPORTNAME>List of Ledgers</REPORTNAME>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>
```

### Check if Stock Item Exists

```xml
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
        <REPORTNAME>List of Stock Items</REPORTNAME>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>
```

### Check if Voucher Already Exists (Duplicate Check)

```xml
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        </STATICVARIABLES>
        <REPORTNAME>Voucher Register</REPORTNAME>
        <FETCHLIST>
          <FETCH>VOUCHERNUMBER</FETCH>
          <FETCH>DATE</FETCH>
          <FETCH>PARTYLEDGERNAME</FETCH>
        </FETCHLIST>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>
```

---

## 7. Date Format Conversion

Tally uses `YYYYMMDD` format for dates in XML. The ERP Bridge must convert from CSV format:

| Source (CSV) | Target (Tally XML) |
|-------------|-------------------|
| `14/02/2026` | `20260214` |
| `01/01/2026` | `20260101` |
| `31/12/2025` | `20251231` |

**Conversion logic:** Split by `/`, rearrange as `YYYY + MM + DD`, no separators.

---

## 8. Place of Supply Mapping

Tally expects the full state name for `<PLACEOFSUPPLY>`, not just the code. The ERP Bridge must map state codes to names:

| Code | Tally Place of Supply Value |
|------|---------------------------|
| 29 | `Karnataka` |
| 07 | `Delhi` |
| 27 | `Maharashtra` |
| 33 | `Tamil Nadu` |

A complete mapping table will be maintained in the `tally_xml_builder.py` module.

---

## 9. XML Escaping Rules

All user-provided values inserted into XML must be escaped:

| Character | Escape |
|-----------|--------|
| `&` | `&amp;` |
| `<` | `&lt;` |
| `>` | `&gt;` |
| `"` | `&quot;` |
| `'` | `&apos;` |

The XML builder will use Python's `xml.etree.ElementTree` or equivalent library which handles escaping automatically. Manual string concatenation for XML generation is prohibited.

---

## 10. Tally Version Compatibility

| Feature | Tally ERP 9 | Tally Prime |
|---------|------------|-------------|
| XML Import endpoint | Port 9000 (default) | Port 9000 (default) |
| Voucher import | Supported | Supported |
| GST fields | Supported (post-GST updates) | Fully supported |
| GSTOVRDNALLEDGER | Supported | Supported |
| Inventory entries | Supported | Supported |
| Response format | XML | XML |

**Note:** The XML structure is largely compatible between Tally ERP 9 and Tally Prime. Any version-specific differences encountered during implementation will be documented and handled via configuration.

---

**End of Tally XML Reference**
