"""
Google Sheets Integration
Handles appending invoice data to Google Sheets
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Dict, List
import config


def get_column_letter(col_num):
    """
    Convert column number to Excel-style column letter
    1 -> A, 26 -> Z, 27 -> AA, etc.
    
    Args:
        col_num: Column number (1-indexed)
        
    Returns:
        Column letter(s)
    """
    result = ""
    while col_num > 0:
        col_num -= 1
        result = chr(col_num % 26 + 65) + result
        col_num //= 26
    return result


class SheetsManager:
    """Manage Google Sheets operations for GST invoice data"""
    
    def __init__(self, sheet_id: str = None):
        """Initialize Google Sheets connection with environment-aware credentials

        Args:
            sheet_id: Optional Google Sheet ID for per-tenant routing (Epic 3).
                      When None, falls back to config.GOOGLE_SHEET_ID (default).
        """
        # Define the scope
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Get credentials path (may be None for ADC)
        creds_path = config.get_credentials_path()
        
        if creds_path:
            # Use service account JSON file (local, Docker, or Cloud Run with secret)
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            self.client = gspread.authorize(creds)
        else:
            # Use Application Default Credentials (Cloud Run with Workload Identity)
            import google.auth
            credentials, project = google.auth.default(scopes=scope)
            self.client = gspread.authorize(credentials)
        
        # Open the spreadsheet (per-tenant or shared)
        target_sheet_id = sheet_id or config.GOOGLE_SHEET_ID
        try:
            self.spreadsheet = self.client.open_by_key(target_sheet_id)
            self.worksheet = self.spreadsheet.worksheet(config.SHEET_NAME)
            self.line_items_worksheet = self.spreadsheet.worksheet(config.LINE_ITEMS_SHEET_NAME)
        except Exception as e:
            raise Exception(f"Failed to open Google Sheet: {str(e)}")
    
    def append_invoice(self, invoice_data: List) -> bool:
        """
        Append invoice data to Google Sheet
        
        Args:
            invoice_data: List of values matching sheet columns
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure data has exactly the right number of columns
            while len(invoice_data) < len(config.SHEET_COLUMNS):
                invoice_data.append('')
            invoice_data = invoice_data[:len(config.SHEET_COLUMNS)]
            
            # Convert all values to strings and handle None values
            invoice_data = [str(val) if val not in [None, 'None', 'null'] else '' for val in invoice_data]
            
            # Use append_row with value_input_option for proper formatting
            self.worksheet.append_row(invoice_data, value_input_option='USER_ENTERED', insert_data_option='INSERT_ROWS', table_range='A1')
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to append data to Google Sheet: {str(e)}")
    
    def get_last_invoice_no(self) -> str:
        """
        Get the last invoice number from the sheet
        
        Returns:
            Last invoice number or empty string
        """
        try:
            # Get all values from Invoice_No column (column A)
            invoice_nos = self.worksheet.col_values(1)
            
            # Return last non-empty value (skip header)
            if len(invoice_nos) > 1:
                return invoice_nos[-1]
            return ""
            
        except Exception as e:
            print(f"Warning: Could not fetch last invoice number: {str(e)}")
            return ""
    
    def check_duplicate(self, invoice_no: str) -> bool:
        """
        Check if invoice number already exists in sheet
        
        Args:
            invoice_no: Invoice number to check
            
        Returns:
            True if duplicate exists, False otherwise
        """
        try:
            # Get all invoice numbers
            invoice_nos = self.worksheet.col_values(1)
            
            # Check if invoice_no exists (case-insensitive)
            return invoice_no.upper() in [inv.upper() for inv in invoice_nos]
            
        except Exception as e:
            print(f"Warning: Could not check for duplicates: {str(e)}")
            return False
    
    def get_sheet_headers(self) -> List[str]:
        """
        Get column headers from the sheet
        Auto-detects header row if not in row 1
        
        Returns:
            List of column headers
        """
        try:
            # Try first 5 rows to find the header row
            # Headers typically contain 'Invoice_No' or similar
            for row_num in range(1, 6):
                row = self.worksheet.row_values(row_num)
                if row and any(header in row for header in ['Invoice_No', 'Invoice_Date', 'Seller_Name', 'Buyer_Name']):
                    # Found the header row
                    if row_num > 1:
                        print(f"[INFO] Headers found in row {row_num} (not row 1)")
                    return row
            
            # Fallback to row 1 if no headers detected
            return self.worksheet.row_values(1)
            
        except Exception as e:
            print(f"Warning: Could not fetch headers: {str(e)}")
            return []
    
    def validate_sheet_structure(self) -> bool:
        """
        Validate that sheet has correct columns
        
        Returns:
            True if valid, False otherwise
        """
        try:
            headers = self.get_sheet_headers()
            
            # Check if required columns exist
            missing_cols = []
            for col in config.SHEET_COLUMNS:
                if col not in headers:
                    missing_cols.append(col)
            
            if missing_cols:
                print(f"Warning: Missing columns in sheet: {missing_cols}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating sheet structure: {str(e)}")
            return False
    
    def get_line_items_worksheet(self):
        """
        Get line items worksheet
        
        Returns:
            Worksheet object for line items
        """
        return self.line_items_worksheet
    
    def append_invoice_with_items(self, invoice_data: List, line_items_data: List[List], validation_result: Dict) -> bool:
        """
        Append invoice header and line items to respective sheets
        ALWAYS starts from Column A with strict validation
        
        Args:
            invoice_data: List of values for invoice header (formatted for sheets)
            line_items_data: List of lists, each inner list is a line item row
            validation_result: Validation result dict with status, errors, warnings
            
        Returns:
            True if successful
            
        Raises:
            Exception: If validation fails or write fails
        """
        try:
            # ============================================
            # STEP 1: INPUT VALIDATION
            # ============================================
            if not invoice_data:
                raise ValueError("invoice_data cannot be empty")
            
            if not isinstance(invoice_data, list):
                raise ValueError(f"invoice_data must be a list, got {type(invoice_data)}")
            
            # Update validation fields in invoice_data before appending
            status_idx = 22  # Validation_Status is column 23 (index 22)
            remarks_idx = 23  # Validation_Remarks is column 24 (index 23)
            
            # Ensure invoice_data has at least 24 elements
            while len(invoice_data) < 24:
                invoice_data.append('')
            
            # Update validation fields
            invoice_data[status_idx] = validation_result.get('status', 'UNKNOWN')
            
            # Format remarks
            remarks = []
            if validation_result.get('errors'):
                remarks.append("ERRORS: " + "; ".join(validation_result['errors']))
            if validation_result.get('warnings'):
                remarks.append("WARNINGS: " + "; ".join(validation_result['warnings']))
            
            if remarks:
                invoice_data[remarks_idx] = " | ".join(remarks)
            else:
                invoice_data[remarks_idx] = "All validations passed"
            
            # ============================================
            # STEP 2: STRICT DATA SANITIZATION
            # ============================================
            # FORCE exactly 24 columns - Tier 1 only (A to X)
            invoice_data = invoice_data[:24]
            
            # Convert all values to strings, handle None/null
            invoice_data = [str(val) if val not in [None, 'None', 'null'] else '' for val in invoice_data]
            
            # Validate no value exceeds reasonable length (prevent garbage)
            MAX_CELL_LENGTH = 5000
            for i, val in enumerate(invoice_data):
                if len(val) > MAX_CELL_LENGTH:
                    print(f"[WARNING] Truncating cell {i} from {len(val)} to {MAX_CELL_LENGTH} chars")
                    invoice_data[i] = val[:MAX_CELL_LENGTH]
            
            # ============================================
            # STEP 3: FIND CORRECT ROW (with validation)
            # ============================================
            all_data = self.worksheet.get_all_values()
            
            # Check for garbage columns beyond X (column 24)
            if all_data and len(all_data[0]) > 24:
                print(f"[WARNING] Sheet has {len(all_data[0])} columns, expected max 24. Clearing garbage...")
                try:
                    # Clear columns Y onwards (25+) for all rows
                    self.worksheet.batch_clear(['Y1:ZZ1000'])
                    # Re-fetch data after cleanup
                    all_data = self.worksheet.get_all_values()
                except Exception as e:
                    print(f"[WARNING] Could not clear garbage columns: {e}")
            
            next_row = len(all_data) + 1
            
            # Minimum row 2 (after header)
            if next_row < 2:
                next_row = 2
            
            # Sanity check: next_row should be reasonable
            MAX_ROWS = 10000
            if next_row > MAX_ROWS:
                raise ValueError(f"next_row {next_row} exceeds maximum {MAX_ROWS}. Sheet may have garbage data.")
            
            # ============================================
            # STEP 4: WRITE DATA (with verification)
            # ============================================
            # Use batch update - ONE API call for entire row (A to X)
            range_str = f'A{next_row}:X{next_row}'
            self.worksheet.update(values=[invoice_data], range_name=range_str, value_input_option='USER_ENTERED')
            
            # ============================================
            # STEP 5: VERIFY WRITE SUCCESS
            # ============================================
            # Read back the first cell to verify
            written_value = self.worksheet.acell(f'A{next_row}').value
            expected_value = invoice_data[0]
            
            if written_value != expected_value:
                raise Exception(f"Write verification failed: Expected '{expected_value}' in A{next_row}, got '{written_value}'")
            
            # ============================================
            # STEP 6: LINE ITEMS - Always Column A (with validation)
            # ============================================
            if line_items_data:
                # Validate line_items_data
                if not isinstance(line_items_data, list):
                    raise ValueError(f"line_items_data must be a list, got {type(line_items_data)}")
                
                all_line_data = self.line_items_worksheet.get_all_values()
                
                # Check for garbage columns beyond S (column 19)
                if all_line_data and len(all_line_data[0]) > 19:
                    print(f"[WARNING] Line_Items has {len(all_line_data[0])} columns, expected max 19. Clearing...")
                    try:
                        self.line_items_worksheet.batch_clear(['T1:ZZ1000'])
                        all_line_data = self.line_items_worksheet.get_all_values()
                    except Exception as e:
                        print(f"[WARNING] Could not clear garbage columns: {e}")
                
                next_line_row = len(all_line_data) + 1
                if next_line_row < 2:
                    next_line_row = 2
                
                # Sanity check
                if next_line_row > MAX_ROWS:
                    raise ValueError(f"next_line_row {next_line_row} exceeds maximum. Sheet may have garbage.")
                
                # Prepare all line items for batch update with validation
                rows_to_write = []
                for idx, item_row in enumerate(line_items_data):
                    if not isinstance(item_row, list):
                        print(f"[WARNING] Skipping invalid line item {idx}: not a list")
                        continue
                    
                    # Ensure exactly 19 columns (A to S)
                    while len(item_row) < 19:
                        item_row.append('')
                    item_row = item_row[:19]  # STRICT: only 19 columns
                    
                    # Convert to strings and truncate if needed
                    clean_row = []
                    for val in item_row:
                        str_val = str(val) if val not in [None, 'None', 'null'] else ''
                        if len(str_val) > MAX_CELL_LENGTH:
                            str_val = str_val[:MAX_CELL_LENGTH]
                        clean_row.append(str_val)
                    
                    rows_to_write.append(clean_row)
                
                if rows_to_write:
                    # Write ALL line items in ONE API call
                    end_row = next_line_row + len(rows_to_write) - 1
                    range_str = f'A{next_line_row}:S{end_row}'
                    self.line_items_worksheet.update(values=rows_to_write, range_name=range_str, value_input_option='USER_ENTERED')
                    
                    # Verify first line item was written correctly
                    first_written = self.line_items_worksheet.acell(f'A{next_line_row}').value
                    if first_written != rows_to_write[0][0]:
                        print(f"[WARNING] Line item verification: expected '{rows_to_write[0][0]}', got '{first_written}'")
                    
                    print(f"[OK] Wrote {len(rows_to_write)} line items to rows {next_line_row}-{end_row}")
            
            print(f"[OK] Invoice '{invoice_data[0]}' written to row {next_row}, columns A-X")
            return True
            
        except ValueError as e:
            # Input validation errors - don't write garbage
            print(f"[ERROR] Validation failed: {str(e)}")
            raise Exception(f"Input validation failed: {str(e)}")
            
        except Exception as e:
            # Log the error with details for debugging
            print(f"[ERROR] Failed to append invoice: {str(e)}")
            raise Exception(f"Failed to append invoice with items: {str(e)}")
    
    def append_invoice_with_audit(
        self,
        invoice_data: List,
        line_items_data: List[List],
        validation_result: Dict,
        audit_data: Dict,
        confidence_scores: Dict = None,
        corrections_metadata: Dict = None,
        fingerprint: str = '',
        duplicate_status: str = 'UNIQUE'
    ) -> bool:
        """
        Append invoice with full Tier 2 audit trail and metadata
        
        Args:
            invoice_data: List of values for invoice header (Tier 1 fields only)
            line_items_data: List of lists, each inner list is a line item row
            validation_result: Validation result dict
            audit_data: Audit metadata from AuditLogger
            confidence_scores: Field confidence scores (optional)
            corrections_metadata: Correction metadata (optional)
            fingerprint: Invoice fingerprint for deduplication
            duplicate_status: UNIQUE or DUPLICATE_OVERRIDE
            
        Returns:
            True if successful
        """
        try:
            # Ensure invoice_data has enough slots for all Tier 2 fields
            # Tier 1 has 24 fields, Tier 2 adds 17 more = 41 total
            while len(invoice_data) < len(config.SHEET_COLUMNS):
                invoice_data.append('')
            
            # Update validation fields (Tier 1)
            status_idx = config.SHEET_COLUMNS.index('Validation_Status')
            remarks_idx = config.SHEET_COLUMNS.index('Validation_Remarks')
            
            invoice_data[status_idx] = validation_result['status']
            
            remarks = []
            if validation_result['errors']:
                remarks.append("ERRORS: " + "; ".join(validation_result['errors']))
            if validation_result['warnings']:
                remarks.append("WARNINGS: " + "; ".join(validation_result['warnings']))
            
            invoice_data[remarks_idx] = " | ".join(remarks) if remarks else "All validations passed"
            
            # Update Tier 2 audit fields
            invoice_data[config.SHEET_COLUMNS.index('Upload_Timestamp')] = audit_data.get('Upload_Timestamp', '')
            invoice_data[config.SHEET_COLUMNS.index('Telegram_User_ID')] = audit_data.get('Telegram_User_ID', '')
            invoice_data[config.SHEET_COLUMNS.index('Telegram_Username')] = audit_data.get('Telegram_Username', '')
            invoice_data[config.SHEET_COLUMNS.index('Extraction_Version')] = audit_data.get('Extraction_Version', '')
            invoice_data[config.SHEET_COLUMNS.index('Model_Version')] = audit_data.get('Model_Version', '')
            invoice_data[config.SHEET_COLUMNS.index('Processing_Time_Seconds')] = audit_data.get('Processing_Time_Seconds', 0)
            invoice_data[config.SHEET_COLUMNS.index('Page_Count')] = audit_data.get('Page_Count', 0)
            
            # Update correction fields
            invoice_data[config.SHEET_COLUMNS.index('Has_Corrections')] = audit_data.get('Has_Corrections', 'N')
            
            if corrections_metadata:
                import json
                corrected_fields = ', '.join(corrections_metadata.get('corrected_values', {}).keys())
                invoice_data[config.SHEET_COLUMNS.index('Corrected_Fields')] = corrected_fields
                invoice_data[config.SHEET_COLUMNS.index('Correction_Metadata')] = json.dumps(corrections_metadata)
            else:
                invoice_data[config.SHEET_COLUMNS.index('Corrected_Fields')] = ''
                invoice_data[config.SHEET_COLUMNS.index('Correction_Metadata')] = ''
            
            # Update deduplication fields
            invoice_data[config.SHEET_COLUMNS.index('Invoice_Fingerprint')] = fingerprint
            invoice_data[config.SHEET_COLUMNS.index('Duplicate_Status')] = duplicate_status
            
            # Update confidence scores
            if confidence_scores:
                invoice_data[config.SHEET_COLUMNS.index('Invoice_No_Confidence')] = confidence_scores.get('Invoice_No', 0.0)
                invoice_data[config.SHEET_COLUMNS.index('Invoice_Date_Confidence')] = confidence_scores.get('Invoice_Date', 0.0)
                invoice_data[config.SHEET_COLUMNS.index('Buyer_GSTIN_Confidence')] = confidence_scores.get('Buyer_GSTIN', 0.0)
                invoice_data[config.SHEET_COLUMNS.index('Total_Taxable_Value_Confidence')] = confidence_scores.get('Total_Taxable_Value', 0.0)
                invoice_data[config.SHEET_COLUMNS.index('Total_GST_Confidence')] = confidence_scores.get('Total_GST', 0.0)
            else:
                invoice_data[config.SHEET_COLUMNS.index('Invoice_No_Confidence')] = 0.0
                invoice_data[config.SHEET_COLUMNS.index('Invoice_Date_Confidence')] = 0.0
                invoice_data[config.SHEET_COLUMNS.index('Buyer_GSTIN_Confidence')] = 0.0
                invoice_data[config.SHEET_COLUMNS.index('Total_Taxable_Value_Confidence')] = 0.0
                invoice_data[config.SHEET_COLUMNS.index('Total_GST_Confidence')] = 0.0
            
            # ============================================
            # SAFEGUARD: Convert all values to strings
            # ============================================
            invoice_data = [str(val) if val not in [None, 'None', 'null'] else '' for val in invoice_data]
            
            # ============================================
            # INVOICE HEADER - Use batch update (not append_row)
            # ============================================
            all_data = self.worksheet.get_all_values()
            next_row = len(all_data) + 1
            if next_row < 2:
                next_row = 2
            
            # Calculate end column based on data length (max 41 for Tier 2)
            num_cols = min(len(invoice_data), 41)
            end_col = chr(65 + num_cols - 1) if num_cols <= 26 else 'A' + chr(65 + num_cols - 27)
            
            # For Tier 2, we need columns up to AO (index 40)
            # A=0, Z=25, AA=26, ..., AO=40
            if num_cols > 26:
                first_letter = chr(65 + (num_cols - 1) // 26 - 1)  # A for 27-52
                second_letter = chr(65 + (num_cols - 1) % 26)
                end_col = first_letter + second_letter
            
            range_str = f'A{next_row}:{end_col}{next_row}'
            self.worksheet.update(values=[invoice_data[:num_cols]], range_name=range_str, value_input_option='USER_ENTERED')
            
            print(f"[OK] Tier 2 invoice written to row {next_row}, columns A-{end_col}")
            
            # ============================================
            # LINE ITEMS - Use batch update
            # ============================================
            if line_items_data:
                all_line_data = self.line_items_worksheet.get_all_values()
                next_line_row = len(all_line_data) + 1
                if next_line_row < 2:
                    next_line_row = 2
                
                # Prepare all line items
                rows_to_write = []
                for item_row in line_items_data:
                    # Ensure exactly 19 columns
                    while len(item_row) < 19:
                        item_row.append('')
                    item_row = item_row[:19]
                    item_row = [str(val) if val not in [None, 'None', 'null'] else '' for val in item_row]
                    rows_to_write.append(item_row)
                
                if rows_to_write:
                    end_row = next_line_row + len(rows_to_write) - 1
                    range_str = f'A{next_line_row}:S{end_row}'
                    self.line_items_worksheet.update(values=rows_to_write, range_name=range_str, value_input_option='USER_ENTERED')
                    print(f"[OK] Wrote {len(rows_to_write)} line items to rows {next_line_row}-{end_row}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to append invoice with audit trail: {str(e)}")
            raise Exception(f"Failed to append invoice with audit trail: {str(e)}")
    
    def check_duplicate_advanced(self, fingerprint: str) -> tuple:
        """
        Check for duplicate invoice using fingerprint
        
        Args:
            fingerprint: Invoice fingerprint hash
            
        Returns:
            Tuple of (is_duplicate: bool, existing_invoice_data: Dict or None)
        """
        try:
            # Check if Invoice_Fingerprint column exists
            headers = self.get_sheet_headers()
            if 'Invoice_Fingerprint' not in headers:
                # Fall back to simple duplicate check if Tier 2 not set up
                return (False, None)
            
            fingerprint_col_idx = headers.index('Invoice_Fingerprint') + 1  # 1-indexed
            
            # Get all fingerprints
            fingerprints = self.worksheet.col_values(fingerprint_col_idx)
            
            # Check if fingerprint exists
            if fingerprint in fingerprints:
                # Get the row index (1-indexed, skip header)
                row_idx = fingerprints.index(fingerprint) + 1
                
                # Get the entire row
                row_data = self.worksheet.row_values(row_idx)
                
                # Convert to dictionary
                existing_invoice = {}
                for i, header in enumerate(headers):
                    if i < len(row_data):
                        existing_invoice[header] = row_data[i]
                    else:
                        existing_invoice[header] = ''
                
                return (True, existing_invoice)
            
            return (False, None)
            
        except Exception as e:
            print(f"Warning: Could not check for duplicates using fingerprint: {str(e)}")
            return (False, None)
    
    # ═══════════════════════════════════════════════════════════════════
    # TIER 3 METHODS - Export and Master Data Support
    # ═══════════════════════════════════════════════════════════════════
    
    def get_invoices_by_period(self, month: int, year: int, status_filter: List[str] = None) -> List[Dict]:
        """
        Fetch invoices for specified period with optional status filter
        
        Args:
            month: Month number (1-12)
            year: Year (e.g., 2026)
            status_filter: List of validation statuses to include (e.g., ['OK', 'WARNING'])
                          If None, includes all invoices
            
        Returns:
            List of invoice dictionaries
        """
        from datetime import datetime
        
        try:
            # Get all data from worksheet
            headers = self.get_sheet_headers()
            all_rows = self.worksheet.get_all_values()
            
            if len(all_rows) <= 1:  # Only header or empty
                return []
            
            # Find which row contains the headers
            header_row_idx = 0
            for idx, row in enumerate(all_rows):
                if row and any(header in row for header in ['Invoice_No', 'Invoice_Date']):
                    header_row_idx = idx
                    break
            
            # Find column indices
            invoice_date_idx = headers.index('Invoice_Date') if 'Invoice_Date' in headers else -1
            validation_status_idx = headers.index('Validation_Status') if 'Validation_Status' in headers else -1
            
            if invoice_date_idx == -1:
                print("Warning: Invoice_Date column not found")
                return []
            
            invoices = []
            
            # Skip rows up to and including header row
            for row in all_rows[header_row_idx + 1:]:
                if not row or len(row) <= invoice_date_idx:
                    continue
                
                invoice_date_str = row[invoice_date_idx].strip()
                if not invoice_date_str:
                    continue
                
                try:
                    # Parse DD/MM/YYYY format
                    invoice_date = datetime.strptime(invoice_date_str, '%d/%m/%Y')
                    
                    # Check if matches period
                    if invoice_date.month == month and invoice_date.year == year:
                        # Check status filter
                        if status_filter and validation_status_idx != -1:
                            if len(row) > validation_status_idx:
                                status = row[validation_status_idx].strip().upper()
                                if status not in [s.upper() for s in status_filter]:
                                    continue
                        
                        # Convert row to dictionary
                        invoice_dict = {}
                        for i, header in enumerate(headers):
                            if i < len(row):
                                invoice_dict[header] = row[i]
                            else:
                                invoice_dict[header] = ''
                        
                        invoices.append(invoice_dict)
                
                except ValueError:
                    # Skip rows with invalid date format
                    continue
            
            return invoices
            
        except Exception as e:
            print(f"Error fetching invoices by period: {str(e)}")
            return []
    
    def get_line_items_by_invoice_numbers(self, invoice_numbers: List[str]) -> Dict[str, List[Dict]]:
        """
        Fetch line items for multiple invoices efficiently
        
        Args:
            invoice_numbers: List of invoice numbers
            
        Returns:
            Dictionary mapping invoice_no to list of line item dictionaries
        """
        try:
            # Get all data from line items worksheet
            headers = self.line_items_worksheet.row_values(1)
            all_rows = self.line_items_worksheet.get_all_values()
            
            if len(all_rows) <= 1:  # Only header or empty
                return {}
            
            invoice_no_idx = headers.index('Invoice_No') if 'Invoice_No' in headers else 0
            
            # Create uppercase set for faster lookup
            invoice_numbers_upper = {inv_no.upper() for inv_no in invoice_numbers}
            
            line_items_map = {}
            
            # Skip header row
            for row in all_rows[1:]:
                if not row or len(row) <= invoice_no_idx:
                    continue
                
                invoice_no = row[invoice_no_idx].strip()
                
                if invoice_no.upper() in invoice_numbers_upper:
                    # Convert row to dictionary
                    item_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(row):
                            item_dict[header] = row[i]
                        else:
                            item_dict[header] = ''
                    
                    # Add to map
                    if invoice_no not in line_items_map:
                        line_items_map[invoice_no] = []
                    line_items_map[invoice_no].append(item_dict)
            
            return line_items_map
            
        except Exception as e:
            print(f"Error fetching line items: {str(e)}")
            return {}
    
    def get_customer_by_gstin(self, gstin: str) -> Dict:
        """
        Lookup customer master by GSTIN
        
        Args:
            gstin: Customer GSTIN to lookup
            
        Returns:
            Customer data dictionary or None if not found
        """
        try:
            # Try to open customer master sheet
            try:
                customer_sheet = self.spreadsheet.worksheet(config.CUSTOMER_MASTER_SHEET)
            except:
                # Sheet doesn't exist yet
                return None
            
            headers = customer_sheet.row_values(1)
            all_rows = customer_sheet.get_all_values()
            
            if len(all_rows) <= 1:
                return None
            
            gstin_idx = headers.index('GSTIN') if 'GSTIN' in headers else 0
            
            # Search for GSTIN
            for row in all_rows[1:]:
                if row and len(row) > gstin_idx and row[gstin_idx].strip().upper() == gstin.upper():
                    # Found - convert to dictionary
                    customer_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(row):
                            customer_dict[header] = row[i]
                        else:
                            customer_dict[header] = ''
                    return customer_dict
            
            return None
            
        except Exception as e:
            print(f"Warning: Could not lookup customer: {str(e)}")
            return None
    
    def update_customer_master(self, gstin: str, customer_data: Dict) -> bool:
        """
        Add or update customer master entry
        
        Args:
            gstin: Customer GSTIN (unique key)
            customer_data: Dictionary with customer fields
            
        Returns:
            True if successful
        """
        from datetime import datetime
        
        try:
            # Try to open customer master sheet, create if doesn't exist
            try:
                customer_sheet = self.spreadsheet.worksheet(config.CUSTOMER_MASTER_SHEET)
                headers = customer_sheet.row_values(1)
                
                # If sheet exists but has no headers, add them
                if not headers:
                    customer_sheet.append_row(config.CUSTOMER_MASTER_COLUMNS)
                    headers = config.CUSTOMER_MASTER_COLUMNS
                    
            except:
                # Sheet doesn't exist - create it
                customer_sheet = self.spreadsheet.add_worksheet(
                    title=config.CUSTOMER_MASTER_SHEET,
                    rows=1000,
                    cols=len(config.CUSTOMER_MASTER_COLUMNS)
                )
                customer_sheet.append_row(config.CUSTOMER_MASTER_COLUMNS)
                headers = config.CUSTOMER_MASTER_COLUMNS
            
            # Check if GSTIN already exists
            existing = self.get_customer_by_gstin(gstin)
            
            if existing:
                # Update existing record - find the row and update
                all_rows = customer_sheet.get_all_values()
                gstin_idx = headers.index('GSTIN')
                usage_count_idx = headers.index('Usage_Count') if 'Usage_Count' in headers else -1
                last_updated_idx = headers.index('Last_Updated') if 'Last_Updated' in headers else -1
                
                for row_idx, row in enumerate(all_rows[1:], start=2):  # Start from row 2 (skip header)
                    if row and len(row) > gstin_idx and row[gstin_idx].strip().upper() == gstin.upper():
                        # Found the row - increment usage count
                        if usage_count_idx != -1 and last_updated_idx != -1:
                            current_usage = int(row[usage_count_idx]) if row[usage_count_idx].isdigit() else 0
                            customer_sheet.update_cell(row_idx, usage_count_idx + 1, current_usage + 1)
                            customer_sheet.update_cell(row_idx, last_updated_idx + 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        return True
            
            # Add new record
            row_data = []
            for col in config.CUSTOMER_MASTER_COLUMNS:
                if col in customer_data:
                    row_data.append(customer_data[col])
                else:
                    row_data.append('')
            
            customer_sheet.append_row(row_data)
            return True
            
        except Exception as e:
            print(f"Warning: Could not update customer master: {str(e)}")
            return False
    
    def get_hsn_by_code(self, hsn_code: str) -> Dict:
        """
        Lookup HSN master by code
        
        Args:
            hsn_code: HSN/SAC code to lookup
            
        Returns:
            HSN data dictionary or None if not found
        """
        try:
            # Try to open HSN master sheet
            try:
                hsn_sheet = self.spreadsheet.worksheet(config.HSN_MASTER_SHEET)
            except:
                return None
            
            headers = hsn_sheet.row_values(1)
            all_rows = hsn_sheet.get_all_values()
            
            if len(all_rows) <= 1:
                return None
            
            hsn_idx = headers.index('HSN_SAC_Code') if 'HSN_SAC_Code' in headers else 0
            
            # Search for HSN code
            for row in all_rows[1:]:
                if row and len(row) > hsn_idx and row[hsn_idx].strip().upper() == hsn_code.upper():
                    # Found - convert to dictionary
                    hsn_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(row):
                            hsn_dict[header] = row[i]
                        else:
                            hsn_dict[header] = ''
                    return hsn_dict
            
            return None
            
        except Exception as e:
            print(f"Warning: Could not lookup HSN: {str(e)}")
            return None
    
    def update_hsn_master(self, hsn_code: str, hsn_data: Dict) -> bool:
        """
        Add or update HSN master entry
        
        Args:
            hsn_code: HSN/SAC code (unique key)
            hsn_data: Dictionary with HSN fields
            
        Returns:
            True if successful
        """
        from datetime import datetime
        
        try:
            # Try to open HSN master sheet, create if doesn't exist
            try:
                hsn_sheet = self.spreadsheet.worksheet(config.HSN_MASTER_SHEET)
                headers = hsn_sheet.row_values(1)
                
                if not headers:
                    hsn_sheet.append_row(config.HSN_MASTER_COLUMNS)
                    headers = config.HSN_MASTER_COLUMNS
                    
            except:
                # Sheet doesn't exist - create it
                hsn_sheet = self.spreadsheet.add_worksheet(
                    title=config.HSN_MASTER_SHEET,
                    rows=1000,
                    cols=len(config.HSN_MASTER_COLUMNS)
                )
                hsn_sheet.append_row(config.HSN_MASTER_COLUMNS)
                headers = config.HSN_MASTER_COLUMNS
            
            # Check if HSN already exists
            existing = self.get_hsn_by_code(hsn_code)
            
            if existing:
                # Update existing record
                all_rows = hsn_sheet.get_all_values()
                hsn_idx = headers.index('HSN_SAC_Code')
                usage_count_idx = headers.index('Usage_Count') if 'Usage_Count' in headers else -1
                last_updated_idx = headers.index('Last_Updated') if 'Last_Updated' in headers else -1
                
                for row_idx, row in enumerate(all_rows[1:], start=2):
                    if row and len(row) > hsn_idx and row[hsn_idx].strip().upper() == hsn_code.upper():
                        if usage_count_idx != -1 and last_updated_idx != -1:
                            current_usage = int(row[usage_count_idx]) if row[usage_count_idx].isdigit() else 0
                            hsn_sheet.update_cell(row_idx, usage_count_idx + 1, current_usage + 1)
                            hsn_sheet.update_cell(row_idx, last_updated_idx + 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        return True
            
            # Add new record
            row_data = []
            for col in config.HSN_MASTER_COLUMNS:
                if col in hsn_data:
                    row_data.append(hsn_data[col])
                else:
                    row_data.append('')
            
            hsn_sheet.append_row(row_data)
            return True
            
        except Exception as e:
            print(f"Warning: Could not update HSN master: {str(e)}")
            return False
    
    def log_duplicate_attempt(self, user_id: str, invoice_no: str, action_taken: str = 'REJECTED') -> bool:
        """
        Log duplicate invoice attempt
        
        Args:
            user_id: Telegram user ID
            invoice_no: Invoice number attempted
            action_taken: Action taken (e.g., 'REJECTED', 'OVERRIDE')
            
        Returns:
            True if successful
        """
        from datetime import datetime
        
        try:
            # Try to open duplicate attempts sheet, create if doesn't exist
            try:
                dup_sheet = self.spreadsheet.worksheet(config.DUPLICATE_ATTEMPTS_SHEET)
                headers = dup_sheet.row_values(1)
                
                if not headers:
                    dup_sheet.append_row(config.DUPLICATE_ATTEMPTS_COLUMNS)
                    
            except:
                # Sheet doesn't exist - create it
                dup_sheet = self.spreadsheet.add_worksheet(
                    title=config.DUPLICATE_ATTEMPTS_SHEET,
                    rows=1000,
                    cols=len(config.DUPLICATE_ATTEMPTS_COLUMNS)
                )
                dup_sheet.append_row(config.DUPLICATE_ATTEMPTS_COLUMNS)
            
            # Append log entry
            log_row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                str(user_id),
                invoice_no,
                action_taken
            ]
            dup_sheet.append_row(log_row)
            return True
            
        except Exception as e:
            print(f"Warning: Could not log duplicate attempt: {str(e)}")
            return False


if __name__ == "__main__":
    # Test Google Sheets connection
    try:
        print("Testing Google Sheets connection...")
        sheets = SheetsManager()
        
        print("✓ Connected to Google Sheets successfully")
        
        # Validate structure
        if sheets.validate_sheet_structure():
            print("✓ Sheet structure is valid")
        else:
            print("✗ Sheet structure validation failed")
        
        # Get last invoice
        last_invoice = sheets.get_last_invoice_no()
        print(f"Last invoice in sheet: {last_invoice if last_invoice else 'None'}")
        
    except Exception as e:
        print(f"✗ Google Sheets test failed: {str(e)}")
