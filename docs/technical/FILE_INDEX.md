# GST Scanner - File Index (New Structure)

**Location:** `C:\Users\clawd bot\Documents\GST-scanner\`  
**Version:** 2.0 (Reorganized Structure)  
**Last Updated:** February 3, 2026

---

## Directory Structure Overview

```
GST-scanner/
├── src/               # Application source code (23 files)
├── docs/              # Documentation (35 files)
├── tests/             # Test suite (13 files)
├── scripts/           # Utility scripts (6 files)
├── config/            # Configuration files
├── temp/              # Temporary files (auto-created)
├── exports/           # Export outputs (auto-created)
└── Root files         # Essential files (7 files)
```

---

## Source Code (src/)

### src/bot/ - Telegram Bot Interface
- `telegram_bot.py` (1,400 lines) - Main bot with menu system, session management, all commands

### src/parsing/ - GST Parsing & Validation
- `gst_parser.py` (319 lines) - GST data extraction with Gemini 2.5 Flash
- `line_item_extractor.py` (210 lines) - Line item extraction
- `gst_validator.py` (280 lines) - GST validation engine

### src/ocr/ - OCR Processing
- `ocr_engine.py` (120 lines) - OCR with Gemini 2.5 Flash Vision

### src/sheets/ - Google Sheets Integration
- `sheets_manager.py` (988 lines) - Complete sheets operations, 5 sheets management

### src/exports/ - GSTR Exports & Reports
- `gstr1_exporter.py` (636 lines) - GSTR-1 B2B, B2C, HSN exports
- `gstr3b_generator.py` (376 lines) - GSTR-3B monthly summary
- `operational_reports.py` (499 lines) - 5 operational report types
- `export_gstr1.py` (161 lines) - Standalone GSTR-1 CLI
- `export_gstr3b.py` (135 lines) - Standalone GSTR-3B CLI
- `generate_reports.py` (278 lines) - Standalone reports CLI

### src/features/ - Advanced Features (Tier 2)
- `confidence_scorer.py` (195 lines) - AI confidence scoring
- `correction_manager.py` (258 lines) - Manual corrections interface
- `dedup_manager.py` (142 lines) - Fingerprint-based deduplication
- `audit_logger.py` (129 lines) - Audit trail generation

### src/commands/ - Command Handlers
- `tier3_commands.py` (511 lines) - Tier 3 command handlers

### src/utils/ - Utilities
- `batch_processor.py` (418 lines) - Batch processing engine
- `send_telegram_update.py` (88 lines) - Telegram notifications
- `list_models.py` (46 lines) - List available AI models

### src/ - Configuration
- `config.py` (178 lines) - Application configuration with path handling

**Total:** 23 source files

---

## Documentation (docs/)

### docs/main/ - Core Documentation (5 files)
- `README.md` - Main documentation (337 lines)
- `ARCHITECTURE.md` - System architecture (340 lines)
- `PROJECT_SUMMARY.md` - Complete overview (642 lines)
- `HARDCODING_ANALYSIS.md` - Configuration analysis (NEW, 389 lines)
- `DOCUMENTATION_UPDATE_LOG.md` - Update log (NEW, 243 lines)

### docs/guides/ - User & Setup Guides (5 files)
- `SETUP_GUIDE.md` - Detailed setup (350 lines)
- `CREDENTIALS_GUIDE.md` - API keys guide (147 lines)
- `USER_MANUAL.md` - End user guide
- `QUICK_REFERENCE.md` - Quick command reference
- `GETTING_STARTED.md` - Beginner's guide

### docs/technical/ - Technical Documentation (11 files)
- `TIER1_QUICK_START.md` - Tier 1 guide
- `TIER1_IMPLEMENTATION_SUMMARY.md` - Tier 1 details
- `TIER2_FEATURES.md` - Tier 2 features
- `TIER2_QUICKSTART.md` - Tier 2 quickstart
- `TIER2_IMPLEMENTATION_SUMMARY.md` - Tier 2 details
- `TIER3_README.md` - Tier 3 guide
- `TIER3_QUICKREF.md` - Tier 3 reference
- `MENU_SYSTEM_COMPLETE.md` - Menu system docs
- `TESTING_INSTRUCTIONS.md` - Testing guide
- `PERFORMANCE_ANALYSIS.md` - Performance metrics
- `FILE_INDEX.md` - This file

### docs/reports/ - Test Reports & Fix Logs (14 files)
- `B6580_TEST_REPORT.md` - Test report
- `MENU_SYSTEM_TEST_REPORT.md` - Menu tests
- `TIER2_VALIDATION_REPORT.md` - Tier 2 validation
- `TIER3_VALIDATION.md` - Tier 3 validation
- `TELEGRAM_BOT_STATUS.md` - Bot status
- `FIX_VERIFICATION.md` - Fix verification
- `COLUMN_FIX_SUMMARY.md` - Column fixes
- `COLUMN_ALIGNMENT_FIX.md` - Alignment fixes
- `MASTER_SHEETS_FIX.md` - Master sheets fixes
- `SHEET_STRUCTURE_FIX.md` - Structure fixes
- `GSTR1_FIX.md` - GSTR1 fixes
- `JPG_FILE_FIX.md` - JPG fixes
- `MARKDOWN_FIX.md` - Markdown fixes
- `MENU_SYSTEM_QUICK_TEST.md` - Quick tests

**Total:** 35 documentation files

---

## Tests (tests/)

### tests/unit/ - Unit Tests (2 files)
- `test_validation.py` - Validation unit tests
- `test_simple.py` - Simple component tests

### tests/integration/ - Integration Tests (11 files)
- `test_system.py` - MAIN SYSTEM TEST (primary test)
- `test_tier1.py` - Tier 1 integration test
- `test_tier2.py` - Tier 2 features test
- `test_tier3.py` - Tier 3 exports test
- `test_full_pipeline.py` - Complete pipeline test
- `test_menu_system.py` - Menu system test
- `test_b6580_invoice.py` - Real invoice test
- `test_real_invoice.py` - Real invoice test
- `test_master_sheets.py` - Master data test
- `validate_all_samples.py` - Bulk validation
- `validate_tier2.py` - Tier 2 validation

**Total:** 13 test files

---

## Scripts (scripts/)

### scripts/ - Deployment Scripts (2 files)
- `start_bot.bat` - Windows launcher (updated paths)
- `run_tests.bat` - Windows test runner (updated paths)

### scripts/maintenance/ - Maintenance Tools (2 files)
- `check_garbage.py` - Check for sheet garbage data
- `cleanup_garbage.py` - Clean garbage from sheets

**Total:** 4 script files

---

## Configuration (config/)

- `.env.example` - Example environment configuration (updated paths)
- `credentials.json` - Google Sheets service account (user adds this)

---

## Root Files

- `README.md` - Main entry point documentation
- `requirements.txt` - Python dependencies
- `requirements-minimal.txt` - Minimal dependencies
- `start_bot.py` - Main launcher (NEW - updated for new structure)
- `.gitignore` - Git ignore rules
- `.env` - Environment variables (user creates from .env.example)
- `credentials.json` - Can also be placed here (alternative to config/)

**Total:** 7 root files

---

## Auto-Created Directories

- `temp/` - Temporary invoice images (created automatically)
- `exports/` - Generated reports and exports (created automatically)

---

## Key Changes from Old Structure

### Import Path Changes
```python
# OLD (saket worksflow):
from config import TELEGRAM_BOT_TOKEN
from gst_parser import GSTParser

