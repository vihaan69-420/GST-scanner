"""
GST Validation Engine
Validates GST invoice data for compliance and accuracy
"""
from typing import Dict, List
from decimal import Decimal, InvalidOperation


class GSTValidator:
    """Validate GST invoice data against compliance rules"""
    
    def __init__(self):
        """Initialize the GST validator"""
        # Tolerance for rounding differences (in rupees)
        self.rounding_tolerance = Decimal('0.50')
        
        # Tolerance percentage for critical mismatches
        self.critical_percentage_threshold = Decimal('1.0')  # 1%
    
    def validate_invoice(self, invoice_data: Dict, line_items: List[Dict]) -> Dict:
        """
        Validate complete invoice with line items
        
        Args:
            invoice_data: Invoice header data dictionary
            line_items: List of line item dictionaries
            
        Returns:
            {
                'status': 'OK' | 'WARNING' | 'ERROR',
                'errors': [list of error messages],
                'warnings': [list of warning messages]
            }
        """
        errors = []
        warnings = []
        
        # Validation A: Taxable Value Reconciliation
        taxable_result = self._validate_taxable_values(invoice_data, line_items)
        errors.extend(taxable_result['errors'])
        warnings.extend(taxable_result['warnings'])
        
        # Validation B: GST Total Reconciliation
        gst_result = self._validate_gst_totals(invoice_data, line_items)
        errors.extend(gst_result['errors'])
        warnings.extend(gst_result['warnings'])
        
        # Validation C: Tax Type Consistency
        tax_type_result = self._validate_tax_type_consistency(invoice_data)
        errors.extend(tax_type_result['errors'])
        warnings.extend(tax_type_result['warnings'])
        
        # Validation D: GST Rate Math Consistency (per line)
        rate_result = self._validate_gst_rate_math(line_items)
        errors.extend(rate_result['errors'])
        warnings.extend(rate_result['warnings'])
        
        # Determine overall status
        if errors:
            status = 'ERROR'
        elif warnings:
            status = 'WARNING'
        else:
            status = 'OK'
        
        return {
            'status': status,
            'errors': errors,
            'warnings': warnings
        }
    
    def _safe_decimal(self, value: str) -> Decimal:
        """Safely convert string to Decimal, return 0 if invalid"""
        try:
            if not value or value == "":
                return Decimal('0')
            # Remove currency symbols and commas
            cleaned = str(value).replace('₹', '').replace(',', '').strip()
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return Decimal('0')
    
    def _validate_taxable_values(self, invoice_data: Dict, line_items: List[Dict]) -> Dict:
        """
        Validation A: Sum of line item taxable values should match invoice total
        
        Returns:
            {'errors': [...], 'warnings': [...]}
        """
        errors = []
        warnings = []
        
        try:
            # Get invoice taxable total
            invoice_taxable = self._safe_decimal(invoice_data.get('Total_Taxable_Value', '0'))
            
            # Sum line item taxable values
            line_items_taxable = sum(
                self._safe_decimal(item.get('Taxable_Value', '0'))
                for item in line_items
            )
            
            # Calculate difference
            difference = abs(invoice_taxable - line_items_taxable)
            
            # Check if difference is significant
            if invoice_taxable > 0:
                percentage_diff = (difference / invoice_taxable) * 100
            else:
                percentage_diff = Decimal('0')
            
            # Determine severity
            if difference > self.rounding_tolerance:
                if percentage_diff > self.critical_percentage_threshold:
                    errors.append(
                        f"Taxable value mismatch: Invoice total Rs.{invoice_taxable} vs "
                        f"Line items sum Rs.{line_items_taxable} (diff: Rs.{difference}, {percentage_diff:.2f}%)"
                    )
                else:
                    warnings.append(
                        f"Minor taxable value difference: Rs.{difference} (likely rounding)"
                    )
        
        except Exception as e:
            warnings.append(f"Could not validate taxable values: {str(e)}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_gst_totals(self, invoice_data: Dict, line_items: List[Dict]) -> Dict:
        """
        Validation B: Sum of line item GST should match invoice GST total
        
        Returns:
            {'errors': [...], 'warnings': [...]}
        """
        errors = []
        warnings = []
        
        try:
            # Get invoice GST total
            invoice_gst = self._safe_decimal(invoice_data.get('Total_GST', '0'))
            
            # Sum line item GST amounts
            line_items_gst = sum(
                self._safe_decimal(item.get('CGST_Amount', '0')) +
                self._safe_decimal(item.get('SGST_Amount', '0')) +
                self._safe_decimal(item.get('IGST_Amount', '0'))
                for item in line_items
            )
            
            # Calculate difference
            difference = abs(invoice_gst - line_items_gst)
            
            # Check if difference is significant
            if invoice_gst > 0:
                percentage_diff = (difference / invoice_gst) * 100
            else:
                percentage_diff = Decimal('0')
            
            # Determine severity
            if difference > self.rounding_tolerance:
                if percentage_diff > self.critical_percentage_threshold:
                    errors.append(
                        f"GST total mismatch: Invoice GST Rs.{invoice_gst} vs "
                        f"Line items GST Rs.{line_items_gst} (diff: Rs.{difference}, {percentage_diff:.2f}%)"
                    )
                else:
                    warnings.append(
                        f"Minor GST total difference: Rs.{difference} (likely rounding)"
                    )
        
        except Exception as e:
            warnings.append(f"Could not validate GST totals: {str(e)}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_tax_type_consistency(self, invoice_data: Dict) -> Dict:
        """
        Validation C: Tax type consistency (INTRA-STATE vs INTER-STATE)
        
        Returns:
            {'errors': [...], 'warnings': [...]}
        """
        errors = []
        warnings = []
        
        try:
            supply_type = invoice_data.get('Supply_Type', '').upper()
            
            igst = self._safe_decimal(invoice_data.get('IGST_Total', '0'))
            cgst = self._safe_decimal(invoice_data.get('CGST_Total', '0'))
            sgst = self._safe_decimal(invoice_data.get('SGST_Total', '0'))
            
            # INTRA-STATE rules
            if 'INTRA' in supply_type:
                if igst > 0:
                    errors.append(
                        f"INTRA-STATE invoice should not have IGST (found Rs.{igst})"
                    )
                if cgst == 0 and sgst == 0:
                    errors.append(
                        "INTRA-STATE invoice must have CGST and SGST"
                    )
                elif cgst == 0 or sgst == 0:
                    warnings.append(
                        f"INTRA-STATE invoice has only one tax component (CGST: Rs.{cgst}, SGST: Rs.{sgst})"
                    )
            
            # INTER-STATE rules
            elif 'INTER' in supply_type:
                if cgst > 0 or sgst > 0:
                    errors.append(
                        f"INTER-STATE invoice should not have CGST/SGST (found CGST: Rs.{cgst}, SGST: Rs.{sgst})"
                    )
                if igst == 0:
                    errors.append(
                        "INTER-STATE invoice must have IGST"
                    )
            
            # General check: Both IGST and CGST/SGST present
            if igst > 0 and (cgst > 0 or sgst > 0):
                errors.append(
                    f"Invoice has both IGST (Rs.{igst}) and CGST/SGST (Rs.{cgst}/Rs.{sgst}) - invalid"
                )
        
        except Exception as e:
            warnings.append(f"Could not validate tax type consistency: {str(e)}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_gst_rate_math(self, line_items: List[Dict]) -> Dict:
        """
        Validation D: GST rate math consistency for each line item
        
        Returns:
            {'errors': [...], 'warnings': [...]}
        """
        errors = []
        warnings = []
        
        for item in line_items:
            try:
                line_no = item.get('Line_No', '?')
                
                taxable = self._safe_decimal(item.get('Taxable_Value', '0'))
                
                # Get GST amounts
                cgst = self._safe_decimal(item.get('CGST_Amount', '0'))
                sgst = self._safe_decimal(item.get('SGST_Amount', '0'))
                igst = self._safe_decimal(item.get('IGST_Amount', '0'))
                
                actual_gst = cgst + sgst + igst
                
                # Skip if no GST or no taxable value
                if actual_gst == 0 or taxable == 0:
                    continue
                
                # Determine GST rate from the actual tax type used
                gst_rate = Decimal('0')
                if igst > 0:
                    # IGST case - rate should be in IGST_Rate
                    gst_rate = self._safe_decimal(item.get('IGST_Rate', '0'))
                    if gst_rate == 0:
                        # Try to infer from GST_Rate field
                        gst_rate = self._safe_decimal(item.get('GST_Rate', '0'))
                elif cgst > 0 or sgst > 0:
                    # CGST/SGST case - rate should be in CGST_Rate or SGST_Rate
                    cgst_rate = self._safe_decimal(item.get('CGST_Rate', '0'))
                    sgst_rate = self._safe_decimal(item.get('SGST_Rate', '0'))
                    # Total rate is CGST + SGST (each is half of total)
                    gst_rate = cgst_rate + sgst_rate
                    if gst_rate == 0:
                        # Try to infer from GST_Rate field
                        gst_rate = self._safe_decimal(item.get('GST_Rate', '0'))
                
                # If still no rate found, skip validation
                if gst_rate == 0:
                    continue
                
                # Calculate expected GST
                expected_gst = taxable * (gst_rate / 100)
                
                # Calculate difference
                difference = abs(expected_gst - actual_gst)
                
                # Allow rounding tolerance
                if difference > self.rounding_tolerance:
                    warnings.append(
                        f"Line {line_no}: GST math mismatch - Expected Rs.{expected_gst:.2f} "
                        f"({gst_rate}% of Rs.{taxable}), got Rs.{actual_gst} (diff: Rs.{difference:.2f})"
                    )
            
            except Exception as e:
                warnings.append(f"Could not validate GST math for line {item.get('Line_No', '?')}: {str(e)}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def format_validation_remarks(self, validation_result: Dict) -> str:
        """
        Format validation result into human-readable remarks
        
        Args:
            validation_result: Result from validate_invoice()
            
        Returns:
            Formatted string for Validation_Remarks column
        """
        remarks = []
        
        if validation_result['status'] == 'OK':
            return "All validations passed"
        
        # Add errors
        if validation_result['errors']:
            remarks.append("ERRORS:")
            for error in validation_result['errors']:
                remarks.append(f"  - {error}")
        
        # Add warnings
        if validation_result['warnings']:
            remarks.append("WARNINGS:")
            for warning in validation_result['warnings']:
                remarks.append(f"  - {warning}")
        
        return "\n".join(remarks)


if __name__ == "__main__":
    # Test the GST validator
    validator = GSTValidator()
    
    # Test data
    invoice_data = {
        'Total_Taxable_Value': '125.32',
        'Total_GST': '22.56',
        'CGST_Total': '11.28',
        'SGST_Total': '11.28',
        'IGST_Total': '',
        'Supply_Type': 'INTRA-STATE'
    }
    
    line_items = [
        {
            'Line_No': '1',
            'Taxable_Value': '125.32',
            'GST_Rate_Percent': '18',
            'CGST_Amount': '11.28',
            'SGST_Amount': '11.28',
            'IGST_Amount': ''
        }
    ]
    
    print("Testing GST Validator...")
    result = validator.validate_invoice(invoice_data, line_items)
    
    print(f"\n[{result['status']}] Validation Result:")
    print("="*80)
    
    if result['errors']:
        print("\nErrors:")
        for error in result['errors']:
            print(f"  - {error}")
    
    if result['warnings']:
        print("\nWarnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")
    
    if result['status'] == 'OK':
        print("All validations passed successfully!")
    
    print("\nRemarks:")
    print(validator.format_validation_remarks(result))
