"""
Health Check HTTP Server for GST Scanner
Provides health, metrics, and monitoring endpoints
"""
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health and metrics endpoints"""
    
    # Shared state (set by server)
    bot_instance = None
    metrics_tracker = None
    logger = None
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            if self.path == '/health':
                self._serve_health()
            elif self.path == '/metrics':
                self._serve_metrics()
            elif self.path == '/status':
                self._serve_status()
            elif self.path == '/api-usage':
                self._serve_api_usage()
            elif self.path == '/dashboard':
                self._serve_dashboard()
            elif self.path.startswith('/logs'):
                self._serve_logs()
            elif self.path == '/':
                self._serve_index()
            else:
                self._send_response(404, {'error': 'Not found'})
        except Exception as e:
            self._send_response(500, {'error': str(e)})
    
    def _serve_health(self):
        """Basic health check endpoint"""
        metrics = self.metrics_tracker.get_metrics() if self.metrics_tracker else {}
        integrations = metrics.get('integrations', {})
        
        # Determine overall health
        all_healthy = all([
            integrations.get('telegram_connected', False),
            integrations.get('sheets_accessible', False),
            integrations.get('gemini_api_available', False)
        ])
        
        health_data = {
            'status': 'healthy' if all_healthy else 'degraded',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'uptime_seconds': metrics.get('uptime_seconds', 0),
            'version': 'v2.0-monitoring',
            'integrations': integrations
        }
        
        self._send_response(200, health_data)
    
    def _serve_metrics(self):
        """Complete metrics endpoint"""
        if self.metrics_tracker:
            metrics = self.metrics_tracker.get_metrics()
            self._send_response(200, metrics)
        else:
            self._send_response(503, {'error': 'Metrics not available'})
    
    def _serve_status(self):
        """Detailed status with active sessions"""
        metrics = self.metrics_tracker.get_metrics() if self.metrics_tracker else {}
        
        # Get active sessions from bot if available
        active_sessions = []
        if self.bot_instance and hasattr(self.bot_instance, 'user_sessions'):
            for user_id, session in self.bot_instance.user_sessions.items():
                active_sessions.append({
                    'user_id': user_id,
                    'state': session.get('state', 'unknown'),
                    'images_count': len(session.get('images', [])),
                    'start_time': session.get('start_time', datetime.now()).isoformat() if session.get('start_time') else None
                })
        
        status_data = {
            'status': 'running',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'uptime_seconds': metrics.get('uptime_seconds', 0),
            'active_sessions': active_sessions,
            'session_count': len(active_sessions),
            'performance': metrics.get('performance', {}),
            'last_error': metrics.get('errors', {}).get('last_error')
        }
        
        self._send_response(200, status_data)
    
    def _serve_api_usage(self):
        """API usage and token tracking endpoint"""
        metrics = self.metrics_tracker.get_metrics() if self.metrics_tracker else {}
        api_calls = metrics.get('api_calls', {})
        
        usage_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'ocr': api_calls.get('ocr', {}),
            'parsing': api_calls.get('parsing', {}),
            'total_cost_usd': api_calls.get('total_cost_usd', 0.0),
            'invoices_processed': metrics.get('invoices', {}).get('total', 0)
        }
        
        self._send_response(200, usage_data)
    
    def _serve_dashboard(self):
        """Serve HTML dashboard"""
        try:
            # Load dashboard HTML
            dashboard_path = Path(__file__).parent / 'dashboard.html'
            if dashboard_path.exists():
                with open(dashboard_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                
                # Send HTML response
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
            else:
                self._send_response(404, {'error': 'Dashboard not found'})
        except Exception as e:
            self._send_response(500, {'error': f'Dashboard error: {str(e)}'})
    
    def _serve_logs(self):
        """Serve recent logs endpoint"""
        try:
            from pathlib import Path
            log_file = Path('logs/gst_scanner.log')
            
            if not log_file.exists():
                self._send_response(404, {'error': 'Log file not found'})
                return
            
            # Get query parameters for filtering
            query_params = {}
            if '?' in self.path:
                query_string = self.path.split('?')[1]
                for param in query_string.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        query_params[key] = value
            
            lines_count = int(query_params.get('lines', 100))
            search_term = query_params.get('search', '')
            level_filter = query_params.get('level', '')
            
            # Read log file
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Apply filters
            filtered_lines = []
            for line in lines:
                # Level filter
                if level_filter and f'[{level_filter}]' not in line:
                    continue
                # Search filter
                if search_term and search_term.lower() not in line.lower():
                    continue
                filtered_lines.append(line.rstrip())
            
            # Get last N lines
            result_lines = filtered_lines[-lines_count:] if len(filtered_lines) > lines_count else filtered_lines
            
            response_data = {
                'total_lines': len(lines),
                'filtered_lines': len(filtered_lines),
                'returned_lines': len(result_lines),
                'logs': result_lines
            }
            
            self._send_response(200, response_data)
            
        except Exception as e:
            self._send_response(500, {'error': f'Failed to read logs: {str(e)}'})
    
    def _serve_index(self):
        """Serve index page with available endpoints"""
        index_html = """
