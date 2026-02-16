# GST Scanner - Professional Invoice Processing Bot

**Version:** 2.0  
**Status:** Production-Ready

Complete end-to-end GST invoice scanner that receives invoice images via Telegram, performs OCR using Google Gemini Vision API, extracts GST-compliant data, and appends to Google Sheets with comprehensive audit trails and export capabilities.

## Quick Start

1. **Copy credentials:**
   ```powershell
   copy .env.example .env
   ```

2. **Edit `.env`** with your Telegram bot token, Gemini API key, Google Sheet ID, and credentials path.

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Start the bot:**
   ```powershell
   python start_bot.py
   ```

## Features

- **Tier 1:** Telegram bot, OCR via Gemini Vision, 24-field GST extraction, line items, validation, Google Sheets integration
- **Tier 2:** Confidence scoring, manual corrections, deduplication, audit logging
- **Tier 3:** GSTR-1/3B exports, operational reports, master data auto-learning, batch processing
- **Epic 2:** Handwritten order upload with pricing match and PDF generation (feature-flagged)

## Documentation

See **[docs/REFERENCE.md](docs/REFERENCE.md)** for complete documentation including setup guide, architecture, user manual, feature details, troubleshooting, and technical reference.

## System Requirements

- Python 3.8+
- Telegram Bot API access
- Google Gemini API access
- Google Sheets API access

## License

Internal use only - Saket Workflow
