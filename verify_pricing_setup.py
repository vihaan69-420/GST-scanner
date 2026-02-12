"""
Quick Verification Test - Google Sheet Pricing Integration
Run this to verify the pricing integration is working correctly
"""
import sys
import os
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def verify_pricing_integration():
    print("\n" + "="*70)
    print("GOOGLE SHEET PRICING INTEGRATION - VERIFICATION TEST")
    print("="*70)
    
    # Test 1: Config check
    print("\n[TEST 1] Configuration Check...")
    import config
    
    print(f"  Pricing Source: {config.PRICING_SHEET_SOURCE}")
    print(f"  Sheet ID: {config.PRICING_SHEET_ID}")
    print(f"  Sheet Name: {config.PRICING_SHEET_NAME}")
    
    if config.PRICING_SHEET_SOURCE != 'google_sheet':
        print("  FAILED: Pricing source should be 'google_sheet'")
        return False
    
    if not config.PRICING_SHEET_ID:
        print("  FAILED: Pricing sheet ID is not set")
        return False
    
    print("  [OK] Configuration valid")
    
    # Test 2: Pricing Matcher initialization
    print("\n[TEST 2] Pricing Matcher Initialization...")
    try:
        from order_normalization.pricing_matcher import PricingMatcher
        matcher = PricingMatcher()
        
        if not matcher.pricing_data:
            print("  FAILED: No pricing data loaded")
            return False
        
        print(f"  [OK] Loaded {len(matcher.pricing_data)} products")
        
        if len(matcher.pricing_data) < 4000:
            print(f"  WARNING: Expected ~4751 products, got {len(matcher.pricing_data)}")
        
    except Exception as e:
        print(f"  FAILED: {e}")
        return False
    
    # Test 3: Sample matching
    print("\n[TEST 3] Sample Product Matching...")
    test_item = {
        'part_name': 'Front Fender',
        'model': 'Hornet',
        'color': 'Black',
        'brand': 'Hero',
        'quantity': 1
    }
    
    result = matcher.match_line_item(test_item)
    
    if result['matched']:
        print(f"  [OK] Match found:")
        print(f"    Part: {result['matched_part_number']}")
        print(f"    Price: Rs.{result['unit_price']:.2f}")
        print(f"    Confidence: {result['match_confidence']:.1%}")
    else:
        print(f"  [INFO] No match (this is OK for some items)")
        print(f"    Best score: {result['match_confidence']:.1%}")
    
    # Test 4: Integration with orchestrator
    print("\n[TEST 4] Orchestrator Integration...")
    try:
        from order_normalization.orchestrator import OrderNormalizationOrchestrator
        orchestrator = OrderNormalizationOrchestrator()
        
        if orchestrator.pricing_matcher:
            print(f"  [OK] Orchestrator has pricing matcher")
            print(f"  [OK] Integration complete")
        else:
            print("  FAILED: Orchestrator missing pricing matcher")
            return False
            
    except Exception as e:
        print(f"  FAILED: {e}")
        return False
    
    # Summary
    print("\n" + "="*70)
    print("SUCCESS - ALL TESTS PASSED - System is ready!")
    print("="*70)
    print("\nNext steps:")
    print("  1. Start the bot: python run_bot.py")
    print("  2. Test with /order command")
    print("  3. Upload order images and verify pricing")
    print("\n")
    
    return True

if __name__ == "__main__":
    try:
        success = verify_pricing_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nVERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
