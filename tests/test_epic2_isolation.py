"""
Epic 2 Isolation Tests
Ensures that Order Upload & Normalization feature is completely isolated from GST scanner
"""
import ast
import os
import sys
import io

# Fix encoding for Windows PowerShell
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config


def test_feature_flag_off_no_new_behavior():
    """
    Test: With feature flag OFF, GST scanner behaves unchanged
    Ensures no order menu visible when feature is disabled
    """
    print("\n[TEST] Feature flag OFF - no new behavior")
    
    # Temporarily disable feature
    original_flag = config.FEATURE_ORDER_UPLOAD_NORMALIZATION
    config.FEATURE_ORDER_UPLOAD_NORMALIZATION = False
    
    try:
        from bot.telegram_bot import GSTScannerBot
        
        bot = GSTScannerBot()
        
        # Assert no order menu visible
        menu = bot.create_main_menu_keyboard()
        menu_str = str(menu)
        
        assert "Upload Order" not in menu_str, "Order Upload button should not be visible when feature is disabled"
        assert "📦" not in menu_str, "Order emoji should not be visible when feature is disabled"
        
        print("✓ PASSED: No order upload button visible when feature disabled")
        
        # Verify order orchestrator is None
        assert bot.order_orchestrator is None, "Order orchestrator should be None when feature disabled"
        assert len(bot.order_sessions) == 0, "Order sessions should be empty when feature disabled"
        
        print("✓ PASSED: Order components not initialized when feature disabled")
        
    finally:
        # Restore original flag
        config.FEATURE_ORDER_UPLOAD_NORMALIZATION = original_flag


def test_no_imports_into_gst_scanner():
    """
    Test: Existing GST code doesn't import from order_normalization
    Ensures complete isolation - no dependencies from old code to new code
    """
    print("\n[TEST] No imports into GST scanner from order_normalization")
    
    gst_files = [
        'src/ocr/ocr_engine.py',
        'src/parsing/gst_parser.py',
        'src/parsing/gst_validator.py',
        'src/parsing/line_item_extractor.py',
        'src/sheets/sheets_manager.py',
        'src/features/confidence_scorer.py',
        'src/features/correction_manager.py',
        'src/features/dedup_manager.py',
        'src/features/audit_logger.py',
    ]
    
    for file_path in gst_files:
        full_path = os.path.join(os.path.dirname(__file__), '..', file_path)
        
        if not os.path.exists(full_path):
            print(f"⚠ SKIP: {file_path} (file not found)")
            continue
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content)
        
        # Check for any imports from order_normalization
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert 'order_normalization' not in alias.name, \
                        f"File {file_path} imports from order_normalization: {alias.name}"
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert 'order_normalization' not in node.module, \
                        f"File {file_path} imports from order_normalization: {node.module}"
        
        print(f"✓ PASSED: {file_path} - no order_normalization imports")


