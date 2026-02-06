"""
Telegram Bot for GST Invoice Scanner
Handles user interactions and orchestrates the invoice processing workflow
"""
import os
import sys
import asyncio
from datetime import datetime

# Fix encoding for Windows PowerShell
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
from typing import List, Dict, Optional
import config
from ocr.ocr_engine import OCREngine
from parsing.gst_parser import GSTParser
from sheets.sheets_manager import SheetsManager

# Tier 2 imports
if config.ENABLE_CONFIDENCE_SCORING:
    from features.confidence_scorer import ConfidenceScorer
if config.ENABLE_MANUAL_CORRECTIONS:
    from features.correction_manager import CorrectionManager
if config.ENABLE_DEDUPLICATION:
    from features.dedup_manager import DeduplicationManager
if config.ENABLE_AUDIT_LOGGING:
    from features.audit_logger import AuditLogger

# Tier 3 imports
from commands.tier3_commands import Tier3CommandHandlers

# ═══════════════════════════════════════════════════════════════════
# Epic 2: Order Upload & Normalization (Feature-Flagged)
# ═══════════════════════════════════════════════════════════════════
if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
    from order_normalization import OrderSession, OrderNormalizationOrchestrator
    print("[OK] Epic 2: Order Upload module loaded")
# ═══════════════════════════════════════════════════════════════════


async def setup_bot_commands(application):
    """
    Set up bot command menu visible in Telegram's menu button
    This runs once when bot starts
    """
    commands = [
        BotCommand("upload", "Upload invoice"),
        BotCommand("generate", "Generate reports"),
        BotCommand("help", "Help & guide"),
    ]
    
    await application.bot.set_my_commands(commands)
    print("[OK] Bot commands menu configured")


class GSTScannerBot:
    """Telegram Bot for GST Invoice Scanning"""
    
    def __init__(self):
        """Initialize the bot and its components"""
        self.ocr_engine = OCREngine()
        self.gst_parser = GSTParser()
        self.sheets_manager = SheetsManager()
        
        # Tier 2 components
        if config.ENABLE_CONFIDENCE_SCORING:
            self.confidence_scorer = ConfidenceScorer(config.CONFIDENCE_THRESHOLD_REVIEW)
        else:
            self.confidence_scorer = None
        
        if config.ENABLE_MANUAL_CORRECTIONS:
            self.correction_manager = CorrectionManager()
        else:
            self.correction_manager = None
        
        if config.ENABLE_DEDUPLICATION:
            self.dedup_manager = DeduplicationManager()
        else:
            self.dedup_manager = None
        
        if config.ENABLE_AUDIT_LOGGING:
            self.audit_logger = AuditLogger()
        else:
            self.audit_logger = None
        
        # ═══════════════════════════════════════════════════════
        # Usage Tracking (NEW - Phase 1)
        # ═══════════════════════════════════════════════════════
        if config.ENABLE_USAGE_TRACKING:
            from utils.usage_tracker import get_usage_tracker
            from utils.metrics_tracker import get_metrics_tracker
            self.usage_tracker = get_usage_tracker()
            self.metrics_tracker = get_metrics_tracker()
            print("[OK] Usage tracking initialized")
        else:
            self.usage_tracker = None
            self.metrics_tracker = None
        # ═══════════════════════════════════════════════════════
        
        # Create temp folder if it doesn't exist
        os.makedirs(config.TEMP_FOLDER, exist_ok=True)
        
        # Store user sessions (invoice images being collected)
        # Enhanced session structure for Tier 2 & Tier 3
        self.user_sessions = {}  # Format: {user_id: {'images': [], 'state': 'uploading', 'data': {}, 'corrections': {}, 'batch': []}}
        
        # Tier 3 command handlers
        self.tier3_handlers = Tier3CommandHandlers(self)
        
        # ═══════════════════════════════════════════════════════
        # Epic 2: Order Upload & Normalization (Feature-Flagged)
        # ═══════════════════════════════════════════════════════
        if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            self.order_orchestrator = OrderNormalizationOrchestrator()
            self.order_sessions = {}  # Separate from GST invoice sessions
            print("[OK] Epic 2: Order processing orchestrator initialized")
        else:
            self.order_orchestrator = None
            self.order_sessions = {}
        # ═══════════════════════════════════════════════════════

    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - Show welcome message with main menu"""
        user = update.effective_user
        
        welcome_message = f"""
👋 Welcome to GST Scanner Bot, {user.first_name}!

I help you extract GST invoice data and append it to Google Sheets automatically.

🎯 **What I can do:**
• Extract invoice data from images
• Validate GST numbers and calculations
• Save to Google Sheets with line items
• Generate GSTR-1 and GSTR-3B exports
• Process multiple invoices in batch
• Provide detailed reports and statistics

