"""
ERP Bridge Configuration
Isolated configuration for the CSV-to-Tally ERP Bridge module.
Loads environment variables and provides defaults.

This module does NOT import from the main src/config.py to maintain isolation.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root (two levels up from this file: src/erp_bridge/erp_config.py)
# ---------------------------------------------------------------------------
ERP_BRIDGE_ROOT = Path(__file__).parent
PROJECT_ROOT = ERP_BRIDGE_ROOT.parent.parent

# ---------------------------------------------------------------------------
# Feature Flag
# ---------------------------------------------------------------------------
ENABLE_ERP_BRIDGE: bool = os.getenv("ENABLE_ERP_BRIDGE", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Tally Connection
# ---------------------------------------------------------------------------
TALLY_HOST: str = os.getenv("TALLY_HOST", "localhost")
TALLY_PORT: int = int(os.getenv("TALLY_PORT", "9000"))
TALLY_TIMEOUT_CONNECT: int = int(os.getenv("TALLY_TIMEOUT_CONNECT", "30"))
TALLY_TIMEOUT_READ: int = int(os.getenv("TALLY_TIMEOUT_READ", "60"))
TALLY_MAX_RETRIES: int = int(os.getenv("TALLY_MAX_RETRIES", "3"))
TALLY_COMPANY_NAME: str = os.getenv("TALLY_COMPANY_NAME", "")

# ---------------------------------------------------------------------------
# Processing Limits
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_MB: int = int(os.getenv("ERP_BRIDGE_MAX_FILE_SIZE_MB", "5"))
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_ROWS: int = int(os.getenv("ERP_BRIDGE_MAX_ROWS", "10000"))
MAX_BATCH_SIZE: int = int(os.getenv("ERP_BRIDGE_MAX_BATCH_SIZE", "500"))
INVOICE_TIMEOUT: int = int(os.getenv("ERP_BRIDGE_INVOICE_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Tally Lookup (optional pre-validation against Tally master data)
# ---------------------------------------------------------------------------
ENABLE_TALLY_LOOKUP: bool = os.getenv("ENABLE_TALLY_LOOKUP", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------------------------
AUDIT_LOG_DIR: str = os.getenv(
    "ERP_BRIDGE_AUDIT_LOG_DIR",
    str(PROJECT_ROOT / "logs" / "erp_bridge"),
)
AUDIT_LOG_MAX_MB: int = int(os.getenv("ERP_BRIDGE_AUDIT_LOG_MAX_MB", "10"))
AUDIT_LOG_BACKUP_COUNT: int = int(os.getenv("ERP_BRIDGE_AUDIT_LOG_BACKUP_COUNT", "5"))

# ---------------------------------------------------------------------------
# Delay between sequential Tally requests (milliseconds)
# ---------------------------------------------------------------------------
TALLY_REQUEST_DELAY_MS: int = int(os.getenv("ERP_BRIDGE_TALLY_DELAY_MS", "100"))

# ---------------------------------------------------------------------------
# Rounding tolerance for GST reconciliation (in rupees)
# ---------------------------------------------------------------------------
ROUNDING_TOLERANCE: str = os.getenv("ERP_BRIDGE_ROUNDING_TOLERANCE", "0.50")
INVOICE_VALUE_TOLERANCE: str = os.getenv("ERP_BRIDGE_INVOICE_VALUE_TOLERANCE", "1.00")

# ---------------------------------------------------------------------------
# Valid reference data
# ---------------------------------------------------------------------------
VALID_VOUCHER_TYPES = {"Sales", "Purchase", "Sales Order"}

VALID_GST_RATES = {
    "0", "0.00", "0.25", "3", "3.00",
    "5", "5.00", "12", "12.00",
    "18", "18.00", "28", "28.00",
}

VALID_STATE_CODES = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "26", "27", "29", "30", "31", "32",
    "33", "34", "35", "36", "37", "38", "97",
}

STATE_CODE_TO_NAME = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
}

VALID_UOM_CODES = {
    "PCS", "NOS", "KG", "KGS", "GM", "LTR", "MTR", "SQM", "CBM",
    "BOX", "SET", "BAG", "TON", "QTL", "DOZ", "PAC", "ROL", "BDL", "OTH",
}

# ---------------------------------------------------------------------------
# Summary CSV expected columns (in order)
# ---------------------------------------------------------------------------
SUMMARY_CSV_COLUMNS = [
    "Voucher_Type",
    "Invoice_No",
    "Invoice_Date",
    "Party_Name",
    "Party_GSTIN",
    "Party_State_Code",
    "Place_Of_Supply",
    "Sales_Ledger",
    "Invoice_Value",
    "Total_Taxable_Value",
    "CGST_Total",
    "SGST_Total",
    "IGST_Total",
    "Cess_Total",
    "Round_Off",
    "Narration",
    "Reference_No",
    "Reference_Date",
    "Reverse_Charge",
    "Company_Name",
]

# ---------------------------------------------------------------------------
# Line Items CSV expected columns (in order)
# ---------------------------------------------------------------------------
ITEMS_CSV_COLUMNS = [
    "Invoice_No",
    "Line_No",
    "Item_Description",
    "HSN_SAC",
    "Qty",
    "UOM",
    "Rate",
    "Discount_Percent",
    "Taxable_Value",
    "GST_Rate",
    "CGST_Rate",
    "CGST_Amount",
    "SGST_Rate",
    "SGST_Amount",
    "IGST_Rate",
    "IGST_Amount",
    "Cess_Amount",
    "Stock_Item_Name",
    "Godown",
]
