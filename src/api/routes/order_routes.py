"""
Order routes - create session, add pages, submit for processing, get result, download PDF.
Gated behind FEATURE_ORDER_UPLOAD_NORMALIZATION feature flag.
Calls the existing order_normalization services directly (not the Telegram-coupled orchestrator).
"""
import os
import uuid
import time
import tempfile
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.auth.dependencies import get_current_user, get_user_db

router = APIRouter()

# ── Pydantic models ──────────────────────────────────────────────

class OrderCreateResponse(BaseModel):
    """Response when creating a new order session."""
    order_id: str
    status: str
    message: str


class OrderPageResponse(BaseModel):
    """Response when adding pages to an order."""
    order_id: str
    page_count: int
    message: str


class OrderSubmitResponse(BaseModel):
    """Response after processing an order."""
    order_id: str
    status: str
    customer_name: Optional[str] = None
    order_date: Optional[str] = None
    total_items: int = 0
    total_quantity: int = 0
    subtotal: float = 0.0
    unmatched_count: int = 0
    line_items: List[Dict[str, Any]] = []
    pdf_available: bool = False
    processing_time_seconds: float = 0.0


class OrderStatusResponse(BaseModel):
    """Response for order status check."""
    order_id: str
    status: str
    page_count: int = 0
    result: Optional[Dict[str, Any]] = None


# ── In-memory order session store ─────────────────────────────────

_order_sessions: Dict[str, Dict[str, Any]] = {}


def _check_feature_flag():
    """Ensure order upload feature is enabled."""
    import config
    if not config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Order upload feature is not enabled",
        )


# ── Routes ────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=OrderCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order session",
)
async def create_order(
    user: dict = Depends(get_current_user),
):
    """
    Start a new order upload session.
    
    After creating, add page images with POST /orders/{order_id}/pages,
    then submit with POST /orders/{order_id}/submit.
    """
    _check_feature_flag()

    order_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix="gst_api_order_")

    _order_sessions[order_id] = {
        "user_id": user["id"],
        "user_email": user["email"],
        "status": "uploading",
        "pages": [],
        "temp_dir": temp_dir,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
        "pdf_path": None,
    }

    return OrderCreateResponse(
        order_id=order_id,
        status="uploading",
        message="Order session created. Add page images next.",
    )


@router.post(
    "/{order_id}/pages",
    response_model=OrderPageResponse,
    summary="Add page images to an order",
)
async def add_order_pages(
    order_id: str,
    files: List[UploadFile] = File(..., description="Order page images"),
    user: dict = Depends(get_current_user),
):
    """
    Upload one or more page images for a handwritten order.
    
    Can be called multiple times to add pages incrementally.
    """
    _check_feature_flag()
    import config

    session = _order_sessions.get(order_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if session["status"] != "uploading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add pages to order in status: {session['status']}",
        )

    total_pages = len(session["pages"]) + len(files)
    if total_pages > config.MAX_IMAGES_PER_ORDER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {config.MAX_IMAGES_PER_ORDER} pages per order",
        )

    allowed_extensions = {'.jpg', '.jpeg', '.png', '.pdf'}
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {ext}",
            )

        safe_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(session["temp_dir"], safe_name)
        content = await f.read()
        with open(file_path, "wb") as out:
            out.write(content)
        session["pages"].append(file_path)

    return OrderPageResponse(
        order_id=order_id,
        page_count=len(session["pages"]),
        message=f"{len(files)} page(s) added. Total: {len(session['pages'])}",
    )


