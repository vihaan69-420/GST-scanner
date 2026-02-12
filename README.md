<<<<<<< HEAD
﻿# GST Scanner â€” Logged-in app (Chat, History, Help, Settings)

This repo contains only the **logged-in experience**: chat, history, help, settings, and full auth (login/register/session). It is exported from the main GST Scanner project.

## What's included

- **Chat** â€” Main dashboard with invoice/order upload and conversation UI
- **History** â€” History list and History & Reports (GSTR-1 / GSTR-3B)
- **Help** â€” FAQ and instructions
- **Settings** â€” Profile, subscription, usage, theme
- **Auth** â€” Login, register, session, middleware protection for \/dashboard\

## Run locally

\\\ash
npm install
cp .env.example .env   # edit if you use Google OAuth or other env vars
npm run dev
\\\

Then open http://localhost:3000 â€” you'll be redirected to login. After logging in you get the dashboard with Chat, History, Help, and Settings.

## Push this to GitHub

\\\ash
cd gst-scanner-logged-in
git init
git add .
git commit -m "Initial: chat, history, help, settings, auth"
# Create a new repository on GitHub (e.g. gst-scanner-logged-in), then:
git remote add origin https://github.com/YOUR_USERNAME/gst-scanner-logged-in.git
git branch -M main
git push -u origin main
\\\
=======
# 🤖 GST Scanner - Professional Invoice Processing Bot

**Version:** 2.0 (Reorganized Structure)  
**Location:** `C:\Users\clawd bot\Documents\GST-scanner\`  
**Status:** ✅ Production-Ready

Complete end-to-end GST invoice scanner that receives invoice images via Telegram, performs OCR using Google Gemini Vision API, extracts GST-compliant data, and appends to Google Sheets with comprehensive audit trails and export capabilities.

---

## ⚡ Quick Start

### For First-Time Setup

1. **Copy your credentials:**
   ```powershell
   copy "..\saket worksflow\.env" ".env"
   copy "..\saket worksflow\credentials.json" "config\credentials.json"
   ```

2. **Update .env file** - Change these two lines:
   ```env
   GOOGLE_SHEETS_CREDENTIALS_FILE=config/credentials.json
   TEMP_FOLDER=temp
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Start the bot:**
   ```powershell
   python start_bot.py
   ```

**See [QUICK_START.md](QUICK_START.md) for detailed 5-minute setup guide.**

---

## 📁 New Directory Structure

```
GST-scanner/
├── src/           # Application source (organized by function)
├── docs/          # Documentation (organized by type)
├── tests/         # Test suite (unit + integration)
├── scripts/       # Utility scripts
├── config/        # Configuration files
├── temp/          # Temporary files (auto-created)
└── exports/       # Export outputs (auto-created)
```

**See [DIRECTORY_TREE.md](DIRECTORY_TREE.md) for complete file listing.**

---

## ✨ What's New in Version 2.0?

### Organization Improvements
- ✅ **Clean Structure** - 95 files organized into 22 directories
- ✅ **Functional Grouping** - Source code grouped by purpose (bot/, parsing/, sheets/, etc.)
- ✅ **Proper Python Package** - All __init__.py files in place
- ✅ **Easy Navigation** - Find files intuitively by function

### Fixed Issues
- ✅ **No Hardcoded Paths** - All paths use config variables
- ✅ **Cross-Platform** - Uses pathlib.Path for compatibility
- ✅ **Clean Imports** - Professional package structure
- ✅ **Fixed temp_images Bug** - Now uses config.TEMP_FOLDER

### Documentation
- ✅ **Organized Docs** - 35 files in 4 categories (main, guides, technical, reports)
- ✅ **Migration Guide** - Complete old → new transition guide
- ✅ **File Index** - Complete file listing with descriptions
- ✅ **Quick Start** - 5-minute setup instructions

---

## 🎯 Features

