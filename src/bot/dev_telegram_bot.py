"""
Dev Telegram Bot for GST Scanner
--------------------------------

Safe, non-destructive bot used only in development.

Phase 7 Update - Order Upload Integration:
- /order_upload - Start order upload session
- Send images - Collect order images
- /done_order - Process collected images through full pipeline
- /cancel_order - Cancel current order session

Behaviour:
- Uses BOT_ENV=dev and TELEGRAM_DEV_BOT_TOKEN from config
- Long-polling only (no webhooks)
- Prefixes all replies with "[DEV BOT]"
- Order upload only active when ENABLE_ORDER_UPLOAD=true

Production bot and existing GST flows remain untouched.
"""
import sys
import os
from typing import Final, Optional, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

try:
    from src import config
    from src.order_upload_orchestrator import OrderUploadOrchestrator
    from src.order_upload_image import generate_order_image
except ImportError:
    import config
    from order_upload_orchestrator import OrderUploadOrchestrator
    from order_upload_image import generate_order_image


DEV_PREFIX: Final[str] = "[DEV BOT] "


# ---- Dashboard stats helpers (safe no-ops if dashboard not available) ----
def _dash_update(key, value=None, increment=1):
    try:
        from pathlib import Path
        import json
        sf = Path(__file__).resolve().parents[2] / "temp" / "dev_bot_stats.json"
        if not sf.exists():
            return
        with open(sf, "r") as f:
            stats = json.load(f)
        if value is not None:
            stats[key] = value
        else:
            stats[key] = stats.get(key, 0) + increment
        from datetime import datetime
        stats["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(sf, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


def _dash_event(event_type, detail=""):
    try:
        from pathlib import Path
        import json
        sf = Path(__file__).resolve().parents[2] / "temp" / "dev_bot_stats.json"
        if not sf.exists():
            return
        with open(sf, "r") as f:
            stats = json.load(f)
        from datetime import datetime
        evt = {"time": datetime.now().strftime("%H:%M:%S"), "type": event_type, "detail": detail[:100]}
        stats["recent_events"] = ([evt] + stats.get("recent_events", []))[:50]
        stats["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(sf, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


def _ensure_dev_environment() -> None:
    """
    Guardrail: ensure we are explicitly in dev mode and using the dev token.

    - Fails fast if BOT_ENV != 'dev'
    - Fails fast if TELEGRAM_DEV_BOT_TOKEN is missing
    - Never touches TELEGRAM_BOT_TOKEN (prod token)
    """
    if config.BOT_ENV != "dev":
        raise RuntimeError(
            "Dev bot can only run when BOT_ENV=dev. "
            "Set BOT_ENV=dev in your .env before starting the dev bot."
        )
    if not config.TELEGRAM_DEV_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_DEV_BOT_TOKEN is not set. "
            "Set it in .env before starting the dev bot."
        )


class DevGSTScannerBot:
    """
    Isolated dev bot with Order Upload capability.
    
    Session management:
    - user_sessions: Dict[user_id, {"images": List[path], "order_id": str}]
    """

    def __init__(self) -> None:
        _ensure_dev_environment()
        self.user_sessions = {}  # Track order upload sessions per user
        
        # Initialize orchestrator only if order upload is enabled
        self.orchestrator: Optional[OrderUploadOrchestrator] = None
        if config.ENABLE_ORDER_UPLOAD:
            try:
                self.orchestrator = OrderUploadOrchestrator()
            except Exception as e:
                print(f"{DEV_PREFIX}Warning: Order upload orchestrator failed to initialize: {e}")

    def _main_menu_keyboard(self):
        """Build the main menu inline keyboard."""
        buttons = []
        if config.ENABLE_ORDER_UPLOAD and self.orchestrator:
            buttons.append([InlineKeyboardButton("📤 Upload Order", callback_data="btn_order_upload")])
        if config.ORDER_UPLOAD_SHEET_ID:
            sheet_url = f"https://docs.google.com/spreadsheets/d/{config.ORDER_UPLOAD_SHEET_ID}"
            buttons.append([InlineKeyboardButton("📊 View Google Sheet", url=sheet_url)])
        buttons.append([InlineKeyboardButton("❓ Help", callback_data="btn_help")])
        return InlineKeyboardMarkup(buttons)

    def _session_keyboard(self, image_count: int = 0):
        """Build the keyboard shown during an active upload session."""
        buttons = []
        if image_count > 0:
            buttons.append([InlineKeyboardButton(f"✅ Process Order ({image_count} image{'s' if image_count != 1 else ''})", callback_data="btn_done_order")])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel_order")])
        return InlineKeyboardMarkup(buttons)

    def _post_process_keyboard(self):
        """Build the keyboard shown after processing is complete."""
        buttons = [
            [InlineKeyboardButton("📤 New Order", callback_data="btn_order_upload")],
        ]
        if config.ORDER_UPLOAD_SHEET_ID:
            sheet_url = f"https://docs.google.com/spreadsheets/d/{config.ORDER_UPLOAD_SHEET_ID}"
            buttons.append([InlineKeyboardButton("📊 View Google Sheet", url=sheet_url)])
        buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")])
        return InlineKeyboardMarkup(buttons)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _dash_update("total_messages")
        _dash_event("command", "/start")
        user = update.effective_user
        name = user.first_name if user else "there"
        text = (
            f"Hey {name}! Great to see you!\n"
            "\n"
            "I'm your SAI-ABS Order Scanner — just snap a photo of any "
            "handwritten order and I'll take care of the rest! "
            "I'll read every item, find the right prices, add it all up, "
            "and save a clean summary straight to your Google Sheet.\n"
            "\n"
            "No more manual data entry — let's get started!"
        )
        await update.message.reply_text(text, reply_markup=self._main_menu_keyboard())

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _dash_update("total_messages")
        _dash_event("command", "/help")
        help_text = (
            f"{DEV_PREFIX}How to use Order Upload:\n\n"
            "1. Tap 'Upload Order' to start a session\n"
            "2. Send one or more images of handwritten orders\n"
            "3. Tap 'Process Order' when all images are sent\n\n"
            "The bot will:\n"
            "- Extract text from handwriting (OCR)\n"
            "- Match items to the price list\n"
            "- Calculate line totals + grand total\n"
            "- Save everything to Google Sheets"
        )
        await update.message.reply_text(help_text, reply_markup=self._main_menu_keyboard())

    async def order_upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start a new order upload session. Works from both /command and button."""
        _dash_update("total_messages")
        _dash_event("command", "/order_upload")
        if not config.ENABLE_ORDER_UPLOAD or not self.orchestrator:
            msg = f"{DEV_PREFIX}Order upload is disabled. Set ENABLE_ORDER_UPLOAD=true to enable."
            if update.callback_query:
                await update.callback_query.message.reply_text(msg)
            else:
                await update.message.reply_text(msg)
            return
        
        user_id = update.effective_user.id
        msg_id = update.callback_query.message.message_id if update.callback_query else update.message.message_id
        
        # Clear any existing session
        self.user_sessions[user_id] = {
            "images": [],
            "order_id": f"order_{user_id}_{msg_id}",
        }
        _dash_update("active_sessions", value=len(self.user_sessions))
        
        text = (
            f"{DEV_PREFIX}Order upload session started!\n\n"
            "Send me images of handwritten order lists.\n"
            "I'll show you buttons to process or cancel once you've sent images."
        )
        target = update.callback_query.message if update.callback_query else update.message
        await target.reply_text(text, reply_markup=self._session_keyboard(0))

    async def done_order_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process collected images through the order upload pipeline."""
        _dash_update("total_messages")
        _dash_event("command", "/done_order")

        target = update.callback_query.message if update.callback_query else update.message

        if not config.ENABLE_ORDER_UPLOAD or not self.orchestrator:
            await target.reply_text(f"{DEV_PREFIX}Order upload is disabled.")
            return
        
        user_id = update.effective_user.id
        session = self.user_sessions.get(user_id)
        
        if not session or not session.get("images"):
            await target.reply_text(
                f"{DEV_PREFIX}No images collected yet.",
                reply_markup=self._main_menu_keyboard(),
            )
            return
        
        # Send processing message
        processing_msg = await target.reply_text(
            f"{DEV_PREFIX}Processing {len(session['images'])} image(s)...\n"
            "This may take a moment."
        )
        
        # Process through orchestrator
        result = self.orchestrator.process_order_images(
            image_paths=session["images"],
            order_id=session.get("order_id"),
        )
        
        # Update dashboard stats from result
        stats = result.get("stats", {})
        _dash_update("orders_completed")
        _dash_update("total_images_processed", increment=len(session["images"]))
        _dash_update("ocr_extractions", increment=len(session["images"]))
        _dash_update("lines_extracted", increment=stats.get("total_extracted", 0))
        _dash_update("lines_matched", increment=stats.get("matched", 0))
        _dash_update("lines_unmatched", increment=stats.get("unmatched", 0))
        _dash_update("duplicates_skipped", increment=stats.get("duplicates_skipped", 0))
        _dash_update("grand_total_value", increment=stats.get("grand_total", 0))
        if result.get("errors"):
            _dash_update("errors", increment=len(result["errors"]))
        _dash_event("process", f"Order done: {stats.get('total_extracted', 0)} lines, {stats.get('matched', 0)} matched")

        # Build response message
        response_parts = [f"{DEV_PREFIX}{result['summary']}"]
        
        if result.get("sheet_url"):
            response_parts.append(f"\nView results: {result['sheet_url']}")
        
        if result.get("errors"):
            response_parts.append(f"\nWarnings/Errors:")
            for err in result["errors"]:
                response_parts.append(f"- {err}")
        
        await target.reply_text(
            "\n".join(response_parts),
            reply_markup=self._post_process_keyboard(),
        )

        # Send the order summary (PDF or image)
        pdf_path = result.get("pdf_path")
        chat_id = update.effective_chat.id
        delivered = False

        # Strategy 1: Try sending PDF directly via Telegram sendDocument
        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as pdf_file:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=pdf_file,
                        filename=os.path.basename(pdf_path),
                        caption=f"{DEV_PREFIX}Here's your order summary PDF.",
                    )
                delivered = True
                _dash_event("info", "PDF sent via Telegram")
            except Exception as e:
                print(f"{DEV_PREFIX}sendDocument blocked (firewall): {e}")

        # Strategy 2: Render as image and send via sendPhoto (bypasses IPS)
        if not delivered:
            try:
                # Get the matched lines and totals from the orchestrator result
                img_path = generate_order_image(
                    matched_lines=result.get("_matched_lines", []),
                    grand_total=stats.get("grand_total", 0),
                    order_id=session.get("order_id"),
                    customer_info=result.get("customer_info"),
                )
                with open(img_path, "rb") as img_file:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=img_file,
                        caption=f"{DEV_PREFIX}Order summary (image). PDF also saved locally.",
                    )
                delivered = True
                _dash_event("info", "Invoice image sent via sendPhoto")
            except Exception as e:
                print(f"{DEV_PREFIX}sendPhoto fallback failed: {e}")
                _dash_event("error", f"sendPhoto failed: {e}")

        # Strategy 3: Last resort — tell user where the PDF is locally
        if not delivered:
            dashboard_port = getattr(config, "DASHBOARD_PORT", 8050)
            pdf_filename = os.path.basename(pdf_path) if pdf_path else "unknown"
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"{DEV_PREFIX}Could not send the file. PDF saved locally:\n"
                    f"http://localhost:{dashboard_port}/pdf/{pdf_filename}\n"
                    f"Or: {pdf_path}"
                ),
            )
        
        # Clear session
        del self.user_sessions[user_id]
        _dash_update("active_sessions", value=len(self.user_sessions))

    async def cancel_order_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Cancel current order upload session."""
        _dash_update("total_messages")
        _dash_event("command", "/cancel_order")
        user_id = update.effective_user.id
        target = update.callback_query.message if update.callback_query else update.message
        
        if user_id in self.user_sessions:
            # Clean up temp files
            session = self.user_sessions[user_id]
            for img_path in session.get("images", []):
                if os.path.exists(img_path):
                    try:
                        os.remove(img_path)
                    except Exception:
                        pass
            
            del self.user_sessions[user_id]
            _dash_update("orders_cancelled")
            _dash_update("active_sessions", value=len(self.user_sessions))
            await target.reply_text(
                f"{DEV_PREFIX}Order session cancelled.",
                reply_markup=self._main_menu_keyboard(),
            )
        else:
            await target.reply_text(
                f"{DEV_PREFIX}No active order session to cancel.",
                reply_markup=self._main_menu_keyboard(),
            )

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all inline keyboard button presses."""
        query = update.callback_query
        await query.answer()  # Acknowledge the button press

        action = query.data

        if action == "btn_order_upload":
            await self.order_upload_command(update, context)
        elif action == "btn_done_order":
            await self.done_order_command(update, context)
        elif action == "btn_cancel_order":
            await self.cancel_order_command(update, context)
        elif action == "btn_help":
            _dash_event("command", "/help (button)")
            help_text = (
                f"{DEV_PREFIX}How to use Order Upload:\n\n"
                "1. Tap 'Upload Order' to start a session\n"
                "2. Send one or more images of handwritten orders\n"
                "3. Tap 'Process Order' when all images are sent\n\n"
                "The bot will:\n"
                "- Extract text from handwriting (OCR)\n"
                "- Match items to the price list\n"
                "- Calculate line totals + grand total\n"
                "- Save everything to Google Sheets"
            )
            await query.message.reply_text(help_text, reply_markup=self._main_menu_keyboard())
        elif action == "btn_main_menu":
            await query.message.reply_text(
                f"{DEV_PREFIX}Main menu:",
                reply_markup=self._main_menu_keyboard(),
            )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _dash_update("total_messages")
        _dash_event("info", "Text message received")
        user_id = update.effective_user.id

        if user_id in self.user_sessions:
            await update.message.reply_text(
                f"{DEV_PREFIX}You have an active order session.\n"
                "Send images, or use the buttons below:",
                reply_markup=self._session_keyboard(len(self.user_sessions[user_id]["images"])),
            )
        else:
            await update.message.reply_text(
                f"{DEV_PREFIX}What would you like to do?",
                reply_markup=self._main_menu_keyboard(),
            )

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo uploads during order session."""
        _dash_update("total_messages")
        _dash_update("total_images_received")
        _dash_event("image", "Image uploaded")
        user_id = update.effective_user.id
        session = self.user_sessions.get(user_id)
        
        if not session:
            await update.message.reply_text(
                f"{DEV_PREFIX}Image received, but no active order session.\n"
                "Use /order_upload to start a session first."
            )
            return
        
        # Download the image
        try:
            photo = update.message.photo[-1]  # Get highest resolution
            file = await context.bot.get_file(photo.file_id)
            
            # Save to temp folder
            temp_folder = config.TEMP_FOLDER or "temp"
            os.makedirs(temp_folder, exist_ok=True)
            
            file_path = os.path.join(temp_folder, f"{photo.file_id}.jpg")
            await file.download_to_drive(file_path)
            
            # Add to session
            session["images"].append(file_path)
            
            await update.message.reply_text(
                f"{DEV_PREFIX}Image {len(session['images'])} received!\n"
                "Send more images, or tap a button below:",
                reply_markup=self._session_keyboard(len(session["images"])),
            )
        except Exception as e:
            _dash_update("errors")
            _dash_event("error", f"Image download failed: {str(e)[:60]}")
            await update.message.reply_text(
                f"{DEV_PREFIX}Failed to download image: {str(e)}"
            )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle document uploads — accept images sent as files, reject others."""
        _dash_update("total_messages")
        user_id = update.effective_user.id
        session = self.user_sessions.get(user_id)
        doc = update.message.document

        # Check if the document is an image (by MIME type or file extension)
        is_image = False
        if doc and doc.mime_type and doc.mime_type.startswith("image/"):
            is_image = True
        elif doc and doc.file_name:
            ext = doc.file_name.lower().rsplit(".", 1)[-1] if "." in doc.file_name else ""
            is_image = ext in ("jpg", "jpeg", "png", "bmp", "webp", "tiff", "tif")

        if not is_image:
            await update.message.reply_text(
                f"{DEV_PREFIX}This file type is not supported. Please send images only.\n"
                "Tip: You can send photos directly or as image files (JPG, PNG)."
            )
            return

        if not session:
            await update.message.reply_text(
                f"{DEV_PREFIX}Image file received, but no active order session.\n"
                "Tap 'Upload Order' to start a session first.",
                reply_markup=self._main_menu_keyboard(),
            )
            return

        # Download the image file
        try:
            _dash_update("total_images_received")
            _dash_event("image", f"Image file: {doc.file_name or 'unnamed'}")

            file = await context.bot.get_file(doc.file_id)

            temp_folder = config.TEMP_FOLDER or "temp"
            os.makedirs(temp_folder, exist_ok=True)

            # Preserve original extension, default to .jpg
            ext = ".jpg"
            if doc.file_name and "." in doc.file_name:
                ext = "." + doc.file_name.rsplit(".", 1)[-1].lower()
            file_path = os.path.join(temp_folder, f"{doc.file_id}{ext}")
            await file.download_to_drive(file_path)

            session["images"].append(file_path)

            await update.message.reply_text(
                f"{DEV_PREFIX}Image {len(session['images'])} received! ({doc.file_name or 'image'})\n"
                "Send more images, or tap a button below:",
                reply_markup=self._session_keyboard(len(session["images"])),
            )
        except Exception as e:
            _dash_update("errors")
            _dash_event("error", f"Doc image download failed: {str(e)[:60]}")
            await update.message.reply_text(
                f"{DEV_PREFIX}Failed to download image file: {str(e)}"
            )

    def run(self) -> None:
        """
        Start the dev bot using long polling only.

        Guardrails:
        - Uses TELEGRAM_DEV_BOT_TOKEN exclusively
        - Does not import or touch production GSTScannerBot
        """
        import ssl
        from telegram.request import HTTPXRequest

        # Build SSL context from Windows/OS certificate store so the bot
        # works behind corporate proxies that inject their own CA certs.
        ssl_context = ssl.create_default_context()
        ssl_context.load_default_certs()

        # Also load our exported CA bundle if it exists
        ca_bundle = os.environ.get("SSL_CERT_FILE", "")
        if ca_bundle and os.path.exists(ca_bundle):
            ssl_context.load_verify_locations(ca_bundle)

        # Create custom HTTPXRequest that uses the OS cert store
        custom_request = HTTPXRequest(
            http_version="1.1",
            httpx_kwargs={"verify": ssl_context},
        )
        custom_get_updates_request = HTTPXRequest(
            http_version="1.1",
            httpx_kwargs={"verify": ssl_context},
        )

        application = (
            Application.builder()
            .token(config.TELEGRAM_DEV_BOT_TOKEN)
            .request(custom_request)
            .get_updates_request(custom_get_updates_request)
            .build()
        )

        # Command handlers (still work if user types them)
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        
        if config.ENABLE_ORDER_UPLOAD:
            application.add_handler(CommandHandler("order_upload", self.order_upload_command))
            application.add_handler(CommandHandler("done_order", self.done_order_command))
            application.add_handler(CommandHandler("cancel_order", self.cancel_order_command))
        
        # Inline button handler
        application.add_handler(CallbackQueryHandler(self.handle_button))
        
        # Message handlers
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )

        print("=" * 80)
        print("GST SCANNER DEV BOT (NON-DESTRUCTIVE)")
        print("=" * 80)
        print(f"BOT_ENV={config.BOT_ENV}")
        print(f"ENABLE_ORDER_UPLOAD={config.ENABLE_ORDER_UPLOAD}")
        print("Replies are prefixed with '[DEV BOT]'.")
        if config.ENABLE_ORDER_UPLOAD:
            print("Order upload workflow: /order_upload > send images > /done_order")
        print("=" * 80)

        # Set dashboard status to running
        from datetime import datetime
        _dash_update("bot_status", value="running")
        _dash_update("bot_started_at", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if config.ORDER_UPLOAD_SHEET_ID:
            _dash_update("sheet_id", value=config.ORDER_UPLOAD_SHEET_ID)
        _dash_event("info", "Dev bot started")

        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> None:
    """Entry point for running the dev bot directly."""
    try:
        bot = DevGSTScannerBot()
        bot.run()
    except Exception as e:
        print(f"{DEV_PREFIX}Failed to start dev bot: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()

