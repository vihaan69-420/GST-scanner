# Dashboard Quick Reference Guide

## Accessing the Dashboard

**URL:** http://localhost:8080/dashboard

## Starting Required Services

### 1. Start the Bot
```powershell
python run_bot.py
```

### 2. Start the Health Server (for Dashboard)
```powershell
python -c "import sys; sys.path.insert(0, 'src'); from utils.health_server import HealthServer; from utils.metrics_tracker import get_metrics_tracker; from utils.logger import get_logger; tracker = get_metrics_tracker(); logger = get_logger(); server = HealthServer(port=8080, metrics_tracker=tracker, logger=logger); server.start(); import time; time.sleep(999999)"
```

**Note:** Keep both terminals running in the background.

## Dashboard Features

### 💰 Usage & Costs Tab (Default)
**Purpose:** Monitor API usage and costs in real-time

**Metrics Displayed:**
- Total invoices processed
- Total pages scanned
- Total API tokens consumed
- Total cost (in USD)
- Average cost per invoice
- OCR costs breakdown
- Parsing costs breakdown

**Recent Invoices Table:**
- Invoice ID
- Page count
- Tokens used
- Cost per invoice
- Processing time
- Validation status
- Timestamp

**Cost Breakdown:**
- Visual split between OCR and Parsing costs
- Percentage distribution

### 📊 Performance Tab
**Purpose:** Monitor system health and performance

**System Performance:**
- Uptime (hours and minutes)
- Average processing time
- Active sessions count

**Invoice Statistics:**
- Total processed
- Success count
- Failed count
- Success rate percentage

**Integration Status:**
- Telegram connection status
- Google Sheets accessibility
- Gemini API availability

### 📝 Logs Tab
**Purpose:** View and search application logs

**Features:**
- **Search:** Find specific log entries
- **Filter by Level:** DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Lines Count:** View last 50/100/200/500 lines
- **Log Statistics:** Total, filtered, and returned line counts
- **Color Coding:**
  - 🟢 INFO (green)
  - 🟡 WARNING (yellow)
  - 🔴 ERROR (red)
  - 🔴 CRITICAL (bright red)
  - 🔵 DEBUG (blue)

**Controls:**
- Search box (press Enter to search)
- Level filter dropdown
- Lines count selector
- Refresh button
- Clear filters button

## Auto-Refresh

The dashboard automatically refreshes every 10 seconds:
- Usage & Costs tab: ✅ Auto-refresh enabled
- Performance tab: ✅ Auto-refresh enabled
- Logs tab: ❌ Manual refresh only (to avoid disrupting reading)

## API Endpoints (For Developers)

All endpoints return JSON data:

| Endpoint | Purpose |
|----------|---------|
| `/health` | Basic health check |
| `/metrics` | Complete system metrics |
| `/status` | Detailed status with sessions |
| `/usage/customer` | Customer usage summary |
| `/usage/invoices` | Recent invoice records (last 20) |
| `/usage/ocr-calls` | Recent OCR API calls (last 50) |
| `/usage/invoice/{id}` | Specific invoice details |
| `/logs?search=&level=&lines=` | Filtered log entries |
| `/dashboard` | HTML dashboard (this page) |

## Usage Examples

### View Total Costs
1. Open dashboard
2. Default tab shows total cost prominently
3. Scroll down to see OCR vs Parsing breakdown

### Check Recent Invoice Processing
1. Open dashboard
2. Scroll to "Recent Invoices" table
3. View individual invoice costs and validation status

### Monitor System Health
1. Click "Performance" tab
2. Check integration status (all should be green ✅)
3. View success rate and uptime

### Search Logs for Errors
1. Click "Logs" tab
2. Select "ERROR" from level dropdown
3. Or type search term and press Enter
4. View matching log entries

### Track API Token Usage
1. Go to "Usage & Costs" tab
2. View "Total Tokens Used" metric
3. Check breakdown by OCR and Parsing

## Troubleshooting

### Dashboard Not Loading?
**Check:** Is health server running?
```powershell
Test-NetConnection -ComputerName localhost -Port 8080 -InformationLevel Quiet
```
Should return `True`

### No Data Showing?
**Reason:** No invoices processed yet
**Solution:** Process at least one invoice via Telegram bot to see data

### "Connection Error" Message?
**Check:** 
1. Health server is running on port 8080
2. Bot is running (has active metrics to report)
3. No firewall blocking localhost:8080

### Usage Data Shows Zero?
**Check:** 
1. Have you processed any invoices?
2. Is usage tracking enabled? (check logs)
3. Files exist: `logs/invoice_usage.jsonl` and `logs/customer_usage_summary.json`

## Data Files

Dashboard reads from these files:

**Usage Tracking:**
- `logs/customer_usage_summary.json` - Aggregated customer usage
- `logs/invoice_usage.jsonl` - Per-invoice records (JSONL format)
- `logs/ocr_calls.jsonl` - Individual OCR API calls

**Logs:**
- `logs/gst_scanner.log` - Application logs

**Notes:**
- JSONL files append one JSON object per line
- Files are created automatically when first invoice is processed
- Safe to view/backup anytime (read-only for dashboard)

## Tips

1. **Keep dashboard open** during bot usage to monitor costs in real-time
2. **Use log search** to quickly find errors during debugging
3. **Check cost breakdown** to optimize API usage (identify expensive operations)
4. **Monitor success rate** to catch validation issues early
5. **Export logs** via browser's "Save Page As" if needed for analysis

## Browser Compatibility

Tested and works on:
- ✅ Chrome/Edge (recommended)
- ✅ Firefox
- ✅ Safari

**Recommended:** Use Chrome or Edge for best performance.

---

**Dashboard Version:** v2.0-monitoring  
**Last Updated:** 2026-02-07