### 🔹 Tier 1: Core Features
- Telegram bot interface with interactive menus
- OCR with Google Gemini 2.5 Flash Vision
- GST data extraction (24 fields)
- Line item extraction (19 fields per item)
- GST validation engine
- Google Sheets integration (5 sheets)
- Multi-page invoice support

### 🔸 Tier 2: Advanced Features
- Confidence scoring (AI-powered)
- Manual corrections interface
- Fingerprint-based deduplication
- Comprehensive audit logging
- Processing metrics
- User tracking

### 🔷 Tier 3: Exports & Reports
- GSTR-1 export (B2B, B2C, HSN)
- GSTR-3B monthly summary
- Operational reports (5 types)
- Master data auto-learning
- Batch processing
- Quick statistics

**See [docs/main/README.md](docs/main/README.md) for complete feature documentation.**

---

## 📖 Documentation

### Essential Guides
- **[QUICK_START.md](QUICK_START.md)** - Start here! (5-minute setup)
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Migrating from old location
- **[DIRECTORY_TREE.md](DIRECTORY_TREE.md)** - Complete file tree

### Main Documentation
- **[docs/main/README.md](docs/main/README.md)** - Complete documentation
- **[docs/main/ARCHITECTURE.md](docs/main/ARCHITECTURE.md)** - System architecture
- **[docs/main/PROJECT_SUMMARY.md](docs/main/PROJECT_SUMMARY.md)** - Project overview
- **[docs/main/HARDCODING_ANALYSIS.md](docs/main/HARDCODING_ANALYSIS.md)** - Configuration best practices

### Setup Guides
- **[docs/guides/SETUP_GUIDE.md](docs/guides/SETUP_GUIDE.md)** - Detailed setup
- **[docs/guides/CREDENTIALS_GUIDE.md](docs/guides/CREDENTIALS_GUIDE.md)** - API keys
- **[docs/guides/USER_MANUAL.md](docs/guides/USER_MANUAL.md)** - User guide

### Technical Documentation
- **[docs/technical/FILE_INDEX.md](docs/technical/FILE_INDEX.md)** - Complete file index
- **[docs/technical/TIER1_QUICK_START.md](docs/technical/TIER1_QUICK_START.md)** - Tier 1 guide
- **[docs/technical/TIER2_FEATURES.md](docs/technical/TIER2_FEATURES.md)** - Tier 2 guide
- **[docs/technical/TIER3_README.md](docs/technical/TIER3_README.md)** - Tier 3 guide

---

## 🧪 Testing

### Run System Test
```powershell
python tests\integration\test_system.py
```

### Run Tier-Specific Tests
```powershell
python tests\integration\test_tier1.py    # Basic features
python tests\integration\test_tier2.py    # Advanced features
python tests\integration\test_tier3.py    # Exports & reports
```

---

## 🚀 Running the Bot

### Option 1: Python (Recommended)
```powershell
python start_bot.py
```

### Option 2: Batch File (Windows)
```powershell
scripts\start_bot.bat
```

### Option 3: Double-Click
- Double-click `start_bot.py` (if Python is associated)
- Or double-click `scripts\start_bot.bat`

---

## 🔧 Configuration

### Environment Variables (.env)
All configuration is in `.env` file:
- `TELEGRAM_BOT_TOKEN` - Your bot token
- `GOOGLE_API_KEY` - Gemini API key
- `GOOGLE_SHEET_ID` - Your sheet ID
- `GOOGLE_SHEETS_CREDENTIALS_FILE` - Path to credentials.json
- Feature flags for Tier 2/3 features

### Default Paths (Updated)
- **Credentials:** `config/credentials.json`
- **Temp folder:** `temp/`
- **Export folder:** `exports/`

**See [docs/main/HARDCODING_ANALYSIS.md](docs/main/HARDCODING_ANALYSIS.md) for complete configuration guide.**

---

## 📊 Extracted Data

### Invoice Header (41 columns)
- **Tier 1:** 24 GST-compliant fields (invoice, seller, buyer, amounts, GST)
- **Tier 2:** 17 audit fields (timestamps, user tracking, corrections, confidence)

