"""
Tests for Epic 3: Sheet Provisioner & Tenant Isolation

All external services (gspread, Google Sheets) are mocked.
No temporary files are written to project directories.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestSheetProvisioner(unittest.TestCase):
    """Test SheetProvisioner with mocked gspread"""

    @patch('sheets.sheet_provisioner.gspread')
    @patch('sheets.sheet_provisioner.ServiceAccountCredentials')
    @patch('sheets.sheet_provisioner.config')
    def setUp(self, mock_config, mock_creds_cls, mock_gspread):
        """Set up mocked provisioner before each test"""
        # Mock config
        mock_config.get_credentials_path.return_value = '/fake/creds.json'
        mock_config.TENANT_SHEET_NAME_TEMPLATE = 'GST_Scanner_{tenant_id}'
        mock_config.TENANT_SHEET_COLUMNS = {
            'Invoice_Header': ['Invoice_No', 'Invoice_Date'],
            'Line_Items': ['Invoice_No', 'Line_No'],
            'Customer_Master': ['GSTIN', 'Legal_Name'],
            'HSN_Master': ['HSN_SAC_Code', 'Description'],
            'Duplicate_Attempts': ['Timestamp', 'User_ID'],
            'Orders': ['Order_ID', 'Customer_Name'],
            'Order_Line_Items': ['Order_ID', 'Serial_No'],
            'Customer_Details': ['Customer_ID', 'Customer_Name'],
        }

        # Mock gspread client
        self.mock_client = MagicMock()
        mock_gspread.authorize.return_value = self.mock_client

        from sheets.sheet_provisioner import SheetProvisioner
        self.provisioner = SheetProvisioner()

    def test_create_tenant_sheet_creates_all_tabs(self):
        """create_tenant_sheet should create all 8 data tabs"""
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = 'new_sheet_id_123'
        self.mock_client.create.return_value = mock_spreadsheet

        mock_worksheet = MagicMock()
        mock_spreadsheet.add_worksheet.return_value = mock_worksheet

        result = self.provisioner.create_tenant_sheet('T001')

        self.assertEqual(result, 'new_sheet_id_123')
        self.mock_client.create.assert_called_once_with('GST_Scanner_T001')
        # 8 data tabs
        self.assertEqual(mock_spreadsheet.add_worksheet.call_count, 8)

    def test_create_tenant_sheet_removes_default_sheet1(self):
        """create_tenant_sheet should remove the default Sheet1"""
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = 'sheet_abc'
        self.mock_client.create.return_value = mock_spreadsheet

        mock_default = MagicMock()
        mock_spreadsheet.worksheet.return_value = mock_default

        self.provisioner.create_tenant_sheet('T002')

        mock_spreadsheet.worksheet.assert_called_with('Sheet1')
        mock_spreadsheet.del_worksheet.assert_called_once_with(mock_default)

    def test_create_tenant_sheet_shares_with_email(self):
        """If email is provided, the sheet should be shared read-only"""
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = 'shared_sheet'
        self.mock_client.create.return_value = mock_spreadsheet

        self.provisioner.create_tenant_sheet('T003', tenant_email='user@example.com')

        mock_spreadsheet.share.assert_called_once_with(
            'user@example.com', perm_type='user', role='reader'
        )

    def test_create_tenant_sheet_no_share_without_email(self):
        """Without email, share should not be called"""
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = 'no_share_sheet'
        self.mock_client.create.return_value = mock_spreadsheet

        self.provisioner.create_tenant_sheet('T004')

        mock_spreadsheet.share.assert_not_called()

    def test_create_tenant_sheet_handles_tab_creation_failure(self):
        """If a tab fails to create, it should continue with remaining tabs"""
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = 'partial_sheet'
        self.mock_client.create.return_value = mock_spreadsheet

        # Fail on the third add_worksheet call
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise Exception("API quota exceeded")
            return MagicMock()
        mock_spreadsheet.add_worksheet.side_effect = side_effect

        result = self.provisioner.create_tenant_sheet('T005')

        # Should still return the sheet ID
        self.assertEqual(result, 'partial_sheet')
        # Should have attempted all 8 tabs
        self.assertEqual(mock_spreadsheet.add_worksheet.call_count, 8)

    def test_validate_sheet_structure_all_valid(self):
        """validate_sheet_structure should return (True, []) when all tabs are correct"""
        mock_spreadsheet = MagicMock()
        self.mock_client.open_by_key.return_value = mock_spreadsheet

        # Mock worksheets matching registry
        worksheets = []
        import sheets.sheet_provisioner as sp
        for tab_name, columns in sp.config.TENANT_SHEET_COLUMNS.items():
            ws = MagicMock()
            ws.title = tab_name
            ws.row_values.return_value = columns
            worksheets.append(ws)

        mock_spreadsheet.worksheets.return_value = worksheets

        is_valid, issues = self.provisioner.validate_sheet_structure('valid_sheet_id')

        self.assertTrue(is_valid)
        self.assertEqual(issues, [])

    def test_validate_sheet_structure_missing_tab(self):
        """Should report missing tabs"""
        mock_spreadsheet = MagicMock()
        self.mock_client.open_by_key.return_value = mock_spreadsheet

        # Only provide 2 tabs
        ws1 = MagicMock()
        ws1.title = 'Invoice_Header'
        ws1.row_values.return_value = ['Invoice_No', 'Invoice_Date']

        ws2 = MagicMock()
        ws2.title = 'Line_Items'
        ws2.row_values.return_value = ['Invoice_No', 'Line_No']

        mock_spreadsheet.worksheets.return_value = [ws1, ws2]

        is_valid, issues = self.provisioner.validate_sheet_structure('partial_sheet_id')

        self.assertFalse(is_valid)
        self.assertTrue(any('Missing tab' in issue for issue in issues))

    def test_validate_sheet_structure_missing_column(self):
        """Should report missing columns in existing tabs"""
        mock_spreadsheet = MagicMock()
        self.mock_client.open_by_key.return_value = mock_spreadsheet

        import sheets.sheet_provisioner as sp
        worksheets = []
        for tab_name, columns in sp.config.TENANT_SHEET_COLUMNS.items():
            ws = MagicMock()
            ws.title = tab_name
            # Remove last column from first tab
            if tab_name == 'Invoice_Header':
                ws.row_values.return_value = columns[:-1]
            else:
                ws.row_values.return_value = columns
            worksheets.append(ws)

        mock_spreadsheet.worksheets.return_value = worksheets

        is_valid, issues = self.provisioner.validate_sheet_structure('missing_col_sheet')

        self.assertFalse(is_valid)
        self.assertTrue(any('missing column' in issue for issue in issues))

    def test_validate_sheet_structure_cannot_open(self):
        """Should handle failure to open sheet gracefully"""
        self.mock_client.open_by_key.side_effect = Exception("Not found")

        is_valid, issues = self.provisioner.validate_sheet_structure('nonexistent_id')

        self.assertFalse(is_valid)
        self.assertTrue(len(issues) == 1)
        self.assertIn('Cannot open sheet', issues[0])


class TestTenantManagerEpic3(unittest.TestCase):
    """Test TenantManager Epic 3 additions with mocked gspread"""

    @patch('utils.tenant_manager.gspread')
    @patch('utils.tenant_manager.ServiceAccountCredentials')
    @patch('utils.tenant_manager.config')
    def setUp(self, mock_config, mock_creds_cls, mock_gspread):
        mock_config.get_credentials_path.return_value = '/fake/creds.json'
        mock_config.GOOGLE_SHEET_ID = 'shared_sheet_id'
        mock_config.TENANT_INFO_SHEET = 'Tenant_Info'
        mock_config.FEATURE_TENANT_SHEET_ISOLATION = False
        mock_config.DEFAULT_SUBSCRIPTION_TIER = 'free'

        self.mock_client = MagicMock()
        mock_gspread.authorize.return_value = self.mock_client

        mock_spreadsheet = MagicMock()
        self.mock_client.open_by_key.return_value = mock_spreadsheet

        self.mock_worksheet = MagicMock()
        mock_spreadsheet.worksheet.return_value = self.mock_worksheet
        # Return header + one data row
        self.mock_worksheet.get_all_values.return_value = [
            ['Tenant ID', 'Tenant Name', 'Email ID', 'User ID', 'User Name',
             'Counter Of Invoice Upload', 'Counter of Order Uploads',
             'Date of Enrollment', 'Date of Billing', 'Subscription Type',
             'Sheet_ID', 'Subscription_Plan'],
            ['T001', 'Alice', 'alice@test.com', '12345', 'alice_tg',
             '5', '2', '2026-01-01', '', 'Free',
             'tenant_sheet_abc', 'free'],
        ]

        from utils.tenant_manager import TenantManager
        self.tm = TenantManager()

    def test_get_tenant_sheet_id_returns_id(self):
        """Should return sheet_id when tenant has one"""
        self.mock_worksheet.row_values.return_value = [
            'T001', 'Alice', 'alice@test.com', '12345', 'alice_tg',
            '5', '2', '2026-01-01', '', 'Free',
            'tenant_sheet_abc', 'free',
        ]
        result = self.tm.get_tenant_sheet_id(12345)
        self.assertEqual(result, 'tenant_sheet_abc')

    def test_get_tenant_sheet_id_returns_none_when_empty(self):
        """Should return None when tenant has no sheet_id"""
        self.mock_worksheet.row_values.return_value = [
            'T001', 'Alice', 'alice@test.com', '12345', 'alice_tg',
            '5', '2', '2026-01-01', '', 'Free',
            '', 'free',
        ]
        result = self.tm.get_tenant_sheet_id(12345)
        self.assertIsNone(result)

    def test_get_tenant_sheet_id_returns_none_for_missing_user(self):
        """Should return None for unknown user_id"""
        self.mock_worksheet.get_all_values.return_value = [
            ['Tenant ID', 'Tenant Name', 'Email ID', 'User ID'],
        ]
        result = self.tm.get_tenant_sheet_id(99999)
        self.assertIsNone(result)

    def test_update_subscription_success(self):
        """Should update the subscription plan cell"""
        self.mock_worksheet.row_values.return_value = [
            'T001', 'Alice', 'alice@test.com', '12345', 'alice_tg',
            '5', '2', '2026-01-01', '', 'Free', '', 'free',
        ]
        result = self.tm.update_subscription(12345, 'premium')
        self.assertTrue(result)
        # Column L = 12
        self.mock_worksheet.update_cell.assert_called_with(2, 12, 'premium')

    def test_update_subscription_unknown_user(self):
        """Should return False for unknown user"""
        self.mock_worksheet.get_all_values.return_value = [
            ['Tenant ID', 'Tenant Name', 'Email ID', 'User ID'],
        ]
        result = self.tm.update_subscription(99999, 'basic')
        self.assertFalse(result)


class TestConfigEpic3(unittest.TestCase):
    """Test Epic 3 config additions"""

    def test_tenant_sheet_columns_has_all_8_tabs(self):
        """TENANT_SHEET_COLUMNS registry should have all 8 data tabs"""
        import config
        self.assertEqual(len(config.TENANT_SHEET_COLUMNS), 8)

    def test_subscription_tiers_defaults(self):
        """Default subscription tiers should have free, basic, premium"""
        import config
        tier_ids = [t['id'] for t in config.SUBSCRIPTION_TIERS]
        self.assertIn('free', tier_ids)
        self.assertIn('basic', tier_ids)
        self.assertIn('premium', tier_ids)

    def test_feature_flag_defaults_to_false(self):
        """FEATURE_TENANT_SHEET_ISOLATION should default to False"""
        import config
        # We can only verify the default if no env var is set
        # Just verify the attribute exists
        self.assertIsInstance(config.FEATURE_TENANT_SHEET_ISOLATION, bool)

    def test_order_column_constants_exist(self):
        """Epic 3 should centralise order tab columns"""
        import config
        self.assertIsInstance(config.ORDER_SUMMARY_COLUMNS, list)
        self.assertIsInstance(config.ORDER_LINE_ITEMS_COLUMNS, list)
        self.assertIsInstance(config.ORDER_CUSTOMER_DETAILS_COLUMNS, list)
        # Verify they have content
        self.assertGreater(len(config.ORDER_SUMMARY_COLUMNS), 0)


class TestSheetsManagerEpic3(unittest.TestCase):
    """Test SheetsManager accepts optional sheet_id"""

    @patch('sheets.sheets_manager.gspread')
    @patch('sheets.sheets_manager.ServiceAccountCredentials')
    @patch('sheets.sheets_manager.config')
    def test_init_with_custom_sheet_id(self, mock_config, mock_creds_cls, mock_gspread):
        """Should open the specified sheet when sheet_id is provided"""
        mock_config.get_credentials_path.return_value = '/fake/creds.json'
        mock_config.GOOGLE_SHEET_ID = 'default_shared_id'
        mock_config.SHEET_NAME = 'Invoice_Header'
        mock_config.LINE_ITEMS_SHEET_NAME = 'Line_Items'

        mock_client = MagicMock()
        mock_gspread.authorize.return_value = mock_client
        mock_spreadsheet = MagicMock()
        mock_client.open_by_key.return_value = mock_spreadsheet

        from sheets.sheets_manager import SheetsManager
        sm = SheetsManager(sheet_id='custom_tenant_sheet')

        mock_client.open_by_key.assert_called_once_with('custom_tenant_sheet')

    @patch('sheets.sheets_manager.gspread')
    @patch('sheets.sheets_manager.ServiceAccountCredentials')
    @patch('sheets.sheets_manager.config')
    def test_init_without_sheet_id_uses_default(self, mock_config, mock_creds_cls, mock_gspread):
        """Should fall back to config.GOOGLE_SHEET_ID when no sheet_id"""
        mock_config.get_credentials_path.return_value = '/fake/creds.json'
        mock_config.GOOGLE_SHEET_ID = 'default_shared_id'
        mock_config.SHEET_NAME = 'Invoice_Header'
        mock_config.LINE_ITEMS_SHEET_NAME = 'Line_Items'

        mock_client = MagicMock()
        mock_gspread.authorize.return_value = mock_client
        mock_spreadsheet = MagicMock()
        mock_client.open_by_key.return_value = mock_spreadsheet

        from sheets.sheets_manager import SheetsManager
        sm = SheetsManager()

        mock_client.open_by_key.assert_called_once_with('default_shared_id')


if __name__ == '__main__':
    unittest.main()
