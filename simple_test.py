#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple test - just extraction"""
import sys
import os
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from order_normalization.extractor import OrderExtractor
import json

print("Testing extraction only...")
extractor = OrderExtractor()

try:
    result = extractor.extract_order_lines("test_order_image.png", 1)
    
    print("\n=== EXTRACTION RESULT ===")
    print(f"Lines: {len(result['lines_raw'])}")
    print(f"\nMetadata:")
    print(json.dumps(result.get('order_metadata', {}), indent=2, ensure_ascii=False))
    
    print(f"\nAll {len(result['lines_raw'])} items:")
    for line in result['lines_raw']:
        print(f"  {line['serial_no']}. {line.get('brand', '')} - {line.get('part_name_raw', '')} "
              f"({line.get('color_raw', '')}) x{line.get('quantity', 0)}")
    
    print("\n✅ SUCCESS!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
