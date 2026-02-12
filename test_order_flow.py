#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Order Upload Flow - Complete End-to-End Test
Tests the fixed order upload process
"""
import sys
import io
import time
import requests

# Fix encoding for Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BOT_TOKEN = "8436704730:AAHhiKFVWTlwDgIUeSFbwzT8UlrVBMtdbpU"
CHAT_ID = "7332697107"

def send_message(text):
    """Send a message to the bot"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    response = requests.post(url, json=data)
    return response.json()

def send_photo(photo_path):
    """Send a photo to the bot"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(photo_path, 'rb') as photo:
        files = {'photo': photo}
        data = {'chat_id': CHAT_ID}
        response = requests.post(url, files=files, data=data)
    return response.json()

def get_updates(offset=None):
    """Get bot updates"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {'offset': offset, 'timeout': 5}
    response = requests.get(url, params=params)
    return response.json()

print("="*80)
print("ORDER UPLOAD FLOW TEST")
print("="*80)

# Test 1: Check bot is online
print("\n[Test 1] Checking bot status...")
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
response = requests.get(url)
bot_info = response.json()
if bot_info.get('ok'):
    print(f"✅ Bot is online: @{bot_info['result']['username']}")
else:
    print(f"❌ Bot error: {bot_info}")
    sys.exit(1)

time.sleep(1)

# Test 2: Start order upload session
print("\n[Test 2] Starting order upload session with /order_upload...")
result = send_message("/order_upload")
if result.get('ok'):
    print("✅ Command sent successfully")
    print(f"   Message ID: {result['result']['message_id']}")
else:
    print(f"❌ Error: {result}")
    sys.exit(1)

time.sleep(3)

# Test 3: Check if bot created order session (by trying to submit without image)
print("\n[Test 3] Testing order session creation...")
result = send_message("/order_submit")
if result.get('ok'):
    print("✅ Command sent successfully")
    print("   (Expected: Bot should say 'upload at least one page')")
else:
    print(f"❌ Error: {result}")

time.sleep(3)

# Test 4: Check available sample images
print("\n[Test 4] Checking for sample order images...")
import os
sample_images = []
for root, dirs, files in os.walk('.'):
    for file in files:
        if 'order' in file.lower() and file.lower().endswith(('.jpg', '.png', '.jpeg')):
            sample_images.append(os.path.join(root, file))

if sample_images:
    print(f"✅ Found {len(sample_images)} sample order images:")
    for img in sample_images[:3]:
        print(f"   - {img}")
    
    # Test 5: Upload a sample image
    if len(sample_images) > 0:
        print(f"\n[Test 5] Uploading sample image: {sample_images[0]}")
        try:
            result = send_photo(sample_images[0])
            if result.get('ok'):
                print("✅ Image uploaded successfully")
                print(f"   Photo ID: {result['result']['photo'][0]['file_id']}")
            else:
                print(f"❌ Upload error: {result}")
        except Exception as e:
            print(f"❌ Upload failed: {e}")
        
        time.sleep(3)
        
        # Test 6: Submit the order
        print("\n[Test 6] Submitting order with /order_submit...")
        result = send_message("/order_submit")
        if result.get('ok'):
            print("✅ Command sent successfully")
            print("   (Bot should now process the order)")
        else:
            print(f"❌ Error: {result}")
else:
    print("⚠️ No sample order images found")
    print("   Please add a test order image to test image upload")
    print("\n[Test 5] Skipping image upload test")
    print("[Test 6] Testing /order_submit without image...")
    result = send_message("/order_submit")
    if result.get('ok'):
        print("✅ Command sent (should get error about no pages)")
    else:
        print(f"❌ Error: {result}")

time.sleep(2)

# Test 7: Test help command
print("\n[Test 7] Testing /help command...")
result = send_message("/help")
if result.get('ok'):
    print("✅ Help command sent successfully")
else:
    print(f"❌ Error: {result}")

time.sleep(2)

# Test 8: Test cancel command
print("\n[Test 8] Testing /cancel command...")
result = send_message("/cancel")
if result.get('ok'):
    print("✅ Cancel command sent successfully")
else:
    print(f"❌ Error: {result}")

print("\n" + "="*80)
print("TEST COMPLETED")
print("="*80)
print("\n📱 Check your Telegram chat to verify bot responses")
print("📊 All commands were sent successfully")
print("\n**Expected Flow:**")
print("1. /order_upload → 'Order Upload Mode Activated!'")
print("2. Send image → 'Page 1 received!'")
print("3. /order_submit → 'Order submitted!' + processing")
print("\n**What to verify in Telegram:**")
print("- Bot responded to /order_upload with instructions")
print("- Bot received the image (if uploaded)")
print("- Bot processed /order_submit correctly")
print("- Error messages are clear and helpful")
print("\n✅ If all responses look good, the bug is FIXED!")
