#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests
import time

BOT_TOKEN = "8436704730:AAHhiKFVWTlwDgIUeSFbwzT8UlrVBMtdbpU"
CHAT_ID = "7332697107"

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    response = requests.post(url, json=data)
    return response.json()

print("="*60)
print("SINGLE MESSAGE TEST")
print("="*60)

print("\nSending /start command...")
result = send_message("/start")
if result.get('ok'):
    print("Command sent successfully!")
    print("\nNow check your Telegram:")
    print("  - You should get ONLY ONE welcome message")
    print("  - If you get TWO messages, multiple bots are still running")
else:
    print(f"Error: {result}")

print("\nWaiting 3 seconds...")
time.sleep(3)

print("\nSending unique test message...")
test_msg = f"TEST_{int(time.time())}"
result = send_message(test_msg)
if result.get('ok'):
    print(f"Sent: {test_msg}")
    print("\nIn Telegram, you should see:")
    print(f"  - ONLY ONE echo/response")
    print("  - If you see TWO responses, report back immediately")
else:
    print(f"Error: {result}")

print("\n" + "="*60)
print("Check Telegram and report back:")
print("  - ONE message = Good, bot fixed!")
print("  - TWO messages = Still multiple instances")
print("="*60)
