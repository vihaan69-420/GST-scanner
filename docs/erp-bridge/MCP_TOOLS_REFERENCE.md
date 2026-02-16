# ERP Bridge - MCP Tools Reference

**Version:** 0.1.0 (Planning Phase)
**Created:** February 14, 2026
**Parent Document:** [EPIC_PLAN.md](EPIC_PLAN.md)

---

## Overview

The ERP Bridge exposes three MCP tools for CSV-to-Tally invoice processing. All tools are gated behind the `ENABLE_ERP_BRIDGE` feature flag and will return a structured error if the feature is disabled.

---

## 1. Tool: `csv_to_tally`

### Description

Process CSV invoice files (Summary + Line Items) and create vouchers in Tally ERP. Supports Sales Invoice, Purchase Invoice, and Sales Order voucher types. Processes invoices sequentially with per-invoice error isolation.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `summary_csv_path` | string | Yes | - | Absolute or relative path to the Summary/Header CSV file |
| `items_csv_path` | string | Yes | - | Absolute or relative path to the Line Items CSV file |
| `tally_company` | string | No | `TALLY_COMPANY_NAME` env var | Tally company name to import vouchers into |
| `dry_run` | boolean | No | `false` | If true, validate and generate XML only; do not post to Tally |
| `skip_duplicates` | boolean | No | `true` | If true, skip invoices that already exist in Tally |

### Workflow

```
1. Feature flag check (ENABLE_ERP_BRIDGE)
2. File existence and size validation
3. CSV schema validation (both files)
4. CSV parsing and joining (Summary + Items)
5. Per-invoice processing loop:
   a. Business rule validation
   b. GST calculation cross-check
   c. Duplicate detection (if skip_duplicates=true)
   d. Tally XML generation
   e. POST to Tally (unless dry_run=true)
   f. Response parsing
   g. Audit log entry
6. Return batch result summary
```

### Success Response

```json
{
  "success": true,
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "dry_run": false,
  "timestamp": "2026-02-14T10:30:00Z",
  "summary": {
    "total_invoices": 10,
    "successful": 8,
    "failed": 1,
    "skipped_duplicates": 1,
    "processing_time_seconds": 45.2
  },
  "results": [
    {
      "invoice_no": "INV-2026-001",
      "voucher_type": "Sales",
      "status": "SUCCESS",
      "tally_voucher_id": "12345",
      "tally_voucher_number": "INV-2026-001",
      "processing_time_seconds": 3.1,
      "validation_warnings": []
    },
    {
      "invoice_no": "INV-2026-002",
      "voucher_type": "Sales",
      "status": "FAILED",
      "error": "Tally error: Ledger 'XYZ Enterprises' is not defined",
      "processing_time_seconds": 2.8,
      "validation_warnings": ["Rounding difference of Rs 0.12 in CGST"]
    },
    {
      "invoice_no": "INV-2026-003",
      "voucher_type": "Purchase",
      "status": "SKIPPED",
      "reason": "Duplicate: voucher INV-2026-003 already exists in Tally",
      "processing_time_seconds": 0.5,
      "validation_warnings": []
    }
  ],
  "audit_log_path": "logs/erp_bridge/batch_550e8400.json"
}
```

### Dry Run Response

When `dry_run=true`, the response includes generated XML for review:

```json
{
  "success": true,
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "dry_run": true,
  "timestamp": "2026-02-14T10:30:00Z",
  "summary": {
    "total_invoices": 10,
    "valid": 9,
    "invalid": 1,
    "processing_time_seconds": 2.5
  },
  "results": [
    {
      "invoice_no": "INV-2026-001",
      "voucher_type": "Sales",
      "status": "VALID",
      "validation_warnings": [],
      "xml_preview": "<VOUCHER VCHTYPE=\"Sales\" ...>...</VOUCHER>"
    },
    {
      "invoice_no": "INV-2026-004",
      "voucher_type": "Sales",
      "status": "INVALID",
      "validation_errors": [
        "IGST amount mismatch: header says 600.00, line items sum to 500.00"
      ]
    }
  ]
}
```

### Error Responses

**Feature disabled:**
```json
{
  "success": false,
  "error": "ERP Bridge feature is disabled. Set ENABLE_ERP_BRIDGE=true to enable.",
  "error_code": "FEATURE_DISABLED"
}
```

**File not found:**
```json
{
  "success": false,
  "error": "Summary CSV file not found: /path/to/invoices_summary.csv",
  "error_code": "FILE_NOT_FOUND"
}
```

**File too large:**
```json
{
  "success": false,
  "error": "File exceeds maximum size of 5 MB: invoices_summary.csv (7.2 MB)",
  "error_code": "FILE_TOO_LARGE"
}
```

**CSV schema invalid:**
```json
{
  "success": false,
  "error": "CSV schema validation failed",
  "error_code": "SCHEMA_INVALID",
  "details": {
    "summary_file_errors": [
      {"row": 1, "column": "Voucher_Type", "message": "Missing required column"}
    ],
    "items_file_errors": []
  }
}
```

