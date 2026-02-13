"""
Phase 7 – Order Upload Orchestrator
====================================

This module orchestrates the full order upload workflow:
1. OCR: Extract text from images
2. Parse: Convert to structured lines
3. Dedupe: Remove duplicates
4. Match: Find prices from price list
5. Write: Append to Google Sheets

Guardrails:
- Only active when config.ENABLE_ORDER_UPLOAD is True.
- Only callable from dev bot (BOT_ENV=dev).
- Returns user-friendly summary + Sheet link + warnings.
"""
from __future__ import annotations

from typing import List, Dict, Tuple, Optional
import os

try:
    from src import config
    from src.order_upload_ocr import OrderOcrRunner
    from src.order_upload_extraction import extract_lines_from_pages, extract_all_from_pages
    from src.order_upload_dedupe import dedupe_lines
    from src.order_upload_price_matcher import PriceListLoader, PriceListMatcher
    from src.order_upload_sheets import OrderUploadSheets
    from src.order_upload_pdf import generate_order_pdf
except ImportError:
    import config
    from order_upload_ocr import OrderOcrRunner
    from order_upload_extraction import extract_lines_from_pages, extract_all_from_pages
    from order_upload_dedupe import dedupe_lines
    from order_upload_price_matcher import PriceListLoader, PriceListMatcher
    from order_upload_sheets import OrderUploadSheets
    from order_upload_pdf import generate_order_pdf


