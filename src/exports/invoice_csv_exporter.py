"""
Invoice CSV Exporter
Generates CSV files that match the exact Google Sheets output.
Two files: invoice header (same columns as Sheets) and line items.
"""
import csv
import os
from datetime import datetime
from typing import Dict, List, Tuple
import config


class InvoiceCSVExporter:
    """Export invoice data to CSV, matching Google Sheets format exactly."""
    
    # Tier 1 columns (first 24) -- same as what gets saved to the sheet
    HEADER_COLUMNS = config.SHEET_COLUMNS[:24]
    ITEM_COLUMNS = config.LINE_ITEM_COLUMNS

    def __init__(self):
        os.makedirs(config.TEMP_FOLDER, exist_ok=True)
    
    def export_invoice(self, invoice_data: Dict, line_items: List[Dict] = None) -> Tuple[str, str]:
        """
        Export invoice header + line items as two CSV files.
        
        Returns:
            Tuple of (header_csv_path, line_items_csv_path or None)
        """
        header_path = self.export_header(invoice_data)
        items_path = None
        if line_items:
            items_path = self.export_line_items(invoice_data, line_items)
        return header_path, items_path

    def export_header(self, invoice_data: Dict, output_path: str = None) -> str:
        """
        Export invoice header CSV with the exact same columns saved to Google Sheets.
        """
        if not output_path:
            invoice_no = invoice_data.get('Invoice_No', 'UNKNOWN').replace('/', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Invoice_{invoice_no}_{timestamp}_header.csv"
            output_path = os.path.join(config.TEMP_FOLDER, filename)
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.HEADER_COLUMNS)
            writer.writerow([invoice_data.get(col, '') for col in self.HEADER_COLUMNS])
        
        print(f"[CSV] Invoice header export ({len(self.HEADER_COLUMNS)} cols): {output_path}")
        return output_path
    
    def export_line_items(self, invoice_data: Dict, line_items: List[Dict], output_path: str = None) -> str:
        """
        Export line items CSV with the exact same columns saved to Google Sheets.
        """
        if not output_path:
            invoice_no = invoice_data.get('Invoice_No', 'UNKNOWN').replace('/', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Invoice_{invoice_no}_{timestamp}_items.csv"
            output_path = os.path.join(config.TEMP_FOLDER, filename)
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.ITEM_COLUMNS)
            for item in line_items:
                writer.writerow([item.get(col, '') for col in self.ITEM_COLUMNS])
        
        print(f"[CSV] Line items export ({len(line_items)} rows, {len(self.ITEM_COLUMNS)} cols): {output_path}")
        return output_path

    # Backward-compatible alias
    def export_invoice_simple(self, invoice_data: Dict, output_path: str = None) -> str:
        return self.export_header(invoice_data, output_path)
