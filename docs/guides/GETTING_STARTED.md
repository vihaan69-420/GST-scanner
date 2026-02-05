# 🚀 GST SCANNER - Getting Started in 5 Minutes

**Quick visual guide to get your GST Scanner running!**

---

## ⏱️ Time Required: 5-10 minutes (after prerequisites)

---

## 📋 Before You Start - Checklist

Have these ready:

- [ ] Python 3.8+ installed
- [ ] Telegram account
- [ ] Google account
- [ ] Google Sheet created
- [ ] 10 minutes of time

---

## 🎯 Step-by-Step Visual Guide

### Step 1️⃣: Install Dependencies (1 minute)

Open terminal/PowerShell in project folder:

```bash
pip install -r requirements.txt
```

**Expected Output:**
```
✓ Successfully installed python-telegram-bot
✓ Successfully installed google-generativeai
✓ Successfully installed gspread
... (more packages)
```

---

### Step 2️⃣: Get Telegram Bot Token (2 minutes)

1. Open Telegram
2. Search: `@BotFather`
3. Send: `/newbot`
4. Follow prompts
5. **Copy your token** (looks like: `1234567890:ABC...`)

```
Example Token:
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-123456
```

---

### Step 3️⃣: Get Google Gemini API Key (1 minute)

1. Visit: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. **Copy your key** (starts with: `AIza...`)

```
Example Key:
AIzaSyABC123def456GHI789jkl012MNO345pqr678
```

---

### Step 4️⃣: Setup Google Sheets (3 minutes)

#### A. Create Service Account

1. Go to: https://console.cloud.google.com/
2. Create new project: "GST Scanner"
3. Enable APIs:
   - Google Sheets API ✓
   - Google Drive API ✓
4. Create Service Account:
   - IAM & Admin → Service Accounts
   - Create → Name: "gst-scanner-bot"
   - Role: Editor
5. Create Key:
   - Keys tab → Add Key → JSON
   - Download file
   - Rename to: `credentials.json`
   - Move to project folder

#### B. Share Your Sheet

1. Open `credentials.json`
2. Find `"client_email"`: `"gst-scanner-bot@..."`
3. **Copy that email**
4. Open your Google Sheet
5. Click "Share"
6. Paste the email
7. Set permission: "Editor"
8. Click "Share"

#### C. Get Sheet ID

Open your Google Sheet, look at URL:
```
https://docs.google.com/spreadsheets/d/1a2b3c4d5e6f7g8h9i0j/edit
                                          ^^^^^^^^^^^^^^^^^^^
                                          This is your ID
```

**Copy the ID part**

---

### Step 5️⃣: Configure .env File (2 minutes)

1. Copy example file:
   ```bash
   copy .env.example .env
   ```

2. Open `.env` in text editor

3. Fill in your values:
   ```env
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   GOOGLE_API_KEY=AIzaSyABC123def456GHI789jkl
   GOOGLE_SHEET_ID=1a2b3c4d5e6f7g8h9i0j
   ```

4. Save the file

---

### Step 6️⃣: Test Everything (1 minute)

Run the test script:

```bash
python test_system.py
```

**You should see:**
```
╔══════════════════════════════════════════════════════════════╗
║                    GST SCANNER - SYSTEM TEST                 ║
╚══════════════════════════════════════════════════════════════╝

✅ All tests passed! System is ready to use.

Run the bot with: python telegram_bot.py
```

**If any test fails**, read the error message and fix the issue.

---

### Step 7️⃣: Start the Bot (10 seconds)

#### Option A: Windows (Easy)
Double-click: `start_bot.bat`

#### Option B: Command Line
```bash
python telegram_bot.py
```

**You should see:**
```
================================================================================
GST SCANNER BOT STARTED
================================================================================
Bot is running and ready to receive invoices...
```

---

### Step 8️⃣: Test with Telegram (1 minute)

1. Open Telegram
2. Search for your bot (username you created)
3. Send: `/start`
4. Send a sample invoice image
5. Send: `/done`
6. Wait for confirmation
7. Check your Google Sheet!

---

## ✅ Success Checklist

After completing all steps:

- [ ] Tests pass
- [ ] Bot starts without errors
- [ ] Bot responds to `/start` in Telegram
- [ ] Sample invoice processes successfully
- [ ] Data appears in Google Sheet

---

## 🎯 Common Issues - Quick Fixes

### Issue: "Module not found"
**Fix:** Run `pip install -r requirements.txt`

### Issue: "Configuration validation failed"
**Fix:** Check `.env` file, ensure all values are filled

### Issue: "Failed to open Google Sheet"
**Fix:** 
1. Share sheet with service account email
2. Check Sheet ID is correct

### Issue: Bot doesn't respond
**Fix:**
1. Make sure bot is running
2. Check Bot Token is correct
3. Try `/start` command

---

## 📊 Visual Workflow

```
┌─────────────────┐
│  Prerequisites  │
│  - Python       │
│  - Telegram     │
│  - Google       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Install Packages│
│ pip install ... │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Get API Keys  │
│ - Telegram      │
│ - Gemini        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Setup Google    │
│ Sheets Access   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Configure .env  │
│  Fill in keys   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Run Tests     │
│ test_system.py  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Start Bot!    │
│telegram_bot.py  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Use via       │
│   Telegram!     │
└─────────────────┘
```

---

## 🎓 What to Do Next

### For Administrators:
1. ✓ Read SETUP_GUIDE.md for detailed info
2. ✓ Read ARCHITECTURE.md to understand system
3. ✓ Keep bot running
4. ✓ Monitor Google Sheet

### For End Users:
1. ✓ Read USER_MANUAL.md
2. ✓ Print QUICK_REFERENCE.md
3. ✓ Practice with sample invoices
4. ✓ Start processing real invoices

---

## 💡 Pro Tips

1. **Keep bot running** - Use screen/tmux on servers
2. **Monitor logs** - Check console for errors
3. **Backup sheet** - Google Sheets has version history
4. **Test first** - Always test with sample invoices
5. **Train users** - Share USER_MANUAL.md with team

---

## 🆘 Need More Help?

### Quick Help:
- Run: `python test_system.py`
- Check: Error messages in console
- Read: Troubleshooting in README.md

### Detailed Help:
- **Setup Issues:** SETUP_GUIDE.md
- **Usage Questions:** USER_MANUAL.md
- **Technical Details:** ARCHITECTURE.md
- **Everything:** PROJECT_SUMMARY.md

---

## 🎉 Congratulations!

Your GST Scanner is ready to process invoices!

**Time to celebrate!** 🎊

Now go process some invoices! 📄→📊

---

**Version:** 1.0.0  
**Last Updated:** February 2026  
**Estimated Time:** 5-10 minutes
