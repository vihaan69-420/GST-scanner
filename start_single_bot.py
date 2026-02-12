#!/usr/bin/env python3
"""
Single Instance Bot Launcher
Ensures only ONE bot instance is running
"""
import sys
import os
import subprocess
import time

def kill_all_bots():
    """Kill all existing bot instances"""
    try:
        # Windows command to find and kill python processes running run_bot.py
        result = subprocess.run(
            ['powershell', '-Command', 
             "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*run_bot.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
            capture_output=True,
            text=True,
            timeout=10
        )
        print("[OK] Killed all existing bot instances")
        time.sleep(2)
    except Exception as e:
        print(f"[WARNING] Failed to kill processes: {e}")

def count_bot_instances():
    """Count how many bot instances are running"""
    try:
        result = subprocess.run(
            ['powershell', '-Command',
             "(Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*run_bot.py*' } | Measure-Object).Count"],
            capture_output=True,
            text=True,
            timeout=10
        )
        count = int(result.stdout.strip()) if result.stdout.strip() else 0
        return count
    except:
        return 0

def start_single_bot():
    """Start a single bot instance"""
    print("="*80)
    print("SINGLE INSTANCE BOT LAUNCHER")
    print("="*80)
    
    # Check for existing instances
    print("\n[1/3] Checking for existing bot instances...")
    count = count_bot_instances()
    
    if count > 0:
        print(f"    Found {count} existing instance(s)")
        print("    Killing them...")
        kill_all_bots()
        count = count_bot_instances()
        if count > 0:
            print(f"    [ERROR] Still {count} instance(s) running!")
            print("    Please manually kill all Python processes and try again.")
            return False
    else:
        print("    No existing instances found")
    
    print("\n[2/3] Starting bot...")
    # Use specific Python path to avoid launcher duplication
    python_exe = r"C:\Users\clawd bot\AppData\Local\Python\pythoncore-3.14-64\python.exe"
    
    if not os.path.exists(python_exe):
        # Fallback to system python
        python_exe = "python"
        print(f"    Using system Python")
    else:
        print(f"    Using: {python_exe}")
    
    # Add current directory to Python path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    # Import and run
    from bot.telegram_bot import main
    
    print("\n[3/3] Bot starting...")
    print("="*80)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n[OK] Bot stopped by user")
    except Exception as e:
        print(f"\n[ERROR] Bot crashed: {e}")
        raise

if __name__ == "__main__":
    start_single_bot()
