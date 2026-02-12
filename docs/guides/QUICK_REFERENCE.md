# GST Scanner Bot - Quick Reference Card

## 🚀 Quick Start
1. Open Telegram → Find bot
2. Send `/start`
3. Send invoice image(s)
4. Type `/done`
5. Wait for confirmation

---

## 💬 Commands

| Command | What it does |
|---------|-------------|
| `/start` | Show welcome message |
| `/done` | Process current invoice |
| `/cancel` | Cancel and clear images |
| `/help` | Show help information |

---

## 📸 Image Guidelines

### ✅ DO
- Clear, well-lit photos
- Capture entire invoice
- Send all pages in order
- Use JPG or PNG format

### ❌ DON'T
- Blurry or dark images
- Cut off parts of invoice
- Mix different invoices
- Use PDF (not supported yet)

---

## 🔢 Process Steps

```
1. SEND IMAGE(S)
   ↓
2. TYPE /done
   ↓
3. WAIT 10-30s
   ↓
4. GET CONFIRMATION
```

---

## ⚠️ Common Issues

### "No images to process"
**Fix:** Send image first, then `/done`

### "Maximum images reached"
**Fix:** Type `/cancel`, then start over

### "Duplicate Invoice"
**Info:** Invoice already processed

### Bot not responding
**Fix:** Check internet, try `/start`

---

## 📊 What Gets Extracted

✓ Invoice number & date  
✓ Seller & buyer details  
✓ GSTIN numbers  
✓ Tax amounts (CGST/SGST/IGST)  
✓ Total invoice value  

---

## 💡 Pro Tips

1. Natural lighting works best
2. Hold phone steady
3. One invoice at a time
4. Wait for confirmation
5. Check Google Sheet after

---

## 🆘 Need Help?

1. Type `/help` in bot
2. Read USER_MANUAL.md
3. Contact administrator

---

## ⏱️ Processing Time

- Single page: 10-15 seconds
- Multi-page: 15-30 seconds

If longer than 1 minute, contact admin.

---

**Print this card for easy reference!**
