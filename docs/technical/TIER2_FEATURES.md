# Tier 2 Features Documentation

## Overview

Tier 2 features enhance the GST Scanner Bot with trust, usability, and auditability improvements. These features add confidence scoring, manual correction workflows, enhanced deduplication, and complete audit trails while keeping the core Tier 1 extraction pipeline intact.

---

## Features

### 1. Confidence Scoring Per Field

**Purpose:** Quantify reliability of extracted data to identify fields needing human review.

**How it works:**
- Each critical field receives a confidence score (0.0 to 1.0)
- Scores calculated based on:
  - Field completeness (populated vs empty)
  - Format validation (GSTIN format, date format, numeric values)
  - Cross-field consistency (state codes match GSTIN)
  - Validation status (fields causing errors get low confidence)

**Critical fields scored:**
- Invoice_No
- Invoice_Date
- Buyer_Name, Buyer_GSTIN
- Seller_Name, Seller_GSTIN
- Total_Taxable_Value
- Total_GST, CGST_Total, SGST_Total, IGST_Total

**Confidence ranges:**
- 0.0: Empty or missing field
- 0.1-0.5: Very low confidence (major issues)
- 0.5-0.7: Low confidence (needs review)
- 0.7-0.9: Medium confidence (acceptable)
- 0.9-1.0: High confidence (reliable)

**Configuration:**
```env
ENABLE_CONFIDENCE_SCORING=true
CONFIDENCE_THRESHOLD_REVIEW=0.7
```

---

### 2. Manual Correction Loop (Telegram)

**Purpose:** Allow users to review and correct low-confidence or error-prone fields before saving.

**Workflow:**

1. **After extraction**, if low-confidence fields or validation errors detected:
   ```
   📄 Invoice Extracted
   
   Invoice Details:
   • Invoice No: INV-2024-001
   • Date: 15/01/2024
   • Buyer: ABC Corp (29ABCDE1234F1Z5)
   
   ⚠️ 2 fields need review:
   1. Buyer_GSTIN (confidence: 0.65)
   2. Total_GST (validation warning)
   
   Actions:
   /confirm - Save as-is
   /correct - Make corrections
   ```

2. **User chooses /correct**:
   ```
   📝 Make Corrections
   
   Reply in format: field_name = new_value
   
   Available fields:
   • invoice_no
   • invoice_date
   • buyer_name
   • buyer_gstin
   • total_taxable_value
   • cgst_total
   • sgst_total
   • igst_total
   
   Example: buyer_gstin = 29AAAAA0000A1Z5
   ```

3. **User makes corrections**:
   ```
   User: buyer_gstin = 29AAAAA0000A1Z5
   
   Bot: ✓ Updated: buyer_gstin = 29AAAAA0000A1Z5
        
        Continue editing or:
        /done - Save with corrections
        /cancel - Discard changes
   ```

4. **User confirms**:
   ```
   User: /done
   
   Bot: ✅ Invoice saved with 1 correction
        Original GSTIN: 29ABCDE1234F1Z5
        Corrected GSTIN: 29AAAAA0000A1Z5
        
        Audit trail recorded.
   ```

**Key principles:**
- No silent corrections - all changes require explicit user input
- Original values preserved in audit trail
- Corrections logged with timestamp and user ID
- Users can always choose `/confirm` to save as-is

**Configuration:**
```env
ENABLE_MANUAL_CORRECTIONS=true
```

---

### 3. Enhanced Invoice Deduplication

**Purpose:** Prevent accidental duplicate invoice uploads using robust fingerprinting.

**How it works:**

**Fingerprint generation:**
- Uses: Seller GSTIN + Invoice Number + Invoice Date
- Normalization ensures different formats recognized as duplicates
- SHA256 hash (16-char) for compact storage

