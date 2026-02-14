# Order Upload - Quick Reference Card

## 🚀 Quick Start (3 Steps)

### Upload an Order
```
1. Type: /order_upload
2. Send: Photos of order
3. Type: /order_submit
```

That's it! Bot will process and generate PDF.

---

## 📋 Two Upload Types

### 📦 Handwritten Orders
**Use for:** Order notes, handwritten forms  
**Commands:**
1. `/order_upload` - Start session
2. Send photos
3. `/order_submit` - Process

**Bot extracts:**
- Customer info
- Line items (brand, part, color, qty)
- Matches pricing automatically
- Generates clean PDF invoice

---

### 📄 GST Invoices
**Use for:** Printed tax invoices  
**Commands:**
1. `/upload` - Start session
2. Send photos
3. `/done` - Process

**Bot extracts:**
- Invoice number & date
- GST numbers
- Tax breakup (CGST/SGST/IGST)
- Saves to Google Sheets

---

## ⚠️ Common Mistakes

### ❌ Wrong: Mixing Commands
```
/order_upload
[send image]
/done  ← WRONG! Use /order_submit
```

### ✅ Right: Use Matching Commands
```
/order_upload
[send image]
/order_submit  ← CORRECT!
```

---

### ❌ Wrong: No Session Started
```
[send image directly]
/order_submit  ← ERROR: No session!
```

### ✅ Right: Start Session First
```
/order_upload  ← Start here!
[send image]
/order_submit
```

---

## 🔧 Troubleshooting

### "No active order session"
**Fix:** Type `/order_upload` first, THEN send images

### "Cannot submit order"
**Reason:** No images uploaded yet  
**Fix:** Send at least one image before `/order_submit`

### "Please upload at least one page"
**Reason:** Same as above  
**Fix:** Send image(s) before submitting

### Bot not responding?
1. Type `/cancel` to clear state
2. Try `/start` to restart
3. Check you're using correct command type

---

## 📱 Command Reference

| Command | What It Does |
|---------|--------------|
| `/order_upload` | **Start order session** |
| `/order_submit` | **Process order** |
| `/upload` | Start invoice session |
| `/done` | Process invoice |
| `/cancel` | Cancel & start over |
| `/help` | Show detailed help |

---

## 💡 Pro Tips

1. **Multiple Pages?** Send them all before `/order_submit`
2. **Made a Mistake?** Use `/cancel` and start fresh
3. **Unsure?** Type `/help` for full guide
4. **Better Photos = Better Results** Use good lighting
5. **One Order at a Time** Complete one before starting another

---

## 📞 Need Help?

- Type `/help` for detailed instructions
- Use `/cancel` if stuck
- Check you're using the right command pair:
  - Orders: `/order_upload` + `/order_submit`
  - Invoices: `/upload` + `/done`

---

**Remember:** Always start with the RIGHT command for what you're uploading!

📦 Orders → `/order_upload`  
📄 Invoices → `/upload`
