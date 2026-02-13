"""
Dev Bot Dashboard
=================

A lightweight, temporary web dashboard to monitor the dev bot's activity.
Displays real-time stats: messages received, images processed, sessions, errors.

Run with: python dashboard.py
Opens at: http://localhost:8050
"""
import os
import sys
import json
import time
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent

# Shared stats file
STATS_FILE = PROJECT_ROOT / "temp" / "dev_bot_stats.json"


def _ensure_stats_file():
    """Create stats file with defaults if it doesn't exist."""
    os.makedirs(STATS_FILE.parent, exist_ok=True)
    if not STATS_FILE.exists():
        reset_stats()


def reset_stats():
    """Reset stats to defaults."""
    stats = {
        "bot_started_at": None,
        "bot_status": "stopped",
        "total_messages": 0,
        "total_images_received": 0,
        "total_images_processed": 0,
        "active_sessions": 0,
        "orders_completed": 0,
        "orders_cancelled": 0,
        "ocr_extractions": 0,
        "lines_extracted": 0,
        "lines_matched": 0,
        "lines_unmatched": 0,
        "duplicates_skipped": 0,
        "grand_total_value": 0.0,
        "errors": 0,
        "last_activity": None,
        "recent_events": [],
    }
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)
    return stats


def read_stats():
    """Read current stats."""
    _ensure_stats_file()
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return reset_stats()