**Example:**
```python
Invoice 1: Seller_GSTIN="24PQRST5678G1Z3", Invoice_No="INV-2024-001", Date="15/01/2024"
Invoice 2: Seller_GSTIN="24 PQRST 5678 G 1Z3", Invoice_No="INV 2024 001", Date="15/01/2024"

Both generate same fingerprint: abc123def456789a
```

**Duplicate detection workflow:**

1. **Bot detects duplicate**:
   ```
   ⚠️ DUPLICATE INVOICE DETECTED
   
   This invoice was already uploaded:
   
   Existing Record:
   • Invoice No: INV-2024-001
   • Date: 15/01/2024
   • Seller: XYZ Ltd (24PQRST5678G1Z3)
   • Uploaded: 20/01/2024 10:30 UTC
   • Uploaded by: User 12345
   
   Current Upload:
   • Invoice No: INV-2024-001
   • Date: 15/01/2024
   • Seller: XYZ Ltd (24PQRST5678G1Z3)
   
   Actions:
   /override - Save anyway (will be marked as duplicate)
   /cancel - Discard this upload
   ```

2. **User can override** if legitimate (amended invoice, correction):
   ```
   User: /override
   
   Bot: ✅ Invoice saved
        ⚠️ Saved as Duplicate Override
   ```

**Storage:**
- `Invoice_Fingerprint`: 16-char hash
- `Duplicate_Status`: UNIQUE | DUPLICATE_OVERRIDE

**Configuration:**
```env
ENABLE_DEDUPLICATION=true
```

---

### 4. Auditability & Traceability

**Purpose:** Complete audit trail for legal accounting compliance and troubleshooting.

**Audit metadata captured:**

| Field | Description | Example |
|-------|-------------|---------|
| `Upload_Timestamp` | When invoice was processed | `2024-01-20T10:30:00Z` |
| `Telegram_User_ID` | Who uploaded it | `12345` |
| `Telegram_Username` | Telegram handle | `@accountant1` |
| `Extraction_Version` | Model/prompt version | `v1.0-tier2` |
| `Model_Version` | AI model used | `gemini-2.5-flash` |
| `Processing_Time_Seconds` | Total processing time | `5.5` |
| `Page_Count` | Number of pages | `2` |
| `Has_Corrections` | Manual corrections applied? | `Y` / `N` |
| `Corrected_Fields` | Which fields corrected | `Buyer_GSTIN, Total_GST` |
| `Correction_Metadata` | Full correction details (JSON) | See below |
| `Invoice_Fingerprint` | Deduplication hash | `abc123def456789a` |
| `Duplicate_Status` | Duplicate status | `UNIQUE` / `DUPLICATE_OVERRIDE` |

**Correction metadata format (JSON):**
```json
{
  "original_values": {
    "Buyer_GSTIN": "29ABCDE1234F1Z5"
  },
  "corrected_values": {
    "Buyer_GSTIN": "29AAAAA0000A1Z5"
  },
  "correction_timestamp": "2024-01-20T10:32:00Z",
  "corrected_by": 12345,
  "correction_reason": "manual_review",
  "correction_count": 1
}
```

**Use cases:**
- **Compliance:** Prove who processed each invoice and when
- **Quality control:** Track correction rates and common errors
- **Troubleshooting:** Identify issues with specific model versions
- **Analytics:** Measure processing times, confidence trends

**Configuration:**
```env
ENABLE_AUDIT_LOGGING=true
EXTRACTION_VERSION=v1.0-tier2
```

---

## Installation & Setup

### Prerequisites
- Tier 1 system already working
- Python 3.8+
- Telegram bot configured
- Google Sheets set up

### Step 1: Update Environment Variables

Add to your `.env` file:

```env
# Tier 2 Features
ENABLE_CONFIDENCE_SCORING=true
ENABLE_MANUAL_CORRECTIONS=true
ENABLE_DEDUPLICATION=true
ENABLE_AUDIT_LOGGING=true
EXTRACTION_VERSION=v1.0-tier2
CONFIDENCE_THRESHOLD_REVIEW=0.7
```

### Step 2: Run Migration Script