def test_existing_sheets_untouched():
    """
    Test: Verify no modifications to Invoice_Header or Line_Items tabs structure
    Ensures existing GST scanner sheets remain unchanged
    """
    print("\n[TEST] Existing sheets untouched")
    
    # Check that original sheet columns are defined and unchanged
    assert hasattr(config, 'SHEET_COLUMNS'), "SHEET_COLUMNS must be defined"
    assert hasattr(config, 'LINE_ITEM_COLUMNS'), "LINE_ITEM_COLUMNS must be defined"
    
    # Verify first 24 columns are Tier 1 (original GST scanner)
    tier1_columns = [
        'Invoice_No', 'Invoice_Date', 'Invoice_Type', 'Seller_Name', 'Seller_GSTIN',
        'Seller_State_Code', 'Buyer_Name', 'Buyer_GSTIN', 'Buyer_State_Code',
        'Ship_To_Name', 'Ship_To_State_Code', 'Place_Of_Supply', 'Supply_Type',
        'Reverse_Charge', 'Invoice_Value', 'Total_Taxable_Value', 'Total_GST',
        'IGST_Total', 'CGST_Total', 'SGST_Total', 'Eway_Bill_No', 'Transporter',
        'Validation_Status', 'Validation_Remarks'
    ]
    
    for i, col in enumerate(tier1_columns):
        assert config.SHEET_COLUMNS[i] == col, \
            f"Original column {i} changed: expected {col}, got {config.SHEET_COLUMNS[i]}"
    
    print("✓ PASSED: Original SHEET_COLUMNS structure intact")
    
    # Verify line item columns unchanged
    original_line_item_cols = [
        'Invoice_No', 'Line_No', 'Item_Code', 'Item_Description', 'HSN',
        'Qty', 'UOM', 'Rate', 'Discount_Percent', 'Taxable_Value',
        'GST_Rate', 'CGST_Rate', 'CGST_Amount', 'SGST_Rate', 'SGST_Amount',
        'IGST_Rate', 'IGST_Amount', 'Cess_Amount', 'Line_Total'
    ]
    
    assert config.LINE_ITEM_COLUMNS == original_line_item_cols, \
        "LINE_ITEM_COLUMNS structure has been modified"
    
    print("✓ PASSED: LINE_ITEM_COLUMNS structure intact")


def test_feature_flag_configuration():
    """
    Test: Feature flag configuration is properly set up
    """
    print("\n[TEST] Feature flag configuration")
    
    assert hasattr(config, 'FEATURE_ORDER_UPLOAD_NORMALIZATION'), \
        "FEATURE_ORDER_UPLOAD_NORMALIZATION flag must be defined"
    
    assert isinstance(config.FEATURE_ORDER_UPLOAD_NORMALIZATION, bool), \
        "Feature flag must be boolean"
    
    print(f"✓ PASSED: Feature flag defined (current value: {config.FEATURE_ORDER_UPLOAD_NORMALIZATION})")
    
    # Check pricing configuration exists
    assert hasattr(config, 'PRICING_SHEET_SOURCE'), "PRICING_SHEET_SOURCE must be defined"
    assert hasattr(config, 'PRICING_SHEET_PATH'), "PRICING_SHEET_PATH must be defined"
    
    print("✓ PASSED: Pricing configuration defined")


def test_order_module_isolation():
    """
    Test: Order normalization module is properly isolated
    """
    print("\n[TEST] Order module isolation")
    
    # Check that order_normalization module exists
    order_module_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'order_normalization')
    assert os.path.exists(order_module_path), "order_normalization module must exist"
    
    # Check all required files exist
    required_files = [
        '__init__.py',
        'order_session.py',
        'orchestrator.py',
        'extractor.py',
        'normalizer.py',
        'deduplicator.py',
        'pricing_matcher.py',
        'pdf_generator.py',
        'sheets_handler.py',
    ]
    
    for filename in required_files:
        file_path = os.path.join(order_module_path, filename)
        assert os.path.exists(file_path), f"Required file {filename} must exist in order_normalization/"
    
    print("✓ PASSED: All order_normalization module files exist")
    
    # Verify __init__.py has feature flag check
    init_path = os.path.join(order_module_path, '__init__.py')
    with open(init_path, 'r', encoding='utf-8') as f:
        init_content = f.read()
    
    assert 'FEATURE_ORDER_UPLOAD_NORMALIZATION' in init_content, \
        "__init__.py must check feature flag"
    
    print("✓ PASSED: __init__.py has feature flag check")


def run_all_tests():
    """Run all Epic 2 isolation tests"""
    print("="*80)
    print("EPIC 2 ISOLATION TESTS")
    print("="*80)
    
    tests = [
        test_feature_flag_configuration,
        test_order_module_isolation,
        test_feature_flag_off_no_new_behavior,
        test_no_imports_into_gst_scanner,
        test_existing_sheets_untouched,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ FAILED: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ ERROR: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
    
    print("\n" + "="*80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*80)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
