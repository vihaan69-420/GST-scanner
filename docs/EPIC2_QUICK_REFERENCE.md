# Epic 2 Quick Reference Guide

## 🚀 Quick Start

### Enable the Feature

1. **Install Dependencies:**
   ```bash
   pip install openpyxl>=3.1.0 reportlab>=4.0.0
   ```

2. **Set Feature Flag:**
   Edit `.env`:
   ```
   FEATURE_ORDER_UPLOAD_NORMALIZATION=true
   ```

3. **Add Pricing Sheet:**
   Place Excel file at:
   ```
   Epic2 artifacts/UPDATED PRICE LIST FOR SAI-ABS 10 MAY-25.xls
   ```

4. **Restart Bot:**
   ```bash
   ./scripts/start_bot.bat
   ```

---

## 📱 User Flow

1. User sends `/start` to bot
2. User clicks **📦 Upload Order** button
3. User sends 1 or more photos of handwritten order notes
4. User types `/order_submit`
5. Bot processes:
   - Extracts line items via OCR + LLM
   - Normalizes part names, colors, models
   - Deduplicates across pages
   - Matches with pricing sheet
   - Generates clean PDF
   - Uploads to Google Sheets
6. User receives PDF via Telegram

---

## 🎯 Key Features

### Extraction
- **OCR:** Reuses existing `OCREngine`
- **LLM:** Gemini-2.5-flash for structured extraction
- **Format:** Handles handwritten serial number, part name, model, color, quantity

### Normalization
- **Brand Extraction:** Removes "Sai -" prefix
- **Color Mapping:** BL→Black, PA→Black, S→Silver, etc.
- **Part Names:** Standardized formatting

### Deduplication
- **Signature:** part_name + model + color + quantity
- **Strategy:** Mark duplicates, don't delete
- **Traceability:** Links to original line

### Pricing Match
- **Method:** Fuzzy name matching (SequenceMatcher)
- **Threshold:** 70% similarity
- **Source:** Excel file (configurable for Google Sheets)
- **Unmatched:** Flagged with price = 0

### PDF Generation
- **Format:** A4, professional styling
- **Content:** Clean data only (no OCR artifacts)
- **Features:** Tables, subtotals, unmatched warnings

### Google Sheets
- **New Tabs:** Orders, Order_Line_Items, Customer_Details
- **Existing Tabs:** Untouched (Invoice_Header, Line_Items)
- **Operations:** Batch writes for efficiency

---

## 🔧 Configuration

### Environment Variables

```bash
# Master feature flag (default: false)
FEATURE_ORDER_UPLOAD_NORMALIZATION=false

# Pricing sheet source (local_file or google_sheet)
PRICING_SHEET_SOURCE=local_file

# Path to pricing Excel file
PRICING_SHEET_PATH=Epic2 artifacts/UPDATED PRICE LIST FOR SAI-ABS 10 MAY-25.xls

# Future: Google Sheet ID for pricing
PRICING_SHEET_ID=

# Tab name for pricing in Google Sheets (future)
PRICING_SHEET_NAME=Pricing_Master

# Order-related Google Sheets tabs
ORDER_SUMMARY_SHEET=Orders
ORDER_LINE_ITEMS_SHEET=Order_Line_Items
ORDER_CUSTOMER_DETAILS_SHEET=Customer_Details

# Max images per order (default: 10)
MAX_IMAGES_PER_ORDER=10
```

---

## 🧪 Testing

### Run Isolation Tests
```bash
python tests/test_epic2_isolation.py
```

Expected: 5 tests pass, 0 fail

### Manual Testing

**With Feature OFF:**
```bash
# Set FEATURE_ORDER_UPLOAD_NORMALIZATION=false
# Start bot
# Send /start
# Should NOT see "📦 Upload Order" button
# GST scanner works normally
```

**With Feature ON:**
```bash
# Set FEATURE_ORDER_UPLOAD_NORMALIZATION=true
# Install dependencies
# Start bot
# Send /start
# Should see "📦 Upload Order" button
# Test order upload flow
```

---

