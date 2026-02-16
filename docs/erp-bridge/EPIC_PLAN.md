# ERP Bridge - CSV to Tally via MCP

## Epic Plan

**Version:** 0.1.0 (Planning Phase)
**Created:** February 14, 2026
**Status:** Planning - No Code
**Branch:** `cursor/csv-tally-erp-bridge-b142`

---

## 1. Objective

Build a new ERP Bridge module that:

1. Accepts invoice data via CSV files (Summary header + Line Items)
2. Validates structure and business rules against GST compliance standards
3. Converts validated data into Tally-compatible XML vouchers
4. Uploads XML to Tally ERP via its HTTP API
5. Validates the Tally response and returns a structured result
6. Logs a complete audit trail per invoice
7. Supports **Sales Invoice**, **Purchase Invoice**, and **Sales Order** voucher types

**Key Constraint:** This is an entirely new feature path. It must have **zero impact** on the existing GST Scanner Telegram bot, OCR pipeline, Google Sheets integration, or any Tier 1/2/3 functionality.

---

## 2. Scope & Boundaries

### In Scope

- New `src/erp_bridge/` module (isolated package)
- MCP tool endpoint for CSV upload + processing
- CSV parsing, schema validation, and business rule validation
- GST calculation reuse (read-only consumption of existing validation logic)
- Tally XML generation (Sales Invoice, Purchase Invoice, Sales Order)
- Tally HTTP connector with retry and timeout handling
- Tally response parsing and structured result return
- Batch processing with per-invoice error isolation
- Duplicate voucher detection and idempotency
- Audit logging per invoice
- Feature flag gating (`ENABLE_ERP_BRIDGE`)

### Out of Scope

- Modification of any existing GST Scanner module
- Telegram bot changes
- Google Sheets integration changes
- OCR pipeline changes
- Tally master data sync (future epic)
- UI/dashboard for ERP Bridge (future epic)
- Credit Note / Debit Note voucher types (future iteration)

---

## 3. Architecture Overview

```
                          ┌──────────────────────┐
                          │     CSV Files         │
                          │  (Summary + Items)    │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │  MCP Tool Endpoint    │
                          │  (csv_to_tally)       │
                          └──────────┬───────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                 │
                    ▼                ▼                 ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
           │ CSV Parser   │ │ CSV Schema   │ │ Feature Flag     │
           │ Service      │ │ Validator    │ │ Guard            │
           └──────┬───────┘ └──────┬───────┘ └──────────────────┘
                  │                │
                  ▼                ▼
           ┌──────────────────────────────┐
           │     Validation Engine        │
           │  (Structure + Business Rules │
           │   + GST Calculation Check)   │
           └──────────────┬───────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │  Tally Lookup Service        │
           │  (Optional: verify ledgers,  │
           │   stock items in Tally)      │
           └──────────────┬───────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │  Tally XML Builder Service   │
           │  (Voucher XML generation)    │
           └──────────────┬───────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │  Tally Connector Service     │
           │  (HTTP POST to Tally)        │
           └──────────────┬───────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │  Response Parser             │
           │  (Parse Tally XML response)  │
           └──────────────┬───────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │  Audit Logger                │
           │  (Per-invoice logging)       │
           └──────────────┬───────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │  Batch Result Summary        │
           │  (Structured JSON output)    │
           └──────────────────────────────┘
```

---

## 4. Core Modules

### 4.1 CSV Schema Validator (`csv_schema_validator.py`)

**Purpose:** Validate that uploaded CSV files conform to the expected schema before any business logic runs.

**Responsibilities:**
- Verify required columns are present (exact header match)
- Validate column data types (string, numeric, date)
- Enforce required vs optional field rules
- Check file encoding (UTF-8 expected)
- Validate file size limits (configurable, default 5 MB)
- Return structured validation result with row-level errors

**Inputs:** Raw CSV file path or file-like object
**Outputs:** `{ valid: bool, errors: [{ row, column, message }] }`

