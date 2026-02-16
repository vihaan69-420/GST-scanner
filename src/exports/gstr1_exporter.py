"""
GSTR-1 Exporter
Generates GSTR-1 export files (B2B, B2C Small, HSN Summary) from invoice data
in Google Sheets, formatted for GST portal upload.
"""
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional
from calendar import month_name

import config


class GSTR1Exporter:
    """Export invoice data in GSTR-1 format"""

    def __init__(self, sheets_manager):
        """
        Initialize with a SheetsManager instance.

        Args:
            sheets_manager: Connected SheetsManager (shared or per-tenant)
        """
        self.sheets_manager = sheets_manager

    # ────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────

    def export_b2b(self, month: int, year: int, output_path: str = None) -> Dict:
        """
        Export B2B invoices (buyer has GSTIN) for a period.

        Args:
            month: Month number (1-12)
            year:  Year (e.g. 2026)
            output_path: Where to write the CSV; auto-generated if None

        Returns:
            Dict with keys: success, message, output_file, invoice_count, data
        """
        try:
            invoices = self._fetch_invoices(month, year)
            b2b = [inv for inv in invoices if self._is_b2b(inv)]

            if not b2b:
                return {
                    'success': True,
                    'message': f'No B2B invoices for {month_name[month]} {year}',
                    'output_file': None,
                    'invoice_count': 0,
                    'data': [],
                }

            if output_path is None:
                output_path = os.path.join(
                    config.EXPORT_FOLDER,
                    f"B2B_Invoices_{year}_{month:02d}.csv",
                )
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            rows = self._format_b2b_rows(b2b)
            self._write_csv(output_path, self._b2b_headers(), rows)

            return {
                'success': True,
                'message': f'Exported {len(b2b)} B2B invoices for {month_name[month]} {year}',
                'output_file': output_path,
                'invoice_count': len(b2b),
                'data': rows,
            }
        except Exception as e:
            return {'success': False, 'message': f'B2B export failed: {e}',
                    'output_file': None, 'invoice_count': 0, 'data': []}

    def export_b2c_small(self, month: int, year: int, output_path: str = None) -> Dict:
        """
        Export B2C Small invoices (buyer has no GSTIN, intra-state).

        Returns:
            Dict with keys: success, message, output_file, invoice_count, data
        """
        try:
            invoices = self._fetch_invoices(month, year)
            b2c = [inv for inv in invoices if self._is_b2c(inv)]

            if not b2c:
                return {
                    'success': True,
                    'message': f'No B2C invoices for {month_name[month]} {year}',
                    'output_file': None,
                    'invoice_count': 0,
                    'data': [],
                }

            if output_path is None:
                output_path = os.path.join(
                    config.EXPORT_FOLDER,
                    f"B2C_Small_{year}_{month:02d}.csv",
                )
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            rows = self._format_b2c_rows(b2c)
            self._write_csv(output_path, self._b2c_headers(), rows)

            return {
                'success': True,
                'message': f'Exported {len(b2c)} B2C invoices for {month_name[month]} {year}',
                'output_file': output_path,
                'invoice_count': len(b2c),
                'data': rows,
            }
        except Exception as e:
            return {'success': False, 'message': f'B2C export failed: {e}',
                    'output_file': None, 'invoice_count': 0, 'data': []}

    def export_hsn_summary(self, month: int, year: int, output_path: str = None) -> Dict:
        """
        Export HSN-wise summary for a period.

        Returns:
            Dict with keys: success, message, output_file, unique_hsn_count, data
        """
        try:
            invoices = self._fetch_invoices(month, year)
            invoice_numbers = [inv.get('Invoice_No', '') for inv in invoices]

            if not invoice_numbers:
                return {
                    'success': True,
                    'message': f'No invoices for {month_name[month]} {year}',
                    'output_file': None,
                    'unique_hsn_count': 0,
                    'data': [],
                }

            line_items_map = self.sheets_manager.get_line_items_by_invoice_numbers(invoice_numbers)
            hsn_summary = self._aggregate_hsn(line_items_map)

            if output_path is None:
                output_path = os.path.join(
                    config.EXPORT_FOLDER,
                    f"HSN_Summary_{year}_{month:02d}.csv",
                )
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            rows = self._format_hsn_rows(hsn_summary)
            self._write_csv(output_path, self._hsn_headers(), rows)

            return {
                'success': True,
                'message': f'Exported HSN summary ({len(hsn_summary)} codes) for {month_name[month]} {year}',
                'output_file': output_path,
                'unique_hsn_count': len(hsn_summary),
                'data': rows,
            }
        except Exception as e:
            return {'success': False, 'message': f'HSN export failed: {e}',
                    'output_file': None, 'unique_hsn_count': 0, 'data': []}

    def export_all(self, month: int, year: int, output_dir: str = None) -> Dict:
        """
        Export all three GSTR-1 sections + a summary report.

        Returns:
            Dict with keys: success, b2b, b2c, hsn, report_file
        """
        if output_dir is None:
            output_dir = os.path.join(config.EXPORT_FOLDER, f"GSTR1_{year}_{month:02d}")
        os.makedirs(output_dir, exist_ok=True)

        period_str = f"{year}_{month:02d}"

        b2b = self.export_b2b(month, year, os.path.join(output_dir, f"B2B_Invoices_{period_str}.csv"))
        b2c = self.export_b2c_small(month, year, os.path.join(output_dir, f"B2C_Small_{period_str}.csv"))
        hsn = self.export_hsn_summary(month, year, os.path.join(output_dir, f"HSN_Summary_{period_str}.csv"))

        # Write summary report
        report_path = os.path.join(output_dir, f"Export_Report_{period_str}.txt")
        self._write_export_report(report_path, month, year, b2b, b2c, hsn)

        return {
            'success': True,
            'b2b': b2b,
            'b2c': b2c,
            'hsn': hsn,
            'report_file': report_path,
        }

    # ────────────────────────────────────────────────────────────
    # Private helpers
    # ────────────────────────────────────────────────────────────

    def _fetch_invoices(self, month: int, year: int) -> List[Dict]:
        """Fetch invoices and optionally exclude ERROR status."""
        status_filter = None
        if config.EXCLUDE_ERROR_INVOICES:
            status_filter = ['OK', 'WARNING']
        return self.sheets_manager.get_invoices_by_period(month, year, status_filter=status_filter)

    @staticmethod
    def _is_b2b(inv: Dict) -> bool:
        gstin = (inv.get('Buyer_GSTIN') or '').strip()
        return len(gstin) >= 15

    @staticmethod
    def _is_b2c(inv: Dict) -> bool:
        gstin = (inv.get('Buyer_GSTIN') or '').strip()
        return len(gstin) < 15

    # ── B2B formatting ──

    @staticmethod
    def _b2b_headers() -> List[str]:
        return [
            'GSTIN of Recipient', 'Receiver Name', 'Invoice Number', 'Invoice Date',
            'Invoice Value', 'Place of Supply', 'Reverse Charge', 'Invoice Type',
            'Rate', 'Taxable Value', 'Cess Amount',
            'Integrated Tax Amount', 'Central Tax Amount', 'State/UT Tax Amount',
        ]

    @staticmethod
    def _format_b2b_rows(invoices: List[Dict]) -> List[List[str]]:
        rows = []
        for inv in invoices:
            rows.append([
                inv.get('Buyer_GSTIN', ''),
                inv.get('Buyer_Name', ''),
                inv.get('Invoice_No', ''),
                inv.get('Invoice_Date', ''),
                inv.get('Invoice_Value', ''),
                inv.get('Place_Of_Supply', ''),
                inv.get('Reverse_Charge', 'N'),
                inv.get('Invoice_Type', 'Regular'),
                inv.get('Total_GST', ''),
                inv.get('Total_Taxable_Value', ''),
                '0',
                inv.get('IGST_Total', '0'),
                inv.get('CGST_Total', '0'),
                inv.get('SGST_Total', '0'),
            ])
        return rows

    # ── B2C formatting ──

    @staticmethod
    def _b2c_headers() -> List[str]:
        return [
            'Type', 'Place of Supply', 'Rate', 'Taxable Value',
            'Cess Amount', 'Integrated Tax Amount',
            'Central Tax Amount', 'State/UT Tax Amount',
        ]

    @staticmethod
    def _format_b2c_rows(invoices: List[Dict]) -> List[List[str]]:
        rows = []
        for inv in invoices:
            rows.append([
                'OE',
                inv.get('Place_Of_Supply', ''),
                inv.get('Total_GST', ''),
                inv.get('Total_Taxable_Value', ''),
                '0',
                inv.get('IGST_Total', '0'),
                inv.get('CGST_Total', '0'),
                inv.get('SGST_Total', '0'),
            ])
        return rows

    # ── HSN formatting ──

    @staticmethod
    def _hsn_headers() -> List[str]:
        return [
            'HSN', 'Description', 'UQC', 'Total Quantity',
            'Total Taxable Value', 'Integrated Tax Amount',
            'Central Tax Amount', 'State/UT Tax Amount', 'Cess Amount',
        ]

    @staticmethod
    def _aggregate_hsn(line_items_map: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """Group line items by HSN code and aggregate."""
        hsn_agg: Dict[str, Dict] = {}
        for items in line_items_map.values():
            for item in items:
                code = (item.get('HSN') or '').strip()
                if not code:
                    continue
                if code not in hsn_agg:
                    hsn_agg[code] = {
                        'HSN': code,
                        'Description': item.get('Item_Description', ''),
                        'UQC': item.get('UOM', ''),
                        'Total_Quantity': 0.0,
                        'Total_Taxable_Value': 0.0,
                        'IGST': 0.0,
                        'CGST': 0.0,
                        'SGST': 0.0,
                        'Cess': 0.0,
                    }
                agg = hsn_agg[code]
                agg['Total_Quantity'] += _float(item.get('Qty', 0))
                agg['Total_Taxable_Value'] += _float(item.get('Taxable_Value', 0))
                agg['IGST'] += _float(item.get('IGST_Amount', 0))
                agg['CGST'] += _float(item.get('CGST_Amount', 0))
                agg['SGST'] += _float(item.get('SGST_Amount', 0))
                agg['Cess'] += _float(item.get('Cess_Amount', 0))
        return hsn_agg

    @staticmethod
    def _format_hsn_rows(hsn_summary: Dict[str, Dict]) -> List[List[str]]:
        rows = []
        for agg in hsn_summary.values():
            rows.append([
                agg['HSN'],
                agg['Description'],
                agg['UQC'],
                f"{agg['Total_Quantity']:.2f}",
                f"{agg['Total_Taxable_Value']:.2f}",
                f"{agg['IGST']:.2f}",
                f"{agg['CGST']:.2f}",
                f"{agg['SGST']:.2f}",
                f"{agg['Cess']:.2f}",
            ])
        return rows

    # ── CSV / report writers ──

    @staticmethod
    def _write_csv(path: str, headers: List[str], rows: List[List[str]]):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

    @staticmethod
    def _write_export_report(path: str, month: int, year: int,
                             b2b: Dict, b2c: Dict, hsn: Dict):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"GSTR-1 Export Report\n")
            f.write(f"Period: {month_name[month]} {year}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"B2B Invoices: {b2b.get('invoice_count', 0)}\n")
            f.write(f"B2C Invoices: {b2c.get('invoice_count', 0)}\n")
            f.write(f"HSN Codes:    {hsn.get('unique_hsn_count', 0)}\n")


def _float(val) -> float:
    """Safe float conversion."""
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0
