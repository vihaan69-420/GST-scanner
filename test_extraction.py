#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to extract data from order image and generate PDF
"""
import sys
import os
import io

# Fix encoding for Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from order_normalization.extractor import OrderExtractor
from order_normalization.normalizer import OrderNormalizer
from order_normalization.pricing_matcher import PricingMatcher
from order_normalization.pdf_generator import OrderPDFGenerator
from datetime import datetime
import json

print("="*80)
print("Testing Epic 2 Order Extraction & PDF Generation")
print("="*80)

# Initialize components
print("\n[1/6] Initializing components...")
extractor = OrderExtractor()
normalizer = OrderNormalizer()
pricing_matcher = PricingMatcher()
pdf_generator = OrderPDFGenerator()

# Extract from image
print("\n[2/6] Extracting order data from image...")
image_path = "test_order_image.png"

try:
    extracted = extractor.extract_order_lines(image_path, page_number=1)
    
    print(f"\n✅ Extraction completed!")
    print(f"   - Lines extracted: {len(extracted.get('lines_raw', []))}")
    
    # Show metadata
    if extracted.get('order_metadata'):
        print(f"\n📋 Order Metadata:")
        metadata = extracted['order_metadata']
        print(f"   - Customer Name: {metadata.get('customer_name', 'N/A')}")
        print(f"   - Mobile Number: {metadata.get('mobile_number', 'N/A')}")
        print(f"   - Order Date: {metadata.get('order_date', 'N/A')}")
        print(f"   - Location: {metadata.get('location', 'N/A')}")
    
    # Show first 5 line items
    print(f"\n📝 First 5 Line Items (Raw):")
    for i, line in enumerate(extracted.get('lines_raw', [])[:5]):
        print(f"   {i+1}. S/N: {line.get('serial_no')}, Brand: {line.get('brand', 'N/A')}, "
              f"Part: {line.get('part_name_raw', 'N/A')[:30]}, Qty: {line.get('quantity')}")
    
    if len(extracted.get('lines_raw', [])) > 5:
        print(f"   ... and {len(extracted.get('lines_raw', [])) - 5} more items")
    
except Exception as e:
    print(f"❌ Extraction failed: {e}")
    sys.exit(1)

# Normalize
print("\n[3/6] Normalizing data...")
try:
    normalized_lines = normalizer.normalize_all_lines([extracted])
    print(f"✅ Normalized {len(normalized_lines)} lines")
except Exception as e:
    print(f"❌ Normalization failed: {e}")
    sys.exit(1)

# Match pricing (will show warnings if no pricing file)
print("\n[4/6] Matching with pricing...")
try:
    matched_lines = pricing_matcher.match_all_lines(normalized_lines)
    matched_count = sum(1 for line in matched_lines if line.get('matched', False))
    print(f"✅ Pricing matched: {matched_count} matched, {len(matched_lines) - matched_count} unmatched")
except Exception as e:
    print(f"⚠️  Pricing match skipped: {e}")
    # Continue with zero prices
    matched_lines = normalized_lines
    for line in matched_lines:
        line['matched'] = False
        line['unit_price'] = 0.0

# Compute totals
print("\n[5/6] Computing totals...")
for line in matched_lines:
    line['quantity'] = int(line.get('quantity', 0))
    line['rate'] = float(line.get('unit_price', 0.0))
    line['line_total'] = line['quantity'] * line['rate']

# Build clean invoice
order_id = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
order_metadata_extracted = extracted.get('order_metadata', {})

clean_lines = []
for i, line in enumerate(matched_lines, 1):
    clean_lines.append({
        'serial_no': i,
        'brand': line.get('brand', ''),
        'part_name': line['part_name'],
        'part_number': line.get('matched_part_number', 'N/A'),
        'model': line.get('model', ''),
        'color': line.get('color', ''),
        'quantity': line['quantity'],
        'rate': line['rate'],
        'line_total': line['line_total'],
        'match_confidence': line.get('match_confidence', 0.0)
    })

subtotal = sum(item['line_total'] for item in clean_lines)
total_qty = sum(item['quantity'] for item in clean_lines)
unmatched = sum(1 for item in clean_lines if item['part_number'] == 'N/A')

clean_invoice = {
    'order_id': order_id,
    'order_date': order_metadata_extracted.get('order_date', datetime.now().strftime('%d/%m/%Y')),
    'customer_name': order_metadata_extracted.get('customer_name', 'Test Customer'),
    'mobile_number': order_metadata_extracted.get('mobile_number', ''),
    'location': order_metadata_extracted.get('location', ''),
    'line_items': clean_lines,
    'subtotal': subtotal,
    'total_items': len(clean_lines),
    'total_quantity': total_qty,
    'unmatched_count': unmatched
}

print(f"✅ Clean invoice built:")
print(f"   - Order ID: {clean_invoice['order_id']}")
print(f"   - Date: {clean_invoice['order_date']}")
print(f"   - Customer: {clean_invoice['customer_name']}")
if clean_invoice['mobile_number']:
    print(f"   - Mobile: {clean_invoice['mobile_number']}")
print(f"   - Total Items: {clean_invoice['total_items']}")
print(f"   - Total Quantity: {clean_invoice['total_quantity']}")
print(f"   - Subtotal: ₹{clean_invoice['subtotal']:.2f}")

# Generate PDF
print("\n[6/6] Generating PDF...")
try:
    pdf_path = pdf_generator.generate_pdf(clean_invoice)
    print(f"✅ PDF generated successfully!")
    print(f"   📄 Path: {pdf_path}")
    
    # Also save extraction data as JSON
    json_path = pdf_path.replace('.pdf', '_extraction.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'order_metadata': order_metadata_extracted,
            'extracted_lines': extracted.get('lines_raw', []),
            'normalized_count': len(normalized_lines),
            'clean_invoice_summary': {
                'total_items': clean_invoice['total_items'],
                'total_quantity': clean_invoice['total_quantity'],
                'customer': clean_invoice['customer_name'],
                'date': clean_invoice['order_date']
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"   📊 Extraction data: {json_path}")
    
except Exception as e:
    print(f"❌ PDF generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("✅ Test completed successfully!")
print("="*80)
print(f"\nGenerated files:")
print(f"  - PDF: {pdf_path}")
print(f"  - JSON: {json_path}")
print("\nYou can now open the PDF to see the improved output!")