# NEW (GST-scanner):
from config import TELEGRAM_BOT_TOKEN
from parsing.gst_parser import GSTParser
```

### Path Configuration
- `TEMP_FOLDER`: `temp_invoices` → `temp`
- `EXPORT_FOLDER`: `exports` (unchanged)
- `CREDENTIALS_FILE`: `credentials.json` → `config/credentials.json`

### Fixed Hardcoding Issues
1. ✅ telegram_bot.py line 1238 - Fixed hardcoded 'temp_images'
2. ✅ config.py - Uses pathlib.Path for cross-platform compatibility
3. ✅ start_bot.py - Proper PROJECT_ROOT path handling
4. ✅ All test files - Added proper sys.path setup

---

## File Counts Summary

| Category | Count |
|----------|-------|
| Source Code | 23 files |
| Documentation | 35 files |
| Tests | 13 files |
| Scripts | 4 files |
| Config Files | 1 file (.env.example) |
| Root Files | 7 files |
| **Total** | **83 files** |

---

## How to Navigate

### For New Users
1. Start with `/README.md`
2. Follow `/docs/guides/SETUP_GUIDE.md`
3. Run `/start_bot.py`

### For Developers
1. Check `/src/` for all source code
2. Review `/docs/main/ARCHITECTURE.md`
3. Read `/docs/main/HARDCODING_ANALYSIS.md`

### For Testing
1. Run `/tests/integration/test_system.py` (main test)
2. Run tier-specific tests in `/tests/integration/`

### For Exports
1. Use bot commands: `/export_gstr1`, `/export_gstr3b`
2. Or run standalone: `/src/exports/export_gstr1.py`

---

## Migration from Old Location

If migrating from `saket worksflow`:

1. Copy your `.env` file to new location
2. Copy your `credentials.json` to `config/` folder
3. Update paths in `.env` if needed
4. Run tests to verify
5. Start bot with `python start_bot.py`

See `MIGRATION_GUIDE.md` for detailed migration instructions.

---

**Document Version:** 2.0 (New Structure)  
**Last Updated:** February 3, 2026  
**Maintained By:** GST Scanner Team
