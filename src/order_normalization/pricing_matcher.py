"""
Pricing Matcher
Matches normalized order line items with pricing sheet using fuzzy matching
"""
import os
from typing import Dict, List
from difflib import SequenceMatcher
import config


class PricingMatcher:
    """Matches order line items with pricing data"""
    
    def __init__(self):
        """Initialize matcher and load pricing sheet"""
        self.pricing_data = []
        self.pricing_source = config.PRICING_SHEET_SOURCE
        
        # Load pricing sheet based on configuration
        if self.pricing_source == 'local_file':
            self._load_from_excel(config.PRICING_SHEET_PATH)
        elif self.pricing_source == 'google_sheet':
            self._load_from_google_sheet()
        else:
            print(f"[WARNING] Unknown pricing source: {self.pricing_source}")
    
    def _load_from_excel(self, file_path: str):
        """
        Load pricing from Excel file
        
        Args:
            file_path: Path to Excel file (relative or absolute)
        """
        try:
            import openpyxl
            
            # Resolve path
            if not os.path.isabs(file_path):
                file_path = os.path.join(config.PROJECT_ROOT, file_path)
            
            if not os.path.exists(file_path):
                print(f"[WARNING] Pricing file not found: {file_path}")
                print(f"[WARNING] Pricing matching will be disabled")
                return
            
            workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            sheet = workbook.active
            
            # Read headers from first row
            headers = []
            for cell in sheet[1]:
                headers.append(cell.value)
            
            # Read data rows
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if not any(row):  # Skip empty rows
                    continue
                
                item = dict(zip(headers, row))
                self.pricing_data.append(item)
            
            workbook.close()
            
            print(f"[PRICING] Loaded {len(self.pricing_data)} items from {os.path.basename(file_path)}")
            
        except ImportError:
            print("[ERROR] openpyxl not installed. Install with: pip install openpyxl")
        except Exception as e:
            print(f"[ERROR] Failed to load pricing sheet: {e}")
    
    def _load_from_google_sheet(self):
        """Load pricing from Google Sheet"""
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            
            # Setup Google Sheets connection
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Get credentials path
            creds_path = config.get_credentials_path()
            
            if creds_path:
                # Use service account credentials
                creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
                client = gspread.authorize(creds)
            else:
                # Use Application Default Credentials
                import google.auth
                credentials, project = google.auth.default(scopes=scope)
                client = gspread.authorize(credentials)
            
            # Open the pricing sheet
            sheet = client.open_by_key(config.PRICING_SHEET_ID)
            worksheet = sheet.worksheet(config.PRICING_SHEET_NAME)
            
            # Get all data
            all_data = worksheet.get_all_values()
            
            if not all_data:
                print("[WARNING] Pricing sheet is empty")
                return
            
            # Parse headers (row 0)
            headers = all_data[0]
            
            print(f"[PRICING] Loading from Google Sheet: {config.PRICING_SHEET_ID}")
            print(f"[PRICING] Worksheet: {config.PRICING_SHEET_NAME}")
            print(f"[PRICING] Headers: {headers[:10]}")  # Debug: show first 10 headers
            
            # Column indices based on actual sheet structure
            # Try to find column indices dynamically
            part_no_col = 0
            description_col = 1
            price_col = 2
            
            # Try to find price column by header name
            for idx, header in enumerate(headers):
                header_lower = str(header).lower().strip()
                if 'mrp' in header_lower or 'price' in header_lower:
                    price_col = idx
                    print(f"[PRICING] Found price column at index {idx}: {header}")
                    break
            
            std_pkg_col = 4
            master_pkg_col = 5
            
            # Parse data rows (skip header)
            for row in all_data[1:]:
                if not row or len(row) <= price_col:
                    continue
                
                part_no = row[part_no_col].strip() if row[part_no_col] else ''
                description = row[description_col].strip() if row[description_col] else ''
                price_str = row[price_col].strip() if row[price_col] else ''
                
                # Only include rows with part number and price
                if not part_no or not price_str:
                    continue
                
                # Parse price (remove commas, convert to float)
                try:
                    price = float(price_str.replace(',', ''))
                    if price <= 0:  # Skip zero or negative prices
                        continue
                except (ValueError, AttributeError):
                    continue
                
                # Build pricing item with correct field names
                pricing_item = {
                    'Part Number': part_no,
                    'Part Name': description,
                    'Description': description,
                    'Price': price,
                    'Rate': price,
                    'Unit Price': price,
                    'MRP': price,  # Add MRP field name
                    'STD_PKG': row[std_pkg_col].strip() if len(row) > std_pkg_col else '',
                    'MASTER_PKG': row[master_pkg_col].strip() if len(row) > master_pkg_col else ''
                }
                
                self.pricing_data.append(pricing_item)
            
            print(f"[PRICING] Loaded {len(self.pricing_data)} products from Google Sheet")
            
        except ImportError as e:
            print(f"[ERROR] Missing required library: {e}")
            print("[ERROR] Install with: pip install gspread oauth2client")
        except Exception as e:
            print(f"[ERROR] Failed to load pricing from Google Sheet: {e}")
            import traceback
            traceback.print_exc()
    
    def match_line_item(self, line: Dict) -> Dict:
        """
        Match a line item with pricing sheet using fuzzy name matching
        
        Args:
            line: Normalized line item
            
        Returns:
            Match result dictionary:
            {
                'matched': bool,
                'matched_part_number': str,
                'matched_part_name': str,
                'unit_price': float,
                'match_confidence': float,
                'match_method': str,
                'pricing_source': str
            }
        """
        if not self.pricing_data:
            # No pricing data available
            return {
                'matched': False,
                'match_confidence': 0.0,
                'reason': 'No pricing data loaded',
                'unit_price': 0.0
            }
        
        # Build search string from normalized line
        # For Google Sheet data, descriptions often include part name, model, and color
        part_name = line.get('part_name', '').lower().strip()
        model = line.get('model', '').lower().strip()
        color = line.get('color', '').lower().strip()
        brand = line.get('brand', '').lower().strip()
        
        # Build comprehensive search string
        search_parts = [part_name]
        if model:
            search_parts.append(model)
        if color:
            search_parts.append(color)
        if brand:
            search_parts.append(brand)
        
        search_string = ' '.join(search_parts)
        
        # Fuzzy matching
        best_match = None
        best_score = 0.0
        threshold = 0.65  # 65% similarity required (lowered from 70% for better matches)
        
        for pricing_item in self.pricing_data:
            # Build pricing string from description
            description = str(pricing_item.get('Description', '') or pricing_item.get('Part Name', '') or '').lower().strip()
            
            if not description:
                continue
            
            # Calculate similarity score
            score = SequenceMatcher(None, search_string, description).ratio()
            
            # Also try partial matches (if search string is contained in description)
            if search_string in description:
                score = max(score, 0.75)  # Boost score for substring matches
            
            if score > best_score:
                best_score = score
                best_match = pricing_item
        
        if best_score >= threshold:
            # Match found
            part_number = str(best_match.get('Part Number', '') or best_match.get('Code', '') or 'N/A')
            part_name = str(best_match.get('Part Name', '') or best_match.get('Description', '') or '')
            
            # Get price (try multiple column names, including MRP)
            price = 0.0
            for price_col in ['Price', 'Rate', 'Unit Price', 'MRP', 'Cost', 'MRP (Incl. Of All Taxes)']:
                if price_col in best_match and best_match[price_col]:
                    try:
                        price_val = best_match[price_col]
                        # Handle both numeric and string prices
                        if isinstance(price_val, (int, float)):
                            price = float(price_val)
                        else:
                            price = float(str(price_val).replace(',', '').strip())
                        
                        if price > 0:  # Only accept positive prices
                            break
                    except (ValueError, TypeError, AttributeError):
                        continue
            
            return {
                'matched': True,
                'matched_part_number': part_number,
                'matched_part_name': part_name,
                'unit_price': price,
                'match_confidence': best_score,
                'match_method': 'fuzzy_name',
                'pricing_source': 'google_sheet' if self.pricing_source == 'google_sheet' else os.path.basename(config.PRICING_SHEET_PATH)
            }
        else:
            # No match above threshold
            return {
                'matched': False,
                'match_confidence': best_score,
                'reason': f'No match above {threshold:.0%} threshold (best: {best_score:.0%})',
                'unit_price': 0.0
            }
    
    def match_all_lines(self, unique_lines: List[Dict]) -> List[Dict]:
        """
        Match all unique lines with pricing
        
        Args:
            unique_lines: List of unique normalized line items
            
        Returns:
            List of lines with pricing match results added
        """
        matched_lines = []
        
        for line in unique_lines:
            match_result = self.match_line_item(line)
            
            # Merge match result into line
            line.update(match_result)
            matched_lines.append(line)
            
            if match_result['matched']:
                print(f"[PRICING] Matched: {line['part_name']} -> {match_result['matched_part_name']} "
                      f"(confidence: {match_result['match_confidence']:.0%}, price: ₹{match_result['unit_price']:.2f})")
            else:
                print(f"[PRICING] No match: {line['part_name']} (reason: {match_result.get('reason', 'unknown')})")
        
        return matched_lines