### Line Items (19 columns per item)
- Item details, HSN codes, quantities, rates, GST breakup

### Master Data (Auto-Learning)
- **Customer_Master:** Buyer database with GSTIN tracking
- **HSN_Master:** Product code database with usage stats

---

## 🛠️ Project Structure

### Source Code (`src/`)
Organized by function for easy navigation:
- `bot/` - Telegram interface
- `parsing/` - GST parsing & validation
- `ocr/` - OCR processing
- `sheets/` - Google Sheets operations
- `exports/` - GSTR exports & reports
- `features/` - Advanced Tier 2 features
- `commands/` - Bot command handlers
- `utils/` - Utility functions

### Documentation (`docs/`)
Organized by type:
- `main/` - Core documentation
- `guides/` - Setup & user guides
- `technical/` - Technical details
- `reports/` - Test reports & logs

---

## 💡 Tips

### For Administrators
1. Read [QUICK_START.md](QUICK_START.md) for fast setup
2. Review [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for changes
3. Check [docs/main/ARCHITECTURE.md](docs/main/ARCHITECTURE.md) for technical details

### For End Users
1. Read [docs/guides/USER_MANUAL.md](docs/guides/USER_MANUAL.md)
2. Print [docs/guides/QUICK_REFERENCE.md](docs/guides/QUICK_REFERENCE.md)
3. Use `/start` command in Telegram

### For Developers
1. Explore `src/` folder structure
2. Read [docs/main/HARDCODING_ANALYSIS.md](docs/main/HARDCODING_ANALYSIS.md)
3. Check [docs/technical/FILE_INDEX.md](docs/technical/FILE_INDEX.md)

---

## 🆘 Support

### Documentation
- All docs in `docs/` folder
- Start with `QUICK_START.md`
- Check `MIGRATION_GUIDE.md` for changes

### Testing
- Run `python tests\integration\test_system.py`
- Check test output for diagnostics

### Issues
1. Review error messages
2. Check troubleshooting in docs
3. Verify configuration in `.env`

---

## 🔗 Migration from Old Location

If you're migrating from `C:\Users\clawd bot\Documents\saket worksflow\`:

1. **Read:** [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
2. **Copy:** Your .env and credentials.json
3. **Update:** Paths in .env file
4. **Test:** Run test_system.py
5. **Start:** Run start_bot.py

**Your old installation remains untouched as backup.**

---

## 📞 Quick Links

| Document | Purpose |
|----------|---------|
| [QUICK_START.md](QUICK_START.md) | 5-minute setup |
| [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) | Old → New changes |
| [DIRECTORY_TREE.md](DIRECTORY_TREE.md) | Complete file tree |
| [docs/main/README.md](docs/main/README.md) | Full documentation |
| [docs/guides/SETUP_GUIDE.md](docs/guides/SETUP_GUIDE.md) | Detailed setup |
| [docs/main/ARCHITECTURE.md](docs/main/ARCHITECTURE.md) | System architecture |

---

## ⚙️ System Requirements

- Python 3.8+
- Windows 10/11 (PowerShell)
- Internet connection
- Google Sheets API access
- Telegram Bot API access
- Google Gemini API access

---

## 📝 Version History

### Version 2.0 (February 2026) - Reorganized
- ✅ Professional directory structure
- ✅ Functional code organization
- ✅ Fixed all hardcoding issues
- ✅ Proper Python packaging
- ✅ Updated documentation
- ✅ Complete migration guide

### Version 1.0 (February 2026) - Initial
- All Tier 1, 2, 3 features implemented
- Complete functionality
- Flat file structure

---

## 🎉 Ready to Go!

Follow [QUICK_START.md](QUICK_START.md) to get running in 5 minutes!

---

**Version:** 2.0  
**Last Updated:** February 3, 2026  
**Maintained By:** GST Scanner Team
>>>>>>> aea23172a90b0064e47cce006f3c83edeb4a5012