---

### 4.2 CSV Loader Service (`csv_loader_service.py`)

**Purpose:** Parse validated CSV files into structured Python objects.

**Responsibilities:**
- Read Summary CSV into list of invoice header dicts
- Read Line Items CSV into list of line item dicts
- Join line items to their parent invoice via `Invoice_No`
- Handle encoding edge cases (BOM, trailing whitespace)
- Normalize field values (strip, trim, type coercion)
- Detect orphan line items (no matching header) and report as warnings

**Inputs:** Validated CSV file paths (summary + line items)
**Outputs:** `List[InvoiceBundle]` where each bundle = `{ header: dict, line_items: [dict] }`

---

### 4.3 Validation Engine (`erp_validation_engine.py`)

**Purpose:** Apply business rules and GST compliance checks to parsed invoice data.

**Responsibilities:**
- Validate GSTIN format (15-character alphanumeric with checksum)
- Validate HSN/SAC codes (4/6/8 digit)
- Validate date formats (DD/MM/YYYY)
- Validate tax type consistency (IGST vs CGST+SGST based on state codes)
- Validate taxable value reconciliation (header total vs sum of line items)
- Validate GST amount reconciliation (header GST vs sum of line item GST)
- Validate invoice value = taxable value + total GST
- Validate mandatory fields per voucher type
- Check for negative amounts or illogical values
- **Reuse logic patterns** from existing `src/parsing/gst_validator.py` (read-only reference, do not import directly to maintain isolation)

**Inputs:** `InvoiceBundle`
**Outputs:** `{ status: OK|WARNING|ERROR, errors: [], warnings: [] }`

---

### 4.4 Tally Lookup Service (`tally_lookup_service.py`)

**Purpose:** Optionally verify that referenced master data exists in the target Tally company.

**Responsibilities:**
- Query Tally for ledger existence (party name, GST ledgers, tax ledgers)
- Query Tally for stock item existence (for Sales Order)
- Cache lookup results per session to minimize Tally round-trips
- Return missing master data as warnings (not blocking errors)
- Configurable: can be disabled via feature flag (`ENABLE_TALLY_LOOKUP`)

**Inputs:** Party names, ledger names, stock item names from invoice bundle
**Outputs:** `{ found: [str], missing: [str], cached: bool }`

---

### 4.5 GST Calculation Integration (`gst_calculation.py`)

**Purpose:** Reuse existing GST validation and calculation logic for the ERP Bridge.

**Responsibilities:**
- Determine supply type (intra-state vs inter-state) from state codes
- Calculate expected CGST/SGST/IGST split from GST rate
- Cross-verify calculated amounts against CSV-provided amounts
- Flag discrepancies as warnings or errors based on tolerance (Rs 0.50)
- **Adapter pattern:** wrap calls to validation logic so the ERP Bridge is decoupled from the internal implementation of `gst_validator.py`

**Design Note:** The existing `GSTValidator` class in `src/parsing/gst_validator.py` contains proven validation logic (taxable value reconciliation, GST total reconciliation, tax type consistency, rounding tolerance). The ERP Bridge will replicate these patterns in its own isolated module to avoid any import dependency on the existing codebase. If in the future the validation logic is extracted into a shared library, both modules can consume it.

---

### 4.6 Tally XML Builder (`tally_xml_builder.py`)

**Purpose:** Generate Tally-compatible XML for each supported voucher type.

**Responsibilities:**
- Generate `<ENVELOPE>` wrapper with proper Tally XML structure
- Support `Sales` voucher type (Sales Invoice)
- Support `Purchase` voucher type (Purchase Invoice)
- Support `Sales Order` voucher type
- Generate `<ALLLEDGERENTRIES.LIST>` for accounting entries
- Generate `<ALLINVENTORYENTRIES.LIST>` for inventory entries (Sales Order)
- Include GST allocation details (`<GSTOVRDNALLEDGER.LIST>`)
- Handle party ledger, sales/purchase ledger, tax ledger entries
- Include Narration field
- Set voucher date, reference number, party name
- Escape XML special characters
- Validate generated XML against Tally DTD expectations
- Return XML as string