**Tally connection failed:**
```json
{
  "success": false,
  "error": "Cannot connect to Tally at localhost:9000 after 3 retries",
  "error_code": "TALLY_CONNECTION_FAILED"
}
```

---

## 2. Tool: `validate_csv`

### Description

Validate CSV files without processing them. Returns a comprehensive validation report covering schema validation, business rules, GST calculations, and cross-file consistency. Use this tool to check files before running `csv_to_tally`.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `summary_csv_path` | string | Yes | - | Path to the Summary/Header CSV file |
| `items_csv_path` | string | Yes | - | Path to the Line Items CSV file |

### Workflow

```
1. Feature flag check
2. File existence and size validation
3. CSV schema validation (column names, data types)
4. CSV parsing
5. Business rule validation per invoice
6. GST calculation cross-check per invoice
7. Cross-file consistency checks
8. Return validation report
```

### Success Response (All Valid)

```json
{
  "success": true,
  "valid": true,
  "timestamp": "2026-02-14T10:30:00Z",
  "summary_file": {
    "path": "invoices_summary.csv",
    "rows": 10,
    "valid_rows": 10,
    "schema_errors": [],
    "voucher_type_breakdown": {
      "Sales": 7,
      "Purchase": 2,
      "Sales Order": 1
    }
  },
  "items_file": {
    "path": "invoices_items.csv",
    "rows": 25,
    "valid_rows": 25,
    "schema_errors": []
  },
  "business_rules": {
    "errors": [],
    "warnings": [
      {
        "invoice_no": "INV-2026-005",
        "message": "Rounding difference of Rs 0.15 between calculated and stated CGST"
      }
    ]
  },
  "cross_file_checks": {
    "orphan_line_items": [],
    "invoices_without_items": [],
    "taxable_value_mismatches": [],
    "gst_amount_mismatches": []
  }
}
```

### Success Response (Validation Failures)

```json
{
  "success": true,
  "valid": false,
  "timestamp": "2026-02-14T10:30:00Z",
  "summary_file": {
    "path": "invoices_summary.csv",
    "rows": 10,
    "valid_rows": 8,
    "schema_errors": [
      {
        "row": 3,
        "column": "Party_GSTIN",
        "value": "29AABCU960",
        "message": "Invalid GSTIN format: must be 15 characters",
        "severity": "ERROR"
      },
      {
        "row": 7,
        "column": "Invoice_Date",
        "value": "2026-02-14",
        "message": "Invalid date format: expected DD/MM/YYYY",
        "severity": "ERROR"
      }
    ]
  },
  "items_file": {
    "path": "invoices_items.csv",
    "rows": 25,
    "valid_rows": 23,
    "schema_errors": [
      {
        "row": 12,
        "column": "GST_Rate",
        "value": "15",
        "message": "Invalid GST rate: must be one of 0, 0.25, 3, 5, 12, 18, 28",
        "severity": "ERROR"
      }
    ]
  },
  "business_rules": {
    "errors": [
      {
        "invoice_no": "INV-2026-003",
        "message": "Tax type mismatch: intra-state supply but IGST amounts provided"
      }
    ],
    "warnings": []
  },
  "cross_file_checks": {
    "orphan_line_items": ["INV-2026-099"],
    "invoices_without_items": [],
    "taxable_value_mismatches": [
      {
        "invoice_no": "INV-2026-005",
        "header_value": "10000.00",
        "items_sum": "9500.00",
        "difference": "500.00"
      }
    ],
    "gst_amount_mismatches": []
  }
}
```

---

## 3. Tool: `tally_connection_test`

### Description

