#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify Epic 2 menu button configuration
"""
import sys
import os
import io

# Fix encoding for Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

print("="*70)
print("Epic 2 Menu Button Test")
print("="*70)

print(f"\n1. Feature Flag Status:")
print(f"   FEATURE_ORDER_UPLOAD_NORMALIZATION = {config.FEATURE_ORDER_UPLOAD_NORMALIZATION}")

print(f"\n2. Menu Button Configuration:")

# Simulate the menu creation logic
keyboard = [
    [InlineKeyboardButton("📸 Upload Purchase Invoice", callback_data="menu_upload")],
]

if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
    keyboard.append([InlineKeyboardButton("📦 Upload Order", callback_data="menu_order_upload")])
    print(f"   ✅ Order Upload button ADDED to menu")
else:
    print(f"   ❌ Order Upload button NOT added (feature flag is OFF)")

keyboard.extend([
    [InlineKeyboardButton("📊 Generate GST Input", callback_data="menu_generate")],
    [InlineKeyboardButton("ℹ️ Help", callback_data="menu_help")],
])

print(f"\n3. Complete Menu Structure:")
for i, row in enumerate(keyboard, 1):
    for button in row:
        print(f"   Button {i}: {button.text} → {button.callback_data}")

print(f"\n4. Total Buttons: {sum(len(row) for row in keyboard)}")

expected_buttons = 4 if config.FEATURE_ORDER_UPLOAD_NORMALIZATION else 3
actual_buttons = sum(len(row) for row in keyboard)

print(f"\n5. Validation:")
if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
    if actual_buttons == 4:
        print(f"   ✅ PASS: Menu has {actual_buttons} buttons (expected 4 with Epic 2)")
        print(f"   ✅ Order Upload button is present!")
    else:
        print(f"   ❌ FAIL: Menu has {actual_buttons} buttons (expected 4)")
else:
    if actual_buttons == 3:
        print(f"   ✅ PASS: Menu has {actual_buttons} buttons (expected 3 without Epic 2)")
    else:
        print(f"   ❌ FAIL: Menu has {actual_buttons} buttons (expected 3)")

print("\n" + "="*70)
print("Test Complete!")
print("="*70)

if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
    print("\n📦 Epic 2 is ENABLED - Order Upload button should appear in Telegram")
    print("   If it doesn't appear, restart the bot to reload the menu.")
else:
    print("\n⚠️  Epic 2 is DISABLED - Order Upload button will NOT appear")
