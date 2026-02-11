# Testing Guide: Usage Tracking (Phases 2-3)

**Date:** February 6, 2026  
**Status:** Bot Running with Tracking ENABLED

---

## ✅ Bot Status

- **Running:** Yes (PID: 23156)
- **Tracking Enabled:** Yes
- **Logs Directory:** Ready (`logs/` folder exists)

---

## 📋 Test Procedure

### Step 1: Send Test Invoice to Bot

1. Open your Telegram app
2. Go to the GST Scanner Bot
3. Send `/start` to wake up the bot
4. Send an invoice image (JPG/PNG)
5. Type `/done` to process

### Step 2: Watch for User Response

**Expected behavior:**
- Bot should reply: "✅ Invoice saved successfully!" 
- Response time should be **normal** (no delay)
- You should NOT notice any difference from before

### Step 3: Check Background Tracking (After User Response)

**Look for in bot console/logs:**
- Message: `[BACKGROUND] Usage tracked for invoice INV-XXXXX`
- This should appear 1-2 seconds AFTER user sees success

### Step 4: Verify Files Created

Check if these files were created in `logs/` folder:
- [ ] `logs/ocr_calls.jsonl` - OCR call records
- [ ] `logs/invoice_usage.jsonl` - Invoice usage records
- [ ] `logs/customer_usage_summary.json` - Customer summary

---

## 🔍 What to Verify

### ✅ User Experience (Critical)
- [ ] User sees success message at normal speed
- [ ] No errors shown to user
- [ ] Processing time feels the same as before

### ✅ Background Tracking
- [ ] Console shows: `[BACKGROUND] Usage tracked...`
- [ ] Appears AFTER user sees success
- [ ] No errors in background tracking

### ✅ Data Files
- [ ] OCR calls file contains per-page data
- [ ] Invoice usage file contains aggregated data
- [ ] Customer summary shows totals

---

## 📊 Sample Expected Output

### Console Output (Expected)
```
Processing page 1/1: invoice.jpg
[2026-02-06 11:22:30] User receives: ✅ Invoice saved successfully!
[BACKGROUND] Usage tracked for invoice INV-2024-12345
```

### logs/ocr_calls.jsonl (Sample Line)
```json
{"call_id": "ocr_20260206_112230_001", "invoice_id": "INV-2024-12345", "page_number": 1, "prompt_tokens": 1245, "output_tokens": 856, "total_tokens": 2101, "image_size_bytes": 85000, "customer_id": "CUST001"}
```

### logs/invoice_usage.jsonl (Sample Line)
```json
{"invoice_id": "INV-2024-12345", "customer_id": "CUST001", "page_count": 1, "total_tokens": 3751, "total_cost_usd": 0.000702, "validation_status": "ok"}
```

### logs/customer_usage_summary.json (Sample)
```json
{
  "customer_id": "CUST001",
  "total_invoices": 1,
  "total_cost_usd": 0.000702,
  "avg_cost_per_invoice": 0.000702
}
```

---

## ❌ Troubleshooting

### If user sees errors:
- **STOP IMMEDIATELY**
- Disable tracking: Set `ENABLE_USAGE_TRACKING=false` in `.env`
- Restart bot
- Report the error

### If no files created:
- Check console for `[BACKGROUND]` messages
- Check for errors in logs
- Verify flags are enabled in `.env`

### If tracking seems slow:
- Verify message appears AFTER user success
- Should not delay user response
- Background can take 1-2 seconds (that's OK)

---

## ✅ Success Criteria

**TEST PASSES IF:**
1. ✅ User sees success at normal speed
2. ✅ Console shows `[BACKGROUND] Usage tracked...`
3. ✅ Files created in `logs/` folder
4. ✅ No errors in console
5. ✅ JSON files contain valid data

**TEST FAILS IF:**
- ❌ User experiences delay
- ❌ User sees tracking errors
- ❌ Bot crashes or hangs
- ❌ Files not created

---

## 📞 After Testing

**If test passes:**
- Keep tracking enabled for more testing
- Process a few more invoices
- Verify customer summary updates correctly

**If test fails:**
- Disable tracking immediately
- Save error logs
- Report issue for debugging

---

## 🚀 Current Status

- Bot: **RUNNING** ✅
- Tracking: **ENABLED** ✅
- Ready for: **USER TO TEST** ⏳

**Next:** Send a test invoice to the bot via Telegram!

---

**Bot Console:** Running in background (PID: 23156)  
**Logs:** `c:\Users\clawd bot\Documents\GST-scanner\logs\`