Test connectivity to Tally ERP and verify that the specified company exists and is accessible. Use this tool to verify configuration before processing invoices.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tally_host` | string | No | `TALLY_HOST` env var | Tally server hostname or IP |
| `tally_port` | integer | No | `TALLY_PORT` env var | Tally server port |
| `company_name` | string | No | `TALLY_COMPANY_NAME` env var | Company name to verify |

### Workflow

```
1. Feature flag check
2. Attempt TCP connection to Tally host:port
3. Send company list request XML
4. Parse response for company names
5. Verify target company exists in response
6. Return connection report
```

### Success Response

```json
{
  "success": true,
  "connected": true,
  "tally_host": "localhost",
  "tally_port": 9000,
  "response_time_ms": 120,
  "tally_version": "Tally Prime Release 5.0",
  "companies": ["My Company Pvt Ltd", "Demo Company"],
  "target_company": "My Company Pvt Ltd",
  "company_found": true
}
```

### Failure Response (Connection Refused)

```json
{
  "success": false,
  "connected": false,
  "tally_host": "localhost",
  "tally_port": 9000,
  "error": "Connection refused: Tally is not running or not accepting connections on localhost:9000",
  "error_code": "CONNECTION_REFUSED",
  "troubleshooting": [
    "Ensure Tally is running",
    "Check that Tally's XML server is enabled (F12 > Advanced > Enable XML Server)",
    "Verify the port number matches Tally's configuration"
  ]
}
```

### Failure Response (Company Not Found)

```json
{
  "success": false,
  "connected": true,
  "tally_host": "localhost",
  "tally_port": 9000,
  "response_time_ms": 85,
  "companies": ["Demo Company", "Test Company"],
  "target_company": "My Company Pvt Ltd",
  "company_found": false,
  "error": "Company 'My Company Pvt Ltd' not found in Tally",
  "error_code": "COMPANY_NOT_FOUND",
  "troubleshooting": [
    "Verify the company name matches exactly (case-sensitive)",
    "Ensure the company is loaded in Tally",
    "Available companies: Demo Company, Test Company"
  ]
}
```

---

## 4. Error Code Reference

| Error Code | HTTP Analogy | Description |
|-----------|-------------|-------------|
| `FEATURE_DISABLED` | 403 | ERP Bridge feature flag is off |
| `FILE_NOT_FOUND` | 404 | CSV file path does not exist |
| `FILE_TOO_LARGE` | 413 | CSV file exceeds size limit |
| `FILE_INVALID_TYPE` | 415 | File is not a .csv file |
| `SCHEMA_INVALID` | 422 | CSV does not match expected schema |
| `VALIDATION_FAILED` | 422 | Business rule validation failed |
| `TALLY_CONNECTION_FAILED` | 502 | Cannot connect to Tally |
| `TALLY_TIMEOUT` | 504 | Tally did not respond in time |
| `TALLY_IMPORT_ERROR` | 502 | Tally rejected the voucher XML |
| `COMPANY_NOT_FOUND` | 404 | Target company not found in Tally |
| `DUPLICATE_VOUCHER` | 409 | Voucher already exists in Tally |
| `INTERNAL_ERROR` | 500 | Unexpected error in ERP Bridge |

---

## 5. Feature Flag Behavior

| Flag Value | `csv_to_tally` | `validate_csv` | `tally_connection_test` |
|-----------|----------------|-----------------|------------------------|
| `ENABLE_ERP_BRIDGE=true` | Fully operational | Fully operational | Fully operational |
| `ENABLE_ERP_BRIDGE=false` | Returns `FEATURE_DISABLED` | Returns `FEATURE_DISABLED` | Returns `FEATURE_DISABLED` |
| Not set (default) | Returns `FEATURE_DISABLED` | Returns `FEATURE_DISABLED` | Returns `FEATURE_DISABLED` |

---

## 6. Rate Limiting & Concurrency

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| Max concurrent batches | 1 | Tally processes requests sequentially |
| Max invoices per batch | 500 | Prevent resource exhaustion |
| Delay between Tally requests | 100ms | Avoid overwhelming Tally |
| Max file uploads per call | 2 (summary + items) | By design |

---

## 7. MCP Tool Registration

The tools will be registered in `src/erp_bridge/mcp_tools.py` following MCP tool conventions:

```python
# Planned tool registration pattern (pseudocode)

@mcp_tool(
    name="csv_to_tally",
    description="Process CSV invoice files and create vouchers in Tally ERP",
    parameters={
        "summary_csv_path": {"type": "string", "required": True},
        "items_csv_path": {"type": "string", "required": True},
        "tally_company": {"type": "string", "required": False},
        "dry_run": {"type": "boolean", "required": False, "default": False},
        "skip_duplicates": {"type": "boolean", "required": False, "default": True},
    }
)
async def csv_to_tally(params):
    ...

@mcp_tool(
    name="validate_csv",
    description="Validate CSV invoice files without processing",
    parameters={
        "summary_csv_path": {"type": "string", "required": True},
        "items_csv_path": {"type": "string", "required": True},
    }
)
async def validate_csv(params):
    ...

@mcp_tool(
    name="tally_connection_test",
    description="Test connectivity to Tally ERP",
    parameters={
        "tally_host": {"type": "string", "required": False},
        "tally_port": {"type": "integer", "required": False},
        "company_name": {"type": "string", "required": False},
    }
)
async def tally_connection_test(params):
    ...
```

---

## 8. Usage Examples

### Example 1: Full Processing

```
User: Process these invoices and send them to Tally.

Tool call: csv_to_tally(
  summary_csv_path="/data/feb_2026_summary.csv",
  items_csv_path="/data/feb_2026_items.csv"
)
```

### Example 2: Validation Only

```
User: Check if my CSV files are correct before sending to Tally.

Tool call: validate_csv(
  summary_csv_path="/data/feb_2026_summary.csv",
  items_csv_path="/data/feb_2026_items.csv"
)
```

### Example 3: Dry Run

```
User: Generate the Tally XML but don't send it yet, I want to review.

Tool call: csv_to_tally(
  summary_csv_path="/data/feb_2026_summary.csv",
  items_csv_path="/data/feb_2026_items.csv",
  dry_run=true
)
```

### Example 4: Connection Test

```
User: Is Tally running and can we connect to it?

Tool call: tally_connection_test(
  company_name="My Company Pvt Ltd"
)
```

---

**End of MCP Tools Reference**
