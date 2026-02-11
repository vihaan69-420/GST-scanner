# GST Scanner: Usage & Cost Tracking Implementation Summary

**Date:** February 6, 2026  
**Version:** 2.1 (Tracking & Analytics)  
**Status:** Design Complete - Ready for Implementation

---

## Overview

This document summarizes the complete implementation plan for adding **three-level usage tracking**, **cost estimation**, and **operational summaries/reporting** to the GST Scanner Bot.

**Core Guarantee:** ZERO regression to existing invoice processing. All tracking happens AFTER user receives success message as a background action.

---

## What's Being Added

### 1. Three-Level Tracking System

#### Level 1: OCR-Level Tracking (Per Page/API Call)
- Tracks every individual Gemini OCR API call
- Records: tokens, cost, processing time, model used
- Enables per-page cost attribution
- Storage: `logs/ocr_calls.jsonl` (append-only)

#### Level 2: Invoice-Level Tracking (Per Invoice)
- Aggregates all OCR and parsing calls for an invoice
- Records: total tokens, total cost, page count, quality metrics
- Links to individual OCR calls
- Storage: `logs/invoice_usage.jsonl` (append-only)

#### Level 3: Customer-Level Aggregation
- Aggregates all usage for the customer
- Records: total invoices, total costs, averages, outliers
- Single customer for now, multi-tenant ready
- Storage: `logs/customer_usage_summary.json` (single file)

### 2. Configurable Pricing Model

```env
# Pricing is configurable in .env (no code changes when prices change)
GEMINI_OCR_PRICE_PER_1K_TOKENS=0.0001875      # Vision API
GEMINI_PARSING_PRICE_PER_1K_TOKENS=0.000075  # Text API
```

### 3. Summary & Reporting

- **Per-Invoice Summary:** Detailed usage for any invoice
- **Daily Summary:** Aggregated daily usage with outliers
- **Monthly Summary:** Aggregated monthly usage with trends
- **Outlier Detection:** Identifies high-cost/high-token/high-page invoices

### 4. Actual Token Capture

- Captures real token counts from Gemini API responses
- No more estimates - accurate cost tracking
- Configurable via `ENABLE_ACTUAL_TOKEN_CAPTURE=true`

---

## Data Models

### OCR Call Record (Per Page)

```json
{
  "call_id": "ocr_20260206_103045_001",
  "invoice_id": "INV-2024-12345",
  "page_number": 1,
  "timestamp": "2026-02-06T10:30:45.123Z",
  "model_name": "gemini-2.5-flash",
  "prompt_tokens": 1245,
  "output_tokens": 856,
  "total_tokens": 2101,
  "processing_time_ms": 1234,
  "image_size_bytes": 85000,
  "customer_id": "CUST001",
  "telegram_user_id": 7332697107,
  "status": "success"
}
```

### Invoice Usage Record (Per Invoice)

```json
{
  "invoice_id": "INV-2024-12345",
  "customer_id": "CUST001",
  "telegram_user_id": 7332697107,
  "timestamp": "2026-02-06T10:30:45.123Z",
  "page_count": 3,
  "total_ocr_calls": 3,
  "total_parsing_calls": 2,
  "ocr_tokens": {"prompt": 3456, "output": 2345, "total": 5801},
  "parsing_tokens": {"prompt": 1200, "output": 450, "total": 1650},
  "total_tokens": 7451,
  "ocr_cost_usd": 0.001087,
  "parsing_cost_usd": 0.000124,
  "total_cost_usd": 0.001211,
  "processing_time_seconds": 12.5,
  "validation_status": "ok",
  "confidence_avg": 0.92,
  "had_corrections": false,
  "ocr_call_ids": ["ocr_20260206_103045_001", "..."]
}
```

### Customer Usage Summary (Aggregate)

```json
{
  "customer_id": "CUST001",
  "customer_name": "Default Customer",
  "period_start": "2026-02-01T00:00:00Z",
  "period_end": "2026-02-28T23:59:59Z",
  "total_invoices": 245,
  "total_pages": 623,
  "total_tokens": 1580245,
  "total_cost_usd": 257.41,
  "avg_cost_per_invoice": 1.05,
  "avg_pages_per_invoice": 2.54,
  "success_rate": 0.978,
  "max_cost_invoice": "INV-2024-99999"
}
```

