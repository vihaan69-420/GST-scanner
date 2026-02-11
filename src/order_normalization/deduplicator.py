"""
Order Deduplicator
Identifies and marks duplicate line items across multiple pages
"""
from typing import Dict, List


class OrderDeduplicator:
    """Deduplicates line items across multiple order pages"""
    
    def __init__(self):
        """Initialize deduplicator"""
        pass
    
    def _generate_signature(self, line: Dict) -> str:
        """
        Generate unique signature for duplicate detection
        
        Rules: Same part_name + model + color + quantity = duplicate
        
        Args:
            line: Normalized line item
            
        Returns:
            Signature string
        """
        part_name = line.get('part_name', '').lower().strip()
        model = line.get('model', '').lower().strip()
        color = line.get('color', '').lower().strip()
        quantity = line.get('quantity', 0)
        
        return f"{part_name}|{model}|{color}|{quantity}"
    
    def deduplicate_lines(self, normalized_lines: List[Dict]) -> Dict:
        """
        Identify duplicate line items across pages
        
        Args:
            normalized_lines: List of normalized line items from all pages
            
        Returns:
            Dictionary with:
            {
                'unique_lines': List[Dict],  # Unique line items
                'duplicate_lines': List[Dict],  # Duplicate line items
                'total_unique': int,
                'total_duplicates': int,
                'duplicate_map': Dict[str, str]  # Maps duplicate line_id to original line_id
            }
        """
        unique_lines = []
        duplicate_lines = []
        seen_signatures = {}
        duplicate_map = {}
        
        for line in normalized_lines:
            signature = self._generate_signature(line)
            
            # Generate line ID for tracking
            line_id = f"P{line['page_number']}_S{line['serial_no_raw']}"
            line['line_id'] = line_id
            
            if signature in seen_signatures:
                # This is a duplicate
                line['is_duplicate'] = True
                line['duplicate_of'] = seen_signatures[signature]
                duplicate_lines.append(line)
                duplicate_map[line_id] = seen_signatures[signature]
                
                print(f"[DEDUP] Duplicate found: {line_id} is duplicate of {seen_signatures[signature]}")
            else:
                # This is unique
                line['is_duplicate'] = False
                line['duplicate_of'] = None
                unique_lines.append(line)
                seen_signatures[signature] = line_id
        
        print(f"[DEDUP] Summary: {len(unique_lines)} unique, {len(duplicate_lines)} duplicates")
        
        return {
            'unique_lines': unique_lines,
            'duplicate_lines': duplicate_lines,
            'total_unique': len(unique_lines),
            'total_duplicates': len(duplicate_lines),
            'duplicate_map': duplicate_map
        }
