"""
Telegram Bot Tier 3 Command Handlers
Extension module for Tier 3 features: batch processing and export commands

This module adds:
- /next command for batch invoice processing
- /export_gstr1 command for GSTR-1 exports
- /export_gstr3b command for GSTR-3B summary
- /reports command for operational reports
- /stats command for quick statistics
"""
import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from calendar import month_name

import config
from exports.gstr1_exporter import GSTR1Exporter
from exports.gstr3b_generator import GSTR3BGenerator
from exports.operational_reports import OperationalReporter
from utils.batch_processor import BatchProcessor


class Tier3CommandHandlers:
    """Tier 3 command handlers for batch processing and exports"""
    
    def __init__(self, bot_instance):
        """
        Initialize Tier 3 handlers
        
        Args:
            bot_instance: Reference to main GSTScannerBot instance
        """
        self.bot = bot_instance
        self.gstr1_exporter = GSTR1Exporter(bot_instance.sheets_manager)
        self.gstr3b_generator = GSTR3BGenerator(bot_instance.sheets_manager)
        self.reporter = OperationalReporter(bot_instance.sheets_manager)
        
        # Initialize batch processor
        self.batch_processor = BatchProcessor(
            bot_instance.ocr_engine,
            bot_instance.gst_parser,
            bot_instance.gst_parser.gst_validator,  # Fixed: use gst_validator not validator
            bot_instance.sheets_manager
        )
    
    # ════════════════════════════════════════════════════════════════════
    # BATCH PROCESSING COMMANDS
    # ════════════════════════════════════════════════════════════════════
    
    async def next_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /next command - Save current invoice images and start next one
        
        Allows processing multiple invoices in one session
        """
        user_id = update.effective_user.id
        session = self.bot._get_user_session(user_id)
        
        images = session.get('images', [])
        
        if not images:
            await update.message.reply_text(
                "⚠️ No images to save.\n"
                "Send invoice images first, then use /next."
            )
            return
        
        # Initialize batch list if not exists
        if 'batch' not in session:
            session['batch'] = []
        
        # Save current images as one invoice in batch
        session['batch'].append(images.copy())
        batch_count = len(session['batch'])
        
        # Clear current images to start collecting next invoice
        session['images'] = []
        
        await update.message.reply_text(
            f"✅ Invoice #{batch_count} saved ({len(images)} page(s)).\n\n"
            f"📸 Send images for next invoice\n"
            f"   or\n"
            f"✅ Type /done to process batch of {batch_count} invoice(s)"
        )
    
    async def process_batch(self, update: Update, user_id: int, session: dict):
        """
        Process batch of invoices
        
        Args:
            update: Telegram update
            user_id: User ID
            session: User session with batch data
        """
        batch_invoices = session.get('batch', [])
        
        # Add current images if any
        if session.get('images'):
            batch_invoices.append(session['images'])
        
        if not batch_invoices:
            await update.message.reply_text(
                "⚠️ No invoices to process.\n"
                "Send invoice images and use /done."
            )
            return
        
        if len(batch_invoices) == 1:
            # Single invoice - use regular processing
            return False  # Signal to use regular processing
        
        # Batch processing
        await update.message.reply_text(
            f"🔄 Processing batch of {len(batch_invoices)} invoices...\n"
            f"This may take a few minutes."
        )
        
        # Progress callback
        async def progress_callback(current, total, status):
            progress_pct = (current / total * 100)
            await update.message.reply_text(
                f"⏳ Progress: {current}/{total} ({progress_pct:.0f}%)\n{status}"
            )
        
        # Get audit logger if available
        audit_logger = getattr(self.bot, 'audit_logger', None)
        username = update.effective_user.username or update.effective_user.first_name
        
        # Process batch
        result = self.batch_processor.process_batch(
            batch_invoices,
            progress_callback,
            audit_logger,
            str(user_id),
            username
        )
        
        # Send results
        success_emoji = "✅" if result['successful'] > 0 else "❌"
        await update.message.reply_text(
            f"{success_emoji} Batch processing complete!\n\n"
            f"✅ Successful: {result['successful']}/{result['total']}\n"
            f"❌ Failed: {result['failed']}/{result['total']}\n"
            f"📊 Success Rate: {result['success_rate']:.1f}%"
        )
        
        # Send detailed report
        report = self.batch_processor.generate_batch_report(result)
        
        # Send report as file
        report_path = f"{config.TEMP_FOLDER}/batch_report_{user_id}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        await update.message.reply_document(
            document=open(report_path, 'rb'),
            filename=f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            caption="📄 Detailed batch processing report"
        )
        
        # Clean up
        os.remove(report_path)
        self.bot._clear_user_session(user_id)
        
        return True  # Signal that batch was processed
    
    # ════════════════════════════════════════════════════════════════════
    # EXPORT COMMANDS
    # ════════════════════════════════════════════════════════════════════
    
    async def export_gstr1_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /export_gstr1 command - Interactive GSTR-1 export"""
        user_id = update.effective_user.id
        session = self.bot._get_user_session(user_id)
        
        # Set state for multi-step interaction
        session['export_command'] = 'gstr1'
        session['export_step'] = 'month'
        
        await update.message.reply_text(
            "📊 GSTR-1 Export\n\n"
            "Enter the month (1-12):"
        )
    
    async def export_gstr3b_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /export_gstr3b command - Interactive GSTR-3B export"""
        user_id = update.effective_user.id
        session = self.bot._get_user_session(user_id)
        
        session['export_command'] = 'gstr3b'
        session['export_step'] = 'month'
        
        await update.message.reply_text(
            "📊 GSTR-3B Summary Generation\n\n"
            "Enter the month (1-12):"
        )
    
    async def reports_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reports command - Interactive report generation"""
        user_id = update.effective_user.id
        session = self.bot._get_user_session(user_id)
        
        session['export_command'] = 'reports'
        session['export_step'] = 'type'
        
        await update.message.reply_text(
            "📈 Operational Reports\n\n"
            "Select report type:\n"
            "1️⃣ Processing Statistics\n"
            "2️⃣ GST Summary (monthly)\n"
            "3️⃣ Duplicate Attempts\n"
            "4️⃣ Correction Analysis\n"
            "5️⃣ Comprehensive Report\n\n"
            "Reply with number (1-5):"
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - Quick statistics"""
        await update.message.reply_text("📊 Generating statistics...")
        
        try:
            result = self.reporter.generate_processing_stats()
            
            if result['success']:
                message = "📊 **Processing Statistics**\n\n"
                message += f"Total Invoices: {result['total_invoices']}\n\n"
                message += "**Validation Status:**\n"
                
                for status, count in result['status_breakdown'].items():
                    pct = result['status_percentages'].get(status, 0)
                    message += f"  {status}: {count} ({pct:.1f}%)\n"
                
                if result['top_errors']:
                    message += "\n**Top Errors:**\n"
                    for error in result['top_errors'][:3]:
                        message += f"  • {error['type']}: {error['count']}\n"
                
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(f"❌ {result['message']}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_export_interaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle text messages during export command interactions
        
        Returns:
            True if message was handled as export interaction, False otherwise
        """
        user_id = update.effective_user.id
        session = self.bot._get_user_session(user_id)
        
        export_command = session.get('export_command')
        if not export_command:
            return False
        
        export_step = session.get('export_step')
        message_text = update.message.text.strip()
        
        # Handle month input
        if export_step == 'month':
            try:
                month = int(message_text)
                if 1 <= month <= 12:
                    session['export_month'] = month
                    session['export_step'] = 'year'
                    await update.message.reply_text(
                        f"✓ Month: {month_name[month]}\n\n"
                        "Enter the year (e.g., 2026):"
                    )
                    return True
                else:
                    await update.message.reply_text("❌ Please enter 1-12")
                    return True
            except ValueError:
                await update.message.reply_text("❌ Please enter a valid number")
                return True
        
        # Handle year input
        elif export_step == 'year':
            try:
                year = int(message_text)
                if 2000 <= year <= 2100:
                    session['export_year'] = year
                    
                    if export_command == 'gstr1':
                        session['export_step'] = 'type'
                        await update.message.reply_text(
                            f"✓ Period: {month_name[session['export_month']]} {year}\n\n"
                            "Select export type:\n"
                            "1️⃣ B2B Invoices\n"
                            "2️⃣ B2C Small\n"
                            "3️⃣ HSN Summary\n"
                            "4️⃣ All Three\n\n"
                            "Reply with number (1-4):"
                        )
                    else:
                        # GSTR-3B or reports - execute now
                        await self._execute_export(update, session)
                    return True
                else:
                    await update.message.reply_text("❌ Please enter a valid year")
                    return True
            except ValueError:
                await update.message.reply_text("❌ Please enter a valid number")
                return True
        
        # Handle GSTR-1 type selection
        elif export_step == 'type' and export_command == 'gstr1':
            if message_text in ['1', '2', '3', '4']:
                session['export_type'] = message_text
                await self._execute_export(update, session)
                return True
            else:
                await update.message.reply_text("❌ Please reply with 1, 2, 3, or 4")
                return True
        
        # Handle reports type selection
        elif export_step == 'type' and export_command == 'reports':
            if message_text in ['1', '2', '3', '4', '5']:
                session['report_type'] = message_text
                
                if message_text in ['2', '3', '5']:
                    # Need period for these reports
                    session['export_step'] = 'month'
                    await update.message.reply_text("Enter the month (1-12):")
                else:
                    # Execute immediately for stats and corrections
                    await self._execute_export(update, session)
                return True
            else:
                await update.message.reply_text("❌ Please reply with 1-5")
                return True
        
        return False
    
    async def _execute_export(self, update: Update, session: dict):
        """Execute the export based on session data"""
        export_command = session['export_command']
        month = session.get('export_month')
        year = session.get('export_year')
        
        await update.message.reply_text("⏳ Generating export... This may take a moment.")
        
        try:
            if export_command == 'gstr1':
                await self._execute_gstr1_export(update, session, month, year)
            elif export_command == 'gstr3b':
                await self._execute_gstr3b_export(update, month, year)
            elif export_command == 'reports':
                await self._execute_reports(update, session, month, year)
        except Exception as e:
            await update.message.reply_text(f"❌ Export failed: {str(e)}")
        finally:
            # Clear export session
            session.pop('export_command', None)
            session.pop('export_step', None)
            session.pop('export_month', None)
            session.pop('export_year', None)
            session.pop('export_type', None)
            session.pop('report_type', None)
    
    async def _execute_gstr1_export(self, update: Update, session: dict, month: int, year: int):
        """Execute GSTR-1 export"""
        export_type = session.get('export_type')
        period_str = f"{year}_{month:02d}"
        output_dir = f"{config.TEMP_FOLDER}/GSTR1_{period_str}"
        os.makedirs(output_dir, exist_ok=True)
        
        type_map = {
            '1': ('b2b', 'B2B Invoices'),
            '2': ('b2c', 'B2C Small'),
            '3': ('hsn', 'HSN Summary'),
            '4': ('all', 'All Three')
        }
        
        type_code, type_name = type_map[export_type]
        
        if type_code == 'all':
            result = self.gstr1_exporter.export_all(month, year, output_dir)
            
            if result['success']:
                message = f"✅ GSTR-1 Export Complete - {month_name[month]} {year}\n\n"
                message += f"B2B: {result['b2b']['invoice_count']} invoices\n"
                message += f"B2C: {result['b2c']['invoice_count']} invoices\n"
                message += f"HSN: {result['hsn']['unique_hsn_count']} codes\n"
                
                await update.message.reply_text(message)
                
                # Send files
                for filename in [
                    f"B2B_Invoices_{period_str}.csv",
                    f"B2C_Small_{period_str}.csv",
                    f"HSN_Summary_{period_str}.csv",
                    f"Export_Report_{period_str}.txt"
                ]:
                    filepath = os.path.join(output_dir, filename)
                    if os.path.exists(filepath):
                        await update.message.reply_document(
                            document=open(filepath, 'rb'),
                            filename=filename
                        )
        else:
            # Single export type
            if type_code == 'b2b':
                output_path = os.path.join(output_dir, f"B2B_Invoices_{period_str}.csv")
                result = self.gstr1_exporter.export_b2b(month, year, output_path)
            elif type_code == 'b2c':
                output_path = os.path.join(output_dir, f"B2C_Small_{period_str}.csv")
                result = self.gstr1_exporter.export_b2c_small(month, year, output_path)
            else:  # hsn
                output_path = os.path.join(output_dir, f"HSN_Summary_{period_str}.csv")
                result = self.gstr1_exporter.export_hsn_summary(month, year, output_path)
            
            if result['success']:
                await update.message.reply_text(f"✅ {result['message']}")
                await update.message.reply_document(
                    document=open(result['output_file'], 'rb'),
                    filename=os.path.basename(result['output_file'])
                )
    
    async def _execute_gstr3b_export(self, update: Update, month: int, year: int):
        """Execute GSTR-3B export"""
        period_str = f"{year}_{month:02d}"
        output_dir = f"{config.TEMP_FOLDER}/GSTR3B_{period_str}"
        os.makedirs(output_dir, exist_ok=True)
        
        json_path = os.path.join(output_dir, f"GSTR3B_Summary_{period_str}.json")
        text_path = os.path.join(output_dir, f"GSTR3B_Report_{period_str}.txt")
        
        result = self.gstr3b_generator.generate_summary(month, year, json_path)
        
        if result['success']:
            summary = result['data']['summary']
            total_tax = summary['total_tax_liability']
            
            message = f"✅ GSTR-3B Summary - {month_name[month]} {year}\n\n"
            message += f"Total Invoices: {summary['total_invoices']}\n"
            message += f"Total Tax Liability: Rs. {total_tax['total']:,.2f}\n"
            
            await update.message.reply_text(message)
            
            # Generate and send text report
            self.gstr3b_generator.generate_formatted_report(month, year, text_path)
            
            # Send both files
            await update.message.reply_document(
                document=open(json_path, 'rb'),
                filename=f"GSTR3B_Summary_{period_str}.json"
            )
            await update.message.reply_document(
                document=open(text_path, 'rb'),
                filename=f"GSTR3B_Report_{period_str}.txt"
            )
        else:
            await update.message.reply_text(f"❌ {result['message']}")
    
    async def _execute_reports(self, update: Update, session: dict, month: int = None, year: int = None):
        """Execute operational reports"""
        report_type = session.get('report_type')
        
        if report_type == '1':  # Processing stats
            result = self.reporter.generate_processing_stats()
            report_name = "Processing_Statistics"
        elif report_type == '2':  # GST summary
            result = self.reporter.generate_gst_summary(month, year)
            report_name = f"GST_Summary_{year}_{month:02d}"
        elif report_type == '3':  # Duplicates
            result = self.reporter.generate_duplicate_report(month, year)
            report_name = f"Duplicate_Attempts_{year}_{month:02d}"
        elif report_type == '4':  # Corrections
            result = self.reporter.generate_correction_analysis()
            report_name = "Correction_Analysis"
        else:  # Comprehensive
            output_dir = f"{config.TEMP_FOLDER}/Reports_{year}_{month:02d}"
            result = self.reporter.generate_comprehensive_report(month, year, output_dir)
            
            if result['success']:
                await update.message.reply_text("✅ Reports generated!")
                await update.message.reply_document(
                    document=open(result['json_file'], 'rb'),
                    filename=os.path.basename(result['json_file'])
                )
                await update.message.reply_document(
                    document=open(result['text_file'], 'rb'),
                    filename=os.path.basename(result['text_file'])
                )
            else:
                await update.message.reply_text("❌ Report generation failed")
            return
        
        if result['success']:
            # Save and send as JSON
            import json
            output_path = f"{config.TEMP_FOLDER}/{report_name}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            await update.message.reply_text("✅ Report generated!")
            await update.message.reply_document(
                document=open(output_path, 'rb'),
                filename=f"{report_name}.json"
            )
        else:
            await update.message.reply_text(f"❌ {result['message']}")
