# GST Scanner - Monitoring & Health Check Guide

## Overview

The GST Scanner Bot now includes a comprehensive monitoring system that provides real-time visibility into bot health, processing metrics, API usage, and errors.

## Features

### 1. Structured Logging
- **Rotating log files** (10MB per file, 5 backups)
- **Separate error logs** for quick troubleshooting
- **Contextual logging** with timestamps, component names, and log levels
- **Immediate flush** to prevent buffering delays

### 2. Metrics Tracking
- **Invoice processing metrics** (success/failure rates, processing times)
- **API usage tracking** (OCR calls, parsing calls, token estimates, costs)
- **Performance metrics** (average processing time, active sessions)
- **Error tracking** (total errors, errors by type, last error details)

### 3. Health Check Endpoints
- **HTTP server** running on port 8080 (configurable)
- **JSON API endpoints** for programmatic access
- **Web dashboard** for visual monitoring

### 4. Integration Monitoring
- Telegram connection status
- Google Sheets accessibility
- Gemini API availability

---

## Quick Start

### Start the Bot with Monitoring

```bash
cd C:\Users\clawd bot\Documents\GST-scanner
python start_bot.py
```

The bot will automatically:
1. Initialize structured logging
2. Start the health server on port 8080
3. Begin tracking metrics

### Check Bot Health (CLI)

```bash
# Quick health check
python scripts/check_health.py

# View detailed metrics
python scripts/check_health.py metrics

# Open web dashboard
python scripts/check_health.py dashboard
```

### View Dashboard (Browser)

Open your browser and navigate to:
```
http://localhost:8080/dashboard
```

The dashboard auto-refreshes every 10 seconds.

---

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Monitoring Configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE_MAX_MB=10                # Max log file size before rotation
LOG_FILE_BACKUP_COUNT=5           # Number of backup log files to keep
HEALTH_SERVER_PORT=8080           # Port for health server
HEALTH_SERVER_ENABLED=true        # Enable/disable health server
METRICS_SAVE_INTERVAL=300         # Save metrics every N seconds (5 min)
```

### Log Levels

| Level    | When to Use                                    |
|----------|------------------------------------------------|
| DEBUG    | Development/troubleshooting (verbose output)   |
| INFO     | Production (normal operations)                 |
| WARNING  | Non-critical issues                            |
| ERROR    | Errors that don't stop processing              |
| CRITICAL | Fatal errors requiring immediate attention     |

---

## HTTP Endpoints

### Base URL
```
http://localhost:8080
```

### Available Endpoints

#### 1. `/health` - Basic Health Check
Returns overall health status and integration status.

**Example:**
```bash
curl http://localhost:8080/health | jq
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-03T10:15:30Z",
  "uptime_seconds": 3600,
  "version": "v2.0-monitoring",
  "integrations": {
    "telegram_connected": true,
    "sheets_accessible": true,
    "gemini_api_available": true
  }
}
```

#### 2. `/metrics` - Complete Metrics
Returns all tracked metrics.

**Example:**
```bash
curl http://localhost:8080/metrics | jq
```

**Response:**
```json
{
  "uptime_seconds": 3600,
  "last_updated": "2026-02-03T10:15:30Z",
  "invoices": {
    "total": 45,
    "success": 42,
    "failed": 3
  },
  "api_calls": {
    "ocr": {
      "count": 98,
      "estimated_tokens": 196000,
      "estimated_cost_usd": 0.0367
    },
    "parsing": {
      "count": 45,
      "estimated_tokens": 45000,
      "estimated_cost_usd": 0.0034
    },
    "total_cost_usd": 0.0401
  },
  "performance": {
    "avg_processing_time_seconds": 12.5,
    "active_sessions": 1
  },
  "errors": {
    "total": 5,
    "by_type": {
      "OCRError": 2,
      "ValidationError": 3
    }
  }
}
```

#### 3. `/status` - Detailed Status
Returns status with active sessions.

**Example:**
```bash
curl http://localhost:8080/status | jq
```

#### 4. `/api-usage` - API Usage Breakdown
Returns API usage and cost details.

**Example:**
```bash
curl http://localhost:8080/api-usage | jq
```

#### 5. `/dashboard` - Web Dashboard
Interactive HTML dashboard with real-time updates.

---

## Log Files

### Location
```
C:\Users\clawd bot\Documents\GST-scanner\logs\
```

### Files

| File                  | Description                          | Max Size | Retention |
|-----------------------|--------------------------------------|----------|-----------|
| `gst_scanner.log`     | Main application log (all levels)    | 10 MB    | 5 files   |
| `gst_scanner.log.1-5` | Rotated backup logs                  | 10 MB    | -         |
| `errors.log`          | Error-only log (ERROR and CRITICAL)  | 5 MB     | 3 files   |
| `metrics.json`        | Persisted metrics (auto-saved)       | -        | 1 file    |

### Log Format
```
[YYYY-MM-DD HH:MM:SS] [LEVEL] [Component] Message
```

**Example:**
```
[2026-02-03 10:15:30] [INFO] [Bot] Starting GST Scanner Bot
[2026-02-03 10:15:32] [INFO] [OCR] Starting OCR for INV-12345-1675432530
[2026-02-03 10:15:38] [INFO] [Parser] Parsing complete for INV-12345-1675432530
[2026-02-03 10:15:40] [ERROR] [Sheets] Failed to update row 45: Network timeout
```

### View Logs in Real-Time

**PowerShell:**
```powershell
Get-Content logs\gst_scanner.log -Wait -Tail 50
```

**Git Bash / WSL:**
```bash
tail -f logs/gst_scanner.log
```

### Search Logs

**Find all errors:**
```powershell
Select-String -Path logs\gst_scanner.log -Pattern "ERROR"
```

**Find specific invoice:**
```powershell
Select-String -Path logs\gst_scanner.log -Pattern "INV-12345"
```

---

## Monitoring Use Cases

### 1. Check if Bot is Running
```bash
python scripts/check_health.py
```
Exit code: 0 = healthy, 1 = unhealthy

### 2. Monitor API Costs
```bash
curl http://localhost:8080/api-usage | jq '.total_cost_usd'
```

### 3. Track Processing Performance
```bash
curl http://localhost:8080/metrics | jq '.performance.avg_processing_time_seconds'
```

### 4. View Current Sessions
```bash
curl http://localhost:8080/status | jq '.active_sessions'
```

### 5. Troubleshoot Recent Errors
```bash
# View last error
curl http://localhost:8080/metrics | jq '.errors.last_error'

