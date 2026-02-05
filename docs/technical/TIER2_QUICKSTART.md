# Tier 2 Quick Start Guide

Get your GST Scanner Bot upgraded to Tier 2 in 5 minutes.

---

## What's New in Tier 2?

✅ **Confidence Scores** - Know which fields are reliable  
✅ **Manual Corrections** - Fix errors before saving  
✅ **Duplicate Detection** - Prevent accidental re-uploads  
✅ **Audit Trails** - Complete traceability for compliance  

---

## Installation (3 Steps)

### Step 1: Update `.env` File

Add these lines to your `.env` file:

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

This adds 17 new columns to your Google Sheets:

```bash
python tier2_migration.py
```

Answer `yes` when prompted.

### Step 3: Restart Bot

```bash
python telegram_bot.py
```

Look for this message:
```
Tier 2 Features:
  • Confidence Scoring: ✓
  • Manual Corrections: ✓
  • Deduplication: ✓
  • Audit Logging: ✓
```

**Done!** Your bot is now Tier 2 enabled.

---

## Quick Test

### Test 1: Normal Invoice (No Review)

1. Send a clear invoice image to bot
2. Type `/done`
3. Bot processes automatically
4. Check Google Sheets - new columns filled

**Expected:** No review prompt (high confidence)

### Test 2: Manual Correction

1. Send an invoice with unclear GSTIN
2. Type `/done`
3. Bot shows review prompt
4. Type `/correct`
5. Reply: `buyer_gstin = 29AAAAA0000A1Z5`
6. Type `/done`

**Expected:** Invoice saved with correction recorded

### Test 3: Duplicate Detection

1. Send same invoice again
2. Type `/done`
3. Bot shows duplicate warning
4. Type `/cancel` or `/override`

**Expected:** Duplicate detected and prevented (or overridden)

---

## New Commands

| Command | When to Use |
|---------|-------------|
| `/confirm` | Save invoice without making corrections |
| `/correct` | Start making corrections |
| `/override` | Save duplicate invoice anyway |

---

## Making Corrections

When bot shows review prompt:

1. Type `/correct`
2. Reply with: `field_name = new_value`
3. Type `/done` when finished

**Example:**
```
User: /correct

Bot: [Shows available fields]

User: buyer_gstin = 29AAAAA0000A1Z5

Bot: ✅ Updated

User: /done

Bot: ✅ Invoice saved with 1 correction
```

**Available fields:**
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

### Bot not asking for review?

**Solution:** Invoice has high confidence (this is good!)  
Or check: `ENABLE_MANUAL_CORRECTIONS=true` in `.env`

### Duplicate not detected?

**Solution:** Run `python tier2_migration.py` to add fingerprint column  
Restart bot after migration

### Corrections not working?

**Solution:** Use correct format: `field_name = value` (lowercase, with spaces)  
Example: ✅ `buyer_gstin = 123` not ❌ `Buyer_GSTIN=123`

### Audit columns empty?

**Solution:** Check `ENABLE_AUDIT_LOGGING=true` in `.env`  
Restart bot after changing `.env`

---

## Configuration Tips

### Adjust Confidence Threshold

```env
# Strict - more review prompts
CONFIDENCE_THRESHOLD_REVIEW=0.8

# Lenient - fewer review prompts
CONFIDENCE_THRESHOLD_REVIEW=0.6

# Balanced (default)
CONFIDENCE_THRESHOLD_REVIEW=0.7
```

### Disable Features Selectively

Don't need manual corrections?

```env
ENABLE_MANUAL_CORRECTIONS=false
```

Want only audit trails?

```env
ENABLE_CONFIDENCE_SCORING=false
ENABLE_MANUAL_CORRECTIONS=false
ENABLE_DEDUPLICATION=true
ENABLE_AUDIT_LOGGING=true
```

### Revert to Tier 1

```env
ENABLE_CONFIDENCE_SCORING=false
ENABLE_MANUAL_CORRECTIONS=false
ENABLE_DEDUPLICATION=false
ENABLE_AUDIT_LOGGING=false
```

---

## What's in Google Sheets?

### New Columns (17 total)

**Audit columns (7):**
- Upload_Timestamp
- Telegram_User_ID
- Telegram_Username
- Extraction_Version
- Model_Version
- Processing_Time_Seconds
- Page_Count

**Correction columns (3):**
- Has_Corrections (Y/N)
- Corrected_Fields (list)
- Correction_Metadata (JSON)

**Deduplication columns (2):**
- Invoice_Fingerprint (hash)
- Duplicate_Status (UNIQUE/DUPLICATE_OVERRIDE)

**Confidence columns (5):**
- Invoice_No_Confidence
- Invoice_Date_Confidence
- Buyer_GSTIN_Confidence
- Total_Taxable_Value_Confidence
- Total_GST_Confidence

---

## Next Steps

✅ Processed your first Tier 2 invoice  
✅ Tested corrections workflow  
✅ Verified duplicate detection  

**Now:**
- Monitor confidence scores in Google Sheets
- Track which fields need most corrections
- Use audit trails for compliance reporting

**Learn more:** See `TIER2_FEATURES.md` for complete documentation

---

## Support

**Run tests:**
```bash
python test_tier2.py
```

**Check bot logs:**  
Look for errors in terminal where bot is running

**Need help?**  
Check `TIER2_FEATURES.md` Troubleshooting section
