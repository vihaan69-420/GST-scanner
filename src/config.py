"""
Configuration module for GST Scanner Bot
Environment-agnostic: Works locally, in Docker, and on Google Cloud
Loads environment variables and validates configuration
"""
import os
import json
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Load environment variables from .env file (if exists - local dev only)
env_file = PROJECT_ROOT / '.env'
if env_file.exists():
    load_dotenv(env_file)

# ═══════════════════════════════════════════════════════════════════
# ENVIRONMENT DETECTION
# ═══════════════════════════════════════════════════════════════════

def detect_environment() -> str:
    """
    Detect which environment we're running in
    
    Returns:
        'cloud_run', 'kubernetes', 'docker', or 'local'
    """
    # Cloud Run sets K_SERVICE
    if os.getenv('K_SERVICE'):
        return 'cloud_run'
    
    # Kubernetes sets KUBERNETES_SERVICE_HOST
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        return 'kubernetes'
    
    # Docker typically has /.dockerenv file
    if Path('/.dockerenv').exists():
        return 'docker'
    
    # Check for common cloud indicators
    if os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCP_PROJECT'):
        return 'cloud_run'
    
    return 'local'

RUNTIME_ENVIRONMENT = detect_environment()

# ═══════════════════════════════════════════════════════════════════
# CREDENTIAL RESOLUTION - Smart multi-source loading
# ═══════════════════════════════════════════════════════════════════

_credentials_path = None  # Lazy loaded

def resolve_credentials() -> str:
    """
    Resolve Google Sheets credentials from multiple sources.
    Priority order:
    1. Local file (GOOGLE_SHEETS_CREDENTIALS_FILE env var or default path)
    2. JSON string in environment variable (GOOGLE_SHEETS_CREDENTIALS_JSON)
    3. Application Default Credentials (for Workload Identity)
    
    Returns:
        Path to credentials JSON file (may be temp file for JSON string sources)
        None if using Application Default Credentials
    """
    # Method 1: Local file path from environment
    creds_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE')
    if creds_file:
        # Handle relative paths
        if not os.path.isabs(creds_file):
            creds_file = str(PROJECT_ROOT / creds_file)
        if os.path.exists(creds_file):
            print(f"[CONFIG] Using credentials file: {creds_file}")
            return creds_file
    
    # Default local path
    default_path = PROJECT_ROOT / 'config' / 'credentials.json'
    if default_path.exists():
        print(f"[CONFIG] Using default credentials file: {default_path}")
        return str(default_path)
    
    # Method 2: JSON string in environment variable (Cloud Run with secrets)
    creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS_JSON')
    if creds_json:
        # Write to temp file
        temp_path = Path(tempfile.gettempdir()) / 'gst_scanner_credentials.json'
        temp_path.write_text(creds_json)
        print(f"[CONFIG] Using credentials from environment variable (GOOGLE_SHEETS_CREDENTIALS_JSON)")
        return str(temp_path)
    
    # Method 3: Application Default Credentials (Cloud Run with Workload Identity)
    if RUNTIME_ENVIRONMENT in ('cloud_run', 'kubernetes'):
        print("[CONFIG] Using Application Default Credentials (Workload Identity)")
        return None  # Signal to use ADC
    
    raise ValueError(
        "No valid credentials source found. Set one of:\n"
        "  - GOOGLE_SHEETS_CREDENTIALS_FILE (path to JSON file)\n"
        "  - GOOGLE_SHEETS_CREDENTIALS_JSON (JSON string)\n"
        "  - Place credentials.json in config/ folder"
    )

def get_credentials_path():
    """Get credentials path (lazy loaded)"""
    global _credentials_path
    if _credentials_path is None:
        _credentials_path = resolve_credentials()
    return _credentials_path

# ═══════════════════════════════════════════════════════════════════
# WRITABLE PATHS - Handle containerized environments
# ═══════════════════════════════════════════════════════════════════

def get_writable_path(folder_name: str) -> str:
    """Get a writable path that works in all environments"""
    env_path = os.getenv(folder_name.upper() + '_FOLDER')
    if env_path:
        if os.path.isabs(env_path):
            path = Path(env_path)
        else:
            path = PROJECT_ROOT / env_path
    else:
        path = PROJECT_ROOT / folder_name
    
    # In containers, /app might be read-only; use /tmp as fallback
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            # Fallback to temp directory
            path = Path(tempfile.gettempdir()) / 'gst_scanner' / folder_name
            path.mkdir(parents=True, exist_ok=True)
    
    return str(path)

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION VALUES
# ═══════════════════════════════════════════════════════════════════

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Google Gemini Configuration
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Google Sheets Configuration
GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv(
    'GOOGLE_SHEETS_CREDENTIALS_FILE',
    str(PROJECT_ROOT / 'config' / 'credentials.json')
)
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
SHEET_NAME = os.getenv('SHEET_NAME', 'Invoice_Header')
LINE_ITEMS_SHEET_NAME = os.getenv('LINE_ITEMS_SHEET_NAME', 'Line_Items')