**Supported Tally XML Envelope Structure:**
```xml
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
          <VOUCHER VCHTYPE="{voucher_type}" ACTION="Create">
            <!-- Voucher details -->
          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>
```

---

### 4.7 Tally Connector (`tally_connector.py`)

**Purpose:** Handle HTTP communication with Tally ERP.

**Responsibilities:**
- POST generated XML to Tally's HTTP endpoint (default: `http://localhost:9000`)
- Configurable Tally host, port, and endpoint
- Connection timeout handling (default: 30 seconds)
- Read timeout handling (default: 60 seconds)
- Retry logic with exponential backoff (max 3 retries, delays: 2s, 4s, 8s)
- Detect Tally not running / connection refused errors
- Return raw XML response for parsing
- Support both Tally Prime and Tally ERP 9

**Configuration:**
- `TALLY_HOST` (default: `localhost`)
- `TALLY_PORT` (default: `9000`)
- `TALLY_TIMEOUT_CONNECT` (default: `30`)
- `TALLY_TIMEOUT_READ` (default: `60`)
- `TALLY_MAX_RETRIES` (default: `3`)

---

### 4.8 Response Parser (`tally_response_parser.py`)

**Purpose:** Parse XML responses from Tally and convert to structured results.

**Responsibilities:**
- Parse Tally XML response
- Detect success (`CREATED = 1`) vs failure (`LINEERROR`, `ERRORS`)
- Extract error messages from Tally response
- Extract created voucher number/ID from response
- Handle malformed XML responses gracefully
- Return structured result: `{ success: bool, voucher_id: str, errors: [str], raw_response: str }`

---

### 4.9 Batch Processor (`erp_batch_processor.py`)

**Purpose:** Process multiple invoices from a CSV batch with error isolation.

**Responsibilities:**
- Iterate through parsed invoice bundles one at a time
- Isolate failures: one invoice error does not stop the batch
- Track progress (current / total)
- Collect per-invoice results (success, failure, skipped)
- Support duplicate detection within the batch (same Invoice_No + Seller_GSTIN)
- Support idempotency: check if voucher was already created in Tally before re-posting
- Return structured batch result summary
- Optional progress callback for real-time status updates

**Batch Result Schema:**
```json
{
  "batch_id": "uuid",
  "timestamp": "ISO-8601",
  "total_invoices": 10,
  "successful": 8,
  "failed": 1,
  "skipped_duplicates": 1,
  "processing_time_seconds": 45.2,
  "results": [
    {
      "invoice_no": "INV-001",
      "status": "SUCCESS",
      "tally_voucher_id": "12345",
      "processing_time_seconds": 3.1
    },
    {
      "invoice_no": "INV-002",
      "status": "FAILED",
      "error": "Ledger 'ABC Corp' not found in Tally",
      "processing_time_seconds": 2.8
    },
    {
      "invoice_no": "INV-001",
      "status": "SKIPPED",
      "reason": "Duplicate invoice detected in batch"
    }
  ]
}
```

---

### 4.10 Audit Logging Module (`erp_audit_logger.py`)

**Purpose:** Log complete audit trail for every invoice processed through the ERP Bridge.

**Responsibilities:**
- Log per-invoice: timestamp, source file, invoice number, voucher type, validation result, Tally result, processing time
- Log batch-level summary
- Log errors with full context (input data, validation errors, Tally response)
- Store audit logs in configurable location (file-based, rotated)
- Structured JSON log format for machine readability
- Human-readable log format for debugging
- Do NOT log sensitive data (full GSTIN should be masked in logs)
- **Design pattern reference:** existing `src/features/audit_logger.py` for metadata generation patterns

