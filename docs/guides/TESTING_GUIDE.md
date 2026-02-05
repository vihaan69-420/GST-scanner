# Testing Guide - GST Scanner Bot

## 🧪 How to Test Invoice Processing

### Step 1: Start Live Monitoring

**Option A: Using Batch File (Recommended)**
```batch
cd "C:\Users\clawd bot\Documents\GST-scanner\scripts"
watch_logs.bat
```

**Option B: Using PowerShell**
```powershell
Get-Content "C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log" -Wait -Tail 20
```

**Option C: Open Web Dashboard**
```
http://localhost:8080/dashboard
```
Click the "Logs" tab to see live processing

---

### Step 2: Upload Test Invoices

Open Telegram and send invoices to your bot:

1. **Single Invoice Test**
   - Send 1 image
   - Type `/done`
   - Watch the monitor for processing

2. **Multi-Image Invoice Test**
   - Send 2-3 images (pages of same invoice)
   - Type `/done`
   - Bot will combine OCR from all images

3. **Multiple Invoices Test**
   - Upload invoice 1 images → `/done`
   - Upload invoice 2 images → `/done`
   - Upload invoice 3 images → `/done`

---

### Step 3: Verify Processing

**Watch for these log entries:**

✅ **Successful Processing Flow:**
```
[INFO] Invoice INV-XXX - Started processing 2 image(s)
[INFO] Starting OCR for INV-XXX
[INFO] OCR complete for INV-XXX
[INFO] Starting parsing for INV-XXX
[INFO] Parsing complete for INV-XXX
[INFO] Saving to Google Sheets
[INFO] Invoice processing complete for INV-XXX (45.23s)
```

❌ **If Processing Hangs:**
```
[INFO] Starting parsing for INV-XXX
... no more logs for 2+ minutes ...
```
→ Bot is hung, needs restart (as we just fixed)

---

### Step 4: Get Test Summary

After testing, run:

```batch
cd "C:\Users\clawd bot\Documents\GST-scanner\scripts"
get_summary.bat
```

Or manually:
```powershell
cd "C:\Users\clawd bot\Documents\GST-scanner"
powershell -File "scripts\test_summary.ps1"
```

This shows:
- ✅ Total invoices processed
- ✅ Success/failure counts
- ✅ API usage and costs
- ✅ Processing times
- ✅ Recent errors

---

### Step 5: Check Results in Google Sheets

1. Open your configured Google Sheet
2. Look for new rows with your test invoices
3. Verify fields are correctly extracted:
   - Invoice Number
   - Date
   - Seller Name/GSTIN
   - Buyer Name/GSTIN
   - Amounts (Taxable, CGST, SGST, IGST, Total)

---

## 📊 Monitoring Methods Comparison

| Method | Live Updates | Ease of Use | Color Coding | Best For |
|--------|--------------|-------------|--------------|----------|
| **Web Dashboard** | ✅ Yes | ⭐⭐⭐⭐⭐ Easy | ✅ Yes | Real-time monitoring with filtering |
| **watch_logs.bat** | ✅ Yes | ⭐⭐⭐⭐ Easy | ✅ Yes | Quick terminal monitoring |
| **PowerShell Get-Content** | ✅ Yes | ⭐⭐⭐ Medium | ❌ No | Basic log watching |
| **test_summary.ps1** | ❌ Snapshot | ⭐⭐⭐⭐ Easy | ✅ Yes | Getting stats after testing |

---

## 🔍 Quick Status Checks

### Check if Bot is Running
```powershell
Get-Process python
```

### Check if Bot is Responsive
```powershell
Invoke-WebRequest http://localhost:8080/health
```

### See Last 10 Log Lines
```powershell
Get-Content "C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log" -Tail 10
```

### Check When Log Was Last Updated
```powershell
Get-Item "C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log" | Select-Object LastWriteTime
```

### Search for Specific Invoice
```powershell
Select-String -Path "C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log" -Pattern "INV-12345"
```

### Find All Errors Today
```powershell
$today = Get-Date -Format "yyyy-MM-dd"
Select-String -Path "C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log" -Pattern "\[$today.*\[ERROR\]"
```

---

## 🐛 Troubleshooting During Testing

### Bot Not Responding to Uploads
```powershell
# Check log update time
$log = Get-Item "C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log"
$age = (Get-Date) - $log.LastWriteTime
Write-Host "Log last updated: $($age.TotalMinutes) minutes ago"

# If > 2 minutes during processing → Bot is hung
# Restart: Get-Process python | Stop-Process -Force
# Then: cd "C:\Users\clawd bot\Documents\GST-scanner"; python start_bot.py
```

### Dashboard Not Loading
```powershell
# Test health endpoint
Test-NetConnection localhost -Port 8080

# If fails, restart bot
```

### Parsing Takes Too Long
- **Normal**: 20-60 seconds for 2-page invoice
- **Slow**: 1-2 minutes (Gemini API congestion)
- **Hung**: 2+ minutes with no new logs → Restart needed

### Google Sheets Not Updating
Check logs for:
```
[ERROR] Failed to save to Google Sheets
```

Common causes:
- Credentials expired
- Sheet not shared with service account
- Invalid sheet ID

---

## 📈 Expected Performance

| Metric | Typical Value |
|--------|---------------|
| **OCR Time (per image)** | 5-15 seconds |
| **Parsing Time** | 10-30 seconds |
| **Total (1-page invoice)** | 20-45 seconds |
| **Total (2-page invoice)** | 30-60 seconds |
| **API Cost (per invoice)** | $0.0001 - $0.0005 |

---

## ✅ Test Checklist

Use this checklist for comprehensive testing:

- [ ] Bot starts without errors
- [ ] Dashboard accessible at http://localhost:8080/dashboard
- [ ] Single-page invoice processes successfully
- [ ] Multi-page invoice combines OCR correctly
- [ ] Extracted data appears in Google Sheets
- [ ] Multiple invoices process in sequence
- [ ] Bot handles invalid images gracefully
- [ ] Logs show all processing stages
- [ ] Metrics track API usage correctly
- [ ] Bot doesn't hang during parsing
- [ ] Error logs capture failures properly
- [ ] Dashboard shows accurate statistics

---

## 🚀 Next Steps After Testing

1. **Document Results**
   - Note success rate
   - Record any errors
   - Identify improvements needed

2. **Monitor API Costs**
   - Check total cost in dashboard
   - Estimate monthly costs based on volume

3. **Optimize if Needed**
   - Adjust parsing prompts
   - Add retry logic
   - Implement rate limiting

4. **Production Deployment**
   - Set up auto-restart (Windows Task Scheduler)
   - Configure log rotation
   - Set up alerts for errors
