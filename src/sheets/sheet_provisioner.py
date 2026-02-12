"""
Sheet Provisioner (Epic 3)
Creates and manages per-tenant Google Sheets with all required data tabs.
Feature-flagged: only active when FEATURE_TENANT_SHEET_ISOLATION is True.
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Dict, List, Optional, Tuple
import config


class SheetProvisioner:
    """Creates and validates per-tenant Google Sheets"""

    def __init__(self):
        """Initialize gspread client using shared credential resolution"""
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]

        creds_path = config.get_credentials_path()

        if creds_path:
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            self.client = gspread.authorize(creds)
        else:
            import google.auth
            credentials, project = google.auth.default(scopes=scope)
            self.client = gspread.authorize(credentials)

    def create_tenant_sheet(
        self,
        tenant_id: str,
        tenant_email: Optional[str] = None,
    ) -> str:
        """
        Create a new Google Sheet for a tenant with all required data tabs.

        Args:
            tenant_id: Unique tenant identifier (e.g. T001)
            tenant_email: Optional email to share the sheet with (read-only)

        Returns:
            The new sheet's spreadsheet ID string.

        Raises:
            Exception: If sheet creation fails.
        """
        sheet_title = config.TENANT_SHEET_NAME_TEMPLATE.format(tenant_id=tenant_id)

        # Create the spreadsheet
        spreadsheet = self.client.create(sheet_title)
        sheet_id = spreadsheet.id
        print(f"[PROVISIONER] Created sheet '{sheet_title}' (ID: {sheet_id})")

        # Create all data tabs from the registry
        tabs_created = []
        for tab_name, columns in config.TENANT_SHEET_COLUMNS.items():
            try:
                worksheet = spreadsheet.add_worksheet(
                    title=tab_name,
                    rows=1000,
                    cols=max(len(columns), 1),
                )
                worksheet.append_row(columns, value_input_option='USER_ENTERED')
                tabs_created.append(tab_name)
            except Exception as e:
                print(f"[PROVISIONER] Warning: failed to create tab '{tab_name}': {e}")

        # Remove the default "Sheet1" that gspread creates automatically
        try:
            default_sheet = spreadsheet.worksheet("Sheet1")
            spreadsheet.del_worksheet(default_sheet)
        except gspread.exceptions.WorksheetNotFound:
            pass  # Already removed or doesn't exist
        except Exception as e:
            print(f"[PROVISIONER] Warning: could not remove default Sheet1: {e}")

        # Optionally share with tenant email (read-only)
        if tenant_email:
            try:
                spreadsheet.share(tenant_email, perm_type='user', role='reader')
                print(f"[PROVISIONER] Shared sheet with {tenant_email} (reader)")
            except Exception as e:
                print(f"[PROVISIONER] Warning: could not share sheet with {tenant_email}: {e}")

        print(f"[PROVISIONER] Provisioned {len(tabs_created)}/{len(config.TENANT_SHEET_COLUMNS)} tabs: {tabs_created}")
        return sheet_id

    def validate_sheet_structure(self, sheet_id: str) -> Tuple[bool, List[str]]:
        """
        Validate that a sheet has all required tabs and columns.

        Args:
            sheet_id: Google Sheet spreadsheet ID to validate.

        Returns:
            Tuple of (is_valid, list_of_issues).
            is_valid is True when all tabs and columns match the registry.
        """
        issues: List[str] = []

        try:
            spreadsheet = self.client.open_by_key(sheet_id)
        except Exception as e:
            return (False, [f"Cannot open sheet {sheet_id}: {e}"])

        existing_tabs = {ws.title: ws for ws in spreadsheet.worksheets()}

        for tab_name, expected_columns in config.TENANT_SHEET_COLUMNS.items():
            if tab_name not in existing_tabs:
                issues.append(f"Missing tab: {tab_name}")
                continue

            # Check column headers
            try:
                headers = existing_tabs[tab_name].row_values(1)
            except Exception as e:
                issues.append(f"Cannot read headers for tab '{tab_name}': {e}")
                continue

            for col in expected_columns:
                if col not in headers:
                    issues.append(f"Tab '{tab_name}': missing column '{col}'")

        is_valid = len(issues) == 0
        if is_valid:
            print(f"[PROVISIONER] Sheet {sheet_id} validation PASSED")
        else:
            print(f"[PROVISIONER] Sheet {sheet_id} validation FAILED with {len(issues)} issue(s)")
            for issue in issues:
                print(f"  - {issue}")

        return (is_valid, issues)
