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

# ═══════════════════════════════════════════════════════════════════
# Tier 4: Batch Processing Engine (Feature-Flagged, Local Only)
# ═══════════════════════════════════════════════════════════════════
if config.ENABLE_BATCH_MODE:
    sys.path.insert(0, str(config.PROJECT_ROOT))
    from batch_engine.batch_manager import BatchManager
    from batch_engine.batch_models import BatchStatus
    print("[OK] Tier 4: Batch engine module loaded")
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
        BotCommand("help", "Help & guide"),
    ]
    
    # Add Epic 2 commands if feature enabled
    if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
        commands.insert(2, BotCommand("order_upload", "Sales Order"))

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

        # ═══════════════════════════════════════════════════════
        # Tier 4: Batch Processing Engine (Feature-Flagged)
        # ═══════════════════════════════════════════════════════
        if config.ENABLE_BATCH_MODE:
            self.batch_manager = BatchManager()
            self.batch_sessions = {}  # {user_id: {'images': [], 'business_type': 'Purchase'}}
            print("[OK] Tier 4: Batch engine enabled")
        else:
            self.batch_manager = None
            self.batch_sessions = {}
        # ═══════════════════════════════════════════════════════

        # Active processing tasks — allows the watchdog to cancel on user request
        self._active_processing_tasks: dict = {}  # {user_id: asyncio.Task}
        self._retry_context: dict = {}  # {user_id: {'operation': 'order'|'invoice', ...}}

    
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

    async def _get_tenant_sheet_id(self, user_id: int):
        """Get tenant-specific sheet ID if feature is enabled (Epic 3).

        Returns:
            Sheet ID string or None (falls back to shared sheet).
        """
        if not config.FEATURE_TENANT_SHEET_ISOLATION:
            return None
        await self._ensure_tenant_manager()
        if self.tenant_manager:
            try:
                return await asyncio.to_thread(self.tenant_manager.get_tenant_sheet_id, user_id)
            except Exception as e:
                print(f"[WARNING] Could not get tenant sheet_id for {user_id}: {e}")
        return None
    
    async def _ensure_tenant_manager(self):
        """Lazy initialize TenantManager on first use (non-blocking)"""
        if self.tenant_manager is None:
            try:
                from utils.tenant_manager import TenantManager
                self.tenant_manager = await asyncio.to_thread(TenantManager)
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
            await self._ensure_tenant_manager()
            if self.tenant_manager:
                tenant = await asyncio.to_thread(self.tenant_manager.get_tenant, user_id)
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
            f"Welcome to GST Scanner Bot\n"
            f"\n"
            f"Here's what I can do for you:\n"
            f"\n"
            f"📸 Purchase Orders — snap invoices, I extract GST data\n"
            f"📦 Sales Orders — turn handwritten notes into clean PDFs\n"
            f"📊 Reports — GSTR-1, GSTR-3B, stats at your fingertips\n"
            f"\n"
            f"Pick an option below to get started!"
        )
        
        # Check tenant registration
        try:
            await self._ensure_tenant_manager()
            if self.tenant_manager:
                print(f"[TENANT] Looking up user_id={user.id} (type={type(user.id).__name__})", flush=True)
                tenant = await asyncio.to_thread(self.tenant_manager.get_tenant, user.id)
                print(f"[TENANT] Lookup result: {tenant}", flush=True)
                if tenant:
                    if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
                        try:
                            from subscription.subscription_config import TIER_PLANS
                            plan_id = tenant.get('subscription_plan') or config.DEFAULT_SUBSCRIPTION_TIER
                            plan = TIER_PLANS.get(plan_id, TIER_PLANS.get('free', {}))
                            plan_name = plan.get('name', plan_id.title())

                            inv_used = int(tenant.get('invoice_count', 0) or 0)
                            ord_used = int(tenant.get('order_count', 0) or 0)
                            inv_limit = plan.get('invoice_limit', 0)
                            ord_limit = plan.get('order_limit', 0)

                            inv_str = f"{inv_used}" if inv_limit == -1 else f"{inv_used}/{inv_limit}"
                            ord_str = f"{ord_used}" if ord_limit == -1 else f"{ord_used}/{ord_limit}"
                            inv_left = "Unlimited" if inv_limit == -1 else f"{max(inv_limit - inv_used, 0)} left"
                            ord_left = "Unlimited" if ord_limit == -1 else f"{max(ord_limit - ord_used, 0)} left"

                            welcome_message += (
                                f"\n\n📋 Plan: {plan_name}\n"
                                f"📸 Invoices: {inv_str} ({inv_left})\n"
                                f"📦 Orders: {ord_str} ({ord_left})"
                            )
                        except Exception:
                            pass
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
            await self._get_main_menu_text(update.effective_user.id),
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
        
        # Tier 4: Show mode selection when batch mode is enabled
        if config.ENABLE_BATCH_MODE:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📄 Single Mode", callback_data="menu_single_upload"),
                    InlineKeyboardButton("📦 Batch Mode", callback_data="menu_batch_upload"),
                ],
                [InlineKeyboardButton("◀ Back", callback_data="menu_main")]
            ])
            await update.message.reply_text(
                "📸 Purchase Order\n\n"
                "Choose processing mode:\n\n"
                "Single Mode — process one invoice now\n"
                "Batch Mode — queue multiple invoices for background processing",
                reply_markup=keyboard
            )
            return
        
        # Initialize session (single mode when batch is disabled)
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
            "Select what you need:",
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
        row = [InlineKeyboardButton("📸 Purchase Order", callback_data="menu_upload")]
        if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            row.append(InlineKeyboardButton("📦 Sales Order", callback_data="menu_order_upload"))
        keyboard = [row]
        keyboard.append([InlineKeyboardButton("📊 Reports & Exports", callback_data="menu_generate")])
        if config.ENABLE_BATCH_MODE:
            keyboard.append([InlineKeyboardButton("📋 Batch Status", callback_data="menu_my_batches")])
        keyboard.append([
            InlineKeyboardButton("💳 Subscription", callback_data="menu_subscribe"),
            InlineKeyboardButton("❓ Help & Guide", callback_data="menu_help"),
        ])
        return InlineKeyboardMarkup(keyboard)

    def create_upload_submenu(self):
        """Submenu for Upload options"""
        keyboard = [
            [InlineKeyboardButton("📄 Single Invoice", callback_data="upload_single")],
            [InlineKeyboardButton("📦 Batch Upload", callback_data="upload_batch")],
            [InlineKeyboardButton("📎 Upload Document", callback_data="upload_document")],
            [InlineKeyboardButton("❓ Upload Help", callback_data="help_upload")],
            [InlineKeyboardButton("◀ Back", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_generate_submenu(self):
        """Submenu for Generate GST options"""
        keyboard = [
            [InlineKeyboardButton("📄 GSTR-1 Export", callback_data="gen_gstr1")],
            [InlineKeyboardButton("📋 GSTR-3B Summary", callback_data="gen_gstr3b")],
            [InlineKeyboardButton("📈 Reports", callback_data="gen_reports")],
            [InlineKeyboardButton("📊 Quick Stats", callback_data="gen_stats")],
            [InlineKeyboardButton("❓ Export Help", callback_data="help_export")],
            [InlineKeyboardButton("◀ Back", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_help_submenu(self):
        """Submenu for Help options"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Getting Started", callback_data="help_start"),
                InlineKeyboardButton("📸 Upload Guide", callback_data="help_upload"),
            ],
            [
                InlineKeyboardButton("✏️ Corrections", callback_data="help_corrections"),
                InlineKeyboardButton("📊 Export Guide", callback_data="help_export"),
            ],
            [
                InlineKeyboardButton("❌ Cancel Operation", callback_data="help_cancel"),
                InlineKeyboardButton("📈 Reports", callback_data="help_reports"),
            ],
            [
                InlineKeyboardButton("💳 Subscription", callback_data="help_subscription"),
                InlineKeyboardButton("📋 Batch Help", callback_data="help_batch"),
            ],
            [
                InlineKeyboardButton("🔧 Troubleshooting", callback_data="help_trouble"),
                InlineKeyboardButton("✉ Support", callback_data="help_contact"),
            ],
            [InlineKeyboardButton("◀ Back", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_usage_submenu(self):
        """Submenu for Usage/Stats options"""
        keyboard = [
            [InlineKeyboardButton("📊 Quick Stats", callback_data="stats_quick")],
            [InlineKeyboardButton("📈 Detailed Reports", callback_data="stats_detailed")],
            [InlineKeyboardButton("📅 History", callback_data="stats_history")],
            [InlineKeyboardButton("💾 Export Data", callback_data="stats_export")],
            [InlineKeyboardButton("◀ Back", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_month_picker(self, command_prefix: str):
        """Create a 4x3 month picker inline keyboard.
        command_prefix is used in callback_data: month_{prefix}_{1-12}"""
        from calendar import month_abbr
        if command_prefix == "stats":
            back_callback = "menu_usage"
        elif command_prefix.startswith("rpt"):
            back_callback = "gen_reports"
        else:
            back_callback = "menu_generate"
        months = []
        for row_start in (1, 4, 7, 10):
            row = []
            for m in range(row_start, row_start + 3):
                row.append(InlineKeyboardButton(
                    month_abbr[m], callback_data=f"month_{command_prefix}_{m}"
                ))
            months.append(row)
        months.append([InlineKeyboardButton("◀ Back", callback_data=back_callback)])
        return InlineKeyboardMarkup(months)

    def create_year_picker(self, command_prefix: str, month: int):
        """Create a year picker with current and previous year."""
        from datetime import datetime as _dt
        current_year = _dt.now().year
        if command_prefix.startswith("rpt"):
            back_callback = "gen_reports"
        elif command_prefix == "stats":
            back_callback = "stats_detailed"
        else:
            back_callback = f"gen_{command_prefix}"
        keyboard = [
            [
                InlineKeyboardButton(
                    str(current_year),
                    callback_data=f"year_{command_prefix}_{month}_{current_year}"
                ),
                InlineKeyboardButton(
                    str(current_year - 1),
                    callback_data=f"year_{command_prefix}_{month}_{current_year - 1}"
                ),
            ],
            [InlineKeyboardButton("◀ Back", callback_data=back_callback)]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_report_type_picker(self):
        """Create a report type picker inline keyboard."""
        keyboard = [
            [InlineKeyboardButton("📊 Processing Statistics", callback_data="report_type_1")],
            [InlineKeyboardButton("📋 GST Summary (monthly)", callback_data="report_type_2")],
            [InlineKeyboardButton("⚠️ Duplicate Attempts", callback_data="report_type_3")],
            [InlineKeyboardButton("✏️ Correction Analysis", callback_data="report_type_4")],
            [InlineKeyboardButton("📈 Comprehensive Report", callback_data="report_type_5")],
            [InlineKeyboardButton("◀ Back", callback_data="menu_generate")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_gstr1_type_picker(self, month: int, year: int):
        """Create GSTR-1 export type picker."""
        keyboard = [
            [InlineKeyboardButton("📄 B2B Invoices", callback_data=f"gstr1type_{month}_{year}_1")],
            [InlineKeyboardButton("📄 B2C Small", callback_data=f"gstr1type_{month}_{year}_2")],
            [InlineKeyboardButton("📄 HSN Summary", callback_data=f"gstr1type_{month}_{year}_3")],
            [InlineKeyboardButton("📄 All Three", callback_data=f"gstr1type_{month}_{year}_4")],
            [InlineKeyboardButton("◀ Back", callback_data="menu_generate")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        max_images = config.MAX_IMAGES_PER_INVOICE
        help_message = (
            "❓ Help & Guide\n"
            "\n"
            "📸 Purchase Order\n"
            f"  Send photos or tap Upload (up to {max_images} pages).\n"
            "  Choose Single or Batch mode when prompted.\n"
            "\n"
            "📦 Sales Order\n"
            "  Send order note photos, then submit for PDF.\n"
            "\n"
            "📊 Reports & Exports\n"
            "  GSTR-1, GSTR-3B, CSV export, quick stats.\n"
            "\n"
            "📋 Batch Processing\n"
            "  Queue multiple invoices for background processing.\n"
            "\n"
            "💡 Tips for best results\n"
            "  Good lighting, clear focus, all pages\n"
            "  from the same document in one session.\n"
            "\n"
            "Tap a topic below for more details:"
        )
        
        await update.message.reply_text(
            help_message,
            reply_markup=self.create_help_submenu()
        )
    
    # ═══════════════════════════════════════════════════════════════════
    # Epic 3: /subscribe command -- subscription enrollment
    # ═══════════════════════════════════════════════════════════════════
    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /subscribe -- show available subscription tiers"""
        user_id = update.effective_user.id

        await self._ensure_tenant_manager()
        if not self.tenant_manager:
            await update.message.reply_text(
                "❌ Subscription service is currently unavailable.\n\n"
                "Please try again later.",
                reply_markup=self.create_main_menu_keyboard()
            )
            return

        tenant = await asyncio.to_thread(self.tenant_manager.get_tenant, user_id)
        if not tenant:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Get Started", callback_data="menu_main")]
            ])
            await update.message.reply_text(
                "You need to register first.\n\nTap below to get started.",
                reply_markup=keyboard
            )
            return

        current_plan = tenant.get('subscription_plan', config.DEFAULT_SUBSCRIPTION_TIER)

        if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
            await self._show_subscription_plans_enhanced(update.message, user_id, current_plan, tenant)
        else:
            buttons = []
            for tier in config.SUBSCRIPTION_TIERS:
                label = tier['name']
                if tier['id'] == current_plan:
                    label = f"✅ {tier['name']} (current)"
                else:
                    label = f"💳 {tier['name']}"
                buttons.append([
                    InlineKeyboardButton(
                        f"{label} -- {tier['description']}",
                        callback_data=f"subscribe_{tier['id']}"
                    )
                ])
            buttons.append([InlineKeyboardButton("◀ Back", callback_data="menu_main")])

            await update.message.reply_text(
                "💳 Subscription Plans\n\n"
                f"Your current plan: {current_plan.title()}\n\n"
                "Select a plan below:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    async def _show_subscription_plans_enhanced(self, message_target, user_id, current_plan, tenant):
        """Enhanced subscription view with pricing, features, and payment links."""
        from subscription.subscription_config import TIER_PLANS, TIER_ORDER

        lines = ["💳 *Subscription Plans*\n"]
        lines.append(f"Your current plan: *{current_plan.title()}*")
        expires_at = tenant.get('subscription_expires_at', '')
        if expires_at:
            lines.append(f"Expires: {expires_at[:10]}")
        lines.append(f"Invoices used: {tenant.get('invoice_count', '0')}")
        lines.append(f"Orders used: {tenant.get('order_count', '0')}")
        lines.append("")

        for tid in TIER_ORDER:
            plan = TIER_PLANS[tid]
            is_current = tid == current_plan
            marker = "✅" if is_current else "💳"
            if plan['monthly_price'] == 0:
                price_str = "Free"
            else:
                annual_monthly = round(plan['annual_price'] / 12)
                price_str = f"₹{plan['monthly_price']}/mo or ₹{plan['annual_price']}/yr (₹{annual_monthly}/mo)"
            lines.append(f"{marker} *{plan['name']}* — {price_str}")
            limit_label = "Unlimited" if plan['invoice_limit'] == -1 else str(plan['invoice_limit'])
            lines.append(f"  Invoices: {limit_label}/mo | Users: {plan['users']}")
            top_features = plan['features'][:3]
            for f in top_features:
                lines.append(f"  • {f}")
            if is_current:
                lines.append("  _(current plan)_")
            lines.append("")

        buttons = []
        current_rank = TIER_ORDER.index(current_plan) if current_plan in TIER_ORDER else 0
        for tid in TIER_ORDER:
            if tid == current_plan:
                continue
            plan = TIER_PLANS[tid]
            rank = TIER_ORDER.index(tid)
            if rank > current_rank and plan['monthly_price'] > 0:
                buttons.append([
                    InlineKeyboardButton(
                        f"⬆ {plan['name']} Monthly (₹{plan['monthly_price']})",
                        callback_data=f"subscribe_pay_{tid}_monthly"
                    ),
                    InlineKeyboardButton(
                        f"⬆ Annual (₹{plan['annual_price']})",
                        callback_data=f"subscribe_pay_{tid}_annual"
                    ),
                ])
            elif rank < current_rank:
                buttons.append([InlineKeyboardButton(
                    f"⬇ Downgrade to {plan['name']}",
                    callback_data=f"subscribe_downgrade_{tid}"
                )])

        if current_plan != 'free':
            buttons.append([InlineKeyboardButton("❌ Cancel Subscription", callback_data="subscribe_cancel")])
        buttons.append([InlineKeyboardButton("📋 View Features", callback_data="subscribe_features")])
        buttons.append([InlineKeyboardButton("🧾 Transaction History", callback_data="subscribe_history")])
        buttons.append([InlineKeyboardButton("◀ Back", callback_data="menu_main")])

        text = "\n".join(lines)
        if hasattr(message_target, 'edit_message_text'):
            await message_target.edit_message_text(
                text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await message_target.reply_text(
                text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons)
            )

    def _get_subscription_service(self):
        """Lazy-init the SubscriptionService for Telegram use."""
        if not hasattr(self, '_sub_service') or self._sub_service is None:
            try:
                from subscription.transaction_store import TransactionStore
                from subscription.subscription_service import SubscriptionService
                from subscription.razorpay_client import RazorpayClient

                db_path = config.API_USER_DB_PATH.replace('users.db', 'subscription.db')
                txn_store = TransactionStore(db_path=db_path)

                razorpay_client = None
                if config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET:
                    razorpay_client = RazorpayClient(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)

                self._sub_service = SubscriptionService(
                    razorpay_client=razorpay_client,
                    transaction_store=txn_store,
                    tenant_manager=self.tenant_manager,
                )
            except Exception as e:
                print(f"[BOT] Subscription service init failed: {e}")
                self._sub_service = None
        return self._sub_service

    async def _check_tier_limit(self, user_id: int, resource: str, page_count: int = 0) -> str:
        """Check subscription tier limits for a Telegram user.
        Returns an error message string if limit exceeded, or empty string if OK."""
        try:
            from subscription.tier_guard import check_invoice_limit, check_order_limit, check_page_limit
            await self._ensure_tenant_manager()
            if not self.tenant_manager:
                return ''
            tenant = await asyncio.to_thread(self.tenant_manager.get_tenant, user_id)
            if not tenant:
                return ''
            user_dict = {
                'id': str(user_id),
                'email': tenant.get('email', ''),
                'invoice_count': tenant.get('invoice_count', 0),
                'order_count': tenant.get('order_count', 0),
            }
            if resource == 'invoices':
                msg = check_invoice_limit(user_dict)
                if msg:
                    return msg
                if page_count > 0:
                    msg = check_page_limit(user_dict, page_count)
                    if msg:
                        return msg
            elif resource == 'orders':
                return check_order_limit(user_dict) or ''
            return ''
        except Exception as e:
            print(f"[BOT] Tier limit check failed (non-blocking): {e}")
            return ''

    async def _get_main_menu_text(self, user_id: int) -> str:
        """Build main menu text with usage stats when subscription management is on."""
        base = "📋 Main Menu\n"
        try:
            if not config.FEATURE_SUBSCRIPTION_MANAGEMENT:
                return base + "\nSelect an option:"

            await self._ensure_tenant_manager()
            if not self.tenant_manager:
                return base + "\nSelect an option:"

            tenant = await asyncio.to_thread(self.tenant_manager.get_tenant, user_id)
            if not tenant:
                return base + "\nSelect an option:"

            from subscription.subscription_config import TIER_PLANS
            plan_id = tenant.get('subscription_plan') or config.DEFAULT_SUBSCRIPTION_TIER
            plan = TIER_PLANS.get(plan_id, TIER_PLANS.get('free', {}))
            plan_name = plan.get('name', plan_id.title())

            inv_used = int(tenant.get('invoice_count', 0) or 0)
            ord_used = int(tenant.get('order_count', 0) or 0)
            inv_limit = plan.get('invoice_limit', 0)
            ord_limit = plan.get('order_limit', 0)

            inv_str = f"{inv_used}" if inv_limit == -1 else f"{inv_used}/{inv_limit}"
            ord_str = f"{ord_used}" if ord_limit == -1 else f"{ord_used}/{ord_limit}"
            inv_label = "Unlimited" if inv_limit == -1 else f"{max(inv_limit - inv_used, 0)} left"
            ord_label = "Unlimited" if ord_limit == -1 else f"{max(ord_limit - ord_used, 0)} left"

            return (
                f"{base}\n"
                f"📋 Plan: {plan_name}\n"
                f"📸 Invoices: {inv_str} ({inv_label})\n"
                f"📦 Orders: {ord_str} ({ord_label})\n"
                f"\nSelect an option:"
            )
        except Exception as e:
            print(f"[BOT] Main menu usage text failed (non-blocking): {e}")
            return base + "\nSelect an option:"

    # ═══════════════════════════════════════════════════════════════════
    # Processing Watchdog — sends timeout warnings during long operations
    # ═══════════════════════════════════════════════════════════════════

    _WATCHDOG_MESSAGES = {
        'order': {
            'warn': (
                "⏳ We're sorry — this is taking longer than expected.\n\n"
                "Your order involves multiple AI steps: reading handwritten "
                "text, matching products with pricing, and generating "
                "documents. Complex or multi-page orders need more time.\n\n"
                "We're still working on it — hang tight!"
            ),
            'retry': (
                "⏳ We apologize for the wait — we're automatically "
                "retrying your order now.\n\n"
                "No action needed on your end. We'll let you know "
                "as soon as it's ready."
            ),
            'final': (
                "⏳ We sincerely apologize — this is taking unusually long.\n\n"
                "Our AI services seem to be under heavy load right now. "
                "You can cancel, or switch to batch processing for "
                "background handling."
            ),
            'final_no_batch': (
                "⏳ We sincerely apologize — this is taking unusually long.\n\n"
                "Our AI services seem to be under heavy load right now. "
                "You can cancel and try again later, or keep waiting."
            ),
        },
        'invoice': {
            'warn': (
                "⏳ We're sorry — this is taking longer than expected.\n\n"
                "Invoice scanning can take longer when images are blurry, "
                "the format is unusual, or our servers are under heavy load.\n\n"
                "We're still working on it — hang tight!"
            ),
            'retry': (
                "⏳ We apologize for the wait — we're automatically "
                "retrying your invoice now.\n\n"
                "No action needed on your end. We'll let you know "
                "as soon as it's ready."
            ),
            'final': (
                "⏳ We sincerely apologize — this is taking unusually long.\n\n"
                "Our OCR or parsing services seem to be under heavy load. "
                "You can cancel, or switch to batch processing for "
                "background handling."
            ),
            'final_no_batch': (
                "⏳ We sincerely apologize — this is taking unusually long.\n\n"
                "Our OCR or parsing services seem to be under heavy load. "
                "You can cancel and try again later, or keep waiting."
            ),
        },
    }

    async def _processing_watchdog(
        self, chat_id: int, user_id: int, processing_task, context, operation: str
    ):
        """Background coroutine that warns the user when processing is slow.

        Phases:
          1. Warn   – apologize, offer Cancel only.
          2. Retry  – cancel stalled task, restart pipeline automatically.
          3. Final  – offer Cancel (and Switch to Batch when applicable).
        """
        try:
            if operation == 'order':
                warn_after = getattr(config, 'ORDER_PROCESSING_WARN_SECONDS', 60)
                critical_after = getattr(config, 'ORDER_PROCESSING_CRITICAL_SECONDS', 180)
            else:
                warn_after = getattr(config, 'INVOICE_PROCESSING_WARN_SECONDS', 45)
                critical_after = getattr(config, 'INVOICE_PROCESSING_CRITICAL_SECONDS', 120)

            max_retries = getattr(config, 'PROCESSING_MAX_AUTO_RETRIES', 1)
            final_offer_wait = getattr(config, 'PROCESSING_FINAL_OFFER_SECONDS', 120)
            messages = self._WATCHDOG_MESSAGES.get(operation, self._WATCHDOG_MESSAGES['invoice'])

            # --- phase 1: first warning ---
            await asyncio.sleep(warn_after)
            if processing_task.done():
                return

            warn_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel_processing")]
            ])
            await context.bot.send_message(
                chat_id=chat_id,
                text=messages['warn'],
                reply_markup=warn_keyboard,
            )

            # --- phase 2: auto-retry ---
            await asyncio.sleep(critical_after - warn_after)
            if processing_task.done():
                return

            retry_ctx = self._retry_context.get(user_id, {})
            retries_done = 0

            while retries_done < max_retries:
                retries_done += 1
                print(f"[WATCHDOG] Auto-retry {retries_done}/{max_retries} for user {user_id} ({operation})")

                if not processing_task.done():
                    processing_task.cancel()
                    try:
                        await processing_task
                    except (asyncio.CancelledError, Exception):
                        pass

                retry_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel_processing")]
                ])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=messages['retry'],
                    reply_markup=retry_keyboard,
                )

                new_task = self._watchdog_restart_pipeline(user_id, retry_ctx)
                if new_task is None:
                    break
                processing_task = new_task
                self._active_processing_tasks[user_id] = processing_task

                await asyncio.sleep(final_offer_wait)
                if processing_task.done():
                    return

            # --- phase 3: final offer ---
            batch_available = (
                getattr(config, 'ENABLE_BATCH_MODE', False)
                and self.batch_manager is not None
                and operation == 'invoice'
                and user_id not in self.batch_sessions
            )
            if batch_available:
                final_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📦 Switch to Batch", callback_data="btn_switch_to_batch"),
                        InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel_processing"),
                    ]
                ])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=messages['final'],
                    reply_markup=final_keyboard,
                )
            else:
                final_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⏳ Keep Waiting", callback_data="btn_keep_waiting"),
                        InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel_processing"),
                    ]
                ])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=messages['final_no_batch'],
                    reply_markup=final_keyboard,
                )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[WATCHDOG] Error in processing watchdog: {e}")

    def _watchdog_restart_pipeline(self, user_id: int, retry_ctx: dict):
        """Create a new asyncio.Task that re-runs the stalled pipeline.

        Returns the new Task, or None if the context is insufficient.
        """
        operation = retry_ctx.get('operation', '')
        try:
            if operation == 'invoice':
                msg = retry_ctx.get('msg')
                session = retry_ctx.get('session')
                image_paths = retry_ctx.get('image_paths')
                if not (msg and session and image_paths):
                    return None
                return asyncio.create_task(
                    self._run_invoice_pipeline(msg, user_id, session, image_paths)
                )
            elif operation == 'order':
                order_session = retry_ctx.get('order_session')
                order_orchestrator = retry_ctx.get('order_orchestrator')
                update = retry_ctx.get('update')
                output_format = retry_ctx.get('output_format', 'pdf')
                if not (order_session and order_orchestrator and update):
                    return None
                order_session._status = 'submitted'
                return asyncio.create_task(
                    order_orchestrator.process_order(
                        order_session, update, output_format=output_format
                    )
                )
        except Exception as e:
            print(f"[WATCHDOG] Failed to restart pipeline: {e}")
        return None

    # ═══════════════════════════════════════════════════════════════════

    _FEATURE_NAME_ABBREV = {
        "Invoices per month": "Invoices/mo",
        "Orders per month": "Orders/mo",
        "Max pages per invoice": "Pages/invoice",
        "Invoice history": "History",
        "GST OCR & extraction": "GST OCR",
        "Line item parsing": "Line items",
        "Basic GST validation": "Basic validation",
        "Advanced GST validation": "Adv. validation",
        "Google Sheets sync": "Sheets sync",
        "Duplicate detection": "Duplicates",
        "Confidence scoring": "Confidence",
        "Manual corrections": "Corrections",
        "Auto-learning corrections": "Auto-learn",
        "Invoice categorization": "Categorization",
        "GSTR-1 export": "GSTR-1",
        "GSTR-3B summary": "GSTR-3B",
        "CSV download": "CSV export",
        "Bulk / batch upload": "Batch upload",
        "Audit logs": "Audit logs",
        "Version history": "Versioning",
        "Role-based access": "Role access",
        "Monthly/quarterly reports": "Reports",
        "Priority support": "Priority support",
    }

    _FEATURE_VAL_ABBREV = {
        "Unlimited": "Unlim.",
        "6 months": "6 mo",
        "Manual + batch (limited)": "Batch",
        "ZIP batch, priority": "ZIP",
        "Multiple": "Multi",
        "limited": "Ltd",
    }

    def _render_feature_page(self, group: str, page_num: int, total_pages: int) -> str:
        """Build a monospace-formatted feature comparison table for one group."""
        from subscription.subscription_config import DETAILED_FEATURE_MATRIX

        rows = [r for r in DETAILED_FEATURE_MATRIX if r.get('group') == group]
        name_w = 17
        col_w = 7

        def _abbrev_name(n):
            return self._FEATURE_NAME_ABBREV.get(n, n)[:name_w]

        def _abbrev_val(v):
            if v is True:
                return "Yes"
            if v is False:
                return "--"
            s = str(v)
            return self._FEATURE_VAL_ABBREV.get(s, s)[:col_w]

        hdr = (
            f"{'Feature':<{name_w}}"
            f" {'Free':^{col_w}}"
            f" {'Basic':^{col_w}}"
            f" {'Prem.':^{col_w}}"
        )
        sep = "─" * (name_w + (col_w + 1) * 3)

        lines = [
            f"📋 Feature Comparison ({page_num}/{total_pages})",
            "",
            f"<pre>",
            hdr,
            sep,
        ]

        for r in rows:
            n = _abbrev_name(r['name'])
            f_val = _abbrev_val(r.get('free', ''))
            b_val = _abbrev_val(r.get('basic', ''))
            p_val = _abbrev_val(r.get('premium', ''))
            lines.append(
                f"{n:<{name_w}}"
                f" {f_val:^{col_w}}"
                f" {b_val:^{col_w}}"
                f" {p_val:^{col_w}}"
            )

        lines.append("</pre>")
        return "\n".join(lines)
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

        try:
            await self._route_menu_callback(query, callback_data, user_id, update, context)
        except Exception as e:
            print(f"[ERROR] Callback handler failed for '{callback_data}': {e}")
            import traceback
            traceback.print_exc()
            try:
                await query.edit_message_text(
                    f"⚠️ Something went wrong.\n\nPlease try again.",
                    reply_markup=self.create_main_menu_keyboard()
                )
            except Exception:
                pass

    async def _route_menu_callback(self, query, callback_data, user_id, update, context):
        """Route callback data to the appropriate handler."""

        # ═══════════════════════════════════════════════════════
        # MAIN MENU NAVIGATION
        # ═══════════════════════════════════════════════════════
        
        if callback_data == "menu_main":
            # Return to main menu with usage stats
            await query.edit_message_text(
                await self._get_main_menu_text(user_id),
                reply_markup=self.create_main_menu_keyboard()
            )
        
        elif callback_data == "menu_upload":
            # ═══════════════════════════════════════════════════════
            # Tier 4: Show mode selection when batch mode is enabled
            # ═══════════════════════════════════════════════════════
            if config.ENABLE_BATCH_MODE:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📄 Single Mode", callback_data="menu_single_upload"),
                        InlineKeyboardButton("📦 Batch Mode", callback_data="menu_batch_upload"),
                    ],
                    [InlineKeyboardButton("◀ Back", callback_data="menu_main")]
                ])
                await query.edit_message_text(
                    "📸 Purchase Order\n\n"
                    "Choose processing mode:\n\n"
                    "Single Mode — process one invoice now\n"
                    "Batch Mode — queue multiple invoices for background processing",
                    reply_markup=keyboard
                )
            else:
                # Original single-mode flow (unchanged)
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
            # ═══════════════════════════════════════════════════════
        
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
        # Tier 4: BATCH MODE CALLBACKS (Feature-Flagged)
        # ═══════════════════════════════════════════════════════
        elif callback_data == "menu_single_upload":
            if not config.ENABLE_BATCH_MODE:
                pass  # Should not reach here, but fail-safe
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

        elif callback_data == "menu_batch_upload":
            if not config.ENABLE_BATCH_MODE:
                await query.edit_message_text(
                    "❌ Batch mode is not enabled.\n\n"
                    "Contact your admin to enable this feature.",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            user_id = update.effective_user.id
            if user_id in self.user_sessions:
                self._clear_user_session(user_id)
            self.batch_sessions[user_id] = {
                'images': [],
                'business_type': 'Purchase',
                'last_button_message_id': None,
            }
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Submit Batch", callback_data="btn_submit_batch"),
                    InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                ]
            ])
            await query.edit_message_text(
                "📦 Batch Mode\n\n"
                "Send me all your invoice images.\n"
                "Each image = one invoice.\n\n"
                "When you've sent everything, tap Submit Batch.\n"
                "I'll queue them for background processing and give you a tracking token.",
                reply_markup=keyboard
            )

        elif callback_data == "btn_submit_batch":
            if not config.ENABLE_BATCH_MODE:
                return
            user_id = update.effective_user.id
            batch_session = self.batch_sessions.get(user_id)
            if not batch_session or not batch_session['images']:
                await query.edit_message_text(
                    "No images to submit yet.\n\n"
                    "Send invoice photos first, then tap Submit Batch.",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Submit Batch", callback_data="btn_submit_batch"),
                            InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                        ]
                    ])
                )
                return
            await query.edit_message_text("Queuing your batch...")
            try:
                record = self.batch_manager.create_batch(
                    user_id=str(user_id),
                    username=update.effective_user.username or '',
                    invoice_paths=batch_session['images'],
                    business_type=batch_session.get('business_type', 'Purchase'),
                )
                del self.batch_sessions[user_id]
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📋 Batch Status", callback_data=f"bst_{record.token_id}"),
                        InlineKeyboardButton("❌ Cancel Batch", callback_data=f"bca_{record.token_id}"),
                    ],
                    [InlineKeyboardButton("◀ Back to Menu", callback_data="menu_main")],
                ])
                await update.effective_message.reply_text(
                    f"✅ Batch queued!\n\n"
                    f"Token: {record.token_id}\n"
                    f"Invoices: {record.total_invoices}\n\n"
                    f"The background worker will process them.",
                    reply_markup=keyboard,
                )
            except Exception as e:
                await update.effective_message.reply_text(
                    f"Failed to queue batch: {str(e)}\n\nPlease try again.",
                    reply_markup=self.create_main_menu_keyboard()
                )

        elif callback_data == "menu_my_batches":
            if not config.ENABLE_BATCH_MODE:
                return
            user_id = update.effective_user.id
            await self._show_user_batches(query, user_id)

        elif callback_data == "menu_single_order_upload":
            if not config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
                return
            user_id = update.effective_user.id
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            order_session = OrderSession(user_id, update.effective_user.username)
            self.order_sessions[user_id] = order_session
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

        elif callback_data == "menu_batch_order_upload":
            if not config.ENABLE_BATCH_MODE or not config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
                return
            user_id = update.effective_user.id
            if user_id in self.user_sessions:
                self._clear_user_session(user_id)
            self.batch_sessions[user_id] = {
                'images': [],
                'business_type': 'Sales',
                'last_button_message_id': None,
            }
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Submit Batch", callback_data="btn_submit_batch"),
                    InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                ]
            ])
            await query.edit_message_text(
                "📦 Batch Mode — Sales Order\n\n"
                "Send me all your order page images.\n"
                "All pages will be treated as one order.\n\n"
                "When you've sent everything, tap Submit Batch.\n"
                "I'll queue them for background processing and give you a tracking token.",
                reply_markup=keyboard
            )
        # ═══════════════════════════════════════════════════════

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
            
            # Clear any stale sessions to prevent state conflicts
            if user_id in self.user_sessions:
                print(f"[DEBUG] Clearing existing invoice session for user {user_id}")
                del self.user_sessions[user_id]
            if user_id in self.order_sessions:
                print(f"[DEBUG] Clearing stale order session for user {user_id}")
                del self.order_sessions[user_id]
            if user_id in self.batch_sessions:
                print(f"[DEBUG] Clearing stale batch session for user {user_id}")
                del self.batch_sessions[user_id]
            
            # Tier 4: Show mode selection when batch mode is enabled
            if config.ENABLE_BATCH_MODE:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📄 Single Mode", callback_data="menu_single_order_upload"),
                        InlineKeyboardButton("📦 Batch Mode", callback_data="menu_batch_order_upload"),
                    ],
                    [InlineKeyboardButton("◀ Back", callback_data="menu_main")]
                ])
                await query.edit_message_text(
                    "📦 Sales Order\n\n"
                    "Choose processing mode:\n\n"
                    "Single Mode — process one order now\n"
                    "Batch Mode — queue order pages for background processing",
                    reply_markup=keyboard
                )
            else:
                # Start order upload session (single mode)
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
                    await query.edit_message_text(
                        "❌ No pages uploaded yet.\n\nSend photos first, then submit.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
                        ])
                    )
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
                await query.edit_message_text(
                    "No images found yet. Send me a photo first!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
                    ])
                )
                return
            # Delegate to done_command — create a fake text message context
            await self.done_command(update, context)
            return

        # ═══════════════════════════════════════════════════════
        # PROCESSING WATCHDOG BUTTONS
        # ═══════════════════════════════════════════════════════
        elif callback_data == "btn_cancel_processing":
            task = self._active_processing_tasks.get(user_id)
            if task and not task.done():
                task.cancel()
            if user_id in self.order_sessions:
                del self.order_sessions[user_id]
            if user_id in self.user_sessions:
                self._clear_user_session(user_id)
            if user_id in self.batch_sessions:
                del self.batch_sessions[user_id]
            self._retry_context.pop(user_id, None)
            try:
                await query.edit_message_text(
                    "✅ Processing cancelled."
                )
            except Exception:
                pass
            await update.effective_message.reply_text(
                await self._get_main_menu_text(user_id),
                reply_markup=self.create_main_menu_keyboard()
            )
            return

        elif callback_data == "btn_keep_waiting":
            try:
                await query.edit_message_text(
                    "👍 Got it — still working on your request. "
                    "We'll let you know as soon as it's done!"
                )
            except Exception:
                pass
            return

        elif callback_data == "btn_switch_to_batch":
            if not getattr(config, 'ENABLE_BATCH_MODE', False) or self.batch_manager is None:
                await query.edit_message_text(
                    "❌ Batch mode is not available right now.",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            task = self._active_processing_tasks.pop(user_id, None)
            if task and not task.done():
                task.cancel()
            retry_ctx = self._retry_context.pop(user_id, {})
            session = self.user_sessions.get(user_id, {})
            image_paths = retry_ctx.get('image_paths') or session.get('images', [])
            if not image_paths:
                await query.edit_message_text(
                    "No images found to queue.\n\n"
                    "Please upload your invoices again.",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            try:
                await query.edit_message_text("📦 Switching to batch processing...")
                record = self.batch_manager.create_batch(
                    user_id=str(user_id),
                    username=update.effective_user.username or '',
                    invoice_paths=image_paths,
                    business_type='Purchase',
                )
                if user_id in self.user_sessions:
                    self._clear_user_session(user_id)
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📋 Batch Status", callback_data=f"bst_{record.token_id}"),
                        InlineKeyboardButton("❌ Cancel Batch", callback_data=f"bca_{record.token_id}"),
                    ],
                    [InlineKeyboardButton("◀ Back to Menu", callback_data="menu_main")],
                ])
                await update.effective_message.reply_text(
                    f"✅ Switched to batch processing!\n\n"
                    f"Token: {record.token_id}\n"
                    f"Invoices: {record.total_invoices}\n\n"
                    f"Your images are queued for background processing. "
                    f"You'll be notified when they're done.",
                    reply_markup=keyboard,
                )
            except Exception as e:
                print(f"[WATCHDOG] Failed to switch to batch: {e}")
                await update.effective_message.reply_text(
                    f"Failed to queue batch: {str(e)}\n\nPlease try again.",
                    reply_markup=self.create_main_menu_keyboard()
                )
            return

        # ═══════════════════════════════════════════════════════

        elif callback_data == "btn_cancel":
            # Cancel any active processing task first
            task = self._active_processing_tasks.pop(user_id, None)
            if task and not task.done():
                task.cancel()
            self._retry_context.pop(user_id, None)
            # Clear order, invoice, and batch sessions
            cancelled = False
            if user_id in self.order_sessions:
                del self.order_sessions[user_id]
                cancelled = True
            if user_id in self.user_sessions:
                self._clear_user_session(user_id)
                cancelled = True
            if user_id in self.batch_sessions:
                del self.batch_sessions[user_id]
                cancelled = True
            menu_text = await self._get_main_menu_text(user_id)
            if cancelled:
                await query.edit_message_text(
                    f"✅ All cleared!\n\n{menu_text}",
                    reply_markup=self.create_main_menu_keyboard()
                )
            else:
                await query.edit_message_text(
                    menu_text,
                    reply_markup=self.create_main_menu_keyboard()
                )
            return
        
        elif callback_data == "btn_save_sheets":
            # Save invoice to Google Sheets (from review screen)
            session = self._get_user_session(user_id)
            if session['state'] != 'reviewing':
                await query.edit_message_text(
                    "No invoice waiting for confirmation.\n\n"
                    "Start a new one?",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            await query.edit_message_text("💾 Saving to Google Sheets...")
            await self._save_invoice_to_sheets(update, user_id, session)
            return
        
        elif callback_data == "btn_download_csv":
            # Download CSV (from review screen)
            session = self._get_user_session(user_id)
            if session['state'] != 'reviewing':
                await query.edit_message_text(
                    "No invoice waiting for confirmation.\n\n"
                    "Start a new one?",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            await query.edit_message_text("⏳ Generating CSV files...")
            try:
                from exports.invoice_csv_exporter import InvoiceCSVExporter
                import os
                
                exporter = InvoiceCSVExporter()
                invoice_data = session['data']['invoice_data']
                line_items = session['data'].get('line_items', [])
                invoice_no = invoice_data.get('Invoice_No', 'Invoice').replace('/', '_')
                msg = update.effective_message
                
                header_path = exporter.export_header(invoice_data)
                await msg.reply_document(
                    document=open(header_path, 'rb'),
                    filename=f"{invoice_no}_header.csv",
                    caption="📊 Invoice Header CSV"
                )
                os.remove(header_path)
                
                if line_items:
                    items_path = exporter.export_line_items(invoice_data, line_items)
                    await msg.reply_document(
                        document=open(items_path, 'rb'),
                        filename=f"{invoice_no}_line_items.csv",
                        caption=f"📋 Line Items CSV ({len(line_items)} items)"
                    )
                    os.remove(items_path)
                
                # After CSV download, offer to also save to sheets
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💾 Also Save to Sheets", callback_data="btn_save_sheets")],
                    [InlineKeyboardButton("✅ Done", callback_data="btn_cancel")]
                ])
                await query.edit_message_text(
                    "✅ CSV sent!\n\nAlso save to Google Sheets?",
                    reply_markup=keyboard
                )
            except Exception as e:
                await query.edit_message_text(f"❌ CSV export failed: {str(e)}")
            return
        
        elif callback_data == "btn_save_and_csv":
            # Save to Sheets AND download CSV (from review screen)
            session = self._get_user_session(user_id)
            if session['state'] != 'reviewing':
                await query.edit_message_text(
                    "No invoice waiting for confirmation.\n\n"
                    "Start a new one?",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            await query.edit_message_text("⏳ Saving & generating CSV...")
            try:
                from exports.invoice_csv_exporter import InvoiceCSVExporter
                import os
                
                exporter = InvoiceCSVExporter()
                invoice_data = session['data']['invoice_data']
                line_items = session['data'].get('line_items', [])
                invoice_no = invoice_data.get('Invoice_No', 'Invoice').replace('/', '_')
                msg = update.effective_message
                
                # Send CSVs first
                header_path = exporter.export_header(invoice_data)
                await msg.reply_document(
                    document=open(header_path, 'rb'),
                    filename=f"{invoice_no}_header.csv",
                    caption="📊 Invoice Header CSV"
                )
                os.remove(header_path)
                
                if line_items:
                    items_path = exporter.export_line_items(invoice_data, line_items)
                    await msg.reply_document(
                        document=open(items_path, 'rb'),
                        filename=f"{invoice_no}_line_items.csv",
                        caption=f"📋 Line Items CSV ({len(line_items)} items)"
                    )
                    os.remove(items_path)
                
                # Then save to sheets
                await self._save_invoice_to_sheets(update, user_id, session)
            except Exception as e:
                await query.edit_message_text(f"❌ Failed: {str(e)}")
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
                    InlineKeyboardButton("◀ Cancel Correction", callback_data="btn_cancel_correction"),
                    InlineKeyboardButton("❌ Discard & Resend", callback_data="btn_cancel_resend"),
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
            # After corrections, go back to reviewing state with save options
            session['state'] = 'reviewing'
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💾 Save to Sheets", callback_data="btn_save_sheets"),
                    InlineKeyboardButton("📊 Download CSV", callback_data="btn_download_csv"),
                ],
                [
                    InlineKeyboardButton("💾📊 Save & CSV", callback_data="btn_save_and_csv"),
                    InlineKeyboardButton("✏️ Corrections", callback_data="btn_correct"),
                ],
                [
                    InlineKeyboardButton("❌ Discard & Resend", callback_data="btn_cancel_resend"),
                ]
            ])
            await query.edit_message_text(
                f"✅ {correction_count} correction(s) applied!\n\nWhat would you like to do?",
                reply_markup=keyboard
            )
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
                        InlineKeyboardButton("💾 Save to Sheets", callback_data="btn_save_sheets"),
                        InlineKeyboardButton("📊 Download CSV", callback_data="btn_download_csv"),
                    ],
                    [
                        InlineKeyboardButton("💾📊 Save & CSV", callback_data="btn_save_and_csv"),
                        InlineKeyboardButton("✏️ Corrections", callback_data="btn_correct"),
                    ],
                    [
                        InlineKeyboardButton("❌ Discard & Resend", callback_data="btn_cancel_resend"),
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
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
            ])
            await query.edit_message_text(
                "✅ Invoice discarded — fresh start!\n\n"
                "Ready to try again?",
                reply_markup=upload_keyboard
            )
            return

        elif callback_data == "btn_resubmit_pages":
            if user_id in self.order_sessions:
                del self.order_sessions[user_id]
                order_session = OrderSession(user_id, update.effective_user.username)
                self.order_sessions[user_id] = order_session
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
                ])
                await query.edit_message_text(
                    "🔄 Order cleared — send your pages again.\n\n"
                    "Upload fewer pages this time to stay within your plan limit.\n\n"
                    "📌 Send me photos of the order pages, then tap ✅ Submit Order.",
                    reply_markup=keyboard
                )
            elif user_id in self.user_sessions:
                session = self.user_sessions[user_id]
                for img_path in session.get('images', []):
                    try:
                        if os.path.exists(img_path):
                            os.remove(img_path)
                    except OSError:
                        pass
                session['images'] = []
                session['state'] = 'uploading'
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Process Invoice", callback_data="btn_done"),
                        InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
                    ]
                ])
                await query.edit_message_text(
                    "🔄 Pages cleared — send your invoice images again.\n\n"
                    "Upload fewer pages this time to stay within your plan limit.",
                    reply_markup=keyboard
                )
            else:
                upload_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📸 Upload Invoice", callback_data="menu_upload"),
                        InlineKeyboardButton("📦 Sales Order", callback_data="menu_order_upload"),
                    ],
                    [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
                ])
                await query.edit_message_text(
                    "Your session expired.\n\nTap below to start a new upload.",
                    reply_markup=upload_keyboard
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
                        InlineKeyboardButton("▶ Next Invoice", callback_data="btn_next"),
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
                await query.edit_message_text(
                    "No pages yet -- send me some photos first!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
                    ])
                )
            return
        # ═══════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════
        # Epic 3: SUBSCRIPTION MENU & TIER SELECTION
        # ═══════════════════════════════════════════════════════
        elif callback_data == "menu_subscribe":
            await self._ensure_tenant_manager()
            if self.tenant_manager:
                tenant = await asyncio.to_thread(self.tenant_manager.get_tenant, user_id)
                if not tenant:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Get Started", callback_data="menu_main")]
                    ])
                    await query.edit_message_text(
                        "You need to register first. Tap below to get started.",
                        reply_markup=keyboard
                    )
                    return
                current_plan = tenant.get('subscription_plan', config.DEFAULT_SUBSCRIPTION_TIER)

                if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
                    await self._show_subscription_plans_enhanced(query, user_id, current_plan, tenant)
                else:
                    inv_count = tenant.get('invoice_count', '0')
                    ord_count = tenant.get('order_count', '0')
                    buttons = []
                    for tier in config.SUBSCRIPTION_TIERS:
                        label = tier['name']
                        if tier['id'] == current_plan:
                            label = f"✅ {tier['name']} (current)"
                        else:
                            label = f"💳 {tier['name']}"
                        buttons.append([
                            InlineKeyboardButton(
                                f"{label} -- {tier['description']}",
                                callback_data=f"subscribe_{tier['id']}"
                            )
                        ])
                    buttons.append([InlineKeyboardButton("📋 View Features", callback_data="subscribe_features")])
                    buttons.append([InlineKeyboardButton("◀ Back", callback_data="menu_main")])
                    await query.edit_message_text(
                        "💳 Subscription Plans\n\n"
                        f"Your current plan: {current_plan.title()}\n"
                        f"Invoices used: {inv_count}\n"
                        f"Orders used: {ord_count}\n\n"
                        "Select a plan below:",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
            else:
                await query.edit_message_text(
                    "❌ Subscription service is temporarily unavailable.",
                    reply_markup=self.create_main_menu_keyboard()
                )
            return

        elif callback_data in ("subscribe_features", "subscribe_features_limits"):
            text = self._render_feature_page("Limits", 1, 2)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Features (2/2) ▶", callback_data="subscribe_features_list")],
                [InlineKeyboardButton("◀ Back to Plans", callback_data="menu_subscribe")]
            ])
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
            return

        elif callback_data == "subscribe_features_list":
            text = self._render_feature_page("Features", 2, 2)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("◀ Limits (1/2)", callback_data="subscribe_features_limits")],
                [InlineKeyboardButton("◀ Back to Plans", callback_data="menu_subscribe")]
            ])
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
            return

        elif callback_data.startswith("subscribe_pay_"):
            parts = callback_data[len("subscribe_pay_"):].rsplit("_", 1)
            tier_id = parts[0]
            billing_period = parts[1] if len(parts) > 1 else "monthly"

            if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
                service = self._get_subscription_service()
                if not service:
                    await query.edit_message_text(
                        "❌ Payment service unavailable. Please try again later.",
                        reply_markup=self.create_main_menu_keyboard()
                    )
                    return
                await self._ensure_tenant_manager()
                tenant = (await asyncio.to_thread(self.tenant_manager.get_tenant, user_id)) if self.tenant_manager else None
                current_plan = tenant.get('subscription_plan', 'free') if tenant else 'free'
                email = tenant.get('email', '') if tenant else ''
                try:
                    from subscription.subscription_config import TIER_PLANS
                    if service.razorpay:
                        result = await asyncio.to_thread(
                            service.initiate_upgrade_link,
                            user_id=str(user_id),
                            email=email,
                            current_tier=current_plan,
                            target_tier=tier_id,
                            billing_period=billing_period,
                            tenant_id=tenant.get('tenant_id', '') if tenant else '',
                        )
                        payment_url = result.get('short_url', '')
                        amount = result.get('amount', 0)
                        plan_name = TIER_PLANS.get(tier_id, {}).get('name', tier_id.title())
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton(f"💳 Pay ₹{amount}", url=payment_url)],
                            [InlineKeyboardButton("◀ Back to Plans", callback_data="menu_subscribe")]
                        ])
                        await query.edit_message_text(
                            f"💳 *Upgrade to {plan_name}*\n\n"
                            f"Amount: ₹{amount} ({billing_period})\n\n"
                            f"Tap the button below to complete payment via Razorpay.\n"
                            f"After payment, your plan will be activated automatically.",
                            parse_mode='Markdown',
                            reply_markup=keyboard
                        )
                    else:
                        result = await asyncio.to_thread(
                            service.activate_without_payment,
                            user_id=str(user_id),
                            email=email,
                            current_tier=current_plan,
                            target_tier=tier_id,
                            billing_period=billing_period,
                            tenant_id=tenant.get('tenant_id', '') if tenant else '',
                        )
                        plan_name = TIER_PLANS.get(tier_id, {}).get('name', tier_id.title())
                        expires = result.get('expires_at', '')[:10]
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("◀ Back to Plans", callback_data="menu_subscribe")],
                            [InlineKeyboardButton("◀ Main Menu", callback_data="menu_main")]
                        ])
                        await query.edit_message_text(
                            f"✅ *Plan upgraded to {plan_name}!*\n\n"
                            f"Billing: {billing_period.capitalize()}\n"
                            f"Expires: {expires}\n\n"
                            f"Your new plan is now active.",
                            parse_mode='Markdown',
                            reply_markup=keyboard
                        )
                except ValueError as e:
                    await query.edit_message_text(
                        f"❌ {str(e)}", reply_markup=self.create_main_menu_keyboard()
                    )
            return

        elif callback_data.startswith("subscribe_downgrade_confirm_"):
            tier_id = callback_data[len("subscribe_downgrade_confirm_"):]
            if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
                service = self._get_subscription_service()
                if not service:
                    await query.edit_message_text(
                        "❌ Service unavailable.", reply_markup=self.create_main_menu_keyboard()
                    )
                    return
                await self._ensure_tenant_manager()
                tenant = (await asyncio.to_thread(self.tenant_manager.get_tenant, user_id)) if self.tenant_manager else None
                current_plan = tenant.get('subscription_plan', 'free') if tenant else 'free'
                email = tenant.get('email', '') if tenant else ''
                try:
                    result = await asyncio.to_thread(
                        service.initiate_downgrade,
                        user_id=str(user_id),
                        email=email,
                        current_tier=current_plan,
                        target_tier=tier_id,
                        tenant_id=tenant.get('tenant_id', '') if tenant else '',
                    )
                    from subscription.subscription_config import TIER_PLANS
                    plan_name = TIER_PLANS.get(tier_id, {}).get('name', tier_id.title())
                    effective = result.get('effective_date', '')
                    msg = f"✅ Downgrade to {plan_name} scheduled."
                    if effective:
                        msg += f"\nEffective: {effective[:10]}"
                    await query.edit_message_text(
                        msg, reply_markup=self.create_main_menu_keyboard()
                    )
                except ValueError as e:
                    await query.edit_message_text(
                        f"❌ {str(e)}", reply_markup=self.create_main_menu_keyboard()
                    )
            return

        elif callback_data.startswith("subscribe_downgrade_"):
            tier_id = callback_data[len("subscribe_downgrade_"):]
            if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
                from subscription.subscription_config import TIER_PLANS
                plan_name = TIER_PLANS.get(tier_id, {}).get('name', tier_id.title())
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        f"✅ Yes, downgrade to {plan_name}",
                        callback_data=f"subscribe_downgrade_confirm_{tier_id}"
                    )],
                    [InlineKeyboardButton("◀ Back to Plans", callback_data="menu_subscribe")]
                ])
                await query.edit_message_text(
                    f"⚠️ Downgrade to {plan_name}?\n\n"
                    f"You may lose access to features on your current plan.\n"
                    f"Downgrade takes effect at the end of your billing period.",
                    reply_markup=keyboard
                )
            return

        elif callback_data == "subscribe_history":
            if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
                service = self._get_subscription_service()
                if not service:
                    await query.edit_message_text(
                        "❌ Service unavailable.", reply_markup=self.create_main_menu_keyboard()
                    )
                    return
                await self._ensure_tenant_manager()
                tenant = (await asyncio.to_thread(self.tenant_manager.get_tenant, user_id)) if self.tenant_manager else None
                email = tenant.get('email', '') if tenant else ''
                txns = await asyncio.to_thread(service.get_transactions, user_id=str(user_id), email=email, limit=5)
                if not txns:
                    text = "🧾 *Transaction History*\n\nNo transactions yet."
                else:
                    lines = ["🧾 *Transaction History*\n"]
                    for t in txns:
                        date = t.get('created_at', '')[:10] if t.get('created_at') else '—'
                        amount = f"₹{t.get('amount', 0)}" if t.get('amount', 0) > 0 else "Free"
                        status_icon = "✅" if t.get('status') == 'paid' else ("❌" if t.get('status') == 'failed' else "⏳")
                        lines.append(
                            f"{status_icon} {date} | {t.get('plan_from', '?')} → {t.get('plan_to', '?')} | {amount}"
                        )
                    lines.append("\n_Showing last 5 transactions_")
                    text = "\n".join(lines)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀ Back to Plans", callback_data="menu_subscribe")]
                ])
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
            return

        elif callback_data == "subscribe_cancel":
            if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "❌ Yes, cancel my subscription",
                        callback_data="subscribe_cancel_confirm"
                    )],
                    [InlineKeyboardButton("◀ Back to Plans", callback_data="menu_subscribe")]
                ])
                await query.edit_message_text(
                    "⚠️ Cancel your subscription?\n\n"
                    "This will immediately downgrade you to the Free plan.\n"
                    "You'll lose access to paid features right away.\n\n"
                    "Contact support for refund requests.",
                    reply_markup=keyboard
                )
            return

        elif callback_data == "subscribe_cancel_confirm":
            if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
                service = self._get_subscription_service()
                if not service:
                    await query.edit_message_text(
                        "❌ Service unavailable.", reply_markup=self.create_main_menu_keyboard()
                    )
                    return
                await self._ensure_tenant_manager()
                tenant = (await asyncio.to_thread(self.tenant_manager.get_tenant, user_id)) if self.tenant_manager else None
                current_plan = tenant.get('subscription_plan', 'free') if tenant else 'free'
                email = tenant.get('email', '') if tenant else ''
                try:
                    result = await asyncio.to_thread(
                        service.cancel_subscription,
                        user_id=str(user_id),
                        email=email,
                        current_tier=current_plan,
                        tenant_id=tenant.get('tenant_id', '') if tenant else '',
                    )
                    await query.edit_message_text(
                        f"✅ Subscription cancelled.\n\n"
                        f"Previous plan: {result.get('previous_plan_name', current_plan.title())}\n"
                        f"Current plan: Free\n\n"
                        f"Contact support for refund requests.",
                        reply_markup=self.create_main_menu_keyboard()
                    )
                except ValueError as e:
                    await query.edit_message_text(
                        f"❌ {str(e)}", reply_markup=self.create_main_menu_keyboard()
                    )
            return

        elif callback_data.startswith("subscribe_"):
            tier_id = callback_data[len("subscribe_"):]
            await self._ensure_tenant_manager()
            if self.tenant_manager:
                success = await asyncio.to_thread(self.tenant_manager.update_subscription, user_id, tier_id)
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
                        "❌ Couldn't update your subscription.\n\n"
                        "Please try again.",
                        reply_markup=self.create_main_menu_keyboard()
                    )
            else:
                await query.edit_message_text(
                    "❌ Subscription service is temporarily unavailable.",
                    reply_markup=self.create_main_menu_keyboard()
                )
            return
        # ═══════════════════════════════════════════════════════

        # ═══════════════════════════════════════════════════════
        # Tier 4: PER-BATCH ACTION BUTTONS (Feature-Flagged)
        # ═══════════════════════════════════════════════════════
        elif callback_data.startswith("bst_"):
            if not config.ENABLE_BATCH_MODE:
                return
            token_id = callback_data[4:]
            user_id = update.effective_user.id
            try:
                record = self.batch_manager.get_status(token_id)
            except Exception as e:
                await query.edit_message_text(
                    f"Could not fetch status: {str(e)}",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            if not record:
                await query.edit_message_text(
                    f"Batch not found: {token_id}",
                    reply_markup=self.create_main_menu_keyboard()
                )
                return
            detail = self._format_batch_detail(record)
            buttons = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data=f"bst_{token_id}"),
                    InlineKeyboardButton("❌ Cancel Batch", callback_data=f"bca_{token_id}"),
                ],
                [InlineKeyboardButton("📋 All Batches", callback_data="menu_my_batches")],
                [InlineKeyboardButton("◀ Back to Menu", callback_data="menu_main")],
            ]
            await query.edit_message_text(
                f"📋 Batch Status\n\n{detail}",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return

        elif callback_data.startswith("bca_"):
            if not config.ENABLE_BATCH_MODE:
                return
            token_id = callback_data[4:]
            user_id = update.effective_user.id
            result = self.batch_manager.cancel_batch(token_id, str(user_id))
            if result['success']:
                await query.edit_message_text(
                    f"✅ Batch cancelled: {token_id}",
                    reply_markup=self.create_main_menu_keyboard()
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                buttons = [
                    [InlineKeyboardButton("🔄 Refresh Status", callback_data=f"bst_{token_id}")],
                    [InlineKeyboardButton("◀ Back to Menu", callback_data="menu_main")],
                ]
                await query.edit_message_text(
                    f"Cannot cancel: {error_msg}",
                    reply_markup=InlineKeyboardMarkup(buttons),
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
                    InlineKeyboardButton("▶ Next Invoice", callback_data="btn_next"),
                    InlineKeyboardButton("✅ Process All", callback_data="btn_done"),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
            ])
            await query.edit_message_text(
                "📦 Batch mode — ready for multiple invoices!\n\n"
                "1. Send pages for the first invoice\n"
                "2. Tap ▶ Next Invoice\n"
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
            await query.edit_message_text(
                "📄 GSTR-1 Export\n\n"
                "Select the month:",
                reply_markup=self.create_month_picker("gstr1")
            )
        
        elif callback_data == "gen_gstr3b":
            await query.edit_message_text(
                "📋 GSTR-3B Summary\n\n"
                "Select the month:",
                reply_markup=self.create_month_picker("gstr3b")
            )
        
        elif callback_data == "gen_reports":
            await query.edit_message_text(
                "📈 Operational Reports\n\n"
                "Select report type:",
                reply_markup=self.create_report_type_picker()
            )
        
        elif callback_data == "gen_stats":
            await query.edit_message_text("📊 Generating statistics...")
            nav_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Reports & Exports", callback_data="menu_generate"),
                    InlineKeyboardButton("📋 Main Menu", callback_data="menu_main"),
                ]
            ])
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
                    await query.message.reply_text(message, reply_markup=nav_keyboard)
                else:
                    await query.message.reply_text(f"❌ {result['message']}", reply_markup=nav_keyboard)
            except Exception as e:
                await query.message.reply_text(f"❌ Error: {str(e)}", reply_markup=nav_keyboard)
        
        # ═══════════════════════════════════════════════════════
        # MONTH / YEAR / TYPE PICKER CALLBACKS
        # ═══════════════════════════════════════════════════════

        elif callback_data.startswith("month_"):
            from calendar import month_name as _mn
            parts = callback_data.split("_")
            cmd_prefix = parts[1]
            month_num = int(parts[2])
            if cmd_prefix == "stats":
                session = self._get_user_session(user_id)
                session['export_command'] = 'reports'
                session['report_type'] = '5'
                session['export_month'] = month_num
                session['export_step'] = 'year'
                await query.edit_message_text(
                    f"📊 Detailed Reports\n\n"
                    f"Month: {_mn[month_num]}\n\n"
                    f"Select the year:",
                    reply_markup=self.create_year_picker(cmd_prefix, month_num)
                )
            else:
                session = self._get_user_session(user_id)
                session['export_command'] = cmd_prefix
                session['export_month'] = month_num
                session['export_step'] = 'year'
                if cmd_prefix == "gstr1":
                    label = "📄 GSTR-1 Export"
                elif cmd_prefix == "gstr3b":
                    label = "📋 GSTR-3B Summary"
                else:
                    label = "📈 Operational Reports"
                await query.edit_message_text(
                    f"{label}\n\n"
                    f"Month: {_mn[month_num]}\n\n"
                    f"Select the year:",
                    reply_markup=self.create_year_picker(cmd_prefix, month_num)
                )
            return

        elif callback_data.startswith("year_"):
            from calendar import month_name as _mn
            parts = callback_data.split("_")
            cmd_prefix = parts[1]
            month_num = int(parts[2])
            year_num = int(parts[3])
            session = self._get_user_session(user_id)
            session['export_month'] = month_num
            session['export_year'] = year_num
            if cmd_prefix == "gstr1":
                session['export_command'] = 'gstr1'
                session['export_step'] = 'type'
                await query.edit_message_text(
                    f"📄 GSTR-1 Export\n\n"
                    f"Period: {_mn[month_num]} {year_num}\n\n"
                    f"Select export type:",
                    reply_markup=self.create_gstr1_type_picker(month_num, year_num)
                )
            elif cmd_prefix == "gstr3b":
                session['export_command'] = 'gstr3b'
                session['export_step'] = None
                await query.edit_message_text(
                    f"📋 GSTR-3B Summary\n\n"
                    f"Period: {_mn[month_num]} {year_num}\n\n"
                    f"⏳ Generating export..."
                )
                await self.tier3_handlers._execute_export(
                    update, session
                )
            elif cmd_prefix == "stats":
                session['export_command'] = 'reports'
                session['report_type'] = '5'
                session['export_step'] = None
                await query.edit_message_text(
                    f"📊 Detailed Reports\n\n"
                    f"Period: {_mn[month_num]} {year_num}\n\n"
                    f"⏳ Generating comprehensive report..."
                )
                await self.tier3_handlers._execute_export(
                    update, session
                )
            elif cmd_prefix.startswith("rpt"):
                report_num = cmd_prefix[3:]
                session['export_command'] = 'reports'
                session['report_type'] = report_num
                session['export_step'] = None
                await query.edit_message_text(
                    f"📈 Generating report...\n\n"
                    f"Period: {_mn[month_num]} {year_num}\n\n"
                    f"⏳ Please wait..."
                )
                await self.tier3_handlers._execute_export(
                    update, session
                )
            return

        elif callback_data.startswith("gstr1type_"):
            parts = callback_data.split("_")
            month_num = int(parts[1])
            year_num = int(parts[2])
            type_num = parts[3]
            session = self._get_user_session(user_id)
            session['export_command'] = 'gstr1'
            session['export_month'] = month_num
            session['export_year'] = year_num
            session['export_type'] = type_num
            session['export_step'] = None
            await query.edit_message_text(
                "📄 GSTR-1 Export\n\n"
                "⏳ Generating export..."
            )
            await self.tier3_handlers._execute_export(
                update, session
            )
            return

        elif callback_data.startswith("report_type_"):
            report_num = callback_data.split("_")[2]
            session = self._get_user_session(user_id)
            session['export_command'] = 'reports'
            session['report_type'] = report_num
            if report_num in ('2', '3', '5'):
                await query.edit_message_text(
                    "📈 Operational Reports\n\n"
                    "Select the month:",
                    reply_markup=self.create_month_picker(f"rpt{report_num}")
                )
            else:
                session['export_step'] = None
                await query.edit_message_text(
                    "📈 Generating report...\n\n"
                    "⏳ Please wait..."
                )
                await self.tier3_handlers._execute_export(
                    update, session
                )
            return

        # ═══════════════════════════════════════════════════════
        # HELP SUBMENU ACTIONS
        # ═══════════════════════════════════════════════════════
        
        elif callback_data == "help_start":
            help_text = (
                "✅ Getting Started\n"
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
                [InlineKeyboardButton("◀ Back", callback_data="menu_help")]
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
                "  2. Tap ▶ Next Invoice\n"
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
                    "  ◀  Cancel Correction -- go back to review\n"
                    "  ❌  Discard & Resend -- start fresh"
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
            help_text = (
                "✉ Contact Support\n"
                "\n"
                "For Technical Issues:\n"
                "  Contact your system administrator\n"
                "\n"
                "For Bot Usage Questions:\n"
                "  Use the help menu above\n"
                "\n"
                "For Feature Requests:\n"
                "  Discuss with your administrator\n"
                "\n"
                "─────────────────────\n"
                "📋 Bot Info\n"
                "  Features: OCR, Validation, Batch, GSTR, CSV\n"
                "  Supported: JPG, PNG images\n"
                f"  Version: v{config.BOT_VERSION} | {config.BOT_BUILD_NAME}"
            )
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_help_submenu()
            )
        
        elif callback_data == "help_cancel":
            help_text = (
                "❌ Cancel Operation\n"
                "\n"
                "Use /cancel at any time to stop the current\n"
                "operation and return to a clean state.\n"
                "\n"
                "This works for:\n"
                "• Invoice uploads in progress\n"
                "• Sales order sessions\n"
                "• Batch uploads being built\n"
                "• Any multi-step workflow\n"
                "\n"
                "After cancelling, you can start a new\n"
                "operation right away."
            )
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_help_submenu()
            )
        
        elif callback_data == "help_reports":
            help_text = (
                "📊 Generate Reports\n"
                "\n"
                "Use /generate to access reports and exports.\n"
                "\n"
                "Available options:\n"
                "• GSTR-1 / GSTR-2 reports\n"
                "• CSV data export\n"
                "• Quick stats overview\n"
                "\n"
                "Reports are generated from your processed\n"
                "invoices stored in Google Sheets."
            )
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_help_submenu()
            )
        
        elif callback_data == "help_subscription":
            help_text = (
                "💳 Manage Subscription\n"
                "\n"
                "Use /subscribe to view and manage your plan.\n"
                "\n"
                "From subscription settings you can:\n"
                "• View your current plan and usage\n"
                "• Check remaining quota\n"
                "• Compare plan features\n"
                "• Upgrade via Razorpay (cards, UPI, netbanking)\n"
                "• Downgrade to a lower plan\n"
                "• Cancel subscription (immediate downgrade to Free)\n"
                "• View transaction history\n"
                "\n"
                "Plans: Free, Basic (₹499/mo), Premium (₹1499/mo)\n"
                "Downgrades take effect at end of billing period.\n"
                "Cancellations are immediate; contact support for refunds."
            )
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_help_submenu()
            )
        
        elif callback_data == "help_batch":
            help_text = (
                "📋 Batch Status & Cancel\n"
                "\n"
                "Check batch progress:\n"
                "  /batch_status — View all your batches\n"
                "  and their current processing status\n"
                "\n"
                "Cancel a batch:\n"
                "  /batch_cancel — Stop a queued or\n"
                "  running batch from processing further\n"
                "\n"
                "Batch modes are available for both\n"
                "Purchase Orders and Sales Orders.\n"
                "Select 'Batch Mode' when prompted after\n"
                "/upload or /order_upload."
            )
            await query.edit_message_text(
                help_text,
                reply_markup=self.create_help_submenu()
            )
        
        # ═══════════════════════════════════════════════════════
        # USAGE/STATS SUBMENU ACTIONS
        # ═══════════════════════════════════════════════════════
        
        elif callback_data == "stats_quick":
            await query.edit_message_text("📊 Generating quick statistics...")
            nav_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 More Stats", callback_data="menu_usage"),
                    InlineKeyboardButton("📋 Main Menu", callback_data="menu_main"),
                ]
            ])
            try:
                result = self.tier3_handlers.reporter.generate_processing_stats()
                if result['success']:
                    message = "📊 QUICK STATISTICS\n\n"
                    message += f"Total Invoices: {result['total_invoices']}\n\n"
                    message += "VALIDATION STATUS\n"
                    for status, count in result['status_breakdown'].items():
                        pct = result['status_percentages'].get(status, 0)
                        message += f"  {status}: {count} ({pct:.1f}%)\n"
                    await query.message.reply_text(message, reply_markup=nav_keyboard)
                else:
                    await query.message.reply_text(f"❌ {result['message']}", reply_markup=nav_keyboard)
            except Exception as e:
                await query.message.reply_text(f"❌ Error: {str(e)}", reply_markup=nav_keyboard)
        
        elif callback_data == "stats_detailed":
            await query.edit_message_text(
                "📊 Detailed Reports\n\n"
                "Select the month for your comprehensive report:",
                reply_markup=self.create_month_picker("stats")
            )
        
        elif callback_data == "stats_history":
            help_text = """📅 Processing History

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
                [InlineKeyboardButton("◀ Back", callback_data="menu_generate")]
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
        
        # (CSV/Save actions are handled by btn_save_sheets, btn_download_csv, btn_save_and_csv above)
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        user_id = update.effective_user.id
        
        cancelled = False
        if user_id in self.order_sessions:
            del self.order_sessions[user_id]
            cancelled = True
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            self._clear_user_session(user_id)
            cancelled = True
        if hasattr(self, 'batch_sessions') and user_id in self.batch_sessions:
            del self.batch_sessions[user_id]
            cancelled = True
        
        menu_text = await self._get_main_menu_text(user_id)
        if cancelled:
            await update.message.reply_text(
                f"✅ All cleared!\n\n{menu_text}",
                reply_markup=self.create_main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                menu_text,
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
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "No invoice waiting to confirm.\n\n"
                "Start by uploading an invoice.",
                reply_markup=keyboard
            )
            return
        
        # Save directly to sheets (text command = quick save)
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
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
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
                InlineKeyboardButton("◀ Cancel Correction", callback_data="btn_cancel_correction"),
                InlineKeyboardButton("❌ Discard & Resend", callback_data="btn_cancel_resend"),
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
        
        # Mark as duplicate override so _save_invoice_to_sheets picks it up later
        session['is_duplicate_override'] = True
        
        # Save directly (override = user already decided)
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
            tenant_sheet_id = await self._get_tenant_sheet_id(user_id)
            await asyncio.to_thread(self._ensure_sheets_manager, tenant_sheet_id)
            if config.ENABLE_AUDIT_LOGGING:
                await asyncio.to_thread(
                    self.sheets_manager.append_invoice_with_audit,
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
                await asyncio.to_thread(
                    self.sheets_manager.append_invoice_with_items,
                    header_row,
                    line_items_data,
                    validation_result
                )
            
            # Update customer master (Tier 3 feature)
            await asyncio.to_thread(self._update_customer_master_data, invoice_data)
            
            # Update seller master (Tier 3 feature)
            await asyncio.to_thread(self._update_seller_master_data, invoice_data)
            
            # Update HSN master from line items (Tier 3 feature)
            await asyncio.to_thread(self._update_hsn_master_data, session['data']['line_items'])
            
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
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
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
            await self._ensure_tenant_manager()
            if self.tenant_manager:
                try:
                    await asyncio.to_thread(self.tenant_manager.increment_invoice_counter, user_id)
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
            success_message += f"\n⏳ Processed in {processing_time:.1f}s\n"
        
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
            session['state'] = 'reviewing'
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💾 Save to Sheets", callback_data="btn_save_sheets"),
                    InlineKeyboardButton("📊 Download CSV", callback_data="btn_download_csv"),
                ],
                [
                    InlineKeyboardButton("💾📊 Save & CSV", callback_data="btn_save_and_csv"),
                    InlineKeyboardButton("✏️ Corrections", callback_data="btn_correct"),
                ],
                [
                    InlineKeyboardButton("❌ Discard & Resend", callback_data="btn_cancel_resend"),
                ]
            ])
            await msg.reply_text(
                f"✅ {correction_count} correction(s) applied!\n\nWhat would you like to do?",
                reply_markup=keyboard
            )
            return
        
        if not session['images'] and not session.get('batch'):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Upload Invoice", callback_data="menu_upload")],
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
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
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "No images yet! Send me a photo first.",
                reply_markup=keyboard
            )
            return
        
        # Tier limit check (additive, behind feature flag)
        if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
            limit_msg = await self._check_tier_limit(user_id, 'invoices', len(session['images']))
            if limit_msg:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Resubmit Pages", callback_data="btn_resubmit_pages")],
                    [InlineKeyboardButton("⬆ Upgrade Plan", callback_data="menu_subscribe")],
                    [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
                ])
                await msg.reply_text(
                    f"⚠️ {limit_msg}",
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

        chat_id = update.effective_chat.id
        processing_task = asyncio.create_task(
            self._run_invoice_pipeline(msg, user_id, session, image_paths)
        )
        self._active_processing_tasks[user_id] = processing_task
        self._retry_context[user_id] = {
            'operation': 'invoice',
            'msg': msg,
            'session': session,
            'image_paths': image_paths,
            'update': update,
            'context': context,
        }

        watchdog_task = asyncio.create_task(
            self._processing_watchdog(chat_id, user_id, processing_task, context, 'invoice')
        )

        try:
            while True:
                current_task = self._active_processing_tasks.get(user_id)
                if current_task is None or current_task.done():
                    break
                try:
                    await current_task
                    break
                except asyncio.CancelledError:
                    new_task = self._active_processing_tasks.get(user_id)
                    if new_task is not None and new_task is not current_task and not new_task.done():
                        continue
                    raise
        except asyncio.CancelledError:
            await msg.reply_text(
                "✅ Invoice processing cancelled.\n\n"
                + await self._get_main_menu_text(user_id),
                reply_markup=self.create_main_menu_keyboard()
            )
        except Exception as e:
            error_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="menu_upload")],
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
            ])
            await msg.reply_text(
                "❌ Something went wrong during processing.\n\n"
                f"Details: {str(e)}\n\n"
                "This can happen with blurry images or unusual formats.\n"
                "Try re-sending a clearer photo.",
                reply_markup=error_keyboard
            )
            print(f"Error processing invoice for user {user_id}: {str(e)}")
        finally:
            watchdog_task.cancel()
            self._active_processing_tasks.pop(user_id, None)
            self._retry_context.pop(user_id, None)

    async def _run_invoice_pipeline(self, msg, user_id: int, session: dict, image_paths: list):
        """Run the invoice OCR / parse / validate pipeline (used as a cancellable task)."""
        # Step 1: OCR - Extract text from all images
        await msg.reply_text("⏳ Reading invoice text...  (1/4)")
        ocr_start_time = datetime.now()

        ocr_result = await asyncio.to_thread(self.ocr_engine.extract_text_from_images, image_paths)

        if isinstance(ocr_result, dict):
            ocr_text = ocr_result['text']
            if config.ENABLE_USAGE_TRACKING and 'pages_metadata' in ocr_result:
                session['_ocr_metadata'] = {
                    'pages': ocr_result['pages_metadata'],
                    'ocr_time_seconds': (datetime.now() - ocr_start_time).total_seconds()
                }
        else:
            ocr_text = ocr_result

        session['ocr_text'] = ocr_text

        # Step 2: Parse GST data with Tier 1 (line items + validation)
        await msg.reply_text("⏳ Extracting GST details...  (2/4)")
        parsing_start_time = datetime.now()

        result = await asyncio.to_thread(self.gst_parser.parse_invoice_with_validation, ocr_text)

        parsing_time_seconds = (datetime.now() - parsing_start_time).total_seconds()

        if config.ENABLE_USAGE_TRACKING:
            session['_parsing_metadata'] = {
                'parsing_time_seconds': parsing_time_seconds,
                'ocr_text_length': len(ocr_text)
            }

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
                        InlineKeyboardButton("💾 Save to Sheets", callback_data="btn_save_sheets"),
                        InlineKeyboardButton("📊 Download CSV", callback_data="btn_download_csv"),
                    ],
                    [
                        InlineKeyboardButton("💾📊 Save & CSV", callback_data="btn_save_and_csv"),
                        InlineKeyboardButton("✏️ Corrections", callback_data="btn_correct"),
                    ],
                    [
                        InlineKeyboardButton("❌ Discard & Resend", callback_data="btn_cancel_resend"),
                    ]
                ])
                await msg.reply_text(review_msg, reply_markup=review_keyboard)
                return

        # Step 5: Tier 2 - Deduplication Check (warn-only mode)
        if config.ENABLE_DEDUPLICATION and self.dedup_manager:
            fingerprint = self.dedup_manager.generate_fingerprint(invoice_data)
            session['fingerprint'] = fingerprint

            tenant_sheet_id = await self._get_tenant_sheet_id(user_id)
            await asyncio.to_thread(self._ensure_sheets_manager, tenant_sheet_id)
            is_duplicate, existing_invoice = await asyncio.to_thread(
                self.sheets_manager.check_duplicate_advanced, fingerprint
            )

            if is_duplicate:
                session['is_duplicate'] = True
                session['duplicate_info'] = existing_invoice

                warning_msg = self.dedup_manager.format_duplicate_warning_brief(
                    invoice_data,
                    existing_invoice
                )
                await msg.reply_text(warning_msg)

                print(f"[DUPLICATE] Invoice {invoice_data.get('Invoice_No', 'unknown')} detected as duplicate but saving anyway (warn-only mode)")

        # No review needed - show save options directly
        session['state'] = 'reviewing'
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💾 Save to Sheets", callback_data="btn_save_sheets"),
                InlineKeyboardButton("📊 Download CSV", callback_data="btn_download_csv"),
            ],
            [
                InlineKeyboardButton("💾📊 Save & CSV", callback_data="btn_save_and_csv"),
            ],
            [
                InlineKeyboardButton("❌ Discard & Resend", callback_data="btn_cancel_resend"),
            ]
        ])
        await msg.reply_text(
            "✅ Validation complete!\n\nWhat would you like to do?",
            reply_markup=keyboard
        )
    
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
        
        # Tier 4: Show mode selection when batch mode is enabled
        if config.ENABLE_BATCH_MODE:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📄 Single Mode", callback_data="menu_single_order_upload"),
                    InlineKeyboardButton("📦 Batch Mode", callback_data="menu_batch_order_upload"),
                ],
                [InlineKeyboardButton("◀ Back", callback_data="menu_main")]
            ])
            await update.message.reply_text(
                "📦 Sales Order\n\n"
                "Choose processing mode:\n\n"
                "Single Mode — process one order now\n"
                "Batch Mode — queue order pages for background processing",
                reply_markup=keyboard
            )
            return
        
        # Create order session (single mode when batch is disabled)
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
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
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
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
            ])
            await update.effective_message.reply_text(
                "Your order session expired.\n\nTap below to start a new one.",
                reply_markup=keyboard
            )
            return
        
        order_session = self.order_sessions[user_id]
        
        # Tier limit check for orders (additive, behind feature flag)
        if config.FEATURE_SUBSCRIPTION_MANAGEMENT:
            limit_msg = await self._check_tier_limit(user_id, 'orders')
            if limit_msg:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Resubmit Pages", callback_data="btn_resubmit_pages")],
                    [InlineKeyboardButton("⬆ Upgrade Plan", callback_data="menu_subscribe")],
                    [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
                ])
                await update.effective_message.reply_text(
                    f"⚠️ {limit_msg}",
                    reply_markup=keyboard
                )
                return
        
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
        tenant_sheet_id = await self._get_tenant_sheet_id(user_id)
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
        
        # Process the order with a watchdog that warns the user if it takes too long
        chat_id = update.effective_chat.id
        processing_task = asyncio.create_task(
            order_orchestrator.process_order(order_session, update, output_format=output_format)
        )
        self._active_processing_tasks[user_id] = processing_task
        self._retry_context[user_id] = {
            'operation': 'order',
            'output_format': output_format,
            'order_session': order_session,
            'order_orchestrator': order_orchestrator,
            'update': update,
            'context': context,
        }

        watchdog_task = asyncio.create_task(
            self._processing_watchdog(chat_id, user_id, processing_task, context, 'order')
        )

        try:
            while True:
                current_task = self._active_processing_tasks.get(user_id)
                if current_task is None or current_task.done():
                    break
                try:
                    await current_task
                    break
                except asyncio.CancelledError:
                    new_task = self._active_processing_tasks.get(user_id)
                    if new_task is not None and new_task is not current_task and not new_task.done():
                        continue
                    raise

            # ── Tenant: increment order counter ───────────────
            await self._ensure_tenant_manager()
            if self.tenant_manager:
                try:
                    await asyncio.to_thread(self.tenant_manager.increment_order_counter, user_id)
                except Exception:
                    pass
            # ──────────────────────────────────────────────────

            await update.effective_message.reply_text(
                await self._get_main_menu_text(user_id),
                reply_markup=self.create_main_menu_keyboard()
            )
        except asyncio.CancelledError:
            await update.effective_message.reply_text(
                "✅ Order processing cancelled.\n\n"
                + await self._get_main_menu_text(user_id),
                reply_markup=self.create_main_menu_keyboard()
            )
        except Exception as e:
            print(f"[ERROR] Order processing failed: {e}")
            import traceback
            traceback.print_exc()
            order_error_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="menu_order_upload")],
                [InlineKeyboardButton("📋 Main Menu", callback_data="menu_main")]
            ])
            await update.effective_message.reply_text(
                f"❌ Couldn't process that order.\n\n"
                f"Details: {str(e)}\n\n"
                f"Try re-sending clearer photos.",
                reply_markup=order_error_keyboard
            )
        finally:
            watchdog_task.cancel()
            self._active_processing_tasks.pop(user_id, None)
            self._retry_context.pop(user_id, None)
            if user_id in self.order_sessions:
                del self.order_sessions[user_id]
    
    async def _update_order_status_message(self, order_session, chat_id: int, context, max_reached: bool = False):
        """Remove buttons from the previous status message, then send a new one with the cumulative total."""
        count = len(order_session.pages)
        label = "page" if count == 1 else "pages"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Submit Order", callback_data="btn_order_submit"),
                InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
            ]
        ])

        if max_reached:
            text = (
                f"⚠️ Maximum {config.MAX_IMAGES_PER_ORDER} pages per order.\n"
                f"Tap Submit Order or Cancel."
            )
        else:
            text = (
                f"📄 Received {count} {label}.\n\n"
                f"Got more pages? Send them.\n"
                f"All done? Tap Submit Order below."
            )

        if order_session.last_button_message_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=order_session.last_button_message_id,
                    reply_markup=None,
                )
            except Exception:
                pass

        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
        )
        order_session.last_button_message_id = msg.message_id

    async def handle_order_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle order photo uploads (separate from invoice photos)"""
        if not config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
            return
        
        user_id = update.effective_user.id
        
        if user_id not in self.order_sessions:
            return
        
        order_session = self.order_sessions[user_id]
        
        # Check max images
        if len(order_session.pages) >= config.MAX_IMAGES_PER_ORDER:
            await self._update_order_status_message(
                order_session, update.effective_chat.id, context, max_reached=True
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
            
            order_session.add_page(filepath)
            
            await self._update_order_status_message(
                order_session, update.effective_chat.id, context
            )
            
        except Exception as e:
            print(f"[ERROR] Order photo download failed: {e}")
            await update.message.reply_text(
                f"❌ Couldn't download that image.\n\n"
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
            await self._update_order_status_message(
                order_session, update.effective_chat.id, context, max_reached=True
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
            
            order_session.add_page(filepath)
            
            await self._update_order_status_message(
                order_session, update.effective_chat.id, context
            )
            
        except Exception as e:
            print(f"[ERROR] Order document download failed: {e}")
            await update.message.reply_text(
                f"❌ Couldn't download that image.\n\n"
                f"Please try sending it again."
            )
    
    # ═══════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════
    # Tier 4: Batch Processing Commands & Handlers (Feature-Flagged)
    # ═══════════════════════════════════════════════════════════════════

    async def _update_batch_status_message(self, batch_session: dict, chat_id: int, context):
        """Remove buttons from the previous status message, then send a new one with the cumulative total."""
        count = len(batch_session['images'])
        label = "invoice" if count == 1 else "invoices"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Submit Batch", callback_data="btn_submit_batch"),
                InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel"),
            ]
        ])
        text = (
            f"📄 Received {count} {label}.\n\n"
            f"Send more, or tap Submit Batch when done."
        )

        if batch_session.get('last_button_message_id'):
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=batch_session['last_button_message_id'],
                    reply_markup=None,
                )
            except Exception:
                pass

        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
        )
        batch_session['last_button_message_id'] = msg.message_id

    async def _handle_batch_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photos sent during a batch session."""
        user_id = update.effective_user.id
        batch_session = self.batch_sessions.get(user_id)
        if not batch_session:
            return

        photo = update.message.photo[-1]
        try:
            file = await photo.get_file()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"batch_{user_id}_{timestamp}.jpg"
            filepath = os.path.join(config.TEMP_FOLDER, filename)
            await file.download_to_drive(filepath)
            batch_session['images'].append(filepath)

            await self._update_batch_status_message(
                batch_session, update.effective_chat.id, context
            )
        except Exception as e:
            await update.message.reply_text(
                f"Could not download that image. Please try again."
            )

    async def _handle_batch_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle documents (image files) sent during a batch session."""
        user_id = update.effective_user.id
        batch_session = self.batch_sessions.get(user_id)
        if not batch_session:
            return
        document = update.message.document
        try:
            file = await context.bot.get_file(document.file_id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = document.file_name or 'batch_doc.jpg'
            filename = f"batch_{user_id}_{timestamp}_{file_name}"
            filepath = os.path.join(config.TEMP_FOLDER, filename)
            await file.download_to_drive(filepath)
            batch_session['images'].append(filepath)

            await self._update_batch_status_message(
                batch_session, update.effective_chat.id, context
            )
        except Exception:
            await update.message.reply_text(
                "Could not download that file. Please try again."
            )

    async def batch_submit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /submit_batch command."""
        if not config.ENABLE_BATCH_MODE:
            return
        user_id = update.effective_user.id
        batch_session = self.batch_sessions.get(user_id)
        if not batch_session or not batch_session['images']:
            await update.message.reply_text(
                "No batch images to submit.\n\n"
                "Start batch mode from the menu first, send photos, then /submit_batch."
            )
            return
        await update.message.reply_text("Queuing your batch...")
        try:
            record = self.batch_manager.create_batch(
                user_id=str(user_id),
                username=update.effective_user.username or '',
                invoice_paths=batch_session['images'],
                business_type=batch_session.get('business_type', 'Purchase'),
            )
            del self.batch_sessions[user_id]
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📋 Batch Status", callback_data=f"bst_{record.token_id}"),
                    InlineKeyboardButton("❌ Cancel Batch", callback_data=f"bca_{record.token_id}"),
                ],
                [InlineKeyboardButton("◀ Back to Menu", callback_data="menu_main")],
            ])
            await update.message.reply_text(
                f"✅ Batch queued!\n\n"
                f"Token: {record.token_id}\n"
                f"Invoices: {record.total_invoices}\n\n"
                f"The background worker will process them.",
                reply_markup=keyboard,
            )
        except Exception as e:
            await update.message.reply_text(
                f"Failed to queue batch: {str(e)}\nPlease try again.",
                reply_markup=self.create_main_menu_keyboard()
            )

    async def batch_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /batch_status TOKEN command."""
        if not config.ENABLE_BATCH_MODE:
            return
        args = context.args
        if not args:
            await update.message.reply_text(
                "Usage: /batch_status TOKEN_ID\n\n"
                "Example: /batch_status BATCH-20260216-12345-A7F92K"
            )
            return
        token_id = args[0]
        record = self.batch_manager.get_status(token_id)
        if not record:
            await update.message.reply_text(f"Batch not found: {token_id}")
            return
        await update.message.reply_text(
            f"Batch Status: {token_id}\n\n"
            f"Status: {record.status}\n"
            f"Stage: {record.current_stage}\n"
            f"Total: {record.total_invoices}\n"
            f"Processed: {record.processed_count}\n"
            f"Failed: {record.failed_count}\n"
            f"Review: {record.review_count}\n"
            f"Last Update: {record.last_update}\n"
            f"Created: {record.created_at}"
        )

    async def batch_cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /batch_cancel TOKEN command."""
        if not config.ENABLE_BATCH_MODE:
            return
        args = context.args
        if not args:
            await update.message.reply_text(
                "Usage: /batch_cancel TOKEN_ID\n\n"
                "Example: /batch_cancel BATCH-20260216-12345-A7F92K"
            )
            return
        token_id = args[0]
        user_id = update.effective_user.id
        result = self.batch_manager.cancel_batch(token_id, str(user_id))
        if result['success']:
            await update.message.reply_text(
                f"Batch cancelled: {token_id}",
                reply_markup=self.create_main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                f"Cannot cancel: {result.get('error', 'Unknown error')}"
            )

    @staticmethod
    def _format_batch_detail(rec, index: int = None) -> str:
        """Format a BatchRecord into a detailed text block."""
        prefix = f"{index}. " if index is not None else ""
        progress = f"{rec.processed_count}/{rec.total_invoices} processed"
        if rec.failed_count:
            progress += f", {rec.failed_count} failed"
        if rec.review_count:
            progress += f", {rec.review_count} review"
        return (
            f"{prefix}{rec.token_id}\n"
            f"   Status: {rec.status}\n"
            f"   Stage: {rec.current_stage}\n"
            f"   Progress: {progress}\n"
            f"   Created: {rec.created_at}\n"
            f"   Last Update: {rec.last_update or '—'}"
        )

    @staticmethod
    def _build_batch_action_buttons(batches) -> list:
        """Build per-batch inline keyboard rows with Refresh and Cancel buttons."""
        rows = []
        for rec in batches:
            tid = rec.token_id
            rows.append([
                InlineKeyboardButton(f"🔄 Refresh {tid[-6:]}", callback_data=f"bst_{tid}"),
                InlineKeyboardButton(f"❌ Cancel {tid[-6:]}", callback_data=f"bca_{tid}"),
            ])
        rows.append([InlineKeyboardButton("◀ Back to Menu", callback_data="menu_main")])
        return rows

    async def my_batches_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /my_batches command — list all outstanding batches for the user."""
        if not config.ENABLE_BATCH_MODE:
            return
        user_id = update.effective_user.id
        try:
            batches = self.batch_manager.get_user_batches(str(user_id), outstanding_only=True)
        except Exception as e:
            await update.message.reply_text(
                f"Could not retrieve batches: {str(e)}",
                reply_markup=self.create_main_menu_keyboard()
            )
            return

        if not batches:
            await update.message.reply_text(
                "You have no outstanding batches.\n\n"
                "Start a batch from 📸 Purchase Order > Batch Mode.",
                reply_markup=self.create_main_menu_keyboard()
            )
            return

        lines = ["📋 Batch Status\n"]
        for i, rec in enumerate(batches, 1):
            lines.append(self._format_batch_detail(rec, index=i))
            lines.append("")

        keyboard = InlineKeyboardMarkup(self._build_batch_action_buttons(batches))
        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=keyboard,
        )

    async def _show_user_batches(self, query, user_id: int):
        """Shared logic for displaying outstanding batches (used by callback and command)."""
        try:
            batches = self.batch_manager.get_user_batches(str(user_id), outstanding_only=True)
        except Exception as e:
            await query.edit_message_text(
                f"Could not retrieve batches: {str(e)}",
                reply_markup=self.create_main_menu_keyboard()
            )
            return

        if not batches:
            await query.edit_message_text(
                "You have no outstanding batches.\n\n"
                "Start a batch from 📸 Purchase Order > Batch Mode.",
                reply_markup=self.create_main_menu_keyboard()
            )
            return

        lines = ["📋 Batch Status\n"]
        for i, rec in enumerate(batches, 1):
            lines.append(self._format_batch_detail(rec, index=i))
            lines.append("")

        keyboard = InlineKeyboardMarkup(self._build_batch_action_buttons(batches))
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=keyboard,
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

        # ═══════════════════════════════════════════════════════════════════
        # Tier 4: Check if this is a batch photo (Feature-Flagged)
        # ═══════════════════════════════════════════════════════════════════
        if config.ENABLE_BATCH_MODE and user_id in self.batch_sessions:
            await self._handle_batch_photo(update, context)
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
                            "⏳ The download timed out.\n\n"
                            "This usually means a slow connection.\n"
                            "Try sending the image again."
                        )
                    else:
                        await update.message.reply_text(
                            f"❌ Couldn't download that image.\n\n"
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

        # ═══════════════════════════════════════════════════════════════════
        # Tier 4: Check if user is in batch mode (Feature-Flagged)
        # ═══════════════════════════════════════════════════════════════════
        if config.ENABLE_BATCH_MODE and user_id in self.batch_sessions:
            document = update.message.document
            mime_type = document.mime_type or ''
            file_name = document.file_name or ''
            is_image = (
                mime_type.startswith('image/') or
                file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            )
            if is_image:
                await self._handle_batch_document(update, context)
                return
            else:
                await update.message.reply_text(
                    "📦 You're in batch upload mode.\n\n"
                    "Please send images (JPG/PNG) of your invoices.\n"
                    "Tap Submit Batch when done or Cancel to abort."
                )
                return
        # ═══════════════════════════════════════════════════════════════════
        
        # No order session — proceed with invoice flow
        session = self._get_user_session(user_id)
        
        if session['state'] not in ['uploading', 'reviewing', 'correcting', 'confirming_duplicate']:
            await update.message.reply_text(
                "Please finish your current operation first.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel")]
                ])
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
                                "⏳ The download timed out.\n\n"
                                "The file might be too large. A few tips:\n"
                                "  • Send as a photo (not file) — it's faster\n"
                                "  • Try a smaller or compressed image\n"
                                "  • Check your internet connection"
                            )
                        else:
                            await update.message.reply_text(
                                f"❌ Couldn't download that file.\n\n"
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
                await self._ensure_tenant_manager()
                if self.tenant_manager:
                    await asyncio.to_thread(
                        self.tenant_manager.register_tenant,
                        user_id=user_id,
                        first_name=tenant_name,
                        username=username,
                        email=email,
                    )
                    await update.message.reply_text(
                        "You're all set! ✅\n\n"
                        "Registration complete. Let's get started!",
                        reply_markup=self.create_main_menu_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Registration service is temporarily unavailable.\n\n"
                        "Please try again in a moment by tapping /start.",
                        reply_markup=self.create_main_menu_keyboard()
                    )
            except Exception as e:
                print(f"[WARNING] Tenant registration failed: {e}")
                await update.message.reply_text(
                    "❌ Something went wrong with registration.\n\n"
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
                        InlineKeyboardButton("◀ Cancel Correction", callback_data="btn_cancel_correction"),
                        InlineKeyboardButton("❌ Discard & Resend", callback_data="btn_cancel_resend"),
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
        await update.message.reply_text(
            "I didn't catch that.\n\n"
            "Send me an invoice photo to get started, or pick an option below.",
            reply_markup=self.create_main_menu_keyboard()
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
        # Tier 4: Batch Processing command handlers (Feature-Flagged)
        # ═══════════════════════════════════════════════════════
        if config.ENABLE_BATCH_MODE:
            application.add_handler(CommandHandler("submit_batch", self.batch_submit_command))
            application.add_handler(CommandHandler("batch_status", self.batch_status_command))
            application.add_handler(CommandHandler("batch_cancel", self.batch_cancel_command))
            application.add_handler(CommandHandler("my_batches", self.my_batches_command))
            print("[OK] Tier 4: Batch commands registered (including /my_batches)")
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
                    drop_pending_updates=False,
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
