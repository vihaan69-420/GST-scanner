# ERP Bridge - CSV Schema Specification

**Version:** 0.1.0 (Planning Phase)
**Created:** February 14, 2026
**Parent Document:** [EPIC_PLAN.md](EPIC_PLAN.md)

---

## Overview

The ERP Bridge accepts invoice data as two CSV files that work together:

1. **Summary CSV** - One row per invoice (header-level data)
2. **Line Items CSV** - One row per line item (detail-level data)

The two files are linked by the `Invoice_No` column. Every row in the Line Items CSV must have a corresponding row in the Summary CSV.

---

## General CSV Rules

| Rule | Specification |
|------|--------------|
| Encoding | UTF-8 (BOM optional, will be stripped) |
| Delimiter | Comma (`,`) |
| Quote character | Double quote (`"`) |
| Escape character | Double quote within quotes (`""`) |
| Line ending | CRLF or LF (both accepted) |
| Header row | Required (first row) |
| Column order | Fixed (must match schema order) |
| Trailing commas | Ignored |
| Empty rows | Skipped with warning |
| Max file size | 5 MB (configurable via `ERP_BRIDGE_MAX_FILE_SIZE_MB`) |
| Max rows | 10,000 (configurable via `ERP_BRIDGE_MAX_ROWS`) |

---

## Data Type Definitions

| Type | Format | Examples | Notes |
|------|--------|---------|-------|
| String | Free text | `ABC Corp`, `INV-001` | Leading/trailing whitespace trimmed |
| Integer | Whole number | `1`, `100` | No decimal point |
| Decimal | Number with up to 2 decimals | `10000.00`, `9.50` | Commas in values not allowed; use quotes if needed |
| Date | DD/MM/YYYY | `14/02/2026` | Strict format; other formats rejected |
| Boolean | Y or N | `Y`, `N` | Case-insensitive; blank = N |

---

## 1. Summary CSV Schema (Invoice Headers)

### File Naming Convention

Accepted patterns (case-insensitive):
- `*_summary.csv`
- `*_header.csv`
- `*_invoices.csv`

### Column Definitions

| # | Column Name | Type | Required | Validation Rules | Example |
|---|-------------|------|----------|-----------------|---------|
| 1 | `Voucher_Type` | String | Yes | Must be one of: `Sales`, `Purchase`, `Sales Order` | `Sales` |
| 2 | `Invoice_No` | String | Yes | Non-empty; max 50 chars; unique within file | `INV-2026-001` |
| 3 | `Invoice_Date` | Date | Yes | DD/MM/YYYY; not future-dated beyond 1 day | `14/02/2026` |
| 4 | `Party_Name` | String | Yes | Non-empty; max 200 chars | `ABC Trading Co` |
| 5 | `Party_GSTIN` | String | Conditional | 15-char alphanumeric with valid checksum; required if GST applicable | `29AABCU9603R1ZP` |
| 6 | `Party_State_Code` | String | Yes | 2-digit valid Indian state code (01-38) | `29` |
| 7 | `Place_Of_Supply` | String | Yes | 2-digit valid Indian state code (01-38) | `29` |
| 8 | `Sales_Ledger` | String | Yes | Non-empty; max 200 chars; Tally ledger name | `Sales - GST 18%` |
| 9 | `Invoice_Value` | Decimal | Yes | Positive; must equal Taxable + GST + Cess +/- Round Off | `11800.00` |
| 10 | `Total_Taxable_Value` | Decimal | Yes | Positive; must equal sum of line item taxable values | `10000.00` |
| 11 | `CGST_Total` | Decimal | Conditional | Required if intra-state; must equal sum of line item CGST | `900.00` |
| 12 | `SGST_Total` | Decimal | Conditional | Required if intra-state; must equal sum of line item SGST | `900.00` |
| 13 | `IGST_Total` | Decimal | Conditional | Required if inter-state; must equal sum of line item IGST | `0.00` |
| 14 | `Cess_Total` | Decimal | No | Non-negative | `0.00` |
| 15 | `Round_Off` | Decimal | No | Between -1.00 and 1.00 | `-0.50` |
| 16 | `Narration` | String | No | Max 500 chars | `Feb 2026 invoice` |
| 17 | `Reference_No` | String | No | Max 50 chars | `PO-2026-100` |
| 18 | `Reference_Date` | Date | No | DD/MM/YYYY; must be on or before Invoice_Date | `10/02/2026` |
| 19 | `Reverse_Charge` | Boolean | No | Y/N; default N | `N` |
| 20 | `Company_Name` | String | No | Tally company name; overrides default from env | `My Company Pvt Ltd` |

### Conditional Field Rules

**Intra-state supply** (Party_State_Code == Place_Of_Supply):
- `CGST_Total` is required and must be > 0
- `SGST_Total` is required and must be > 0
- `IGST_Total` must be 0 or empty

