"""
Invoice routes - upload, OCR, parse, list, detail, confirm, correct.
These call the existing OCREngine, GSTParser, and SheetsManager services.
"""
import os
import time
import uuid
import tempfile
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query
from pydantic import BaseModel, Field

from api.auth.dependencies import get_current_user, get_user_db

router = APIRouter()

# ── Pydantic models for request/response ──────────────────────────

class InvoiceUploadResponse(BaseModel):
    """Response from invoice upload + OCR + parsing."""
    session_id: str
    invoice_data: Dict[str, Any]
    line_items: List[Dict[str, Any]]
    validation_result: Dict[str, Any]
    confidence_scores: Optional[Dict[str, float]] = None
    ocr_text: str
    page_count: int
    processing_time_seconds: float


class InvoiceConfirmRequest(BaseModel):
    """Request to confirm and save an invoice to Google Sheets."""
    session_id: str
    invoice_data: Dict[str, Any]
    line_items: List[Dict[str, Any]]
    validation_result: Dict[str, Any]
    confidence_scores: Optional[Dict[str, float]] = None


class CorrectionRequest(BaseModel):
    """Request to apply corrections to extracted invoice data."""
    corrections: Dict[str, str] = Field(
        ...,
        description="Map of field_name -> corrected_value",
        examples=[{"Invoice_No": "INV-2025-001", "Invoice_Date": "2025-01-15"}],
    )


class InvoiceListResponse(BaseModel):
    """Response for invoice listing."""
    invoices: List[Dict[str, Any]]
    total: int
    month: int
    year: int


# ── In-memory session store for pending invoices ──────────────────

_invoice_sessions: Dict[str, Dict[str, Any]] = {}


