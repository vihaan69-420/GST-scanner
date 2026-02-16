"""
Standalone GSTR-3B Export Script
Interactive command-line interface for generating GSTR-3B summary

Usage:
    python export_gstr3b.py

The script will interactively prompt for:
- Month (1-12)
- Year (e.g., 2026)
- Output directory
"""
import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from sheets.sheets_manager import SheetsManager
from exports.gstr3b_generator import GSTR3BGenerator


def print_banner():
    """Print script banner"""
    print("=" * 80)
    print("GSTR-3B SUMMARY GENERATOR")
    print("=" * 80)
    print("Generate monthly tax liability summary for GSTR-3B filing")
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


def get_output_directory(period_month, period_year):
    """Get or create output directory"""
    period_str = f"{period_year}_{period_month:02d}"
    default_dir = f"exports/GSTR3B_{period_str}"
    
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
        generator = GSTR3BGenerator(sheets)
        print("✓ Connected successfully\n")
    except Exception as e:
        print(f"❌ Connection error: {str(e)}\n")
        sys.exit(1)
    
    # Get user input
    period_month, period_year = get_period_input()
    output_dir = get_output_directory(period_month, period_year)
    
    # Generate paths
    period_str = f"{period_year}_{period_month:02d}"
    json_path = os.path.join(output_dir, f"GSTR3B_Summary_{period_str}.json")
    text_path = os.path.join(output_dir, f"GSTR3B_Report_{period_str}.txt")
    
    # Confirm and execute
    print("\n" + "=" * 80)
    print("GENERATING GSTR-3B SUMMARY...")
    print("=" * 80 + "\n")
    
    try:
        # Generate JSON summary
        result = generator.generate_summary(period_month, period_year, json_path)
        
        if not result['success']:
            print(f"❌ {result['message']}")
            sys.exit(1)
        
        summary = result['data']['summary']
        
        # Generate text report
        report = generator.generate_formatted_report(period_month, period_year, text_path)
        
        # Display summary
        print(f"✓ {result['message']}\n")
        print(f"Period: {result['data']['period_name']}")
        print(f"Total Invoices: {summary['total_invoices']}")
        print(f"  Normal Supplies: {summary['normal_supply_invoices']}")
        print(f"  Reverse Charge: {summary['reverse_charge_invoices']}")
        print("")
        
        outward = summary['outward_supplies']
        print("Outward Supplies:")
        print(f"  Taxable Value: Rs. {outward['taxable_value']:,.2f}")
        print(f"  IGST: Rs. {outward['integrated_tax']:,.2f}")
        print(f"  CGST: Rs. {outward['central_tax']:,.2f}")
        print(f"  SGST: Rs. {outward['state_ut_tax']:,.2f}")
        print("")
        
        total_tax = summary['total_tax_liability']
        print(f"Total Tax Liability: Rs. {total_tax['total']:,.2f}")
        print("")
        
        print("Files generated:")
        print(f"  📄 JSON Summary: {json_path}")
        print(f"  📄 Text Report: {text_path}")
        
        print("\n" + "=" * 80)
        print("✓ GENERATION COMPLETED")
        print("=" * 80)
        
        # Ask if user wants to view the report
        view = input("\nView full report? (y/n): ").strip().lower()
        if view == 'y':
            print("\n" + "=" * 80)
            print(report)
        
    except Exception as e:
        print(f"\n❌ Generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
