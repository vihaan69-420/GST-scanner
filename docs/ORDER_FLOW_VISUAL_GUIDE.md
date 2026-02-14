# Order Upload Flow - Visual Guide

## 🎯 The Complete Flow (Fixed!)

```
┌─────────────────────────────────────────────────────┐
│          START HERE: User Types Command             │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   /order_upload      │
              └──────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Bot Response:                                       │
│  📦 Order Upload Mode Activated!                    │
│                                                      │
│  Instructions:                                       │
│  1. Send me photos of handwritten order notes       │
│  2. You can send multiple pages if needed           │
│  3. Type /order_submit when done                    │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  User Sends Photo    │
              └──────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Bot Response:                                       │
│  ✅ Page 1 received!                                │
│                                                      │
│  Send more pages or type /order_submit to process.  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │  More pages to send?          │
         └───────────────────────────────┘
                 │               │
            Yes  │               │  No
                 │               │
                 ▼               ▼
         ┌──────────┐    ┌──────────────┐
         │Send More │    │ /order_submit│
         │  Photos  │    └──────────────┘
         └──────────┘            │
                 │               │
                 └───────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Bot Response:                                       │
│  ✅ Order submitted!                                │
│                                                      │
│  📄 Order ID: ORD_20260207_143022                   │
│  📄 Pages: 1                                        │
│                                                      │
│  Processing your order... This may take a moment.   │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Bot Processing...   │
              │  (30-60 seconds)     │
              └──────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Bot Sends Results:                                  │
│                                                      │
│  📄 Clean PDF Invoice                               │
│  📊 Item Summary                                    │
│  💰 Pricing Information                             │
│  ✅ Match Confidence Scores                         │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
                   ┌─────────┐
                   │  DONE!  │
                   └─────────┘
```

---

## ❌ What NOT to Do (Common Mistakes)

### Mistake #1: No Command First
```
❌ WRONG FLOW:

[Send Photo Directly]
      │
      ▼
❌ No session created!
      │
      ▼
/order_submit
      │
      ▼
❌ ERROR: No active order session
```

**Fix:** Always type `/order_upload` FIRST!

---

### Mistake #2: Wrong Submit Command
```
❌ WRONG FLOW:

/order_upload
      │
      ▼
[Send Photos]
      │
      ▼
/done  ← WRONG COMMAND!
      │
      ▼
❌ ERROR: Command for invoices, not orders
```

**Fix:** Use `/order_submit` for orders (not `/done`)

---

### Mistake #3: Using Invoice Commands
```
❌ WRONG FLOW:

/upload  ← Invoice command!
      │
      ▼
[Send Photos]
      │
      ▼
/order_submit  ← Order command!
      │
      ▼
❌ ERROR: Mixing two different flows
```

**Fix:** Pick ONE flow:
- Orders: `/order_upload` → `/order_submit`
- Invoices: `/upload` → `/done`

---

## 🔄 Comparison: Orders vs Invoices

```
┌─────────────────────────────────┬─────────────────────────────────┐
│        📦 ORDER UPLOAD          │       📄 INVOICE UPLOAD         │
├─────────────────────────────────┼─────────────────────────────────┤
│                                 │                                 │
│   /order_upload                 │   /upload                       │
│         │                       │         │                       │
│         ▼                       │         ▼                       │
│   [Send Photos]                 │   [Send Photos]                 │
│         │                       │         │                       │
│         ▼                       │         ▼                       │
│   /order_submit                 │   /done                         │
│         │                       │         │                       │
│         ▼                       │         ▼                       │
│   PDF Generated                 │   Data to Sheets                │
│                                 │                                 │
└─────────────────────────────────┴─────────────────────────────────┘
```

**Key Difference:**
- **Orders:** Handwritten notes → Clean PDF invoice
- **Invoices:** Printed invoices → Google Sheets data

---

## 🆘 Error Handling Flow

```
User sends /order_submit without session
      │
      ▼
┌─────────────────────────────────────────────┐
│  ❌ No Active Order Session                 │
│                                             │
│  You need to start an order upload session  │
│  first!                                     │
│                                             │
│  How to upload an order:                    │
│  1. Type /order_upload                      │
│  2. Send your order photos                  │
│  3. Type /order_submit                      │
└─────────────────────────────────────────────┘
      │
      ▼
User reads error message
      │
      ▼
User types /order_upload
      │
      ▼
✅ Session created - Flow continues normally
```

---

## 🎓 Decision Tree: Which Command to Use?

```
                    START
                      │
                      ▼
        ┌─────────────────────────────┐
        │  What are you uploading?    │
        └─────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
         ▼                         ▼
  ┌────────────┐          ┌─────────────────┐
  │ Handwritten│          │ Printed Invoice │
  │   Order    │          │ (has GST info)  │
  └────────────┘          └─────────────────┘
         │                         │
         ▼                         ▼
  /order_upload             /upload
         │                         │
         ▼                         ▼
  [Send Photos]            [Send Photos]
         │                         │
         ▼                         ▼
  /order_submit             /done
         │                         │
         ▼                         ▼
    PDF File              Google Sheets
```

---

## 📱 Bot Menu Structure

```
Main Menu
├── 📤 Upload Invoice
│   ├── Single Invoice → /upload → /done
│   ├── Batch Upload
│   └── Upload Document
│
├── 📦 Upload Order [NEW!]
│   └── /order_upload → [photos] → /order_submit
│
├── 📊 Generate GST Input
│   ├── GSTR-1 Export
│   ├── GSTR-3B Summary
│   └── Reports
│
├── ❓ Help
│   └── /help
│
└── 📈 Usage & Stats
```

---

## ⏱️ Timing Expectations

```
/order_upload
    │
    ├─ Instant: Session created
    │
    ▼
[Send Photo]
    │
    ├─ 2-5 sec: Photo uploaded
    │
    ▼
/order_submit
    │
    ├─ Instant: Validation
    │
    ▼
Processing
    │
    ├─ 30-60 sec: OCR + Extraction
    ├─ 10-15 sec: Normalization
    ├─ 5-10 sec: Pricing Match
    ├─ 5-10 sec: PDF Generation
    │
    ▼
Results Sent
    │
    └─ Total: 60-120 seconds
```

---

## 🎯 Success Checklist

Before `/order_submit`:
- [ ] Typed `/order_upload` first
- [ ] Got "Order Upload Mode Activated" message
- [ ] Sent at least one photo
- [ ] Got "Page X received" confirmation

Ready to submit:
- [ ] All pages sent
- [ ] Photos are clear
- [ ] Ready to wait 1-2 minutes for processing

After submission:
- [ ] Got "Order submitted!" confirmation
- [ ] Received Order ID
- [ ] Waiting for results
- [ ] PDF file delivered

---

**Remember: The magic happens in the right sequence!**

🔹 Start: `/order_upload`  
🔹 Middle: Send photos  
🔹 End: `/order_submit`  
🔹 Result: Beautiful PDF! ✨
