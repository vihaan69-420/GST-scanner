"""
Order PDF/CSV Generator
Generates clean, customer-facing PDFs or CSVs from normalized order data
"""
import os
import csv
from datetime import datetime
from typing import Dict
import config


class OrderPDFGenerator:
    """Generates clean invoice PDFs from order data"""
    
    def __init__(self):
        """Initialize PDF generator"""
        # Ensure output folder exists
        os.makedirs(config.ORDER_FOLDER, exist_ok=True)
    
    def generate_pdf(self, clean_invoice: Dict, output_path: str = None) -> str:
        """
        Generate clean PDF from invoice model
        
        Args:
            clean_invoice: Clean invoice dictionary with line_items
            output_path: Optional custom output path
            
        Returns:
            Path to generated PDF
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            
            # Generate output path if not provided
            if not output_path:
                filename = f"{clean_invoice['order_id']}.pdf"
                output_path = os.path.join(config.ORDER_FOLDER, filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(output_path, pagesize=A4,
                                    rightMargin=72, leftMargin=72,
                                    topMargin=72, bottomMargin=18)
            
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#2C3E50'),
                spaceAfter=30,
                alignment=1  # Center
            )
            title = Paragraph(f"<b>Order Summary</b>", title_style)
            elements.append(title)
            
            # Order ID and Date
            meta_style = ParagraphStyle(
                'Meta',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=20
            )
            
            meta_text = f"""
            <b>Order ID:</b> {clean_invoice['order_id']}<br/>
            <b>Order Date:</b> {clean_invoice['order_date']}<br/>
            <b>Customer:</b> {clean_invoice.get('customer_name', 'N/A')}
            """
            
            # Add mobile and location if available
            if clean_invoice.get('mobile_number'):
                meta_text += f"<br/><b>Mobile:</b> {clean_invoice['mobile_number']}"
            if clean_invoice.get('location'):
                meta_text += f"<br/><b>Location:</b> {clean_invoice['location']}"
            
            elements.append(Paragraph(meta_text, meta_style))
            elements.append(Spacer(1, 20))
            
            # Summary Section
            summary_text = f"""
            <b>Summary:</b><br/>
            Total Items: {clean_invoice['total_items']}<br/>
            Total Quantity: {clean_invoice['total_quantity']}<br/>
            """
            
            if clean_invoice.get('unmatched_count', 0) > 0:
                summary_text += f"<i>Note: {clean_invoice['unmatched_count']} items without pricing</i><br/>"
            
            elements.append(Paragraph(summary_text, meta_style))
            elements.append(Spacer(1, 20))
            
            # Line Items Table - with Part Number, Price List Name, and confidence %
            table_data = [['S.N', 'Part No.', 'Item (OCR)', 'Price List Match', 'Color', 'Qty', 'Rate (₹)', 'Total (₹)']]
            
            # Confidence threshold for showing matched part info
            DISPLAY_CONFIDENCE = 0.80
            
            for item in clean_invoice['line_items']:
                # Club Brand, Part Name, and Model into one field
                brand = item.get('brand', '')
                part = item['part_name']
                model = item.get('model', '')
                
                # Build description: "Brand Part Name (Model)"
                description_parts = []
                if brand:
                    description_parts.append(brand)
                if part:
                    description_parts.append(part)
                if model and model != part:
                    description_parts.append(f"({model})")
                
                item_description = ' '.join(description_parts)[:45]
                
                # Part number and price list name
                match_confidence = item.get('match_confidence', 0.0)
                part_number = item.get('part_number', 'N/A')
                matched_name = item.get('matched_part_name', '')
                
                if part_number == 'N/A' or match_confidence < DISPLAY_CONFIDENCE:
                    part_number = '-'
                    price_list_cell = Paragraph(
                        f'<font size="6" color="#999999"><i>No confident match</i></font>',
                        styles['Normal']
                    )
                else:
                    # Show matched name + confidence %
                    conf_pct = int(match_confidence * 100)
                    truncated_name = matched_name[:55] if matched_name else ''
                    price_list_cell = Paragraph(
                        f'<font size="6">{truncated_name}</font><br/>'
                        f'<font size="5" color="#27AE60"><b>({conf_pct}% match)</b></font>',
                        styles['Normal']
                    )
                
                table_data.append([
                    str(item['serial_no']),
                    part_number,
                    item_description,
                    price_list_cell,
                    item.get('color', '')[:15],
                    str(item['quantity']),
                    f"{item['rate']:.2f}",
                    f"{item['line_total']:.2f}"
                ])
            
            # Add subtotal row (8 columns)
            table_data.append([
                '', '', '', '', '', '',
                Paragraph('<b>Subtotal:</b>', styles['Normal']),
                Paragraph(f"<b>₹{clean_invoice['subtotal']:.2f}</b>", styles['Normal'])
            ])
            
            # Create table with column widths (8 columns)
            table = Table(table_data, colWidths=[
                0.35*inch,   # S.N
                0.7*inch,    # Part No.
                1.8*inch,    # Item (OCR)
                2.2*inch,    # Price List Match
                0.75*inch,   # Color
                0.35*inch,   # Qty
                0.7*inch,    # Rate
                0.85*inch,   # Total
            ])
            
            # Style the table
            table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                
                # Data rows
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -2), 7),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # S.N centered
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Part No. centered
                ('ALIGN', (5, 1), (-1, -1), 'RIGHT'),  # Qty, Rate, Total right-aligned
                ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#ECF0F1')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Subtotal row
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 9),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
                ('TOPPADDING', (0, -1), (-1, -1), 10),
            ]))
            
            elements.append(table)
            
            # Footer note
            if clean_invoice.get('unmatched_count', 0) > 0:
                elements.append(Spacer(1, 30))
                note_text = f"<i>* {clean_invoice['unmatched_count']} items marked as 'N/A' do not have pricing information. Please verify manually.</i>"
                note_style = ParagraphStyle(
                    'Note',
                    parent=styles['Normal'],
                    fontSize=8,
                    textColor=colors.HexColor('#E74C3C')
                )
                elements.append(Paragraph(note_text, note_style))
            
            # Build PDF
            doc.build(elements)
            
            print(f"[PDF] Generated: {output_path}")
            return output_path
            
        except ImportError:
            print("[ERROR] reportlab not installed. Install with: pip install reportlab")
            raise Exception("PDF generation failed: reportlab not installed")
        
        except Exception as e:
            print(f"[ERROR] PDF generation failed: {e}")
            raise Exception(f"PDF generation failed: {str(e)}")
    
    def generate_csv(self, clean_invoice: Dict, output_path: str = None) -> str:
        """
        Generate clean CSV from invoice model
        
        Args:
            clean_invoice: Clean invoice dictionary with line_items
            output_path: Optional custom output path
            
        Returns:
            Path to generated CSV file
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            order_id = clean_invoice.get('order_id', f'ORD_{timestamp}')
            output_path = os.path.join(config.ORDER_FOLDER, f"{order_id}.csv")
        
        DISPLAY_CONFIDENCE = 0.80
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header info rows
                writer.writerow(['Order ID', clean_invoice.get('order_id', 'N/A')])
                writer.writerow(['Date', clean_invoice.get('order_date', 'N/A')])
                writer.writerow(['Customer', clean_invoice.get('customer_name', 'N/A')])
                writer.writerow(['Mobile', clean_invoice.get('mobile_number', '')])
                writer.writerow([])  # Blank row separator
                
                # Column headers
                writer.writerow([
                    'S.N', 'Part No.', 'Item (OCR)', 'Price List Match',
                    'Match %', 'Color', 'Qty', 'Rate', 'Total'
                ])
                
                # Line items
                for item in clean_invoice['line_items']:
                    # Build OCR description
                    brand = item.get('brand', '')
                    part = item['part_name']
                    model = item.get('model', '')
                    desc_parts = []
                    if brand:
                        desc_parts.append(brand)
                    if part:
                        desc_parts.append(part)
                    if model and model != part:
                        desc_parts.append(f"({model})")
                    item_description = ' '.join(desc_parts)
                    
                    match_confidence = item.get('match_confidence', 0.0)
                    part_number = item.get('part_number', 'N/A')
                    matched_name = item.get('matched_part_name', '')
                    
                    if part_number == 'N/A' or match_confidence < DISPLAY_CONFIDENCE:
                        part_number = ''
                        matched_name = ''
                        conf_str = ''
                    else:
                        conf_str = f"{int(match_confidence * 100)}%"
                    
                    writer.writerow([
                        item['serial_no'],
                        part_number,
                        item_description,
                        matched_name,
                        conf_str,
                        item.get('color', ''),
                        item['quantity'],
                        f"{item['rate']:.2f}",
                        f"{item['line_total']:.2f}"
                    ])
                
                # Summary rows
                writer.writerow([])
                writer.writerow(['', '', '', '', '', '', 'Subtotal:', '', f"{clean_invoice['subtotal']:.2f}"])
                writer.writerow(['', '', '', '', '', '', 'Total Items:', '', clean_invoice['total_items']])
                writer.writerow(['', '', '', '', '', '', 'Total Qty:', '', clean_invoice['total_quantity']])
            
            print(f"[CSV] Generated: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"[ERROR] CSV generation failed: {e}")
            raise Exception(f"CSV generation failed: {str(e)}")
