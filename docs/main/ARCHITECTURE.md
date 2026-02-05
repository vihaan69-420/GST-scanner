# GST Scanner - Architecture & Workflow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USER (Telegram)                            │
│                                                                       │
│  Actions:                                                            │
│  • Sends invoice images (single or multiple pages)                  │
│  • Types /done to process                                           │
│  • Receives extracted data summary                                  │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TELEGRAM BOT (telegram_bot.py)                  │
│                                                                       │
│  Responsibilities:                                                   │
│  • Receive and validate images                                      │
│  • Manage user sessions                                             │
│  • Coordinate workflow between components                           │
│  • Send status updates and results                                  │
│  • Handle errors gracefully                                         │
└───┬───────────────┬───────────────┬───────────────┬─────────────────┘
    │               │               │               │
    │               │               │               │
    ▼               ▼               ▼               ▼
┌────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│CONFIG  │    │  OCR     │    │   GST    │    │ SHEETS   │
│.py     │    │ ENGINE   │    │  PARSER  │    │ MANAGER  │
│        │    │  .py     │    │   .py    │    │  .py     │
└────────┘    └─────┬────┘    └─────┬────┘    └─────┬────┘
                    │               │               │
                    ▼               ▼               ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐
              │ Google   │    │ Google   │    │ Google   │
              │ Gemini   │    │ Gemini   │    │ Sheets   │
              │ Vision   │    │ 1.5 Flash│    │   API    │
              │   API    │    │          │    │          │
              └──────────┘    └──────────┘    └──────────┘
```

---

## Data Flow

### Phase 1: Image Collection

```
User                    Telegram Bot
 │                           │
 │─── Send Image 1 ────────→ │
 │                           │ ✓ Validate format
 │                           │ ✓ Save to temp folder
 │                           │ ✓ Add to user session
 │←─ "Page 1 received" ───── │
 │                           │
 │─── Send Image 2 ────────→ │
 │                           │ ✓ Validate format
 │                           │ ✓ Save to temp folder
 │                           │ ✓ Add to user session
 │←─ "Page 2 received" ───── │
 │                           │
 │─────── /done ───────────→ │
 │                           │
 │                           ▼
 │                    Start Processing
```

### Phase 2: OCR Processing

```
Telegram Bot              OCR Engine              Gemini Vision API
     │                         │                         │
     │─── Process Images ─────→│                         │
     │                         │                         │
     │                         │─── Image 1 + Prompt ───→│
     │                         │                         │
     │                         │←─── Extracted Text ─────│
     │                         │                         │
     │                         │─── Image 2 + Prompt ───→│
     │                         │                         │
     │                         │←─── Extracted Text ─────│
     │                         │                         │
     │                         │ Merge all text          │
     │                         │                         │
     │←─ Combined OCR Text ────│                         │
     │                         │                         │
```

### Phase 3: GST Data Extraction

```
Telegram Bot              GST Parser              Gemini 1.5 Flash
     │                         │                         │
     │─── Parse OCR Text ─────→│                         │
     │                         │                         │
     │                         │─ OCR Text + Extraction ─→│
     │                         │   Prompt                │
     │                         │                         │
     │                         │←── Structured JSON ─────│
     │                         │                         │
     │                         │ Validate & Clean        │
     │                         │                         │
     │←─ Validated Invoice ────│                         │
     │    Data (24 fields)     │                         │
```

### Phase 4: Google Sheets Update

```
Telegram Bot           Sheets Manager         Google Sheets API
     │                       │                        │
     │─── Append Data ──────→│                        │
     │                       │                        │
     │                       │ Check for duplicate    │
     │                       │                        │
     │                       │──── Get existing ─────→│
     │                       │     invoice numbers    │
     │                       │                        │
     │                       │←─── Invoice list ──────│
     │                       │                        │
     │                       │ ✓ Not duplicate        │
     │                       │                        │
     │                       │─── Append new row ────→│
     │                       │                        │
     │                       │←───── Success ─────────│
     │                       │                        │
     │←──── Success ─────────│                        │
     │                       │                        │
     │                       │                        │
     ▼                       │                        │
