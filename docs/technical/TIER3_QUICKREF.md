# Tier 3 Quick Reference Card

## 📋 New Telegram Bot Commands

### Batch Processing
```
/next       Save current invoice and start collecting next one
            Use when processing multiple invoices in one session
            
Example workflow:
1. Send invoice 1 images → /next
2. Send invoice 2 images → /next
3. Send invoice 3 images → /done (processes all 3)
```

### GSTR-1 Export
```
/export_gstr1    Generate GSTR-1 CSV exports
                 Interactive prompts for:
                 - Month (1-12)
                 - Year (e.g., 2026)
                 - Export type (B2B, B2C, HSN, or All)
                 
Outputs: CSV files ready for GST portal upload
```

### GSTR-3B Summary
```
/export_gstr3b   Generate GSTR-3B summary
                 Interactive prompts for:
                 - Month (1-12)
                 - Year (e.g., 2026)
                 
Outputs: JSON summary + formatted text report
```

### Operational Reports
```
/reports    Generate operational reports
            Options:
            1. Processing Statistics (all invoices)
            2. GST Summary (monthly)
            3. Duplicate Attempts
            4. Correction Analysis
            5. Comprehensive Report (all of above)
```

### Quick Statistics
```
/stats      Show quick processing statistics
            Displays: Invoice counts, validation status breakdown
```

---

## 🖥️ Standalone Scripts

### GSTR-1 Export Script
```bash
python export_gstr1.py
```
Interactive prompts guide you through:
- Period selection
- Export type selection
- Output directory

**Outputs:**
- `B2B_Invoices_YYYY_MM.csv`
- `B2C_Small_YYYY_MM.csv`
- `HSN_Summary_YYYY_MM.csv`
- `Export_Report_YYYY_MM.txt`

### GSTR-3B Export Script
```bash
python export_gstr3b.py
```
Interactive prompts for period selection.

**Outputs:**
- `GSTR3B_Summary_YYYY_MM.json`
- `GSTR3B_Report_YYYY_MM.txt`

### Reports Generator
```bash
python generate_reports.py
```
Interactive menu for report type and period.

**Outputs:** JSON and/or text reports

---

## 📁 Export File Locations

All exports saved in `exports/` directory:

```
exports/
├── GSTR1_2026_01/          # GSTR-1 exports by period
│   ├── B2B_Invoices_2026_01.csv
│   ├── B2C_Small_2026_01.csv
│   ├── HSN_Summary_2026_01.csv
│   └── Export_Report_2026_01.txt
│
├── GSTR3B_2026_01/         # GSTR-3B summaries by period
│   ├── GSTR3B_Summary_2026_01.json
│   └── GSTR3B_Report_2026_01.txt
│
└── Reports_2026_01/        # Operational reports by period
    ├── Operational_Reports_2026_01.json
    └── Operational_Report_2026_01.txt
```

---

## 🔧 Testing

Run comprehensive test suite:
```bash
python test_tier3.py
```

Tests validate:
- GSTR-1 exports (B2B, B2C, HSN)
- GSTR-3B generation
- Master data operations
- Operational reports
- Data aggregation logic

---

## 📊 Master Data Sheets

### Automatically Created Google Sheets Tabs

**Customer_Master**
- Tracks buyer GST numbers
- Auto-populated from invoices
- Advisory data for consistency

**HSN_Master**
- Tracks HSN/SAC codes
- Auto-populated from line items
- Stores descriptions and default rates

**Duplicate_Attempts**
- Logs duplicate invoice attempts
- Tracks user behavior
- Audit trail for compliance

---

## 💡 Quick Tips

### Batch Processing
- Use `/next` between different invoices
- Use `/done` to process the entire batch
- Each invoice processes independently
- Failures don't block other invoices

### Exports
- Export by month for GST return filing
- Generated CSVs import directly to GST portal
- Always review Export_Report file first
- ERROR invoices listed but not excluded

### Reports
- `/stats` for quick overview
- `/reports` for detailed analysis
- Use monthly reports to track trends
- Check duplicate attempts for data quality

### Master Data
- Updates automatically after processing
- Never overrides invoice data silently
- Helps with consistency over time
- No manual maintenance needed

---

## 🚨 Common Issues

**Q: Export shows "No invoices found"**
A: Check that Invoice_Date format is DD/MM/YYYY and invoices exist for that period

**Q: CSV won't import to GST portal**
A: Verify all required columns present and format matches official schema

**Q: Master data sheet not found**
A: Sheets auto-create on first use. Process an invoice to trigger creation.

**Q: Batch processing fails**
A: Check individual errors in batch report. One failure doesn't affect others.

---

## 📖 Documentation

- **TIER3_README.md** - Complete feature documentation
- **TIER3_VALIDATION.md** - Testing and validation report
- **README.md** - Main project documentation

---

## ✅ Checklist: First Time Use

- [ ] Run `python test_tier3.py` to validate installation
- [ ] Process a test invoice to trigger master sheet creation
- [ ] Try `/next` and batch workflow with 2-3 test invoices
- [ ] Export GSTR-1 for current month (check empty is OK)
- [ ] Generate GSTR-3B summary
- [ ] Run `/stats` to see processing overview
- [ ] Check `exports/` folder for generated files

---

*Quick Reference v3.0 - All commands validated and operational*
