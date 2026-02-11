"""
Order Normalizer
Normalizes extracted line item fields (part names, colors, models, etc.)
"""
import re
from typing import Dict, List


class OrderNormalizer:
    """Normalizes handwritten order data into clean, standardized format"""
    
    def __init__(self):
        """Initialize normalizer with mappings"""
        # Color normalization mappings
        self.color_map = {
            # Black variants
            'BL': 'Black',
            'PA': 'Black',
            'BLACK': 'Black',
            'BLK': 'Black',
            
            # Grey variants
            'GREY': 'Grey',
            'GRAY': 'Grey',
            'GRY': 'Grey',
            
            # Silver variants
            'S': 'Silver',
            'SILVR': 'Silver',
            'SLVR': 'Silver',
            'SILVER': 'Silver',
            
            # Blue variants
            'BLU': 'Blue',
            'BLUE': 'Blue',
            
            # Red variants
            'RED': 'Red',
            'RD': 'Red',
            
            # White variants
            'WHITE': 'White',
            'WHT': 'White',
            'WHI': 'White',
            
            # Green variants
            'GREEN': 'Green',
            'GRN': 'Green',
            
            # Golden variants
            'GOLDEN': 'Golden',
            'GOLD': 'Golden',
            'GLD': 'Golden',
        }
        
        # Common brand prefixes to remove
        self.brand_prefixes = ['Sai -', 'SAI -', 'Sai-', 'SAI-']
    
    def normalize_line_item(self, raw_line: Dict) -> Dict:
        """
        Normalize a single line item
        
        Args:
            raw_line: Raw extracted line item
            {
                'serial_no': int,
                'brand': str (NEW),
                'part_name_raw': str,
                'model_raw': str,
                'color_raw': str,
                'quantity': int
            }
            
        Returns:
            Normalized line item with additional fields
        """
        # Extract brand from new field or fallback to parsing part_name
        brand_raw = raw_line.get('brand', '')
        if not brand_raw:
            brand_raw = self._extract_brand(raw_line.get('part_name_raw', ''))
        
        return {
            # Raw fields (preserved for audit)
            'serial_no_raw': raw_line.get('serial_no', 0),
            'brand_raw': brand_raw,
            'part_name_raw': raw_line.get('part_name_raw', ''),
            'model_raw': raw_line.get('model_raw', ''),
            'color_raw': raw_line.get('color_raw', ''),
            
            # Normalized fields
            'brand': brand_raw.strip() if brand_raw else '',
            'part_name': self._normalize_part_name(raw_line.get('part_name_raw', '')),
            'model': self._normalize_model(raw_line.get('model_raw', '')),
            'color': self._normalize_color(raw_line.get('color_raw', '')),
            'quantity': int(raw_line.get('quantity') or 0),
            
            # Metadata
            'normalization_confidence': 1.0,  # Placeholder for future ML confidence
        }
    
    def _normalize_part_name(self, raw: str) -> str:
        """
        Normalize part name (remove brand, standardize formatting)
        
        Args:
            raw: Raw part name (e.g., "Sai - Rodeo V2+ Stound")
            
        Returns:
            Normalized part name (e.g., "Rodeo V2+ Stound")
        """
        if not raw:
            return ''
        
        normalized = raw.strip()
        
        # Remove brand prefixes
        for prefix in self.brand_prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
                break
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _normalize_model(self, raw: str) -> str:
        """
        Normalize model identifier
        
        Args:
            raw: Raw model (e.g., "V2+", "Activa 3G")
            
        Returns:
            Normalized model
        """
        if not raw:
            return ''
        
        return raw.strip()
    
    def _normalize_color(self, raw: str) -> str:
        """
        Normalize color (standardize abbreviations and multi-part colors)
        
        Args:
            raw: Raw color (e.g., "PA/Grey", "BL/Red", "Silver")
            
        Returns:
            Normalized color (e.g., "Black/Grey", "Black/Red", "Silver")
        """
        if not raw:
            return ''
        
        # Handle multi-part colors (e.g., "PA/Grey" -> "Black/Grey")
        if '/' in raw:
            parts = raw.split('/')
            normalized_parts = []
            for part in parts:
                part_upper = part.strip().upper()
                normalized_parts.append(self.color_map.get(part_upper, part.strip()))
            return '/'.join(normalized_parts)
        
        # Single color
        color_upper = raw.strip().upper()
        return self.color_map.get(color_upper, raw.strip())
    
    def _extract_brand(self, raw_part_name: str) -> str:
        """
        Extract brand from part name
        
        Args:
            raw_part_name: Raw part name (e.g., "Sai - Rodeo V2+")
            
        Returns:
            Brand name (e.g., "Sai")
        """
        if not raw_part_name:
            return ''
        
        # Check for brand prefix patterns
        for prefix in self.brand_prefixes:
            if raw_part_name.startswith(prefix):
                # Extract brand (remove separator)
                brand = prefix.replace('-', '').strip()
                return brand
        
        return ''
    
    def normalize_all_lines(self, extracted_pages: List[Dict]) -> List[Dict]:
        """
        Normalize all lines from all pages
        
        Args:
            extracted_pages: List of extraction results
            
        Returns:
            List of normalized line items (flattened across pages)
        """
        all_normalized = []
        
        for page_data in extracted_pages:
            page_number = page_data['page_number']
            lines_raw = page_data.get('lines_raw', [])
            
            for raw_line in lines_raw:
                normalized = self.normalize_line_item(raw_line)
                # Add page tracking
                normalized['page_number'] = page_number
                all_normalized.append(normalized)
        
        return all_normalized
