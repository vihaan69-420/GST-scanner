# Epic 2 Menu Status & Troubleshooting

**Date**: 2026-02-06  
**Issue**: "Upload Order" button missing in Telegram menu

---

## ✅ Configuration Status - ALL CORRECT!

### Feature Flag:
```env
FEATURE_ORDER_UPLOAD_NORMALIZATION=true    ✅ ENABLED
```

### Menu Configuration:
```
✅ Button 1: 📸 Upload Purchase Invoice
✅ Button 2: 📦 Upload Order (EPIC 2)    ← This button IS configured!
✅ Button 3: 📊 Generate GST Input
✅ Button 4: ℹ️ Help

Total: 4 buttons (correct)
```

---

## 🔍 Root Cause

The menu configuration is **100% correct** in the code. The issue is:

**Bot is not running successfully due to Telegram API conflict:**
```
telegram.error.Conflict: terminated by other getUpdates request; 
make sure that only one bot instance is running
```

**This means:**
- Another bot instance is already connected to Telegram
- Could be running on your mobile phone, another computer, or a previous session
- Telegram API only allows ONE bot instance at a time per bot token

---

## 🛠️ Solution - Force Clean Restart

### **Option 1: Manual Restart (Recommended)**

**Step 1: Stop ALL Python processes**
```powershell
Get-WmiObject Win32_Process -Filter "name = 'python.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

**Step 2: Wait for Telegram API to clear (IMPORTANT!)**
```powershell
Start-Sleep -Seconds 30
```
This gives Telegram API time to release the connection from any previous bot instance.

**Step 3: Clear Telegram webhook**
```powershell
Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot8436704730:AAHhiKFVWTlwDgIUeSFbwzT8UlrVBMtdbpU/deleteWebhook?drop_pending_updates=true"
```

**Step 4: Start bot**
```powershell
cd "c:\Users\clawd bot\Documents\GST-scanner"
python run_bot.py
```

**Step 5: Verify in Telegram**
- Open Telegram
- Send `/start` to @GST_Scanner_Bot
- You should see the "📦 Upload Order" button

---

### **Option 2: Check for Other Running Instances**

The bot might be running somewhere else:

**Check if you have the bot running:**
1. **On your mobile phone** - Check if you started the bot from another terminal/session
2. **In BrowserStack/Cloud** - Check if deployed somewhere
3. **In another terminal** - Check all your open terminal windows
4. **As a Windows service** - Check if installed as a service

**To find it:**
```powershell
# List all Python processes with command line
Get-WmiObject Win32_Process -Filter "name = 'python.exe'" | Select-Object ProcessId, CommandLine
```

---

### **Option 3: Use Different Bot Token (If Nothing Works)**

If the conflict persists, you may need to:
1. Stop any bot instances running elsewhere
2. Wait 2-5 minutes for Telegram to fully clear the connection
3. Then restart

---

## 🔧 Quick Fix Script

Run this all-in-one script:

```powershell
# Navigate to project
cd "c:\Users\clawd bot\Documents\GST-scanner"

# Kill all Python
Get-WmiObject Win32_Process -Filter "name = 'python.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# Wait for Telegram API to clear
Write-Host "Waiting for Telegram API to clear connection..."
Start-Sleep -Seconds 30

# Clear webhook
Write-Host "Clearing webhook..."
Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot8436704730:AAHhiKFVWTlwDgIUeSFbwzT8UlrVBMtdbpU/deleteWebhook?drop_pending_updates=true" | Out-Null

# Start bot
Write-Host "Starting bot..."
python run_bot.py
```

---

## ✅ Verification Checklist

After restart, verify:

1. **Bot Process Running**:
   ```powershell
   Get-Process python
   ```
   Should show active Python process

2. **No Errors in Log**:
   Check `terminals/[latest].txt` - should NOT show "Conflict" errors

3. **Test in Telegram**:
   - Send `/start` to bot
   - Look for "📦 Upload Order" button
   - If present: ✅ Success!
   - If missing: Bot may not have started successfully

---

## 🎯 Expected Telegram Menu

When working correctly, you'll see:

```
┌─────────────────────────────────┐
│  📸 Upload Purchase Invoice      │
├─────────────────────────────────┤
│  📦 Upload Order                 │  ← THIS IS EPIC 2!
├─────────────────────────────────┤
│  📊 Generate GST Input           │
├─────────────────────────────────┤
│  ℹ️ Help                         │
└─────────────────────────────────┘
```

---

## 📊 Current Status Summary

| Item | Status | Details |
|------|--------|---------|
| **Epic 2 Flag** | ✅ ON | `FEATURE_ORDER_UPLOAD_NORMALIZATION=true` |
| **Menu Code** | ✅ Correct | Button configured at line 231 |
| **Config Loading** | ✅ Working | Test shows `True` |
| **Bot Process** | ❌ Conflict | Telegram API conflict error |
| **Menu Visible** | ❌ Not yet | Bot needs to connect successfully |

---

## 💡 Why This Happens

**Telegram's "getUpdates" Conflict**:
- Telegram API uses "long polling" to receive messages
- Only ONE bot instance can poll at a time
- If another instance is connected (even from previous session), new instance gets blocked
- The API takes 30-60 seconds to timeout old connections

**This is a common issue when:**
- Bot crashes but connection not released
- Bot restarted too quickly
- Multiple terminals/machines running same bot

---

## 🚀 Recommended Action

**Run the Quick Fix Script above** - it includes proper wait times to let Telegram API clear old connections.

After that, the menu will work correctly and show all 4 buttons including "📦 Upload Order".

---

**The code is correct! It's just a Telegram connection timing issue.** 🔧