**Audit Log Entry Schema:**
```json
{
  "timestamp": "ISO-8601",
  "batch_id": "uuid",
  "invoice_no": "INV-001",
  "voucher_type": "Sales",
  "source_file": "invoices_feb_2026.csv",
  "validation_status": "OK",
  "validation_errors": [],
  "validation_warnings": ["Rounding difference of Rs 0.12"],
  "tally_status": "SUCCESS",
  "tally_voucher_id": "12345",
  "tally_errors": [],
  "processing_time_seconds": 3.1,
  "duplicate_check": "UNIQUE",
  "seller_gstin_masked": "29AAAC****M1ZP"
}
```

---

## 5. CSV Schema Specification

### 5.1 Summary CSV (Invoice Headers)

**File naming convention:** `*_summary.csv` or `*_header.csv`

| # | Column Name | Type | Required | Description | Example |
|---|-------------|------|----------|-------------|---------|
| 1 | Voucher_Type | String | Yes | Sales / Purchase / Sales Order | Sales |
| 2 | Invoice_No | String | Yes | Unique invoice/voucher number | INV-2026-001 |
| 3 | Invoice_Date | Date | Yes | DD/MM/YYYY format | 14/02/2026 |
| 4 | Party_Name | String | Yes | Customer/Vendor ledger name in Tally | ABC Trading Co |
| 5 | Party_GSTIN | String | Conditional | GSTIN (required if GST applicable) | 29AABCU9603R1ZP |
| 6 | Party_State_Code | String | Yes | 2-digit state code | 29 |
| 7 | Place_Of_Supply | String | Yes | 2-digit state code of supply | 29 |
| 8 | Sales_Ledger | String | Yes | Sales/Purchase ledger name in Tally | Sales - GST 18% |
| 9 | Invoice_Value | Decimal | Yes | Total invoice value (inclusive of GST) | 11800.00 |
| 10 | Total_Taxable_Value | Decimal | Yes | Sum of taxable values | 10000.00 |
| 11 | CGST_Total | Decimal | Conditional | Total CGST (intra-state) | 900.00 |
| 12 | SGST_Total | Decimal | Conditional | Total SGST (intra-state) | 900.00 |
| 13 | IGST_Total | Decimal | Conditional | Total IGST (inter-state) | 0.00 |
| 14 | Cess_Total | Decimal | No | Total Cess amount | 0.00 |
| 15 | Round_Off | Decimal | No | Rounding adjustment | -0.50 |
| 16 | Narration | String | No | Voucher narration/remarks | Feb 2026 invoice |
| 17 | Reference_No | String | No | External reference number | PO-2026-100 |
| 18 | Reference_Date | Date | No | Reference date DD/MM/YYYY | 10/02/2026 |
| 19 | Reverse_Charge | String | No | Y/N (default N) | N |
| 20 | Company_Name | String | No | Tally company name (overrides default) | My Company Pvt Ltd |

### 5.2 Line Items CSV

**File naming convention:** `*_items.csv` or `*_lineitems.csv`

