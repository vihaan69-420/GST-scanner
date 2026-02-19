"""
Tenant Manager
Manages tenant registration and usage tracking in the Tenant_Info Google Sheet tab.
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from typing import Dict, Optional, Tuple
import time
import config

TENANT_CACHE_TTL_SECONDS = 60


# Column mapping for the Tenant_Info sheet (1-indexed)
COL_TENANT_ID = 1          # A
COL_TENANT_NAME = 2        # B
COL_EMAIL_ID = 3            # C
COL_USER_ID = 4             # D
COL_USER_NAME = 5           # E
COL_INVOICE_COUNT = 6       # F
COL_ORDER_COUNT = 7         # G
COL_DATE_ENROLLMENT = 8     # H
COL_DATE_BILLING = 9        # I
COL_SUBSCRIPTION_TYPE = 10  # J
COL_SHEET_ID = 11           # K  (Epic 3: per-tenant sheet ID)
COL_SUBSCRIPTION_PLAN = 12  # L  (Epic 3: configurable tier id)
COL_SUBSCRIPTION_EXPIRES_AT = 13  # M  (Subscription expiry date)
COL_RAZORPAY_CUSTOMER_ID = 14    # N  (Razorpay customer reference)

HEADERS = [
    'Tenant ID', 'Tenant Name', 'Email ID', 'User ID', 'User Name',
    'Counter Of Invoice Upload', 'Counter of Order Uploads',
    'Date of Enrollment', 'Date of Billing', 'Subscription Type',
    'Sheet_ID', 'Subscription_Plan', 'Subscription_Expires_At',
    'Razorpay_Customer_ID'
]


def _col_letter(col_num: int) -> str:
    """Convert 1-indexed column number to letter (1->A, 2->B, ..., 26->Z)."""
    return chr(ord('A') + col_num - 1)


class TenantManager:
    """Manages tenant info in Google Sheets"""

    def __init__(self):
        """Connect to Google Sheet and open/create the Tenant_Info tab"""
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

        self.spreadsheet = self.client.open_by_key(config.GOOGLE_SHEET_ID)

        # Open or create the Tenant_Info tab
        try:
            self.worksheet = self.spreadsheet.worksheet(config.TENANT_INFO_SHEET)
            print(f"[TENANT] Opened existing '{config.TENANT_INFO_SHEET}' tab")
        except gspread.exceptions.WorksheetNotFound:
            self.worksheet = self.spreadsheet.add_worksheet(
                title=config.TENANT_INFO_SHEET, rows=100, cols=len(HEADERS)
            )
            self.worksheet.append_row(HEADERS)
            print(f"[TENANT] Created '{config.TENANT_INFO_SHEET}' tab with headers")

        # Cache: map user_id -> row number for fast lookups
        self._row_cache: Dict[int, int] = {}
        # TTL data cache: user_id -> (tenant_dict, timestamp)
        self._data_cache: Dict[int, Tuple[Dict, float]] = {}
        self._load_cache()

    def _load_cache(self):
        """Load user_id -> row mapping from sheet"""
        try:
            all_values = self.worksheet.get_all_values()
            for row_idx, row in enumerate(all_values):
                if row_idx == 0:
                    continue  # Skip header
                if len(row) >= COL_USER_ID and row[COL_USER_ID - 1]:
                    try:
                        uid = int(row[COL_USER_ID - 1])
                        self._row_cache[uid] = row_idx + 1  # 1-indexed
                    except (ValueError, TypeError):
                        pass
            print(f"[TENANT] Cached {len(self._row_cache)} tenant(s)")
        except Exception as e:
            print(f"[TENANT] Cache load warning: {e}")

    def invalidate_cache(self, user_id: int):
        """Remove a user's entry from the TTL data cache."""
        self._data_cache.pop(user_id, None)

    def get_tenant(self, user_id: int) -> Optional[Dict]:
        """
        Look up a tenant by Telegram User ID.

        Returns:
            Dict with tenant info, or None if not found.
        """
        # Check TTL data cache first — avoids any Sheets call
        cached = self._data_cache.get(user_id)
        if cached is not None:
            tenant_dict, ts = cached
            if time.monotonic() - ts < TENANT_CACHE_TTL_SECONDS:
                return tenant_dict

        # Check row-number cache (still needs a single row read)
        if user_id in self._row_cache:
            row_num = self._row_cache[user_id]
            try:
                row = self.worksheet.row_values(row_num)
                if row and len(row) >= COL_SUBSCRIPTION_TYPE:
                    result = self._row_to_dict(row)
                    self._data_cache[user_id] = (result, time.monotonic())
                    return result
            except Exception:
                pass  # Fall through to full scan

        # Full scan (cache miss or stale)
        try:
            all_values = self.worksheet.get_all_values()
            for row_idx, row in enumerate(all_values):
                if row_idx == 0:
                    continue
                if len(row) >= COL_USER_ID and row[COL_USER_ID - 1]:
                    try:
                        if int(row[COL_USER_ID - 1]) == user_id:
                            self._row_cache[user_id] = row_idx + 1
                            result = self._row_to_dict(row)
                            self._data_cache[user_id] = (result, time.monotonic())
                            return result
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            print(f"[TENANT] Lookup error: {e}")

        return None

    def register_tenant(
        self,
        user_id: int,
        first_name: str,
        username: str,
        email: str
    ) -> Dict:
        """
        Register a new tenant.

        Args:
            user_id: Telegram user ID
            first_name: Telegram first name
            username: Telegram @username
            email: User-provided email

        Returns:
            Dict with the new tenant row data
        """
        tenant_id = self._next_tenant_id()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Epic 3: Provision a per-tenant Google Sheet if feature enabled
        sheet_id = ''
        if config.FEATURE_TENANT_SHEET_ISOLATION:
            try:
                from sheets.sheet_provisioner import SheetProvisioner
                provisioner = SheetProvisioner()
                sheet_id = provisioner.create_tenant_sheet(
                    tenant_id=tenant_id,
                    tenant_email=email if email else None,
                )
                print(f"[TENANT] Provisioned sheet for {tenant_id}: {sheet_id}")
            except Exception as e:
                print(f"[TENANT] Sheet provisioning failed for {tenant_id}, continuing with shared sheet: {e}")
                sheet_id = ''

        new_row = [
            tenant_id,                  # A: Tenant ID
            first_name or '',           # B: Tenant Name
            email,                      # C: Email ID
            str(user_id),               # D: User ID
            username or '',             # E: User Name
            '0',                        # F: Counter Of Invoice Upload
            '0',                        # G: Counter of Order Uploads
            now,                        # H: Date of Enrollment
            '',                         # I: Date of Billing (empty for Free)
            'Free',                     # J: Subscription Type
            sheet_id,                   # K: Sheet_ID (Epic 3)
            config.DEFAULT_SUBSCRIPTION_TIER,  # L: Subscription_Plan (Epic 3)
            '',                         # M: Subscription_Expires_At
            '',                         # N: Razorpay_Customer_ID
        ]

        self.worksheet.append_row(new_row, value_input_option='USER_ENTERED', insert_data_option='INSERT_ROWS', table_range='A1')

        # Update cache with the new row number
        all_values = self.worksheet.get_all_values()
        self._row_cache[user_id] = len(all_values)
        self.invalidate_cache(user_id)

        print(f"[TENANT] Registered new tenant: {tenant_id} ({first_name}, {user_id})")
        return self._row_to_dict(new_row)

    def increment_invoice_counter(self, user_id: int):
        """Increment the invoice upload counter for a tenant"""
        self._increment_counter(user_id, COL_INVOICE_COUNT)

    def increment_order_counter(self, user_id: int):
        """Increment the order upload counter for a tenant"""
        self._increment_counter(user_id, COL_ORDER_COUNT)

    def _increment_counter(self, user_id: int, col: int):
        """Increment a numeric counter cell for the given user"""
        row_num = self._row_cache.get(user_id)
        if not row_num:
            # Try a fresh lookup
            tenant = self.get_tenant(user_id)
            if not tenant:
                print(f"[TENANT] Cannot increment counter: user {user_id} not found")
                return
            row_num = self._row_cache.get(user_id)

        try:
            current_val = self.worksheet.cell(row_num, col).value
            new_val = int(current_val or 0) + 1
            self.worksheet.update_cell(row_num, col, new_val)
            self.invalidate_cache(user_id)
            print(f"[TENANT] Updated counter col {col} for user {user_id}: {new_val}")
        except Exception as e:
            print(f"[TENANT] Counter increment failed for user {user_id}: {e}")

    def _next_tenant_id(self) -> str:
        """Generate next tenant ID (T001, T002, ...)"""
        try:
            all_values = self.worksheet.get_all_values()
            max_num = 0
            for row in all_values[1:]:  # Skip header
                if row and row[0].startswith('T'):
                    try:
                        num = int(row[0][1:])
                        max_num = max(max_num, num)
                    except (ValueError, IndexError):
                        pass
            return f"T{max_num + 1:03d}"
        except Exception:
            return f"T{len(self._row_cache) + 1:03d}"

    def get_tenant_sheet_id(self, user_id: int) -> Optional[str]:
        """
        Get the per-tenant Google Sheet ID for a user (Epic 3).

        Returns:
            Sheet ID string, or None if the tenant has no dedicated sheet.
        """
        tenant = self.get_tenant(user_id)
        if tenant and tenant.get('sheet_id'):
            return tenant['sheet_id']
        return None

    def update_subscription(self, user_id: int, tier_id: str) -> bool:
        """
        Update a tenant's subscription plan (Epic 3).

        Args:
            user_id: Telegram user ID
            tier_id: Subscription tier identifier (e.g. 'free', 'basic', 'premium')

        Returns:
            True if updated successfully, False otherwise.
        """
        row_num = self._row_cache.get(user_id)
        if not row_num:
            tenant = self.get_tenant(user_id)
            if not tenant:
                print(f"[TENANT] Cannot update subscription: user {user_id} not found")
                return False
            row_num = self._row_cache.get(user_id)

        try:
            self.worksheet.update_cell(row_num, COL_SUBSCRIPTION_PLAN, tier_id)
            self.invalidate_cache(user_id)
            print(f"[TENANT] Updated subscription for user {user_id}: {tier_id}")
            return True
        except Exception as e:
            print(f"[TENANT] Subscription update failed for user {user_id}: {e}")
            return False

    def update_subscription_with_expiry(
        self, user_id: int, tier_id: str, expires_at: str, razorpay_customer_id: str = ''
    ) -> bool:
        """
        Update subscription plan, expiry, billing date, and optionally Razorpay customer ID.

        Args:
            user_id: Telegram user ID
            tier_id: Subscription tier identifier
            expires_at: ISO date string for expiry (empty string for free tier)
            razorpay_customer_id: Razorpay customer identifier

        Returns:
            True if updated successfully, False otherwise.
        """
        row_num = self._row_cache.get(user_id)
        if not row_num:
            tenant = self.get_tenant(user_id)
            if not tenant:
                print(f"[TENANT] Cannot update subscription: user {user_id} not found")
                return False
            row_num = self._row_cache.get(user_id)

        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            batch_updates = [
                {'range': f'{_col_letter(COL_SUBSCRIPTION_PLAN)}{row_num}', 'values': [[tier_id]]},
                {'range': f'{_col_letter(COL_DATE_BILLING)}{row_num}', 'values': [[now]]},
                {'range': f'{_col_letter(COL_SUBSCRIPTION_EXPIRES_AT)}{row_num}', 'values': [[expires_at]]},
            ]
            if razorpay_customer_id:
                batch_updates.append(
                    {'range': f'{_col_letter(COL_RAZORPAY_CUSTOMER_ID)}{row_num}', 'values': [[razorpay_customer_id]]}
                )
            self.worksheet.batch_update(batch_updates, value_input_option='USER_ENTERED')
            self.invalidate_cache(user_id)
            print(f"[TENANT] Updated subscription for user {user_id}: {tier_id}, expires: {expires_at}")
            return True
        except Exception as e:
            print(f"[TENANT] Subscription update with expiry failed for user {user_id}: {e}")
            return False

    def get_tenant_by_email(self, email: str) -> Optional[Dict]:
        """Look up a tenant by email address (for API user resolution)."""
        try:
            all_values = self.worksheet.get_all_values()
            for row_idx, row in enumerate(all_values):
                if row_idx == 0:
                    continue
                if len(row) >= COL_EMAIL_ID and row[COL_EMAIL_ID - 1]:
                    if row[COL_EMAIL_ID - 1].strip().lower() == email.strip().lower():
                        uid_str = row[COL_USER_ID - 1] if len(row) >= COL_USER_ID else ''
                        if uid_str:
                            try:
                                self._row_cache[int(uid_str)] = row_idx + 1
                            except (ValueError, TypeError):
                                pass
                        return self._row_to_dict(row)
        except Exception as e:
            print(f"[TENANT] Email lookup error: {e}")
        return None

    @staticmethod
    def _row_to_dict(row) -> Dict:
        """Convert a sheet row to a dict"""
        return {
            'tenant_id': row[COL_TENANT_ID - 1] if len(row) >= COL_TENANT_ID else '',
            'tenant_name': row[COL_TENANT_NAME - 1] if len(row) >= COL_TENANT_NAME else '',
            'email': row[COL_EMAIL_ID - 1] if len(row) >= COL_EMAIL_ID else '',
            'user_id': row[COL_USER_ID - 1] if len(row) >= COL_USER_ID else '',
            'user_name': row[COL_USER_NAME - 1] if len(row) >= COL_USER_NAME else '',
            'invoice_count': row[COL_INVOICE_COUNT - 1] if len(row) >= COL_INVOICE_COUNT else '0',
            'order_count': row[COL_ORDER_COUNT - 1] if len(row) >= COL_ORDER_COUNT else '0',
            'enrollment_date': row[COL_DATE_ENROLLMENT - 1] if len(row) >= COL_DATE_ENROLLMENT else '',
            'billing_date': row[COL_DATE_BILLING - 1] if len(row) >= COL_DATE_BILLING else '',
            'subscription_type': row[COL_SUBSCRIPTION_TYPE - 1] if len(row) >= COL_SUBSCRIPTION_TYPE else 'Free',
            'sheet_id': row[COL_SHEET_ID - 1] if len(row) >= COL_SHEET_ID else '',
            'subscription_plan': row[COL_SUBSCRIPTION_PLAN - 1] if len(row) >= COL_SUBSCRIPTION_PLAN else '',
            'subscription_expires_at': row[COL_SUBSCRIPTION_EXPIRES_AT - 1] if len(row) >= COL_SUBSCRIPTION_EXPIRES_AT else '',
            'razorpay_customer_id': row[COL_RAZORPAY_CUSTOMER_ID - 1] if len(row) >= COL_RAZORPAY_CUSTOMER_ID else '',
        }
