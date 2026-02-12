"""
Health check and metrics routes - public, no authentication required.
"""
import sys
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()


@router.get(
    "",
    summary="System health check",
)
async def health_check():
    """
    Check system health status.
    
    Returns status of connected services (Sheets, Gemini, etc.).
    No authentication required.
    """
    health = {
        "status": "healthy",
        "service": "GST Scanner API",
        "version": "1.0.0",
        "components": {}
    }

    # Check if core services are importable
    try:
        import config
        health["components"]["config"] = "ok"
    except Exception as e:
        health["components"]["config"] = f"error: {str(e)}"
        health["status"] = "degraded"

    # Check Google Sheets connectivity
    try:
        from sheets.sheets_manager import SheetsManager
        health["components"]["sheets"] = "available"
    except Exception:
        health["components"]["sheets"] = "unavailable"

    # Check OCR engine
    try:
        from ocr.ocr_engine import OCREngine
        health["components"]["ocr"] = "available"
    except Exception:
        health["components"]["ocr"] = "unavailable"

    # Check parser
    try:
        from parsing.gst_parser import GSTParser
        health["components"]["parser"] = "available"
    except Exception:
        health["components"]["parser"] = "unavailable"

    return health


@router.get(
    "/metrics",
    summary="System metrics",
)
async def get_metrics():
    """
    Get system performance metrics.
    
    No authentication required.
    """
    try:
        from utils.metrics_tracker import get_metrics_tracker
        metrics = get_metrics_tracker()
        return metrics.get_metrics()
    except Exception as e:
        return {
            "error": f"Metrics unavailable: {str(e)}",
            "status": "unavailable",
        }
