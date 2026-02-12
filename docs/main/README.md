# GST Scanner - Telegram Bot for Invoice Processing

Complete end-to-end GST invoice scanner that receives invoice images via Telegram, performs OCR using Google Gemini Vision API, extracts GST-compliant data, and appends to Google Sheets with comprehensive audit trails and export capabilities.

## Features

### 🎯 Tier 1: Core Features
✅ **Telegram Bot Interface**
- Receive invoice images from users
- Support for multi-page invoices
- Interactive menu system with inline buttons
- Simple command-based workflow

✅ **OCR with Google Gemini Vision API**
- Complete text extraction from invoice images
- High accuracy for GST invoices
- Handles various invoice formats
- Multi-page invoice support

✅ **Intelligent GST Data Extraction**
- Extracts 24 GST-compliant fields
- Line item extraction (19 fields per item)
- Validates IGST vs CGST+SGST rules
- Comprehensive validation engine

✅ **Google Sheets Integration**
- Automatic appending to spreadsheet
- Matches your existing schema
- Real-time updates
- Garbage data prevention

### 🔥 Tier 2: Advanced Features
✅ **Confidence Scoring**
- AI-powered confidence scores for extracted fields
- Automatic flagging of low-confidence data
- Review prompts for critical fields

✅ **Manual Corrections**
- User-friendly correction interface
- Field-by-field editing
- Correction history tracking
- Original vs corrected value storage

✅ **Deduplication**
- Fingerprint-based duplicate detection
- Intelligent matching algorithm
- Override capability for legitimate duplicates
- Duplicate attempt logging

✅ **Audit Logging**
- Complete audit trail for every invoice
- User tracking (Telegram ID & username)
- Processing timestamps
- Model version tracking
- Processing time metrics

### 📊 Tier 3: Exports & Reports
✅ **GSTR-1 Export**
- B2B invoices CSV
- B2C Small invoices CSV
- HSN Summary with quantities and values
- Ready for GSTR-1 filing

✅ **GSTR-3B Summary**
- Monthly tax liability summary
- ITC (Input Tax Credit) calculations
- JSON format for easy integration
- Tax payable breakdown

✅ **Operational Reports**
- Processing statistics
- Validation error analysis
- Correction tracking
- User activity reports

✅ **Master Data Auto-Learning**
- Customer Master (auto-populated from invoices)
- HSN Master (auto-populated from line items)
- Usage tracking for both
- Smart defaults for repeat customers/products

✅ **Batch Processing**
- Upload multiple invoices in sequence
- Bulk processing capability
- Progress tracking
- Batch statistics

## Architecture

```
User (Telegram) 
    ↓
Telegram Bot (telegram_bot.py) + Menu System
    ↓
OCR Engine (ocr_engine.py) → Google Gemini 2.5 Flash Vision
    ↓
GST Parser (gst_parser.py) → Google Gemini 2.5 Flash
    ├─→ Line Item Extractor (line_item_extractor.py)
    └─→ GST Validator (gst_validator.py)
    ↓
Tier 2 Components (if enabled)
    ├─→ Confidence Scorer (confidence_scorer.py)
    ├─→ Correction Manager (correction_manager.py)
    ├─→ Deduplication Manager (dedup_manager.py)
    └─→ Audit Logger (audit_logger.py)
    ↓
Sheets Manager (sheets_manager.py) → Google Sheets API
    ├─→ Invoice_Header (41 columns: Tier 1 + Tier 2)
    ├─→ Line_Items (19 columns)
    ├─→ Customer_Master (auto-learning)
    └─→ HSN_Master (auto-learning)
    ↓
Tier 3 Exports (tier3_commands.py)
    ├─→ GSTR-1 Exporter (gstr1_exporter.py)
    ├─→ GSTR-3B Generator (gstr3b_generator.py)
    └─→ Operational Reports (operational_reports.py)
```

## Prerequisites

