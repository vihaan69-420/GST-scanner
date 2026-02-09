# Phase 7: Telegram Dev Flow - Order Upload Integration

## Overview

Phase 7 integrates the complete order upload pipeline (Phases 3-6) into the development Telegram bot, providing a user-friendly workflow for processing handwritten order images.

## Components Added

### 1. Order Upload Orchestrator (`src/order_upload_orchestrator.py`)

**Purpose**: Coordinates the full order upload workflow from images to Google Sheets.

**Workflow**:
1. **OCR**: Extract text from images using Gemini Vision
2. **Parse**: Convert to structured order lines (S.N, PART NAME, QTY)
3. **Dedupe**: Remove duplicate entries based on rules
4. **Match**: Find prices from the local .xlsx price list
5. **Write**: Append results to Google Sheets (4 sheets: Raw_OCR, Normalized_Lines, Matched_Lines, Errors)

**Key Method**:
```python
def process_order_images(image_paths: List[str], order_id: Optional[str]) -> Dict:
    """
    Returns:
        {
            "success": bool,
            "summary": str,  # User-friendly message
            "stats": {       # Counts and metrics
                "total_extracted": int,
                "kept": int,
                "duplicates_skipped": int,
                "matched": int,
                "unmatched": int
            },
            "sheet_url": str,  # Link to Google Sheet
            "errors": List[str]
        }
    ```

### 2. Enhanced Dev Bot (`src/bot/dev_telegram_bot.py`)

**New Commands**:
- `/order_upload` - Start a new order upload session
- `/done_order` - Process collected images through the pipeline
- `/cancel_order` - Cancel current session and cleanup

**Session Management**:
```python
user_sessions[user_id] = {
    "images": [path1, path2, ...],  # Collected image paths
    "order_id": "order_12345_67890"  # Unique identifier
}
```

**Workflow**:
1. User: `/order_upload` → Bot creates session
2. User: Sends images → Bot downloads and collects
3. User: `/done_order` → Bot processes through orchestrator
4. Bot: Returns summary + Sheet link + warnings

### 3. Configuration

**Required Environment Variables**:
```bash
# Enable order upload feature
ENABLE_ORDER_UPLOAD=true

# Dev bot token
TELEGRAM_DEV_BOT_TOKEN=your_dev_bot_token

# Google Sheets for results
ORDER_UPLOAD_SHEET_ID=your_sheet_id

# Local price list (optional, defaults to ORDER_UPLOAD_SHEET_ID)
LOCAL_PRICE_LIST_PATH=C:\path\to\price_list.xlsx

# Temp folder for downloaded images
TEMP_FOLDER=temp

# Required for OCR (Gemini Vision API)
GOOGLE_API_KEY=your_gemini_api_key
```

## User Experience Flow

### Happy Path

```
User: /order_upload
Bot:  [DEV BOT] Order upload session started!
      Send me images of handwritten order lists.
      When done, use /done_order to process them.

User: [sends image 1]
Bot:  [DEV BOT] Image 1 received!
      Send more images or use /done_order to process.

User: [sends image 2]
Bot:  [DEV BOT] Image 2 received!
      Send more images or use /done_order to process.

User: /done_order
Bot:  [DEV BOT] Processing 2 image(s)...
      This may take a moment.

Bot:  [DEV BOT] Order processing complete!
      
      Extracted: 45 lines
      Kept: 42 (skipped 3 duplicates)
      Matched: 38 items with prices
      Unmatched: 4 items (no price found)
      
      View results: https://docs.google.com/spreadsheets/d/...
```

### Error Handling

**No API Key**:
```
Bot: [DEV BOT] Failed to extract text from images. 
     Please check API key configuration.
```

**No Active Session**:
```
User: [sends image]
Bot:  [DEV BOT] Image received, but no active order session.
      Use /order_upload to start a session first.
```

**No Images Collected**:
```
User: /done_order
Bot:  [DEV BOT] No images collected. 
      Use /order_upload to start a session first.
```

## Google Sheets Output

The orchestrator writes to 4 separate sheets:

### 1. Raw_OCR
- Page_No
- Raw_Text (extracted by Gemini Vision)
- Image_Path
- Order_ID
- Timestamp

### 2. Normalized_Lines
- S.N
- PART_NAME
- QTY (from circled numbers only)
- Source_Page
- Order_ID
- Timestamp

### 3. Matched_Lines
- S.N
- PART_NAME
- PART_NUMBER (from price list)
- PRICE (from price list)
- QTY
- LINE_TOTAL (calculated)
- Match_Type (EXACT_PN, EXACT_NAME, FUZZY, UNMATCHED)
- Order_ID
- Timestamp

### 4. Errors
- S.N
- PART_NAME
- Error_Type (DUPLICATE, UNMATCHED)
- Error_Details
- Order_ID
- Timestamp

## Testing

### Unit Tests (`tests/test_dev_bot_integration.py`)

✅ Dev bot initializes with order upload enabled
✅ Session management structure works correctly

### Integration Testing (Manual)

**Prerequisites**:
1. Set `BOT_ENV=dev` in `.env`
2. Set `ENABLE_ORDER_UPLOAD=true`
3. Configure `TELEGRAM_DEV_BOT_TOKEN`
4. Configure `GOOGLE_API_KEY`
5. Set up Google Sheets credentials

**Test Steps**:
1. Run dev bot: `python start_dev_bot.py`
2. In Telegram, start conversation with dev bot
3. Send `/order_upload`
4. Upload handwritten order images
5. Send `/done_order`
6. Verify results in Google Sheets

## Guardrails

### Environment Isolation
- ✅ Only runs when `BOT_ENV=dev`
- ✅ Uses separate `TELEGRAM_DEV_BOT_TOKEN`
- ✅ Writes to separate sheet (`ORDER_UPLOAD_SHEET_ID`)
- ✅ Never touches production bot or data

### Feature Flag
- ✅ Only active when `ENABLE_ORDER_UPLOAD=true`
- ✅ Gracefully degrades if disabled
- ✅ Shows clear error messages

### Data Safety
- ✅ Idempotent writes (checks for existing keys)
- ✅ Error logging (nothing silently fails)
- ✅ Session cleanup on cancel/completion
- ✅ Temp file cleanup

## Rollback

To disable Order Upload:

1. Set `ENABLE_ORDER_UPLOAD=false` in `.env`
2. Restart dev bot
3. Commands `/order_upload`, `/done_order`, `/cancel_order` will not be registered
4. Existing order data remains in Google Sheets (read-only)

## Known Limitations

1. **No PDF support yet** - Only image files (.jpg, .png)
2. **Requires GOOGLE_API_KEY** - Gemini Vision API must be configured
3. **Sequential processing** - Images processed one at a time (not parallelized)
4. **No progress updates** - User waits until complete (could add progress bar)
5. **Basic error messages** - Could be more user-friendly

## Next Steps (Phase 8: Testing & Assertions)

- [ ] Golden image parsing test with actual sample
- [ ] End-to-end test with mocked Gemini API
- [ ] Performance test with multiple images
- [ ] Verify S.N 3 quantity extraction (golden fixture)
- [ ] Schema validation tests
