#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick test script to verify bot is responding
"""
import sys
import io
# Fix encoding for Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests
import time

BOT_TOKEN = "8436704730:AAHhiKFVWTlwDgIUeSFbwzT8UlrVBMtdbpU"
# Replace with your actual Telegram user ID
CHAT_ID = "7332697107"  # Update this with the actual test user ID

def send_message(text):
    """Send a message to the bot"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text
    }
    response = requests.post(url, json=data)
    return response.json()

def get_bot_info():
    """Get bot information to verify it's running"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    response = requests.get(url)
    return response.json()

if __name__ == "__main__":
    print("Testing GST Scanner Bot...")
    print("="*80)
    
    # Test 1: Check bot info
    print("\n[Test 1] Getting bot info...")
    bot_info = get_bot_info()
    if bot_info.get('ok'):
        print(f"[OK] Bot is online: @{bot_info['result']['username']}")
    else:
        print(f"[FAIL] Bot error: {bot_info}")
        exit(1)
    
    # Test 2: Send /start command
    print("\n[Test 2] Sending /start command...")
    result = send_message("/start")
    if result.get('ok'):
        print("[OK] Command sent successfully")
    else:
        print(f"[FAIL] Error: {result}")
    
    time.sleep(2)
    
    # Test 3: Send /help command  
    print("\n[Test 3] Sending /help command...")
    result = send_message("/help")
    if result.get('ok'):
        print("[OK] Command sent successfully")
    else:
        print(f"[FAIL] Error: {result}")
    
    print("\n" + "="*80)
    print("Test commands sent. Check your Telegram to see if bot responded.")
    print("Check logs at: logs/gst_scanner.log")
    print("="*80)
