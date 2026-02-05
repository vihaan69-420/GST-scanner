# GST Scanner - Quick Setup Guide

This guide will help you set up the GST Scanner bot from scratch.

## 📋 Prerequisites Checklist

Before starting, ensure you have:
- [ ] Python 3.8 or higher installed
- [ ] A Telegram account
- [ ] A Google account
- [ ] Your Google Sheet ready

---

## 🚀 Step-by-Step Setup

### Step 1: Install Python Dependencies

Open PowerShell/Command Prompt in the project folder and run:

```powershell
pip install -r requirements.txt
```

Wait for all packages to install. You should see "Successfully installed..." messages.

---

### Step 2: Create Telegram Bot

1. **Open Telegram** and search for `@BotFather`

2. **Start a chat** with BotFather and send:
   ```
   /newbot
   ```

3. **Follow the prompts:**
   - Enter a name for your bot (e.g., "GST Scanner Bot")
   - Enter a username (must end with 'bot', e.g., "gst_scanner_bot")

4. **Copy the token** - BotFather will give you a token like:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   
   ⚠️ **Keep this token secret!**

---

### Step 3: Get Google Gemini API Key

1. **Go to** [Google AI Studio](https://makersuite.google.com/app/apikey)

2. **Sign in** with your Google account

3. **Click "Create API Key"**

4. **Copy the API key** (starts with "AIza...")

   ⚠️ **Keep this key secret!**

---

### Step 4: Set Up Google Sheets API

This is the most important step!

#### 4.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name: "GST Scanner"
4. Click "Create"

#### 4.2 Enable Required APIs

1. In the search bar, type "Google Sheets API"
2. Click on it and click "Enable"
3. Go back and search for "Google Drive API"
4. Click on it and click "Enable"

#### 4.3 Create Service Account

1. Go to **"IAM & Admin"** → **"Service Accounts"**
2. Click **"Create Service Account"**
3. Enter details:
   - Name: "gst-scanner-bot"
   - Description: "Service account for GST Scanner Bot"
4. Click **"Create and Continue"**
5. Select role: **"Editor"**
6. Click **"Continue"** then **"Done"**

#### 4.4 Generate Credentials JSON

1. Click on the service account you just created
2. Go to **"Keys"** tab
3. Click **"Add Key"** → **"Create new key"**
4. Choose **"JSON"** format
5. Click **"Create"**
6. A file will be downloaded (e.g., `gst-scanner-xyz123.json`)
7. **Rename it to `credentials.json`**
8. **Move it to your project folder** (same folder as telegram_bot.py)

#### 4.5 Share Your Google Sheet

1. **Open the JSON file** you just downloaded
2. **Find the "client_email"** field - it looks like:
   ```
   "gst-scanner-bot@project-name.iam.gserviceaccount.com"
   ```
3. **Copy this email address**
4. **Open your Google Sheet**
5. **Click "Share"** button (top-right)
6. **Paste the service account email**
7. **Make sure "Editor" permission is selected**
8. **Uncheck "Notify people"** (it's a bot, not a person)
9. **Click "Share"**

✅ Now your bot can access the sheet!

---

### Step 5: Get Your Google Sheet ID

1. **Open your Google Sheet** in a browser
2. **Look at the URL:**
   ```
   https://docs.google.com/spreadsheets/d/1a2b3c4d5e6f7g8h9i0j/edit
                                          ^^^^^^^^^^^^^^^^^^^
                                          This is your Sheet ID
   ```
3. **Copy the part between `/d/` and `/edit`**

---

### Step 6: Configure Environment Variables

1. **Copy the example file:**
   ```powershell
   copy .env.example .env
   ```

2. **Open `.env`** file in a text editor (Notepad, VS Code, etc.)

3. **Fill in your credentials:**

   ```env
   # Telegram Bot Configuration
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

   # Google Gemini API Configuration  
   GOOGLE_API_KEY=AIzaSyABC123...

   # Google Sheets Configuration
   GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
   GOOGLE_SHEET_ID=1a2b3c4d5e6f7g8h9i0j
   SHEET_NAME=Invoice_Header

   # Application Configuration (usually no need to change)
   ALLOWED_IMAGE_FORMATS=jpg,jpeg,png,pdf
   MAX_IMAGES_PER_INVOICE=10
   TEMP_FOLDER=temp_invoices
   ```

4. **Save the file**

   ⚠️ **Make sure `.env` is in the same folder as your Python files!**

---

### Step 7: Verify Your Setup

Run the test script to verify everything is configured correctly:

```powershell
python test_system.py
```

You should see:

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    GST SCANNER - SYSTEM TEST                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

================================================================================
TEST 1: Testing imports...
================================================================================
✓ python-telegram-bot
✓ google-generativeai
✓ gspread
✓ oauth2client
✓ Pillow
✓ python-dotenv

✅ All imports successful!

================================================================================
TEST 2: Testing configuration...
================================================================================
Telegram Bot Token: ✓ Set
Google API Key: ✓ Set
Google Sheet ID: ✓ Set
Credentials File: ✓ Exists

✅ Configuration is valid!

... (more tests)

🎉 All tests passed! System is ready to use.

Run the bot with: python telegram_bot.py
```

If any test fails, read the error message and fix the issue.

---

### Step 8: Start the Bot

```powershell
python telegram_bot.py
```

You should see:

```
✓ Configuration validated
================================================================================
GST SCANNER BOT STARTED
================================================================================
Bot is running and ready to receive invoices...
Temp folder: temp_invoices
Google Sheet: Invoice_Header
================================================================================
```

✅ **Your bot is now running!**

---

## 🎯 Using the Bot

### Step 1: Find Your Bot
1. Open Telegram
2. Search for your bot username (e.g., `@gst_scanner_bot`)
3. Click "Start"

### Step 2: Send Invoice
1. Take a photo of the invoice OR forward existing images
2. Send the image(s) to the bot
3. If it's a multi-page invoice, send all pages one by one

### Step 3: Process
1. Type `/done` when all pages are sent
2. Wait for the bot to process (10-30 seconds)
3. Receive confirmation with extracted data
4. Check your Google Sheet - data should be appended!

---

## 🆘 Troubleshooting

### Problem: "Configuration validation failed"
**Solution:** Check your `.env` file. Make sure all values are filled in correctly.

### Problem: "Failed to open Google Sheet"
**Solution:** 
1. Check if Sheet ID is correct in `.env`
2. Verify you shared the sheet with service account email
3. Make sure sheet name matches exactly (case-sensitive)

### Problem: "OCR Engine test failed"
**Solution:**
1. Check if Google API Key is correct
2. Verify you enabled the Gemini API
3. Check your internet connection

### Problem: Bot doesn't respond in Telegram
**Solution:**
1. Make sure bot is running (`python telegram_bot.py`)
2. Check if Bot Token is correct
3. Try sending `/start` command

### Problem: "Module not found" error
**Solution:** Run `pip install -r requirements.txt` again

---

## 📁 File Structure

Your project folder should look like this:

```
saket worksflow/
├── telegram_bot.py          ✅ Main bot file
├── ocr_engine.py            ✅ OCR logic
├── gst_parser.py            ✅ GST extraction
├── sheets_manager.py        ✅ Google Sheets
├── config.py                ✅ Configuration
├── test_system.py           ✅ Test script
├── requirements.txt         ✅ Dependencies
├── .env                     ⚠️  Your secrets (CREATE THIS)
├── credentials.json         ⚠️  Google credentials (ADD THIS)
├── README.md                📖 Documentation
├── SETUP_GUIDE.md          📖 This guide
└── temp_invoices/          📁 Auto-created for temp files
```

---

## 🔒 Security Reminders

⚠️ **NEVER share these files publicly:**
- `.env` - Contains your API keys
- `credentials.json` - Google service account credentials

⚠️ **If you use Git:**
- `.gitignore` is already configured
- Still, double-check before committing

---

## ✅ Success Checklist

Before going live, verify:

- [ ] All tests pass (`python test_system.py`)
- [ ] Bot responds to `/start` in Telegram
- [ ] Sample invoice processes successfully
- [ ] Data appears in Google Sheet correctly
- [ ] All 24 fields are extracted
- [ ] GST calculations are correct

---

## 🎉 You're Done!

Your GST Scanner bot is now ready to process invoices!

For detailed documentation, see `README.md`

**Need help?** Contact your system administrator.

---

**Last Updated:** February 2026  
**Version:** 1.0.0
