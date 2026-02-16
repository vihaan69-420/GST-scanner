"""
GSTR-3B Generator
Generates monthly GSTR-3B tax liability summary from invoice data.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from calendar import month_name

import config


class GSTR3BGenerator:
    """Generate GSTR-3B monthly summary"""

    def __init__(self, sheets_manager):
        """
        Initialize with a SheetsManager instance.

        Args:
            sheets_manager: Connected SheetsManager (shared or per-tenant)
        """
        self.sheets_manager = sheets_manager

    def generate_summary(self, month: int, year: int, output_path: str = None) -> Dict:
        """
        Generate GSTR-3B summary for a period.

        Args:
            month: Month (1-12)
            year:  Year
            output_path: Optional path to write JSON result

        Returns:
            Dict with keys: success, message, data (containing summary)
        """
        try:
            invoices = self._fetch_invoices(month, year)

            if not invoices:
                return {
                    'success': True,
                    'message': f'No invoices for {month_name[month]} {year}',
                    'data': {'summary': self._empty_summary(month, year)},
                }

            summary = self._compute_summary(invoices, month, year)

            result = {
                'success': True,
                'message': f'GSTR-3B summary for {month_name[month]} {year}',
                'data': {'summary': summary},
            }

            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

            return result

        except Exception as e:
            return {'success': False, 'message': f'GSTR-3B generation failed: {e}', 'data': None}

    def generate_formatted_report(self, month: int, year: int, output_path: str = None) -> Dict:
        """
        Generate a human-readable text report.

        Args:
            month, year: Period
            output_path: Where to write the text file

        Returns:
            Dict with keys: success, text, output_file
        """
        result = self.generate_summary(month, year)
        if not result['success']:
            return result

        summary = result['data']['summary']
        text = self._format_text(summary, month, year)

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)

        return {'success': True, 'text': text, 'output_file': output_path}

    # ────────────────────────────────────────────────────────────
    # Private helpers
    # ────────────────────────────────────────────────────────────

    def _fetch_invoices(self, month: int, year: int) -> List[Dict]:
        status_filter = None
        if config.EXCLUDE_ERROR_INVOICES:
            status_filter = ['OK', 'WARNING']
        return self.sheets_manager.get_invoices_by_period(month, year, status_filter=status_filter)

    def _compute_summary(self, invoices: List[Dict], month: int, year: int) -> Dict:
        total_invoices = len(invoices)
        b2b = [i for i in invoices if self._is_b2b(i)]
        b2c = [i for i in invoices if not self._is_b2b(i)]

        igst = sum(_float(i.get('IGST_Total', 0)) for i in invoices)
        cgst = sum(_float(i.get('CGST_Total', 0)) for i in invoices)
        sgst = sum(_float(i.get('SGST_Total', 0)) for i in invoices)
        taxable = sum(_float(i.get('Total_Taxable_Value', 0)) for i in invoices)
        invoice_value = sum(_float(i.get('Invoice_Value', 0)) for i in invoices)

        return {
            'period': f"{month_name[month]} {year}",
            'total_invoices': total_invoices,
            'b2b_count': len(b2b),
            'b2c_count': len(b2c),
            'total_taxable_value': round(taxable, 2),
            'total_invoice_value': round(invoice_value, 2),
            'total_tax_liability': {
                'igst': round(igst, 2),
                'cgst': round(cgst, 2),
                'sgst': round(sgst, 2),
                'total': round(igst + cgst + sgst, 2),
            },
        }

    def _empty_summary(self, month: int, year: int) -> Dict:
        return {
            'period': f"{month_name[month]} {year}",
            'total_invoices': 0,
            'b2b_count': 0,
            'b2c_count': 0,
            'total_taxable_value': 0.0,
            'total_invoice_value': 0.0,
            'total_tax_liability': {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'total': 0.0},
        }

    @staticmethod
    def _is_b2b(inv: Dict) -> bool:
        return len((inv.get('Buyer_GSTIN') or '').strip()) >= 15

    @staticmethod
    def _format_text(summary: Dict, month: int, year: int) -> str:
        tax = summary['total_tax_liability']
        lines = [
            f"GSTR-3B Summary Report",
            f"Period: {month_name[month]} {year}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 50,
            "",
            f"Total Invoices:      {summary['total_invoices']}",
            f"  B2B:               {summary['b2b_count']}",
            f"  B2C:               {summary['b2c_count']}",
            "",
            f"Total Taxable Value: Rs. {summary['total_taxable_value']:,.2f}",
            f"Total Invoice Value: Rs. {summary['total_invoice_value']:,.2f}",
            "",
            "Tax Liability:",
            f"  IGST:  Rs. {tax['igst']:,.2f}",
            f"  CGST:  Rs. {tax['cgst']:,.2f}",
            f"  SGST:  Rs. {tax['sgst']:,.2f}",
            f"  TOTAL: Rs. {tax['total']:,.2f}",
        ]
        return "\n".join(lines)


def _float(val) -> float:
    """Safe float conversion."""
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0
