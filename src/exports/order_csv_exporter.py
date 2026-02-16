"""
Order CSV Exporter
Generates two CSV files matching the Google Sheets tab schemas:
  - Order Header (ORDER_SUMMARY_COLUMNS)
  - Order Line Items (ORDER_LINE_ITEMS_COLUMNS)

Mirrors the pattern of InvoiceCSVExporter. Gated behind FEATURE_ORDER_SPLIT_CSV.
"""
import csv
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import config


class OrderCSVExporter:
    """Export order data to split CSV files matching Google Sheets format."""

    HEADER_COLUMNS = config.ORDER_SUMMARY_COLUMNS
    ITEM_COLUMNS = config.ORDER_LINE_ITEMS_COLUMNS

    def __init__(self):
        os.makedirs(config.ORDER_FOLDER, exist_ok=True)

    def export_order(
        self, clean_invoice: Dict, session_metadata: Dict = None
    ) -> Tuple[str, Optional[str]]:
        """
        Export order header + line items as two CSV files.

        Args:
            clean_invoice: Clean invoice dictionary with line_items
            session_metadata: Optional session metadata (user_id, page_count, etc.)

        Returns:
            Tuple of (header_csv_path, line_items_csv_path or None)
        """
        header_path = self.export_order_header(clean_invoice, session_metadata)
        items_path = None
        if clean_invoice.get("line_items"):
            items_path = self.export_order_line_items(clean_invoice)
        return header_path, items_path

    def export_order_header(
        self,
        clean_invoice: Dict,
        session_metadata: Dict = None,
        output_path: str = None,
    ) -> str:
        """
        Export order header CSV with ORDER_SUMMARY_COLUMNS schema.
        """
        if not output_path:
            order_id = clean_invoice.get("order_id", "UNKNOWN").replace("/", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Order_{order_id}_{timestamp}_header.csv"
            output_path = os.path.join(config.ORDER_FOLDER, filename)

        meta = session_metadata or {}

        row_data = {
            "Order_ID": clean_invoice.get("order_id", ""),
            "Customer_Name": clean_invoice.get("customer_name", "N/A"),
            "Order_Date": clean_invoice.get("order_date", ""),
            "Status": "completed",
            "Total_Items": clean_invoice.get("total_items", 0),
            "Total_Quantity": clean_invoice.get("total_quantity", 0),
            "Subtotal": clean_invoice.get("subtotal", 0),
            "Unmatched_Count": clean_invoice.get("unmatched_count", 0),
            "Page_Count": meta.get("page_count", 0),
            "Created_By": meta.get("created_by", "unknown"),
            "Processed_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.HEADER_COLUMNS)
            writer.writerow([row_data.get(col, "") for col in self.HEADER_COLUMNS])

        print(
            f"[CSV] Order header export ({len(self.HEADER_COLUMNS)} cols): {output_path}"
        )
        return output_path

    def export_order_line_items(
        self, clean_invoice: Dict, output_path: str = None
    ) -> str:
        """
        Export order line items CSV with ORDER_LINE_ITEMS_COLUMNS schema.
        """
        if not output_path:
            order_id = clean_invoice.get("order_id", "UNKNOWN").replace("/", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Order_{order_id}_{timestamp}_items.csv"
            output_path = os.path.join(config.ORDER_FOLDER, filename)

        with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.ITEM_COLUMNS)

            for item in clean_invoice.get("line_items", []):
                row_data = {
                    "Order_ID": clean_invoice.get("order_id", ""),
                    "Serial_No": item.get("serial_no", ""),
                    "Part_Name": item.get("part_name", item.get("item_ocr", "")),
                    "Part_Number": item.get("part_number", ""),
                    "Model": item.get("model", ""),
                    "Color": item.get("color", ""),
                    "Quantity": item.get("quantity", 0),
                    "Rate": item.get("rate", 0),
                    "Line_Total": item.get("line_total", 0),
                    "Match_Confidence": item.get("match_confidence", 0.0),
                }
                writer.writerow(
                    [row_data.get(col, "") for col in self.ITEM_COLUMNS]
                )

        line_count = len(clean_invoice.get("line_items", []))
        print(
            f"[CSV] Order line items export ({line_count} rows, "
            f"{len(self.ITEM_COLUMNS)} cols): {output_path}"
        )
        return output_path