# Application Configuration
ALLOWED_IMAGE_FORMATS = os.getenv('ALLOWED_IMAGE_FORMATS', 'jpg,jpeg,png,pdf').split(',')
MAX_IMAGES_PER_INVOICE = int(os.getenv('MAX_IMAGES_PER_INVOICE', '10'))
TEMP_FOLDER = get_writable_path('temp')
EXPORT_FOLDER = get_writable_path('exports')

# Tier 3 Configuration - Master Data Sheets
CUSTOMER_MASTER_SHEET = os.getenv('CUSTOMER_MASTER_SHEET', 'Customer_Master')
HSN_MASTER_SHEET = os.getenv('HSN_MASTER_SHEET', 'HSN_Master')
DUPLICATE_ATTEMPTS_SHEET = os.getenv('DUPLICATE_ATTEMPTS_SHEET', 'Duplicate_Attempts')

# Tier 3 Configuration - Export Settings
EXCLUDE_ERROR_INVOICES = os.getenv('EXCLUDE_ERROR_INVOICES', 'false').lower() == 'true'

# Tier 2 Features Configuration
ENABLE_CONFIDENCE_SCORING = os.getenv('ENABLE_CONFIDENCE_SCORING', 'true').lower() == 'true'
ENABLE_MANUAL_CORRECTIONS = os.getenv('ENABLE_MANUAL_CORRECTIONS', 'true').lower() == 'true'
ENABLE_DEDUPLICATION = os.getenv('ENABLE_DEDUPLICATION', 'true').lower() == 'true'
ENABLE_AUDIT_LOGGING = os.getenv('ENABLE_AUDIT_LOGGING', 'false').lower() == 'true'
EXTRACTION_VERSION = os.getenv('EXTRACTION_VERSION', 'v1.0-tier2')
BOT_VERSION = os.getenv('BOT_VERSION', '2.2.0')
BOT_BUILD_NAME = os.getenv('BOT_BUILD_NAME', 'local-dev')
CONFIDENCE_THRESHOLD_REVIEW = float(os.getenv('CONFIDENCE_THRESHOLD_REVIEW', '0.7'))

# Monitoring Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE_MAX_MB = int(os.getenv('LOG_FILE_MAX_MB', '10'))
LOG_FILE_BACKUP_COUNT = int(os.getenv('LOG_FILE_BACKUP_COUNT', '5'))
HEALTH_SERVER_PORT = int(os.getenv('HEALTH_SERVER_PORT', '8080'))
HEALTH_SERVER_ENABLED = os.getenv('HEALTH_SERVER_ENABLED', 'true').lower() == 'true'
METRICS_SAVE_INTERVAL = int(os.getenv('METRICS_SAVE_INTERVAL', '300'))  # 5 minutes

# ═══════════════════════════════════════════════════════
# USAGE TRACKING & COST ESTIMATION (NEW)
# ═══════════════════════════════════════════════════════

# Master switch - disables all tracking if false
ENABLE_USAGE_TRACKING = os.getenv('ENABLE_USAGE_TRACKING', 'false').lower() == 'true'

# Individual feature switches (require master=true)
ENABLE_OCR_LEVEL_TRACKING = os.getenv('ENABLE_OCR_LEVEL_TRACKING', 'false').lower() == 'true'
ENABLE_INVOICE_LEVEL_TRACKING = os.getenv('ENABLE_INVOICE_LEVEL_TRACKING', 'false').lower() == 'true'
ENABLE_CUSTOMER_AGGREGATION = os.getenv('ENABLE_CUSTOMER_AGGREGATION', 'false').lower() == 'true'
ENABLE_SUMMARY_GENERATION = os.getenv('ENABLE_SUMMARY_GENERATION', 'false').lower() == 'true'
ENABLE_OUTLIER_DETECTION = os.getenv('ENABLE_OUTLIER_DETECTION', 'false').lower() == 'true'
ENABLE_ORDER_TRACKING = os.getenv('ENABLE_ORDER_TRACKING', 'true').lower() == 'true'  # Order upload metrics