1. **Python 3.8+**
2. **Telegram Bot Token** - Get from [@BotFather](https://t.me/botfather)
3. **Google Gemini API Key** - Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
4. **Google Sheets API Credentials** - Set up service account

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up Google Sheets API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "Google Sheets API" and "Google Drive API"
4. Create a Service Account:
   - Go to "IAM & Admin" > "Service Accounts"
   - Create new service account
   - Grant "Editor" role
   - Create key (JSON format)
   - Download and save as `credentials.json` in project root
5. Share your Google Sheet with the service account email

### 3. Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow instructions to create bot
4. Copy the bot token

### 4. Configure Environment

1. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```

2. Edit `.env` and fill in your credentials:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   GOOGLE_API_KEY=your_google_gemini_api_key_here
   GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
   GOOGLE_SHEET_ID=your_google_sheet_id_here
   SHEET_NAME=Invoice_Header
   ```

   **To get Google Sheet ID:**
   - Open your Google Sheet
   - Copy the ID from URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`

### 5. Verify Setup

Test individual components:

```bash
# Test configuration
python config.py

# Test OCR engine
python ocr_engine.py

# Test GST parser
python gst_parser.py

# Test Google Sheets connection
python sheets_manager.py
```

### 6. Run the Bot

```bash
python telegram_bot.py
```

You should see:
```
✓ Configuration validated
================================================================================
GST SCANNER BOT STARTED
================================================================================
Bot is running and ready to receive invoices...
Temp folder: temp_invoices
Google Sheet: Invoice_Header
================================================================================
```

## Usage

### For End Users (via Telegram)

1. **Start the bot**
   ```
   /start
   ```

2. **Send invoice images**
   - Send one or more invoice images
   - For multi-page invoices, send all pages sequentially

3. **Process the invoice**
   ```
   /done
   ```
   The bot will:
   - Extract text via OCR
   - Parse GST data
   - Append to Google Sheets
   - Show summary

## Available Commands

### Basic Commands
- `/start` - Welcome message with main menu
- `/menu` - Show main menu anytime
- `/help` - Show detailed help
- `/cancel` - Cancel current operation

### Upload Commands
- `/upload` - Show upload options
- `/done` - Process uploaded invoice(s)
- `/next` - Save current and start next (batch mode)

### Correction Commands (if enabled)
- `/confirm` - Save without corrections
- `/correct` - Enter correction mode
- `/override` - Override duplicate warning

### Export Commands (Tier 3)
- `/export_gstr1` - Generate GSTR-1 exports
- `/export_gstr3b` - Generate GSTR-3B summary
- `/reports` - Generate operational reports
- `/stats` - Quick statistics

### Example Workflow

```
User: [Sends invoice image]
Bot: ✅ Page 1 received! Send more pages or type /done to process.

User: [Sends second page]
Bot: ✅ Page 2 received! Send more pages or type /done to process.

User: /done
Bot: 🔄 Processing 2 page(s)...
     📖 Step 1/3: Extracting text from images...
     🔍 Step 2/3: Parsing GST invoice data...
     📊 Step 3/3: Updating Google Sheet...
     
     ✅ Invoice Processed Successfully!
     
     📄 Invoice Details:
     • Invoice No: 2025/JW/303
     • Date: 28/11/2025
     • Seller: KESARI AUTOMOTIVES
     • Buyer: SAKET MOTORCYCLES
     ...
```

## Extracted Fields

### Tier 1: Invoice Header (24 fields)
1. Invoice_No
2. Invoice_Date
3. Invoice_Type
4. Seller_Name
5. Seller_GSTIN
6. Seller_State_Code
7. Buyer_Name
8. Buyer_GSTIN
9. Buyer_State_Code
10. Ship_To_Name
11. Ship_To_State_Code
12. Place_Of_Supply
13. Supply_Type
14. Reverse_Charge
15. Invoice_Value
16. Total_Taxable_Value
17. Total_GST
18. IGST_Total
19. CGST_Total
20. SGST_Total
21. Eway_Bill_No
22. Transporter
23. Validation_Status
24. Validation_Remarks

### Tier 2: Audit & Metadata (17 fields)
25-31. Processing metadata (timestamp, user, version, time, pages)
32-34. Correction tracking (flags, fields, metadata)
35-36. Deduplication (fingerprint, status)
37-41. Confidence scores (5 key fields)

### Line Items (19 fields per item)
- Invoice_No, Line_No, Item_Code, Description
- HSN, Qty, UOM, Rate
- Discount, Taxable_Value, GST_Rate
- CGST/SGST/IGST rates and amounts
- Cess_Amount, Line_Total

## File Structure

```
saket worksflow/
├── telegram_bot.py          # Main Telegram bot
├── ocr_engine.py            # OCR using Gemini Vision
├── gst_parser.py            # GST data extraction
├── sheets_manager.py        # Google Sheets integration
├── config.py                # Configuration management
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (create this)
├── .env.example            # Example environment file
├── credentials.json        # Google Sheets credentials (add this)
├── README.md               # This file
├── temp_invoices/          # Temporary storage for images
└── Sample Invoices/        # Sample invoice images
```

## Features in Detail

### Multi-Page Invoice Support
- Users can send multiple images for a single invoice
- All pages are processed together as one invoice
- OCR is performed on each page and text is merged
- Page count tracked in audit log

### Line Item Extraction
- Automatically extracts line-level details
- Captures HSN codes, quantities, rates
- Individual item GST breakup
- Validates totals match header

### Duplicate Detection
- Fingerprint-based matching (invoice no + date + buyer + amount)
- Checks if invoice already exists in sheet
- Prevents duplicate entries
- Allows override for legitimate duplicates
- Logs all duplicate attempts

### GST Validation
- Validates GSTIN format (15 characters)
- Checks IGST vs CGST+SGST rules
- Ensures only one type of GST is present
- Validates date formats
- Cross-checks totals
- Adds validation remarks for anomalies

### Confidence Scoring (Tier 2)
- AI-powered confidence analysis
- Scores 5 critical fields (0.0 to 1.0)
- Automatic review flag if < 70%
- Helps identify extraction issues

### Manual Corrections (Tier 2)
- User-friendly field editing
- Tracks original vs corrected values
- Stores correction metadata
- Shows which fields were modified

### Audit Trail (Tier 2)
- Complete processing history
- User identification (Telegram ID & username)
- Timestamps (upload, processing time)
- Model version tracking
- Processing duration
- Page count
- Correction history

### Master Data Auto-Learning (Tier 3)
- **Customer Master**: Automatically populates buyer database
  - GSTIN, legal name, state code
  - Default place of supply
  - Usage count tracking
  
- **HSN Master**: Automatically populates product code database
  - HSN/SAC codes
  - Descriptions
  - Default GST rates
  - UQC (Unit of Quantity Code)
  - Usage count tracking

### Batch Processing (Tier 3)
- Upload multiple invoices in sequence
- Use `/next` to move to next invoice
- Process all at once with `/done`
- Batch statistics report

### GSTR-1 Export (Tier 3)
- **B2B Invoices**: Business-to-business transactions
- **B2C Small**: Invoices under ₹2.5 lakhs
- **HSN Summary**: HSN-wise quantities and values
- CSV format ready for GST portal

### GSTR-3B Export (Tier 3)
- Monthly tax liability summary
- ITC (Input Tax Credit) calculations
- IGST/CGST/SGST breakup
- JSON format for easy processing

### Operational Reports (Tier 3)
1. **Processing Statistics**: Volume, success rate, avg time
2. **Validation Errors**: Common issues, error breakdown
3. **Duplicate Analysis**: Duplicate attempts, patterns
4. **Correction Tracking**: Most corrected fields, accuracy trends
5. **Comprehensive Report**: All above combined

### Error Handling
- Comprehensive error messages
- Session management for retries
- Graceful failure without data loss
- Detailed logging for debugging

## Troubleshooting

### Bot not responding
- Check if bot token is correct in `.env`
- Verify bot is running (`python telegram_bot.py`)
- Check internet connection

### OCR accuracy issues
- Ensure invoice images are clear and well-lit
- Try sending higher resolution images
- Check if text is readable in the image

### Google Sheets not updating
- Verify service account email has edit access to sheet
- Check if sheet ID is correct in `.env`
- Ensure sheet name matches exactly
- Verify `credentials.json` is valid

### Configuration errors
- Run `python config.py` to validate setup
- Check all required fields in `.env`
- Ensure all API keys are active

## Cost Considerations

### Google Gemini API
- **OCR (Vision)**: ~$0.01-0.02 per invoice
- **Parsing (2.5 Flash)**: ~$0.001 per invoice
- **Total per invoice**: ~$0.011-0.021
- **Pricing**: Check [Google AI Pricing](https://ai.google.dev/pricing)
- **Free tier**: 1,500 requests/day for testing

### Google Sheets API
- Free for most use cases
- Rate limits: 300 requests per minute per project

### Telegram Bot API
- Completely free
- No rate limits for most bots

### Monthly Estimates

| Invoices/Month | Estimated Cost |
|----------------|----------------|
| 100            | $1.10 - $2.10  |
| 500            | $5.50 - $10.50 |
| 1,000          | $11.00 - $21.00|
| 5,000          | $55.00 - $105.00|

## Security

⚠️ **Important Security Notes:**

1. **Never commit `.env` file** - Contains sensitive credentials
2. **Keep `credentials.json` private** - Service account credentials
3. **Restrict bot access** - Only share bot link with authorized users
4. **Regularly rotate API keys** - Update keys periodically
5. **Use service account** - Don't use personal Google account

## Limitations

- Maximum 10 images per invoice (configurable via `.env`)
- Supports JPG, JPEG, PNG formats only
- PDF support planned for future release
- OCR accuracy depends on image quality
- Processing time: 10-30 seconds per invoice
- Requires internet connection
- Google API quotas apply

## Configuration Options

All configuration via `.env` file:

### Required Settings
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `GOOGLE_API_KEY` - Google Gemini API key
- `GOOGLE_SHEET_ID` - Your Google Sheet ID
- `GOOGLE_SHEETS_CREDENTIALS_FILE` - Path to credentials.json

### Optional Settings
- `SHEET_NAME` - Invoice header sheet name (default: Invoice_Header)
- `LINE_ITEMS_SHEET_NAME` - Line items sheet name (default: Line_Items)
- `CUSTOMER_MASTER_SHEET` - Customer master sheet (default: Customer_Master)
- `HSN_MASTER_SHEET` - HSN master sheet (default: HSN_Master)
- `MAX_IMAGES_PER_INVOICE` - Max images per invoice (default: 10)
- `TEMP_FOLDER` - Temp folder for images (default: temp_invoices)
- `EXPORT_FOLDER` - Export folder for reports (default: exports)

### Tier 2 Feature Flags
- `ENABLE_CONFIDENCE_SCORING` - Enable/disable confidence scoring (default: true)
- `ENABLE_MANUAL_CORRECTIONS` - Enable/disable corrections (default: true)
- `ENABLE_DEDUPLICATION` - Enable/disable duplicate detection (default: true)
- `ENABLE_AUDIT_LOGGING` - Enable/disable audit logs (default: false)
- `CONFIDENCE_THRESHOLD_REVIEW` - Confidence threshold (default: 0.7)

### Tier 3 Settings
- `EXCLUDE_ERROR_INVOICES` - Exclude error invoices from exports (default: false)

See `.env.example` for complete list and [HARDCODING_ANALYSIS.md](HARDCODING_ANALYSIS.md) for detailed configuration guide.

## Future Enhancements

### Planned Features
- [ ] PDF support for invoice upload
- [ ] Bulk invoice processing (upload ZIP)
- [ ] WhatsApp integration
- [ ] Email invoice forwarding
- [ ] Mobile app (Android/iOS)

### Under Consideration
- [ ] Advanced validation rules (industry-specific)
- [ ] Custom field extraction
- [ ] Analytics dashboard (web interface)
- [ ] Export to multiple formats (Excel, PDF report)
- [ ] Multi-language support
- [ ] Integration with accounting software (Tally, QuickBooks)
- [ ] Machine learning model fine-tuning with user feedback

## Support & Documentation

### Documentation Files
- **[README.md](README.md)** - This file (main documentation)
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed setup instructions
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture & technical details
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Complete project overview
- **[CREDENTIALS_GUIDE.md](CREDENTIALS_GUIDE.md)** - API keys & credentials guide
- **[USER_MANUAL.md](USER_MANUAL.md)** - End user guide
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick reference card
- **[HARDCODING_ANALYSIS.md](HARDCODING_ANALYSIS.md)** - Configuration best practices
- **[TIER1_QUICK_START.md](TIER1_QUICK_START.md)** - Tier 1 features guide
- **[TIER2_FEATURES.md](TIER2_FEATURES.md)** - Tier 2 features guide
- **[TIER3_README.md](TIER3_README.md)** - Tier 3 features guide

### Tier-Specific Documentation
- **TIER1**: Basic invoice processing (24 fields + line items + validation)
- **TIER2**: Advanced features (corrections, confidence, deduplication, audit)
- **TIER3**: Exports & reports (GSTR-1, GSTR-3B, operational reports, batch)

For issues or questions:
1. Check troubleshooting section above
2. Review error messages in console
3. Run `python test_system.py` for diagnostics
4. Check relevant documentation file
5. Contact your system administrator

## License

Internal use only - Saket Workflow

---

**Version**: 1.0.0 (Tier 3 Complete)  
**Includes**: Tier 1 (Basic) + Tier 2 (Audit) + Tier 3 (Exports)  
**Last Updated:** February 2026  
**Author:** GST Scanner Team

---

## Quick Links

- 🚀 [Get Started](SETUP_GUIDE.md)
- 📖 [User Manual](USER_MANUAL.md)
- 🏗️ [Architecture](ARCHITECTURE.md)
- 🔧 [Configuration](HARDCODING_ANALYSIS.md)
- 📊 [Project Summary](PROJECT_SUMMARY.md)