Add new columns to your existing Google Sheets:

```bash
python tier2_migration.py
```

This adds 17 new columns to your `Invoice_Header` sheet.

### Step 3: Restart Bot

```bash
python telegram_bot.py
```

You should see:
```
================================================================================
GST SCANNER BOT STARTED (Tier 2 Enabled)
================================================================================
Bot is running and ready to receive invoices...
Temp folder: temp_invoices
Google Sheet: Invoice_Header

Tier 2 Features:
  • Confidence Scoring: ✓
  • Manual Corrections: ✓
  • Deduplication: ✓
  • Audit Logging: ✓
================================================================================
```

---

## Configuration Options

### Feature Toggles

All Tier 2 features can be enabled/disabled independently:

```env
# Disable all Tier 2 features (revert to Tier 1)
ENABLE_CONFIDENCE_SCORING=false
ENABLE_MANUAL_CORRECTIONS=false
ENABLE_DEDUPLICATION=false
ENABLE_AUDIT_LOGGING=false
```

### Confidence Threshold

Controls when review prompts appear:

```env
# Strict: Review needed if any field < 0.8
CONFIDENCE_THRESHOLD_REVIEW=0.8

# Lenient: Review only if field < 0.6
CONFIDENCE_THRESHOLD_REVIEW=0.6

# Default
CONFIDENCE_THRESHOLD_REVIEW=0.7
```

### Extraction Version

Track prompt/model changes:

```env
# Increment when you change extraction prompts
EXTRACTION_VERSION=v1.1-tier2-updated

# For A/B testing
EXTRACTION_VERSION=v1.0-tier2-experimental
```

---

## Testing

### Run Tier 2 Tests

```bash
python test_tier2.py
```

Tests cover:
- Confidence scoring logic
- Correction parsing and application
- Deduplication fingerprinting
- Audit metadata generation
- End-to-end integration

### Manual Testing Workflow

1. **Upload invoice with clear data**
   - Should process automatically (no review needed)
   - Check Google Sheets for audit data

2. **Upload invoice with unclear GSTIN**
   - Should trigger review prompt
   - Test `/correct` flow
   - Test `/confirm` flow

3. **Upload same invoice twice**
   - Should trigger duplicate warning
   - Test `/override` flow

4. **Check Google Sheets**
   - Verify all 17 new columns populated
   - Check correction metadata (if corrections made)
   - Verify fingerprints are unique per invoice

---

## Telegram Commands

### User Commands

| Command | Purpose | When to use |
|---------|---------|-------------|
| `/start` | Show welcome | First interaction |
| `/help` | Show help | Need instructions |
| `/done` | Process invoice | After uploading all pages |
| `/cancel` | Cancel & clear | Start over |
| `/confirm` | Save without corrections | Review prompt shown |
| `/correct` | Start corrections | Review prompt shown |
| `/override` | Save duplicate | Duplicate warning shown |

### Correction Format

```
field_name = new_value
```

Available fields:
- `invoice_no`
- `invoice_date`
- `buyer_name`
- `buyer_gstin`
- `seller_name`
- `seller_gstin`
- `total_taxable_value`
- `cgst_total`
- `sgst_total`
- `igst_total`

---

## Troubleshooting

### Issue: Review prompt not appearing

**Cause:** All fields have high confidence
**Solution:** This is correct behavior - invoice processed automatically

**Cause:** Manual corrections disabled
**Solution:** Set `ENABLE_MANUAL_CORRECTIONS=true` in `.env`

### Issue: Duplicate not detected

**Cause:** Fingerprint column missing
**Solution:** Run `python tier2_migration.py`

**Cause:** Different seller or date
**Solution:** Deduplication requires exact match on Seller GSTIN + Invoice No + Date

### Issue: Audit columns empty for new invoices

**Cause:** Audit logging disabled
**Solution:** Set `ENABLE_AUDIT_LOGGING=true` in `.env`