| # | Column Name | Type | Required | Description | Example |
|---|-------------|------|----------|-------------|---------|
| 1 | Invoice_No | String | Yes | Links to Summary CSV | INV-2026-001 |
| 2 | Line_No | Integer | Yes | Sequential line number | 1 |
| 3 | Item_Description | String | Yes | Product/service description | Widget Type A |
| 4 | HSN_SAC | String | Yes | HSN/SAC code | 84714190 |
| 5 | Qty | Decimal | Conditional | Quantity (required for goods) | 100 |
| 6 | UOM | String | Conditional | Unit of measure (required if Qty) | PCS |
| 7 | Rate | Decimal | Conditional | Per-unit rate (required if Qty) | 100.00 |
| 8 | Discount_Percent | Decimal | No | Discount percentage | 0.00 |
| 9 | Taxable_Value | Decimal | Yes | Taxable amount for this line | 10000.00 |
| 10 | GST_Rate | Decimal | Yes | GST rate percentage | 18 |
| 11 | CGST_Rate | Decimal | Conditional | CGST rate (intra-state) | 9 |
| 12 | CGST_Amount | Decimal | Conditional | CGST amount | 900.00 |
| 13 | SGST_Rate | Decimal | Conditional | SGST rate (intra-state) | 9 |
| 14 | SGST_Amount | Decimal | Conditional | SGST amount | 900.00 |
| 15 | IGST_Rate | Decimal | Conditional | IGST rate (inter-state) | 0 |
| 16 | IGST_Amount | Decimal | Conditional | IGST amount | 0.00 |
| 17 | Cess_Amount | Decimal | No | Cess amount | 0.00 |
| 18 | Stock_Item_Name | String | Conditional | Tally stock item name (Sales Order) | Widget Type A |
| 19 | Godown | String | No | Tally godown name | Main Godown |

---

## 6. MCP Tool Endpoint Design

### 6.1 Tool: `csv_to_tally`

**Description:** Process CSV invoice files and create vouchers in Tally ERP.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| summary_csv_path | string | Yes | Path to the Summary/Header CSV file |
| items_csv_path | string | Yes | Path to the Line Items CSV file |
| tally_company | string | No | Tally company name (overrides env default) |
| dry_run | boolean | No | If true, validate and generate XML but do not post to Tally |
| skip_duplicates | boolean | No | If true, skip invoices already in Tally (default: true) |

**Response Schema:**

```json
{
  "success": true,
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "summary": {
    "total": 10,
    "successful": 8,
    "failed": 1,
    "skipped": 1
  },
  "results": [ ... ],
  "audit_log_path": "/path/to/audit/log.json"
}
```

### 6.2 Tool: `validate_csv`

**Description:** Validate CSV files without processing. Returns validation report.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| summary_csv_path | string | Yes | Path to the Summary/Header CSV file |
| items_csv_path | string | Yes | Path to the Line Items CSV file |

**Response Schema:**

```json
{
  "valid": true,
  "summary_file": {
    "rows": 10,
    "valid_rows": 10,
    "errors": []
  },
  "items_file": {
    "rows": 25,
    "valid_rows": 25,
    "errors": []
  },
  "business_rule_errors": [],
  "business_rule_warnings": []
}
```

### 6.3 Tool: `tally_connection_test`

**Description:** Test connectivity to Tally ERP and verify company exists.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| tally_host | string | No | Tally host (overrides env default) |
| tally_port | integer | No | Tally port (overrides env default) |
| company_name | string | No | Company name to verify |

**Response Schema:**

```json
{
  "connected": true,
  "tally_version": "Tally Prime 5.0",
  "company_found": true,
  "company_name": "My Company Pvt Ltd",
  "response_time_ms": 120
}
```

---

## 7. Tally XML Reference

### 7.1 Sales Invoice XML Structure

