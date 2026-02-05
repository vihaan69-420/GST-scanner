# GST Scanner Bot - User Manual

**For End Users**

This manual is for people who will be using the GST Scanner Bot to process invoices via Telegram.

---

## 📱 Getting Started

### Step 1: Find the Bot
1. Open Telegram on your phone or computer
2. Search for the bot name (ask your administrator for the bot username)
3. Tap/click on the bot to open the chat

### Step 2: Start the Bot
1. Tap the **START** button or type `/start`
2. You'll see a welcome message explaining how to use the bot

---

## 📸 Processing an Invoice

### Simple Process (3 Steps)

1. **Send** → Send invoice image(s) to the bot
2. **Done** → Type `/done` when all pages are sent
3. **Wait** → Bot processes and confirms

### Detailed Instructions

#### For Single-Page Invoices

1. **Take a photo** of the invoice OR **forward** existing image
2. **Send the image** to the bot
3. Bot confirms: "✅ Page 1 received!"
4. **Type `/done`**
5. Wait for processing (10-30 seconds)
6. Receive confirmation with invoice details

#### For Multi-Page Invoices

1. **Send the first page** to the bot
   - Bot confirms: "✅ Page 1 received!"
2. **Send the second page**
   - Bot confirms: "✅ Page 2 received!"
3. **Continue** for all pages
4. **Type `/done`** when all pages are sent
5. Wait for processing (15-30 seconds)
6. Receive confirmation with invoice details

---

## 📋 Commands Reference

### `/start`
Shows welcome message and instructions.

**Example:**
```
/start
```

### `/done`
Process all images you've sent as one invoice.

**Example:**
```
[You send 2 images]
/done
```

### `/cancel`
Cancel current invoice and clear all images.

**Example:**
```
[You send an image by mistake]
/cancel
```

### `/help`
Show help information and tips.

**Example:**
```
/help
```

---

## ✅ What the Bot Extracts

The bot automatically extracts:

### Invoice Information
- Invoice number
- Invoice date
- Invoice type

### Seller Details
- Seller name
- Seller GSTIN
- Seller state code

### Buyer Details
- Buyer name
- Buyer GSTIN
- Buyer state code

### Tax Information
- Total taxable amount
- Total GST amount
- CGST, SGST, or IGST breakdown

### Additional Info
- Place of supply
- E-way bill number
- Transporter details

---

## 📊 Understanding the Results

After processing, you'll receive a summary like this:

```
✅ Invoice Processed Successfully!

📄 Invoice Details:
• Invoice No: 2025/JW/303
• Date: 28/11/2025
• Seller: KESARI AUTOMOTIVES
• Buyer: SAKET MOTORCYCLES

💰 GST Summary:
• Invoice Value: ₹148.00
• Taxable Amount: ₹125.32
• Total GST: ₹22.56
  - CGST: ₹11.28
  - SGST: ₹11.28

✨ Data has been appended to your Google Sheet!
```

This means:
- ✅ Invoice was processed successfully
- ✅ Data was extracted correctly
- ✅ Information was added to the spreadsheet

---

## 💡 Tips for Best Results

### Image Quality

✅ **DO:**
- Take clear, well-lit photos
- Ensure all text is readable
- Capture the entire invoice in frame
- Use good lighting (natural light is best)
- Hold phone steady

❌ **DON'T:**
- Send blurry or dark images
- Cut off parts of the invoice
- Use extreme angles
- Send heavily compressed images

### Multi-Page Invoices

✅ **DO:**
- Send pages in order (page 1, then page 2, etc.)
- Send all pages before typing `/done`
- Make sure each page is a separate image

❌ **DON'T:**
- Mix pages from different invoices
- Send pages out of order
- Send duplicate pages

### File Formats

✅ **Supported:**
- JPG / JPEG images
- PNG images

❌ **Not Supported (Yet):**
- PDF files (coming soon)
- Other document formats

---

## ⚠️ Common Issues & Solutions

### Issue: Bot doesn't respond

**Possible Causes:**
- Bot is offline
- Your message didn't send

**Solution:**
1. Check your internet connection
2. Try sending `/start` again
3. Contact administrator if issue persists

---

### Issue: "No images to process"

**Cause:** You typed `/done` without sending any images

**Solution:**
1. Send invoice image(s) first
2. Then type `/done`

---

### Issue: "Maximum images reached"

**Cause:** You've sent too many images (limit is 10)

**Solution:**
1. Type `/cancel` to clear
2. Send only the pages of one invoice
3. Type `/done`

---

### Issue: "Duplicate Invoice Detected"

**Cause:** This invoice number already exists in the spreadsheet

