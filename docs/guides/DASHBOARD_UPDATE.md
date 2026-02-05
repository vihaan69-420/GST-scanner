# Enhanced Monitoring Dashboard - Update Summary

## What Changed

The monitoring dashboard has been enhanced with **tabbed navigation** and a **live log viewer** with search capabilities.

## New Features

### 1. Tabbed Interface

The dashboard now has three distinct tabs:

#### 📊 **Overview Tab** (Default)
- Invoice processing statistics
- API usage summary
- Performance metrics  
- Integration status

#### 📝 **Logs Tab** (NEW!)
- **Real-time log viewer** with syntax highlighting
- **Search functionality** - Find specific text in logs
- **Level filtering** - Filter by DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Adjustable line count** - View last 50, 100, 200, or 500 lines
- **Color-coded log levels** for easy identification
- **Log statistics** - Shows total, filtered, and displayed line counts
- **Auto-scroll** to latest logs
- **One-click refresh** and clear filters

#### 🔌 **API Details Tab** (NEW!)
- Detailed breakdown of OCR API usage
- Detailed breakdown of Parsing API usage
- Per-API token and cost tracking
- API pricing reference table
- Average tokens per call

### 2. New HTTP Endpoint

**`GET /logs`** - Returns log file contents with filtering

**Query Parameters:**
- `lines` - Number of lines to return (default: 100)
- `search` - Search term to filter logs
- `level` - Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

**Example:**
```bash
# Get last 50 lines
curl http://localhost:8080/logs?lines=50

# Search for specific text
curl http://localhost:8080/logs?search=invoice

# Filter by ERROR level
curl http://localhost:8080/logs?level=ERROR

# Combine filters
curl http://localhost:8080/logs?lines=200&level=WARNING&search=validation
```

**Response:**
```json
{
  "total_lines": 1250,
  "filtered_lines": 45,
  "returned_lines": 45,
  "logs": [
    "[2026-02-03 10:46:09] [INFO] [GST-Scanner] [Main] Starting GST Scanner Bot",
    "..."
  ]
}
```

## Benefits

### Before
- Single static page
- No log viewing capability
- Had to manually check log files
- Difficult to troubleshoot in real-time

### After
✅ **Organized sections** - Separate tabs for different monitoring needs  
✅ **Live log viewing** - See logs without leaving the browser  
✅ **Instant search** - Find specific invoices, errors, or events quickly  
✅ **Better UX** - Clear separation of concerns  
✅ **Detailed API tracking** - Per-API cost and usage visibility  

## How to Use

### Access the Enhanced Dashboard

Open your browser: `http://localhost:8080/dashboard`

### Navigate Tabs

Click on any tab button at the top:
- **📊 Overview** - General metrics and status
- **📝 Logs** - Live log viewer
- **🔌 API Details** - Detailed API usage

### Use the Log Viewer

1. **Search logs:**
   - Type in the search box
   - Press Enter or click 🔄 Refresh

2. **Filter by level:**
   - Select level from dropdown (All, DEBUG, INFO, WARNING, ERROR, CRITICAL)
   - Logs update automatically

3. **Adjust line count:**
   - Select from Last 50, 100, 200, or 500 lines
   - Useful for viewing more history

4. **Clear filters:**
   - Click ✖ Clear to reset all filters

5. **Refresh:**
   - Click 🔄 Refresh to get latest logs

### Color Coding

Logs are color-coded by level:
- **🔵 DEBUG** - Light blue
- **🟢 INFO** - Teal/Cyan
- **🟡 WARNING** - Orange
- **🔴 ERROR** - Red
- **🔴 CRITICAL** - Bright red

## Example Use Cases

### 1. Find a Specific Invoice
1. Go to **📝 Logs** tab
2. Search for invoice number (e.g., "INV-12345")
3. See all log entries related to that invoice

### 2. Check for Recent Errors
1. Go to **📝 Logs** tab
2. Select **ERROR** or **CRITICAL** from level filter
3. Review error messages

### 3. Monitor API Costs
1. Go to **🔌 API Details** tab
2. View per-API costs and token usage
3. See average tokens per call

### 4. Watch Real-Time Processing
1. Go to **📝 Logs** tab
2. Set to "Last 100" lines
3. Click refresh periodically to see new entries

## Technical Implementation

### Files Modified

1. **`src/utils/health_server.py`**
   - Added `/logs` endpoint with filtering
   - Reads from `logs/gst_scanner.log`
   - Supports search and level filtering

2. **`src/utils/dashboard.html`**
   - Complete redesign with tabbed interface
   - Added log viewer with syntax highlighting
   - Added API details section
   - Enhanced styling and UX

### Log Viewer Features

- **Syntax highlighting** using CSS classes for log levels
- **Dark theme** for better readability of logs
- **Auto-scroll** to bottom when new logs load
- **Responsive design** works on all screen sizes
- **HTML escaping** prevents XSS from log content

## Auto-Refresh Behavior

- **Overview & API tabs**: Auto-refresh every 10 seconds
- **Logs tab**: Manual refresh only (to avoid interrupting reading)

## Performance

- Log file reading is efficient (reads file once per request)
- Filtering happens in memory (fast)
- Returns only requested number of lines (bandwidth efficient)
- No database or complex backend needed

## Next Steps

Try it out:
1. Open `http://localhost:8080/dashboard`
2. Click through the tabs
3. Try searching your logs
4. Process an invoice and watch the logs update!

---

**Updated:** February 3, 2026  
**Version:** 2.1 - Enhanced Dashboard with Tabs & Log Viewer