# ── Routes ────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=InvoiceUploadResponse,
    summary="Upload invoice image(s) for OCR and parsing",
)
async def upload_invoice(
    files: List[UploadFile] = File(..., description="Invoice image files (jpg, png, pdf)"),
    user: dict = Depends(get_current_user),
):
    """
    Upload one or more invoice images. The system will:
    
    1. Run OCR (Google Gemini Vision) on each image
    2. Parse the extracted text into structured GST fields
    3. Validate the parsed data
    4. Return the extracted data for review
    
    After reviewing, call `/invoices/confirm` to save to Google Sheets,
    or `/invoices/correct` to fix fields first.
    """
    import config
    from ocr.ocr_engine import OCREngine
    from parsing.gst_parser import GSTParser

    # Validate file types
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.pdf'}
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}",
            )

    if len(files) > config.MAX_IMAGES_PER_INVOICE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {config.MAX_IMAGES_PER_INVOICE} images per invoice",
        )

    # Save uploaded files to temp directory
    temp_dir = tempfile.mkdtemp(prefix="gst_api_invoice_")
    saved_paths = []
    try:
        for f in files:
            safe_name = f"{uuid.uuid4().hex}{os.path.splitext(f.filename or '.jpg')[1]}"
            file_path = os.path.join(temp_dir, safe_name)
            content = await f.read()
            with open(file_path, "wb") as out:
                out.write(content)
            saved_paths.append(file_path)

        start_time = time.time()

        # OCR
        ocr_engine = OCREngine()
        if len(saved_paths) == 1:
            ocr_result = ocr_engine.extract_text_from_image(saved_paths[0])
        else:
            ocr_result = ocr_engine.extract_text_from_images(saved_paths)

        ocr_text = ocr_result.get("text", "")
        if not ocr_text.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="OCR could not extract any text from the uploaded image(s)",
            )

        # Parse
        parser = GSTParser()
        parse_result = parser.parse_invoice_with_validation(ocr_text)

        processing_time = round(time.time() - start_time, 2)

        # Confidence scoring (if enabled)
        confidence_scores = None
        if config.ENABLE_CONFIDENCE_SCORING:
            try:
                from features.confidence_scorer import ConfidenceScorer
                scorer = ConfidenceScorer()
                confidence_scores = scorer.score_invoice(
                    parse_result["invoice_data"],
                    parse_result.get("validation_result", {}),
                )
            except Exception:
                pass  # Non-critical

        # Create session for later confirmation
        session_id = str(uuid.uuid4())
        _invoice_sessions[session_id] = {
            "user_id": user["id"],
            "user_email": user["email"],
            "invoice_data": parse_result["invoice_data"],
            "line_items": parse_result.get("line_items", []),
            "validation_result": parse_result.get("validation_result", {}),
            "confidence_scores": confidence_scores,
            "ocr_text": ocr_text,
            "page_count": len(saved_paths),
            "processing_time": processing_time,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return InvoiceUploadResponse(
            session_id=session_id,
            invoice_data=parse_result["invoice_data"],
            line_items=parse_result.get("line_items", []),
            validation_result=parse_result.get("validation_result", {}),
            confidence_scores=confidence_scores,
            ocr_text=ocr_text,
            page_count=len(saved_paths),
            processing_time_seconds=processing_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invoice processing failed: {str(e)}",
        )
    finally:
        # Cleanup temp files
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post(
    "/{session_id}/correct",
    response_model=InvoiceUploadResponse,
    summary="Apply corrections to extracted invoice data",
)
async def correct_invoice(
    session_id: str,
    body: CorrectionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Apply field corrections to a pending invoice session.
    
    Returns the updated invoice data after corrections.
    """
    from features.correction_manager import CorrectionManager

    session = _invoice_sessions.get(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice session not found",
        )

    correction_mgr = CorrectionManager()
    corrected_data = correction_mgr.apply_corrections(
        session["invoice_data"],
        body.corrections,
    )

    # Update session
    session["invoice_data"] = corrected_data
    session["corrections"] = body.corrections

    return InvoiceUploadResponse(
        session_id=session_id,
        invoice_data=corrected_data,
        line_items=session["line_items"],
        validation_result=session["validation_result"],
        confidence_scores=session.get("confidence_scores"),
        ocr_text=session["ocr_text"],
        page_count=session["page_count"],
        processing_time_seconds=session["processing_time"],
    )


@router.post(
    "/{session_id}/confirm",
    summary="Confirm and save invoice to Google Sheets",
)
async def confirm_invoice(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Confirm a pending invoice and save it to Google Sheets.
    
    This writes the invoice header + line items to the configured Google Sheet.
    """
    from parsing.gst_parser import GSTParser
    from api.helpers import get_tenant_sheets_manager

    session = _invoice_sessions.get(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice session not found",
        )

    try:
        import config
        sheets = get_tenant_sheets_manager(user)
        parser = GSTParser()

        # Format invoice data for sheets
        invoice_data = session["invoice_data"]
        invoice_row = parser.format_for_sheets(invoice_data)

        # ── Deduplication check (mirrors Telegram bot) ──
        fingerprint = ""
        duplicate_status = "UNIQUE"
        if config.ENABLE_DEDUPLICATION:
            try:
                from features.dedup_manager import DeduplicationManager
                dedup = DeduplicationManager()
                fingerprint = dedup.generate_fingerprint(invoice_data)
                is_dup, existing = sheets.check_duplicate_advanced(fingerprint)
                if is_dup:
                    duplicate_status = "DUPLICATE"
                    return {
                        "message": "Duplicate invoice detected",
                        "invoice_no": invoice_data.get("Invoice_No", "unknown"),
                        "duplicate": True,
                        "existing_invoice": existing,
                        "session_id": session_id,
                    }
            except Exception as dedup_err:
                print(f"[API] Dedup check non-critical error: {dedup_err}")

        # Build line items rows
        line_items_rows = []
        for item in session.get("line_items", []):
            row = [item.get(col, "") for col in [
                "Invoice_No", "Line_No", "Item_Code", "Item_Description",
                "HSN", "Qty", "UOM", "Rate", "Discount_Percent",
                "Taxable_Value", "GST_Rate", "CGST_Rate", "CGST_Amount",
                "SGST_Rate", "SGST_Amount", "IGST_Rate", "IGST_Amount",
                "Cess_Amount", "Line_Total",
            ]]
            line_items_rows.append(row)

        # Build audit data
        audit_data = {
            "Upload_Timestamp": session.get("created_at", datetime.now(timezone.utc).isoformat()),
            "Telegram_User_ID": f"api_{user['id'][:8]}",
            "Telegram_Username": user["email"],
            "Extraction_Version": "v1.0-api",
            "Model_Version": "gemini-2.5-flash",
            "Processing_Time_Seconds": session.get("processing_time", 0),
            "Page_Count": session.get("page_count", 1),
            "Has_Corrections": "Yes" if session.get("corrections") else "No",
        }

        # Save to sheets
        success = sheets.append_invoice_with_audit(
            invoice_data=invoice_row,
            line_items_data=line_items_rows,
            validation_result=session.get("validation_result", {}),
            audit_data=audit_data,
            confidence_scores=session.get("confidence_scores"),
            fingerprint=fingerprint,
            duplicate_status=duplicate_status,
        )

        if success:
            # ── Master data updates (mirrors Telegram bot) ──
            try:
                _update_customer_master(sheets, invoice_data)
            except Exception:
                pass  # Non-critical

            try:
                _update_seller_master(sheets, invoice_data)
            except Exception:
                pass  # Non-critical

            try:
                _update_hsn_master(sheets, session.get("line_items", []))
            except Exception:
                pass  # Non-critical

            # Increment user's invoice count
            user_db = get_user_db()
            user_db.increment_invoice_count(user["id"])

            # ── Usage tracking (non-blocking) ──
            if config.ENABLE_USAGE_TRACKING and config.ENABLE_INVOICE_LEVEL_TRACKING:
                try:
                    from utils.usage_tracker import get_usage_tracker
                    tracker = get_usage_tracker()
                    tracker.record_invoice_usage(
                        invoice_id=invoice_data.get("Invoice_No", session_id[:8]),
                        customer_id=config.DEFAULT_CUSTOMER_ID,
                        telegram_user_id=0,
                        telegram_username=user["email"],
                        page_count=session.get("page_count", 1),
                        total_ocr_calls=session.get("page_count", 1),
                        total_parsing_calls=1,
                        ocr_tokens={"prompt": 0, "output": 0},
                        parsing_tokens={"prompt": 0, "output": 0},
                        processing_time_seconds=session.get("processing_time", 0),
                        ocr_time_seconds=0,
                        parsing_time_seconds=0,
                        sheets_time_seconds=0,
                        validation_status=session.get("validation_result", {}).get("status", "OK"),
                        confidence_avg=0.0,
                        had_corrections=bool(session.get("corrections")),
                        ocr_call_ids=[],
                    )
                except Exception:
                    pass  # Usage tracking is non-critical

            # Clean up session
            del _invoice_sessions[session_id]

            return {
                "message": "Invoice saved successfully",
                "invoice_no": invoice_data.get("Invoice_No", "unknown"),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save invoice to Google Sheets",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save invoice: {str(e)}",
        )


@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="List invoices for a given period",
)
async def list_invoices(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    status_filter: Optional[str] = Query(
        None, description="Comma-separated validation statuses (e.g. OK,WARNING)"
    ),
    user: dict = Depends(get_current_user),
):
    """
    List invoices from Google Sheets for a given month and year.
    
    Optionally filter by validation status.
    """
    from api.helpers import get_tenant_sheets_manager

    try:
        sheets = get_tenant_sheets_manager(user)
        filters = status_filter.split(",") if status_filter else None
        invoices = sheets.get_invoices_by_period(month, year, status_filter=filters)

        return InvoiceListResponse(
            invoices=invoices,
            total=len(invoices),
            month=month,
            year=year,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch invoices: {str(e)}",
        )


@router.get(
    "/{invoice_no}",
    summary="Get invoice detail with line items",
)
async def get_invoice(
    invoice_no: str,
    user: dict = Depends(get_current_user),
):
    """
    Get detailed invoice data including line items.
    """
    from api.helpers import get_tenant_sheets_manager

    try:
        sheets = get_tenant_sheets_manager(user)
        line_items_map = sheets.get_line_items_by_invoice_numbers([invoice_no])
        line_items = line_items_map.get(invoice_no, [])

        return {
            "invoice_no": invoice_no,
            "line_items": line_items,
            "line_item_count": len(line_items),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch invoice: {str(e)}",
        )


# ── Batch processing ──────────────────────────────────────────────

@router.post(
    "/batch",
    summary="Process a batch of invoices",
)
async def batch_process_invoices(
    files: List[UploadFile] = File(
        ...,
        description=(
            "Invoice image files. Multiple images for the same invoice "
            "should share the same filename prefix (e.g. inv1_page1.jpg, "
            "inv1_page2.jpg). Each unique prefix is treated as one invoice."
        ),
    ),
    user: dict = Depends(get_current_user),
):
    """
    Upload and process multiple invoices at once.

    Each uploaded file is treated as a separate single-page invoice.
    If you need multi-page invoices in a batch, use the regular
    upload/confirm flow per invoice.

    Returns a batch processing report with per-invoice results.
    """
    import config
    from ocr.ocr_engine import OCREngine
    from parsing.gst_parser import GSTParser
    from api.helpers import get_tenant_sheets_manager

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch")

    temp_dir = tempfile.mkdtemp(prefix="gst_api_batch_")
    try:
        # Save all files to temp dir
        saved: List[List[str]] = []
        for f in files:
            ext = os.path.splitext(f.filename or ".jpg")[1].lower()
            safe_name = f"{uuid.uuid4().hex}{ext}"
            path = os.path.join(temp_dir, safe_name)
            content = await f.read()
            with open(path, "wb") as out:
                out.write(content)
            # Each file = one invoice (single page)
            saved.append([path])

        sheets = get_tenant_sheets_manager(user)
        ocr_engine = OCREngine()
        parser = GSTParser()

        from utils.batch_processor import BatchProcessor
        processor = BatchProcessor(
            ocr_engine=ocr_engine,
            gst_parser=parser,
            validator=parser.gst_validator,
            sheets_manager=sheets,
        )

        result = processor.process_batch(
            batch_invoices=saved,
            progress_callback=None,
            audit_logger=None,
            user_id=f"api_{user['id'][:8]}",
            username=user["email"],
        )

        return {
            "total": result["total"],
            "successful": result["successful"],
            "failed": result["failed"],
            "success_rate": result["success_rate"],
            "results": result["results"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ── Master data update helpers (mirror telegram_bot.py logic) ──────

def _update_customer_master(sheets, invoice_data: dict):
    """Update Customer_Master with seller-buyer pair from invoice."""
    seller_gstin = (invoice_data.get("Seller_GSTIN") or "").strip()
    buyer_gstin = (invoice_data.get("Buyer_GSTIN") or "").strip()
    if len(seller_gstin) < 15 or len(buyer_gstin) < 15:
        return
    customer_data = {
        "Buyer_Name": (invoice_data.get("Buyer_Name") or "").strip(),
        "Trade_Name": (invoice_data.get("Buyer_Name") or "").strip(),
        "Buyer_State_Code": (invoice_data.get("Buyer_State_Code") or "").strip(),
        "Default_Place_Of_Supply": (invoice_data.get("Buyer_State") or "").strip(),
        "Last_Updated": "",
        "Usage_Count": 1,
    }
    sheets.update_customer_master(seller_gstin, buyer_gstin, customer_data)


def _update_seller_master(sheets, invoice_data: dict):
    """Update Seller_Master with seller information."""
    seller_gstin = (invoice_data.get("Seller_GSTIN") or "").strip()
    if len(seller_gstin) < 15:
        return
    seller_data = {
        "GSTIN": seller_gstin,
        "Legal_Name": (invoice_data.get("Seller_Name") or "").strip(),
        "Trade_Name": (invoice_data.get("Seller_Name") or "").strip(),
        "State_Code": (invoice_data.get("Seller_State_Code") or "").strip(),
        "Address": "",
        "Contact_Number": "",
        "Email": "",
        "Last_Updated": "",
        "Usage_Count": 1,
    }
    sheets.update_seller_master(seller_gstin, seller_data)


def _update_hsn_master(sheets, line_items: list):
    """Update HSN_Master with HSN codes from line items."""
    for item in line_items:
        hsn_code = (item.get("HSN") or "").strip()
        if len(hsn_code) < 4:
            continue
        hsn_data = {
            "HSN_SAC_Code": hsn_code,
            "Description": (item.get("Item_Description") or "").strip(),
            "Default_GST_Rate": (item.get("GST_Rate") or "").strip(),
            "UQC": (item.get("UOM") or "").strip(),
            "Category": "",
            "Last_Updated": "",
            "Usage_Count": 1,
        }
        sheets.update_hsn_master(hsn_code, hsn_data)