Send Summary                 │                        │
to User                      │                        │
```

---

## Component Details

### 1. Configuration (config.py)
- Loads environment variables from `.env`
- Validates all required credentials
- Defines Google Sheets column schema
- Provides constants for the application

### 2. OCR Engine (ocr_engine.py)
- Uses Google Gemini Vision API
- Processes single or multiple images
- Extracts ALL text from invoices
- Preserves layout structure
- No summarization or calculation

### 3. GST Parser (gst_parser.py)
- Uses Google Gemini 2.5 Flash for intelligence
- Extracts GST-compliant fields (24 Tier 1 fields + 17 Tier 2 audit fields)
- Validates IGST vs CGST+SGST rules
- Includes line item extraction
- Performs GST validation
- Cleans and formats data
- Returns structured JSON

### 4. Sheets Manager (sheets_manager.py)
- Authenticates via service account
- Connects to specified Google Sheet
- Manages multiple sheets (Invoice_Header, Line_Items, Customer_Master, HSN_Master)
- Checks for duplicate invoices (fingerprint-based)
- Appends data in correct column order with strict validation
- Updates master data automatically
- Validates sheet structure
- Includes garbage data prevention

### 5. Telegram Bot (telegram_bot.py)
- Handles user interactions with menu system
- Manages image collection (single and batch mode)
- Orchestrates the workflow
- Provides status updates
- Handles errors gracefully
- Supports Tier 2 features (corrections, confidence scoring, deduplication)
- Supports Tier 3 features (GSTR-1/3B exports, reports, batch processing)

---

## Google Sheets Schema

### Invoice_Header Sheet (41 columns)

#### Tier 1 Fields (24 columns A-X)
| # | Column Name | Description |
|---|-------------|-------------|
| 1-24 | Tier 1 Fields | Invoice_No, Invoice_Date, Invoice_Type, Seller details, Buyer details, GST amounts, Validation status |

#### Tier 2 Audit Fields (7 columns Y-AE)
| # | Column Name | Description |
|---|-------------|-------------|
| 25 | Upload_Timestamp | When invoice was processed |
| 26 | Telegram_User_ID | User who uploaded |
| 27 | Telegram_Username | Username |
| 28 | Extraction_Version | Version of extraction logic |
| 29 | Model_Version | AI model used |
| 30 | Processing_Time_Seconds | Time taken |
| 31 | Page_Count | Number of pages |

#### Tier 2 Correction Fields (3 columns AF-AH)
| # | Column Name | Description |
|---|-------------|-------------|
| 32 | Has_Corrections | Y/N flag |
| 33 | Corrected_Fields | List of corrected fields |
| 34 | Correction_Metadata | JSON metadata |

#### Tier 2 Deduplication Fields (2 columns AI-AJ)
| # | Column Name | Description |
|---|-------------|-------------|
| 35 | Invoice_Fingerprint | Unique hash |
| 36 | Duplicate_Status | UNIQUE or DUPLICATE_OVERRIDE |

#### Tier 2 Confidence Fields (5 columns AK-AO)
| # | Column Name | Description |
|---|-------------|-------------|
| 37-41 | Confidence Scores | For key fields (0.0-1.0) |

### Line_Items Sheet (19 columns A-S)
Contains item-level details for each invoice with HSN codes, quantities, rates, and GST breakup.

### Customer_Master Sheet (Tier 3)
Auto-learning customer database with GSTIN, legal names, and usage tracking.

### HSN_Master Sheet (Tier 3)
Auto-learning HSN/SAC code database with descriptions, GST rates, and usage tracking.

### Duplicate_Attempts Sheet (Tier 3)
Logs all duplicate invoice attempts for audit trail.

---

## Error Handling

### Image Issues
- Invalid format → User notified to send JPG/PNG
- Too many images → User notified of limit
- Download fails → Retry requested

### OCR Failures
- API error → User notified with error details
- Partial page failure → Marked in combined text
- Network issues → Error message with retry option

### Parsing Errors
- JSON parsing fails → Error logged, user notified
- Missing fields → Empty string used
- Validation fails → Remarks added to data

### Sheets Errors
- Authentication fails → User notified, check credentials
- Duplicate invoice → User warned, no append
- Network issues → Error message, data preserved

---

## Security Features

1. **Credential Protection**
   - All secrets in `.env` (not committed)
   - Service account for Google Sheets
   - No credentials in code

2. **Data Privacy**
   - Temporary images deleted after processing
   - No data logging of invoice content
   - Session isolation per user

3. **Access Control**
   - Only authorized users can access bot
   - Google Sheet access via service account only
   - API keys restricted to necessary scopes

---

## Performance

### Processing Time
- Single page invoice: 10-15 seconds
- Multi-page invoice: 15-30 seconds
- Mostly dependent on API response times

### Resource Usage
- Minimal memory footprint
- Temporary storage cleaned automatically
- Can handle multiple concurrent users

### API Costs
- **Gemini Vision (OCR)**: ~$0.01-0.02 per invoice
- **Gemini 1.5 Flash (Parsing)**: ~$0.001 per invoice
- **Google Sheets API**: Free
- **Telegram Bot API**: Free

---

## Workflow Summary

```
START
  │
  ├─→ User sends invoice image(s)
  │
  ├─→ Bot validates and stores images
  │
  ├─→ User types /done
  │
  ├─→ Bot extracts text via OCR (Gemini Vision)
  │
  ├─→ Bot parses GST data (Gemini 1.5 Flash)
  │
  ├─→ Bot checks for duplicates
  │
  ├─→ Bot appends to Google Sheets
  │
  ├─→ Bot sends success summary to user
  │
  └─→ User receives confirmation
       │
      END
```

---

**Version:** 1.0.0 (Tier 3 Complete)  
**Includes:** Tier 1 (Basic), Tier 2 (Audit), Tier 3 (Exports & Reports)  
**Last Updated:** February 2026

---

## Additional Documentation

- **[HARDCODING_ANALYSIS.md](HARDCODING_ANALYSIS.md)** - Complete analysis of all hardcoded values
- **[README.md](README.md)** - Main documentation
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Setup instructions
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Complete project overview