# Search error logs
Select-String -Path logs\errors.log -Pattern "." | Select-Object -Last 10
```

### 6. Verify Integrations
```bash
curl http://localhost:8080/health | jq '.integrations'
```

---

## Dashboard Overview

### Sections

1. **Invoice Processing**
   - Total invoices processed
   - Success/failure counts
   - Success rate percentage

2. **API Usage & Costs**
   - OCR and parsing call counts
   - Token usage estimates
   - Total estimated cost in USD

3. **Performance**
   - Bot uptime
   - Average processing time
   - Active sessions
   - Current processing status

4. **Integrations Status**
   - Telegram connection (green = connected)
   - Google Sheets access (green = accessible)
   - Gemini API status (green = available)

5. **Recent Errors**
   - Last error timestamp
   - Error type and message
   - Total error count

### Auto-Refresh
The dashboard automatically refreshes every 10 seconds to show real-time data.

---

## Troubleshooting

### Health Server Not Starting

**Problem:** Health server fails to start

**Solutions:**
1. Check if port 8080 is already in use:
   ```powershell
   netstat -ano | findstr :8080
   ```

2. Change port in `.env`:
   ```env
   HEALTH_SERVER_PORT=8081
   ```

3. Disable health server if not needed:
   ```env
   HEALTH_SERVER_ENABLED=false
   ```

### Logs Not Appearing

**Problem:** Logs are not being written or updated

**Solutions:**
1. Check if `logs/` directory exists and is writable
2. Verify `LOG_LEVEL` is not set to a restrictive level
3. Check disk space

### Metrics Not Updating

**Problem:** Metrics on dashboard are stale

**Solutions:**
1. Verify bot is processing invoices
2. Check if metrics file is writable: `logs/metrics.json`
3. Restart bot to reset metrics

### Dashboard Shows "Connection Error"

**Problem:** Cannot connect to health server

**Solutions:**
1. Verify bot is running
2. Check health server started successfully in console output
3. Verify port number matches configuration
4. Check firewall settings

---

## Best Practices

### Production Deployment

1. **Set appropriate log level:**
   ```env
   LOG_LEVEL=INFO  # Use INFO for production, DEBUG for development
   ```

2. **Monitor disk space:**
   - Log files rotate automatically, but check disk space regularly
   - Each log file can be up to 10 MB

3. **Regular health checks:**
   - Set up a cron job or scheduled task to check health
   - Alert on unhealthy status

4. **Cost monitoring:**
   - Check API costs daily
   - Set up alerts for unexpected cost increases

5. **Error review:**
   - Review `errors.log` weekly
   - Investigate patterns in error types

### Development

1. **Use DEBUG log level:**
   ```env
   LOG_LEVEL=DEBUG
   ```

2. **Monitor logs in real-time:**
   ```powershell
   Get-Content logs\gst_scanner.log -Wait -Tail 50
   ```

3. **Clear old metrics:**
   ```powershell
   Remove-Item logs\metrics.json
   ```

---

## Integration with External Tools

### Prometheus/Grafana

Scrape metrics from `/metrics` endpoint:
```yaml
scrape_configs:
  - job_name: 'gst-scanner'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
```

### Uptime Monitoring

Use `/health` endpoint with services like:
- UptimeRobot
- Pingdom
- StatusCake

Configuration:
- URL: `http://your-server:8080/health`
- Check for: `"status": "healthy"`
- Interval: 5 minutes

### Log Aggregation

Forward logs to centralized logging:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Splunk**
- **Datadog**

Logs are already in structured format for easy parsing.

---

## Metrics Reference

### Token Cost Estimates

| API Type | Model          | Pricing (per 1K tokens) | Avg Tokens |
|----------|----------------|-------------------------|------------|
| OCR      | Gemini Flash   | $0.0001875              | 2000       |
| Parsing  | Gemini Flash   | $0.000075               | 1000       |

**Note:** Costs are estimates based on typical invoice sizes.

### Processing Times

| Operation      | Typical Time |
|----------------|--------------|
| OCR (1 page)   | 3-5 seconds  |
| Parsing        | 2-3 seconds  |
| Sheets Update  | 1-2 seconds  |
| **Total**      | **6-10 sec** |

---

## Support

For issues or questions:
1. Check logs in `logs/gst_scanner.log` and `logs/errors.log`
2. Run health check: `python scripts/check_health.py`
3. Review dashboard: `http://localhost:8080/dashboard`
4. Refer to main documentation: `docs/main/README.md`

---

**Last Updated:** February 3, 2026  
**Version:** 2.0 (Monitoring Release)
