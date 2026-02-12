"""
API helper functions shared across route modules.
Provides tenant-aware SheetsManager resolution and other utilities.
"""
from typing import Optional, Dict
import config


def get_tenant_sheets_manager(user: Dict, sheet_id_override: str = None):
    """
    Return a SheetsManager routed to the correct Google Sheet for the user.

    Resolution order:
    1. If ``sheet_id_override`` is given, use it directly.
    2. If ``FEATURE_TENANT_SHEET_ISOLATION`` is enabled, look up the
       tenant record by the API user's email and return a SheetsManager
       pointed at the tenant's dedicated sheet.
    3. Fall back to the shared (default) sheet.

    Args:
        user: Current API user dict (from ``get_current_user``).
        sheet_id_override: Explicit sheet ID (e.g. for admin endpoints).

    Returns:
        A connected ``SheetsManager`` instance.
    """
    from sheets.sheets_manager import SheetsManager

    # Explicit override
    if sheet_id_override:
        return SheetsManager(sheet_id=sheet_id_override)

    # Tenant isolation
    if config.FEATURE_TENANT_SHEET_ISOLATION:
        tenant_sheet_id = _resolve_tenant_sheet_id(user)
        if tenant_sheet_id:
            return SheetsManager(sheet_id=tenant_sheet_id)

    # Shared sheet
    return SheetsManager()


def _resolve_tenant_sheet_id(user: Dict) -> Optional[str]:
    """
    Look up the tenant's dedicated sheet ID by email.

    The Tenant_Info sheet stores an email in column C (Email ID).
    We scan it for the API user's email and, if found, return the
    value in column K (Sheet_ID).
    """
    try:
        from utils.tenant_manager import TenantManager
        tm = TenantManager()

        email = (user.get("email") or "").strip().lower()
        if not email:
            return None

        all_values = tm.worksheet.get_all_values()
        for row in all_values[1:]:  # skip header
            # Column C (index 2) is Email ID
            if len(row) > 10 and row[2].strip().lower() == email:
                sheet_id = row[10].strip()  # Column K (index 10) is Sheet_ID
                return sheet_id if sheet_id else None

        return None
    except Exception as e:
        print(f"[API] Tenant sheet lookup failed for {user.get('email')}: {e}")
        return None


def get_tenant_order_orchestrator(user: Dict):
    """
    Return an OrderNormalizationOrchestrator routed to the correct sheet.
    """
    from order_normalization.orchestrator import OrderNormalizationOrchestrator

    sheet_id = None
    if config.FEATURE_TENANT_SHEET_ISOLATION:
        sheet_id = _resolve_tenant_sheet_id(user)

    return OrderNormalizationOrchestrator(sheet_id=sheet_id)
