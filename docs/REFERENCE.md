# GST Scanner - Complete Reference

**Version:** 2.0  
**Last Updated:** February 2026  
**Status:** Production-Ready

Complete end-to-end GST invoice scanner that receives invoice images via Telegram, performs OCR using Google Gemini Vision API, extracts GST-compliant data, and appends to Google Sheets with comprehensive audit trails and export capabilities.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Setup & Configuration](#3-setup--configuration)
4. [User Guide](#4-user-guide)
5. [Features by Tier](#5-features-by-tier)
6. [Order Upload (Epic 2)](#6-order-upload-epic-2)
7. [Pricing Integration](#7-pricing-integration)
8. [OCR Improvements](#8-ocr-improvements)
9. [Usage & Cost Tracking](#9-usage--cost-tracking)
10. [Monitoring & Dashboard](#10-monitoring--dashboard)
11. [Testing](#11-testing)
12. [Troubleshooting & Rollback](#12-troubleshooting--rollback)
13. [Operations](#13-operations)
14. [Technical Reference](#14-technical-reference)

---

## 1. Project Overview

### Directory Structure

```
GST-scanner/
├── src/               # Application source code
│   ├── bot/           # Telegram bot interface
│   ├── parsing/       # GST parsing & validation
│   ├── ocr/           # OCR processing
│   ├── sheets/        # Google Sheets integration
│   ├── exports/       # GSTR exports & reports
│   ├── features/      # Advanced Tier 2 features
│   ├── commands/      # Bot command handlers
│   ├── utils/         # Utilities (monitoring, dashboard, batch)
│   ├── order_normalization/  # Epic 2: Order upload module
│   └── config.py      # Application configuration
├── docs/              # Documentation
├── tests/             # Test suite (unit + integration)
├── scripts/           # Utility & deployment scripts
├── config/            # Configuration files (credentials.json)
├── temp/              # Temporary files (auto-created)
├── exports/           # Export outputs (auto-created)
├── logs/              # Log files (auto-created)
├── orders/            # Generated order PDFs (auto-created)
├── requirements.txt   # Python dependencies
├── start_bot.py       # Main launcher
├── run_bot.py         # Alternative launcher
└── .env               # Environment variables (user creates)
```

### Key Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/bot/telegram_bot.py` | ~1,600 | Main bot with menu system, session management, all commands |
| `src/sheets/sheets_manager.py` | ~988 | Google Sheets operations, 5 sheets management |
| `src/parsing/gst_parser.py` | ~319 | GST data extraction with Gemini |
| `src/parsing/line_item_extractor.py` | ~210 | Line item extraction |
| `src/parsing/gst_validator.py` | ~280 | GST validation engine |
| `src/ocr/ocr_engine.py` | ~120 | OCR with Gemini Vision |
| `src/config.py` | ~345 | Configuration management |
| `src/exports/gstr1_exporter.py` | ~636 | GSTR-1 export engine |
| `src/exports/gstr3b_generator.py` | ~376 | GSTR-3B summary generator |
| `src/commands/tier3_commands.py` | ~511 | Tier 3 command handlers |
| `src/utils/batch_processor.py` | ~418 | Batch processing engine |

### System Requirements

- Python 3.8+
- Windows 10/11 (PowerShell) or Linux
- Internet connection
- Google Sheets API access
- Telegram Bot API access
- Google Gemini API access

---

## 2. Architecture

### System Diagram

```
User (Telegram)
    |
    v
Telegram Bot (telegram_bot.py) + Menu System
    |
    v
OCR Engine (ocr_engine.py) --> Google Gemini 2.5 Flash Vision
    |
    v
GST Parser (gst_parser.py) --> Google Gemini 2.5 Flash
    |-- Line Item Extractor (line_item_extractor.py)
    |-- GST Validator (gst_validator.py)
    |
    v
Tier 2 Components (if enabled)
    |-- Confidence Scorer (confidence_scorer.py)
    |-- Correction Manager (correction_manager.py)
    |-- Deduplication Manager (dedup_manager.py)
    |-- Audit Logger (audit_logger.py)
    |
    v
Sheets Manager (sheets_manager.py) --> Google Sheets API
    |-- Invoice_Header (41 columns: Tier 1 + Tier 2)
    |-- Line_Items (19 columns)
    |-- Customer_Master (auto-learning)
    |-- HSN_Master (auto-learning)
    |
    v
Tier 3 Exports (tier3_commands.py)
    |-- GSTR-1 Exporter (gstr1_exporter.py)
    |-- GSTR-3B Generator (gstr3b_generator.py)
    |-- Operational Reports (operational_reports.py)
```

### Data Flow

**Phase 1 - Image Collection:** User sends invoice images via Telegram. Bot validates format, saves to temp folder, tracks in user session.

**Phase 2 - OCR Processing:** Each image is sent to Gemini Vision API. Text is extracted from all pages and merged.

**Phase 3 - GST Data Extraction:** Combined OCR text is sent to Gemini Flash with a structured extraction prompt. Returns validated JSON with 24 GST fields plus line items.

**Phase 4 - Google Sheets Update:** Sheets Manager checks for duplicates, appends invoice header row (41 columns), appends line items, updates Customer_Master and HSN_Master.

### Component Details

| Component | Responsibility |
|-----------|---------------|
| **config.py** | Loads `.env`, validates credentials, defines Sheets column schema |
| **ocr_engine.py** | Gemini Vision API calls, text extraction, layout preservation |
| **gst_parser.py** | Gemini Flash for structured extraction, GST validation, JSON output |
| **sheets_manager.py** | Service account auth, multi-sheet management, dedup, master data |
| **telegram_bot.py** | User interaction, session management, workflow orchestration |

### Google Sheets Schema

**Invoice_Header (41 columns):**
- Columns A-X (1-24): Tier 1 fields -- Invoice_No, Invoice_Date, Invoice_Type, Seller/Buyer details, GST amounts, Validation_Status, Validation_Remarks
- Columns Y-AE (25-31): Tier 2 audit fields -- Upload_Timestamp, Telegram_User_ID, Username, Extraction_Version, Model_Version, Processing_Time, Page_Count
- Columns AF-AH (32-34): Tier 2 corrections -- Has_Corrections, Corrected_Fields, Correction_Metadata
- Columns AI-AJ (35-36): Tier 2 deduplication -- Invoice_Fingerprint, Duplicate_Status
- Columns AK-AO (37-41): Tier 2 confidence scores (5 key fields, 0.0-1.0)

**Line_Items (19 columns):** Invoice_No, Line_No, Item_Code, Description, HSN, Qty, UOM, Rate, Discount, Taxable_Value, GST_Rate, CGST/SGST/IGST rates and amounts, Cess_Amount, Line_Total

**Customer_Master (7 columns):** GSTIN, Legal_Name, Trade_Name, State_Code, Default_Place_Of_Supply, Last_Updated, Usage_Count

**HSN_Master (7 columns):** HSN_SAC_Code, Description, Default_GST_Rate, UQC, Category, Last_Updated, Usage_Count

---

## 3. Setup & Configuration

### Prerequisites

- Python 3.8+ installed
- A Telegram account
- A Google account with Google Sheet created

### Step 1: Install Dependencies

```powershell
pip install -r requirements.txt
```

### Step 2: Create Telegram Bot

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow prompts
3. Copy the bot token (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 3: Get Google Gemini API Key

1. Visit https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key (starts with `AIza...`)

### Step 4: Set Up Google Sheets API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "GST Scanner"
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to IAM & Admin > Service Accounts > Create Service Account
   - Name: "gst-scanner-bot", Role: "Editor"
5. Create JSON key, download, rename to `credentials.json`
6. Place in `config/credentials.json`
7. Open `credentials.json`, copy the `client_email` value
8. Open your Google Sheet > Share > paste service account email > Editor permission

### Step 5: Get Google Sheet ID

From the Sheet URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit` -- copy the `{SHEET_ID}` part.

### Step 6: Configure Environment

```powershell
copy .env.example .env
```

Edit `.env` with your values:

```env
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GOOGLE_API_KEY=your_google_gemini_api_key_here
GOOGLE_SHEETS_CREDENTIALS_FILE=config/credentials.json
GOOGLE_SHEET_ID=your_google_sheet_id_here
SHEET_NAME=Invoice_Header

# Optional (defaults shown)
LINE_ITEMS_SHEET_NAME=Line_Items
CUSTOMER_MASTER_SHEET=Customer_Master
HSN_MASTER_SHEET=HSN_Master
MAX_IMAGES_PER_INVOICE=10
TEMP_FOLDER=temp
EXPORT_FOLDER=exports
ALLOWED_IMAGE_FORMATS=jpg,jpeg,png,pdf

# Tier 2 Feature Flags
ENABLE_CONFIDENCE_SCORING=true
ENABLE_MANUAL_CORRECTIONS=true
ENABLE_DEDUPLICATION=true
ENABLE_AUDIT_LOGGING=false
CONFIDENCE_THRESHOLD_REVIEW=0.7

# Tier 3 Settings
EXCLUDE_ERROR_INVOICES=false

# Monitoring
LOG_LEVEL=INFO
HEALTH_SERVER_PORT=8080
HEALTH_SERVER_ENABLED=true

# Epic 2: Order Upload (disabled by default)
FEATURE_ORDER_UPLOAD_NORMALIZATION=false
PRICING_SHEET_SOURCE=google_sheet
PRICING_SHEET_ID=
PRICING_SHEET_NAME=Sheet1

# Usage Tracking (disabled by default)
ENABLE_USAGE_TRACKING=false
```

### Step 7: Verify & Start

```powershell
python tests\integration\test_system.py   # Run tests
python start_bot.py                        # Start the bot
```

### Security Notes

- NEVER commit `.env` or `credentials.json`
- `.gitignore` is already configured to exclude these
- Rotate API keys periodically
- Use service account (not personal Google account)

---

## 4. User Guide

### Quick Start

1. Open Telegram, find your bot
2. Send `/start`
3. Send invoice image(s)
4. Type `/done`
5. Wait for confirmation

### Commands Reference

| Command | Purpose |
|---------|---------|
| `/start` | Welcome message with main menu |
| `/menu` | Show main menu anytime |
| `/help` | Detailed help |
| `/cancel` | Cancel current operation |
| `/upload` | Show upload options |
| `/done` | Process uploaded invoice(s) |
| `/next` | Save current and start next (batch mode) |
| `/confirm` | Save without corrections (Tier 2) |
| `/correct` | Enter correction mode (Tier 2) |
| `/override` | Override duplicate warning (Tier 2) |
| `/export_gstr1` | Generate GSTR-1 exports (Tier 3) |
| `/export_gstr3b` | Generate GSTR-3B summary (Tier 3) |
| `/reports` | Generate operational reports (Tier 3) |
| `/stats` | Quick statistics (Tier 3) |
| `/order_upload` | Start order upload session (Epic 2) |
| `/order_submit` | Submit order for processing (Epic 2) |

### Invoice Upload Workflow

**Single-page invoice:**
```
You: [Send photo]
Bot: "Page 1 received! Send more or type /done"
You: /done
Bot: Processing... -> Success! Data appended to Google Sheet.
```

**Multi-page invoice:**
```
You: [Send page 1]
Bot: "Page 1 received!"
You: [Send page 2]
Bot: "Page 2 received!"
You: /done
Bot: Processing 2 pages... -> Success!
```

### Image Guidelines

**Do:** Clear, well-lit photos; capture entire invoice; JPG or PNG format; send pages in order.

**Don't:** Blurry/dark images; cut off parts; extreme angles; mix different invoices.

### Orders vs Invoices

| | Orders | Invoices |
|---|--------|----------|
| **Input** | Handwritten order notes | Printed GST invoices |
| **Start** | `/order_upload` | `/upload` |
| **Submit** | `/order_submit` | `/done` |
| **Output** | Clean PDF invoice | Data in Google Sheets |

### Processing Times

- Single page invoice: 10-15 seconds
- Multi-page invoice: 15-30 seconds
- Order processing: 60-120 seconds

---

## 5. Features by Tier

### Tier 1: Core Features

**Telegram Bot Interface** -- Interactive menu system with inline buttons, simple command-based workflow, multi-page invoice support.

**OCR with Gemini Vision** -- Complete text extraction from invoice images, handles various invoice formats.

**GST Data Extraction (24 fields):**
Invoice_No, Invoice_Date, Invoice_Type, Seller_Name, Seller_GSTIN, Seller_State_Code, Buyer_Name, Buyer_GSTIN, Buyer_State_Code, Ship_To_Name, Ship_To_State_Code, Place_Of_Supply, Supply_Type, Reverse_Charge, Invoice_Value, Total_Taxable_Value, Total_GST, IGST_Total, CGST_Total, SGST_Total, Eway_Bill_No, Transporter, Validation_Status, Validation_Remarks

**Line Item Extraction (19 fields per item):**
Invoice_No, Line_No, Item_Code, Description, HSN, Qty, UOM, Rate, Discount, Taxable_Value, GST_Rate, CGST_Rate, CGST_Amount, SGST_Rate, SGST_Amount, IGST_Rate, IGST_Amount, Cess_Amount, Line_Total

**GST Validation Engine:**
- Validates GSTIN format (15 characters)
- Checks IGST vs CGST+SGST rules (only one type per invoice)
- Validates date formats, cross-checks totals
- Adds validation remarks for anomalies

**Google Sheets Integration (5 sheets):**
- Invoice_Header, Line_Items, Customer_Master, HSN_Master, Duplicate_Attempts
- Automatic appending, garbage data prevention, real-time updates

**Line_Items Sheet Setup:**
Create a tab named `Line_Items` with headers in Row 1:
```
Invoice_No | Line_No | Item_Code | Description | HSN | Qty | UOM | Rate |
Discount | Taxable_Value | GST_Rate | CGST_Rate | CGST_Amount | SGST_Rate |
SGST_Amount | IGST_Rate | IGST_Amount | Cess_Amount | Line_Total
```

### Tier 2: Advanced Features

**Confidence Scoring** -- AI-powered scores (0.0-1.0) for 5 critical fields. Automatic flagging below 70% threshold. Helps identify extraction issues.

**Manual Corrections** -- Field-by-field editing via Telegram. Tracks original vs corrected values. Stores correction metadata.

**Deduplication** -- Fingerprint-based matching (invoice no + date + buyer + amount). Prevents duplicate entries. Override capability for legitimate duplicates. All attempts logged.

**Audit Logging** -- Complete processing history: user identification (Telegram ID/username), timestamps, model version, processing duration, page count, correction history.

**Configuration:**
```env
ENABLE_CONFIDENCE_SCORING=true
ENABLE_MANUAL_CORRECTIONS=true
ENABLE_DEDUPLICATION=true
ENABLE_AUDIT_LOGGING=false
CONFIDENCE_THRESHOLD_REVIEW=0.7
```

### Tier 3: Exports & Reports

**GSTR-1 Export:**
- B2B Invoices CSV (Table 4A/4B)
- B2C Small Summary CSV (Table 7)
- HSN Summary CSV (Table 12)
- GST portal CSV schema compliance
- Period-based filtering

```powershell
python src\exports\export_gstr1.py   # Standalone
# Or via Telegram: /export_gstr1
```

**GSTR-3B Summary:**
- Section 3.1: Outward supplies with tax breakdown
- Reverse charge tracking, inter/intra-state analysis
- JSON and formatted text reports

```powershell
python src\exports\export_gstr3b.py   # Standalone
# Or via Telegram: /export_gstr3b
```

**Master Data Auto-Learning:**
- Customer_Master: GSTIN-based tracking, auto-populated from invoices, usage frequency
- HSN_Master: HSN/SAC codes, default GST rates, descriptions, UQC

**Batch Processing:**
```
Send invoice 1 images -> /next -> Send invoice 2 images -> /next -> ... -> /done
```
Sequential processing with error isolation, progress tracking, batch reports.

**Operational Reports (5 types):**
1. Processing Statistics -- volume, success rate, avg time
2. GST Amount Summary -- monthly tax liability
3. Duplicate Analysis -- attempts and patterns
4. Correction Tracking -- most corrected fields
5. Comprehensive Report -- all above combined

```powershell
# Via Telegram:
/reports    # Interactive selection
/stats      # Quick statistics
```

**Export File Locations:**
```
exports/
├── GSTR1_2026_01/
│   ├── B2B_Invoices_2026_01.csv
│   ├── B2C_Small_2026_01.csv
│   ├── HSN_Summary_2026_01.csv
│   └── Export_Report_2026_01.txt
├── GSTR3B_2026_01/
│   ├── GSTR3B_Summary_2026_01.json
│   └── GSTR3B_Report_2026_01.txt
└── Reports_2026_01/
    └── Operational_Reports_2026_01.json
```

---

## 6. Order Upload (Epic 2)

### Overview

Order upload converts handwritten order notes into clean, professional PDF invoices with pricing. Gated behind feature flag `FEATURE_ORDER_UPLOAD_NORMALIZATION`.

### User Flow

```
/order_upload -> [Send photos] -> /order_submit -> Wait 60-120s -> Receive PDF
```

1. User sends `/start`, clicks "Upload Order" button
2. Sends 1+ photos of handwritten order notes
3. Types `/order_submit`
4. Bot processes: OCR + LLM extraction -> Normalization -> Deduplication -> Pricing match -> PDF generation -> Google Sheets upload
5. User receives clean PDF via Telegram

### Architecture

```
GSTScannerBot (feature flag check)
  -> OrderSession (tracks pages)
  -> OrderNormalizationOrchestrator
     |-- OrderExtractor (OCR + LLM via Gemini)
     |-- OrderNormalizer (brand, color, part name cleanup)
     |-- OrderDeduplicator (cross-page signature matching)
     |-- PricingMatcher (fuzzy match with pricing sheet)
     |-- OrderPDFGenerator (reportlab, A4 format)
     |-- OrderSheetsHandler (Google Sheets)
```

### Module Files

All code lives in `src/order_normalization/`:
- `__init__.py`, `order_session.py`, `orchestrator.py`, `extractor.py`, `normalizer.py`, `deduplicator.py`, `pricing_matcher.py`, `pdf_generator.py`, `sheets_handler.py`

### Google Sheets (Additive, New Tabs Only)

- **Orders** -- Order_ID, Customer_Name, Order_Date, Status, Total_Items, Total_Quantity, Subtotal, Unmatched_Count, Page_Count, Created_By, Processed_At
- **Order_Line_Items** -- Order_ID, Serial_No, Part_Name, Part_Number, Model, Color, Quantity, Rate, Line_Total, Match_Confidence
- **Customer_Details** -- Customer_ID, Customer_Name, Contact, Last_Order_Date, Total_Orders

Existing tabs (Invoice_Header, Line_Items) are untouched.

### Configuration

```env
FEATURE_ORDER_UPLOAD_NORMALIZATION=false   # Master flag (default: OFF)
PRICING_SHEET_SOURCE=google_sheet          # or local_file
PRICING_SHEET_ID=your_sheet_id             # Google Sheet with pricing data
PRICING_SHEET_NAME=Sheet1                  # Tab name
PRICING_SHEET_PATH=path/to/file.xls       # For local_file source
MAX_IMAGES_PER_ORDER=10
ORDER_SUMMARY_SHEET=Orders
ORDER_LINE_ITEMS_SHEET=Order_Line_Items
ORDER_CUSTOMER_DETAILS_SHEET=Customer_Details
```

Dependencies: `openpyxl>=3.1.0`, `reportlab>=4.0.0`

### Feature Flag Enforcement

Checked at 3 levels: menu rendering, API callbacks, background processing. Flag OFF = zero behavioral change, zero side effects.

### Error Handling

- Extraction failure: stop and notify user
- Pricing failure: continue with `review_required` status
- PDF failure: sheet write still succeeds
- Sheet failure: user still gets PDF

### Rollback

**Immediate (< 1 minute):**
1. Set `FEATURE_ORDER_UPLOAD_NORMALIZATION=false` in `.env`
2. Restart bot
3. Verify: no "Upload Order" button, GST scanner works normally

**Data preservation:** Google Sheets tabs, processed data, and PDFs remain intact. Only in-memory sessions are lost on restart.

**Re-enable:** Set flag to `true`, restart bot. Sheets tabs are auto-recreated if deleted.

---

## 7. Pricing Integration

### Overview

Google Sheets-based pricing data source for the Order Normalization system. Loads 4,751+ products with fuzzy matching.

### How It Works

1. On bot startup, pricing data is loaded from Google Sheet (10-13 second initial load)
2. During order processing, each line item is fuzzy-matched against pricing data
3. Matched items get price and part number; unmatched items are flagged with price = 0
4. Matching uses SequenceMatcher with 65% similarity threshold plus substring boost

### Configuration

```env
PRICING_SHEET_SOURCE=google_sheet
PRICING_SHEET_ID=1uNUYg0tpBWn7flNENk_kWHvGdimXhhzq3VAQAeNd4GE
PRICING_SHEET_NAME=Sheet1
```

### Pricing Sheet Structure

| Column | Name | Description |
|--------|------|-------------|
| 0 | Part No. | Unique identifier (e.g., SAI-910) |
| 1 | Description | Full product description with model/color |
| 3 | MRP | Price including all taxes |
| 4 | STD PKG | Standard packaging quantity |
| 5 | MASTER PKG | Master carton quantity |

### Administration

- **Update pricing:** Edit the Google Sheet directly, restart bot to reload
- **Switch to local file:** Set `PRICING_SHEET_SOURCE=local_file` and `PRICING_SHEET_PATH=path/to/file.xls`
- **Performance:** Initial load ~10-13s (cached in memory after), matching <100ms per item

---

## 8. OCR Improvements

### Enhancements for Handwritten Orders

**Date Extraction:** Extracts date from document header (DD/MM/YY format) instead of using system date.

**Customer Metadata:** Extracts customer name, mobile number, and location from header area.

**Brand Recognition:** Dedicated `brand` field in extraction schema. "Sai" and similar brands shown in separate column.

**Ditto Mark Handling:** Recognizes `--`, `~~`, `-~-` as "copy from above". Propagates brand name from previous line.

**Accurate Item Count:** Counts only numbered line items. No hallucinated extras from header information.

**Color Code Preservation:** Handles abbreviations: `PA`/`BL` -> Black, `S` -> Silver. Multi-tone colors preserved (e.g., "PA/Grey" -> "Black/Grey"). Uses image-based extraction (Gemini Vision directly) for better handwriting recognition.

### PDF Output

8-column format: S.N, Brand, Part Name, Model, Color, Qty, Rate, Total (upgraded from 6 columns).

---

## 9. Usage & Cost Tracking

### Overview

Three-level tracking system for API usage and costs. All tracking happens AFTER the user receives their success message (background task). Gated behind `ENABLE_USAGE_TRACKING` feature flag.

### Three Levels

**Level 1 - OCR-Level (Per Page/API Call):**
Tracks every Gemini OCR call: tokens, cost, processing time, model used.
Storage: `logs/ocr_calls.jsonl`

**Level 2 - Invoice-Level (Per Invoice):**
Aggregates all OCR and parsing calls: total tokens, total cost, page count, quality metrics.
Storage: `logs/invoice_usage.jsonl`

**Level 3 - Customer-Level (Aggregate):**
Total invoices, costs, averages, outlier detection.
Storage: `logs/customer_usage_summary.json`

### Cost Formulas

```
OCR cost     = (total_tokens / 1000) x GEMINI_OCR_PRICE_PER_1K_TOKENS
Parsing cost = (total_tokens / 1000) x GEMINI_PARSING_PRICE_PER_1K_TOKENS
Invoice cost = OCR cost + Parsing cost
```

### Feature Flags

```env
ENABLE_USAGE_TRACKING=false              # Master switch
ENABLE_OCR_LEVEL_TRACKING=false
ENABLE_INVOICE_LEVEL_TRACKING=false
ENABLE_CUSTOMER_AGGREGATION=false
ENABLE_SUMMARY_GENERATION=false
ENABLE_OUTLIER_DETECTION=false
ENABLE_ACTUAL_TOKEN_CAPTURE=true
GEMINI_OCR_PRICE_PER_1K_TOKENS=0.0001875
GEMINI_PARSING_PRICE_PER_1K_TOKENS=0.000075
```

### Cost Estimates

| API | Model | Per 1K Tokens | Avg Tokens/Call |
|-----|-------|---------------|-----------------|
| OCR (Vision) | Gemini Flash | $0.0001875 | ~2,000 |
| Parsing (Text) | Gemini Flash | $0.000075 | ~1,000 |

| Invoices/Month | Estimated Cost |
|----------------|----------------|
| 100 | $1.10 - $2.10 |
| 500 | $5.50 - $10.50 |
| 1,000 | $11.00 - $21.00 |

---

## 10. Monitoring & Dashboard

### Overview

Real-time monitoring system with structured logging, metrics tracking, health check HTTP endpoints, and a web dashboard.

### Quick Start

```powershell
python start_bot.py              # Bot + health server start together
# Dashboard: http://localhost:8080/dashboard
```

### Dashboard Tabs

**Usage & Costs (Default):** Total invoices, pages, tokens, cost (USD), average cost per invoice, OCR vs parsing breakdown, recent invoices table. Auto-refreshes every 10 seconds.

**Performance:** System uptime, average processing time, active sessions, invoice success/failure counts, integration status (Telegram, Sheets, Gemini).

**Logs:** Real-time log viewer with search, level filtering (DEBUG/INFO/WARNING/ERROR/CRITICAL), adjustable line count (50/100/200/500), color-coded entries.

### HTTP Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Basic health check + integration status |
| `GET /metrics` | Complete system metrics (JSON) |
| `GET /status` | Detailed status with active sessions |
| `GET /usage/customer` | Customer usage summary |
| `GET /usage/invoices` | Recent invoice records (last 20) |
| `GET /usage/ocr-calls` | Recent OCR API calls (last 50) |
| `GET /logs?search=&level=&lines=` | Filtered log entries |
| `GET /dashboard` | HTML dashboard |

### Log Files

| File | Description | Max Size |
|------|-------------|----------|
| `logs/gst_scanner.log` | Main log (all levels) | 10 MB, 5 rotations |
| `logs/errors.log` | Errors only | 5 MB, 3 rotations |
| `logs/metrics.json` | Persisted metrics | Auto-saved |

Log format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] [Component] Message`

### Configuration

```env
LOG_LEVEL=INFO
LOG_FILE_MAX_MB=10
LOG_FILE_BACKUP_COUNT=5
HEALTH_SERVER_PORT=8080
HEALTH_SERVER_ENABLED=true
```

### External Integration

- **Prometheus/Grafana:** Scrape `/metrics` endpoint
- **Uptime monitoring:** Poll `/health` for `"status": "healthy"`
- **Log aggregation:** Forward structured logs to ELK/Splunk/Datadog

---

## 11. Testing

### System Tests

```powershell
python tests\integration\test_system.py    # Main system test
python tests\integration\test_tier1.py     # Tier 1 features
python tests\integration\test_tier2.py     # Tier 2 features
python tests\integration\test_tier3.py     # Tier 3 exports
python tests\test_epic2_isolation.py       # Epic 2 isolation
```

### Live Testing (Telegram)

**Invoice flow:**
1. Send `/start` to bot
2. Send a test invoice image
3. Type `/done`
4. Verify data in Google Sheet (all 41 columns)

**Order flow (with Epic 2 enabled):**
1. Type `/order_upload`
2. Send handwritten order image
3. Type `/order_submit`
4. Verify PDF received and Sheets tabs populated

### Verification Checklist

- [ ] Bot responds to `/start`
- [ ] Invoice upload processes successfully
- [ ] Data appears in Google Sheet correctly
- [ ] All 24 Tier 1 fields extracted
- [ ] GST calculations are correct
- [ ] Line items appear in Line_Items sheet
- [ ] Dashboard accessible at `http://localhost:8080/dashboard`

---

## 12. Troubleshooting & Rollback

### Common Issues

**Bot not responding:**
- Verify bot is running (`python start_bot.py`)
- Check bot token is correct in `.env`
- Check internet connection
- Try `/start` command

**"Configuration validation failed":**
- Check `.env` file exists and all values are filled
- Verify `credentials.json` exists at configured path

**"Failed to open Google Sheet":**
- Verify Sheet ID is correct
- Confirm sheet is shared with service account email (Editor)
- Check sheet name matches exactly (case-sensitive)

**OCR accuracy issues:**
- Ensure images are clear and well-lit
- Send higher resolution images
- Check that all text is readable

**"Cannot submit order" / Order upload not working:**
1. Verify `FEATURE_ORDER_UPLOAD_NORMALIZATION=true` in `.env`
2. Always type `/order_upload` BEFORE sending images
3. Use `/order_submit` (not `/done`) for orders
4. If stuck, type `/cancel` and start over

**"Upload Order" button missing:**
- Check feature flag is enabled
- Likely a Telegram API conflict (multiple bot instances)
- Kill all Python processes, wait 30 seconds, restart bot

**Multiple bot instances / duplicate messages:**
```powershell
# Kill all Python processes
Get-Process python | Stop-Process -Force
# Wait for Telegram API to clear
Start-Sleep -Seconds 30
# Restart
python run_bot.py
```

**Dashboard not loading:**
- Verify health server is running on port 8080
- Check: `Test-NetConnection -ComputerName localhost -Port 8080`
- Ensure no firewall blocking

**"Module not found":**
- Run `pip install -r requirements.txt`
- Ensure running from project root directory

### Rollback Procedures

**Epic 2 (Order Upload):**
1. Set `FEATURE_ORDER_UPLOAD_NORMALIZATION=false`
2. Restart bot
3. Verify: no order button, GST scanner works normally
4. Recovery time: < 1 minute, zero downtime for GST scanning

**Usage Tracking:**
1. Set `ENABLE_USAGE_TRACKING=false`
2. Restart bot
3. All tracking code skipped, zero performance impact

**General rollback:** All features use feature flags. Set flag to `false` and restart.

---

## 13. Operations

### Running the Bot

```powershell
# Option 1: Python (recommended)
python start_bot.py

# Option 2: Batch file (Windows)
scripts\start_bot.bat

# Option 3: With no bytecode caching
python -B run_bot.py
```

### Git Workflow

```powershell
git status                    # Check changes
git add .                     # Stage all
git commit -m "description"   # Commit
git push origin main          # Push
```

### Migration from Old Location

If migrating from `saket worksflow`:

1. Copy `.env` and `credentials.json` to new location
2. Update `.env`:
   ```env
   GOOGLE_SHEETS_CREDENTIALS_FILE=config/credentials.json
   TEMP_FOLDER=temp
   ```
3. Install dependencies: `pip install -r requirements.txt`
4. Run tests: `python tests\integration\test_system.py`
5. Start bot: `python start_bot.py`

Old installation remains untouched as backup.

### Import Path Changes (from v1.0)

```python
# Old (flat structure):
from config import TELEGRAM_BOT_TOKEN
from gst_parser import GSTParser

# New (organized structure):
from config import TELEGRAM_BOT_TOKEN
from parsing.gst_parser import GSTParser
```

---

## 14. Technical Reference

### Menu System

The Telegram bot uses an interactive inline button menu:

**Main Menu (4 buttons):**
1. Upload Purchase Invoice
2. Upload Order (Epic 2, feature-flagged)
3. Generate GST Input
4. Help

**Sub-menus:** Upload options (single, batch, document), GST options (GSTR-1, GSTR-3B, reports, stats).

Total: 22 callback handlers for menu navigation.

### Performance Profile

Typical processing time for a single invoice (e.g., Invoice B6580):

| Phase | Time |
|-------|------|
| OCR (per page) | 3-5 seconds |
| GST Parsing | 2-3 seconds |
| Sheets Update | 1-2 seconds |
| **Total (1 page)** | **6-10 seconds** |
| **Total (multi-page)** | **15-30 seconds** |

Order processing: 60-120 seconds (includes PDF generation and pricing match).

Export generation: 100 invoices < 30s, 500 < 2min, 1000+ < 5min.

### Configuration Analysis

Items correctly using environment variables: ~85% of configurable values.

**Key configurable items:**
- All API keys and credentials (via `.env`)
- Sheet names and IDs (via `.env`)
- Feature flags for Tier 2/3/Epic 2 (via `.env`)
- Temp folder, export folder paths (via `.env`)
- Log levels and monitoring ports (via `.env`)
- Pricing configuration (via `.env`)

### Error Handling Strategy

| Error Type | Handling |
|------------|----------|
| Invalid image format | User notified to send JPG/PNG |
| OCR API error | User notified, retry requested |
| JSON parsing fails | Error logged, user notified |
| Missing fields | Empty string used, validation remarks added |
| Duplicate invoice | User warned, no append (override available) |
| Sheet auth failure | User notified, check credentials |
| Network issues | Error message, data preserved for retry |

### Security

1. All secrets in `.env` (not committed)
2. Service account for Google Sheets (not personal account)
3. Temporary images deleted after processing
4. Session isolation per user
5. No credentials in code

---

**End of Reference Document**