**Inter-state supply** (Party_State_Code != Place_Of_Supply):
- `IGST_Total` is required and must be > 0
- `CGST_Total` must be 0 or empty
- `SGST_Total` must be 0 or empty

**GSTIN requirement:**
- Required when `Voucher_Type` is `Sales` or `Purchase` and transaction is B2B
- Optional for B2C transactions (can be empty)

---

## 2. Line Items CSV Schema

### File Naming Convention

Accepted patterns (case-insensitive):
- `*_items.csv`
- `*_lineitems.csv`
- `*_details.csv`

### Column Definitions

| # | Column Name | Type | Required | Validation Rules | Example |
|---|-------------|------|----------|-----------------|---------|
| 1 | `Invoice_No` | String | Yes | Must match a row in Summary CSV | `INV-2026-001` |
| 2 | `Line_No` | Integer | Yes | Positive; sequential per invoice starting from 1 | `1` |
| 3 | `Item_Description` | String | Yes | Non-empty; max 500 chars | `Widget Type A` |
| 4 | `HSN_SAC` | String | Yes | 4, 6, or 8 digit numeric string | `84714190` |
| 5 | `Qty` | Decimal | Conditional | Positive; required for goods | `100` |
| 6 | `UOM` | String | Conditional | Required if Qty provided; valid UOM code | `PCS` |
| 7 | `Rate` | Decimal | Conditional | Positive; required if Qty provided | `100.00` |
| 8 | `Discount_Percent` | Decimal | No | 0-100 range | `0.00` |
| 9 | `Taxable_Value` | Decimal | Yes | Positive; should equal Qty * Rate * (1 - Discount/100) if Qty provided | `10000.00` |
| 10 | `GST_Rate` | Decimal | Yes | Must be one of: 0, 0.25, 3, 5, 12, 18, 28 | `18` |
| 11 | `CGST_Rate` | Decimal | Conditional | Must be GST_Rate / 2 for intra-state | `9` |
| 12 | `CGST_Amount` | Decimal | Conditional | Must equal Taxable_Value * CGST_Rate / 100 (within tolerance) | `900.00` |
| 13 | `SGST_Rate` | Decimal | Conditional | Must be GST_Rate / 2 for intra-state | `9` |
| 14 | `SGST_Amount` | Decimal | Conditional | Must equal Taxable_Value * SGST_Rate / 100 (within tolerance) | `900.00` |
| 15 | `IGST_Rate` | Decimal | Conditional | Must equal GST_Rate for inter-state | `0` |
| 16 | `IGST_Amount` | Decimal | Conditional | Must equal Taxable_Value * IGST_Rate / 100 (within tolerance) | `0.00` |
| 17 | `Cess_Amount` | Decimal | No | Non-negative | `0.00` |
| 18 | `Stock_Item_Name` | String | Conditional | Required for `Sales Order` voucher type | `Widget Type A` |
| 19 | `Godown` | String | No | Tally godown name; max 200 chars | `Main Godown` |

### Cross-File Validation Rules

| Rule | Description | Severity |
|------|-------------|----------|
| Orphan check | Every `Invoice_No` in Line Items must exist in Summary | Error |
| Completeness check | Every `Invoice_No` in Summary must have at least 1 line item | Error |
| Taxable reconciliation | Sum of line item `Taxable_Value` must equal Summary `Total_Taxable_Value` (tolerance: Rs 0.50) | Error |
| CGST reconciliation | Sum of line item `CGST_Amount` must equal Summary `CGST_Total` (tolerance: Rs 0.50) | Error |
| SGST reconciliation | Sum of line item `SGST_Amount` must equal Summary `SGST_Total` (tolerance: Rs 0.50) | Error |
| IGST reconciliation | Sum of line item `IGST_Amount` must equal Summary `IGST_Total` (tolerance: Rs 0.50) | Error |
| Invoice value check | Summary `Invoice_Value` must equal `Total_Taxable_Value` + `CGST_Total` + `SGST_Total` + `IGST_Total` + `Cess_Total` + `Round_Off` (tolerance: Rs 1.00) | Error |
| Line number sequence | `Line_No` values per invoice should be sequential starting from 1 | Warning |
| Tax type consistency | All line items for an invoice must use the same tax type (CGST+SGST or IGST) | Error |

---

## 3. Valid Indian State Codes

For `Party_State_Code` and `Place_Of_Supply` validation:

