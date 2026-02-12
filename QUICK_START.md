# 🚀 GST-scanner - Quick Start Guide

**Location:** `C:\Users\clawd bot\Documents\GST-scanner\`  
**Version:** 2.0 (Reorganized & Improved)  
**Status:** ✅ Ready for Configuration

---

## ⚡ 5-Minute Setup

### Step 1: Copy Your Credentials (2 minutes)

Open PowerShell and run:

```powershell
cd "C:\Users\clawd bot\Documents\GST-scanner"

# Copy your .env file
copy "..\saket worksflow\.env" ".env"

# Copy your credentials
copy "..\saket worksflow\credentials.json" "config\credentials.json"
```

### Step 2: Update .env Paths (1 minute)

Open `.env` in Notepad and change these 2 lines:

```env
GOOGLE_SHEETS_CREDENTIALS_FILE=config/credentials.json
TEMP_FOLDER=temp
```

Save and close.

### Step 3: Install Dependencies (1 minute)

```powershell
pip install -r requirements.txt
```

### Step 4: Start the Bot (1 minute)

```powershell
python start_bot.py
```

**That's it!** Your bot should now be running with the new organized structure.

---

## 📁 New Directory Structure

```
GST-scanner/
├── src/              # All source code (organized by function)
│   ├── bot/          # Telegram interface
│   ├── parsing/      # GST parsing & validation
│   ├── ocr/          # OCR processing
│   ├── sheets/       # Google Sheets
│   ├── exports/      # GSTR exports
│   ├── features/     # Advanced features
│   ├── commands/     # Command handlers
│   └── utils/        # Utilities
│
├── docs/             # All documentation (organized by type)
│   ├── main/         # Core docs
│   ├── guides/       # Setup & user guides
│   ├── technical/    # Technical docs
│   └── reports/      # Test reports
│
├── tests/            # All tests (organized by type)
├── scripts/          # Utility scripts
├── config/           # Configuration files
│   └── .env.example
│
└── Root Files
    ├── README.md           # Main documentation
    ├── start_bot.py        # Main launcher
    ├── .env                # Your configuration
    └── requirements.txt    # Dependencies
```

---

## 🎯 What's Improved?

### Before (saket worksflow)
- ❌ 80+ files in root directory (cluttered)
- ❌ Hard to find files
- ❌ Hardcoded paths
- ❌ Import issues in tests

### After (GST-scanner)
- ✅ Organized into 7 clear directories
- ✅ Easy to navigate
- ✅ All paths use config
- ✅ Proper Python package structure
- ✅ Professional, production-ready

---

## 🧪 Verify Installation

### Quick Test

```powershell
cd "C:\Users\clawd bot\Documents\GST-scanner"
python tests\integration\test_system.py
```

Expected:
```
✅ All imports successful!
✅ Configuration is valid!
✅ Google Sheets connection works!
```

### Test Bot Startup

```powershell
python start_bot.py
```

Expected:
```
================================================================================
GST SCANNER BOT
================================================================================
Project Root: C:\Users\clawd bot\Documents\GST-scanner
================================================================================

[OK] Configuration validated
================================================================================
GST SCANNER BOT STARTED
================================================================================
```

---

## 📚 Documentation

All docs are now in `docs/` folder:

| Document | Location | Purpose |
|----------|----------|---------|
| Setup Guide | `docs/guides/SETUP_GUIDE.md` | Detailed setup |
| User Manual | `docs/guides/USER_MANUAL.md` | How to use |
| Architecture | `docs/main/ARCHITECTURE.md` | Technical details |
| Migration Guide | `MIGRATION_GUIDE.md` | Old → New changes |
| File Index | `docs/technical/FILE_INDEX.md` | Complete file list |

---

## 🆘 Troubleshooting

### Problem: "Module not found"

**Solution:** Make sure you're in the right directory

```powershell
cd "C:\Users\clawd bot\Documents\GST-scanner"
python start_bot.py
```

### Problem: "Configuration validation failed"

**Solution:** Check paths in `.env`

```env
# These two lines must be updated:
GOOGLE_SHEETS_CREDENTIALS_FILE=config/credentials.json
TEMP_FOLDER=temp
```

### Problem: "credentials.json not found"

**Solution:** Copy to config folder

```powershell
copy "..\saket worksflow\credentials.json" "config\credentials.json"
```

---

## ✨ Key Improvements Made

1. ✅ **Organized Structure** - 8 functional folders in src/
2. ✅ **Fixed Hardcoding** - All paths use config
3. ✅ **Proper Imports** - Clean package structure
4. ✅ **Better Docs** - Organized into 4 categories
5. ✅ **Professional** - Production-ready layout
6. ✅ **Tested** - All imports verified working

---

## 🎉 You're All Set!

Your GST Scanner is now installed in a clean, professional structure!

**Next:** Copy your credentials (Step 1 above) and start the bot!

---

**Quick Start Version:** 2.0  
**Last Updated:** February 3, 2026
