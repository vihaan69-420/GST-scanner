"""
Standalone GSTR-1 Export Script
Interactive command-line interface for generating GSTR-1 CSV exports

Usage:
    python export_gstr1.py

The script will interactively prompt for:
- Month (1-12)
- Year (e.g., 2026)
- Export type (B2B, B2C Small, HSN Summary, or All)
- Output directory
"""
import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from sheets.sheets_manager import SheetsManager
from exports.gstr1_exporter import GSTR1Exporter


def print_banner():
    """Print script banner"""
    print("=" * 80)
    print("GSTR-1 EXPORT TOOL")
    print("=" * 80)
    print("Generate GST portal-ready CSV files for GSTR-1 filing")
    print("")


def get_period_input():
    """Get period (month and year) from user"""
    print("-" * 80)
    print("PERIOD SELECTION")
    print("-" * 80)
    
    while True:
        try:
            month_input = input("Enter month (1-12): ").strip()
            month = int(month_input)
            if 1 <= month <= 12:
                break
            print("  ❌ Please enter a number between 1 and 12")
        except ValueError:
            print("  ❌ Please enter a valid number")
    
    while True:
        try:
            year_input = input("Enter year (e.g., 2026): ").strip()
            year = int(year_input)
            if 2000 <= year <= 2100:
                break
            print("  ❌ Please enter a valid year")
        except ValueError:
            print("  ❌ Please enter a valid number")
    
    from calendar import month_name
    print(f"\n  ✓ Selected: {month_name[month]} {year}")
    return month, year


def get_export_type():
    """Get export type from user"""
    print("\n" + "-" * 80)
    print("EXPORT TYPE")
    print("-" * 80)
    print("1️⃣  B2B Invoices (Table 4A/4B)")
    print("2️⃣  B2C Small Summary (Table 7)")
    print("3️⃣  HSN Summary (Table 12)")
    print("4️⃣  All Three (Complete GSTR-1 export)")
    print("")
    
    while True:
        choice = input("Select export type (1-4): ").strip()
        if choice in ['1', '2', '3', '4']:
            types = {
                '1': ('b2b', 'B2B Invoices'),
                '2': ('b2c', 'B2C Small Summary'),
                '3': ('hsn', 'HSN Summary'),
                '4': ('all', 'All Three')
            }
            type_code, type_name = types[choice]
            print(f"  ✓ Selected: {type_name}")
            return type_code
        print("  ❌ Please enter 1, 2, 3, or 4")


def get_output_directory(period_month, period_year):
    """Get or create output directory"""
    period_str = f"{period_year}_{period_month:02d}"
    default_dir = f"exports/GSTR1_{period_str}"
    
    print("\n" + "-" * 80)
    print("OUTPUT DIRECTORY")
    print("-" * 80)
    print(f"Default: {default_dir}")
    
    custom_dir = input("Press Enter for default or enter custom path: ").strip()
    
    if custom_dir:
        output_dir = custom_dir
    else:
        output_dir = default_dir
    
    # Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    print(f"  ✓ Output directory: {output_dir}")
    
    return output_dir


def main():
    """Main execution function"""
    print_banner()
    
    # Validate configuration
    try:
        config.validate_config()
        print("✓ Configuration validated\n")
    except ValueError as e:
        print(f"❌ Configuration error:\n{e}\n")
        print("Please check your .env file and credentials.json")
        sys.exit(1)
    
    # Initialize components
    try:
        print("Connecting to Google Sheets...")
        sheets = SheetsManager()
        exporter = GSTR1Exporter(sheets)
        print("✓ Connected successfully\n")
    except Exception as e:
        print(f"❌ Connection error: {str(e)}\n")
        sys.exit(1)
    
    # Get user input
    period_month, period_year = get_period_input()
    export_type = get_export_type()
    output_dir = get_output_directory(period_month, period_year)
    
    # Confirm and execute
    print("\n" + "=" * 80)
    print("GENERATING EXPORTS...")
    print("=" * 80 + "\n")
    
    period_str = f"{period_year}_{period_month:02d}"
    
    try:
        if export_type == 'b2b':
            output_path = os.path.join(output_dir, f"B2B_Invoices_{period_str}.csv")
            result = exporter.export_b2b(period_month, period_year, output_path)
            
            if result['success']:
                print(f"✓ {result['message']}")
                print(f"  Invoices: {result['invoice_count']}")
                print(f"  Rows: {result['row_count']}")
                print(f"  Total Taxable Value: Rs. {result['total_taxable_value']}")
                print(f"  File: {result['output_file']}")
            else:
                print(f"❌ {result['message']}")
        
        elif export_type == 'b2c':
            output_path = os.path.join(output_dir, f"B2C_Small_{period_str}.csv")
            result = exporter.export_b2c_small(period_month, period_year, output_path)
            
            if result['success']:
                print(f"✓ {result['message']}")
                print(f"  Invoices: {result['invoice_count']}")
                print(f"  Summary Rows: {result['row_count']}")
                print(f"  Total Taxable Value: Rs. {result['total_taxable_value']}")
                print(f"  File: {result['output_file']}")
            else:
                print(f"❌ {result['message']}")
        
        elif export_type == 'hsn':
            output_path = os.path.join(output_dir, f"HSN_Summary_{period_str}.csv")
            result = exporter.export_hsn_summary(period_month, period_year, output_path)
            
            if result['success']:
                print(f"✓ {result['message']}")
                print(f"  Unique HSN Codes: {result['unique_hsn_count']}")
                print(f"  Rows: {result['row_count']}")
                print(f"  Total Taxable Value: Rs. {result['total_taxable_value']}")
                print(f"  File: {result['output_file']}")
            else:
                print(f"❌ {result['message']}")
        
        else:  # all
            result = exporter.export_all(period_month, period_year, output_dir)
            
            if result['success']:
                print(f"✓ {result['message']}\n")
                
                if result['b2b']['success']:
                    print(f"B2B Invoices:")
                    print(f"  Invoices: {result['b2b']['invoice_count']}")
                    print(f"  Rows: {result['b2b']['row_count']}")
                    print(f"  Taxable Value: Rs. {result['b2b']['total_taxable_value']}")
                
                if result['b2c']['success']:
                    print(f"\nB2C Small:")
                    print(f"  Invoices: {result['b2c']['invoice_count']}")
                    print(f"  Summary Rows: {result['b2c']['row_count']}")
                
                if result['hsn']['success']:
                    print(f"\nHSN Summary:")
                    print(f"  Unique HSN Codes: {result['hsn']['unique_hsn_count']}")
                    print(f"  Rows: {result['hsn']['row_count']}")
                
                print(f"\nAll files saved in: {output_dir}")
                print(f"Report: {result['report_file']}")
            else:
                print(f"❌ {result['message']}")
        
        print("\n" + "=" * 80)
        print("✓ EXPORT COMPLETED")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Export failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
