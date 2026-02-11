#!/usr/bin/env python3
"""Manual test to verify order upload fix"""
import requests
import time

BOT_TOKEN = "8436704730:AAHhiKFVWTlwDgIUeSFbwzT8UlrVBMtdbpU"
CHAT_ID = "7332697107"

def send_command(cmd):
    """Send a command and return response"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": cmd}
    response = requests.post(url, json=data)
    print(f"Sent: {cmd}")
    return response.json()

print("="*60)
print("MANUAL TEST - ORDER UPLOAD FIX")
print("="*60)

print("\n[1] Sending /cancel to clear any state...")
send_command("/cancel")
time.sleep(2)

print("\n[2] Sending /order_upload to start session...")
send_command("/order_upload")
time.sleep(3)

print("\n[3] ⚠️  NOW SEND YOUR ORDER IMAGE IN TELEGRAM")
print("    After you send the image, check what the bot says:")
print("    ✅ CORRECT: 'Send more pages or type /order_submit to process'")
print("    ❌ WRONG: 'Send more pages or type /done to process'")
print()
input("Press ENTER after you've sent the image and seen bot's response...")

print("\n[4] Now type /order_submit in Telegram")
print("    Expected: 'Order submitted! Processing...'")
print()
print("="*60)
print("MANUAL VERIFICATION COMPLETE")
print("="*60)
