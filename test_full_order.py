#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Full Order Processing Test - Extract → Normalize → Price → PDF
"""
import sys
import os
import io
import json
from datetime import datetime

# Fix console encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from order_normalization.extractor import OrderExtractor
from order_normalization.normalizer import OrderNormalizer
from order_normalization.pricing_matcher import PricingMatcher
from order_normalization.pdf_generator import OrderPDFGenerator
import config

print("="*80)
print("FULL ORDER PROCESSING TEST")
print("="*80)

# Initialize components
print("\n[1/6] Initializing components...")
extractor = OrderExtractor()
normalizer = OrderNormalizer()
pricing_matcher = PricingMatcher()
pdf_generator = OrderPDFGenerator()

# Extract from image
print("\n[2/6] Extracting order data from image...")
image_path = "test_order_input.png"

try:
    extracted = extractor.extract_order_lines(image_path, page_number=1)
    
    print(f"✅ Extraction completed!")
    print(f"   - Lines extracted: {len(extracted.get('lines_raw', []))}")
    
    # Show metadata
    if extracted.get('order_metadata'):
        print(f"\n📋 Order Metadata:")
        metadata = extracted['order_metadata']
        print(f"   - Customer Name: {metadata.get('customer_name', 'N/A')}")
        print(f"   - Mobile Number: {metadata.get('mobile_number', 'N/A')}")
        print(f"   - Order Date: {metadata.get('order_date', 'N/A')}")
        print(f"   - Location: {metadata.get('location', 'N/A')}")
    
    # Show first 5 items
    print(f"\n📝 First 5 Line Items (Raw):")
    for i, line in enumerate(extracted.get('lines_raw', [])[:5]):
        print(f"   {i+1}. {line.get('brand', '')} - {line.get('part_name_raw', '')} ({line.get('color_raw', '')}) x{line.get('quantity', 0)}")

except Exception as e:
    print(f"❌ Extraction failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Normalize
print("\n[3/6] Normalizing data...")
try:
    normalized_lines = normalizer.normalize_all_lines([extracted])
    print(f"✅ Normalized {len(normalized_lines)} lines")
except Exception as e:
    print(f"❌ Normalization failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Match pricing
print("\n[4/6] Matching with pricing sheet...")
try:
    matched_lines = pricing_matcher.match_all_lines(normalized_lines)
    matched_count = sum(1 for line in matched_lines if line.get('matched', False))
    print(f"✅ Pricing: {matched_count} matched, {len(matched_lines) - matched_count} unmatched")
    
    # Show pricing sample
    if matched_count > 0:
        print(f"\n💰 Sample Matched Prices:")
        count = 0
        for line in matched_lines:
            if line.get('matched', False) and count < 3:
                print(f"   - {line['part_name']}: ₹{line['unit_price']:.2f} (confidence: {line['match_confidence']:.0%})")
                count += 1
    
except Exception as e:
    print(f"⚠️ Pricing match failed: {e}")
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
serial_no = 1
for line in matched_lines:
    # Build item description (clubbed)
    brand = line.get('brand', '')
    part = line.get('part_name', '')
    model = line.get('model', '')
    
    description_parts = []
    if brand:
        description_parts.append(brand)
    if part:
        description_parts.append(part)
    if model and model != part:
        description_parts.append(f"({model})")
    
    item_description = ' '.join(description_parts)
    
    clean_lines.append({
        'serial_no': serial_no,
        'brand': brand,
        'part_name': part,
        'item_description': item_description,  # Clubbed field
        'part_number': line.get('matched_part_number', 'N/A'),
        'model': model,
        'color': line.get('color', ''),
        'quantity': line['quantity'],
        'rate': line['rate'],
        'line_total': line['line_total'],
        'match_confidence': line.get('match_confidence', 0.0)
    })
    serial_no += 1

subtotal = sum(item['line_total'] for item in clean_lines)
total_qty = sum(item['quantity'] for item in clean_lines)
unmatched = sum(1 for item in clean_lines if item['part_number'] == 'N/A')

# Get customer info from metadata
customer_name = order_metadata_extracted.get('customer_name', 'N/A')
mobile_number = order_metadata_extracted.get('mobile_number', '')
order_date_str = order_metadata_extracted.get('order_date', datetime.now().strftime('%d/%m/%Y'))
location = order_metadata_extracted.get('location', '')

clean_invoice = {
    'order_id': order_id,
    'order_date': order_date_str,
    'customer_name': customer_name,
    'mobile_number': mobile_number,
    'location': location,
    'line_items': clean_lines,
    'subtotal': subtotal,
    'total_items': len(clean_lines),
    'total_quantity': total_qty,
    'unmatched_count': unmatched
}

print(f"✅ Clean invoice built:")
print(f"   - Total Items: {clean_invoice['total_items']}")
print(f"   - Total Quantity: {clean_invoice['total_quantity']}")
print(f"   - Subtotal: ₹{clean_invoice['subtotal']:.2f}")
print(f"   - Unmatched: {clean_invoice['unmatched_count']}")

# Generate PDF
print(f"\n[6/6] Generating PDF...")
try:
    pdf_path = pdf_generator.generate_pdf(clean_invoice, f"TEST_OUTPUT_{order_id}.pdf")
    print(f"✅ PDF generated: {pdf_path}")
    
    # Save raw data as JSON
    json_path = f"TEST_OUTPUT_{order_id}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'order_metadata': order_metadata_extracted,
            'raw_extraction': extracted['lines_raw'],
            'normalized_lines': normalized_lines,
            'matched_lines': matched_lines,
            'clean_invoice': clean_invoice
        }, f, indent=2, ensure_ascii=False)
    print(f"✅ Raw data saved: {json_path}")
    
except Exception as e:
    print(f"❌ PDF generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("✅ TEST COMPLETED SUCCESSFULLY")
print("="*80)
print(f"\n📄 Output files:")
print(f"   - PDF: {pdf_path}")
print(f"   - JSON: {json_path}")
