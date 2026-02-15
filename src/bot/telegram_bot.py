"""
Telegram Bot for GST Invoice Scanner
Handles user interactions and orchestrates the invoice processing workflow
"""
import os
import sys
import asyncio
from datetime import datetime

print("[STARTUP] Starting imports...", flush=True)

# Fix encoding for Windows PowerShell
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
print("[STARTUP] Telegram imports done", flush=True)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
print("[STARTUP] Telegram.ext imports done", flush=True)
from typing import List, Dict, Optional
import config
print("[STARTUP] Config imported", flush=True)
from ocr.ocr_engine import OCREngine
print("[STARTUP] OCR engine imported", flush=True)
from parsing.gst_parser import GSTParser
print("[STARTUP] GST parser imported", flush=True)
from sheets.sheets_manager import SheetsManager
print("[STARTUP] Sheets manager imported", flush=True)

# Tier 2 imports
print("[STARTUP] Starting tier 2 imports...", flush=True)
if config.ENABLE_CONFIDENCE_SCORING:
    from features.confidence_scorer import ConfidenceScorer
if config.ENABLE_MANUAL_CORRECTIONS:
    from features.correction_manager import CorrectionManager
if config.ENABLE_DEDUPLICATION:
    from features.dedup_manager import DeduplicationManager
if config.ENABLE_AUDIT_LOGGING:
    from features.audit_logger import AuditLogger

# Tier 3 imports
print("[STARTUP] Starting tier 3 imports...", flush=True)
from commands.tier3_commands import Tier3CommandHandlers
print("[STARTUP] Tier 3 imports done", flush=True)

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
        BotCommand("start", "Start bot & show main menu"),
        BotCommand("upload", "Purchase Order"),
        BotCommand("generate", "Generate GST reports"),
        BotCommand("cancel", "Cancel current operation"),
        BotCommand("help", "Help & guide"),
    ]
    
    # Add Epic 2 commands if feature enabled (only primary action, not derived ones)
    if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
        commands.insert(2, BotCommand("order_upload", "Sales Order"))
    
    # Epic 3: Subscribe command (always available)
    commands.append(BotCommand("subscribe", "Manage subscription plan"))
    
    await application.bot.set_my_commands(commands)
    print("[OK] Bot commands menu configured", flush=True)
    print(f"[OK] Menu commands: {[c.command for c in commands]}", flush=True)