@router.post(
    "/{order_id}/submit",
    response_model=OrderSubmitResponse,
    summary="Process an order through the full pipeline",
)
async def submit_order(
    order_id: str,
    output_format: str = Query("pdf", description="Output format: pdf or csv"),
    user: dict = Depends(get_current_user),
):
    """
    Submit an order for processing. Runs the full pipeline:
    
    1. Extract order data from images (OCR + LLM)
    2. Normalize part names and colors
    3. Match prices from pricing sheet
    4. Compute totals
    5. Generate PDF/CSV output
    6. Save to Google Sheets
    
    Returns the processed order data. Use GET /orders/{order_id}/pdf to download.
    """
    _check_feature_flag()

    session = _order_sessions.get(order_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if session["status"] != "uploading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is already in status: {session['status']}",
        )

    if not session["pages"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pages uploaded. Add images first.",
        )

    session["status"] = "processing"
    start_time = time.time()

    try:
        import config
        from order_normalization.extractor import OrderExtractor
        from order_normalization.normalizer import OrderNormalizer
        from order_normalization.pricing_matcher import PricingMatcher
        from order_normalization.pdf_generator import OrderPDFGenerator
        from order_normalization.sheets_handler import OrderSheetsHandler

        # ── Step 1: Extract order data from images (OCR + LLM) ──
        extractor = OrderExtractor()

        # Convert flat file-path list into the format extract_all_pages expects
        pages_for_extractor = [
            {"image_path": path, "page_number": idx + 1}
            for idx, path in enumerate(session["pages"])
        ]
        extracted_pages = extractor.extract_all_pages(pages_for_extractor)

        # Validate extraction produced line items
        total_lines = sum(len(p.get("lines_raw", [])) for p in extracted_pages)
        if total_lines == 0:
            session["status"] = "failed"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not extract any items from the uploaded images",
            )

        # Grab order metadata from the first page (customer name, date, etc.)
        order_metadata = {}
        if extracted_pages and "order_metadata" in extracted_pages[0]:
            order_metadata = extracted_pages[0]["order_metadata"]

        # ── Step 2: Normalize part names and colors ──
        normalizer = OrderNormalizer()
        normalized_lines = normalizer.normalize_all_lines(extracted_pages)

        # ── Step 3: Deduplicate (disabled per user request, same as orchestrator) ──
        unique_lines = normalized_lines

        # ── Step 4: Match prices from pricing sheet ──
        matcher = PricingMatcher()
        try:
            matched_lines = matcher.match_all_lines(unique_lines)
        except Exception:
            # Pricing failure is non-critical – continue with zero prices
            matched_lines = unique_lines
            for line in matched_lines:
                line["matched"] = False
                line["unit_price"] = 0.0

        # ── Step 5: Compute line totals (mirrors orchestrator.compute_line_totals) ──
        PRICE_CONFIDENCE_THRESHOLD = 0.80
        for line in matched_lines:
            line["quantity"] = int(line.get("quantity") or 0)
            match_confidence = float(line.get("match_confidence") or 0.0)
            if match_confidence >= PRICE_CONFIDENCE_THRESHOLD:
                line["rate"] = float(line.get("unit_price") or 0.0)
            else:
                line["rate"] = 0.0
            line["line_total"] = line["quantity"] * line["rate"]

        # ── Step 6: Build clean invoice model (mirrors orchestrator.build_clean_invoice) ──
        clean_lines = []
        serial_no = 1
        for line in matched_lines:
            clean_lines.append({
                "serial_no": serial_no,
                "brand": line.get("brand", ""),
                "part_name": line["part_name"],
                "part_number": line.get("matched_part_number", "N/A"),
                "matched_part_name": line.get("matched_part_name", ""),
                "model": line.get("model", ""),
                "color": line.get("color", ""),
                "quantity": line["quantity"],
                "rate": line["rate"],
                "line_total": line["line_total"],
                "match_confidence": line.get("match_confidence", 0.0),
            })
            serial_no += 1

        subtotal = sum(item["line_total"] for item in clean_lines)
        total_quantity = sum(item["quantity"] for item in clean_lines)
        unmatched = sum(1 for item in clean_lines if item["part_number"] == "N/A")

        customer_name = order_metadata.get("customer_name") or user.get("full_name", "N/A")
        order_date_str = order_metadata.get("order_date") or datetime.now().strftime("%d/%m/%Y")

        clean_invoice = {
            "order_id": order_id[:8].upper(),
            "order_date": order_date_str,
            "customer_name": customer_name,
            "mobile_number": order_metadata.get("mobile_number", ""),
            "location": order_metadata.get("location", ""),
            "line_items": clean_lines,
            "subtotal": subtotal,
            "total_items": len(clean_lines),
            "total_quantity": total_quantity,
            "unmatched_count": unmatched,
        }

        # ── Step 7: Generate PDF or CSV output ──
        pdf_path = None
        try:
            pdf_gen = OrderPDFGenerator()
            if output_format.lower() == "csv":
                pdf_path = pdf_gen.generate_csv(clean_invoice)
            else:
                pdf_path = pdf_gen.generate_pdf(clean_invoice)
            session["pdf_path"] = pdf_path
        except Exception:
            pass  # Output generation is non-critical

        # ── Step 8: Save to Google Sheets (tenant-aware) ──
        try:
            from api.helpers import _resolve_tenant_sheet_id
            tenant_sheet_id = None
            if config.FEATURE_TENANT_SHEET_ISOLATION:
                tenant_sheet_id = _resolve_tenant_sheet_id(user)
            sheets_handler = OrderSheetsHandler(sheet_id=tenant_sheet_id)
            session_metadata = {
                "page_count": len(session["pages"]),
                "created_by": user["email"],
            }
            sheets_handler.append_order_summary(clean_invoice, session_metadata)
            sheets_handler.append_order_line_items(clean_invoice)
            sheets_handler.update_customer_details(
                clean_invoice.get("customer_name", "N/A"),
                clean_invoice["order_date"],
            )
        except Exception:
            pass  # Sheets save is non-critical for API response

        processing_time = round(time.time() - start_time, 2)

        # Update session
        session["status"] = "completed"
        session["result"] = {
            "customer_name": clean_invoice["customer_name"],
            "order_date": clean_invoice["order_date"],
            "line_items": clean_lines,
            "total_items": clean_invoice["total_items"],
            "total_quantity": clean_invoice["total_quantity"],
            "subtotal": clean_invoice["subtotal"],
            "unmatched_count": clean_invoice["unmatched_count"],
        }

        # Increment user's order count
        user_db = get_user_db()
        user_db.increment_order_count(user["id"])

        # ── Usage tracking (non-blocking) ──
        if config.ENABLE_USAGE_TRACKING and config.ENABLE_ORDER_TRACKING:
            try:
                from utils.usage_tracker import get_usage_tracker
                tracker = get_usage_tracker()
                tracker.record_order_usage(
                    order_id=clean_invoice["order_id"],
                    customer_id=config.DEFAULT_CUSTOMER_ID,
                    telegram_user_id=0,
                    telegram_username=user["email"],
                    page_count=len(session["pages"]),
                    total_items=clean_invoice["total_items"],
                    total_quantity=clean_invoice["total_quantity"],
                    matched_count=clean_invoice["total_items"] - clean_invoice["unmatched_count"],
                    unmatched_count=clean_invoice["unmatched_count"],
                    subtotal=clean_invoice["subtotal"],
                    processing_time_seconds=processing_time,
                    status="completed",
                    customer_name=clean_invoice.get("customer_name", ""),
                    pdf_size_bytes=os.path.getsize(pdf_path) if pdf_path and os.path.exists(pdf_path) else 0,
                )
            except Exception:
                pass  # Usage tracking is non-critical

        return OrderSubmitResponse(
            order_id=order_id,
            status="completed",
            customer_name=clean_invoice["customer_name"],
            order_date=clean_invoice["order_date"],
            total_items=clean_invoice["total_items"],
            total_quantity=clean_invoice["total_quantity"],
            subtotal=clean_invoice["subtotal"],
            unmatched_count=clean_invoice["unmatched_count"],
            line_items=clean_lines,
            pdf_available=pdf_path is not None,
            processing_time_seconds=processing_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        session["status"] = "failed"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Order processing failed: {str(e)}",
        )


