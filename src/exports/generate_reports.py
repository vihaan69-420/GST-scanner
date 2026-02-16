"""
Standalone Reports Generator Script
Interactive command-line interface for generating operational reports

Usage:
    python generate_reports.py

The script will interactively prompt for:
- Report type
- Period (if applicable)
- Output directory
"""
import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from sheets.sheets_manager import SheetsManager
from exports.operational_reports import OperationalReporter


def print_banner():
    """Print script banner"""
    print("=" * 80)
    print("OPERATIONAL REPORTS GENERATOR")
    print("=" * 80)
    print("Generate internal operational reports for monitoring and auditing")
    print("")


def get_report_type():
    """Get report type from user"""
    print("-" * 80)
    print("REPORT TYPE")
    print("-" * 80)
    print("1️⃣  Processing Statistics (all invoices)")
    print("2️⃣  GST Amount Summary (monthly)")
    print("3️⃣  Duplicate Invoice Attempts")
    print("4️⃣  Correction Frequency Analysis")
    print("5️⃣  Comprehensive Report (all reports for a period)")
    print("")
    
    while True:
        choice = input("Select report type (1-5): ").strip()
        if choice in ['1', '2', '3', '4', '5']:
            types = {
                '1': ('stats', 'Processing Statistics'),
                '2': ('gst', 'GST Amount Summary'),
                '3': ('duplicates', 'Duplicate Attempts'),
                '4': ('corrections', 'Correction Analysis'),
                '5': ('comprehensive', 'Comprehensive Report')
            }
            type_code, type_name = types[choice]
            print(f"  ✓ Selected: {type_name}")
            return type_code
        print("  ❌ Please enter 1, 2, 3, 4, or 5")


def get_period_input():
    """Get period (month and year) from user"""
    print("\n" + "-" * 80)
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


def get_output_directory(report_type, period_month=None, period_year=None):
    """Get or create output directory"""
    if period_month and period_year:
        period_str = f"{period_year}_{period_month:02d}"
        default_dir = f"exports/Reports_{period_str}"
    else:
        default_dir = "exports/Reports"
    
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
        reporter = OperationalReporter(sheets)
        print("✓ Connected successfully\n")
    except Exception as e:
        print(f"❌ Connection error: {str(e)}\n")
        sys.exit(1)
    
    # Get report type
    report_type = get_report_type()
    
    # Get period if needed
    period_month = None
    period_year = None
    if report_type in ['gst', 'duplicates', 'comprehensive']:
        period_month, period_year = get_period_input()
    
    # Get output directory
    output_dir = get_output_directory(report_type, period_month, period_year)
    
    # Generate report
    print("\n" + "=" * 80)
    print("GENERATING REPORT...")
    print("=" * 80 + "\n")
    
    try:
        if report_type == 'stats':
            result = reporter.generate_processing_stats()
            
            if result['success']:
                print("✓ Processing Statistics Generated\n")
                print(f"Total Invoices: {result['total_invoices']}")
                print("\nValidation Status Breakdown:")
                for status, count in result['status_breakdown'].items():
                    pct = result['status_percentages'].get(status, 0)
                    print(f"  {status}: {count} ({pct:.1f}%)")
                
                if result['top_errors']:
                    print("\nTop Error Types:")
                    for error in result['top_errors']:
                        print(f"  • {error['type']}: {error['count']} occurrences")
                
                # Save to JSON
                import json
                output_path = os.path.join(output_dir, "Processing_Statistics.json")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"\n📄 Report saved to: {output_path}")
            else:
                print(f"❌ {result['message']}")
        
        elif report_type == 'gst':
            result = reporter.generate_gst_summary(period_month, period_year)
            
            if result['success']:
                print(f"✓ GST Summary Generated - {result['period']}\n")
                print(f"Total Invoices: {result['invoice_count']}")
                print(f"Total Taxable Value: Rs. {result['total_taxable_value']:,.2f}")
                print(f"Total IGST: Rs. {result['total_igst']:,.2f}")
                print(f"Total CGST: Rs. {result['total_cgst']:,.2f}")
                print(f"Total SGST: Rs. {result['total_sgst']:,.2f}")
                print(f"Total GST: Rs. {result['total_gst']:,.2f}")
                print(f"Average Invoice Value: Rs. {result['average_invoice_value']:,.2f}")
                
                # Save to JSON
                import json
                period_str = f"{period_year}_{period_month:02d}"
                output_path = os.path.join(output_dir, f"GST_Summary_{period_str}.json")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"\n📄 Report saved to: {output_path}")
            else:
                print(f"❌ {result['message']}")
        
        elif report_type == 'duplicates':
            result = reporter.generate_duplicate_report(period_month, period_year)
            
            if result['success']:
                print(f"✓ Duplicate Attempts Report - {result['period']}\n")
                print(f"Total Attempts: {result['total_attempts']}")
                print(f"Unique Invoices: {result['unique_invoices']}")
                print(f"Unique Users: {result['unique_users']}")
                
                if result.get('most_attempted_invoices'):
                    print("\nMost Attempted Invoices:")
                    for item in result['most_attempted_invoices'][:5]:
                        print(f"  • {item['invoice_no']}: {item['attempts']} attempts")
                
                # Save to JSON
                import json
                period_str = f"{period_year}_{period_month:02d}"
                output_path = os.path.join(output_dir, f"Duplicate_Attempts_{period_str}.json")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"\n📄 Report saved to: {output_path}")
            else:
                print(f"❌ {result['message']}")
        
        elif report_type == 'corrections':
            result = reporter.generate_correction_analysis()
            
            if result['success']:
                print("✓ Correction Analysis Generated\n")
                print(f"Total Errors: {result['total_errors']}")
                print(f"Total Warnings: {result['total_warnings']}")
                print(f"Unique Error Types: {result['unique_error_types']}")
                print(f"Unique Warning Types: {result['unique_warning_types']}")
                
                if result.get('top_errors'):
                    print("\nTop Error Types:")
                    for error in result['top_errors'][:5]:
                        print(f"  • {error['error_type']}: {error['count']} ({error['percentage']:.1f}%)")
                
                if result.get('top_warnings'):
                    print("\nTop Warning Types:")
                    for warning in result['top_warnings'][:5]:
                        print(f"  • {warning['warning_type']}: {warning['count']} ({warning['percentage']:.1f}%)")
                
                # Save to JSON
                import json
                output_path = os.path.join(output_dir, "Correction_Analysis.json")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"\n📄 Report saved to: {output_path}")
            else:
                print(f"❌ {result['message']}")
        
        else:  # comprehensive
            result = reporter.generate_comprehensive_report(period_month, period_year, output_dir)
            
            if result['success']:
                print("✓ Comprehensive Report Generated\n")
                print("All reports have been generated:")
                print(f"  📄 JSON: {result['json_file']}")
                print(f"  📄 Text: {result['text_file']}")
                
                # Ask if user wants to view the text report
                view = input("\nView text report? (y/n): ").strip().lower()
                if view == 'y':
                    with open(result['text_file'], 'r', encoding='utf-8') as f:
                        print("\n" + "=" * 80)
                        print(f.read())
            else:
                print(f"❌ Generation failed")
        
        print("\n" + "=" * 80)
        print("✓ REPORT GENERATION COMPLETED")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Report generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