def update_stat(key, value=None, increment=1):
    """Update a single stat. If value is None, increment by `increment`."""
    stats = read_stats()
    if value is not None:
        stats[key] = value
    else:
        stats[key] = stats.get(key, 0) + increment
    stats["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)
    return stats


def add_event(event_type, detail=""):
    """Add an event to the recent events list (max 50)."""
    stats = read_stats()
    event = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "type": event_type,
        "detail": detail[:100],
    }
    stats["recent_events"] = ([event] + stats.get("recent_events", []))[:50]
    stats["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GST Scanner Dev Bot Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    min-height: 100vh;
  }
  .header {
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    padding: 24px 32px;
    border-bottom: 1px solid #334155;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .header h1 {
    font-size: 22px;
    font-weight: 600;
    color: #f1f5f9;
  }
  .header .subtitle {
    font-size: 13px;
    color: #94a3b8;
    margin-top: 2px;
  }
  .status-badge {
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .status-running { background: #065f46; color: #6ee7b7; }
  .status-stopped { background: #7f1d1d; color: #fca5a5; }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  .stat-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    transition: transform 0.15s, border-color 0.15s;
  }
  .stat-card:hover {
    transform: translateY(-2px);
    border-color: #475569;
  }
  .stat-value {
    font-size: 32px;
    font-weight: 700;
    color: #f1f5f9;
    line-height: 1;
    margin-bottom: 6px;
  }
  .stat-label {
    font-size: 12px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .stat-card.blue .stat-value { color: #60a5fa; }
  .stat-card.green .stat-value { color: #34d399; }
  .stat-card.yellow .stat-value { color: #fbbf24; }
  .stat-card.red .stat-value { color: #f87171; }
  .stat-card.purple .stat-value { color: #a78bfa; }

  .panels {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }
  @media (max-width: 768px) {
    .panels { grid-template-columns: 1fr; }
  }
  .panel {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    overflow: hidden;
  }
  .panel-header {
    padding: 14px 20px;
    background: #334155;
    font-size: 14px;
    font-weight: 600;
    color: #cbd5e1;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .panel-body {
    padding: 16px 20px;
    max-height: 400px;
    overflow-y: auto;
  }
  .event-row {
    display: flex;
    align-items: flex-start;
    padding: 8px 0;
    border-bottom: 1px solid #1e293b44;
    font-size: 13px;
  }
  .event-row:last-child { border-bottom: none; }
  .event-time {
    color: #64748b;
    min-width: 70px;
    font-family: 'Cascadia Code', monospace;
    font-size: 12px;
  }
  .event-type {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    margin: 0 8px;
    min-width: 80px;
    text-align: center;
  }
  .event-type.command { background: #1e3a5f; color: #60a5fa; }
  .event-type.image { background: #064e3b; color: #6ee7b7; }
  .event-type.process { background: #713f12; color: #fbbf24; }
  .event-type.error { background: #7f1d1d; color: #fca5a5; }
  .event-type.info { background: #3b0764; color: #c4b5fd; }
  .event-detail { color: #94a3b8; flex: 1; }

  .info-row {
    display: flex;
    justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid #33415544;
    font-size: 13px;
  }
  .info-row:last-child { border-bottom: none; }
  .info-label { color: #64748b; }
  .info-value { color: #e2e8f0; font-weight: 500; font-family: monospace; }

  .refresh-note {
    text-align: center;
    color: #475569;
    font-size: 12px;
    margin-top: 20px;
  }
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>GST Scanner Dev Bot Dashboard</h1>
      <div class="subtitle">@sir_gst_scanner_dev_bot | Order Upload Monitor</div>
    </div>
    <div id="statusBadge" class="status-badge status-stopped">Stopped</div>
  </div>

  <div class="container">
    <div class="stats-grid">
      <div class="stat-card blue">
        <div class="stat-value" id="totalMessages">0</div>
        <div class="stat-label">Messages</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value" id="imagesReceived">0</div>
        <div class="stat-label">Images Received</div>
      </div>
      <div class="stat-card purple">
        <div class="stat-value" id="ordersCompleted">0</div>
        <div class="stat-label">Orders Completed</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value" id="linesExtracted">0</div>
        <div class="stat-label">Lines Extracted</div>
      </div>
      <div class="stat-card yellow">
        <div class="stat-value" id="linesMatched">0</div>
        <div class="stat-label">Lines Matched</div>
      </div>
      <div class="stat-card red">
        <div class="stat-value" id="errors">0</div>
        <div class="stat-label">Errors</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value" id="grandTotalValue">0.00</div>
        <div class="stat-label">Total Order Value</div>
      </div>
    </div>

    <div class="panels">
      <div class="panel">
        <div class="panel-header">Live Activity Feed</div>
        <div class="panel-body" id="eventFeed">
          <div style="color: #475569; text-align: center; padding: 40px;">
            Waiting for bot activity...
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">Bot Info</div>
        <div class="panel-body" id="botInfo">
          <div class="info-row">
            <span class="info-label">Bot Username</span>
            <span class="info-value">@sir_gst_scanner_dev_bot</span>
          </div>
          <div class="info-row">
            <span class="info-label">Environment</span>
            <span class="info-value">DEV</span>
          </div>
          <div class="info-row">
            <span class="info-label">Order Upload</span>
            <span class="info-value" style="color: #34d399;">ENABLED</span>
          </div>
          <div class="info-row">
            <span class="info-label">Started At</span>
            <span class="info-value" id="startedAt">--</span>
          </div>
          <div class="info-row">
            <span class="info-label">Last Activity</span>
            <span class="info-value" id="lastActivity">--</span>
          </div>
          <div class="info-row">
            <span class="info-label">Active Sessions</span>
            <span class="info-value" id="activeSessions">0</span>
          </div>
          <div class="info-row">
            <span class="info-label">Duplicates Skipped</span>
            <span class="info-value" id="duplicatesSkipped">0</span>
          </div>
          <div class="info-row">
            <span class="info-label">Unmatched Lines</span>
            <span class="info-value" id="linesUnmatched">0</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent PDFs section -->
    <div class="panel" style="margin-top: 20px;">
      <div class="panel-header">Recent Order PDFs</div>
      <div class="panel-body" id="pdfList">
        <div style="color: #475569; text-align: center; padding: 20px;">
          No PDFs generated yet...
        </div>
      </div>
    </div>

    <div class="refresh-note">Auto-refreshes every 2 seconds</div>
  </div>

  <script>
    // ---- Stats polling ----
    async function refreshStats() {
      try {
        const resp = await fetch('/api/stats?' + Date.now());
        if (!resp.ok) return;
        const s = await resp.json();

        const badge = document.getElementById('statusBadge');
        if (s.bot_status === 'running') {
          badge.textContent = 'Running';
          badge.className = 'status-badge status-running';
        } else {
          badge.textContent = 'Stopped';
          badge.className = 'status-badge status-stopped';
        }

        document.getElementById('totalMessages').textContent = s.total_messages || 0;
        document.getElementById('imagesReceived').textContent = s.total_images_received || 0;
        document.getElementById('ordersCompleted').textContent = s.orders_completed || 0;
        document.getElementById('linesExtracted').textContent = s.lines_extracted || 0;
        document.getElementById('linesMatched').textContent = s.lines_matched || 0;
        document.getElementById('errors').textContent = s.errors || 0;
        var gtVal = parseFloat(s.grand_total_value || 0);
        document.getElementById('grandTotalValue').textContent = gtVal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        document.getElementById('startedAt').textContent = s.bot_started_at || '--';
        document.getElementById('lastActivity').textContent = s.last_activity || '--';
        document.getElementById('activeSessions').textContent = s.active_sessions || 0;
        document.getElementById('duplicatesSkipped').textContent = s.duplicates_skipped || 0;
        document.getElementById('linesUnmatched').textContent = s.lines_unmatched || 0;

        const feed = document.getElementById('eventFeed');
        const events = s.recent_events || [];
        if (events.length === 0) {
          feed.innerHTML = '<div style="color:#475569;text-align:center;padding:40px;">Waiting for bot activity...</div>';
        } else {
          feed.innerHTML = events.map(e => `
            <div class="event-row">
              <span class="event-time">${e.time}</span>
              <span class="event-type ${e.type}">${e.type}</span>
              <span class="event-detail">${e.detail}</span>
            </div>
          `).join('');
        }
      } catch (err) {
        // Silently retry
      }
    }

    async function refreshPdfs() {
      try {
        const resp = await fetch('/api/pdfs?' + Date.now());
        if (!resp.ok) return;
        const pdfs = await resp.json();
        const el = document.getElementById('pdfList');
        if (pdfs.length === 0) {
          el.innerHTML = '<div style="color:#475569;text-align:center;padding:20px;">No PDFs generated yet...</div>';
        } else {
          el.innerHTML = pdfs.map(p => `
            <div class="event-row" style="align-items:center;">
              <span class="event-time">${p.modified.split(' ')[1]}</span>
              <a href="${p.url}" target="_blank" style="color:#60a5fa;text-decoration:none;flex:1;margin-left:8px;">
                ${p.name}
              </a>
              <span style="color:#64748b;font-size:12px;margin-left:8px;">
                ${(p.size / 1024).toFixed(1)} KB
              </span>
              <a href="${p.url}" download style="color:#34d399;margin-left:12px;font-size:12px;text-decoration:none;">
                Download
              </a>
            </div>
          `).join('');
        }
      } catch (err) {}
    }

    setInterval(refreshStats, 2000);
    setInterval(refreshPdfs, 5000);
    refreshStats();
    refreshPdfs();
  </script>
</body>
</html>"""


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for the dashboard."""

    def log_message(self, format, *args):
        """Suppress default access logs."""
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
        elif self.path.startswith("/api/stats"):
            stats = read_stats()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode("utf-8"))
        elif self.path.startswith("/api/pdfs"):
            # List available PDFs in the temp folder
            pdf_dir = PROJECT_ROOT / "temp"
            pdfs = []
            if pdf_dir.exists():
                for f in sorted(pdf_dir.glob("order_*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True):
                    pdfs.append({
                        "name": f.name,
                        "size": f.stat().st_size,
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "url": f"/pdf/{f.name}",
                    })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(pdfs).encode("utf-8"))
        elif self.path.startswith("/pdf/"):
            # Serve a PDF file from the temp folder
            filename = self.path[5:]  # strip "/pdf/"
            # Security: only allow simple filenames (no path traversal)
            if "/" in filename or "\\" in filename or ".." in filename:
                self.send_error(403, "Forbidden")
                return
            pdf_path = PROJECT_ROOT / "temp" / filename
            if pdf_path.exists() and pdf_path.suffix == ".pdf":
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f"inline; filename=\"{filename}\"")
                self.send_header("Content-Length", str(pdf_path.stat().st_size))
                self.end_headers()
                with open(pdf_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "PDF not found")
        else:
            self.send_error(404)


def run_dashboard(port=8050):
    """Start the dashboard HTTP server."""
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Dashboard running at http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    _ensure_stats_file()
    print("=" * 60)
    print("GST SCANNER DEV BOT DASHBOARD")
    print("=" * 60)
    run_dashboard()
