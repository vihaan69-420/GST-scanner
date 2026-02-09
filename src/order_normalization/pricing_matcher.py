"""
Pricing Matcher
Matches normalized order line items with pricing sheet using word-boundary matching
"""
import os
import re
from typing import Dict, List
from difflib import SequenceMatcher
import config


class PricingMatcher:
    """Matches order line items with pricing data"""
    
    def __init__(self):
        """Initialize matcher (lazy loading - pricing loaded on first use)"""
        self.pricing_data = []
        self.pricing_source = config.PRICING_SHEET_SOURCE
        self._pricing_loaded = False
    
    def _ensure_pricing_loaded(self):
        """Load pricing sheet if not already loaded (lazy initialization)"""
        if self._pricing_loaded:
            return
        
        # Load pricing sheet based on configuration
        if self.pricing_source == 'local_file':
            self._load_from_excel(config.PRICING_SHEET_PATH)
        elif self.pricing_source == 'google_sheet':
            self._load_from_google_sheet()
        else:
            print(f"[WARNING] Unknown pricing source: {self.pricing_source}")
        
        self._pricing_loaded = True
    
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
            part_no_col = 0
            description_col = 1
            
            # Find price column: look for actual numeric data, not just header
            # The MRP header may span merged cells, so the actual price data
            # could be in the column AFTER the header column
            price_col = None
            
            # First, find the MRP header column
            mrp_header_col = None
            for idx, header in enumerate(headers):
                header_lower = str(header).lower().strip()
                if 'mrp' in header_lower or 'price' in header_lower:
                    mrp_header_col = idx
                    print(f"[PRICING] Found MRP header at column {idx}: '{header}'")
                    break
            
            # Now find where the actual price DATA lives by checking data rows
            if mrp_header_col is not None:
                # Check columns at and after the header for actual numeric data
                for check_col in [mrp_header_col, mrp_header_col + 1, mrp_header_col + 2]:
                    values_found = 0
                    for row in all_data[1:min(50, len(all_data))]:
                        if len(row) > check_col and row[check_col]:
                            val = row[check_col].strip().replace(',', '')
                            try:
                                float(val)
                                values_found += 1
                            except (ValueError, AttributeError):
                                pass
                    if values_found >= 3:
                        price_col = check_col
                        print(f"[PRICING] Actual price data found in column {check_col} ({values_found} numeric values)")
                        break
            
            if price_col is None:
                # Fallback: scan all columns for numeric data
                for check_col in range(2, min(8, len(headers))):
                    values_found = 0
                    for row in all_data[1:min(50, len(all_data))]:
                        if len(row) > check_col and row[check_col]:
                            val = row[check_col].strip().replace(',', '')
                            try:
                                float(val)
                                values_found += 1
                            except (ValueError, AttributeError):
                                pass
                    if values_found >= 3:
                        price_col = check_col
                        print(f"[PRICING] Fallback: price data found in column {check_col}")
                        break
            
            if price_col is None:
                print("[WARNING] Could not find price column in pricing sheet!")
                return
            
            # Determine STD_PKG and MASTER_PKG columns (after price)
            std_pkg_col = price_col + 1
            master_pkg_col = price_col + 2
            
            # Parse data rows (skip header)
            for row in all_data[1:]:
                if not row or len(row) <= price_col:
                    continue
                
                part_no = row[part_no_col].strip() if row[part_no_col] else ''
                description = row[description_col].strip() if len(row) > description_col and row[description_col] else ''
                price_str = row[price_col].strip() if len(row) > price_col and row[price_col] else ''
                
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
                    'MRP': price,
                    'STD_PKG': row[std_pkg_col].strip() if len(row) > std_pkg_col and row[std_pkg_col] else '',
                    'MASTER_PKG': row[master_pkg_col].strip() if len(row) > master_pkg_col and row[master_pkg_col] else ''
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
    
    def _word_in_text(self, word: str, text: str) -> bool:
        """
        Check if word appears as a WHOLE WORD in text (not substring).
        
        This prevents false matches like:
        - "pass" matching "passion" 
        - "old" matching "golden"
        - "110" matching "1100"
        
        Uses regex word boundaries for accurate matching.
        """
        if not word or not text:
            return False
        escaped = re.escape(word)
        return bool(re.search(r'(?:^|[\s\-\(/])' + escaped + r'(?:$|[\s\-\)/,])', text))
    
    def _count_word_matches(self, words: List[str], text: str) -> int:
        """Count how many words from the list appear as whole words in text"""
        return sum(1 for w in words if self._word_in_text(w, text))
    
    def match_line_item(self, line: Dict) -> Dict:
        """
        Match a line item with pricing sheet using word-boundary matching.
        
        The pricing sheet descriptions are long-form like:
            "Head Light Visor Fit For Splendor Plus BS7 (2023) Black With Blue Sticker"
        While our extracted items are short-form like:
            part_name="Visor", model="Splendor", color="Black"
        
        CRITICAL: Uses word-boundary matching to prevent false substring matches.
        """
        self._ensure_pricing_loaded()
        
        if not self.pricing_data:
            return {
                'matched': False,
                'match_confidence': 0.0,
                'reason': 'No pricing data loaded',
                'unit_price': 0.0
            }
        
        part_name = line.get('part_name', '').lower().strip()
        model = line.get('model', '').lower().strip()
        color = line.get('color', '').lower().strip()
        brand = line.get('brand', '').lower().strip()
        
        # Normalize common abbreviations for matching
        model_normalized = self._normalize_for_matching(model)
        part_normalized = self._normalize_for_matching(part_name)
        color_normalized = self._normalize_for_matching(color)
        
        # Extract significant words for matching
        part_words = [w for w in part_normalized.split() if len(w) > 1]
        model_words = [w for w in model_normalized.split() if len(w) > 1]
        color_parts = [c.strip() for c in color_normalized.replace('/', ' ').replace(',', ' ').split() if len(c.strip()) > 1]
        
        best_match = None
        best_score = 0.0
        threshold = 0.65  # Minimum threshold for accepting a match
        
        for pricing_item in self.pricing_data:
            description = str(pricing_item.get('Description', '') or pricing_item.get('Part Name', '') or '').lower().strip()
            
            if not description:
                continue
            
            desc_normalized = self._normalize_for_matching(description)
            
            # === Check product type (part name) match using WORD BOUNDARIES ===
            part_match_ratio = 0.0
            if part_words:
                matched_part_count = self._count_word_matches(part_words, desc_normalized)
                part_match_ratio = matched_part_count / len(part_words)
            
            # HARD RULE: If product type doesn't match at all, SKIP this item
            if part_words and part_match_ratio == 0:
                continue  # Product type completely absent - wrong product
            
            # === Check model match using WORD BOUNDARIES ===
            model_match_ratio = 0.0
            if model_words:
                matched_model_count = self._count_word_matches(model_words, desc_normalized)
                model_match_ratio = matched_model_count / len(model_words)
            
            # === Check color match using WORD BOUNDARIES ===
            color_match_ratio = 0.0
            if color_parts:
                matched_color_count = self._count_word_matches(color_parts, desc_normalized)
                color_match_ratio = matched_color_count / len(color_parts)
            
            # === Calculate weighted score ===
            # Product type: 0.40, Model: 0.45 (most important for correct match), Color: 0.15
            score = 0.0
            score += 0.40 * part_match_ratio
            score += 0.45 * model_match_ratio
            score += 0.15 * color_match_ratio
            
            # === ALL model words must match for the bonus ===
            # Only grant high-confidence bonus when EVERY model word is found
            all_model_matched = model_words and model_match_ratio == 1.0
            all_part_matched = part_words and part_match_ratio >= 0.5
            
            if all_part_matched and all_model_matched:
                score = max(score, 0.88)
                # Extra bonus for color match on top of perfect part+model
                if color_parts and color_match_ratio > 0:
                    score = min(score + 0.07 * color_match_ratio, 1.0)
            
            if score > best_score:
                best_score = score
                best_match = pricing_item
        
        if best_score >= threshold and best_match:
            part_number = str(best_match.get('Part Number', '') or 'N/A')
            matched_name = str(best_match.get('Part Name', '') or best_match.get('Description', '') or '')
            price = float(best_match.get('Price', 0) or 0)
            
            return {
                'matched': True,
                'matched_part_number': part_number,
                'matched_part_name': matched_name,
                'unit_price': price,
                'match_confidence': best_score,
                'match_method': 'word_boundary',
                'pricing_source': 'google_sheet' if self.pricing_source == 'google_sheet' else os.path.basename(config.PRICING_SHEET_PATH)
            }
        else:
            return {
                'matched': False,
                'match_confidence': best_score,
                'reason': f'No match above {threshold:.0%} threshold (best: {best_score:.0%})',
                'unit_price': 0.0
            }
    
    def _normalize_for_matching(self, text: str) -> str:
        """Normalize text for matching (expand abbreviations, standardize)"""
        if not text:
            return ''
        
        text = text.lower().strip()
        
        # Standardize "type X" variants to consistent format "type-X"
        text = re.sub(r'\btype[\s\-]?(\d+)\b', r'type-\1', text)
        
        # Standardize "bs X" variants to "bsX"
        text = re.sub(r'\bbs[\s\-]?(\d+)\b', r'bs\1', text)
        
        # Minimal, safe abbreviation expansions (whole-word only)
        replacements = {
            'hfdlx': 'hf deluxe',
            'hf dlx': 'hf deluxe',
            'dlx': 'deluxe',
            'ismart': 'i smart',
            'xpro': 'x pro',
            'wreay': 'grey',
            'n/m': 'new model',
            'pass pro': 'passion pro',
        }
        
        for abbr, full in replacements.items():
            # Use word boundary aware replacement for short abbreviations
            if len(abbr) <= 3:
                text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text)
            elif abbr in text:
                text = text.replace(abbr, full)
        
        return text
    
    def _keyword_match_score(self, part_name: str, model: str, color: str, description: str) -> float:
        """
        Score based on keyword presence in description using WORD BOUNDARY matching.
        Pricing descriptions are like: "Body Kit Fit For Activa 3G Black"
        
        CRITICAL: Uses word boundaries. "pass" will NOT match "passion".
        """
        if not description:
            return 0.0
        
        # Part name match (REQUIRED for any meaningful score)
        part_ratio = 0.0
        if part_name:
            part_words = [w for w in part_name.split() if len(w) > 1]
            if part_words:
                matched_words = self._count_word_matches(part_words, description)
                part_ratio = matched_words / len(part_words)
        
        # If part_name was provided but NONE of it matched, cap score low
        if part_name and part_ratio == 0:
            return 0.10
        
        score = 0.0
        score += 0.40 * part_ratio
        
        # Model match (0.45 weight - most important for distinguishing variants)
        if model:
            model_words = [w for w in model.split() if len(w) > 1]
            if model_words:
                matched_words = self._count_word_matches(model_words, description)
                model_ratio = matched_words / len(model_words)
                score += 0.45 * model_ratio
        
        # Color match (0.15 weight)
        if color:
            color_parts = [c.strip() for c in color.replace('/', ' ').replace(',', ' ').split() if len(c.strip()) > 1]
            if color_parts:
                matched_colors = self._count_word_matches(color_parts, description)
                color_ratio = matched_colors / len(color_parts)
                score += 0.15 * color_ratio
        
        return score
    
    def match_all_lines(self, unique_lines: List[Dict]) -> List[Dict]:
        """
        Match all unique lines with pricing using algorithmic matching first,
        then optionally falling back to Gemini LLM for unmatched items.
        
        Args:
            unique_lines: List of unique normalized line items
            
        Returns:
            List of lines with pricing match results added
        """
        matched_lines = []
        unmatched_indices = []  # Track which items need LLM fallback
        
        # === Phase 1: Algorithmic matching (fast, free) ===
        print(f"[PRICING] Phase 1: Algorithmic matching for {len(unique_lines)} items...")
        
        for i, line in enumerate(unique_lines):
            match_result = self.match_line_item(line)
            line.update(match_result)
            matched_lines.append(line)
            
            if match_result['matched'] and match_result['match_confidence'] >= 0.80:
                print(f"[PRICING] Matched: {line['part_name']} ({line.get('model','')}) -> "
                      f"{match_result['matched_part_name'][:50]} "
                      f"(confidence: {match_result['match_confidence']:.0%}, "
                      f"price: Rs{match_result['unit_price']:.2f})")
            else:
                print(f"[PRICING] Low/No match: {line['part_name']} ({line.get('model','')}) "
                      f"(best: {match_result['match_confidence']:.0%})")
                unmatched_indices.append(i)
        
        # === Phase 2: LLM fallback for unmatched items (if enabled) ===
        if unmatched_indices and config.ENABLE_LLM_PRICING_FALLBACK:
            print(f"\n[PRICING] Phase 2: LLM fallback for {len(unmatched_indices)} unmatched items...")
            unmatched_items = [matched_lines[i] for i in unmatched_indices]
            
            try:
                llm_results = self._llm_match_items(unmatched_items)
                
                for idx, llm_result in zip(unmatched_indices, llm_results):
                    if llm_result and llm_result.get('matched'):
                        # LLM found a match - update the line
                        matched_lines[idx].update(llm_result)
                        print(f"[PRICING-LLM] Matched: {matched_lines[idx]['part_name']} "
                              f"({matched_lines[idx].get('model','')}) -> "
                              f"{llm_result['matched_part_name'][:50]} "
                              f"(price: Rs{llm_result['unit_price']:.2f})")
                    else:
                        print(f"[PRICING-LLM] Still no match: {matched_lines[idx]['part_name']} "
                              f"({matched_lines[idx].get('model','')})")
            except Exception as e:
                print(f"[PRICING-LLM] Fallback failed: {e}")
                import traceback
                traceback.print_exc()
        elif unmatched_indices:
            print(f"[PRICING] LLM fallback disabled (ENABLE_LLM_PRICING_FALLBACK=false). "
                  f"{len(unmatched_indices)} items unmatched.")
        
        # Summary
        final_matched = sum(1 for l in matched_lines if l.get('matched') and l.get('match_confidence', 0) >= 0.80)
        print(f"\n[PRICING] Summary: {final_matched}/{len(matched_lines)} items matched with high confidence")
        
        return matched_lines
    
    def _llm_match_items(self, unmatched_items: List[Dict]) -> List[Dict]:
        """
        Use Gemini LLM to match unmatched items against the pricing catalog.
        
        Sends a single batched request with all unmatched items and a relevant
        subset of the pricing catalog to stay within token limits.
        
        Args:
            unmatched_items: List of line items that failed algorithmic matching
            
        Returns:
            List of match results (one per input item)
        """
        import json
        import google.generativeai as genai
        
        genai.configure(api_key=config.GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        self._ensure_pricing_loaded()
        
        # Build a compact pricing catalog for the prompt
        # Include Part Number, Description, and Price only
        catalog_lines = []
        for item in self.pricing_data:
            part_no = item.get('Part Number', '')
            desc = item.get('Description', '') or item.get('Part Name', '')
            price = item.get('Price', 0)
            if part_no and desc:
                catalog_lines.append(f"{part_no} | {desc} | Rs{price}")
        
        # If catalog is huge, we need to be smart about what we send
        # Strategy: pre-filter catalog to items containing any relevant keywords
        relevant_keywords = set()
        for item in unmatched_items:
            for field in ['part_name', 'model', 'color']:
                val = item.get(field, '')
                if val:
                    for word in val.lower().split():
                        if len(word) > 2:
                            relevant_keywords.add(word)
        
        # Filter catalog to items with at least one relevant keyword
        filtered_catalog = []
        for line in catalog_lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in relevant_keywords):
                filtered_catalog.append(line)
        
        # Cap at ~2000 items to stay within token limits
        if len(filtered_catalog) > 2000:
            filtered_catalog = filtered_catalog[:2000]
        
        print(f"[PRICING-LLM] Sending {len(unmatched_items)} items against "
              f"{len(filtered_catalog)} filtered catalog entries (from {len(catalog_lines)} total)")
        
        # Build the unmatched items list for the prompt
        items_text = ""
        for i, item in enumerate(unmatched_items):
            items_text += (f"  Item {i+1}: part_name=\"{item.get('part_name', '')}\", "
                          f"model=\"{item.get('model', '')}\", "
                          f"color=\"{item.get('color', '')}\"\n")
        
        prompt = f"""You are a vehicle accessories pricing lookup assistant.

I have items from a handwritten order that I need to match against a pricing catalog.
The items are from the "Sai" brand of vehicle accessories (visors, body kits, guards, etc.).

UNMATCHED ITEMS TO FIND:
{items_text}
PRICING CATALOG (Part No | Description | Price):
{chr(10).join(filtered_catalog)}

INSTRUCTIONS:
- For each unmatched item, find the BEST matching product from the catalog
- Match based on: product type (visor, kit, etc.), vehicle model, and variant
- "Type 7", "Type 5", "SP" are variant/style identifiers for the product
- "Pass+" = Passport Plus, "Pass Pro" = Passion Pro
- "Susp Old" could mean "Super Splendor Old" or "Suspension Old Model"
- "Stound" is a variant name
- If no reasonable match exists, return matched=false
- Be STRICT: only match if you're confident it's the right product

Return ONLY valid JSON (no markdown code blocks):
{{
  "results": [
    {{
      "item_index": 1,
      "matched": true,
      "part_number": "SAI-XXX",
      "description": "Full description from catalog",
      "price": 999.00,
      "reasoning": "Brief reason why this matches"
    }},
    {{
      "item_index": 2,
      "matched": false,
      "reasoning": "No matching product found for this variant"
    }}
  ]
}}
"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean markdown if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join([
                line for line in lines
                if not line.strip().startswith('```') and not line.strip() == 'json'
            ])
        
        parsed = json.loads(response_text)
        results_list = parsed.get('results', [])
        
        # Map LLM results back to our format
        output = []
        for i, item in enumerate(unmatched_items):
            # Find the result for this item (item_index is 1-based)
            llm_result = None
            for r in results_list:
                if r.get('item_index') == i + 1:
                    llm_result = r
                    break
            
            if llm_result and llm_result.get('matched'):
                output.append({
                    'matched': True,
                    'matched_part_number': llm_result.get('part_number', 'N/A'),
                    'matched_part_name': llm_result.get('description', ''),
                    'unit_price': float(llm_result.get('price', 0)),
                    'match_confidence': 0.85,  # LLM matches get 85% confidence
                    'match_method': 'llm_fallback',
                    'pricing_source': 'gemini_llm'
                })
                if llm_result.get('reasoning'):
                    print(f"[PRICING-LLM] Item {i+1} reasoning: {llm_result['reasoning']}")
            else:
                reason = llm_result.get('reasoning', 'LLM could not find match') if llm_result else 'No LLM result'
                output.append({
                    'matched': False,
                    'match_confidence': 0.0,
                    'reason': reason,
                    'unit_price': 0.0
                })
        
        return output