@router.get(
    "/{order_id}",
    response_model=OrderStatusResponse,
    summary="Get order status and result",
)
async def get_order(
    order_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the status and result of an order."""
    _check_feature_flag()

    session = _order_sessions.get(order_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return OrderStatusResponse(
        order_id=order_id,
        status=session["status"],
        page_count=len(session["pages"]),
        result=session.get("result"),
    )


@router.get(
    "/{order_id}/download",
    summary="Download the generated order output (PDF or CSV)",
)
async def download_order_output(
    order_id: str,
    user: dict = Depends(get_current_user),
):
    """Download the generated output file for a completed order (PDF or CSV)."""
    _check_feature_flag()

    session = _order_sessions.get(order_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if session["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is not yet completed",
        )

    file_path = session.get("pdf_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file not available for this order",
        )

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        media_type = "text/csv"
        filename = f"order_{order_id[:8]}.csv"
    else:
        media_type = "application/pdf"
        filename = f"order_{order_id[:8]}.pdf"

    return FileResponse(path=file_path, media_type=media_type, filename=filename)


# Keep legacy /pdf endpoint for backwards compatibility
@router.get(
    "/{order_id}/pdf",
    summary="Download the generated order PDF (legacy)",
    include_in_schema=False,
)
async def download_order_pdf(
    order_id: str,
    user: dict = Depends(get_current_user),
):
    """Legacy endpoint - redirects to /download."""
    return await download_order_output(order_id, user)


# ── Session cleanup ────────────────────────────────────────────────

@router.delete(
    "/{order_id}",
    summary="Delete an order session and clean up temp files",
)
async def delete_order(
    order_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Delete an order session and its temporary files.

    Can be called after downloading the output, or to cancel an upload.
    """
    _check_feature_flag()

    session = _order_sessions.get(order_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # Clean up temp directory
    temp_dir = session.get("temp_dir")
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

    del _order_sessions[order_id]

    return {"message": "Order session deleted", "order_id": order_id}
