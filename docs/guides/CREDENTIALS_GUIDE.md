# API Keys and Credentials Checklist

## ✅ What You Need

### 1. Telegram Bot Token
- **Where to get:** [@BotFather](https://t.me/botfather) on Telegram
- **Command:** `/newbot`
- **Format:** `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
- **Add to:** `.env` file as `TELEGRAM_BOT_TOKEN`

### 2. Google Gemini API Key
- **Where to get:** [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Format:** `AIzaSyABC123...`
- **Add to:** `.env` file as `GOOGLE_API_KEY`
- **Note:** Free tier available for testing

### 3. Google Sheets Credentials
- **Where to get:** [Google Cloud Console](https://console.cloud.google.com/)
- **Steps:**
  1. Create project
  2. Enable Google Sheets API
  3. Enable Google Drive API
  4. Create Service Account
  5. Download JSON key
- **File name:** `credentials.json`
- **Location:** Project root folder

### 4. Google Sheet ID
- **Where to find:** Google Sheets URL
- **URL format:** `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`
- **Example:** `1a2b3c4d5e6f7g8h9i0j`
- **Add to:** `.env` file as `GOOGLE_SHEET_ID`

---

## 📋 Pre-Setup Checklist

Before running the bot, make sure you have:

- [ ] Created Telegram bot via BotFather
- [ ] Copied bot token
- [ ] Created Google Cloud project
- [ ] Enabled Google Sheets API
- [ ] Enabled Google Drive API
- [ ] Created service account
- [ ] Downloaded credentials.json
- [ ] Renamed file to credentials.json
- [ ] Moved credentials.json to project folder
- [ ] Copied service account email
- [ ] Opened your Google Sheet
- [ ] Shared sheet with service account email (Editor permission)
- [ ] Copied Google Sheet ID from URL
- [ ] Obtained Google Gemini API key
- [ ] Created .env file (copied from .env.example)
- [ ] Filled in all values in .env

---

## 🔐 Sample .env File

```env
# Copy this to .env and fill in your actual values

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Google Gemini API Configuration
GOOGLE_API_KEY=AIzaSyABC123def456GHI789jkl

# Google Sheets Configuration
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEET_ID=1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r
SHEET_NAME=Invoice_Header

# Application Configuration
ALLOWED_IMAGE_FORMATS=jpg,jpeg,png,pdf
MAX_IMAGES_PER_INVOICE=10
TEMP_FOLDER=temp_invoices
```

---

## 🧪 Testing Your Credentials

After setting up, run:

```bash
python test_system.py
```

This will verify:
- ✅ All API keys are valid
- ✅ Google Sheets connection works
- ✅ Sheet structure is correct
- ✅ OCR engine initializes
- ✅ GST parser works

---

## ⚠️ Security Notes

**NEVER commit or share:**
- `.env` file
- `credentials.json` file
- Any API keys or tokens

**If credentials are compromised:**
1. **Telegram Bot:** Use BotFather to revoke and create new token
2. **Gemini API:** Delete old key in Google AI Studio, create new
3. **Service Account:** Delete and create new in Google Cloud Console

---

## 🆘 Common Issues

### Issue: "Invalid authentication credentials"
**Solution:** 
- Check Google API key is correct
- Verify credentials.json is valid
- Ensure service account has access to sheet

### Issue: "Bot token invalid"
**Solution:**
- Copy token again from BotFather
- Make sure no extra spaces in .env file
- Check token format is correct

### Issue: "Permission denied on Google Sheet"
**Solution:**
- Share sheet with service account email
- Grant "Editor" permission
- Check sheet ID is correct

---

## 📞 Support

For setup help:
1. Read SETUP_GUIDE.md
2. Run test_system.py to diagnose
3. Check error messages carefully
4. Contact your administrator

---

**Last Updated:** February 2026