### Daily Summary

```json
{
  "date": "2026-02-06",
  "customer_id": "CUST001",
  "invoices_processed": 12,
  "pages_processed": 31,
  "total_tokens": 195234,
  "total_cost_usd": 12.45,
  "success_rate": 1.0,
  "high_cost_invoices": [
    {"invoice_id": "INV-2024-12345", "cost_usd": 3.21, "pages": 8}
  ]
}
```

---

## Cost Calculation Formulas

### OCR Cost (Per Page)
```
ocr_cost_usd = (total_tokens / 1000) × GEMINI_OCR_PRICE_PER_1K_TOKENS
```

### Parsing Cost (Per Invoice)
```
parsing_cost_usd = (total_tokens / 1000) × GEMINI_PARSING_PRICE_PER_1K_TOKENS
```

### Invoice Total Cost
```
total_cost_usd = ocr_cost_usd + parsing_cost_usd
```

### Customer Total Cost
```
customer_total_cost_usd = Σ(invoice.total_cost_usd)
```

---

## Tracking Hooks in Pipeline

### Hook 1: OCR Call Metadata Capture (During Processing)

**Location:** `src/bot/telegram_bot.py` - `done_command()` (line 1115)  
**Timing:** After OCR completes, before user response  
**Action:** Capture lightweight metadata (<1ms overhead)

```python
# After OCR extraction
ocr_text = self.ocr_engine.extract_text_from_images(image_paths)

# Capture metadata (fast, no disk I/O)
session['_ocr_tracking'] = [
    {
        'page_number': idx + 1,
        'image_size_bytes': os.path.getsize(path),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    for idx, path in enumerate(image_paths)
]
```

### Hook 2: Parsing Metadata Capture (During Processing)

**Location:** `src/bot/telegram_bot.py` - `done_command()` (line 1120)  
**Timing:** After parsing completes, before user response  
**Action:** Capture parsing token metadata

```python
# After parsing
result = self.gst_parser.parse_invoice_with_validation(ocr_text)

# Capture parsing metadata
session['_parsing_tracking'] = {
    'header_tokens': {...},
    'line_items_tokens': {...}
}
```

### Hook 3: Background Tracking Task (After User Response)

**Location:** `src/bot/telegram_bot.py` - `_save_invoice_to_sheets()` (line 903)  
**Timing:** AFTER user sees "✅ Success" message  
**Action:** Write all tracking data to disk (background)

```python
# User sees success FIRST
await update.message.reply_text("✅ Invoice saved successfully!")

# THEN track in background (fire-and-forget)
if config.ENABLE_USAGE_TRACKING:
    asyncio.create_task(self._track_invoice_complete_async(user_id, session))

# Clear session
self._clear_user_session(user_id)
```

**Background Task Does:**
1. Write OCR call records to `logs/ocr_calls.jsonl`
2. Write invoice usage record to `logs/invoice_usage.jsonl`
3. Update customer summary in `logs/customer_usage_summary.json`
4. Update daily summary (if enabled)
5. Detect outliers (if enabled)

**Result:** User never waits for tracking. If tracking takes 5 seconds or fails, user doesn't notice.

---

## Feature Flags (.env)

### Master Switch
```env
ENABLE_USAGE_TRACKING=false  # Master switch - disables all tracking
```

### Individual Features
```env
ENABLE_OCR_LEVEL_TRACKING=false       # Per-page tracking
ENABLE_INVOICE_LEVEL_TRACKING=false   # Per-invoice aggregates
ENABLE_CUSTOMER_AGGREGATION=false     # Customer-level summary
ENABLE_SUMMARY_GENERATION=false       # Daily/monthly summaries
ENABLE_OUTLIER_DETECTION=false        # Anomaly detection
ENABLE_ACTUAL_TOKEN_CAPTURE=true      # Capture real tokens from API
```

### Pricing Configuration
```env
GEMINI_OCR_PRICE_PER_1K_TOKENS=0.0001875      # Vision API pricing
GEMINI_PARSING_PRICE_PER_1K_TOKENS=0.000075  # Text API pricing
```

### Customer Identifier (Single Customer)
```env
DEFAULT_CUSTOMER_ID=CUST001
DEFAULT_CUSTOMER_NAME=Default Customer
```

