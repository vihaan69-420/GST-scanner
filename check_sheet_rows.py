#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check specific rows in Google Sheet for validation errors
"""
import sys
import os
sys.path.insert(0, 'src')

from sheets.sheets_manager import SheetsManager
import config

def main():
    print("\n" + "="*80)
    print("Checking Google Sheet Rows 7 & 8 for Validation Errors")
    print("="*80 + "\n")
    
    try:
        # Initialize sheets manager
        sheets = SheetsManager()
        
        # Get all data from Invoice_Header sheet
        all_data = sheets.worksheet.get_all_values()
        
        if len(all_data) < 8:
            print(f"[INFO] Sheet only has {len(all_data)} rows")
            return
        
        # Get header row
        headers = all_data[0]
        print(f"[INFO] Sheet has {len(all_data)} rows total\n")
        
        # Find validation columns
        try:
            val_status_idx = headers.index('Validation_Status')
            val_remarks_idx = headers.index('Validation_Remarks')
        except ValueError:
            print("[ERROR] Could not find validation columns in sheet")
            return
        
        # Check rows 7 and 8 (indices 6 and 7 in 0-based)
        for row_num in [7, 8]:
            if row_num >= len(all_data):
                print(f"[INFO] Row {row_num} does not exist")
                continue
            
            row = all_data[row_num - 1]  # Convert to 0-based index
            
            print(f"\n{'='*80}")
            print(f"ROW {row_num}:")
            print(f"{'='*80}")
            
            # Get invoice number (usually first column)
            invoice_no = row[0] if len(row) > 0 else "N/A"
            print(f"Invoice Number: {invoice_no}")
            
            # Get validation status
            val_status = row[val_status_idx] if len(row) > val_status_idx else "N/A"
            print(f"Validation Status: {val_status}")
            
            # Get validation remarks
            val_remarks = row[val_remarks_idx] if len(row) > val_remarks_idx else "N/A"
            print(f"Validation Remarks: {val_remarks}")
            
            # Show some key fields for context
            if len(headers) > 4 and len(row) > 4:
                print(f"\nKey Fields:")
                print(f"  Invoice Date: {row[1] if len(row) > 1 else 'N/A'}")
                print(f"  Seller GSTIN: {row[2] if len(row) > 2 else 'N/A'}")
                print(f"  Buyer GSTIN: {row[4] if len(row) > 4 else 'N/A'}")
        
        print(f"\n{'='*80}\n")
        
        # Analyze if errors are valid
        print("ANALYSIS:")
        print("-" * 80)
        
        for row_num in [7, 8]:
            if row_num >= len(all_data):
                continue
            row = all_data[row_num - 1]
            val_remarks = row[val_remarks_idx] if len(row) > val_remarks_idx else ""
            
            if val_remarks and val_remarks != "All validations passed":
                print(f"\nRow {row_num} has validation issues:")
                print(f"  {val_remarks}")
                
                # Check if errors are meaningful
                if "ERRORS:" in val_remarks:
                    print("  -> Contains ERRORS - these should be reviewed")
                if "WARNINGS:" in val_remarks:
                    print("  -> Contains WARNINGS - may be acceptable")
        
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