```xml
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Vouchers</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>My Company Pvt Ltd</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Invoice Voucher View">
            <DATE>20260214</DATE>
            <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
            <VOUCHERNUMBER>INV-2026-001</VOUCHERNUMBER>
            <REFERENCE>INV-2026-001</REFERENCE>
            <PARTYLEDGERNAME>ABC Trading Co</PARTYLEDGERNAME>
            <BASICBASEPARTYNAME>ABC Trading Co</BASICBASEPARTYNAME>
            <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
            <ISINVOICE>Yes</ISINVOICE>
            <NARRATION>Feb 2026 invoice</NARRATION>

            <!-- Party Ledger Entry (Debit) -->
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>ABC Trading Co</LEDGERNAME>
              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
              <AMOUNT>-11800.00</AMOUNT>
            </ALLLEDGERENTRIES.LIST>

            <!-- Sales Ledger Entry (Credit) -->
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>Sales - GST 18%</LEDGERNAME>
              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
              <AMOUNT>10000.00</AMOUNT>
            </ALLLEDGERENTRIES.LIST>

            <!-- CGST Ledger Entry -->
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>CGST</LEDGERNAME>
              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
              <AMOUNT>900.00</AMOUNT>
            </ALLLEDGERENTRIES.LIST>

            <!-- SGST Ledger Entry -->
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>SGST</LEDGERNAME>
              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
              <AMOUNT>900.00</AMOUNT>
            </ALLLEDGERENTRIES.LIST>

            <!-- GST Override Details -->
            <GSTOVRDNALLEDGER.LIST>
              <LEDGERNAME>Sales - GST 18%</LEDGERNAME>
              <GSTOVRDNHSNDETAILS.LIST>
                <HSNCODE>84714190</HSNCODE>
                <TAXABLEAMOUNT>10000.00</TAXABLEAMOUNT>
              </GSTOVRDNHSNDETAILS.LIST>
            </GSTOVRDNALLEDGER.LIST>

          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>
```

### 7.2 Purchase Invoice

Same structure as Sales Invoice with:
- `VCHTYPE="Purchase"`
- Reversed debit/credit entries (party is Credit, purchase ledger is Debit)
- Input tax credit GST ledgers

### 7.3 Sales Order

Same envelope structure with:
- `VCHTYPE="Sales Order"`
- `ISINVOICE>No</ISINVOICE>`
- `<ALLINVENTORYENTRIES.LIST>` instead of/in addition to ledger entries
- Stock item names, quantities, rates, godown references

---

## 8. Batch Processing Rules

| Rule | Description |
|------|-------------|
| Sequential processing | Process one invoice at a time (no parallel Tally calls) |
| Error isolation | A single invoice failure does not stop the batch |
| Structured result | Return per-invoice result in the batch summary |
| Intra-batch dedup | Detect duplicate Invoice_No + Seller_GSTIN within the same batch |
| Cross-batch dedup | Query Tally to check if voucher already exists before posting |
| Idempotency | Re-running the same CSV should skip already-created vouchers |
| Progress tracking | Emit progress callbacks (current/total/status) |
| Timeout per invoice | Individual invoice processing capped at configurable timeout |
| Batch size limit | Configurable max invoices per batch (default: 500) |

---

## 9. Security & Guardrails

| Guardrail | Implementation |
|-----------|---------------|
| Feature flag | `ENABLE_ERP_BRIDGE=false` by default; must be explicitly enabled |
| File type validation | Only `.csv` files accepted; reject all other extensions |
| File size limit | Max 5 MB per CSV file (configurable) |
| Row count limit | Max 10,000 rows per CSV file (configurable) |
| No existing code modification | Entirely new module under `src/erp_bridge/` |
| Duplicate prevention | Fingerprint-based dedup (Invoice_No + Party_GSTIN + Date) |
| Tally timeout | Connection timeout 30s, read timeout 60s |
| Tally retry | Exponential backoff, max 3 retries |
| Input sanitization | Strip and validate all CSV fields before XML generation |
| XML injection prevention | Proper XML escaping for all user-provided values |
| GSTIN masking in logs | Audit logs mask middle digits of GSTIN |
| Dry run mode | Allow validation + XML generation without posting to Tally |

---

## 10. Configuration (Environment Variables)

All new configuration for the ERP Bridge will be added as new environment variables, with no changes to existing configuration.

