#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Health Checker CLI Tool
Quick script to check GST Scanner Bot health status
"""
import sys
import os
import json
from pathlib import Path

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))


def check_health():
    """Check bot health via HTTP endpoint"""
    try:
        import requests
        from config import HEALTH_SERVER_PORT
        
        url = f"http://localhost:{HEALTH_SERVER_PORT}/health"
        
        print("\n" + "="*80)
        print("GST SCANNER - HEALTH CHECK")
        print("="*80 + "\n")
        
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            
            # Display status
            status = data.get('status', 'unknown')
            if status == 'healthy':
                print("✅ Status: HEALTHY")
            elif status == 'degraded':
                print("⚠️  Status: DEGRADED")
            else:
                print("❌ Status: UNHEALTHY")
            
            # Display uptime
            uptime_sec = data.get('uptime_seconds', 0)
            uptime_hours = uptime_sec / 3600
            uptime_mins = (uptime_sec % 3600) / 60
            print(f"⏱️  Uptime: {int(uptime_hours)}h {int(uptime_mins)}m")
            
            # Display integrations
            integrations = data.get('integrations', {})
            print("\n🔗 Integrations:")
            print(f"   Telegram:      {'✅' if integrations.get('telegram_connected') else '❌'}")
            print(f"   Google Sheets: {'✅' if integrations.get('sheets_accessible') else '❌'}")
            print(f"   Gemini API:    {'✅' if integrations.get('gemini_api_available') else '❌'}")
            
            print("\n" + "="*80 + "\n")
            
            return status == 'healthy'
            
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to health server")
            print(f"   Is the bot running? Check http://localhost:{HEALTH_SERVER_PORT}\n")
            return False
        except requests.exceptions.Timeout:
            print("❌ Health check timed out")
            return False
            
    except ImportError:
        print("❌ 'requests' library not installed")
        print("   Install with: pip install requests\n")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}\n")
        return False


def check_metrics():
    """Check bot metrics via HTTP endpoint"""
    try:
        import requests
        from config import HEALTH_SERVER_PORT
        
        url = f"http://localhost:{HEALTH_SERVER_PORT}/metrics"
        
        response = requests.get(url, timeout=5)
        data = response.json()
        
        print("="*80)
        print("METRICS SUMMARY")
        print("="*80 + "\n")
        
        # Invoices
        inv = data.get('invoices', {})
        print(f"📊 Invoices:")
        print(f"   Total:    {inv.get('total', 0)}")
        print(f"   Success:  {inv.get('success', 0)}")
        print(f"   Failed:   {inv.get('failed', 0)}")
        
        success_rate = 0
        if inv.get('total', 0) > 0:
            success_rate = (inv.get('success', 0) / inv.get('total', 1)) * 100
        print(f"   Success Rate: {success_rate:.1f}%")
        
        # API Usage
        api = data.get('api_calls', {})
        print(f"\n🔌 API Usage:")
        print(f"   OCR Calls:    {api.get('ocr', {}).get('count', 0)}")
        print(f"   Parse Calls:  {api.get('parsing', {}).get('count', 0)}")
        print(f"   Total Cost:   ${api.get('total_cost_usd', 0):.4f}")
        
        # Performance
        perf = data.get('performance', {})
        print(f"\n⚡ Performance:")
        print(f"   Avg Time:     {perf.get('avg_processing_time_seconds', 0):.2f}s")
        print(f"   Active:       {perf.get('active_sessions', 0)} session(s)")
        
        # Errors
        errors = data.get('errors', {})
        print(f"\n⚠️  Errors:")
        print(f"   Total:        {errors.get('total', 0)}")
        
        print("\n" + "="*80 + "\n")
        
    except Exception as e:
        print(f"❌ Could not fetch metrics: {str(e)}\n")


def main():
    """Main CLI entry point"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'metrics':
            check_metrics()
        elif command == 'dashboard':
            try:
                from config import HEALTH_SERVER_PORT
                print(f"\n🌐 Opening dashboard at http://localhost:{HEALTH_SERVER_PORT}/dashboard\n")
                import webbrowser
                webbrowser.open(f"http://localhost:{HEALTH_SERVER_PORT}/dashboard")
            except Exception as e:
                print(f"❌ Error opening dashboard: {str(e)}\n")
        else:
            print("Usage: python check_health.py [metrics|dashboard]")
            print("\nCommands:")
            print("  (none)    - Check health status")
            print("  metrics   - Show detailed metrics")
            print("  dashboard - Open web dashboard")
            sys.exit(1)
    else:
        # Default: health check
        is_healthy = check_health()
        sys.exit(0 if is_healthy else 1)


if __name__ == "__main__":
    main()