### Outlier Thresholds
```env
OUTLIER_COST_ZSCORE_THRESHOLD=2.0       # Cost outliers (std devs)
OUTLIER_PAGE_COUNT_THRESHOLD=10         # High page count threshold
OUTLIER_TOKEN_PERCENTILE_THRESHOLD=95   # Top 5% token usage
```

---

## File Changes

### New Files Created

```
logs/
├── ocr_calls.jsonl              # OCR-level tracking
├── invoice_usage.jsonl          # Invoice-level tracking
├── customer_usage_summary.json  # Customer aggregate
├── daily_summaries.jsonl        # Daily rollups
└── monthly_summaries.jsonl      # Monthly rollups

src/utils/
├── usage_tracker.py             # Three-level tracking logic
├── summary_generator.py         # Summary/reporting logic
├── outlier_detector.py          # Outlier detection
└── pricing_calculator.py        # Cost calculation
```

### Files Modified

```
.env                             # Add tracking flags + pricing
src/config.py                    # Load new config variables
src/bot/telegram_bot.py          # Add tracking hooks + background tasks
src/ocr/ocr_engine.py            # Capture token usage from API
src/parsing/gst_parser.py        # Capture token usage from API
```

**Total New Files:** 9  
**Total Modified Files:** 5

---

## Summary & Reporting Features

### 1. Per-Invoice Summary

**Command:** `/invoice_stats INV-2024-12345`

**Output:**
```
📊 Invoice: INV-2024-12345

Processing:
• Pages: 3
• Processing Time: 12.5s
• Validation: ✅ OK

Usage:
• Total Tokens: 7,451
• OCR Tokens: 5,801 (3 calls)
• Parsing Tokens: 1,650 (2 calls)

Cost:
• OCR: $0.0011
• Parsing: $0.0001
• Total: $0.0012
```

### 2. Daily Summary

**Command:** `/daily_stats 2026-02-06`

**Output:**
```
📊 Daily Summary: February 6, 2026

Invoices: 12
Pages: 31
Tokens: 195,234
Cost: $12.45

Quality:
• Success Rate: 100%
• Avg Confidence: 91%

⚠️ Outliers Detected:
• INV-2024-12345: $3.21 (8 pages)
• INV-2024-12346: 45,678 tokens (12 pages)
```

### 3. Monthly Summary

**Command:** `/monthly_stats 2026-02`

**Output:**
```
📊 Monthly Summary: February 2026

Invoices: 245
Pages: 623
Total Cost: $257.41

Averages:
• Per Day: $9.19
• Per Invoice: $1.05
• Pages Per Invoice: 2.54

Top 3 Expensive Invoices:
1. INV-2024-99999: $5.67 (15 pages)
2. INV-2024-88888: $4.32 (12 pages)
3. INV-2024-77777: $3.89 (10 pages)
```

### 4. Outlier Detection

**Purpose:** Identify anomalous invoices for investigation

**Methods:**
- **Statistical:** Z-score > 2.0 (2 std devs above mean)
- **Absolute:** Page count > 10
- **Percentile:** Top 5% token usage

**Output:**
```
⚠️ Outlier Alert: INV-2024-12345

Cost: $3.21 (2.5σ above average)
Pages: 8
Tokens: 45,678
Tokens/Page: 5,710 (average: 3,200)

Possible Reasons:
• Multi-page invoice with complex layouts
• Poor image quality requiring more tokens
• Dense content with many line items
```

---

## Rollback Strategy

### Instant Rollback (No Code Changes)

**Set in .env:**
```env
ENABLE_USAGE_TRACKING=false
```

**Result:**
- All tracking code skipped
- Bot behaves exactly as before
- Zero performance impact
- No restart needed (takes effect on next bot start)

### Incremental Rollback (Disable Individual Features)

```env
# Keep basic tracking, disable summaries
ENABLE_USAGE_TRACKING=true
ENABLE_OCR_LEVEL_TRACKING=true
ENABLE_INVOICE_LEVEL_TRACKING=true
ENABLE_CUSTOMER_AGGREGATION=false     # Disable this
ENABLE_SUMMARY_GENERATION=false       # Disable this
ENABLE_OUTLIER_DETECTION=false        # Disable this
```

### Git Rollback (Code-Level)

```bash
# Revert to baseline before tracking
git checkout v2.0-baseline-before-tracking

# Or revert specific phase
git revert <commit-hash>
```