# Token capture method
ENABLE_ACTUAL_TOKEN_CAPTURE = os.getenv('ENABLE_ACTUAL_TOKEN_CAPTURE', 'true').lower() == 'true'

# Customer identifier (single customer for now)
DEFAULT_CUSTOMER_ID = os.getenv('DEFAULT_CUSTOMER_ID', 'CUST001')
DEFAULT_CUSTOMER_NAME = os.getenv('DEFAULT_CUSTOMER_NAME', 'Default Customer')

# Gemini API Pricing (Configurable)
GEMINI_OCR_PRICE_PER_1K_TOKENS = float(os.getenv('GEMINI_OCR_PRICE_PER_1K_TOKENS', '0.0001875'))
GEMINI_PARSING_PRICE_PER_1K_TOKENS = float(os.getenv('GEMINI_PARSING_PRICE_PER_1K_TOKENS', '0.000075'))

# Rate limits (optional monitoring)
GEMINI_RATE_LIMIT_RPM = int(os.getenv('GEMINI_RATE_LIMIT_RPM', '15'))
GEMINI_RATE_LIMIT_TPM = int(os.getenv('GEMINI_RATE_LIMIT_TPM', '1000000'))

# Outlier Detection Thresholds
OUTLIER_COST_ZSCORE_THRESHOLD = float(os.getenv('OUTLIER_COST_ZSCORE_THRESHOLD', '2.0'))
OUTLIER_PAGE_COUNT_THRESHOLD = int(os.getenv('OUTLIER_PAGE_COUNT_THRESHOLD', '10'))
OUTLIER_TOKEN_PERCENTILE_THRESHOLD = int(os.getenv('OUTLIER_TOKEN_PERCENTILE_THRESHOLD', '95'))

# Google Sheets Column Mapping
# Tier 1 columns (original 24 fields)
SHEET_COLUMNS = [
    'Invoice_No',
    'Invoice_Date',
    'Invoice_Type',
    'Seller_Name',
    'Seller_GSTIN',
    'Seller_State_Code',
    'Buyer_Name',
    'Buyer_GSTIN',
    'Buyer_State_Code',
    'Ship_To_Name',
    'Ship_To_State_Code',
    'Place_Of_Supply',
    'Supply_Type',
    'Reverse_Charge',
    'Invoice_Value',
    'Total_Taxable_Value',
    'Total_GST',
    'IGST_Total',
    'CGST_Total',
    'SGST_Total',
    'Eway_Bill_No',
    'Transporter',
    'Validation_Status',
    'Validation_Remarks',
    # Tier 2 audit columns
    'Upload_Timestamp',
    'Telegram_User_ID',
    'Telegram_Username',
    'Extraction_Version',
    'Model_Version',
    'Processing_Time_Seconds',
    'Page_Count',
    # Tier 2 correction columns
    'Has_Corrections',
    'Corrected_Fields',
    'Correction_Metadata',
    # Tier 2 deduplication columns
    'Invoice_Fingerprint',
    'Duplicate_Status',
    # Tier 2 confidence columns
    'Invoice_No_Confidence',
    'Invoice_Date_Confidence',
    'Buyer_GSTIN_Confidence',
    'Total_Taxable_Value_Confidence',
    'Total_GST_Confidence'
]

# Line Items Sheet Column Mapping
# Matches existing Google Sheet structure
LINE_ITEM_COLUMNS = [
    'Invoice_No',
    'Line_No',
    'Item_Code',
    'Item_Description',
    'HSN',
    'Qty',
    'UOM',
    'Rate',
    'Discount_Percent',
    'Taxable_Value',
    'GST_Rate',
    'CGST_Rate',
    'CGST_Amount',
    'SGST_Rate',
    'SGST_Amount',
    'IGST_Rate',
    'IGST_Amount',
    'Cess_Amount',
    'Line_Total'
]

# Tier 3 - Customer Master Sheet Column Mapping
CUSTOMER_MASTER_COLUMNS = [
    'GSTIN',
    'Legal_Name',
    'Trade_Name',
    'State_Code',
    'Default_Place_Of_Supply',
    'Last_Updated',
    'Usage_Count'
]

# Tier 3 - HSN Master Sheet Column Mapping
HSN_MASTER_COLUMNS = [
    'HSN_SAC_Code',
    'Description',
    'Default_GST_Rate',
    'UQC',
    'Category',
    'Last_Updated',
    'Usage_Count'
]

# Tier 3 - Duplicate Attempts Sheet Column Mapping
DUPLICATE_ATTEMPTS_COLUMNS = [
    'Timestamp',
    'User_ID',
    'Invoice_No',
    'Action_Taken'
]