| Code | State/UT | Code | State/UT |
|------|----------|------|----------|
| 01 | Jammu & Kashmir | 20 | Jharkhand |
| 02 | Himachal Pradesh | 21 | Odisha |
| 03 | Punjab | 22 | Chhattisgarh |
| 04 | Chandigarh | 23 | Madhya Pradesh |
| 05 | Uttarakhand | 24 | Gujarat |
| 06 | Haryana | 26 | Dadra & Nagar Haveli and Daman & Diu |
| 07 | Delhi | 27 | Maharashtra |
| 08 | Rajasthan | 29 | Karnataka |
| 09 | Uttar Pradesh | 30 | Goa |
| 10 | Bihar | 31 | Lakshadweep |
| 11 | Sikkim | 32 | Kerala |
| 12 | Arunachal Pradesh | 33 | Tamil Nadu |
| 13 | Nagaland | 34 | Puducherry |
| 14 | Manipur | 35 | Andaman & Nicobar |
| 15 | Mizoram | 36 | Telangana |
| 16 | Tripura | 37 | Andhra Pradesh |
| 17 | Meghalaya | 38 | Ladakh |
| 18 | Assam | 97 | Other Territory |
| 19 | West Bengal | | |

---

## 4. Valid GST Rates

| Rate (%) | Category |
|----------|----------|
| 0 | Exempt / Nil rated |
| 0.25 | Rough precious/semi-precious stones |
| 3 | Gold, silver, platinum |
| 5 | Essential goods |
| 12 | Standard goods |
| 18 | Standard goods/services |
| 28 | Luxury / demerit goods |

---

## 5. Valid UOM Codes

Common Unit of Measure codes accepted:

| Code | Description |
|------|-------------|
| PCS | Pieces |
| NOS | Numbers |
| KG | Kilograms |
| KGS | Kilograms |
| GM | Grams |
| LTR | Litres |
| MTR | Metres |
| SQM | Square Metres |
| CBM | Cubic Metres |
| BOX | Boxes |
| SET | Sets |
| BAG | Bags |
| TON | Metric Tonnes |
| QTL | Quintals |
| DOZ | Dozens |
| PAC | Packs |
| ROL | Rolls |
| BDL | Bundles |
| OTH | Others |

---

## 6. Sample CSV Files

### Sample Summary CSV

```csv
Voucher_Type,Invoice_No,Invoice_Date,Party_Name,Party_GSTIN,Party_State_Code,Place_Of_Supply,Sales_Ledger,Invoice_Value,Total_Taxable_Value,CGST_Total,SGST_Total,IGST_Total,Cess_Total,Round_Off,Narration,Reference_No,Reference_Date,Reverse_Charge,Company_Name
Sales,INV-2026-001,14/02/2026,ABC Trading Co,29AABCU9603R1ZP,29,29,Sales - GST 18%,11800.00,10000.00,900.00,900.00,0.00,0.00,0.00,Feb 2026 invoice,PO-100,10/02/2026,N,
Sales,INV-2026-002,14/02/2026,XYZ Enterprises,07AAPCX1234M1ZT,07,07,Sales - GST 12%,5600.00,5000.00,0.00,0.00,600.00,0.00,0.00,Inter-state sale,,,,
Purchase,INV-2026-003,14/02/2026,Supplier Corp,29AADCS5678N1Z4,29,29,Purchase - GST 18%,23600.00,20000.00,1800.00,1800.00,0.00,0.00,0.00,Raw material purchase,,,N,
```

### Sample Line Items CSV

```csv
Invoice_No,Line_No,Item_Description,HSN_SAC,Qty,UOM,Rate,Discount_Percent,Taxable_Value,GST_Rate,CGST_Rate,CGST_Amount,SGST_Rate,SGST_Amount,IGST_Rate,IGST_Amount,Cess_Amount,Stock_Item_Name,Godown
INV-2026-001,1,Widget Type A,84714190,50,PCS,100.00,0.00,5000.00,18,9,450.00,9,450.00,0,0.00,0.00,,
INV-2026-001,2,Widget Type B,84714190,50,PCS,100.00,0.00,5000.00,18,9,450.00,9,450.00,0,0.00,0.00,,
INV-2026-002,1,Service Package,998311,1,NOS,5000.00,0.00,5000.00,12,0,0.00,0,0.00,12,600.00,0.00,,
INV-2026-003,1,Steel Rods,72142000,1000,KG,20.00,0.00,20000.00,18,9,1800.00,9,1800.00,0,0.00,0.00,,
```

---

## 7. Error Response Format

When CSV validation fails, the response includes row-level and field-level details:

```json
{
  "valid": false,
  "file": "invoices_summary.csv",
  "errors": [
    {
      "row": 3,
      "column": "Party_GSTIN",
      "value": "29AABCU960",
      "message": "Invalid GSTIN format: must be 15 characters",
      "severity": "ERROR"
    },
    {
      "row": 5,
      "column": "Invoice_Date",
      "value": "2026-02-14",
      "message": "Invalid date format: expected DD/MM/YYYY",
      "severity": "ERROR"
    },
    {
      "row": 7,
      "column": "Line_No",
      "value": "3",
      "message": "Line_No sequence gap: expected 2, got 3",
      "severity": "WARNING"
    }
  ],
  "cross_file_errors": [
    {
      "invoice_no": "INV-2026-005",
      "message": "Invoice in Summary CSV has no line items in Line Items CSV",
      "severity": "ERROR"
    }
  ]
}
```

---

**End of CSV Schema Specification**