class OrderUploadOrchestrator:
    """
    Orchestrates the full order upload workflow from images to Google Sheets.
    """

    def __init__(self):
        """Initialize the orchestrator with all required components."""
        if not config.ENABLE_ORDER_UPLOAD:
            raise RuntimeError("Order upload is disabled. Set ENABLE_ORDER_UPLOAD=true to enable.")
        
        self.ocr_runner = OrderOcrRunner()
        
        # Sheets integration is optional (graceful if credentials missing)
        self.sheets_manager = None
        try:
            self.sheets_manager = OrderUploadSheets()
        except Exception as e:
            print(f"[OrderUploadOrchestrator] Sheets not available (will skip writes): {e}")
        
        # Load price list from Google Sheets tabs (Price_List1, Price_List2,
        # Correct standard packaging) — merged with corrections taking priority.
        # Falls back to local .xlsx if Sheets are not available.
        self.price_list = []
        if self.sheets_manager:
            try:
                self.price_list = PriceListLoader.load_from_sheets(
                    self.sheets_manager.spreadsheet
                )
            except Exception as e:
                print(f"[OrderUploadOrchestrator] Failed to load from Sheets: {e}")

        if not self.price_list:
            # Fallback to local Excel file
            if config.LOCAL_PRICE_LIST_PATH and os.path.exists(config.LOCAL_PRICE_LIST_PATH):
                self.price_list = PriceListLoader.load_from_xlsx(config.LOCAL_PRICE_LIST_PATH)
                print(f"[OrderUploadOrchestrator] Loaded {len(self.price_list)} items from local .xlsx")
        
        self.price_matcher = PriceListMatcher(self.price_list)

    def process_order_images(
        self,
        image_paths: List[str],
        order_id: Optional[str] = None,
    ) -> Dict:
        """
        Process order images through the full pipeline.
        
        Args:
            image_paths: List of paths to order images
            order_id: Optional order identifier for tracking
        
        Returns:
            Dict with:
                - success: bool
                - summary: str (user-friendly message)
                - stats: Dict (counts, warnings, etc.)
                - sheet_url: Optional[str] (link to Google Sheet)
        """
        result = {
            "success": False,
            "summary": "",
            "stats": {},
            "sheet_url": None,
            "pdf_path": None,
            "errors": [],
        }

        try:
            # Step 1: OCR
            ocr_results = self.ocr_runner.ocr_images(image_paths)
            
            # Check for OCR errors
            if not ocr_results or all("[OCR ERROR:" in page.get("text", "") for page in ocr_results):
                result["errors"].append("OCR failed - check GOOGLE_API_KEY configuration")
                result["summary"] = "Failed to extract text from images. Please check API key configuration."
                return result

            # Log raw OCR to sheets (if available)
            if self.sheets_manager:
                from datetime import datetime
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for page in ocr_results:
                    self.sheets_manager.append_raw_ocr(
                        order_id=order_id or "",
                        page_no=page["page_no"],
                        raw_text=page["text"],
                        timestamp=ts,
                    )

            # Step 2: Parse into structured lines + extract customer info
            customer_info, order_lines = extract_all_from_pages(ocr_results)
            result["customer_info"] = customer_info
            
            if not order_lines:
                result["errors"].append("No order lines extracted from images")
                result["summary"] = "No valid order lines found in the images."
                return result

            # Sort all lines by S.N for consistent ordering
            order_lines = sorted(
                order_lines,
                key=lambda x: int(x.get("sn", 0) or 0),
            )

            # Step 3: Deduplicate
            kept_lines, skipped_lines = dedupe_lines(order_lines)

            # Log normalized lines (before matching)
            if self.sheets_manager:
                norm_rows = []
                for line in kept_lines:
                    norm_rows.append({
                        "S.N": line.get("sn", ""),
                        "PART NAME": line.get("part_name", ""),
                        "QTY": line.get("qty", ""),
                        "source_page": line.get("source_page", 1),
                        "confidence": "",
                    })
                self.sheets_manager.append_normalized_lines(norm_rows)

            # Step 4: Price matching (AI-powered for abbreviated OCR text)
            ocr_names = [line.get("part_name", "") for line in kept_lines]
            ai_matches = self.price_matcher.match_batch_with_ai(ocr_names)

            matched_lines = []
            unmatched_lines = []
            
            for line in kept_lines:
                part_name = line.get("part_name", "")
                part_number, price, match_type = ai_matches.get(
                    part_name, (None, None, "UNMATCHED")
                )
                
                matched_line = {
                    "sn": line.get("sn", ""),
                    "part_name": part_name,
                    "part_number": part_number or "",
                    "price": price or "",
                    "qty": line.get("qty", ""),
                    "line_total": "",
                    "match_type": match_type,
                }
                
                # Calculate line total if we have price and qty
                if price and line.get("qty"):
                    try:
                        qty_val = int(str(line["qty"]).strip())
                        matched_line["line_total"] = float(price) * qty_val
                    except (ValueError, TypeError):
                        pass
                
                if match_type == "UNMATCHED":
                    unmatched_lines.append(matched_line)
                else:
                    matched_lines.append(matched_line)

            # Compute grand total across all lines that have a line_total
            grand_total = 0.0
            for line in matched_lines + unmatched_lines:
                try:
                    grand_total += float(line["line_total"]) if line["line_total"] else 0.0
                except (ValueError, TypeError):
                    pass

            # Sort output lines by S.N before writing to sheets and generating PDF
            all_output_sorted = sorted(
                matched_lines + unmatched_lines,
                key=lambda x: int(x.get("sn", 0) or 0),
            )

            # Step 5: Write matched + unmatched lines to sheets (if available)
            if self.sheets_manager:
                sheet_rows = []
                for line in all_output_sorted:
                    sheet_rows.append({
                        "S.N": line["sn"],
                        "PART NAME": line["part_name"],
                        "PART NUMBER": line["part_number"],
                        "PRICE": line["price"],
                        "QTY": line["qty"],
                        "LINE TOTAL": line["line_total"],
                    })
                self.sheets_manager.append_matched_lines(sheet_rows, grand_total=grand_total)

                # Batch log errors for unmatched and duplicate lines
                error_rows = []
                for line in unmatched_lines:
                    error_rows.append({
                        "order_id": order_id or "",
                        "error_type": "UNMATCHED",
                        "description": f"No price found for: {line['part_name']}",
                    })
                for line in skipped_lines:
                    error_rows.append({
                        "order_id": order_id or "",
                        "error_type": "DUPLICATE",
                        "description": f"{line.get('part_name', '')}: {'; '.join(line.get('dup_reasons', []))}",
                    })
                if error_rows:
                    self.sheets_manager.append_errors_batch(error_rows)

            # Step 6: Generate PDF
            try:
                pdf_path = generate_order_pdf(
                    matched_lines=all_output_sorted,
                    grand_total=grand_total,
                    order_id=order_id,
                    customer_info=customer_info,
                )
                result["pdf_path"] = pdf_path
            except Exception as e:
                print(f"[OrderUploadOrchestrator] PDF generation failed: {e}")
                result["errors"].append(f"PDF generation failed: {str(e)}")

            # Step 7: Write order summary row to Order_Summary sheet
            if self.sheets_manager:
                from datetime import datetime
                # Build customer display name: Hindi (English) or just whichever is available
                cust_display = ""
                if customer_info.get("name"):
                    cust_display = customer_info["name"]
                    if customer_info.get("name_en"):
                        cust_display += f" ({customer_info['name_en']})"
                elif customer_info.get("name_en"):
                    cust_display = customer_info["name_en"]

                summary_row = {
                    "order_id": order_id or "",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "customer_name": cust_display,
                    "customer_phone": customer_info.get("phone", ""),
                    "order_date": customer_info.get("date", ""),
                    "total_images": str(len(image_paths)),
                    "lines_extracted": str(len(order_lines)),
                    "lines_matched": str(len(matched_lines)),
                    "lines_unmatched": str(len(unmatched_lines)),
                    "duplicates_skipped": str(len(skipped_lines)),
                    "grand_total": f"{grand_total:.2f}",
                }
                try:
                    self.sheets_manager.append_order_summary(summary_row)
                except Exception as e:
                    print(f"[OrderUploadOrchestrator] Failed to write order summary: {e}")

            # Build result
            result["success"] = True
            # Include matched lines for image rendering (sendPhoto fallback)
            result["_matched_lines"] = all_output_sorted
            result["stats"] = {
                "total_extracted": len(order_lines),
                "kept": len(kept_lines),
                "duplicates_skipped": len(skipped_lines),
                "matched": len(matched_lines),
                "unmatched": len(unmatched_lines),
                "grand_total": grand_total,
            }
            
            # Build summary message
            summary_parts = [
                f"Order processing complete!",
                f"",
            ]

            # Include customer details if available
            if customer_info.get("name") or customer_info.get("name_en"):
                name_display = customer_info.get("name", "")
                if customer_info.get("name_en"):
                    name_display += f" ({customer_info['name_en']})" if name_display else customer_info["name_en"]
                summary_parts.append(f"Customer: {name_display}")
            if customer_info.get("phone"):
                summary_parts.append(f"Phone: {customer_info['phone']}")
            if customer_info.get("date"):
                summary_parts.append(f"Order Date: {customer_info['date']}")
            if any(customer_info.get(k) for k in ("name", "name_en", "phone", "date")):
                summary_parts.append("")

            summary_parts.extend([
                f"Extracted: {len(order_lines)} lines",
                f"Kept: {len(kept_lines)} (skipped {len(skipped_lines)} duplicates)",
                f"Matched: {len(matched_lines)} items with prices",
            ])
            
            if unmatched_lines:
                summary_parts.append(f"Unmatched: {len(unmatched_lines)} items (no price found)")
            
            summary_parts.append(f"")
            summary_parts.append(f"GRAND TOTAL: {grand_total:,.2f}")
            
            result["summary"] = "\n".join(summary_parts)
            
            # Sheet URL (if configured)
            if config.ORDER_UPLOAD_SHEET_ID:
                result["sheet_url"] = f"https://docs.google.com/spreadsheets/d/{config.ORDER_UPLOAD_SHEET_ID}"

        except Exception as e:
            result["errors"].append(f"Unexpected error: {str(e)}")
            result["summary"] = f"Processing failed: {str(e)}"

        return result