# ═══════════════════════════════════════════════════════════════════
# EPIC 2: ORDER UPLOAD & NORMALIZATION
# ═══════════════════════════════════════════════════════════════════

# Master feature flag - disables entire Epic 2 feature when false
FEATURE_ORDER_UPLOAD_NORMALIZATION = os.getenv('FEATURE_ORDER_UPLOAD_NORMALIZATION', 'false').lower() == 'true'

# Split order CSV export: when true, generate two files (header + line items)
# matching ORDER_SUMMARY_COLUMNS and ORDER_LINE_ITEMS_COLUMNS schemas.
# When false, uses the original single combined CSV from pdf_generator.
FEATURE_ORDER_SPLIT_CSV = os.getenv('FEATURE_ORDER_SPLIT_CSV', 'false').lower() == 'true'

# Pricing sheet configuration (configurable for future migration to Google Sheets)
PRICING_SHEET_SOURCE = os.getenv('PRICING_SHEET_SOURCE', 'google_sheet')  # 'local_file' or 'google_sheet'
PRICING_SHEET_PATH = os.getenv('PRICING_SHEET_PATH', 'Epic2 artifacts/UPDATED PRICE LIST FOR SAI-ABS 10 MAY-25.xls')
PRICING_SHEET_ID = os.getenv('PRICING_SHEET_ID', '1uNUYg0tpBWn7flNENk_kWHvGdimXhhzq3VAQAeNd4GE')  # Google Sheet with pricing data
PRICING_SHEET_NAME = os.getenv('PRICING_SHEET_NAME', 'Sheet1')  # Worksheet name in pricing sheet

# LLM-based pricing fallback (uses Gemini for unmatched items - costs API tokens)
ENABLE_LLM_PRICING_FALLBACK = os.getenv('ENABLE_LLM_PRICING_FALLBACK', 'true').lower() == 'true'

# Order-related Google Sheets tabs
ORDER_SUMMARY_SHEET = os.getenv('ORDER_SUMMARY_SHEET', 'Orders')
ORDER_LINE_ITEMS_SHEET = os.getenv('ORDER_LINE_ITEMS_SHEET', 'Order_Line_Items')
ORDER_CUSTOMER_DETAILS_SHEET = os.getenv('ORDER_CUSTOMER_DETAILS_SHEET', 'Customer_Details')

# Tenant tracking tab
TENANT_INFO_SHEET = os.getenv('TENANT_INFO_SHEET', 'Tenant_Info')

# Order-related configuration
MAX_IMAGES_PER_ORDER = int(os.getenv('MAX_IMAGES_PER_ORDER', '10'))
ORDER_FOLDER = get_writable_path('orders')  # Folder for order PDFs


# ═══════════════════════════════════════════════════════════════════
# EPIC 3: MULTI-TENANCY & ENVIRONMENT PROVISIONING
# ═══════════════════════════════════════════════════════════════════

# Master feature flag - enables per-tenant Google Sheet isolation
FEATURE_TENANT_SHEET_ISOLATION = os.getenv('FEATURE_TENANT_SHEET_ISOLATION', 'false').lower() == 'true'

# Sheet naming template for new tenant sheets
TENANT_SHEET_NAME_TEMPLATE = os.getenv('TENANT_SHEET_NAME_TEMPLATE', 'GST_Scanner_{tenant_id}')

# Order tab column definitions (centralised from sheets_handler.py hardcoded values)
ORDER_SUMMARY_COLUMNS = [
    'Order_ID', 'Customer_Name', 'Order_Date', 'Status',
    'Total_Items', 'Total_Quantity', 'Subtotal', 'Unmatched_Count',
    'Page_Count', 'Created_By', 'Processed_At'
]

ORDER_LINE_ITEMS_COLUMNS = [
    'Order_ID', 'Serial_No', 'Part_Name', 'Part_Number',
    'Model', 'Color', 'Quantity', 'Rate', 'Line_Total', 'Match_Confidence'
]

ORDER_CUSTOMER_DETAILS_COLUMNS = [
    'Customer_ID', 'Customer_Name', 'Contact',
    'Last_Order_Date', 'Total_Orders'
]