<!DOCTYPE html>
<html>
<head>
    <title>GST Scanner - Monitoring</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }
        .endpoint { background: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }
        .endpoint a { color: #1976D2; text-decoration: none; font-weight: bold; }
        .endpoint a:hover { text-decoration: underline; }
        .description { color: #666; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 GST Scanner Monitoring</h1>
        <p>Bot is running. Available endpoints:</p>
        
        <div class="endpoint">
            <a href="/health">/health</a>
            <div class="description">Basic health check (JSON)</div>
        </div>
        
        <div class="endpoint">
            <a href="/metrics">/metrics</a>
            <div class="description">Complete metrics (JSON)</div>
        </div>
        
        <div class="endpoint">
            <a href="/status">/status</a>
            <div class="description">Detailed status with active sessions (JSON)</div>
        </div>
        
        <div class="endpoint">
            <a href="/api-usage">/api-usage</a>
            <div class="description">API token usage and costs (JSON)</div>
        </div>
        
        <div class="endpoint">
            <a href="/dashboard">/dashboard</a>
            <div class="description">Interactive monitoring dashboard (HTML)</div>
        </div>
    </div>
</body>
</html>
"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(index_html.encode('utf-8'))
    
    def _send_response(self, status_code: int, data: dict):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')  # Allow CORS
        self.end_headers()
        
        response_json = json.dumps(data, indent=2, ensure_ascii=False)
        self.wfile.write(response_json.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging (we use our own logger)"""
        if self.logger:
            self.logger.debug(f"HTTP {format % args}", component="HealthServer")


class HealthServer:
    """HTTP server for health checks and monitoring"""
    
    def __init__(self, port: int, bot_instance=None, metrics_tracker=None, logger=None):
        """
        Initialize health server
        
        Args:
            port: Port to run server on
            bot_instance: Reference to bot instance
            metrics_tracker: Reference to metrics tracker
            logger: Reference to logger
        """
        self.port = port
        self.server = None
        self.thread = None
        
        # Set shared state for handler
        HealthCheckHandler.bot_instance = bot_instance
        HealthCheckHandler.metrics_tracker = metrics_tracker
        HealthCheckHandler.logger = logger
    
    def start(self):
        """Start health server in background thread"""
        try:
            self.server = HTTPServer(('0.0.0.0', self.port), HealthCheckHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            
            print(f"[OK] Health server started on http://localhost:{self.port}")
            print(f"     Dashboard: http://localhost:{self.port}/dashboard")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to start health server: {e}")
            return False
    
    def stop(self):
        """Stop health server"""
        if self.server:
            self.server.shutdown()
            print("[OK] Health server stopped")


if __name__ == "__main__":
    # Test the health server
    print("\n" + "="*80)
    print("Testing Health Server")
    print("="*80 + "\n")
    
    from metrics_tracker import get_metrics_tracker
    from logger import get_logger
    
    tracker = get_metrics_tracker()
    logger = get_logger()
    
    # Add some test data
    tracker.record_ocr_call(85000, 2000)
    tracker.record_invoice_complete(True, 12.5)
    
    # Start server
    server = HealthServer(port=8080, metrics_tracker=tracker, logger=logger)
    server.start()
    
    print("\nServer running. Test endpoints:")
    print("  - http://localhost:8080/")
    print("  - http://localhost:8080/health")
    print("  - http://localhost:8080/metrics")
    print("  - http://localhost:8080/dashboard")
    print("\nPress Ctrl+C to stop...")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping server...")
        server.stop()
        print("Goodbye!")