**What it means:**
- ✅ Good! Prevents duplicate entries
- ℹ️ This invoice was already processed

**Solution:**
- If it's truly a duplicate: No action needed
- If it's a different invoice with same number: Contact administrator

---

### Issue: Processing takes too long

**Normal Processing Time:**
- Single page: 10-15 seconds
- Multiple pages: 15-30 seconds

**If longer than 1 minute:**
1. Wait a bit more (sometimes APIs are slow)
2. If it fails, you'll get an error message
3. Try again or contact administrator

---

### Issue: Incorrect data extracted

**Possible Causes:**
- Poor image quality
- Unusual invoice format
- Text not clearly visible

**Solution:**
1. Retake photo with better lighting
2. Ensure all text is clearly visible
3. Send clearer images and try again

---

## 🔒 Privacy & Security

### Your Data
- Images are **temporarily stored** during processing
- Images are **automatically deleted** after processing
- Only extracted data is saved to Google Sheet

### Who Can See
- ✅ Authorized users with Google Sheet access
- ❌ No one else can access your data

### Confidentiality
- Bot processes invoices securely
- All communication is encrypted by Telegram
- No data is shared with third parties

---

## 📞 Getting Help

### Self-Help
1. **Type `/help`** in the bot for quick tips
2. **Read this manual** for detailed instructions
3. **Try `/cancel` and start over** if something goes wrong

### Contact Administrator
If you encounter persistent issues:
- Bot not responding
- Repeated processing failures
- Incorrect data extraction
- Access issues

Provide:
- Screenshot of the error (if any)
- Invoice number (if applicable)
- Brief description of the issue

---

## 📝 Example Workflows

### Example 1: Simple Single-Page Invoice

```
You: [Send photo of invoice]

Bot: ✅ Page 1 received!
     Send more pages or type /done to process.

You: /done

Bot: 🔄 Processing 1 page(s)...
     This may take a moment. Please wait.

Bot: 📖 Step 1/3: Extracting text from images...

Bot: 🔍 Step 2/3: Parsing GST invoice data...

Bot: 📊 Step 3/3: Updating Google Sheet...

Bot: ✅ Invoice Processed Successfully!
     
     📄 Invoice Details:
     • Invoice No: 2025/JW/303
     ...
```

---

### Example 2: Multi-Page Invoice

```
You: [Send page 1]

Bot: ✅ Page 1 received!
     Send more pages or type /done to process.

You: [Send page 2]

Bot: ✅ Page 2 received!
     Send more pages or type /done to process.

You: /done

Bot: 🔄 Processing 2 page(s)...
     [Processing steps...]

Bot: ✅ Invoice Processed Successfully!
     ...
```

---

### Example 3: Canceling

```
You: [Send wrong image]

Bot: ✅ Page 1 received!
     Send more pages or type /done to process.

You: /cancel

Bot: ✅ Cancelled! Cleared 1 image(s).
     Send new invoice images whenever you're ready.

You: [Send correct image]

Bot: ✅ Page 1 received!
     ...
```

---

## ❓ Frequently Asked Questions

### Q: How many pages can I send?
**A:** Up to 10 images per invoice.

### Q: Can I process multiple invoices at once?
**A:** No, process one invoice at a time. After typing `/done`, wait for confirmation before starting the next invoice.

### Q: What happens if I make a mistake?
**A:** Type `/cancel` to clear everything and start over.

### Q: Can I edit the data after it's processed?
**A:** Not through the bot. You can edit directly in the Google Sheet.

### Q: What if the invoice is in poor quality?
**A:** Try to take a better photo. Clear, well-lit images give best results.

### Q: Does the bot work 24/7?
**A:** Yes, as long as the bot is running on the server.

### Q: Is my data safe?
**A:** Yes, all data is securely processed and stored in your organization's Google Sheet only.

### Q: Can I use the bot on mobile and desktop?
**A:** Yes, the bot works on any device with Telegram installed.

---

## 📚 Quick Tips

1. **Better photos = Better results**
2. **Send all pages before `/done`**
3. **One invoice at a time**
4. **Use `/cancel` if you make a mistake**
5. **Wait for confirmation before next invoice**

---

## 🎯 Success Checklist

Before sending to the bot:
- [ ] Invoice image is clear and readable
- [ ] All text is visible
- [ ] Lighting is good
- [ ] All pages are captured (for multi-page)

After receiving confirmation:
- [ ] Check if invoice number is correct
- [ ] Verify amounts match the invoice
- [ ] Confirm data appears in Google Sheet

---

**Need more help?** Contact your system administrator.

---

**Version:** 1.0.0  
**Last Updated:** February 2026  
**For:** End Users
