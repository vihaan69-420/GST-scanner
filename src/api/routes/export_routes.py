"""
Export routes - GSTR-1, GSTR-3B reports, operational reports.
Uses the exports module with a properly initialized SheetsManager.
"""
import os
import tempfile
import shutil
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import FileResponse, JSONResponse

from api.auth.dependencies import get_current_user

router = APIRouter()


def _get_sheets_manager(user: dict = None, sheet_id: str = None):
    """Get a SheetsManager, optionally tenant-aware."""
    if user:
        from api.helpers import get_tenant_sheets_manager
        return get_tenant_sheets_manager(user, sheet_id_override=sheet_id)
    from sheets.sheets_manager import SheetsManager
    return SheetsManager(sheet_id=sheet_id)


# ═══════════════════════════════════════════════════════════════════
# GSTR-1 Exports
# ═══════════════════════════════════════════════════════════════════

@router.get(
    "/gstr1",
    summary="Generate GSTR-1 export data (JSON)",
)
async def export_gstr1(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    export_type: str = Query(
        "all", description="Export type: b2b, b2c, hsn, or all"
    ),
    user: dict = Depends(get_current_user),
):
    """
    Generate GSTR-1 export data for the specified period.

    Returns JSON summary. Use `/exports/gstr1/download` for CSV files.
    """
    try:
        from exports.gstr1_exporter import GSTR1Exporter

        sheets = _get_sheets_manager(user)
        exporter = GSTR1Exporter(sheets)

        if export_type == "b2b":
            result = exporter.export_b2b(month, year)
            return {"period": f"{month:02d}/{year}", "b2b": result}
        elif export_type == "b2c":
            result = exporter.export_b2c_small(month, year)
            return {"period": f"{month:02d}/{year}", "b2c": result}
        elif export_type == "hsn":
            result = exporter.export_hsn_summary(month, year)
            return {"period": f"{month:02d}/{year}", "hsn": result}
        else:
            b2b = exporter.export_b2b(month, year)
            b2c = exporter.export_b2c_small(month, year)
            hsn = exporter.export_hsn_summary(month, year)
            return {
                "period": f"{month:02d}/{year}",
                "b2b": b2b,
                "b2c": b2c,
                "hsn": hsn,
            }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GSTR-1 export module is not available",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GSTR-1 export failed: {str(e)}",
        )


@router.get(
    "/gstr1/download",
    summary="Download GSTR-1 CSV files",
)
async def download_gstr1(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    export_type: str = Query(
        "all", description="Export type: b2b, b2c, hsn, or all"
    ),
    user: dict = Depends(get_current_user),
):
    """
    Download GSTR-1 export as CSV file(s).

    For 'all' type, returns a summary report text file. Individual
    CSV files can be fetched with b2b, b2c, or hsn type.
    """
    try:
        from exports.gstr1_exporter import GSTR1Exporter

        sheets = _get_sheets_manager(user)
        exporter = GSTR1Exporter(sheets)
        period_str = f"{year}_{month:02d}"
        temp_dir = tempfile.mkdtemp(prefix="gstr1_export_")

        try:
            if export_type == "b2b":
                path = os.path.join(temp_dir, f"B2B_Invoices_{period_str}.csv")
                result = exporter.export_b2b(month, year, path)
            elif export_type == "b2c":
                path = os.path.join(temp_dir, f"B2C_Small_{period_str}.csv")
                result = exporter.export_b2c_small(month, year, path)
            elif export_type == "hsn":
                path = os.path.join(temp_dir, f"HSN_Summary_{period_str}.csv")
                result = exporter.export_hsn_summary(month, year, path)
            else:
                result = exporter.export_all(month, year, temp_dir)
                path = result.get("report_file")

            if not result.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=result.get("message", "Export returned no data"),
                )

            output = result.get("output_file") or path
            if output and os.path.exists(output):
                return FileResponse(
                    path=output,
                    media_type="text/csv" if output.endswith(".csv") else "text/plain",
                    filename=os.path.basename(output),
                )
            raise HTTPException(status_code=404, detail="Export produced no file")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    except ImportError:
        raise HTTPException(status_code=501, detail="GSTR-1 module not available")


# ═══════════════════════════════════════════════════════════════════
# GSTR-3B Exports
# ═══════════════════════════════════════════════════════════════════

@router.get(
    "/gstr3b",
    summary="Generate GSTR-3B summary (JSON)",
)
async def export_gstr3b(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    user: dict = Depends(get_current_user),
):
    """Generate GSTR-3B tax liability summary for the specified period."""
    try:
        from exports.gstr3b_generator import GSTR3BGenerator

        sheets = _get_sheets_manager(user)
        generator = GSTR3BGenerator(sheets)
        result = generator.generate_summary(month, year)

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("message"))

        return {"period": f"{month:02d}/{year}", "summary": result["data"]["summary"]}
    except ImportError:
        raise HTTPException(status_code=501, detail="GSTR-3B module not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GSTR-3B failed: {str(e)}")


@router.get(
    "/gstr3b/download",
    summary="Download GSTR-3B report (text file)",
)
async def download_gstr3b(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    user: dict = Depends(get_current_user),
):
    """Download GSTR-3B as a formatted text report."""
    try:
        from exports.gstr3b_generator import GSTR3BGenerator

        sheets = _get_sheets_manager(user)
        generator = GSTR3BGenerator(sheets)
        period_str = f"{year}_{month:02d}"
        temp_dir = tempfile.mkdtemp(prefix="gstr3b_export_")
        text_path = os.path.join(temp_dir, f"GSTR3B_Report_{period_str}.txt")

        result = generator.generate_formatted_report(month, year, text_path)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("message"))

        return FileResponse(
            path=text_path,
            media_type="text/plain",
            filename=f"GSTR3B_Report_{period_str}.txt",
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="GSTR-3B module not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GSTR-3B download failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# Operational Reports
# ═══════════════════════════════════════════════════════════════════

@router.get(
    "/reports/{report_type}",
    summary="Generate an operational report",
)
async def get_report(
    report_type: int,
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (required for types 2, 3, 5)"),
    year: Optional[int] = Query(None, ge=2020, le=2100, description="Year (required for types 2, 3, 5)"),
    user: dict = Depends(get_current_user),
):
    """
    Generate an operational report.

    Report types:
    - 1: Processing Statistics (no month/year needed)
    - 2: GST Summary (month + year required)
    - 3: Duplicate Attempts (month + year optional, all-time if omitted)
    - 4: Correction Analysis (no month/year needed)
    - 5: Comprehensive Report (month + year required)
    """
    if report_type not in (1, 2, 3, 4, 5):
        raise HTTPException(status_code=400, detail="report_type must be 1-5")

    if report_type in (2, 5) and (month is None or year is None):
        raise HTTPException(
            status_code=400,
            detail=f"month and year are required for report type {report_type}",
        )

    try:
        from exports.operational_reports import OperationalReporter

        sheets = _get_sheets_manager(user)
        reporter = OperationalReporter(sheets)

        if report_type == 1:
            result = reporter.generate_processing_stats(month, year)
        elif report_type == 2:
            result = reporter.generate_gst_summary(month, year)
        elif report_type == 3:
            result = reporter.generate_duplicate_report(month, year)
        elif report_type == 4:
            result = reporter.generate_correction_analysis(month, year)
        else:
            result = reporter.generate_comprehensive_report(month, year)

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("message"))

        return result
    except ImportError:
        raise HTTPException(status_code=501, detail="Reports module not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report failed: {str(e)}")
