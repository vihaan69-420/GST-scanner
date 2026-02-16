"""
Operational Reports
Generates processing statistics, GST summaries, duplicate reports,
correction analysis, and comprehensive reports.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from calendar import month_name
from collections import Counter

import config


class OperationalReporter:
    """Generate operational reports from Google Sheets data"""

    def __init__(self, sheets_manager):
        """
        Initialize with a SheetsManager instance.

        Args:
            sheets_manager: Connected SheetsManager (shared or per-tenant)
        """
        self.sheets_manager = sheets_manager

    # ────────────────────────────────────────────────────────────
    # Report Type 1: Processing Statistics
    # ────────────────────────────────────────────────────────────

    def generate_processing_stats(self, month: int = None, year: int = None) -> Dict:
        """
        Generate processing statistics.

        When month/year are None, returns stats across all invoices.

        Returns:
            Dict with: success, total_invoices, status_breakdown,
                       status_percentages, top_errors, message
        """
        try:
            invoices = self._get_all_invoices() if month is None else self._fetch_invoices(month, year)
            total = len(invoices)

            if total == 0:
                return {
                    'success': True,
                    'message': 'No invoices found',
                    'total_invoices': 0,
                    'status_breakdown': {},
                    'status_percentages': {},
                    'top_errors': [],
                }

            statuses = [inv.get('Validation_Status', 'UNKNOWN') for inv in invoices]
            breakdown = dict(Counter(statuses))
            percentages = {s: round(c / total * 100, 1) for s, c in breakdown.items()}

            # Top errors from validation remarks
            error_counter: Counter = Counter()
            for inv in invoices:
                remarks = inv.get('Validation_Remarks', '')
                if remarks:
                    for part in remarks.split(';'):
                        part = part.strip()
                        if part:
                            error_counter[part] += 1

            top_errors = [{'type': err, 'count': cnt}
                          for err, cnt in error_counter.most_common(10)]

            return {
                'success': True,
                'message': f'Stats for {total} invoices',
                'total_invoices': total,
                'status_breakdown': breakdown,
                'status_percentages': percentages,
                'top_errors': top_errors,
            }
        except Exception as e:
            return {'success': False, 'message': f'Stats failed: {e}'}

    # ────────────────────────────────────────────────────────────
    # Report Type 2: GST Summary (monthly)
    # ────────────────────────────────────────────────────────────

    def generate_gst_summary(self, month: int, year: int) -> Dict:
        """
        Generate GST summary for a period.

        Returns:
            Dict with: success, period, total_invoices, total_taxable,
                       tax_breakdown, message
        """
        try:
            invoices = self._fetch_invoices(month, year)
            total = len(invoices)

            if total == 0:
                return {
                    'success': True,
                    'message': f'No invoices for {month_name[month]} {year}',
                    'period': f'{month_name[month]} {year}',
                    'total_invoices': 0,
                    'total_taxable': 0.0,
                    'tax_breakdown': {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'total': 0.0},
                }

            taxable = sum(_float(i.get('Total_Taxable_Value', 0)) for i in invoices)
            igst = sum(_float(i.get('IGST_Total', 0)) for i in invoices)
            cgst = sum(_float(i.get('CGST_Total', 0)) for i in invoices)
            sgst = sum(_float(i.get('SGST_Total', 0)) for i in invoices)

            return {
                'success': True,
                'message': f'GST summary for {month_name[month]} {year}',
                'period': f'{month_name[month]} {year}',
                'total_invoices': total,
                'total_taxable': round(taxable, 2),
                'tax_breakdown': {
                    'igst': round(igst, 2),
                    'cgst': round(cgst, 2),
                    'sgst': round(sgst, 2),
                    'total': round(igst + cgst + sgst, 2),
                },
            }
        except Exception as e:
            return {'success': False, 'message': f'GST summary failed: {e}'}

    # ────────────────────────────────────────────────────────────
    # Report Type 3: Duplicate Attempts
    # ────────────────────────────────────────────────────────────

    def generate_duplicate_report(self, month: int = None, year: int = None) -> Dict:
        """
        Report on duplicate invoice attempts.

        Returns:
            Dict with: success, total_duplicates, details, message
        """
        try:
            invoices = self._get_all_invoices() if month is None else self._fetch_invoices(month, year)
            duplicates = [inv for inv in invoices
                          if (inv.get('Duplicate_Status') or '').upper() not in ('', 'UNIQUE')]

            details = []
            for d in duplicates:
                details.append({
                    'invoice_no': d.get('Invoice_No', ''),
                    'date': d.get('Invoice_Date', ''),
                    'seller': d.get('Seller_Name', ''),
                    'status': d.get('Duplicate_Status', ''),
                })

            period = f'{month_name[month]} {year}' if month else 'All time'
            return {
                'success': True,
                'message': f'{len(duplicates)} duplicate attempt(s) ({period})',
                'total_duplicates': len(duplicates),
                'details': details,
            }
        except Exception as e:
            return {'success': False, 'message': f'Duplicate report failed: {e}'}

    # ────────────────────────────────────────────────────────────
    # Report Type 4: Correction Analysis
    # ────────────────────────────────────────────────────────────

    def generate_correction_analysis(self, month: int = None, year: int = None) -> Dict:
        """
        Report on manual corrections made.

        Returns:
            Dict with: success, total_corrected, field_frequency, message
        """
        try:
            invoices = self._get_all_invoices() if month is None else self._fetch_invoices(month, year)
            corrected = [inv for inv in invoices
                         if (inv.get('Has_Corrections') or '').upper() == 'YES']

            field_counter: Counter = Counter()
            for inv in corrected:
                fields = inv.get('Corrected_Fields', '')
                if fields:
                    for f in fields.split(','):
                        f = f.strip()
                        if f:
                            field_counter[f] += 1

            return {
                'success': True,
                'message': f'{len(corrected)} corrected invoice(s)',
                'total_corrected': len(corrected),
                'total_invoices': len(invoices),
                'correction_rate': round(len(corrected) / max(len(invoices), 1) * 100, 1),
                'field_frequency': dict(field_counter.most_common(20)),
            }
        except Exception as e:
            return {'success': False, 'message': f'Correction analysis failed: {e}'}

    # ────────────────────────────────────────────────────────────
    # Report Type 5: Comprehensive Report
    # ────────────────────────────────────────────────────────────

    def generate_comprehensive_report(self, month: int, year: int, output_dir: str = None) -> Dict:
        """
        Generate a comprehensive report combining all report types.

        Returns:
            Dict with: success, json_file, text_file, data, message
        """
        try:
            stats = self.generate_processing_stats(month, year)
            gst = self.generate_gst_summary(month, year)
            dupes = self.generate_duplicate_report(month, year)
            corrections = self.generate_correction_analysis(month, year)

            combined = {
                'period': f'{month_name[month]} {year}',
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'processing_stats': stats,
                'gst_summary': gst,
                'duplicate_report': dupes,
                'correction_analysis': corrections,
            }

            if output_dir is None:
                output_dir = os.path.join(config.EXPORT_FOLDER, f"Reports_{year}_{month:02d}")
            os.makedirs(output_dir, exist_ok=True)

            period_str = f"{year}_{month:02d}"
            json_file = os.path.join(output_dir, f"Comprehensive_Report_{period_str}.json")
            text_file = os.path.join(output_dir, f"Comprehensive_Report_{period_str}.txt")

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(combined, f, indent=2, ensure_ascii=False)

            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(self._format_comprehensive_text(combined))

            return {
                'success': True,
                'message': 'Comprehensive report generated',
                'json_file': json_file,
                'text_file': text_file,
                'data': combined,
            }
        except Exception as e:
            return {'success': False, 'message': f'Comprehensive report failed: {e}'}

    # ────────────────────────────────────────────────────────────
    # Data access
    # ────────────────────────────────────────────────────────────

    def _fetch_invoices(self, month: int, year: int) -> List[Dict]:
        return self.sheets_manager.get_invoices_by_period(month, year)

    def _get_all_invoices(self) -> List[Dict]:
        """Fetch all invoices across all periods."""
        try:
            headers = self.sheets_manager.worksheet.row_values(1)
            all_rows = self.sheets_manager.worksheet.get_all_values()
            invoices = []
            for row in all_rows[1:]:
                inv = {}
                for i, header in enumerate(headers):
                    inv[header] = row[i] if i < len(row) else ''
                invoices.append(inv)
            return invoices
        except Exception:
            return []

    # ────────────────────────────────────────────────────────────
    # Formatting
    # ────────────────────────────────────────────────────────────

    @staticmethod
    def _format_comprehensive_text(data: Dict) -> str:
        lines = [
            "COMPREHENSIVE REPORT",
            f"Period: {data['period']}",
            f"Generated: {data['generated_at']}",
            "=" * 60,
        ]

        # Stats section
        stats = data.get('processing_stats', {})
        lines.append(f"\n--- Processing Statistics ---")
        lines.append(f"Total Invoices: {stats.get('total_invoices', 0)}")
        for status, count in stats.get('status_breakdown', {}).items():
            pct = stats.get('status_percentages', {}).get(status, 0)
            lines.append(f"  {status}: {count} ({pct}%)")

        # GST section
        gst = data.get('gst_summary', {})
        tax = gst.get('tax_breakdown', {})
        lines.append(f"\n--- GST Summary ---")
        lines.append(f"Total Taxable: Rs. {gst.get('total_taxable', 0):,.2f}")
        lines.append(f"IGST: Rs. {tax.get('igst', 0):,.2f}")
        lines.append(f"CGST: Rs. {tax.get('cgst', 0):,.2f}")
        lines.append(f"SGST: Rs. {tax.get('sgst', 0):,.2f}")
        lines.append(f"Total Tax: Rs. {tax.get('total', 0):,.2f}")

        # Duplicates section
        dupes = data.get('duplicate_report', {})
        lines.append(f"\n--- Duplicate Attempts ---")
        lines.append(f"Total: {dupes.get('total_duplicates', 0)}")

        # Corrections section
        corr = data.get('correction_analysis', {})
        lines.append(f"\n--- Corrections ---")
        lines.append(f"Corrected: {corr.get('total_corrected', 0)}/{corr.get('total_invoices', 0)}")
        lines.append(f"Rate: {corr.get('correction_rate', 0)}%")

        return "\n".join(lines)


def _float(val) -> float:
    """Safe float conversion."""
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0
