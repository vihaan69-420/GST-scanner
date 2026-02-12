# Epic 2 Rollback Strategy

## Overview

This document outlines the rollback strategy for the Order Upload & Invoice Normalization feature (Epic 2). The feature is designed to be completely rollback-safe with a single feature flag.

## Quick Rollback (Zero Downtime)

### Step 1: Disable Feature Flag

**On Local/Development:**

Edit `.env` file:
```bash
FEATURE_ORDER_UPLOAD_NORMALIZATION=false
```

Then restart the bot:
```bash
./scripts/start_bot.bat
```

**On Production/Cloud Run:**

Update environment variable:
```bash
# Using gcloud CLI
gcloud run services update gst-scanner-bot \
  --update-env-vars FEATURE_ORDER_UPLOAD_NORMALIZATION=false

# Or via Cloud Console:
# 1. Go to Cloud Run service
# 2. Click "Edit & Deploy New Revision"
# 3. Go to "Variables & Secrets" tab
# 4. Set FEATURE_ORDER_UPLOAD_NORMALIZATION=false
# 5. Deploy
```

### Step 2: Verify Rollback

After restarting/redeploying, verify:

1. **Main Menu Check:**
   - Send `/start` to bot
   - Main menu should NOT show "📦 Upload Order" button
   - Only shows: Upload Purchase Invoice, Generate GST Input, Help, Usage & Stats

2. **Command Check:**
   - `/order_submit` should respond with "Order upload feature is not enabled"

3. **GST Scanner Functionality:**
   - Existing GST invoice upload works normally
   - `/upload`, `/done`, `/generate` commands work as before
   - No changes to existing functionality

## What Happens During Rollback

### Immediate Effects

- **Menu Button Removed:** "Upload Order" button disappears from main menu
- **Commands Disabled:** `/order_submit` command returns disabled message
- **Module Not Loaded:** `order_normalization` module not imported
- **No Background Processing:** Order orchestrator not initialized

### Data Preservation

✅ **Safe - Data is Preserved:**
- Google Sheets tabs remain intact (Orders, Order_Line_Items, Customer_Details)
- All processed order data remains accessible
- PDFs in `orders/` folder remain

❌ **Lost - Session Data:**
- In-memory order sessions are cleared on restart
- Users with orders in progress will need to re-upload

## Data Cleanup (Optional)

If you want to completely remove Epic 2 data after rollback:

### 1. Remove Google Sheets Tabs

Manually delete these tabs from Google Sheets:
- `Orders`
- `Order_Line_Items`
- `Customer_Details` (if different from GST scanner's Customer_Master)

**Note:** This is destructive - you'll lose all order history.

### 2. Remove Generated PDFs

```bash
# Local
rm -rf orders/

# Or manually delete the folder
```

### 3. Remove Module (Optional)

```bash
# Only if you want to completely remove the code
rm -rf src/order_normalization/
```

**Note:** This is NOT recommended unless permanently removing the feature.

## Re-enabling the Feature

To re-enable Epic 2 after rollback:

### Step 1: Enable Feature Flag

Edit `.env` or environment variables:
```bash
FEATURE_ORDER_UPLOAD_NORMALIZATION=true
```

### Step 2: Restart Bot

```bash
./scripts/start_bot.bat
```

### Step 3: Verify Re-activation

1. Main menu shows "📦 Upload Order" button
2. `/order_submit` command works
3. Order processing pipeline functional

### Step 4: Recreate Sheets (If Deleted)

If you deleted the Google Sheets tabs, they will be automatically recreated on first order upload.

## Rollback Scenarios

### Scenario 1: Critical Bug in Production

**Problem:** Order processing causing bot crashes

**Solution:**
1. Disable feature flag immediately (< 1 minute)
2. Redeploy/restart
3. Fix bug in code
4. Test in dev environment
5. Re-enable when fixed

**Impact:** 
- Users can't upload orders temporarily
- GST scanner continues working normally
- Zero downtime for GST scanning

### Scenario 2: Pricing Sheet Issues

**Problem:** Pricing matching failing or incorrect

**Solution:**
1. Keep feature enabled
2. Update pricing sheet at configured path
3. Restart bot to reload pricing data

**Alternative:**
- Disable feature temporarily if critical
- Fix pricing sheet
- Re-enable

### Scenario 3: Performance Issues

**Problem:** Order processing too slow, affecting bot responsiveness

**Solution:**
1. Disable feature flag
2. Investigate performance bottleneck
3. Optimize (e.g., caching, async processing)
4. Re-enable after optimization

## Monitoring After Rollback

### Verify No Errors

Check logs for any Epic 2 related errors:
```bash
# Look for import errors or feature references
grep "order_normalization" logs/*.log
grep "FEATURE_ORDER_UPLOAD_NORMALIZATION" logs/*.log
```

Should see:
- No import errors
- Feature flag checks returning False
- No order-related processing

### Verify GST Scanner Health

Test existing functionality:
1. Upload a GST invoice (multi-page)
2. Process with `/done`
3. Check Google Sheets for correct data
4. Generate GSTR-1 export
5. Run `/stats` command

All should work without changes.

## Rollback Checklist

- [ ] Feature flag set to `false`
- [ ] Bot restarted/redeployed
- [ ] Main menu verified (no Order button)
- [ ] `/order_submit` command disabled
- [ ] GST scanner upload works
- [ ] GST scanner processing works
- [ ] Google Sheets writes work
- [ ] GSTR exports work
- [ ] No errors in logs
- [ ] Users notified (if necessary)

## Emergency Contacts

**For Production Issues:**
- Check logs: `logs/` folder or Cloud Logging
- Monitor health: `/health` endpoint
- Bot admin: [Your Contact]

## Rollback SLA

- **Detection Time:** < 5 minutes (monitoring alerts)
- **Rollback Time:** < 1 minute (feature flag flip)
- **Verification Time:** < 2 minutes (automated checks)
- **Total Recovery:** < 10 minutes

## Prevention

### Pre-Deployment Checklist

Before enabling Epic 2 in production:

- [ ] All tests passing (run `python tests/test_epic2_isolation.py`)
- [ ] Dev environment tested end-to-end
- [ ] Pricing sheet validated and accessible
- [ ] Google Sheets permissions verified
- [ ] Dependencies installed (`openpyxl`, `reportlab`)
- [ ] Feature flag OFF by default
- [ ] Rollback procedure documented (this file)
- [ ] Team trained on rollback process

### Gradual Rollout

Recommended approach:

1. **Dev Environment:** Test thoroughly
2. **Staging/UAT:** Enable for internal users
3. **Production - Pilot:** Enable for 1-2 test users
4. **Production - Limited:** Enable for 10% of users
5. **Production - Full:** Enable for all users

At each stage, monitor for 24-48 hours before proceeding.

## Rollback History

Document all rollbacks here:

| Date | Reason | Duration | Resolution |
|------|--------|----------|------------|
| - | - | - | - |

## Notes

- **Feature Flag Location:** `src/config.py` line ~327
- **Module Location:** `src/order_normalization/`
- **Dependencies:** `openpyxl>=3.1.0`, `reportlab>=4.0.0`
- **Google Sheets Tabs:** Orders, Order_Line_Items, Customer_Details
- **Commands:** `/order_submit`
- **Callbacks:** `menu_order_upload`

---

**Last Updated:** 2026-02-06  
**Document Version:** 1.0  
**Feature:** Epic 2 - Order Upload & Normalization