## 🔄 Rollback

### Immediate Rollback
```bash
# 1. Set feature flag to false
FEATURE_ORDER_UPLOAD_NORMALIZATION=false

# 2. Restart bot
./scripts/start_bot.bat

# 3. Verify - no order button visible
```

**Time:** < 1 minute  
**Impact:** Zero downtime for GST scanning

See: `docs/EPIC2_ROLLBACK.md` for complete guide

---

## 📊 Google Sheets Structure

### Orders Tab
```
Order_ID | Customer_Name | Order_Date | Status | Total_Items | 
Total_Quantity | Subtotal | Unmatched_Count | Page_Count | 
Created_By | Processed_At
```

### Order_Line_Items Tab
```
Order_ID | Serial_No | Part_Name | Part_Number | Model | 
Color | Quantity | Rate | Line_Total | Match_Confidence
```

### Customer_Details Tab
```
Customer_ID | Customer_Name | Contact | Last_Order_Date | Total_Orders
```

---

## 📝 Commands

| Command | Description |
|---------|-------------|
| `/start` | Show main menu (with order button if enabled) |
| `/order_submit` | Process uploaded order pages |
| `/cancel` | Cancel current operation |

---

## 🏗️ Architecture

```
User → Telegram
  ↓
GSTScannerBot (feature flag check)
  ↓
OrderSession (tracks pages)
  ↓
OrderNormalizationOrchestrator
  ├─ OrderExtractor (OCR + LLM)
  ├─ OrderNormalizer (field cleanup)
  ├─ OrderDeduplicator (cross-page)
  ├─ PricingMatcher (fuzzy match)
  ├─ OrderPDFGenerator (reportlab)
  └─ OrderSheetsHandler (Google Sheets)
  ↓
User receives PDF
```

---

## 🛡️ Guardrails

✅ **Isolation:**
- All code in `src/order_normalization/`
- Zero imports from order module to GST scanner
- Separate order_sessions from invoice sessions

✅ **Feature Flag:**
- Checked at 3 levels: menu, callback, processing
- Default: OFF (safe for deployment)

✅ **Data Safety:**
- Existing sheets untouched
- New tabs additive only
- Raw data preserved alongside normalized

✅ **Error Handling:**
- Extraction failure → stop and notify
- Pricing failure → continue with review_required
- PDF failure → sheet write still succeeds
- Sheet failure → user still gets PDF

---

## 📁 File Locations

### Configuration
- `src/config.py` - Lines ~327-345

### Module
- `src/order_normalization/` - All Epic 2 code

### Bot Integration
- `src/bot/telegram_bot.py` - Feature-flagged changes

### Tests
- `tests/test_epic2_isolation.py`

### Documentation
- `docs/EPIC2_ROLLBACK.md`
- `EPIC2_IMPLEMENTATION_COMPLETE.md`

---

## 🐛 Troubleshooting

### "Order upload feature is not enabled"
- Check: `FEATURE_ORDER_UPLOAD_NORMALIZATION=true` in `.env`
- Restart bot

### "No pricing data loaded"
- Check: Excel file exists at `PRICING_SHEET_PATH`
- Check: `openpyxl` installed

### "PDF generation failed"
- Check: `reportlab` installed
- Check: `orders/` folder writable

### Import errors
- Check: All dependencies installed
- Run: `pip install -r requirements.txt`

### Tests fail
- Ensure in project root
- Check: `src/` folder in Python path
- Run: `python tests/test_epic2_isolation.py`

---

## 📞 Support

**Documentation:**
- Implementation: `EPIC2_IMPLEMENTATION_COMPLETE.md`
- Rollback: `docs/EPIC2_ROLLBACK.md`
- Plan: `.cursor/plans/order_upload_epic_2_*.plan.md`

**Tests:**
- Isolation: `python tests/test_epic2_isolation.py`

**Logs:**
- Check console output for `[ORDER*]` prefixed messages
- Error tracking in orchestrator with try-catch blocks

---

**Version:** 1.0  
**Date:** 2026-02-06  
**Status:** ✅ Implementation Complete