class GSTScannerBot:
    """Telegram Bot for GST Invoice Scanning"""
    
    def __init__(self):
        """Initialize the bot and its components"""
        self.ocr_engine = OCREngine()
        self.gst_parser = GSTParser()
        # Lazy initialization for SheetsManager to prevent slow startup
        self.sheets_manager = None  # Will be initialized on first use
        
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
            self.order_orchestrator = None  # Lazy initialization - created on first use
            self.order_sessions = {}  # Separate from GST invoice sessions
            print("[OK] Epic 2: Order processing enabled (lazy init)")
        else:
            self.order_orchestrator = None
            self.order_sessions = {}
        # ═══════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════
        # Tenant Management (lazy init on first /start)
        # ═══════════════════════════════════════════════════════
        self.tenant_manager = None
        self.pending_email_users = {}  # {user_id: {'first_name': ..., 'username': ...}}
        # ═══════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════
        # Epic 3: Per-tenant SheetsManager cache
        # ═══════════════════════════════════════════════════════
        self._tenant_sheets_cache = {}  # {sheet_id: SheetsManager}
        # ═══════════════════════════════════════════════════════

    
    def _ensure_sheets_manager(self, sheet_id: str = None):
        """Lazy initialize SheetsManager on first use.

        Args:
            sheet_id: Optional per-tenant sheet ID (Epic 3). When provided and
                      FEATURE_TENANT_SHEET_ISOLATION is ON, returns a tenant-specific
                      SheetsManager. Otherwise returns the shared instance.
        """
        if not config.FEATURE_TENANT_SHEET_ISOLATION:
            # Feature OFF: original behaviour -- single shared manager
            if self.sheets_manager is None:
                self.sheets_manager = SheetsManager()
                print("[OK] SheetsManager initialized (lazy)")
            return

        # Feature ON: per-tenant routing via cache (None key = shared)
        cache_key = sheet_id  # None means shared sheet
        if cache_key not in self._tenant_sheets_cache:
            self._tenant_sheets_cache[cache_key] = SheetsManager(sheet_id=sheet_id)
            if sheet_id:
                print(f"[OK] Tenant SheetsManager initialized for sheet {sheet_id[:12]}...")
            else:
                print("[OK] SheetsManager initialized (shared, tenant isolation ON)")
        self.sheets_manager = self._tenant_sheets_cache[cache_key]

    def _get_tenant_sheet_id(self, user_id: int):
        """Get tenant-specific sheet ID if feature is enabled (Epic 3).

        Returns:
            Sheet ID string or None (falls back to shared sheet).
        """
        if not config.FEATURE_TENANT_SHEET_ISOLATION:
            return None
        self._ensure_tenant_manager()
        if self.tenant_manager:
            try:
                return self.tenant_manager.get_tenant_sheet_id(user_id)
            except Exception as e:
                print(f"[WARNING] Could not get tenant sheet_id for {user_id}: {e}")
        return None
    
    def _ensure_tenant_manager(self):
        """Lazy initialize TenantManager on first use"""
        if self.tenant_manager is None:
            try:
                from utils.tenant_manager import TenantManager
                self.tenant_manager = TenantManager()
                print("[OK] TenantManager initialized (lazy)")
            except Exception as e:
                print(f"[WARNING] TenantManager init failed: {e}")
                self.tenant_manager = None
    
    async def _check_registration_pending(self, update: Update) -> bool:
        """Check if user has a pending registration or is not registered at all.
        Returns True if blocked (user must complete registration first)."""
        user_id = update.effective_user.id
        user = update.effective_user

        # Case 1: Already in the middle of registration
        if user_id in self.pending_email_users:
            info = self.pending_email_users[user_id]
            if info.get('needs_name'):
                await update.message.reply_text(
                    "⚠️ Please complete registration first.\n\n"
                    "Send your name and email separated by a comma.\n"
                    "Example: John Doe, john@example.com"
                )
            else:
                await update.message.reply_text(
                    "⚠️ Please complete registration first.\n\n"
                    "Send your email ID to continue:"
                )
            return True

        # Case 2: Not registered at all — start registration flow
        try:
            self._ensure_tenant_manager()
            if self.tenant_manager:
                tenant = self.tenant_manager.get_tenant(user_id)
                if not tenant:
                    # User has no tenant — initiate registration
                    tg_username = user.username or ''
                    tg_full_name = user.full_name or user.first_name or ''
                    self.pending_email_users[user_id] = {
                        'full_name': tg_full_name,
                        'username': tg_username,
                        'needs_name': not tg_username,
                    }
                    if tg_username:
                        await update.message.reply_text(
                            "📝 One-time registration required\n\n"
                            "Please share your email ID to complete registration:"
                        )
                    else:
                        await update.message.reply_text(
                            "📝 One-time registration required\n\n"
                            "Please share your name and email ID "
                            "(separated by a comma) to complete registration.\n\n"
                            "Example: John Doe, john@example.com"
                        )
                    return True
        except Exception as e:
            print(f"[WARNING] Tenant check failed in registration guard: {e}")
            # If tenant check fails, allow through to avoid blocking users
            # when the tenant service is unavailable

        return False
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - Show welcome message with main menu"""
        user = update.effective_user
        
        welcome_message = (
            f"Hey {user.first_name}! 👋\n"
            f"Welcome to GST Scanner Bot.\n"
            f"\n"
            f"📸 Purchase Orders — snap & organize\n"
            f"📦 Sales Orders — handwritten to digital\n"
            f"\n"
            f"Tap below to get started!"
        )
        
        # Check tenant registration
        try:
            self._ensure_tenant_manager()
            if self.tenant_manager:
                print(f"[TENANT] Looking up user_id={user.id} (type={type(user.id).__name__})", flush=True)
                tenant = self.tenant_manager.get_tenant(user.id)
                print(f"[TENANT] Lookup result: {tenant}", flush=True)
                if tenant:
                    # Existing user - show welcome + menu
                    await update.message.reply_text(
                        welcome_message,
                        reply_markup=self.create_main_menu_keyboard()
                    )
                    return
                else:
                    # New user - collect info
                    tg_username = user.username or ''
                    tg_full_name = user.full_name or user.first_name or ''
                    self.pending_email_users[user.id] = {
                        'full_name': tg_full_name,
                        'username': tg_username,
                        'needs_name': not tg_username,  # Ask for name if @username missing
                    }
                    await update.message.reply_text(welcome_message)
                    if tg_username:
                        await update.message.reply_text(
                            "📝 Quick Setup (one time only)\n\n"
                            "Just need your email to get you started.\n"
                            "Type it below:"
                        )
                    else:
                        await update.message.reply_text(
                            "📝 Quick Setup (one time only)\n\n"
                            "I just need your name and email to get started.\n"
                            "Type them separated by a comma.\n\n"
                            "Example: John Doe, john@example.com"
                        )
                    return
        except Exception as e:
            print(f"[WARNING] Tenant check failed, showing menu anyway: {e}")
        
        # Fallback: show menu without tenant check
        await update.message.reply_text(
            welcome_message,
            reply_markup=self.create_main_menu_keyboard()
        )
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command - Show main menu"""
        await update.message.reply_text(
            "What would you like to do? 👇",
            reply_markup=self.create_main_menu_keyboard()
        )
    
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /upload command - Start upload session"""
        if await self._check_registration_pending(update):
            return
        
        user_id = update.effective_user.id
        
        # Clear any stale order session to avoid routing conflicts
        if user_id in self.order_sessions:
            del self.order_sessions[user_id]
        
        # Initialize session
        self._get_user_session(user_id)
        self.user_sessions[user_id]['state'] = 'uploading'
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
        ])
        await update.message.reply_text(
            "📸 Ready to scan!\n\n"
            "Send me a photo of your invoice.\n"
            "Multi-page? Just send all pages one by one.\n\n"
            "I'll wait for all your images before processing.",
            reply_markup=keyboard
        )
    
    async def generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate command - Show generate submenu"""
        if await self._check_registration_pending(update):
            return
        await update.message.reply_text(
            "📊 Reports & Exports\n\n"
            "What do you need?",
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
        # ═══════════════════════════════════════════════════════
        # Purchase Order + Sales Order side by side
        # ═══════════════════════════════════════════════════════
        row = [InlineKeyboardButton("📸 Purchase Order", callback_data="menu_upload")]
        if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            row.append(InlineKeyboardButton("📦 Sales Order", callback_data="menu_order_upload"))
        keyboard = [row]
        # ═══════════════════════════════════════════════════════
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
        max_images = config.MAX_IMAGES_PER_INVOICE
        help_message = (
            "📚 How to Use GST Scanner Bot\n"
            "\n"
            "─────────────────────\n"
            "📸 INVOICES\n"
            "─────────────────────\n"
            "1. Tap Upload Invoice (or just send a photo)\n"
            "2. Send one or more pages (JPG/PNG)\n"
            "3. Tap Process Invoice — done!\n"
            f"\n"
            f"Up to {max_images} images per invoice.\n"
            "\n"
            "─────────────────────\n"
            "📦 HANDWRITTEN ORDERS\n"
            "─────────────────────\n"
            "1. Tap Sales Order from the menu\n"
            "2. Send photos of order notes\n"
            "3. Tap Submit Order for PDF generation\n"
            "\n"
            "─────────────────────\n"
            "💡 Tips for best results\n"
            "─────────────────────\n"
            "• Good lighting = better accuracy\n"
            "• Keep images clear and focused\n"
            "• Send all pages from the same document\n"
            "\n"
            "Questions? Contact your administrator."
        )
        
        await update.message.reply_text(
            help_message,
            reply_markup=self.create_main_menu_keyboard()
        )
    
    # ═══════════════════════════════════════════════════════════════════
    # Epic 3: /subscribe command -- subscription enrollment
    # ═══════════════════════════════════════════════════════════════════
    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /subscribe -- show available subscription tiers"""
        user_id = update.effective_user.id

        self._ensure_tenant_manager()
        if not self.tenant_manager:
            await update.message.reply_text(
                "Subscription service is currently unavailable. Please try again later."
            )
            return

        tenant = self.tenant_manager.get_tenant(user_id)
        if not tenant:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Get Started", callback_data="menu_main")]
            ])
            await update.message.reply_text(
                "You need to register first. Tap below to get started.",
                reply_markup=keyboard
            )
            return

        current_plan = tenant.get('subscription_plan', config.DEFAULT_SUBSCRIPTION_TIER)

        # Build inline keyboard with available tiers
        buttons = []
        for tier in config.SUBSCRIPTION_TIERS:
            label = tier['name']
            if tier['id'] == current_plan:
                label = f"{tier['name']} (current)"
            buttons.append([
                InlineKeyboardButton(
                    f"{label} -- {tier['description']}",
                    callback_data=f"subscribe_{tier['id']}"
                )
            ])
        buttons.append([InlineKeyboardButton("Back to Menu", callback_data="menu_main")])

        await update.message.reply_text(
            "Subscription Plans\n\n"
            f"Your current plan: {current_plan.title()}\n\n"
            "Select a plan:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    # ═══════════════════════════════════════════════════════════════════

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
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
            ])
            await query.edit_message_text(
                "📸 Upload Invoice\n\n"
                "Send me your invoice images (one or multiple pages).\n"
                "Tap Process Invoice when you've sent all pages.",
                reply_markup=keyboard
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
                    "Order upload isn't available yet. Contact your admin to enable it.",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            
            # Cancel any existing invoice session
            if user_id in self.user_sessions:
                print(f"[DEBUG] Clearing existing invoice session for user {user_id}")
                del self.user_sessions[user_id]
            
            # Start order upload session
            order_session = OrderSession(user_id, update.effective_user.username)
            self.order_sessions[user_id] = order_session
            print(f"[DEBUG] Created order session for user {user_id}")
            print(f"[DEBUG] order_sessions now contains: {list(self.order_sessions.keys())}")
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
            ])
            await query.edit_message_text(
                "📦 Sales Order (Handwritten Notes)\n\n"
                "✅ Ready to receive order pages!\n\n"
                "📌 INSTRUCTIONS\n"
                "1. Send me photos of handwritten order notes\n"
                "2. You can send multiple pages if the order spans multiple sheets\n"
                "3. Tap ✅ Submit Order when you've sent all pages\n\n"
                "I'll extract the line items, match with pricing, and generate a clean PDF.",
                reply_markup=keyboard
            )
        # ═══════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════
        # ORDER FORMAT CHOICE (PDF vs CSV)
        # ═══════════════════════════════════════════════════════
        elif callback_data in ("order_format_pdf", "order_format_csv"):
            output_format = "pdf" if callback_data == "order_format_pdf" else "csv"
            await query.edit_message_text(
                f"📋 Format selected: {output_format.upper()}\n\nProcessing..."
            )
            # Process the order with the chosen format
            await self._process_order_with_format(update, user_id, output_format)
            return
        
        # ═══════════════════════════════════════════════════════
        # INLINE ACTION BUTTONS (Submit / Process / Cancel / Next)
        # ═══════════════════════════════════════════════════════
        elif callback_data == "btn_order_submit":
            await query.edit_message_text("⏳ Submitting order...")
            # Check for active order session
            if config.FEATURE_ORDER_UPLOAD_NORMALIZATION and user_id in self.order_sessions:
                order_session = self.order_sessions[user_id]
                if not order_session.pages:
                    await query.edit_message_text("❌ No pages uploaded yet. Send photos first.")
                    return
                # Ask user for output format
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📄 PDF", callback_data="order_format_pdf"),
                        InlineKeyboardButton("📊 CSV", callback_data="order_format_csv"),
                    ]
                ])
                await query.edit_message_text(
                    f"📦 Ready to process your order!\n\n"
                    f"📄 Pages: {len(order_session.pages)}\n\n"
                    f"Choose output format:",
                    reply_markup=keyboard
                )
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 Sales Order", callback_data="menu_order_upload")]
                ])
                await query.edit_message_text(
                    "No order in progress.\n\nTap below to start one!",
                    reply_markup=keyboard
                )
            return
        
        elif callback_data == "btn_done":
            await query.edit_message_text("🔄 Starting invoice processing...")
            # Trigger the done command logic
            session = self._get_user_session(user_id)
            if not session['images']:
                await query.edit_message_text("Hmm, no images found. Send me a photo first!")
                return
            # Delegate to done_command — create a fake text message context
            await self.done_command(update, context)
            return
        
        elif callback_data == "btn_cancel":
            # Clear both order and invoice sessions
            cancelled = False
            if user_id in self.order_sessions:
                del self.order_sessions[user_id]
                cancelled = True
            if user_id in self.user_sessions:
                self._clear_user_session(user_id)
                cancelled = True
            if cancelled:
                await query.edit_message_text(
                    "All cleared! What's next? 👇",
                    reply_markup=self.create_main_menu_keyboard()
                )
            else:
                await query.edit_message_text(
                    "Nothing active to cancel.\n\n"
                    "What would you like to do?",
                    reply_markup=self.create_main_menu_keyboard()
                )
            return
        
        elif callback_data == "btn_confirm":
            # Save invoice as-is (from review screen)
            session = self._get_user_session(user_id)
            if session['state'] != 'reviewing':
                await query.edit_message_text(
                    "No invoice waiting for confirmation.\n\n"
                    "Start a new one?",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            # Keep the extracted details visible — append saving status and remove buttons
            current_text = query.message.text or ""
            await query.edit_message_text(
                current_text + "\n\n💾 Saving to Google Sheets..."
            )
            await self._save_invoice_to_sheets(update, user_id, session)
            return
        
        elif callback_data == "btn_correct":
            # Enter correction mode (from review screen)
            session = self._get_user_session(user_id)
            if session['state'] != 'reviewing':
                await query.edit_message_text(
                    "No invoice to correct right now.\n\n"
                    "What would you like to do?",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            session['state'] = 'correcting'
            instructions = self.correction_manager.generate_correction_instructions()
            correction_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💾 Save Corrections", callback_data="btn_save_corrections"),
                ],
                [
                    InlineKeyboardButton("↩️ Cancel Correction", callback_data="btn_cancel_correction"),
                    InlineKeyboardButton("🗑 Cancel & Resend", callback_data="btn_cancel_resend"),
                ]
            ])
            await query.edit_message_text(instructions, reply_markup=correction_keyboard)
            return
        
        elif callback_data == "btn_save_corrections":
            # Save invoice with corrections applied
            session = self._get_user_session(user_id)
            if session['state'] != 'correcting':
                await query.edit_message_text(
                    "No corrections in progress.\n\n"
                    "What would you like to do?",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            correction_count = len(session.get('corrections', {}))
            # Keep the correction instructions visible — append saving status and remove buttons
            current_text = query.message.text or ""
            await query.edit_message_text(
                current_text + f"\n\n💾 Applying {correction_count} correction(s) and saving..."
            )
            await self._save_invoice_to_sheets(update, user_id, session)
            return
        
        elif callback_data == "btn_cancel_correction":
            # Cancel correction mode only - go back to review screen with extracted data
            session = self._get_user_session(user_id)
            if session['state'] == 'correcting':
                # Discard any corrections made, go back to reviewing
                session['corrections'] = {}
                session['state'] = 'reviewing'
                
                # Re-show the review message with buttons
                invoice_data = session['data']['invoice_data']
                review_msg = self.correction_manager.generate_review_message(
                    invoice_data,
                    session.get('confidence_scores', {}),
                    session.get('validation_result', {}),
                    config.CONFIDENCE_THRESHOLD_REVIEW
                )
                review_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Save As-Is", callback_data="btn_confirm"),
                        InlineKeyboardButton("✏️ Make Corrections", callback_data="btn_correct"),
                    ],
                    [
                        InlineKeyboardButton("🗑 Cancel & Resend New Images", callback_data="btn_cancel_resend"),
                    ]
                ])
                await query.edit_message_text(review_msg, reply_markup=review_keyboard)
            else:
                await query.edit_message_text(
                    "No correction in progress.\n\n"
                    "What would you like to do?",
                    reply_markup=self.create_main_menu_keyboard()
                )
            return
        
        elif callback_data == "btn_cancel_resend":
            # Full cancel - clear everything so user can resend new images
            if user_id in self.order_sessions:
                del self.order_sessions[user_id]
            if user_id in self.user_sessions:
                self._clear_user_session(user_id)
            
            upload_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📸 Upload Invoice", callback_data="menu_upload"),
                    InlineKeyboardButton("📦 Sales Order", callback_data="menu_order_upload"),
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await query.edit_message_text(
                "🗑 Invoice discarded — fresh start!\n\n"
                "Ready to try again?",
                reply_markup=upload_keyboard
            )
            return
        
        elif callback_data == "menu_upload":
            await query.edit_message_text(
                "📸 Ready to scan!\n\n"
                "Send me a photo of your invoice.\n"
                "Multi-page? Just send all pages one by one.\n\n"
                "I'll wait for all your images before processing."
            )
            return
        
        elif callback_data == "menu_help":
            await query.edit_message_text(
                "Need a hand? Here's a quick overview:\n\n"
                "📸 Upload Invoice — Send photos, I extract GST data\n"
                "📦 Sales Order — Send handwritten orders for PDF\n"
                "📊 Generate — GSTR-1, GSTR-3B, reports & stats\n\n"
                "The fastest way to start? Just send me a photo!",
                reply_markup=self.create_main_menu_keyboard()
            )
            return
        
        elif callback_data == "menu_main":
            await query.edit_message_text(
                "What would you like to do? 👇",
                reply_markup=self.create_main_menu_keyboard()
            )
            return
        
        elif callback_data == "btn_next":
            # Batch mode: save current invoice and start next
            session = self._get_user_session(user_id)
            if session.get('images'):
                if not session.get('batch'):
                    session['batch'] = []
                session['batch'].append(session['images'][:])
                session['images'] = []
                batch_num = len(session['batch']) + 1
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⏭ Next Invoice", callback_data="btn_next"),
                        InlineKeyboardButton("✅ Process All", callback_data="btn_done"),
                    ],
                    [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
                ])
                await query.edit_message_text(
                    f"Invoice {len(session['batch'])} queued!\n\n"
                    f"Now send pages for invoice #{batch_num}.\n"
                    f"When you're done with all invoices, tap Process All.",
                    reply_markup=keyboard
                )
            else:
                await query.edit_message_text("No pages yet — send me some photos first!")
            return
        # ═══════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════
        # Epic 3: SUBSCRIPTION TIER SELECTION
        # ═══════════════════════════════════════════════════════
        elif callback_data.startswith("subscribe_"):
            tier_id = callback_data[len("subscribe_"):]
            self._ensure_tenant_manager()
            if self.tenant_manager:
                success = self.tenant_manager.update_subscription(user_id, tier_id)
                if success:
                    tier_name = tier_id.title()
                    for tier in config.SUBSCRIPTION_TIERS:
                        if tier['id'] == tier_id:
                            tier_name = tier['name']
                            break
                    await query.edit_message_text(
                        f"✅ Subscription updated to {tier_name}!\n\n"
                        "What would you like to do next?",
                        reply_markup=self.create_main_menu_keyboard()
                    )
                else:
                    await query.edit_message_text(
                        "😕 Couldn't update your subscription.\n\n"
                        "Please try again.",
                        reply_markup=self.create_main_menu_keyboard()
                    )
            else:
                await query.edit_message_text(
                    "😕 Subscription service is temporarily unavailable.",
                    reply_markup=self.create_main_menu_keyboard()
                )
            return
        # ═══════════════════════════════════════════════════════

        # ═══════════════════════════════════════════════════════
        # UPLOAD SUBMENU ACTIONS
        # ═══════════════════════════════════════════════════════
        
        elif callback_data == "upload_single":
            session = self._get_user_session(user_id)
            session['state'] = 'uploading'
            session['images'] = []
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
            ])
            await query.edit_message_text(
                "📸 Ready to scan!\n\n"
                "Send me your invoice photo(s).\n"
                "Multi-page? Send all pages — I'll combine them.\n\n"
                "Tap ✅ Process Invoice when you're done.",
                reply_markup=keyboard
            )
        
        elif callback_data == "upload_batch":
            session = self._get_user_session(user_id)
            session['state'] = 'uploading'
            session['images'] = []
            session['batch'] = []
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⏭ Next Invoice", callback_data="btn_next"),
                    InlineKeyboardButton("✅ Process All", callback_data="btn_done"),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
            ])
            await query.edit_message_text(
                "📦 Batch mode — ready for multiple invoices!\n\n"
                "1. Send pages for the first invoice\n"
                "2. Tap ⏭ Next Invoice\n"
                "3. Repeat for each invoice\n"
                "4. Tap ✅ Process All when done\n\n"
                "Great for processing several invoices at once.",
                reply_markup=keyboard
            )
        
        elif callback_data == "upload_document":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
            ])
            await query.edit_message_text(
                "📎 Upload from Document\n\n"
                "You can send invoices as:\n"
                "• Image files (JPG, PNG)\n"
                "• Documents (right now)\n"
                "• PDF files (coming soon!)\n\n"
                "Just send your file and I'll process it.\n"
                "Tap Process Invoice when finished.",
                reply_markup=keyboard
            )
        
        # ═══════════════════════════════════════════════════════
        # GENERATE SUBMENU ACTIONS
        # ═══════════════════════════════════════════════════════
        
        elif callback_data == "gen_gstr1":
            session = self._get_user_session(user_id)
            session['export_command'] = 'gstr1'
            session['export_step'] = 'month'
            await query.edit_message_text(
                "📄 GSTR-1 Export\n\n"
                "Enter the month (1-12):"
            )
        
        elif callback_data == "gen_gstr3b":
            session = self._get_user_session(user_id)
            session['export_command'] = 'gstr3b'
            session['export_step'] = 'month'
            await query.edit_message_text(
                "📋 GSTR-3B Summary\n\n"
                "Enter the month (1-12):"
            )
        
        elif callback_data == "gen_reports":
            session = self._get_user_session(user_id)
            session['export_command'] = 'reports'
            session['export_step'] = 'type'
            await query.edit_message_text(
                "📈 Operational Reports\n\n"
                "Select report type:\n"
                "1️⃣ Processing Statistics\n"
                "2️⃣ GST Summary (monthly)\n"
                "3️⃣ Duplicate Attempts\n"
                "4️⃣ Correction Analysis\n"
                "5️⃣ Comprehensive Report\n\n"
                "Reply with number (1-5):"
            )
        
        elif callback_data == "gen_stats":
            await query.edit_message_text("📊 Generating statistics...")
            try:
                result = self.tier3_handlers.reporter.generate_processing_stats()
                if result['success']:
                    message = "📊 PROCESSING STATISTICS\n\n"
                    message += f"Total Invoices: {result['total_invoices']}\n\n"
                    message += "VALIDATION STATUS\n"
                    for status, count in result['status_breakdown'].items():
                        pct = result['status_percentages'].get(status, 0)
                        message += f"  {status}: {count} ({pct:.1f}%)\n"
                    if result['top_errors']:
                        message += "\n⚠️ TOP ERRORS\n"
                        for error in result['top_errors'][:3]:
                            message += f"  • {error['type']}: {error['count']}\n"
                    await query.message.reply_text(message)
                else:
                    await query.message.reply_text(f"❌ {result['message']}")
            except Exception as e:
                await query.message.reply_text(f"❌ Error: {str(e)}")
        
        # ═══════════════════════════════════════════════════════
        # HELP SUBMENU ACTIONS
        # ═══════════════════════════════════════════════════════
        
        elif callback_data == "help_start":
            help_text = (
                "🚀 Getting Started\n"
                "\n"
                "It's simple — just 4 steps:\n"
                "\n"
                "1️⃣  Send me a photo of your invoice\n"
                "2️⃣  Tap Process Invoice when ready\n"
                "3️⃣  Review what I extracted\n"
                "4️⃣  Save — it goes straight to your Google Sheet\n"
                "\n"
                "─────────────────────\n"
                "What I extract automatically:\n"
                "  • Invoice number & date\n"
                "  • Seller & buyer details\n"
                "  • GST breakup (CGST/SGST/IGST)\n"
                "  • Line items with HSN codes\n"
                "\n"
                "─────────────────────\n"
                "Tips for best results:\n"
                "  📸  Clear, well-lit photos\n"
                "  📄  Include all pages of multi-page invoices\n"
                "  🔍  Make sure GST numbers are visible\n"
                "\n"
                "Ready to try?"
            )
            keyboard = [
                [InlineKeyboardButton("📤 Upload First Invoice", callback_data="upload_single")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu_help")]
            ]
            await query.edit_message_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif callback_data == "help_upload":
            help_text = (
                "📸 Upload Guide\n"
                "\n"
                "Single invoice:\n"
                "  1. Send your invoice photo(s)\n"
                "  2. Tap ✅ Process Invoice — done!\n"
                "\n"
                "Batch mode (multiple invoices):\n"
                "  1. Send pages for the first invoice\n"
                "  2. Tap ⏭ Next Invoice\n"
                "  3. Repeat for each invoice\n"
                "  4. Tap ✅ Process All when finished\n"
                "\n"
                "─────────────────────\n"
                "Supported: JPG, JPEG, PNG\n"
                "Coming soon: PDF\n"
                "Max: 10 images per invoice\n"
                "─────────────────────\n"
                "\n"
                "For multi-page invoices, just send all\n"
                "pages before tapping Process."
            )
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_help_submenu()
            )
        
        elif callback_data == "help_corrections":
            if not config.ENABLE_MANUAL_CORRECTIONS:
                await query.edit_message_text(
                    "✏️ Corrections are not enabled right now.\n\n"
                    "Contact your administrator to turn this on.",
                    reply_markup=self.create_help_submenu()
                )
            else:
                help_text = (
                    "✏️ Corrections Guide\n"
                    "\n"
                    "After extraction, I'll show you the data.\n"
                    "You can review and fix anything before saving.\n"
                    "\n"
                    "I'll flag fields that may need attention\n"
                    "(low confidence or validation issues).\n"
                    "\n"
                    "─────────────────────\n"
                    "How it works:\n"
                    "  1. Tap ✏️ Make Corrections\n"
                    "  2. Type: field_name = new_value\n"
                    "  3. Tap 💾 Save when done\n"
                    "\n"
                    "Example:\n"
                    "  buyer_gstin = 29AAAAA0000A1Z5\n"
                    "─────────────────────\n"
                    "\n"
                    "Your buttons:\n"
                    "  ✅  Save As-Is — keep data as extracted\n"
                    "  ✏️  Make Corrections — edit fields\n"
                    "  💾  Save Corrections — save edits\n"
                    "  ↩️  Cancel Correction — go back to review\n"
                    "  🗑  Cancel & Resend — start fresh"
                )
                await query.edit_message_text(
                    help_text,
                    reply_markup=self.create_help_submenu()
                )
        
        elif callback_data == "help_export":
            help_text = (
                "📊 Exports & Reports\n"
                "\n"
                "GSTR-1 Export (CSV)\n"
                "  • B2B invoices\n"
                "  • B2C small (under 2.5L)\n"
                "  • HSN summary\n"
                "\n"
                "GSTR-3B Summary (JSON)\n"
                "  • Tax liability\n"
                "  • ITC available\n"
                "  • Tax payable breakdown\n"
                "\n"
                "Operational Reports\n"
                "  • Processing stats\n"
                "  • Validation errors\n"
                "  • Duplicate attempts\n"
                "  • Correction history\n"
                "\n"
                "─────────────────────\n"
                "How to export:\n"
                "  1. Tap Generate GST Input\n"
                "  2. Pick your export type\n"
                "  3. Enter month and year\n"
                "  4. Get your CSV/JSON file!"
            )
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_generate_submenu()
            )
        
        elif callback_data == "help_trouble":
            help_text = (
                "🔧 Troubleshooting\n"
                "\n"
                "Image not recognized?\n"
                "  • Better lighting, less glare\n"
                "  • Hold camera steady\n"
                "  • Try taking the photo again\n"
                "\n"
                "Wrong data extracted?\n"
                "  • Use ✏️ Make Corrections to fix fields\n"
                "  • Send clearer or additional pages\n"
                "\n"
                "Validation errors?\n"
                "  • GSTIN should be 15 characters\n"
                "  • Check that dates and amounts match\n"
                "\n"
                "Duplicate warning?\n"
                "  • I found a similar invoice already saved\n"
                "  • Save anyway if you're sure it's unique\n"
                "\n"
                "Bot not responding?\n"
                "  • Check your internet connection\n"
                "  • Tap ❌ Cancel and try again\n"
                "  • I might still be processing — give it a moment\n"
                "\n"
                "Still stuck? Contact your administrator."
            )
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
            await query.edit_message_text("📊 Generating quick statistics...")
            try:
                result = self.tier3_handlers.reporter.generate_processing_stats()
                if result['success']:
                    message = "📊 QUICK STATISTICS\n\n"
                    message += f"Total Invoices: {result['total_invoices']}\n\n"
                    message += "VALIDATION STATUS\n"
                    for status, count in result['status_breakdown'].items():
                        pct = result['status_percentages'].get(status, 0)
                        message += f"  {status}: {count} ({pct:.1f}%)\n"
                    await query.message.reply_text(message)
                else:
                    await query.message.reply_text(f"❌ {result['message']}")
            except Exception as e:
                await query.message.reply_text(f"❌ Error: {str(e)}")
        
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
Tap 📊 Quick Stats for overall processing statistics
Tap 📋 Reports for detailed analysis"""
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_usage_submenu()
            )
        
        elif callback_data == "stats_export":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 GSTR-1 Export", callback_data="gen_gstr1")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu_generate")]
            ])
            await query.edit_message_text(
                "💾 Export Processing Data\n\n"
                "Your data is already in Google Sheets!\n\n"
                "Sheets Available:\n"
                "• Invoice_Header - Main invoice data\n"
                "• Line_Items - Item-level details\n"
                "• Customer_Master - Buyer database\n"
                "• HSN_Master - Product codes\n\n"
                "You can export directly from Google Sheets:\n"
                "File → Download → CSV/Excel\n\n"
                "Or tap below for GSTR-1 CSV exports.",
                reply_markup=keyboard
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
                f"All cleared ({image_count} image(s) removed).\n\n"
                "What's next? 👇",
                reply_markup=self.create_main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                "Nothing active to cancel.\n\n"
                "What would you like to do?",
                reply_markup=self.create_main_menu_keyboard()
            )
    
    async def confirm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /confirm command - save invoice without corrections"""
        user_id = update.effective_user.id
        msg = update.effective_message
        session = self._get_user_session(user_id)
        
        if session['state'] != 'reviewing':
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Upload Invoice", callback_data="menu_upload")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "No invoice waiting to confirm.\n\n"
                "Start by uploading an invoice.",
                reply_markup=keyboard
            )
            return
        
        # Proceed to save without corrections
        await self._save_invoice_to_sheets(update, user_id, session)
    
    async def correct_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /correct command - start correction mode"""
        msg = update.effective_message
        if not config.ENABLE_MANUAL_CORRECTIONS:
            await msg.reply_text("Manual corrections are disabled.")
            return
        
        user_id = update.effective_user.id
        session = self._get_user_session(user_id)
        
        if session['state'] != 'reviewing':
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Upload Invoice", callback_data="menu_upload")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "No invoice to correct right now.\n\n"
                "Start by uploading an invoice.",
                reply_markup=keyboard
            )
            return
        
        # Enter correction mode
        session['state'] = 'correcting'
        
        instructions = self.correction_manager.generate_correction_instructions()
        correction_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💾 Save Corrections", callback_data="btn_save_corrections"),
            ],
            [
                InlineKeyboardButton("↩️ Cancel Correction", callback_data="btn_cancel_correction"),
                InlineKeyboardButton("🗑 Cancel & Resend", callback_data="btn_cancel_resend"),
            ]
        ])
        await msg.reply_text(instructions, reply_markup=correction_keyboard)
    
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
        msg = update.effective_message
        try:
            await msg.reply_text("⏳ Saving to Google Sheets...  (4/4)")
            
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
            tenant_sheet_id = self._get_tenant_sheet_id(user_id)
            self._ensure_sheets_manager(sheet_id=tenant_sheet_id)  # Lazy init (tenant-aware)
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
            post_save_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📸 Upload Another", callback_data="menu_upload"),
                    InlineKeyboardButton("📊 Reports", callback_data="menu_generate"),
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(success_message, reply_markup=post_save_keyboard)  # No Markdown - plain text only
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
            
            # ── Tenant: increment invoice counter ─────────────
            self._ensure_tenant_manager()
            if self.tenant_manager:
                try:
                    self.tenant_manager.increment_invoice_counter(user_id)
                except Exception:
                    pass  # Non-blocking
            # ──────────────────────────────────────────────────
            
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
            self._ensure_sheets_manager()  # Lazy init
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
            
            self._ensure_sheets_manager()  # Lazy init
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
                
                self._ensure_sheets_manager()  # Lazy init
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
        
        # Build GST tax breakdown
        tax_lines = []
        igst = invoice_data.get('IGST_Total', '')
        cgst = invoice_data.get('CGST_Total', '')
        sgst = invoice_data.get('SGST_Total', '')
        if igst:
            tax_lines.append(f"  IGST: Rs.{igst}")
        if cgst:
            tax_lines.append(f"  CGST: Rs.{cgst}")
        if sgst:
            tax_lines.append(f"  SGST: Rs.{sgst}")
        tax_breakdown = "\n".join(tax_lines)
        
        validation_status = validation_result.get('status', 'UNKNOWN')
        
        success_message = (
            "✅ Invoice saved successfully!\n"
            "\n"
            "─────────────────────\n"
            f"  Invoice No:   {invoice_no}\n"
            f"  Date:         {invoice_date}\n"
            f"  Seller:       {seller_name}\n"
            f"  Buyer:        {buyer_name}\n"
            f"  Line Items:   {len(line_items)}\n"
            "─────────────────────\n"
            "\n"
            "💰 GST Summary\n"
            f"  Invoice Value:  Rs.{invoice_value}\n"
            f"  Taxable:        Rs.{total_taxable}\n"
            f"  Total GST:      Rs.{total_gst}\n"
        )
        
        if tax_breakdown:
            success_message += tax_breakdown + "\n"
        
        success_message += f"\n  Validation: {validation_status}\n"
        
        if corrections:
            success_message += f"\n📝 {len(corrections)} correction(s) applied\n"
        
        if is_duplicate_override:
            success_message += "\n⚠️ Saved as duplicate override\n"
        
        if audit_data:
            processing_time = audit_data.get('Processing_Time_Seconds', 0)
            success_message += f"\n⏱ Processed in {processing_time:.1f}s\n"
        
        success_message += "\n📊 Data saved to Google Sheets."
        
        return success_message
    
    async def done_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /done command - process all collected images"""
        user_id = update.effective_user.id
        # Use effective_message so this works from both /done command and btn_done callback
        msg = update.effective_message
        
        # ═══════════════════════════════════════════════════════════════════
        # Epic 2: If user has active order session, treat /done as /order_submit
        # ═══════════════════════════════════════════════════════════════════
        if config.FEATURE_ORDER_UPLOAD_NORMALIZATION and user_id in self.order_sessions:
            await self.order_submit_command(update, context)
            return
        # ═══════════════════════════════════════════════════════════════════
        
        session = self._get_user_session(user_id)
        
        # If user is in correction mode, /done means save with corrections
        if session['state'] == 'correcting':
            correction_count = len(session.get('corrections', {}))
            await msg.reply_text(f"💾 Applying {correction_count} correction(s) and saving...")
            await self._save_invoice_to_sheets(update, user_id, session)
            return
        
        if not session['images'] and not session.get('batch'):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Upload Invoice", callback_data="menu_upload")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "No images yet! Send me a photo first.",
                reply_markup=keyboard
            )
            return
        
        # Tier 3: Check if this is a batch processing request
        if session.get('batch') or (session['images'] and len(session.get('batch', [])) > 0):
            batch_processed = await self.tier3_handlers.process_batch(update, user_id, session)
            if batch_processed:
                return
        
        # Single invoice processing
        if not session['images']:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Upload Invoice", callback_data="menu_upload")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "No images yet! Send me a photo first.",
                reply_markup=keyboard
            )
            return
        
        image_paths = session['images']
        session['start_time'] = datetime.now()
        
        page_word = "page" if len(image_paths) == 1 else "pages"
        await msg.reply_text(
            f"🔄 Got it! Processing {len(image_paths)} {page_word}...\n\n"
            "Sit tight — this usually takes 15-30 seconds."
        )
        
        try:
            # Step 1: OCR - Extract text from all images
            await msg.reply_text("⏳ Reading invoice text...  (1/4)")
            ocr_start_time = datetime.now()
            
            ocr_result = await asyncio.to_thread(self.ocr_engine.extract_text_from_images, image_paths)
            
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
            await msg.reply_text("⏳ Extracting GST details...  (2/4)")
            parsing_start_time = datetime.now()
            
            result = await asyncio.to_thread(self.gst_parser.parse_invoice_with_validation, ocr_text)
            
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
                    review_keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Save As-Is", callback_data="btn_confirm"),
                            InlineKeyboardButton("✏️ Make Corrections", callback_data="btn_correct"),
                        ],
                        [
                            InlineKeyboardButton("🗑 Cancel & Resend New Images", callback_data="btn_cancel_resend"),
                        ]
                    ])
                    await msg.reply_text(review_msg, reply_markup=review_keyboard)
                    return
            
            # Step 5: Tier 2 - Deduplication Check (warn-only mode)
            if config.ENABLE_DEDUPLICATION and self.dedup_manager:
                fingerprint = self.dedup_manager.generate_fingerprint(invoice_data)
                session['fingerprint'] = fingerprint
                
                tenant_sheet_id = self._get_tenant_sheet_id(user_id)
                self._ensure_sheets_manager(sheet_id=tenant_sheet_id)  # Lazy init (tenant-aware)
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
                    await msg.reply_text(warning_msg)
                    
                    # Log the duplicate attempt
                    print(f"[DUPLICATE] Invoice {invoice_data.get('Invoice_No', 'unknown')} detected as duplicate but saving anyway (warn-only mode)")
            
            # No review needed - proceed to save (even if duplicate)
            await msg.reply_text("⏳ Validating data...  (3/4)")
            await self._save_invoice_to_sheets(update, user_id, session)
            
        except Exception as e:
            error_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="menu_upload")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "😕 Something went wrong during processing.\n\n"
                f"Details: {str(e)}\n\n"
                "This can happen with blurry images or unusual formats.\n"
                "Try re-sending a clearer photo.",
                reply_markup=error_keyboard
            )
            print(f"Error processing invoice for user {user_id}: {str(e)}")
    
    # ═══════════════════════════════════════════════════════════════════
    # Epic 2: ORDER UPLOAD COMMANDS (Feature-Flagged)
    # ═══════════════════════════════════════════════════════════════════
    
    async def order_upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /order_upload command - start order upload session"""
        if await self._check_registration_pending(update):
            return
        if not config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            await update.message.reply_text("Order upload isn't available yet. Contact your admin to enable it.")
            return
        
        user_id = update.effective_user.id
        
        # Cancel any existing regular invoice session
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        # Create order session
        from order_normalization import OrderSession
        order_session = OrderSession(user_id, update.effective_user.username)
        self.order_sessions[user_id] = order_session
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
        ])
        await update.message.reply_text(
            "📦 Sales Order upload\n\n"
            "Send me photos of your handwritten order notes.\n"
            "Multiple pages? No problem — send them all.\n\n"
            "When you're done, tap ✅ Submit Order.\n"
            "I'll extract items, match prices, and generate a clean PDF.",
            reply_markup=keyboard
        )
    
    async def order_submit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /order_submit command - ask user for output format then process"""
        if not config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            await update.message.reply_text("Order upload isn't available yet. Contact your admin to enable it.")
            return
        
        user_id = update.effective_user.id
        
        # Check if user has an active order session
        msg = update.effective_message
        if user_id not in self.order_sessions:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Sales Order", callback_data="menu_order_upload")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "❌ No Active Order Session\n\n"
                "You need to start an order upload session first!\n\n"
                "📌 HOW TO UPLOAD AN ORDER\n"
                "1. Tap 📦 Sales Order below\n"
                "2. Send your order photos\n"
                "3. Tap ✅ Submit Order\n\n"
                "Note: Invoice upload is different from order upload.",
                reply_markup=keyboard
            )
            return
        
        order_session = self.order_sessions[user_id]
        
        # Check if order has pages
        if not order_session.pages:
            await update.message.reply_text(
                "❌ Cannot submit order.\n\n"
                "Please upload at least one page first."
            )
            return
        
        # Ask user for output format
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📄 PDF", callback_data="order_format_pdf"),
                InlineKeyboardButton("📊 CSV", callback_data="order_format_csv"),
            ]
        ])
        
        await update.message.reply_text(
            f"📦 Ready to process your order!\n\n"
            f"📄 Pages: {len(order_session.pages)}\n\n"
            f"Choose output format:",
            reply_markup=keyboard
        )
    
    async def _process_order_with_format(self, update: Update, user_id: int, output_format: str):
        """Process submitted order with the chosen output format (pdf or csv)"""
        if user_id not in self.order_sessions:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Sales Order", callback_data="menu_order_upload")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await update.effective_message.reply_text(
                "Your order session expired.\n\nTap below to start a new one.",
                reply_markup=keyboard
            )
            return
        
        order_session = self.order_sessions[user_id]
        
        # Submit the order
        if not order_session.submit():
            await update.effective_message.reply_text(
                "Looks like this order was already submitted!"
            )
            return
        
        page_word = "page" if len(order_session.pages) == 1 else "pages"
        await update.effective_message.reply_text(
            f"🔄 Processing order...\n\n"
            f"  Order ID: {order_session.order_id}\n"
            f"  Pages: {len(order_session.pages)} {page_word}\n"
            f"  Format: {output_format.upper()}\n\n"
            f"Sit tight — this usually takes a moment."
        )
        
        # Epic 3: tenant-aware orchestrator initialisation
        tenant_sheet_id = self._get_tenant_sheet_id(user_id)
        from order_normalization import OrderNormalizationOrchestrator
        if tenant_sheet_id and config.FEATURE_TENANT_SHEET_ISOLATION:
            # Per-tenant: create an orchestrator targeting the tenant sheet
            order_orchestrator = OrderNormalizationOrchestrator(sheet_id=tenant_sheet_id)
            print(f"[OK] Epic 3: Tenant order orchestrator for sheet {tenant_sheet_id[:12]}...")
        else:
            # Shared: lazy-init a single shared orchestrator
            if self.order_orchestrator is None:
                self.order_orchestrator = OrderNormalizationOrchestrator()
                print("[OK] Epic 2: Order orchestrator initialized (lazy)")
            order_orchestrator = self.order_orchestrator
        
        # Process the order asynchronously
        try:
            await order_orchestrator.process_order(order_session, update, output_format=output_format)
            
            # ── Tenant: increment order counter ───────────────
            self._ensure_tenant_manager()
            if self.tenant_manager:
                try:
                    self.tenant_manager.increment_order_counter(user_id)
                except Exception:
                    pass  # Non-blocking
            # ──────────────────────────────────────────────────
        except Exception as e:
            print(f"[ERROR] Order processing failed: {e}")
            order_error_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="menu_order_upload")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
            await update.effective_message.reply_text(
                f"😕 Couldn't process that order.\n\n"
                f"Details: {str(e)}\n\n"
                f"Try re-sending clearer photos.",
                reply_markup=order_error_keyboard
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
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Submit Order", callback_data="btn_order_submit"),
                    InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                ]
            ])
            await update.message.reply_text(
                f"⚠️ Maximum {config.MAX_IMAGES_PER_ORDER} pages per order.\n"
                f"Tap Submit Order or Cancel.",
                reply_markup=keyboard
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
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Submit Order", callback_data="btn_order_submit"),
                    InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                ]
            ])
            await update.message.reply_text(
                f"📄 Page {page_number} received!\n\n"
                f"Got more pages? Send them.\n"
                f"All done? Tap Submit Order below.",
                reply_markup=keyboard
            )
            
        except Exception as e:
            print(f"[ERROR] Order photo download failed: {e}")
            await update.message.reply_text(
                f"😕 Couldn't download that image.\n\n"
                f"Please try sending it again."
            )
    
    async def _handle_order_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document images in order upload mode (mirrors handle_order_photo for file attachments)"""
        user_id = update.effective_user.id
        
        if user_id not in self.order_sessions:
            return
        
        order_session = self.order_sessions[user_id]
        
        # Check max images
        if len(order_session.pages) >= config.MAX_IMAGES_PER_ORDER:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Submit Order", callback_data="btn_order_submit"),
                    InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                ]
            ])
            await update.message.reply_text(
                f"⚠️ Maximum {config.MAX_IMAGES_PER_ORDER} pages per order.\n"
                f"Tap Submit Order or Cancel.",
                reply_markup=keyboard
            )
            return
        
        document = update.message.document
        file_name = document.file_name or 'order_image.jpg'
        
        try:
            file = await context.bot.get_file(document.file_id)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"order_{user_id}_{timestamp}_{file_name}"
            filepath = os.path.join(config.TEMP_FOLDER, filename)
            
            os.makedirs(config.TEMP_FOLDER, exist_ok=True)
            await file.download_to_drive(filepath)
            
            # Add page to order session
            page_number = order_session.add_page(filepath)
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Submit Order", callback_data="btn_order_submit"),
                    InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                ]
            ])
            await update.message.reply_text(
                f"📄 Page {page_number} received!\n\n"
                f"Got more pages? Send them.\n"
                f"All done? Tap Submit Order below.",
                reply_markup=keyboard
            )
            
        except Exception as e:
            print(f"[ERROR] Order document download failed: {e}")
            await update.message.reply_text(
                f"😕 Couldn't download that image.\n\n"
                f"Please try sending it again."
            )
    
    # ═══════════════════════════════════════════════════════════════════
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming photo messages"""
        user_id = update.effective_user.id
        
        # ═══════════════════════════════════════════════════════════════════
        # Epic 2: Check if this is an order photo (Feature-Flagged)
        # Order session takes priority — check BEFORE creating invoice session
        # ═══════════════════════════════════════════════════════════════════
        if (config.FEATURE_ORDER_UPLOAD_NORMALIZATION 
                and user_id in self.order_sessions):
            await self.handle_order_photo(update, context)
            return
        # ═══════════════════════════════════════════════════════════════════
        
        # No order session — proceed with invoice flow
        invoice_session = self._get_user_session(user_id)
        
        session = invoice_session
        
        if session['state'] != 'uploading':
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel & Start Over", callback_data="btn_cancel_resend")]
            ])
            await update.message.reply_text(
                "Looks like you're in the middle of something.\n\n"
                "Finish that first, or tap below to start over.",
                reply_markup=keyboard
            )
            return
        
        if len(session['images']) >= config.MAX_IMAGES_PER_INVOICE:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Process Invoice", callback_data="btn_done"),
                    InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                ]
            ])
            await update.message.reply_text(
                f"That's the limit — {config.MAX_IMAGES_PER_INVOICE} images max per invoice.\n\n"
                f"Ready to process, or want to cancel?",
                reply_markup=keyboard
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
                
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Process Invoice", callback_data="btn_done"),
                        InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                    ]
                ])
                await update.message.reply_text(
                    f"📄 Page {page_count} received!\n\n"
                    f"Got more pages? Send them.\n"
                    f"All done? Tap the button below.",
                    reply_markup=keyboard
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
                            "⏱ The download timed out.\n\n"
                            "This usually means a slow connection.\n"
                            "Try sending the image again."
                        )
                    else:
                        await update.message.reply_text(
                            f"😕 Couldn't download that image.\n\n"
                            f"Please try sending it again."
                        )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document messages - accept images sent as files"""
        user_id = update.effective_user.id
        
        # ═══════════════════════════════════════════════════════════════════
        # Epic 2: Check if user is in order upload mode (Feature-Flagged)
        # Order session takes priority — check BEFORE creating invoice session
        # ═══════════════════════════════════════════════════════════════════
        if (config.FEATURE_ORDER_UPLOAD_NORMALIZATION 
                and user_id in self.order_sessions):
            document = update.message.document
            mime_type = document.mime_type or ''
            file_name = document.file_name or ''
            
            is_image = (
                mime_type.startswith('image/') or 
                file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            )
            
            if is_image:
                # Route to order photo handler (reuse handle_order_photo logic for documents)
                await self._handle_order_document(update, context)
                return
            else:
                await update.message.reply_text(
                    "📦 You're in order upload mode.\n\n"
                    "Please send images (JPG/PNG) of your handwritten order.\n"
                    "Tap ✅ Submit Order when done or ❌ Cancel to abort."
                )
                return
        # ═══════════════════════════════════════════════════════════════════
        
        # No order session — proceed with invoice flow
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
                    
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Process Invoice", callback_data="btn_done"),
                            InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                        ]
                    ])
                    await update.message.reply_text(
                        f"✅ Page {page_count} received!\n\n"
                        f"Send more pages or tap Process Invoice.",
                        reply_markup=keyboard
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
                                "⏱ The download timed out.\n\n"
                                "The file might be too large. A few tips:\n"
                                "  • Send as a photo (not file) — it's faster\n"
                                "  • Try a smaller or compressed image\n"
                                "  • Check your internet connection"
                            )
                        else:
                            await update.message.reply_text(
                                f"😕 Couldn't download that file.\n\n"
                                f"Please try sending it again."
                            )
        else:
            await update.message.reply_text(
                "📎 PDF support is coming soon!\n\n"
                "For now, please send images (JPG or PNG).\n"
                "Tip: Send as a photo rather than a file — it's faster!"
            )
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle random text messages and correction input"""
        user_id = update.effective_user.id
        
        # ── Tenant registration collection ───────────────────
        if user_id in self.pending_email_users:
            import re
            text = (update.message.text or '').strip()
            info = self.pending_email_users[user_id]
            needs_name = info.get('needs_name', False)
            
            # Parse input depending on whether we need name+email or just email
            tenant_name = info.get('full_name', '')
            username = info.get('username', '')
            email = None
            
            if needs_name:
                # Expect "Name, email" format
                if ',' in text:
                    parts = [p.strip() for p in text.split(',', 1)]
                    name_part, email_part = parts[0], parts[1]
                else:
                    # Maybe they just typed an email - use Telegram name
                    name_part = ''
                    email_part = text
                
                if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email_part):
                    email = email_part
                    if name_part:
                        tenant_name = name_part
                        username = name_part  # Use provided name as username too
                else:
                    await update.message.reply_text(
                        "Hmm, that doesn't look right.\n\n"
                        "Please type your name and email, separated by a comma:\n"
                        "  Example: John Doe, john@example.com"
                    )
                    return
            else:
                # Just email
                if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
                    email = text
                else:
                    await update.message.reply_text(
                        "Hmm, that doesn't look like a valid email.\n\n"
                        "Try again — for example: name@example.com"
                    )
                    return
            
            # Register the tenant
            self.pending_email_users.pop(user_id)
            try:
                self._ensure_tenant_manager()
                if self.tenant_manager:
                    self.tenant_manager.register_tenant(
                        user_id=user_id,
                        first_name=tenant_name,
                        username=username,
                        email=email,
                    )
                    await update.message.reply_text(
                        "You're all set! 🎉\n\n"
                        "Registration complete. Let's get started!",
                        reply_markup=self.create_main_menu_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "😕 Registration service is temporarily unavailable.\n\n"
                        "Please try again in a moment by tapping /start.",
                        reply_markup=self.create_main_menu_keyboard()
                    )
            except Exception as e:
                print(f"[WARNING] Tenant registration failed: {e}")
                await update.message.reply_text(
                    "😕 Something went wrong with registration.\n\n"
                    "Please try again by tapping /start.",
                    reply_markup=self.create_main_menu_keyboard()
                )
            return
        # ─────────────────────────────────────────────────────
        
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
                
                correction_count = len(session['corrections'])
                correction_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(f"💾 Save {correction_count} Correction(s)", callback_data="btn_save_corrections"),
                    ],
                    [
                        InlineKeyboardButton("↩️ Cancel Correction", callback_data="btn_cancel_correction"),
                        InlineKeyboardButton("🗑 Cancel & Resend", callback_data="btn_cancel_resend"),
                    ]
                ])
                await update.message.reply_text(
                    f"Got it! {field_name} updated.\n\n"
                    f"Keep editing, or use the buttons below.",
                    reply_markup=correction_keyboard
                )
            else:
                await update.message.reply_text(
                    "Hmm, I didn't understand that.\n\n"
                    "Use this format: field_name = value\n"
                    "  Example: buyer_gstin = 29AAAAA0000A1Z5"
                )
            return
        
        # Default response
        default_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📸 Upload Invoice", callback_data="menu_upload"),
                InlineKeyboardButton("📦 Sales Order", callback_data="menu_order_upload"),
            ],
            [InlineKeyboardButton("❓ Help", callback_data="menu_help")]
        ])
        await update.message.reply_text(
            "Not sure what to do with that! 🤔\n\n"
            "To get started, send me an invoice photo — or pick an option below.",
            reply_markup=default_keyboard
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
            .post_init(setup_bot_commands)
            .build()
        )
        
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
            application.add_handler(CommandHandler("order_upload", self.order_upload_command))
            application.add_handler(CommandHandler("order_submit", self.order_submit_command))
            print("[OK] Epic 2: Order upload commands registered")
        # ═══════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════
        # Epic 3: Subscription command
        # ═══════════════════════════════════════════════════════
        application.add_handler(CommandHandler("subscribe", self.subscribe_command))
        print("[OK] Epic 3: Subscribe command registered")
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
        
        # Cloud Run: Add startup delay to let any lingering old container instances
        # fully terminate before this instance starts polling Telegram.
        import time
        startup_delay = int(os.getenv('BOT_STARTUP_DELAY', '0'))
        if startup_delay > 0:
            print(f"[STARTUP] Waiting {startup_delay}s for old instances to terminate...")
            time.sleep(startup_delay)

        # Retry loop: python-telegram-bot does not retry on Conflict errors
        # (only on network errors). On Cloud Run, revision transitions cause
        # brief periods where two bot instances poll simultaneously, which
        # triggers Conflict. We wrap run_polling in a retry loop so the bot
        # recovers automatically.
        max_retries = int(os.getenv('BOT_POLLING_RETRIES', '5'))
        for attempt in range(1, max_retries + 1):
            try:
                application.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True,
                )
                break  # Clean exit (e.g. SIGTERM) — don't retry
            except Exception as poll_err:
                err_str = str(poll_err).lower()
                if 'conflict' in err_str and attempt < max_retries:
                    wait = min(10 * attempt, 30)
                    print(f"[RETRY] Polling conflict (attempt {attempt}/{max_retries}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise  # Non-conflict error or retries exhausted


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