# Complete registry of all data tabs and their column schemas
# Used by SheetProvisioner to create tenant sheets with all tabs
TENANT_SHEET_COLUMNS = {
    SHEET_NAME: SHEET_COLUMNS,
    LINE_ITEMS_SHEET_NAME: LINE_ITEM_COLUMNS,
    CUSTOMER_MASTER_SHEET: CUSTOMER_MASTER_COLUMNS,
    HSN_MASTER_SHEET: HSN_MASTER_COLUMNS,
    DUPLICATE_ATTEMPTS_SHEET: DUPLICATE_ATTEMPTS_COLUMNS,
    ORDER_SUMMARY_SHEET: ORDER_SUMMARY_COLUMNS,
    ORDER_LINE_ITEMS_SHEET: ORDER_LINE_ITEMS_COLUMNS,
    ORDER_CUSTOMER_DETAILS_SHEET: ORDER_CUSTOMER_DETAILS_COLUMNS,
}

# Subscription tiers (configurable via env var as JSON, or defaults)
_default_tiers = json.dumps([
    {"id": "free", "name": "Free", "description": "Basic access"},
    {"id": "basic", "name": "Basic", "description": "Standard features"},
    {"id": "premium", "name": "Premium", "description": "All features"}
])
SUBSCRIPTION_TIERS = json.loads(os.getenv('SUBSCRIPTION_TIERS', _default_tiers))
DEFAULT_SUBSCRIPTION_TIER = os.getenv('DEFAULT_SUBSCRIPTION_TIER', 'free')


# ═══════════════════════════════════════════════════════════════════
# TIER 4: BATCH PROCESSING ENGINE (Local Only)
# ═══════════════════════════════════════════════════════════════════

ENABLE_BATCH_MODE = os.getenv('ENABLE_BATCH_MODE', 'false').lower() == 'true'
BATCH_QUEUE_SHEET_NAME = os.getenv('BATCH_QUEUE_SHEET_NAME', 'Batch_Queue')
BATCH_SUPPRESS_VALIDATION = os.getenv('BATCH_SUPPRESS_VALIDATION', 'false').lower() == 'true'


# ═══════════════════════════════════════════════════════════════════
# EPIC 4: REST API (FastAPI + Swagger + JWT Auth)
# ═══════════════════════════════════════════════════════════════════

# Master feature flag - enables the FastAPI REST API layer
FEATURE_API_ENABLED = os.getenv('FEATURE_API_ENABLED', 'false').lower() == 'true'

# API server configuration
API_PORT = int(os.getenv('API_PORT', '8000'))
API_HOST = os.getenv('API_HOST', '0.0.0.0')

# Cloud Run PORT override: Cloud Run sets PORT to the single port it routes
# traffic to (usually 8080). When the API is enabled on Cloud Run, FastAPI
# should bind to this port so it receives external HTTP requests.
_cloud_run_port = os.getenv('PORT')  # Set automatically by Cloud Run
if _cloud_run_port and FEATURE_API_ENABLED:
    API_PORT = int(_cloud_run_port)

# JWT configuration
API_JWT_SECRET = os.getenv('API_JWT_SECRET', '')  # Required when API is enabled
API_JWT_ALGORITHM = os.getenv('API_JWT_ALGORITHM', 'HS256')
API_JWT_EXPIRY_MINUTES = int(os.getenv('API_JWT_EXPIRY_MINUTES', '30'))
API_JWT_REFRESH_EXPIRY_DAYS = int(os.getenv('API_JWT_REFRESH_EXPIRY_DAYS', '7'))

# CORS configuration (comma-separated origins)
API_CORS_ORIGINS = os.getenv('API_CORS_ORIGINS', 'http://localhost:3000').split(',')

# SQLite user database path
API_USER_DB_PATH = os.getenv('API_USER_DB_PATH', str(PROJECT_ROOT / 'data' / 'users.db'))

# Rate limiting
API_RATE_LIMIT_PER_MINUTE = int(os.getenv('API_RATE_LIMIT_PER_MINUTE', '60'))


def validate_config():
    """Validate that all required configuration is present"""
    errors = []
    
    print(f"[CONFIG] Runtime environment: {RUNTIME_ENVIRONMENT}")
    
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set")
    
    if not GOOGLE_API_KEY:
        errors.append("GOOGLE_API_KEY is not set")
    
    if not GOOGLE_SHEET_ID:
        errors.append("GOOGLE_SHEET_ID is not set")
    
    # Validate credentials - try to resolve them
    try:
        creds_path = get_credentials_path()
        if creds_path and not os.path.exists(creds_path):
            errors.append(f"Google Sheets credentials file not found: {creds_path}")
    except ValueError as e:
        errors.append(str(e))
    
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(errors))
    
    return True


if __name__ == "__main__":
    try:
        validate_config()
        print("[OK] Configuration validated successfully")
    except ValueError as e:
        print(f"[FAIL] Configuration validation failed:\n{e}")