**Cause:** Using old Tier 1 save method
**Solution:** Ensure bot restarted after enabling Tier 2

### Issue: Corrections not saving

**Cause:** Invalid field name
**Solution:** Use lowercase with underscores (e.g., `buyer_gstin` not `Buyer_GSTIN`)

**Cause:** Invalid format
**Solution:** Use `field_name = value` format (with spaces around `=`)

---

## Best Practices

### For Operators

1. **Always review low-confidence fields** - Don't blindly confirm
2. **Use corrections sparingly** - If many fields wrong, re-scan invoice
3. **Document override reasons** - Note why duplicate is legitimate
4. **Monitor audit logs** - Track which users make most corrections

### For Administrators

1. **Set appropriate confidence threshold** - Balance automation vs accuracy
2. **Track extraction version** - Update when changing prompts
3. **Monitor confidence trends** - Low scores may indicate scanning issues
4. **Review correction patterns** - Identify systematic extraction errors

### For Developers

1. **Test all features after changes** - Run `test_tier2.py`
2. **Increment extraction version** - When modifying prompts
3. **Preserve audit trails** - Never delete correction metadata
4. **Handle errors gracefully** - Keep session on failure for retry

---

## Data Privacy & Security

### User Data Stored

- Telegram User ID (numeric)
- Telegram Username (if available)
- Upload timestamps
- Correction actions

### Compliance Notes

- No personal data beyond Telegram ID
- Audit trails support SOX/GDPR requirements
- All corrections traceable to specific user
- Invoice fingerprints are one-way hashes (not reversible)

### Data Retention

- Historical invoices retain Tier 2 fields empty (legacy data)
- New invoices always populate all Tier 2 fields
- Correction metadata stored indefinitely in Google Sheets

---

## Performance Impact

### Processing Time

Tier 2 adds minimal overhead:

| Feature | Added Time | Notes |
|---------|------------|-------|
| Confidence Scoring | ~0.1s | Heuristic calculations |
| Deduplication | ~0.2s | Fingerprint generation + lookup |
| Audit Logging | ~0.1s | Metadata collection |
| **Total overhead** | **~0.4s** | Per invoice |

### Human-in-the-Loop

Manual corrections add user interaction time (variable):
- Review prompt: 10-30 seconds
- Making corrections: 30-120 seconds per field
- Total: 1-5 minutes if corrections needed

### Google Sheets Performance

- 17 new columns per invoice (minimal impact)
- Correction metadata stored as JSON string (efficient)
- Fingerprint lookups: O(n) but typically <1000 rows

---

## Backward Compatibility

### Disabling Tier 2

To revert to Tier 1:

```env
ENABLE_CONFIDENCE_SCORING=false
ENABLE_MANUAL_CORRECTIONS=false
ENABLE_DEDUPLICATION=false
ENABLE_AUDIT_LOGGING=false
```

Bot will:
- Use Tier 1 save method
- Skip all Tier 2 features
- Leave Tier 2 columns empty

### Mixed Mode

You can enable features selectively:

```env
# Only audit logging and deduplication
ENABLE_CONFIDENCE_SCORING=false
ENABLE_MANUAL_CORRECTIONS=false
ENABLE_DEDUPLICATION=true
ENABLE_AUDIT_LOGGING=true
```

### Historical Data

- Invoices processed before Tier 2 have empty Tier 2 columns
- No migration of historical data (by design)
- New invoices always populate all columns

---

## Support & Feedback

For issues or feature requests:
1. Check troubleshooting section above
2. Run `test_tier2.py` to verify setup
3. Review bot console output for errors
4. Contact your system administrator

---

## Version History

### v1.0-tier2 (Current)
- Initial Tier 2 release
- Confidence scoring for 11 critical fields
- Manual correction workflow
- Fingerprint-based deduplication
- Complete audit trails

### Planned (Tier 3)
- GSTR-1/GSTR-3B export formats
- HSN summary aggregation
- Multi-currency support
- Advanced analytics dashboard
