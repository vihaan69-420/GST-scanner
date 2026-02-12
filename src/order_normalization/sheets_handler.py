"""
Order Sheets Handler
Handles Google Sheets operations for order data (additive only)
"""
from datetime import datetime
from typing import Dict, List
from sheets.sheets_manager import SheetsManager
import config


class OrderSheetsHandler:
    """Manages Google Sheets operations for orders (Epic 2)"""
    
    def __init__(self, sheet_id: str = None):
        """Initialize handler with existing SheetsManager connection

        Args:
            sheet_id: Optional Google Sheet ID for per-tenant routing (Epic 3).
                      When None, falls back to shared sheet via SheetsManager default.
        """
        # Lazy initialization - sheets_manager created on first use
        self._sheet_id = sheet_id
        self.sheets_manager = None
        self.spreadsheet = None
        self._tabs_initialized = False
        
        # Note: Tabs are initialized lazily on first use to avoid slow bot startup
    
    def _ensure_tabs_initialized(self):
        """Ensure tabs are initialized (lazy initialization)"""
        if self._tabs_initialized:
            return
        
        # Initialize SheetsManager if not already done
        if self.sheets_manager is None:
            self.sheets_manager = SheetsManager(sheet_id=self._sheet_id)
            self.spreadsheet = self.sheets_manager.spreadsheet
        
        self.initialize_order_tabs()
        self._tabs_initialized = True
    
    def initialize_order_tabs(self):
        """
        Create order-related tabs if they don't exist (additive only)
        
        Tabs created:
        - Orders: Order summary data
        - Order_Line_Items: Line item details
        - Customer_Details: Customer master (Epic 2 specific)
        """
        required_tabs = {
            config.ORDER_SUMMARY_SHEET: [
                'Order_ID', 'Customer_Name', 'Order_Date', 'Status',
                'Total_Items', 'Total_Quantity', 'Subtotal', 'Unmatched_Count',
                'Page_Count', 'Created_By', 'Processed_At'
            ],
            config.ORDER_LINE_ITEMS_SHEET: [
                'Order_ID', 'Serial_No', 'Part_Name', 'Part_Number',
                'Model', 'Color', 'Quantity', 'Rate', 'Line_Total', 'Match_Confidence'
            ],
            config.ORDER_CUSTOMER_DETAILS_SHEET: [
                'Customer_ID', 'Customer_Name', 'Contact',
                'Last_Order_Date', 'Total_Orders'
            ]
        }
        
        # Get existing tabs
        existing_tabs = [ws.title for ws in self.spreadsheet.worksheets()]
        
        # Create missing tabs
        for tab_name, headers in required_tabs.items():
            if tab_name not in existing_tabs:
                try:
                    # Create new tab
                    worksheet = self.spreadsheet.add_worksheet(
                        title=tab_name,
                        rows=1000,
                        cols=len(headers)
                    )
                    # Write headers
                    worksheet.append_row(headers, value_input_option='USER_ENTERED')
                    print(f"[ORDER_SHEETS] Created tab: {tab_name}")
                except Exception as e:
                    print(f"[ERROR] Failed to create tab {tab_name}: {e}")
        
        print("[ORDER_SHEETS] Order tabs initialized")
    
    def append_order_summary(self, clean_invoice: Dict, session_metadata: Dict):
        """
        Append one row to Orders tab
        
        Args:
            clean_invoice: Clean invoice dictionary
            session_metadata: Session metadata (user_id, page_count, etc.)
        """
        self._ensure_tabs_initialized()  # Lazy initialization
        try:
            orders_sheet = self.spreadsheet.worksheet(config.ORDER_SUMMARY_SHEET)
            
            row_data = [
                clean_invoice['order_id'],
                clean_invoice.get('customer_name', 'N/A'),
                clean_invoice['order_date'],
                'completed',
                clean_invoice['total_items'],
                clean_invoice['total_quantity'],
                clean_invoice['subtotal'],
                clean_invoice['unmatched_count'],
                session_metadata.get('page_count', 0),
                session_metadata.get('created_by', 'unknown'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            orders_sheet.append_row(row_data, value_input_option='USER_ENTERED')
            print(f"[ORDER_SHEETS] Appended order summary: {clean_invoice['order_id']}")
            
        except Exception as e:
            print(f"[ERROR] Failed to append order summary: {e}")
            raise
    
    def append_order_line_items(self, clean_invoice: Dict):
        """
        Append multiple rows to Order_Line_Items tab
        
        Args:
            clean_invoice: Clean invoice dictionary with line_items
        """
        self._ensure_tabs_initialized()  # Lazy initialization
        try:
            line_items_sheet = self.spreadsheet.worksheet(config.ORDER_LINE_ITEMS_SHEET)
            
            rows_to_write = []
            for item in clean_invoice['line_items']:
                row_data = [
                    clean_invoice['order_id'],
                    item['serial_no'],
                    item['part_name'],
                    item['part_number'],
                    item.get('model', ''),
                    item.get('color', ''),
                    item['quantity'],
                    item['rate'],
                    item['line_total'],
                    item.get('match_confidence', 0.0)
                ]
                rows_to_write.append(row_data)
            
            # Batch write for efficiency
            if rows_to_write:
                # Use append_rows for batch insert
                for row in rows_to_write:
                    line_items_sheet.append_row(row, value_input_option='USER_ENTERED')
                
                print(f"[ORDER_SHEETS] Appended {len(rows_to_write)} line items")
            
        except Exception as e:
            print(f"[ERROR] Failed to append line items: {e}")
            raise
    
    def update_customer_details(self, customer_name: str, order_date: str):
        """
        Update or create customer record
        
        Args:
            customer_name: Customer name
            order_date: Order date string
        """
        self._ensure_tabs_initialized()  # Lazy initialization
        try:
            customer_sheet = self.spreadsheet.worksheet(config.ORDER_CUSTOMER_DETAILS_SHEET)
            
            # Get all customers
            all_records = customer_sheet.get_all_records()
            
            # Check if customer exists
            existing = None
            existing_row_idx = None
            
            for idx, record in enumerate(all_records):
                if record.get('Customer_Name', '').strip().upper() == customer_name.strip().upper():
                    existing = record
                    existing_row_idx = idx + 2  # +2 for header and 0-indexing
                    break
            
            if existing:
                # Update existing customer
                current_orders = int(existing.get('Total_Orders', 0))
                customer_sheet.update_cell(existing_row_idx, 4, order_date)  # Last_Order_Date
                customer_sheet.update_cell(existing_row_idx, 5, current_orders + 1)  # Total_Orders
                print(f"[ORDER_SHEETS] Updated customer: {customer_name}")
            else:
                # Create new customer
                customer_id = f"CUST_{len(all_records) + 1:04d}"
                customer_sheet.append_row([
                    customer_id,
                    customer_name,
                    '',  # Contact (placeholder)
                    order_date,
                    1  # Total_Orders
                ], value_input_option='USER_ENTERED')
                print(f"[ORDER_SHEETS] Created new customer: {customer_name}")
        
        except Exception as e:
            print(f"[ERROR] Failed to update customer details: {e}")
            # Non-critical, don't raise