```env
# ERP Bridge - Feature Flag
ENABLE_ERP_BRIDGE=false

# ERP Bridge - Tally Connection
TALLY_HOST=localhost
TALLY_PORT=9000
TALLY_TIMEOUT_CONNECT=30
TALLY_TIMEOUT_READ=60
TALLY_MAX_RETRIES=3
TALLY_COMPANY_NAME=My Company Pvt Ltd

# ERP Bridge - Processing Limits
ERP_BRIDGE_MAX_FILE_SIZE_MB=5
ERP_BRIDGE_MAX_ROWS=10000
ERP_BRIDGE_MAX_BATCH_SIZE=500
ERP_BRIDGE_INVOICE_TIMEOUT=120

# ERP Bridge - Tally Lookup
ENABLE_TALLY_LOOKUP=false

# ERP Bridge - Audit Logging
ERP_BRIDGE_AUDIT_LOG_DIR=logs/erp_bridge
ERP_BRIDGE_AUDIT_LOG_MAX_MB=10
ERP_BRIDGE_AUDIT_LOG_BACKUP_COUNT=5
```

---

## 11. Proposed Directory Structure

```
src/
├── erp_bridge/                     # NEW - Entirely isolated module
│   ├── __init__.py
│   ├── csv_schema_validator.py     # CSV structure validation
│   ├── csv_loader_service.py       # CSV parsing and joining
│   ├── erp_validation_engine.py    # Business rules + GST checks
│   ├── gst_calculation.py          # GST calc adapter (isolated)
│   ├── tally_lookup_service.py     # Optional Tally master data lookup
│   ├── tally_xml_builder.py        # XML generation
│   ├── tally_connector.py          # HTTP communication with Tally
│   ├── tally_response_parser.py    # Parse Tally XML responses
│   ├── erp_batch_processor.py      # Batch processing orchestrator
│   ├── erp_audit_logger.py         # Audit trail logging
│   ├── mcp_tools.py                # MCP tool endpoint definitions
│   ├── models.py                   # Data classes / type definitions
│   └── erp_config.py               # ERP Bridge specific config
│
├── bot/                            # UNCHANGED
├── parsing/                        # UNCHANGED
├── ocr/                            # UNCHANGED
├── sheets/                         # UNCHANGED
├── features/                       # UNCHANGED
├── commands/                       # UNCHANGED
├── utils/                          # UNCHANGED
└── config.py                       # MINIMAL CHANGE: add ENABLE_ERP_BRIDGE flag only

docs/
├── erp-bridge/                     # NEW - ERP Bridge documentation
│   ├── EPIC_PLAN.md                # This document
│   ├── CSV_SCHEMA.md               # CSV format specification
│   ├── TALLY_XML_REFERENCE.md      # Tally XML templates
│   └── MCP_TOOLS_REFERENCE.md      # MCP endpoint documentation
│
├── main/                           # UNCHANGED
├── guides/                         # UNCHANGED
└── technical/                      # UNCHANGED
```

---

## 12. Reusable Patterns from Existing Codebase

The following existing modules contain patterns and logic that the ERP Bridge will reference (but not import from) to maintain strict isolation:

| Existing Module | Reusable Pattern | ERP Bridge Usage |
|----------------|-----------------|-----------------|
| `src/parsing/gst_validator.py` | GST validation rules, tolerance thresholds, tax type consistency checks | Replicate validation logic in `erp_validation_engine.py` |
| `src/features/audit_logger.py` | Audit metadata generation pattern, structured logging format | Reference for `erp_audit_logger.py` design |
| `src/features/dedup_manager.py` | Fingerprint generation (GSTIN + Invoice_No + Date), normalization logic | Replicate dedup logic in `erp_batch_processor.py` |
| `src/utils/batch_processor.py` | Error isolation pattern, progress tracking, batch result schema | Reference for `erp_batch_processor.py` design |
| `src/config.py` | Feature flag pattern, env var loading, writable path resolution | Reference for `erp_config.py` design |

---

## 13. Implementation Phases

### Phase 1: Foundation (Sprint 1)
- [ ] Set up `src/erp_bridge/` package structure
- [ ] Implement `erp_config.py` with feature flag
- [ ] Implement `models.py` with data classes
- [ ] Implement `csv_schema_validator.py`
- [ ] Implement `csv_loader_service.py`
- [ ] Unit tests for CSV parsing and validation

