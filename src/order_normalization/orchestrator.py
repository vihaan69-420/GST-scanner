"""
Order Normalization Orchestrator
Main coordinator for order processing pipeline
"""
import asyncio
from datetime import datetime
from typing import Dict, List
import os
import config
from telegram.error import BadRequest
from .extractor import OrderExtractor
from .normalizer import OrderNormalizer
from .deduplicator import OrderDeduplicator
from .pricing_matcher import PricingMatcher
from .pdf_generator import OrderPDFGenerator
from .sheets_handler import OrderSheetsHandler


class OrderNormalizationOrchestrator:
    """Orchestrates the complete order normalization pipeline"""
    
    def __init__(self, sheet_id: str = None):
        """Initialize orchestrator with all components

        Args:
            sheet_id: Optional per-tenant Google Sheet ID (Epic 3).
                      When None, uses shared sheet via default config.
        """
        self.extractor = OrderExtractor()
        self.normalizer = OrderNormalizer()
        self.deduplicator = OrderDeduplicator()
        self.pricing_matcher = PricingMatcher()
        self.pdf_generator = OrderPDFGenerator()
        self.sheets_handler = OrderSheetsHandler(sheet_id=sheet_id)
    
    @staticmethod
    async def _safe_edit(msg, text: str):
        """Edit a message in-place, silently ignoring 'Message is not modified'."""
        try:
            await msg.edit_text(text)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise

    async def process_order(self, order_session, update, output_format: str = 'pdf'):
        """
        Main orchestration method - processes complete order pipeline
        
        Args:
            order_session: OrderSession object
            update: Telegram update object
            
        Pipeline:
        1. Extract line items from all pages (OCR + LLM)
        2. Normalize fields (part names, colors, models)
        3. Deduplicate across pages
        4. Match with pricing sheet
        5. Compute totals
        6. Build clean invoice model
        7. Generate PDF
        8. Upload to Google Sheets
        9. Send PDF to user
        """
        try:
            order_session.set_processing()

            # Single progress message — edited in-place for each step
            progress_msg = await update.effective_message.reply_text(
                "🔄 Step 1/6: Extracting order data from images..."
            )
            
            # === PHASE 1: EXTRACTION ===
            try:
                print(f"[ORCHESTRATOR] Starting extraction for {order_session.order_id}...")
                
                extracted_pages = await asyncio.to_thread(
                    self.extractor.extract_all_pages, order_session.pages
                )
                
                # Check if extraction yielded any lines
                total_lines = sum(len(page.get('lines_raw', [])) for page in extracted_pages)
                if total_lines == 0:
                    raise Exception("No line items extracted from images. Please check image quality.")
                
                # Extract order metadata from first page
                order_metadata = {}
                if extracted_pages and 'order_metadata' in extracted_pages[0]:
                    order_metadata = extracted_pages[0]['order_metadata']
                    print(f"[ORCHESTRATOR] Order metadata: {order_metadata}")
                
                print(f"[ORCHESTRATOR] Extracted {total_lines} lines from {len(extracted_pages)} pages")
                
            except Exception as e:
                order_session.set_failed(f"Extraction failed: {str(e)}")
                await self._safe_edit(
                    progress_msg,
                    f"❌ Order extraction failed.\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please try again or contact support."
                )
                return
            
            # === PHASE 2: NORMALIZATION ===
            try:
                print(f"[ORCHESTRATOR] Normalizing extracted data...")
                await self._safe_edit(progress_msg, "🔄 Step 2/6: Normalizing part names and colors...")
                
                normalized_lines = await asyncio.to_thread(
                    self.normalizer.normalize_all_lines, extracted_pages
                )
                print(f"[ORCHESTRATOR] Normalized {len(normalized_lines)} lines")
                
            except Exception as e:
                order_session.set_failed(f"Normalization failed: {str(e)}")
                await self._safe_edit(progress_msg, f"❌ Data normalization failed: {str(e)}")
                return
            
            # === PHASE 3: DEDUPLICATION (DISABLED) ===
            print(f"[ORCHESTRATOR] Skipping deduplication (disabled by user request)")
            await self._safe_edit(progress_msg, "🔄 Step 3/6: Processing all items...")
            
            # Use all normalized lines (no deduplication)
            unique_lines = normalized_lines
            print(f"[ORCHESTRATOR] Processing all {len(unique_lines)} lines (deduplication disabled)")
            
            # === PHASE 4: PRICING MATCH ===
            try:
                print(f"[ORCHESTRATOR] Matching with pricing sheet...")
                await self._safe_edit(progress_msg, "🔄 Step 4/6: Matching prices...")
                
                matched_lines = await asyncio.to_thread(
                    self.pricing_matcher.match_all_lines, unique_lines
                )
                
                # Count matches
                matched_count = sum(1 for line in matched_lines if line.get('matched', False))
                unmatched_count = len(matched_lines) - matched_count
                
                print(f"[ORCHESTRATOR] Pricing: {matched_count} matched, {unmatched_count} unmatched")
                
                if unmatched_count > 0:
                    order_session.set_review_required(
                        f"{unmatched_count} items could not be matched with pricing"
                    )
                
            except Exception as e:
                # Pricing failure is non-critical - continue with zero prices
                print(f"[WARNING] Pricing match failed: {e}")
                order_session.set_review_required(f"Pricing match failed: {str(e)}")
                matched_lines = unique_lines
                for line in matched_lines:
                    line['matched'] = False
                    line['unit_price'] = 0.0
            
            # === PHASE 5: COMPUTE TOTALS & BUILD CLEAN MODEL ===
            try:
                print(f"[ORCHESTRATOR] Building clean invoice model...")
                await self._safe_edit(progress_msg, "🔄 Step 5/6: Computing totals...")
                
                matched_lines = self.compute_line_totals(matched_lines)
                
                clean_invoice = self.build_clean_invoice(
                    matched_lines,
                    order_session.to_dict(),
                    order_metadata
                )
                
                print(f"[ORCHESTRATOR] Clean invoice: {clean_invoice['total_items']} items, "
                      f"subtotal: ₹{clean_invoice['subtotal']:.2f}")
                
            except Exception as e:
                order_session.set_failed(f"Invoice model generation failed: {str(e)}")
                await self._safe_edit(progress_msg, f"❌ Invoice generation failed: {str(e)}")
                return
            
            # === PHASE 6: GENERATE OUTPUT (PDF or CSV) ===
            output_path = None
            output_paths_extra = []
            try:
                format_label = output_format.upper()
                print(f"[ORCHESTRATOR] Generating {format_label}...")
                await self._safe_edit(progress_msg, f"🔄 Step 6/6: Generating {format_label}...")
                
                if output_format == 'csv' and config.FEATURE_ORDER_SPLIT_CSV:
                    from exports.order_csv_exporter import OrderCSVExporter
                    _csv_exporter = OrderCSVExporter()
                    session_meta = {
                        'page_count': len(order_session.pages),
                        'created_by': order_session.user_id,
                    }
                    header_path, items_path = await asyncio.to_thread(
                        _csv_exporter.export_order, clean_invoice, session_meta
                    )
                    output_path = header_path
                    if items_path:
                        output_paths_extra = [items_path]
                elif output_format == 'csv':
                    output_path = await asyncio.to_thread(
                        self.pdf_generator.generate_csv, clean_invoice
                    )
                else:
                    output_path = await asyncio.to_thread(
                        self.pdf_generator.generate_pdf, clean_invoice
                    )
                
            except Exception as e:
                print(f"[WARNING] {output_format.upper()} generation failed: {e}")
                order_session.pdf_error = str(e)
            
            # === PHASE 7: UPLOAD TO GOOGLE SHEETS ===
            try:
                print(f"[ORCHESTRATOR] Uploading to Google Sheets...")
                
                session_metadata = {
                    'page_count': len(order_session.pages),
                    'created_by': order_session.user_id
                }
                
                await asyncio.to_thread(
                    self.sheets_handler.append_order_summary, clean_invoice, session_metadata
                )
                await asyncio.to_thread(
                    self.sheets_handler.append_order_line_items, clean_invoice
                )
                await asyncio.to_thread(
                    self.sheets_handler.update_customer_details,
                    clean_invoice.get('customer_name', 'N/A'),
                    clean_invoice['order_date']
                )
                
                print(f"[ORCHESTRATOR] Successfully uploaded to Google Sheets")
                
            except Exception as e:
                print(f"[WARNING] Google Sheets upload failed: {e}")
                if output_path:
                    await update.effective_message.reply_text(
                        "⚠️ Order processed but couldn't save to Google Sheets.\n"
                        "PDF is attached below."
                    )
            
            # Remove the progress message now that processing is done
            try:
                await progress_msg.delete()
            except Exception:
                pass

            # === PHASE 8: SEND OUTPUT TO USER ===
            if output_path and os.path.exists(output_path):
                await self.send_order_output_to_user(update, clean_invoice, output_path, output_format)
                if config.FEATURE_ORDER_SPLIT_CSV and output_paths_extra:
                    for extra_path in output_paths_extra:
                        if os.path.exists(extra_path):
                            try:
                                with open(extra_path, 'rb') as ef:
                                    await update.effective_message.reply_document(
                                        document=ef,
                                        filename=os.path.basename(extra_path),
                                        caption="Order line items CSV"
                                    )
                            except Exception as send_err:
                                print(f"[WARNING] Failed to send extra CSV: {send_err}")
            else:
                await update.effective_message.reply_text(
                    "✅ Order processed and saved to Google Sheets!\n\n"
                    f"📄 Order ID: {clean_invoice['order_id']}\n"
                    f"📦 Total Items: {clean_invoice['total_items']}\n"
                    f"💰 Subtotal: ₹{clean_invoice['subtotal']:.2f}\n\n"
                    f"⚠️ {output_format.upper()} generation failed - please check Google Sheets."
                )
            
            # Mark session as completed
            order_session.set_completed(clean_invoice)
            
            # ═══════════════════════════════════════════════════════
            # Track order usage in background (non-blocking)
            # ═══════════════════════════════════════════════════════
            if config.ENABLE_USAGE_TRACKING and config.ENABLE_ORDER_TRACKING:
                try:
                    asyncio.create_task(
                        self._track_order_complete_async(
                            order_session=order_session,
                            clean_invoice=clean_invoice,
                            pdf_path=output_path
                        )
                    )
                except Exception as track_err:
                    print(f"[BACKGROUND] Could not start order tracking: {track_err}")
            # ═══════════════════════════════════════════════════════
            
        except Exception as e:
            order_session.set_failed(str(e))
            await update.effective_message.reply_text(
                f"❌ Unexpected error during processing:\n\n{str(e)}\n\n"
                f"Please contact support."
            )
            print(f"[ERROR] Orchestrator failed: {e}")

    def process_order_headless(self, pages: List[Dict], user_id: str, username: str = '', output_format: str = 'pdf') -> Dict:
        """
        Process an order without Telegram context (for batch worker).

        Args:
            pages: List of dicts with 'page_number', 'image_path', 'uploaded_at'
            user_id: User ID string
            username: Username string
            output_format: 'pdf' or 'csv'

        Returns:
            Dict with 'success', 'order_id', 'output_path', 'error', 'clean_invoice'
        """
        from .order_session import OrderSession

        order_session = OrderSession(int(user_id), username)
        for page in pages:
            order_session.add_page(page['image_path'])
        order_session.submit()
        order_session.set_processing()

        try:
            print(f"[ORCHESTRATOR-HEADLESS] Starting extraction for {order_session.order_id}...")
            extracted_pages = self.extractor.extract_all_pages(order_session.pages)
            total_lines = sum(len(page.get('lines_raw', [])) for page in extracted_pages)
            if total_lines == 0:
                raise Exception("No line items extracted from images. Please check image quality.")
            order_metadata = {}
            if extracted_pages and 'order_metadata' in extracted_pages[0]:
                order_metadata = extracted_pages[0]['order_metadata']
            print(f"[ORCHESTRATOR-HEADLESS] Extracted {total_lines} lines from {len(extracted_pages)} pages")

            print(f"[ORCHESTRATOR-HEADLESS] Normalizing extracted data...")
            normalized_lines = self.normalizer.normalize_all_lines(extracted_pages)
            print(f"[ORCHESTRATOR-HEADLESS] Normalized {len(normalized_lines)} lines")

            unique_lines = normalized_lines

            print(f"[ORCHESTRATOR-HEADLESS] Matching with pricing sheet...")
            try:
                matched_lines = self.pricing_matcher.match_all_lines(unique_lines)
            except Exception as e:
                print(f"[WARNING] Pricing match failed: {e}")
                matched_lines = unique_lines
                for line in matched_lines:
                    line['matched'] = False
                    line['unit_price'] = 0.0

            print(f"[ORCHESTRATOR-HEADLESS] Building clean invoice model...")
            matched_lines = self.compute_line_totals(matched_lines)
            clean_invoice = self.build_clean_invoice(
                matched_lines,
                order_session.to_dict(),
                order_metadata
            )

            output_path = None
            try:
                if output_format == 'csv':
                    output_path = self.pdf_generator.generate_csv(clean_invoice)
                else:
                    output_path = self.pdf_generator.generate_pdf(clean_invoice)
                print(f"[ORCHESTRATOR-HEADLESS] Generated {output_format.upper()}: {output_path}")
            except Exception as e:
                print(f"[WARNING] {output_format.upper()} generation failed: {e}")

            try:
                session_metadata = {
                    'page_count': len(order_session.pages),
                    'created_by': order_session.user_id,
                }
                self.sheets_handler.append_order_summary(clean_invoice, session_metadata)
                self.sheets_handler.append_order_line_items(clean_invoice)
                self.sheets_handler.update_customer_details(
                    clean_invoice.get('customer_name', 'N/A'),
                    clean_invoice['order_date'],
                )
                print(f"[ORCHESTRATOR-HEADLESS] Uploaded to Google Sheets")
            except Exception as e:
                print(f"[WARNING] Google Sheets upload failed: {e}")

            order_session.set_completed(clean_invoice)
            return {
                'success': True,
                'order_id': clean_invoice['order_id'],
                'output_path': output_path,
                'error': '',
                'clean_invoice': clean_invoice,
            }

        except Exception as e:
            order_session.set_failed(str(e))
            print(f"[ERROR] Orchestrator headless failed: {e}")
            return {
                'success': False,
                'order_id': getattr(order_session, 'order_id', 'UNKNOWN'),
                'output_path': None,
                'error': str(e),
                'clean_invoice': None,
            }

    def compute_line_totals(self, matched_lines: List[Dict]) -> List[Dict]:
        """
        Compute quantity × rate = line total for each line
        
        Args:
            matched_lines: Lines with pricing information
            
        Returns:
            Lines with computed totals
        """
        PRICE_CONFIDENCE_THRESHOLD = 0.80  # Only use price if match is reliable
        
        for line in matched_lines:
            line['quantity'] = int(line.get('quantity') or 0)
            match_confidence = float(line.get('match_confidence') or 0.0)
            
            # Only use the matched price if confidence is high enough
            if match_confidence >= PRICE_CONFIDENCE_THRESHOLD:
                line['rate'] = float(line.get('unit_price') or 0.0)
            else:
                line['rate'] = 0.0
            
            line['line_total'] = line['quantity'] * line['rate']
        
        return matched_lines
    
    def build_clean_invoice(self, matched_lines: List[Dict], order_session_data: Dict, order_metadata_extracted: Dict = None) -> Dict:
        """
        Build clean invoice model from matched lines
        
        Args:
            matched_lines: Lines with pricing and totals
            order_session_data: Order session metadata
            order_metadata_extracted: Extracted metadata from images (customer name, date, etc.)
            
        Returns:
            Clean invoice dictionary
        """
        clean_lines = []
        serial_no = 1
        
        # Extract metadata or use defaults
        if order_metadata_extracted is None:
            order_metadata_extracted = {}
        
        for line in matched_lines:
            # Include ALL lines (no deduplication check)
            clean_lines.append({
                'serial_no': serial_no,  # Regenerated (no gaps)
                'brand': line.get('brand', ''),  # NEW: Include brand
                'part_name': line['part_name'],
                'part_number': line.get('matched_part_number', 'N/A'),
                'matched_part_name': line.get('matched_part_name', ''),
                'model': line.get('model', ''),
                'color': line.get('color', ''),
                'quantity': line['quantity'],
                'rate': line['rate'],
                'line_total': line['line_total'],
                'match_confidence': line.get('match_confidence', 0.0)
            })
            serial_no += 1
        
        # Calculate totals
        subtotal = sum(item['line_total'] for item in clean_lines)
        total_qty = sum(item['quantity'] for item in clean_lines)
        unmatched = sum(1 for item in clean_lines if item['part_number'] == 'N/A')
        
        # Extract customer info from metadata (if available)
        customer_name = order_metadata_extracted.get('customer_name') or order_session_data.get('username', 'N/A')
        mobile_number = order_metadata_extracted.get('mobile_number', '')
        
        # Use extracted date if available, otherwise session date
        order_date_str = order_metadata_extracted.get('order_date')
        if not order_date_str:
            order_date_str = order_session_data['created_at'].strftime('%d/%m/%Y')
        
        return {
            'order_id': order_session_data['order_id'],
            'order_date': order_date_str,
            'customer_name': customer_name,
            'mobile_number': mobile_number,  # NEW
            'location': order_metadata_extracted.get('location', ''),  # NEW
            'line_items': clean_lines,
            'subtotal': subtotal,
            'total_items': len(clean_lines),
            'total_quantity': total_qty,
            'unmatched_count': unmatched
        }
    
    async def _track_order_complete_async(
        self,
        order_session,
        clean_invoice: Dict,
        pdf_path: str = None
    ):
        """
        Background task - tracks order completion AFTER user gets PDF.
        Runs asynchronously so it never impacts the upload process.
        
        Args:
            order_session: OrderSession object
            clean_invoice: Clean invoice dictionary
            pdf_path: Path to generated PDF (optional)
        """
        try:
            from utils.usage_tracker import get_usage_tracker
            tracker = get_usage_tracker()
            
            # Calculate processing time
            processing_time = 0.0
            if order_session.submitted_at and order_session.completed_at:
                processing_time = (order_session.completed_at - order_session.submitted_at).total_seconds()
            
            # Get PDF size
            pdf_size = 0
            if pdf_path and os.path.exists(pdf_path):
                pdf_size = os.path.getsize(pdf_path)
            
            # Determine status
            status = order_session.status.value if hasattr(order_session.status, 'value') else str(order_session.status)
            
            tracker.record_order_usage(
                order_id=clean_invoice.get('order_id', order_session.order_id),
                customer_id=config.DEFAULT_CUSTOMER_ID,
                telegram_user_id=order_session.user_id,
                telegram_username=order_session.username or "unknown",
                page_count=len(order_session.pages),
                total_items=clean_invoice.get('total_items', 0),
                total_quantity=clean_invoice.get('total_quantity', 0),
                matched_count=clean_invoice.get('total_items', 0) - clean_invoice.get('unmatched_count', 0),
                unmatched_count=clean_invoice.get('unmatched_count', 0),
                subtotal=clean_invoice.get('subtotal', 0.0),
                processing_time_seconds=processing_time,
                status=status,
                customer_name=clean_invoice.get('customer_name', ''),
                pdf_size_bytes=pdf_size
            )
            
            print(f"[BACKGROUND] Order usage tracked for {clean_invoice.get('order_id', 'unknown')}")
            
        except Exception as e:
            # Silent fail - user already has their PDF
            print(f"[BACKGROUND] Order tracking failed (user unaffected): {e}")
    
    async def send_order_output_to_user(self, update, clean_invoice: Dict, output_path: str, output_format: str = 'pdf'):
        """
        Send completed order output (PDF or CSV) to Telegram user
        
        Args:
            update: Telegram update object
            clean_invoice: Clean invoice dictionary
            output_path: Path to generated file
            output_format: 'pdf' or 'csv'
        """
        format_label = output_format.upper()
        format_emoji = "📄" if output_format == 'pdf' else "📊"
        
        summary_message = f"""
✅ Order Processed Successfully!

📄 Order ID: {clean_invoice['order_id']}
📅 Date: {clean_invoice['order_date']}

📦 Summary:
• Total Items: {clean_invoice['total_items']}
• Total Quantity: {clean_invoice['total_quantity']}
• Subtotal: ₹{clean_invoice['subtotal']:.2f}
"""
        
        if clean_invoice['unmatched_count'] > 0:
            summary_message += f"\n⚠️ Unmatched Items: {clean_invoice['unmatched_count']}\n"
            summary_message += "(Items with no price - please review)\n"
        
        summary_message += f"\n📥 Downloading {format_label}..."
        
        message = update.effective_message
        await message.reply_text(summary_message)
        
        # Send file
        try:
            ext = output_format
            filename = f"{clean_invoice['order_id']}.{ext}"
            
            with open(output_path, 'rb') as output_file:
                await message.reply_document(
                    document=output_file,
                    filename=filename,
                    caption=f"{format_emoji} Your clean order invoice ({format_label})"
                )
            print(f"[ORCHESTRATOR] {format_label} sent to user")
        except Exception as e:
            print(f"[ERROR] Failed to send {format_label}: {e}")
            await message.reply_text(
                f"⚠️ Couldn't send {format_label} file.\n"
                f"File saved at: {output_path}"
            )
