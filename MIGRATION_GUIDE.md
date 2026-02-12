# Migration Guide: saket worksflow → GST-scanner

**From:** `C:\Users\clawd bot\Documents\saket worksflow\`  
**To:** `C:\Users\clawd bot\Documents\GST-scanner\`  
**Migration Date:** February 3, 2026  
**Version:** 1.0 → 2.0 (Reorganized)

---

## What Changed?

### Directory Structure

#### Before (Flat Structure)
```
saket worksflow/
├── (all 80+ files in root directory)
└── Sample Invoices/
```

#### After (Organized Structure)
```
GST-scanner/
├── src/           # Source code organized by function
├── docs/          # Documentation organized by type
├── tests/         # Tests organized by purpose
├── scripts/       # Utility scripts
├── config/        # Configuration files
├── temp/          # Temporary files
└── exports/       # Export outputs
```

### Source Code Organization

| Module | Old Location | New Location |
|--------|--------------|--------------|
| Main Bot | `telegram_bot.py` | `src/bot/telegram_bot.py` |
| OCR Engine | `ocr_engine.py` | `src/ocr/ocr_engine.py` |
| GST Parser | `gst_parser.py` | `src/parsing/gst_parser.py` |
| Line Items | `line_item_extractor.py` | `src/parsing/line_item_extractor.py` |
| Validator | `gst_validator.py` | `src/parsing/gst_validator.py` |
| Sheets Manager | `sheets_manager.py` | `src/sheets/sheets_manager.py` |
| Config | `config.py` | `src/config.py` |
| Tier 2 Features | (root) | `src/features/` |
| Tier 3 Exports | (root) | `src/exports/` |
| Commands | `tier3_commands.py` | `src/commands/tier3_commands.py` |
| Utilities | (root) | `src/utils/` |

---

## Fixed Issues

### 1. Hardcoded Paths - FIXED ✅
- **telegram_bot.py line 1238**: Changed `'temp_images'` → `config.TEMP_FOLDER`
- **config.py**: Now uses `pathlib.Path` for cross-platform compatibility
- **start_bot.py**: Completely rewritten with proper path handling

### 2. Import System - IMPROVED ✅
- All imports now use proper package structure
- Added `__init__.py` to all packages
- Test files have proper `sys.path` setup
- No more sys.path hacks scattered everywhere

### 3. Configuration - ENHANCED ✅
- `TEMP_FOLDER`: Default changed from `temp_invoices` to `temp`
- `CREDENTIALS_FILE`: Default changed from `credentials.json` to `config/credentials.json`
- All paths use `PROJECT_ROOT` for proper resolution

---

## Migration Steps

### Option A: Fresh Start (Recommended)

1. **Navigate to new location:**
   ```powershell
   cd "C:\Users\clawd bot\Documents\GST-scanner"
   ```

2. **Copy your configuration:**
   ```powershell
   # Copy your .env file
   copy "..\saket worksflow\.env" ".env"
   
   # Copy your credentials
   copy "..\saket worksflow\credentials.json" "config\credentials.json"
   ```

3. **Update .env file:**
   ```env
   # Update these two lines:
   GOOGLE_SHEETS_CREDENTIALS_FILE=config/credentials.json
   TEMP_FOLDER=temp
   ```

4. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Run tests:**
   ```powershell
   python tests\integration\test_system.py
   ```

6. **Start bot:**
   ```powershell
   python start_bot.py
   ```

### Option B: Keep Both Versions

You can run both versions simultaneously:
- Old version: `C:\Users\clawd bot\Documents\saket worksflow\`
- New version: `C:\Users\clawd bot\Documents\GST-scanner\`

Just make sure they use different bot tokens if running simultaneously.

---

## Import Changes

### Python Code

If you have any custom scripts importing from the old structure:

#### Before
```python
from config import TELEGRAM_BOT_TOKEN
from gst_parser import GSTParser
from sheets_manager import SheetsManager
```

#### After
```python
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import TELEGRAM_BOT_TOKEN
from parsing.gst_parser import GSTParser
from sheets.sheets_manager import SheetsManager
```

### Test Files

All test files now include:
```python
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))
```

---

## Configuration Changes

### .env File Updates

#### Required Changes
```env
# OLD:
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
TEMP_FOLDER=temp_invoices

# NEW:
GOOGLE_SHEETS_CREDENTIALS_FILE=config/credentials.json
TEMP_FOLDER=temp
```

#### Optional (defaults work fine)
```env
EXPORT_FOLDER=exports  # unchanged
```

### credentials.json Location

#### Option 1: config/ folder (recommended)
```
GST-scanner/
└── config/
    └── credentials.json
```

Set in `.env`: `GOOGLE_SHEETS_CREDENTIALS_FILE=config/credentials.json`

#### Option 2: Root folder (also works)
```
GST-scanner/
└── credentials.json
```

Set in `.env`: `GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json`

---

## Verification Checklist

After migration, verify:

### 1. Configuration
- [ ] `.env` file exists in root
- [ ] `credentials.json` exists in `config/` folder
- [ ] All tokens and keys are correct

### 2. Structure
- [ ] `src/` folder contains all source code
- [ ] `docs/` folder contains all documentation
- [ ] `tests/` folder contains test files

### 3. Dependencies
- [ ] Run `pip install -r requirements.txt`
- [ ] No errors during installation

### 4. Tests
- [ ] Run `python tests\integration\test_system.py`
- [ ] All critical tests pass

### 5. Bot Startup
- [ ] Run `python start_bot.py`
- [ ] Bot starts without errors
- [ ] Bot responds in Telegram

### 6. Functionality
- [ ] Upload a test invoice
- [ ] Verify data appears in Google Sheet
- [ ] Check all 41 columns populate correctly

---

## Troubleshooting

### "Module not found" Error

**Cause:** Python can't find the src/ directory

**Fix:**
```python
# Make sure you're running from project root
cd "C:\Users\clawd bot\Documents\GST-scanner"
python start_bot.py
```

### "Configuration validation failed"

**Cause:** .env file not found or credentials.json missing

**Fix:**
1. Check `.env` exists in root
2. Check `credentials.json` exists in `config/`
3. Verify paths in `.env` are correct

### "Failed to open Google Sheet"

**Cause:** credentials.json path incorrect

**Fix:**
```env
# In .env file:
GOOGLE_SHEETS_CREDENTIALS_FILE=config/credentials.json
```

---

## Benefits of New Structure

### Organization
- ✅ Clear separation of concerns
- ✅ Easy to navigate
- ✅ Scalable structure

### Maintainability
- ✅ Proper Python package
- ✅ Clean imports
- ✅ No path hacks

### Professional
- ✅ Industry-standard layout
- ✅ Production-ready
- ✅ Easy onboarding

### Fixed Issues
- ✅ No hardcoded paths
- ✅ Cross-platform compatible
- ✅ Consistent configuration

---

## Backward Compatibility

The old installation continues to work independently:
- Keep `saket worksflow` as backup
- Test new `GST-scanner` thoroughly
- Delete old version once verified
- Or keep both for A/B testing

---

## Support

If you encounter issues:
1. Check this migration guide
2. Review `/docs/main/HARDCODING_ANALYSIS.md`
3. Check `/docs/guides/SETUP_GUIDE.md`
4. Run `/tests/integration/test_system.py` for diagnostics

---

**Migration Guide Version:** 1.0  
**Last Updated:** February 3, 2026  
**Status:** Complete