### Phase 2: Validation & GST (Sprint 2)
- [ ] Implement `erp_validation_engine.py`
- [ ] Implement `gst_calculation.py`
- [ ] Business rule validation tests
- [ ] GST calculation cross-verification tests

### Phase 3: Tally XML (Sprint 3)
- [ ] Implement `tally_xml_builder.py` (Sales Invoice)
- [ ] Implement `tally_xml_builder.py` (Purchase Invoice)
- [ ] Implement `tally_xml_builder.py` (Sales Order)
- [ ] XML generation tests with Tally validation

### Phase 4: Tally Connectivity (Sprint 4)
- [ ] Implement `tally_connector.py`
- [ ] Implement `tally_response_parser.py`
- [ ] Implement `tally_lookup_service.py`
- [ ] Integration tests with Tally instance

### Phase 5: Batch & Audit (Sprint 5)
- [ ] Implement `erp_batch_processor.py`
- [ ] Implement `erp_audit_logger.py`
- [ ] Duplicate detection and idempotency tests
- [ ] Batch processing stress tests

### Phase 6: MCP Integration (Sprint 6)
- [ ] Implement `mcp_tools.py` (csv_to_tally, validate_csv, tally_connection_test)
- [ ] End-to-end integration tests
- [ ] Documentation finalization

### Phase 7: Hardening (Sprint 7)
- [ ] Security review (input sanitization, XML injection)
- [ ] Performance testing (large batch, slow Tally)
- [ ] Error handling review
- [ ] Regression testing of existing GST Scanner flows
- [ ] Production readiness checklist

---

## 14. Definition of Done

| Criteria | Verification |
|----------|-------------|
| No regression in existing flows | All existing tests pass; no changes to existing modules (except feature flag in config.py) |
| Proper logging per invoice | Every processed invoice has a complete audit log entry |
| Duplicate prevention working | Re-running same CSV skips already-created vouchers |
| Batch processing stable | 500-invoice batch completes without crash; failures isolated |
| Production-ready XML generation | Generated XML accepted by Tally Prime and Tally ERP 9 |
| All three voucher types supported | Sales Invoice, Purchase Invoice, Sales Order all functional |
| Feature flag gating works | With `ENABLE_ERP_BRIDGE=false`, all ERP Bridge tools return "feature disabled" |
| Dry run mode works | Can validate and generate XML without touching Tally |
| CSV validation comprehensive | Invalid CSVs rejected with clear, actionable error messages |
| Security guardrails in place | File size limits, row limits, XML escaping, GSTIN masking all verified |

---

## 15. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Tally XML format varies between versions | Medium | High | Test against both Tally Prime and ERP 9; make XML templates configurable |
| Large CSV files cause memory issues | Low | Medium | Stream-process CSV files; enforce row limits |
| Tally is offline during batch processing | Medium | Medium | Retry logic with exponential backoff; graceful error reporting |
| Ledger names in CSV don't match Tally | High | Medium | Tally lookup service with clear error messages; dry run mode |
| Duplicate vouchers created on retry | Medium | High | Fingerprint-based dedup; Tally duplicate check before posting |
| Impact on existing GST Scanner | Low | Critical | Complete module isolation; feature flag; no shared imports |

---

## 16. Dependencies

### External Dependencies (New)
- `requests` - HTTP client for Tally communication (likely already available)
- `lxml` or `xml.etree.ElementTree` - XML generation (stdlib)
- `csv` - CSV parsing (stdlib)
- `uuid` - Batch ID generation (stdlib)

### No New Third-Party Dependencies Expected
The implementation should use Python stdlib where possible. The existing `requirements.txt` should not need changes unless a specific library (e.g., `lxml` for advanced XML handling) is deemed necessary during implementation.

---

**End of Epic Plan**

*This document will be updated as the planning phase progresses and before any implementation begins.*