🚀 **Ready to get started?**
Select an option from the menu below:
"""
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=self.create_main_menu_keyboard()
        )
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command - Show main menu"""
        await update.message.reply_text(
            "📋 Main Menu\n\nSelect an option:",
            reply_markup=self.create_main_menu_keyboard()
        )
    
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /upload command - Start upload session"""
        user_id = update.effective_user.id
        
        # Initialize session
        self._get_user_session(user_id)
        self.user_sessions[user_id]['state'] = 'uploading'
        
        await update.message.reply_text(
            "📸 Upload Invoice\n\n"
            "Send me your invoice images (one or multiple pages).\n"
            "When done, type /done to process."
        )
    
    async def generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate command - Show generate submenu"""
        await update.message.reply_text(
            "📊 Generate GST Input\n\n"
            "Select the type of report or export you need:",
            reply_markup=self.create_generate_submenu()
        )
    
    def _get_user_session(self, user_id: int) -> Dict:
        """Get or create user session"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'images': [],
                'state': 'uploading',  # uploading, reviewing, correcting, confirming_duplicate
                'data': {},  # Stores extracted invoice data
                'corrections': {},  # Stores manual corrections
                'start_time': None,
                'ocr_text': '',
                'confidence_scores': {},
                'validation_result': {},
                'fingerprint': '',
                'duplicate_info': None
            }
        return self.user_sessions[user_id]
    
    def _clear_user_session(self, user_id: int):
        """Clear user session"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
    
    def _escape_markdown(self, text: str) -> str:
        """Escape special Markdown characters to prevent parsing errors"""
        if not text:
            return text
        # Escape Markdown special characters
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = str(text).replace(char, f'\\{char}')
        return text
    
    def create_main_menu_keyboard(self):
        """Create main menu with inline buttons"""
        keyboard = [
            [InlineKeyboardButton("📸 Upload Purchase Invoice", callback_data="menu_upload")],
        ]
        
        # ═══════════════════════════════════════════════════════
        # Epic 2: Conditional Order Upload button (Feature-Flagged)
        # ═══════════════════════════════════════════════════════
        if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            keyboard.append([InlineKeyboardButton("📦 Upload Order", callback_data="menu_order_upload")])
        # ═══════════════════════════════════════════════════════
        
        keyboard.extend([
            [InlineKeyboardButton("📊 Generate GST Input", callback_data="menu_generate")],
            [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
            [InlineKeyboardButton("📈 Usage & Stats", callback_data="menu_usage")],
        ])
        return InlineKeyboardMarkup(keyboard)

    def create_upload_submenu(self):
        """Submenu for Upload options"""
        keyboard = [
            [InlineKeyboardButton("Single Invoice", callback_data="upload_single")],
            [InlineKeyboardButton("Batch Upload", callback_data="upload_batch")],
            [InlineKeyboardButton("Upload Document", callback_data="upload_document")],
            [InlineKeyboardButton("Upload Help", callback_data="help_upload")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_generate_submenu(self):
        """Submenu for Generate GST options"""
        keyboard = [
            [InlineKeyboardButton("GSTR-1 Export", callback_data="gen_gstr1")],
            [InlineKeyboardButton("GSTR-3B Summary", callback_data="gen_gstr3b")],
            [InlineKeyboardButton("Reports", callback_data="gen_reports")],
            [InlineKeyboardButton("Quick Stats", callback_data="gen_stats")],
            [InlineKeyboardButton("Export Help", callback_data="help_export")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_help_submenu(self):
        """Submenu for Help options"""
        keyboard = [
            [InlineKeyboardButton("Getting Started", callback_data="help_start")],
            [InlineKeyboardButton("Upload Guide", callback_data="help_upload")],
            [InlineKeyboardButton("Corrections", callback_data="help_corrections")],
            [InlineKeyboardButton("Export Guide", callback_data="help_export")],
            [InlineKeyboardButton("Troubleshooting", callback_data="help_trouble")],
            [InlineKeyboardButton("Support", callback_data="help_contact")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_usage_submenu(self):
        """Submenu for Usage/Stats options"""
        keyboard = [
            [InlineKeyboardButton("Quick Stats", callback_data="stats_quick")],
            [InlineKeyboardButton("Detailed Reports", callback_data="stats_detailed")],
            [InlineKeyboardButton("History", callback_data="stats_history")],
            [InlineKeyboardButton("Export Data", callback_data="stats_export")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
📚 **GST Scanner Bot Help**

**Sending Invoices:**
• Send invoice images one by one
• For multi-page invoices, send all pages in sequence
• Supported formats: JPG, JPEG, PNG
• Maximum {max_images} images per invoice

**Processing:**
• Type /done after sending all pages
• Bot will extract GST data automatically
• Data will be appended to Google Sheet

**Commands:**
• /start - Welcome message
• /done - Process current invoice
• /cancel - Cancel and clear current invoice
• /help - Show this help

**What gets extracted:**
• Invoice number and date
• Seller and buyer details
• GST numbers and state codes
• Taxable amounts and GST totals
• CGST, SGST, IGST breakup

**Tips:**
- Ensure images are clear and readable
- All pages should be from the same invoice
- Check that GST numbers are visible
- Good lighting improves accuracy

Need assistance? Contact your administrator.
""".format(max_images=config.MAX_IMAGES_PER_INVOICE)
        
        await update.message.reply_text(help_message)
    
    async def handle_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle inline keyboard button callbacks
        Routes all menu button clicks to appropriate actions
        """
        query = update.callback_query
        await query.answer()  # Acknowledge button press (removes loading state)
        
        callback_data = query.data
        user_id = update.effective_user.id
        
        # ═══════════════════════════════════════════════════════
        # MAIN MENU NAVIGATION
        # ═══════════════════════════════════════════════════════
        
        if callback_data == "menu_main":
            # Return to main menu
            await query.edit_message_text(
                "📋 Main Menu\n\nSelect an option:",
                reply_markup=self.create_main_menu_keyboard()
            )
        
        elif callback_data == "menu_upload":
            # Start upload session
            user_id = update.effective_user.id
            self._get_user_session(user_id)
            self.user_sessions[user_id]['state'] = 'uploading'
            
            await query.edit_message_text(
                "📸 Upload Invoice\n\n"
                "Send me your invoice images (one or multiple pages).\n"
                "When done, type /done to process."
            )
        
        elif callback_data == "menu_generate":
            # Show generate submenu
            await query.edit_message_text(
                "📊 Generate GST Input\n\n"
                "Select the type of report or export you need:",
                reply_markup=self.create_generate_submenu()
            )
        
        elif callback_data == "menu_help":
            # Show help submenu
            await query.edit_message_text(
                "❓ Help & Documentation\n\n"
                "What do you need help with?",
                reply_markup=self.create_help_submenu()
            )
        
        elif callback_data == "menu_usage":
            # Show usage submenu
            await query.edit_message_text(
                "📈 Usage & Statistics\n\n"
                "Select what you'd like to view:",
                reply_markup=self.create_usage_submenu()
            )
        
        # ═══════════════════════════════════════════════════════
        # Epic 2: ORDER UPLOAD MENU (Feature-Flagged)
        # ═══════════════════════════════════════════════════════
        elif callback_data == "menu_order_upload":
            # Check feature flag
            if not config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
                await query.edit_message_text(
                    "⚠️ Order upload feature is not enabled.",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            
            # Start order upload session
            order_session = OrderSession(user_id, update.effective_user.username)
            self.order_sessions[user_id] = order_session
            
            await query.edit_message_text(
                "📦 Upload Order (Handwritten Notes)\n\n"
                "✅ Ready to receive order pages!\n\n"
                "**Instructions:**\n"
                "1. Send me photos of handwritten order notes\n"
                "2. You can send multiple pages if the order spans multiple sheets\n"
                "3. Type /order_submit when you've sent all pages\n\n"
                "I'll extract the line items, match with pricing, and generate a clean PDF.\n\n"
                "Type /cancel to abort."
            )
        # ═══════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════
        # UPLOAD SUBMENU ACTIONS
        # ═══════════════════════════════════════════════════════
        
        elif callback_data == "upload_single":
            session = self._get_user_session(user_id)
            session['state'] = 'uploading'
            session['images'] = []
            
            await query.edit_message_text(
                "📷 Single Invoice Upload Mode\n\n"
                "✅ Ready to receive photos!\n\n"
                "**Instructions:**\n"
                "1. Send me one or more images of your invoice\n"
                "2. For multi-page invoices, send all pages\n"
                "3. Type /done when you've sent all pages\n\n"
                "I'll extract the data and save it to Google Sheets.\n\n"
                "Type /cancel to abort."
            )
        
        elif callback_data == "upload_batch":
            session = self._get_user_session(user_id)
            session['state'] = 'uploading'
            session['images'] = []
            session['batch'] = []
            
            await query.edit_message_text(
                "📦 Batch Upload Mode\n\n"
                "✅ Ready for multiple invoices!\n\n"
                "**Instructions:**\n"
                "1. Upload all pages of first invoice\n"
                "2. Type /next to save and start next invoice\n"
                "3. Repeat for all invoices\n"
                "4. Type /done to process entire batch\n\n"
                "This is perfect for processing multiple invoices at once.\n\n"
                "Type /cancel to abort."
            )
        
        elif callback_data == "upload_document":
            await query.edit_message_text(
                "📎 Upload from Document\n\n"
                "You can send invoices as:\n"
                "• Image files (JPG, PNG)\n"
                "• Documents (right now)\n"
                "• PDF files (coming soon!)\n\n"
                "Just send your file and I'll process it.\n"
                "Type /done when finished.\n\n"
                "Type /cancel to abort."
            )
        
        # ═══════════════════════════════════════════════════════
        # GENERATE SUBMENU ACTIONS
        # ═══════════════════════════════════════════════════════
        
        elif callback_data == "gen_gstr1":
            # Call existing tier3 handler
            await query.message.reply_text(
                "📄 Starting GSTR-1 Export...\n"
                "This will be interactive."
            )
            # Convert callback query to regular update for tier3 handler
            await self.tier3_handlers.export_gstr1_command(update, context)
        
        elif callback_data == "gen_gstr3b":
            # Call existing tier3 handler
            await query.message.reply_text(
                "📋 Starting GSTR-3B Summary...\n"
                "This will be interactive."
            )
            await self.tier3_handlers.export_gstr3b_command(update, context)
        
        elif callback_data == "gen_reports":
            # Call existing tier3 handler
            await query.message.reply_text(
                "📊 Starting Operational Reports...\n"
                "This will be interactive."
            )
            await self.tier3_handlers.reports_command(update, context)
        
        elif callback_data == "gen_stats":
            # Call existing tier3 handler directly
            await self.tier3_handlers.stats_command(update, context)
        
        # ═══════════════════════════════════════════════════════
        # HELP SUBMENU ACTIONS
        # ═══════════════════════════════════════════════════════
        
        elif callback_data == "help_start":
            help_text = """🚀 Getting Started Guide

Welcome to GST Scanner Bot! Here's how to use it:

Step 1: Upload Invoice
Send me a photo of your GST invoice (JPG/PNG format)

Step 2: Process
Type /done after sending all pages

Step 3: Review
I'll extract all GST data automatically

Step 4: Save
Data is saved to your Google Sheet

That's it! The bot handles:
✅ Invoice number & date
✅ Seller & buyer details
✅ GST breakup (CGST/SGST/IGST)
✅ Line items with HSN codes
✅ Validation & deduplication

Tips for best results:
📸 Take clear, well-lit photos
📄 Include all pages for multi-page invoices
🔍 Ensure GST numbers are visible

Ready to start? Click below!"""
            keyboard = [
                [InlineKeyboardButton("Upload First Invoice", callback_data="upload_single")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu_help")]
            ]
            await query.edit_message_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif callback_data == "help_upload":
            help_text = """📸 How to Upload Invoices

Single Invoice:
1. Click "Upload Single Invoice"
2. Send invoice photo(s)
3. Type /done to process

Multiple Invoices (Batch):
1. Click "Upload Batch"
2. Send pages of first invoice
3. Type /next for next invoice
4. Repeat for all invoices
5. Type /done to process all

Supported Formats:
✅ JPG, JPEG, PNG
✅ Photos (direct from camera)
✅ Image files (sent as documents)
⏳ PDF (coming soon!)

Multi-page Invoices:
If your invoice has multiple pages, send them all before typing /done

Tips:
• Maximum 10 images per invoice
• Good lighting improves accuracy
• Avoid blurry or tilted images
• Ensure text is readable

Commands:
/done - Process uploaded images
/cancel - Clear images and start over
/next - Save current & start next (batch mode)"""
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_help_submenu()
            )
        
        elif callback_data == "help_corrections":
            if not config.ENABLE_MANUAL_CORRECTIONS:
                await query.edit_message_text(
                    "✏️ Manual Corrections\n\n"
                    "Manual corrections are currently disabled.\n"
                    "Contact your administrator to enable this feature.",
                    reply_markup=self.create_help_submenu()
                )
            else:
                help_text = """✏️ Manual Corrections Guide

When the bot extracts data, you can review and correct it before saving.

When Corrections Are Needed:
The bot will prompt you if:
• Confidence score is low (< 70%)
• Validation warnings detected
• Critical fields are unclear

How to Correct:
1. Bot shows extracted data
2. Click "Correct" or type /correct
3. Enter corrections in format:
   field_name = value

Example:
buyer_gstin = 29AAAAA0000A1Z5
invoice_value = 125000.00

Available Fields:
• invoice_no
• invoice_date
• seller_gstin
• buyer_gstin
• invoice_value
• total_taxable_value
• total_gst
(and more...)

Commands:
/correct - Start correction mode
/confirm - Save without corrections
/done - Save with corrections
/cancel - Discard everything"""
                await query.edit_message_text(
                    help_text,
                    reply_markup=self.create_help_submenu()
                )
        
        elif callback_data == "help_export":
            help_text = """📊 Export & Reports Guide

GSTR-1 Export:
Generate CSV files for GSTR-1 filing:
• B2B Invoices (Business-to-Business)
• B2C Small (Under ₹2.5L)
• HSN Summary (with quantities & values)

GSTR-3B Summary:
Monthly summary JSON for GSTR-3B:
• Total tax liability
• ITC available
• Tax payable breakdown

Operational Reports:
Various reports for analysis:
• Processing statistics
• Validation errors
• Duplicate attempts
• Correction history

How to Export:
1. Click "Generate GST input"
2. Select export type
3. Enter month (1-12)
4. Enter year (e.g., 2026)
5. Receive CSV/JSON files

Commands:
/export_gstr1 - GSTR-1 exports
/export_gstr3b - GSTR-3B summary
/reports - Operational reports
/stats - Quick statistics"""
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_generate_submenu()
            )
        
        elif callback_data == "help_trouble":
            help_text = """🔧 Troubleshooting

Common Issues:

1. Image not recognized
• Ensure good lighting
• Avoid glare and shadows
• Keep camera steady (no blur)
• Try taking photo again

2. Wrong data extracted
• Check if image is clear
• Verify GST numbers are visible
• Use /correct to fix specific fields
• Send additional pages if multi-page

3. Validation errors
• Check GSTIN format (15 chars)
• Verify dates are valid
• Ensure amounts match invoice
• Review error message for details

4. Duplicate invoice warning
• Bot found similar invoice already processed
• Check invoice number and date
• Use /override if you're sure it's unique
• Use /cancel if it's actually duplicate

5. Bot not responding
• Check your internet connection
• Try /cancel and start over
• Bot may be processing (be patient)
• Contact support if persists

Still having issues?
Contact your administrator or support team."""
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_help_submenu()
            )
        
        elif callback_data == "help_contact":
            help_text = """📞 Contact Support

For Technical Issues:
Contact your system administrator

For Bot Usage Questions:
Use the help menu or /help command

For Feature Requests:
Discuss with your administrator

Bot Information:
• Version: Tier 3 (with exports)
• Features: OCR, Validation, Batch, GSTR
• Supported: JPG, PNG images

Useful Commands:
/start - Restart bot & show menu
/help - Show help information
/cancel - Cancel current operation"""
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_help_submenu()
            )
        
        # ═══════════════════════════════════════════════════════
        # USAGE/STATS SUBMENU ACTIONS
        # ═══════════════════════════════════════════════════════
        
        elif callback_data == "stats_quick":
            # Show quick stats inline
            await query.message.reply_text("📊 Generating quick statistics...")
            await self.tier3_handlers.stats_command(update, context)
        
        elif callback_data == "stats_detailed":
            session = self._get_user_session(user_id)
            session['export_command'] = 'reports'
            session['export_step'] = 'month'
            session['report_type'] = '5'  # Comprehensive report
            
            await query.message.reply_text(
                "📊 Detailed Reports\n\n"
                "Enter month (1-12) for comprehensive report:"
            )
        
        elif callback_data == "stats_history":
            help_text = """🕒 Processing History

Your processing history is stored in Google Sheets.

Where to find it:
1. Open your Google Sheet
2. Check "Invoice_Header" tab
3. Look for your Telegram username

What's tracked:
• Upload timestamp
• Telegram user ID & username
• Processing time
• Model version
• Corrections made
• Validation status

Tier 2 Audit Trail:
If audit logging is enabled, additional details:
• Confidence scores
• Duplicate checks
• Manual corrections
• Processing metadata

View Statistics:
Use /stats for overall processing statistics
Use /reports for detailed analysis"""
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_usage_submenu()
            )
        
        elif callback_data == "stats_export":
            await query.message.reply_text(
                "💾 Export Processing Data\n\n"
                "Your data is already in Google Sheets!\n\n"
                "Sheets Available:\n"
                "• Invoice_Header - Main invoice data\n"
                "• Line_Items - Item-level details\n"
                "• Customer_Master - Buyer database\n"
                "• HSN_Master - Product codes\n\n"
                "You can export directly from Google Sheets:\n"
                "File → Download → CSV/Excel\n\n"
                "Or use /export_gstr1 for GSTR-1 CSV exports."
            )
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            # Clear user session
            session = self.user_sessions[user_id]
            image_count = len(session.get('images', []))
            self._clear_user_session(user_id)
            
            await update.message.reply_text(
                f"✅ Cancelled! Cleared {image_count} image(s).\n"
                "Send new invoice images whenever you're ready."
            )
        else:
            await update.message.reply_text(
                "No active invoice to cancel.\n"
                "Send an invoice image to start!"
            )
    
    async def confirm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /confirm command - save invoice without corrections"""
        user_id = update.effective_user.id
        session = self._get_user_session(user_id)
        
        if session['state'] != 'reviewing':
            await update.message.reply_text(
                "⚠️ No invoice pending confirmation.\n"
                "Use /done after uploading images."
            )
            return
        
        # Proceed to save without corrections
        await self._save_invoice_to_sheets(update, user_id, session)
    
    async def correct_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /correct command - start correction mode"""
        if not config.ENABLE_MANUAL_CORRECTIONS:
            await update.message.reply_text("Manual corrections are disabled.")
            return
        
        user_id = update.effective_user.id
        session = self._get_user_session(user_id)
        
        if session['state'] != 'reviewing':
            await update.message.reply_text(
                "⚠️ No invoice pending corrections.\n"
                "Use /done after uploading images."
            )
            return
        
        # Enter correction mode
        session['state'] = 'correcting'
        
        instructions = self.correction_manager.generate_correction_instructions()
        await update.message.reply_text(instructions)  # No Markdown to avoid parsing errors
    
    async def override_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /override command - save duplicate invoice anyway"""
        user_id = update.effective_user.id
        session = self._get_user_session(user_id)
        
        if session['state'] != 'confirming_duplicate':
            await update.message.reply_text(
                "⚠️ No duplicate confirmation pending."
            )
            return
        
        # Save with duplicate override
        await self._save_invoice_to_sheets(update, user_id, session, is_duplicate_override=True)
    
    async def _save_invoice_to_sheets(
        self,
        update: Update,
        user_id: int,
        session: Dict,
        is_duplicate_override: bool = False
    ):
        """Save invoice data to Google Sheets with Tier 2 audit trail"""
        try:
            await update.message.reply_text("📊 Step 4/4: Updating Google Sheets...")
            
            invoice_data = session['data']['invoice_data']
            line_items_data = session['data']['line_items_data']
            validation_result = session['validation_result']
            
            # Apply corrections if any
            if session['corrections']:
                invoice_data = self.correction_manager.apply_corrections(
                    invoice_data,
                    session['corrections']
                )
                
                # Create correction metadata
                corrections_metadata = self.correction_manager.create_correction_metadata(
                    session['data']['invoice_data'],  # Original
                    session['corrections'],
                    user_id
                )
            else:
                corrections_metadata = None
            
            # Format invoice data for sheets
            header_row = self.gst_parser.format_for_sheets(invoice_data)
            
            # Generate audit metadata
            end_time = datetime.now()
            username = update.effective_user.username
            
            if config.ENABLE_AUDIT_LOGGING and self.audit_logger:
                audit_data = self.audit_logger.generate_audit_metadata(
                    user_id=user_id,
                    username=username,
                    images=session['images'],
                    start_time=session['start_time'],
                    end_time=end_time,
                    validation_result=validation_result,
                    corrections=session['corrections'],
                    extraction_version=config.EXTRACTION_VERSION,
                    model_version="gemini-2.5-flash"
                )
            else:
                audit_data = {}
            
            # Determine duplicate status
            if config.ENABLE_DEDUPLICATION and self.dedup_manager:
                fingerprint = session.get('fingerprint', '')
                # Check if duplicate was detected (warn-only mode) or manually overridden
                is_duplicate = session.get('is_duplicate', False) or is_duplicate_override
                duplicate_status = self.dedup_manager.get_duplicate_status(is_duplicate)
            else:
                fingerprint = ''
                duplicate_status = 'UNIQUE'
            
            # Save to sheets with full audit trail
            if config.ENABLE_AUDIT_LOGGING:
                self.sheets_manager.append_invoice_with_audit(
                    invoice_data=header_row,
                    line_items_data=line_items_data,
                    validation_result=validation_result,
                    audit_data=audit_data,
                    confidence_scores=session['confidence_scores'],
                    corrections_metadata=corrections_metadata,
                    fingerprint=fingerprint,
                    duplicate_status=duplicate_status
                )
            else:
                # Fall back to Tier 1 method
                self.sheets_manager.append_invoice_with_items(
                    header_row,
                    line_items_data,
                    validation_result
                )
            
            # Update customer master (Tier 3 feature)
            self._update_customer_master_data(invoice_data)
            
            # Update seller master (Tier 3 feature)
            self._update_seller_master_data(invoice_data)
            
            # Update HSN master from line items (Tier 3 feature)
            self._update_hsn_master_data(session['data']['line_items'])
            
            # Generate success message
            success_message = self._format_success_message(
                invoice_data,
                session['data']['line_items'],
                validation_result,
                session['corrections'],
                audit_data,
                is_duplicate_override
            )
            
            # ═══════════════════════════════════════════════════════
            # CRITICAL: Send success to user IMMEDIATELY (Phase 3)
            # ═══════════════════════════════════════════════════════
            await update.message.reply_text(success_message)  # No Markdown - plain text only
            # User now has confirmation - invoice processing COMPLETE
            # ═══════════════════════════════════════════════════════
            
            # ═══════════════════════════════════════════════════════
            # NEW: Track usage in background AFTER user response (Phase 3)
            # ═══════════════════════════════════════════════════════
            if config.ENABLE_USAGE_TRACKING and self.usage_tracker:
                # Fire-and-forget background task
                asyncio.create_task(
                    self._track_invoice_complete_async(
                        user_id=user_id,
                        username=update.effective_user.username,
                        session=session.copy(),  # Copy to avoid mutations
                        end_time=end_time
                    )
                )
            # ═══════════════════════════════════════════════════════
            
            # Clear user session
            self._clear_user_session(user_id)
            
        except Exception as e:
            raise Exception(f"Failed to save invoice: {str(e)}")
    
    def _update_customer_master_data(self, invoice_data: Dict):
        """Update customer_master sheet with seller-buyer pair from invoice"""
        try:
            seller_gstin = invoice_data.get('Seller_GSTIN', '').strip()
            buyer_gstin = invoice_data.get('Buyer_GSTIN', '').strip()
            
            # Both seller and buyer GSTIN required for pair tracking
            if not seller_gstin or len(seller_gstin) < 15:
                print(f"[INFO] Skipping customer master update - invalid seller GSTIN: {seller_gstin}")
                return
            if not buyer_gstin or len(buyer_gstin) < 15:
                print(f"[INFO] Skipping customer master update - invalid buyer GSTIN: {buyer_gstin}")
                return
            
            customer_data = {
                'Seller_GSTIN': seller_gstin,
                'Seller_Name': invoice_data.get('Seller_Name', '').strip(),
                'Buyer_GSTIN': buyer_gstin,
                'Buyer_Name': invoice_data.get('Buyer_Name', '').strip(),
                'Trade_Name': invoice_data.get('Buyer_Name', '').strip(),
                'Buyer_State_Code': invoice_data.get('Buyer_State_Code', '').strip(),
                'Default_Place_Of_Supply': invoice_data.get('Buyer_State', '').strip(),
                'Last_Updated': '',
                'Usage_Count': 1
            }
            
            print(f"[INFO] Updating customer master: {seller_gstin[:10]}... -> {buyer_gstin[:10]}...")
            self.sheets_manager.update_customer_master(seller_gstin, buyer_gstin, customer_data)
            
        except Exception as e:
            print(f"[ERROR] Could not update customer master: {str(e)}")
    
    async def _update_metrics(self, context: ContextTypes.DEFAULT_TYPE):
        """Periodic task to update metrics like active sessions"""
        try:
            # Update active session count
            active_count = len(self.user_sessions)
            self.metrics_tracker.set_active_sessions(active_count)
            
            # Update integration status
            try:
                # Check if sheets are accessible
                self.metrics_tracker.update_integration_status('sheets_accessible', True)
            except:
                self.metrics_tracker.update_integration_status('sheets_accessible', False)
            
            # Telegram is always connected if this job runs
            self.metrics_tracker.update_integration_status('telegram_connected', True)
            
            # Gemini API is assumed available (would need actual check)
            self.metrics_tracker.update_integration_status('gemini_api_available', True)
            
        except Exception as e:
            print(f"[WARNING] Could not update metrics: {e}")
    
    # ═══════════════════════════════════════════════════════
    # Background Tracking Task (NEW - Phase 3)
    # ═══════════════════════════════════════════════════════
    
    async def _track_invoice_complete_async(
        self,
        user_id: int,
        username: str,
        session: Dict,
        end_time: datetime
    ):
        """
        Background task - tracks invoice completion AFTER user gets response.
        This runs asynchronously and can take as long as needed without impacting UX.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            session: Copy of user session data
            end_time: Processing end time
        """
        try:
            start_time = session.get('start_time', end_time)
            processing_time = (end_time - start_time).total_seconds()
            
            invoice_data = session['data']['invoice_data']
            invoice_id = invoice_data.get('Invoice_No', 'unknown')
            
            # Extract timing information
            ocr_time = session.get('_ocr_metadata', {}).get('ocr_time_seconds', 0)
            parsing_time = session.get('_parsing_metadata', {}).get('parsing_time_seconds', 0)
            sheets_time = processing_time - ocr_time - parsing_time
            
            # Get validation status
            validation_result = session.get('validation_result', {})
            validation_status = validation_result.get('status', 'unknown')
            
            # Get confidence average
            confidence_scores = session.get('confidence_scores', {})
            if confidence_scores:
                conf_values = [v for v in confidence_scores.values() if isinstance(v, (int, float))]
                confidence_avg = sum(conf_values) / len(conf_values) if conf_values else 0.0
            else:
                confidence_avg = 0.0
            
            # Check if corrections were made
            had_corrections = bool(session.get('corrections'))
            
            # Track OCR calls (Level 1)
            ocr_call_ids = []
            if config.ENABLE_OCR_LEVEL_TRACKING:
                pages_metadata = session.get('_ocr_metadata', {}).get('pages', [])
                for page_meta in pages_metadata:
                    ocr_record = self.usage_tracker.record_ocr_call(
                        invoice_id=invoice_id,
                        page_number=page_meta.get('page_number', 1),
                        model_name="gemini-2.5-flash",
                        prompt_tokens=page_meta.get('prompt_tokens', 0),
                        output_tokens=page_meta.get('output_tokens', 0),
                        processing_time_ms=int(ocr_time * 1000 / len(pages_metadata)) if pages_metadata else 0,
                        image_size_bytes=page_meta.get('image_size_bytes', 0),
                        customer_id=config.DEFAULT_CUSTOMER_ID,
                        telegram_user_id=user_id,
                        status="success"
                    )
                    if ocr_record:
                        ocr_call_ids.append(ocr_record.get('call_id', ''))
            
            # Calculate token totals
            pages_metadata = session.get('_ocr_metadata', {}).get('pages', [])
            ocr_prompt_tokens = sum(p.get('prompt_tokens', 0) for p in pages_metadata)
            ocr_output_tokens = sum(p.get('output_tokens', 0) for p in pages_metadata)
            ocr_total_tokens = ocr_prompt_tokens + ocr_output_tokens
            
            # Parsing tokens (estimated from text length if not available)
            parsing_text_length = session.get('_parsing_metadata', {}).get('ocr_text_length', 0)
            parsing_prompt_tokens = int(parsing_text_length * 0.75)
            parsing_output_tokens = int(parsing_prompt_tokens * 0.3)
            parsing_total_tokens = parsing_prompt_tokens + parsing_output_tokens
            
            # Track Invoice usage (Level 2)
            if config.ENABLE_INVOICE_LEVEL_TRACKING:
                invoice_record = self.usage_tracker.record_invoice_usage(
                    invoice_id=invoice_id,
                    customer_id=config.DEFAULT_CUSTOMER_ID,
                    telegram_user_id=user_id,
                    telegram_username=username or "unknown",
                    page_count=len(session.get('images', [])),
                    total_ocr_calls=len(pages_metadata),
                    total_parsing_calls=2,  # Header + line items
                    ocr_tokens={
                        'prompt': ocr_prompt_tokens,
                        'output': ocr_output_tokens,
                        'total': ocr_total_tokens
                    },
                    parsing_tokens={
                        'prompt': parsing_prompt_tokens,
                        'output': parsing_output_tokens,
                        'total': parsing_total_tokens
                    },
                    processing_time_seconds=processing_time,
                    ocr_time_seconds=ocr_time,
                    parsing_time_seconds=parsing_time,
                    sheets_time_seconds=sheets_time,
                    validation_status=validation_status,
                    confidence_avg=confidence_avg,
                    had_corrections=had_corrections,
                    ocr_call_ids=ocr_call_ids
                )
                
                # Update customer summary (Level 3)
                if invoice_record and config.ENABLE_CUSTOMER_AGGREGATION:
                    self.usage_tracker.update_customer_summary(invoice_record)
            
            print(f"[BACKGROUND] Usage tracked for invoice {invoice_id}")
            
        except Exception as e:
            # Silent fail - user already has their success message
            print(f"[BACKGROUND] Tracking failed (user unaffected): {e}")
    
    # ═══════════════════════════════════════════════════════
    
    def _update_seller_master_data(self, invoice_data: Dict):
        """Update seller_master sheet with seller information from invoice"""
        try:
            seller_gstin = invoice_data.get('Seller_GSTIN', '').strip()
            
            if not seller_gstin or len(seller_gstin) < 15:
                return
            
            seller_data = {
                'GSTIN': seller_gstin,
                'Legal_Name': invoice_data.get('Seller_Name', '').strip(),
                'Trade_Name': invoice_data.get('Seller_Name', '').strip(),
                'State_Code': invoice_data.get('Seller_State_Code', '').strip(),
                'Address': '',
                'Contact_Number': '',
                'Email': '',
                'Last_Updated': '',
                'Usage_Count': 1
            }
            
            self.sheets_manager.update_seller_master(seller_gstin, seller_data)
            
        except Exception as e:
            print(f"[ERROR] Could not update seller master: {str(e)}")
    
    def _update_hsn_master_data(self, line_items: List[Dict]):
        """Update hsn_master sheet with HSN codes from line items"""
        try:
            for item in line_items:
                hsn_code = item.get('HSN', '').strip()
                
                if not hsn_code or len(hsn_code) < 4:
                    continue
                
                hsn_data = {
                    'HSN_SAC_Code': hsn_code,
                    'Description': item.get('Item_Description', '').strip(),
                    'Default_GST_Rate': item.get('GST_Rate', '').strip(),
                    'UQC': item.get('UOM', '').strip(),
                    'Category': '',
                    'Last_Updated': '',
                    'Usage_Count': 1
                }
                
                self.sheets_manager.update_hsn_master(hsn_code, hsn_data)
                
        except Exception as e:
            print(f"[ERROR] Could not update HSN master: {str(e)}")
    
    def _format_success_message(
        self,
        invoice_data: Dict,
        line_items: List,
        validation_result: Dict,
        corrections: Dict,
        audit_data: Dict,
        is_duplicate_override: bool
    ) -> str:
        """Format success message with all details (plain text, no Markdown)"""
        invoice_no = invoice_data.get('Invoice_No', 'N/A')
        invoice_date = invoice_data.get('Invoice_Date', 'N/A')
        seller_name = invoice_data.get('Seller_Name', 'N/A')
        buyer_name = invoice_data.get('Buyer_Name', 'N/A')
        invoice_value = invoice_data.get('Invoice_Value', 'N/A')
        total_taxable = invoice_data.get('Total_Taxable_Value', 'N/A')
        total_gst = invoice_data.get('Total_GST', 'N/A')
        
        success_message = f"""
✅ INVOICE PROCESSED SUCCESSFULLY!

📄 Invoice Details:
• Invoice No: {invoice_no}
• Date: {invoice_date}
• Seller: {seller_name}
• Buyer: {buyer_name}

📦 Line Items: {len(line_items)} items extracted

💰 GST Summary:
• Invoice Value: Rs.{invoice_value}
• Taxable Amount: Rs.{total_taxable}
• Total GST: Rs.{total_gst}
"""
        
        igst = invoice_data.get('IGST_Total', '')
        cgst = invoice_data.get('CGST_Total', '')
        sgst = invoice_data.get('SGST_Total', '')
        
        if igst:
            success_message += f"  - IGST: Rs.{igst}\n"
        if cgst:
            success_message += f"  - CGST: Rs.{cgst}\n"
        if sgst:
            success_message += f"  - SGST: Rs.{sgst}\n"
        
        validation_status = validation_result.get('status', 'UNKNOWN')
        success_message += f"\n✔️ Validation: {validation_status}\n"
        
        if corrections:
            success_message += f"\n📝 Corrections Applied: {len(corrections)} field(s)\n"
        
        if is_duplicate_override:
            success_message += "\n⚠️ Saved as Duplicate Override\n"
        
        if audit_data:
            processing_time = audit_data.get('Processing_Time_Seconds', 0)
            success_message += f"\n⏱️ Processing time: {processing_time:.1f}s\n"
        
        success_message += "\n✅ Data has been appended to Google Sheets!"
        
        return success_message
    
    async def done_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /done command - process all collected images"""
        user_id = update.effective_user.id
        session = self._get_user_session(user_id)
        
        if not session['images'] and not session.get('batch'):
            await update.message.reply_text(
                "❌ No images to process!\n"
                "Send invoice images first, then type /done"
            )
            return
        
        # Tier 3: Check if this is a batch processing request
        if session.get('batch') or (session['images'] and len(session.get('batch', [])) > 0):
            batch_processed = await self.tier3_handlers.process_batch(update, user_id, session)
            if batch_processed:
                return
        
        # Single invoice processing
        if not session['images']:
            await update.message.reply_text(
                "❌ No images to process!\n"
                "Send invoice images first, then type /done"
            )
            return
        
        image_paths = session['images']
        session['start_time'] = datetime.now()
        
        await update.message.reply_text(
            f"⏳ Processing {len(image_paths)} page(s)...\n"
            "This may take a moment. Please wait."
        )
        
        try:
            # Step 1: OCR - Extract text from all images
            await update.message.reply_text("📄 Step 1/4: Extracting text from images...")
            ocr_start_time = datetime.now()
            
            ocr_result = self.ocr_engine.extract_text_from_images(image_paths)
            
            # Handle both old (str) and new (dict) return types for backward compatibility
            if isinstance(ocr_result, dict):
                ocr_text = ocr_result['text']
                # ═══════════════════════════════════════════════════════
                # NEW: Store OCR metadata for background tracking (Phase 2)
                # ═══════════════════════════════════════════════════════
                if config.ENABLE_USAGE_TRACKING and 'pages_metadata' in ocr_result:
                    session['_ocr_metadata'] = {
                        'pages': ocr_result['pages_metadata'],
                        'ocr_time_seconds': (datetime.now() - ocr_start_time).total_seconds()
                    }
                # ═══════════════════════════════════════════════════════
            else:
                # Backward compatibility: old code returned string directly
                ocr_text = ocr_result
            
            session['ocr_text'] = ocr_text
            
            # Step 2: Parse GST data with Tier 1 (line items + validation)
            await update.message.reply_text("🔍 Step 2/4: Parsing invoice and line items...")
            parsing_start_time = datetime.now()
            
            result = self.gst_parser.parse_invoice_with_validation(ocr_text)
            
            parsing_time_seconds = (datetime.now() - parsing_start_time).total_seconds()
            
            # ═══════════════════════════════════════════════════════
            # NEW: Store parsing metadata (Phase 2)
            # ═══════════════════════════════════════════════════════
            if config.ENABLE_USAGE_TRACKING:
                session['_parsing_metadata'] = {
                    'parsing_time_seconds': parsing_time_seconds,
                    'ocr_text_length': len(ocr_text)
                }
            # ═══════════════════════════════════════════════════════
            
            invoice_data = result['invoice_data']
            line_items = result['line_items']
            validation_result = result['validation_result']
            
            session['data'] = {
                'invoice_data': invoice_data,
                'line_items': line_items,
                'line_items_data': self.gst_parser.line_item_extractor.format_items_for_sheets(line_items)
            }
            session['validation_result'] = validation_result
            
            # Step 3: Tier 2 - Confidence Scoring
            if config.ENABLE_CONFIDENCE_SCORING and self.confidence_scorer:
                confidence_scores = self.confidence_scorer.score_fields(
                    invoice_data,
                    line_items,
                    validation_result,
                    ocr_text
                )
                session['confidence_scores'] = confidence_scores
            else:
                session['confidence_scores'] = {}
            
            # Step 4: Tier 2 - Check if review is needed
            if config.ENABLE_MANUAL_CORRECTIONS and self.correction_manager:
                needs_review = self.correction_manager.needs_review(
                    session['confidence_scores'],
                    validation_result,
                    config.CONFIDENCE_THRESHOLD_REVIEW
                )
                
                if needs_review:
                    session['state'] = 'reviewing'
                    review_msg = self.correction_manager.generate_review_message(
                        invoice_data,
                        session['confidence_scores'],
                        validation_result,
                        config.CONFIDENCE_THRESHOLD_REVIEW
                    )
                    await update.message.reply_text(review_msg)
                    return
            
            # Step 5: Tier 2 - Deduplication Check (warn-only mode)
            if config.ENABLE_DEDUPLICATION and self.dedup_manager:
                fingerprint = self.dedup_manager.generate_fingerprint(invoice_data)
                session['fingerprint'] = fingerprint
                
                is_duplicate, existing_invoice = self.sheets_manager.check_duplicate_advanced(fingerprint)
                
                if is_duplicate:
                    # Mark as duplicate but don't block - warn-only mode
                    session['is_duplicate'] = True
                    session['duplicate_info'] = existing_invoice
                    
                    # Show brief warning
                    warning_msg = self.dedup_manager.format_duplicate_warning_brief(
                        invoice_data,
                        existing_invoice
                    )
                    await update.message.reply_text(warning_msg)
                    
                    # Log the duplicate attempt
                    print(f"[DUPLICATE] Invoice {invoice_data.get('Invoice_No', 'unknown')} detected as duplicate but saving anyway (warn-only mode)")
            
            # No review needed - proceed to save (even if duplicate)
            await update.message.reply_text("✅ Step 3/4: Validation complete...")
            await self._save_invoice_to_sheets(update, user_id, session)
            
        except Exception as e:
            error_message = f"""
❌ Processing Failed!

Error: {str(e)}

Please try again or contact support if the issue persists.
"""
            await update.message.reply_text(error_message)
            print(f"Error processing invoice for user {user_id}: {str(e)}")
    
    # ═══════════════════════════════════════════════════════════════════
    # Epic 2: ORDER UPLOAD COMMANDS (Feature-Flagged)
    # ═══════════════════════════════════════════════════════════════════
    
    async def order_submit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /order_submit command - process uploaded order pages"""
        if not config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            await update.message.reply_text("⚠️ Order upload feature is not enabled.")
            return
        
        user_id = update.effective_user.id
        
        # Check if user has an active order session
        if user_id not in self.order_sessions:
            await update.message.reply_text(
                "❌ No active order session.\n\n"
                "Click 📦 Upload Order from the main menu to start."
            )
            return
        
        order_session = self.order_sessions[user_id]
        
        # Submit the order
        if not order_session.submit():
            await update.message.reply_text(
                "❌ Cannot submit order.\n\n"
                "Please upload at least one page, or the order is already submitted."
            )
            return
        
        await update.message.reply_text(
            f"✅ Order submitted!\n\n"
            f"📄 Order ID: {order_session.order_id}\n"
            f"📄 Pages: {len(order_session.pages)}\n\n"
            f"Processing your order... This may take a moment."
        )
        
        # Process the order asynchronously
        try:
            await self.order_orchestrator.process_order(order_session, update)
        except Exception as e:
            print(f"[ERROR] Order processing failed: {e}")
            await update.message.reply_text(
                f"❌ Order processing failed: {str(e)}\n\n"
                f"Please try again or contact support."
            )
        finally:
            # Clean up session
            if user_id in self.order_sessions:
                del self.order_sessions[user_id]
    
    async def handle_order_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle order photo uploads (separate from invoice photos)"""
        if not config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            return  # Silently ignore if feature disabled
        
        user_id = update.effective_user.id
        
        # Check if user has an active order session
        if user_id not in self.order_sessions:
            # Not in order mode, let normal invoice handler take care of it
            return
        
        order_session = self.order_sessions[user_id]
        
        # Check max images
        if len(order_session.pages) >= config.MAX_IMAGES_PER_ORDER:
            await update.message.reply_text(
                f"⚠️ Maximum {config.MAX_IMAGES_PER_ORDER} pages per order.\n"
                f"Type /order_submit to process or /cancel to start over."
            )
            return
        
        # Download photo
        photo = update.message.photo[-1]
        
        try:
            file = await photo.get_file()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"order_{user_id}_{timestamp}.jpg"
            filepath = os.path.join(config.TEMP_FOLDER, filename)
            
            await file.download_to_drive(filepath)
            
            # Add page to order session
            page_number = order_session.add_page(filepath)
            
            await update.message.reply_text(
                f"✅ Page {page_number} received!\n\n"
                f"Send more pages or type /order_submit to process."
            )
            
        except Exception as e:
            print(f"[ERROR] Order photo download failed: {e}")
            await update.message.reply_text(
                f"❌ Failed to download image: {str(e)}\n"
                f"Please try again."
            )
    
    # ═══════════════════════════════════════════════════════════════════
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming photo messages"""
        user_id = update.effective_user.id
        
        # ═══════════════════════════════════════════════════════════════════
        # Epic 2: Check if this is an order photo (Feature-Flagged)
        # ═══════════════════════════════════════════════════════════════════
        if config.FEATURE_ORDER_UPLOAD_NORMALIZATION and user_id in self.order_sessions:
            # This is an order photo, not an invoice photo
            await self.handle_order_photo(update, context)
            return
        # ═══════════════════════════════════════════════════════════════════
        
        # Normal GST invoice photo handling
        session = self._get_user_session(user_id)
        
        if session['state'] != 'uploading':
            await update.message.reply_text(
                "⚠️ Please complete the current action first.\n"
                "Use /cancel to start over."
            )
            return
        
        if len(session['images']) >= config.MAX_IMAGES_PER_INVOICE:
            await update.message.reply_text(
                f"⚠️ Maximum {config.MAX_IMAGES_PER_INVOICE} images per invoice.\n"
                f"Type /done to process or /cancel to start over."
            )
            return
        
        photo = update.message.photo[-1]
        
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                file = await photo.get_file()
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"invoice_{user_id}_{timestamp}.jpg"
                filepath = os.path.join(config.TEMP_FOLDER, filename)
                
                await file.download_to_drive(filepath)
                
                session['images'].append(filepath)
                
                page_count = len(session['images'])
                
                await update.message.reply_text(
                    f"✅ Page {page_count} received!\n\n"
                    f"Send more pages or type /done to process."
                )
                return  # Success - exit retry loop
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count < max_retries:
                    # Wait before retry (exponential backoff)
                    import asyncio
                    wait_time = 2 ** retry_count
                    print(f"[WARNING] Photo download failed (attempt {retry_count}/{max_retries}), retrying in {wait_time}s: {str(e)}")
                    await asyncio.sleep(wait_time)
                else:
                    # All retries failed
                    error_msg = str(last_error)
                    if "Timed out" in error_msg or "timeout" in error_msg.lower():
                        await update.message.reply_text(
                            f"❌ Download timed out after {max_retries} attempts.\n\n"
                            f"Please check your internet connection and try again."
                        )
                    else:
                        await update.message.reply_text(
                            f"❌ Failed to download image: {error_msg}\n"
                            f"Please try again."
                        )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document messages - accept images sent as files"""
        user_id = update.effective_user.id
        session = self._get_user_session(user_id)
        
        if session['state'] not in ['uploading', 'reviewing', 'correcting', 'confirming_duplicate']:
            await update.message.reply_text(
                "Please finish your current operation first."
            )
            return
        
        document = update.message.document
        mime_type = document.mime_type or ''
        file_name = document.file_name or ''
        
        is_image = (
            mime_type.startswith('image/') or 
            file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
        )
        
        if is_image:
            max_retries = 3
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    # Get file metadata from Telegram
                    file = await context.bot.get_file(document.file_id)
                    
                    os.makedirs(config.TEMP_FOLDER, exist_ok=True)
                    
                    file_path = os.path.join(config.TEMP_FOLDER, f"{user_id}_{len(session['images'])}_{file_name}")
                    
                    # Download with explicit timeout handling
                    await file.download_to_drive(file_path)
                    
                    session['images'].append(file_path)
                    session['state'] = 'uploading'
                    
                    page_count = len(session['images'])
                    
                    await update.message.reply_text(
                        f"✅ Page {page_count} received!\n\n"
                        f"Send more pages or type /done to process."
                    )
                    return  # Success - exit retry loop
                    
                except Exception as e:
                    last_error = e
                    retry_count += 1
                    
                    if retry_count < max_retries:
                        # Wait before retry (exponential backoff: 2s, 4s)
                        import asyncio
                        wait_time = 2 ** retry_count
                        print(f"[WARNING] Download failed (attempt {retry_count}/{max_retries}), retrying in {wait_time}s: {str(e)}")
                        await asyncio.sleep(wait_time)
                    else:
                        # All retries failed
                        error_msg = str(last_error)
                        if "Timed out" in error_msg or "timeout" in error_msg.lower():
                            await update.message.reply_text(
                                f"❌ Download timed out after {max_retries} attempts.\n\n"
                                f"This image may be too large or your connection is slow.\n"
                                f"Try:\n"
                                f"• Send as photo (not file) for faster processing\n"
                                f"• Use a smaller/compressed image\n"
                                f"• Check your internet connection"
                            )
                        else:
                            await update.message.reply_text(
                                f"❌ Failed to download image: {error_msg}\n\n"
                                f"Please try again or contact support."
                            )
        else:
            await update.message.reply_text(
                "PDF support coming soon!\n"
                "Please send images (JPG/PNG) for now.\n\n"
                "Tip: You can also send images as photos (not files) for faster processing."
            )
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle random text messages and correction input"""
        user_id = update.effective_user.id
        session = self._get_user_session(user_id)
        
        # Tier 3: Check if this is an export command interaction
        if await self.tier3_handlers.handle_export_interaction(update, context):
            return
        
        # Check if user is in correction mode
        if session['state'] == 'correcting' and config.ENABLE_MANUAL_CORRECTIONS:
            result = self.correction_manager.parse_correction_input(update.message.text)
            
            if result:
                field_name, new_value = result
                session['corrections'][field_name] = new_value
                
                await update.message.reply_text(
                    f"✅ Updated: {field_name} = {new_value}\n\n"
                    f"Continue editing or:\n"
                    f"/done - Save with corrections\n"
                    f"/cancel - Discard changes"
                )
            else:
                await update.message.reply_text(
                    "⚠️ Invalid format. Use: field_name = value\n\n"
                    "Example: buyer_gstin = 29AAAAA0000A1Z5"
                )
            return
        
        # Check if user typed /done as correction confirm
        if session['state'] == 'correcting' and update.message.text.strip().lower() == '/done':
            await self._save_invoice_to_sheets(update, user_id, session)
            return
        
        # Default response
        await update.message.reply_text(
            "👋 Send me invoice images to get started!\n"
            "Type /help for instructions."
        )
    
    def run(self):
        """Start the bot"""
        # Build application with increased timeouts for large file downloads
        application = (
            Application.builder()
            .token(config.TELEGRAM_BOT_TOKEN)
            .read_timeout(30)  # Increase read timeout to 30 seconds
            .write_timeout(30)  # Increase write timeout to 30 seconds
            .connect_timeout(30)  # Increase connection timeout to 30 seconds
            .build()
        )
        
        async def post_init(app):
            await setup_bot_commands(app)
        
        application.post_init = post_init
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("menu", self.menu_command))
        application.add_handler(CommandHandler("upload", self.upload_command))
        application.add_handler(CommandHandler("generate", self.generate_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("done", self.done_command))
        application.add_handler(CommandHandler("cancel", self.cancel_command))
        
        # Tier 2 command handlers
        if config.ENABLE_MANUAL_CORRECTIONS:
            application.add_handler(CommandHandler("confirm", self.confirm_command))
            application.add_handler(CommandHandler("correct", self.correct_command))
        if config.ENABLE_DEDUPLICATION:
            application.add_handler(CommandHandler("override", self.override_command))
        
        # Tier 3 command handlers
        application.add_handler(CommandHandler("next", self.tier3_handlers.next_command))
        application.add_handler(CommandHandler("export_gstr1", self.tier3_handlers.export_gstr1_command))
        application.add_handler(CommandHandler("export_gstr3b", self.tier3_handlers.export_gstr3b_command))
        application.add_handler(CommandHandler("reports", self.tier3_handlers.reports_command))
        application.add_handler(CommandHandler("stats", self.tier3_handlers.stats_command))
        
        # ═══════════════════════════════════════════════════════
        # Epic 2: Order Upload command handlers (Feature-Flagged)
        # ═══════════════════════════════════════════════════════
        if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            application.add_handler(CommandHandler("order_submit", self.order_submit_command))
            print("[OK] Epic 2: Order upload commands registered")
        # ═══════════════════════════════════════════════════════
        
        # Add callback query handler for inline buttons
        application.add_handler(CallbackQueryHandler(self.handle_menu_callback))
        
        # Add message handlers
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        # Start the bot
        print("="*80)
        print("GST SCANNER BOT STARTED")
        print("="*80)
        print(f"Bot is running and ready to receive invoices...")
        print(f"Temp folder: {config.TEMP_FOLDER}")
        print("="*80)
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point"""
    try:
        config.validate_config()
        print("[OK] Configuration validated")
        
        bot = GSTScannerBot()
        bot.run()
        
    except Exception as e:
        print(f"[FAIL] Failed to start bot: {str(e)}")
        raise


if __name__ == "__main__":
    main()