---

## Testing Strategy

### 1. Baseline Tests (Before Implementation)

**Purpose:** Establish golden reference outputs

**Process:**
1. Set `ENABLE_USAGE_TRACKING=false`
2. Process 3 test invoices
3. Capture: OCR text, invoice data, line items, sheet rows
4. Save to `tests/baselines/invoice_X_baseline.json`

### 2. Non-Regression Tests (After Each Phase)

**Purpose:** Verify new code doesn't change existing outputs

**Tests:**
- With tracking OFF → outputs match baseline exactly
- With tracking ON → outputs STILL match baseline exactly
- Processing time is identical

**Failure = Immediate rollback**

### 3. Feature-Specific Tests

**Tests:**
- OCR call tracking records correct tokens
- Invoice usage aggregates correctly
- Customer summary calculates totals accurately
- Daily/monthly summaries match invoice records
- Outlier detection identifies anomalies
- Cost calculations match expected values

### 4. Performance Tests

**Tests:**
- User-facing processing time unchanged
- Background tasks complete within 2 seconds
- No memory leaks from background tasks
- Tracking failures don't crash bot

---

## Implementation Phases

### Phase 1: Infrastructure Setup
- Add feature flags to .env
- Create usage_tracker.py
- Create pricing_calculator.py
- Initialize tracking in bot

### Phase 2: OCR & Parsing Tracking
- Capture OCR metadata (lightweight)
- Capture parsing metadata
- Modify OCR/parsing engines to return token usage

### Phase 3: Background Tracking
- Create background task for invoice tracking
- Write OCR call records
- Write invoice usage records
- Update customer summary

### Phase 4: Summaries & Reporting
- Create summary_generator.py
- Create outlier_detector.py
- Implement daily/monthly summary logic
- Add summary commands to bot

### Phase 5: UI & Stats Commands
- Implement /invoice_stats command
- Implement /daily_stats command
- Implement /monthly_stats command
- Update Usage & Stats menu

---

## Success Criteria

### Functional
- ✅ All three tracking levels working
- ✅ Actual tokens captured from API
- ✅ Costs calculated accurately from config
- ✅ Summaries generated correctly
- ✅ Outliers detected and reported

### Non-Functional
- ✅ Zero user-facing performance impact
- ✅ All tests pass (baseline + regression)
- ✅ Background tasks complete within 2s
- ✅ Tracking failures don't break invoice processing
- ✅ Feature flags enable instant rollback

### Quality
- ✅ No hardcoded pricing (configurable)
- ✅ Multi-tenant ready (customer_id field exists)
- ✅ Reproducible summaries (from raw data)
- ✅ Complete audit trail (every API call logged)

---

## Out of Scope (Explicitly)

- ❌ Multi-tenant subscriptions
- ❌ Plan enforcement or usage limits
- ❌ Billing or payment processing
- ❌ User authentication beyond Telegram
- ❌ Real-time usage alerts
- ❌ Cost optimization recommendations
- ❌ Historical data migration

---

## Future Enhancements (Post-Launch)

### Phase 2 (Multi-Tenant)
- Add customer onboarding flow
- Implement per-customer pricing tiers
- Add plan enforcement logic
- Support multiple customer_id values

### Phase 3 (Billing)
- Generate monthly invoices from usage data
- Integrate payment gateway
- Implement usage alerts
- Add cost optimization tips

### Phase 4 (Advanced Analytics)
- Cost prediction models
- Usage trend analysis
- Anomaly detection improvements
- Performance optimization insights

---

## Contact & Support

**Implementation Lead:** AI Assistant  
**Review Required:** System Owner  
**Documentation:** This file + Plan file  
**Questions:** Review `TRACKING_IMPLEMENTATION_PLAN.md`

---

## Approval Checklist

Before implementation begins:

- [ ] Review data models - approved?
- [ ] Review tracking hooks - approved?
- [ ] Review cost formulas - approved?
- [ ] Review feature flags - approved?
- [ ] Review rollback strategy - approved?
- [ ] Review testing strategy - approved?
- [ ] Baseline tests captured?
- [ ] Git tagged: `v2.0-baseline-before-tracking`?

**Approved By:** _______________  
**Date:** _______________

---

**END OF SUMMARY**
