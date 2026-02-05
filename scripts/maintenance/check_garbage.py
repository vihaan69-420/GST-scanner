"""
Check for garbage data beyond column X in Invoice_Header
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import config

scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(config.GOOGLE_SHEETS_CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
ws = client.open_by_key(config.GOOGLE_SHEET_ID).worksheet('Invoice_Header')

def col_letter(idx):
    """Convert 0-based index to column letter"""
    if idx < 26:
        return chr(65 + idx)
    else:
        return chr(65 + (idx // 26) - 1) + chr(65 + (idx % 26))

print('=' * 70)
print('CHECKING FOR GARBAGE DATA BEYOND COLUMN X')
print('=' * 70)
print()

# Get all data including beyond column X
all_data = ws.get_all_values()
print(f'Total rows: {len(all_data)}')
print(f'Total columns in data: {len(all_data[0]) if all_data else 0}')
print(f'Sheet row_count: {ws.row_count}')
print(f'Sheet col_count: {ws.col_count}')
print()

# Check each row for data beyond column X (index 23)
print('=' * 70)
print('ROW BY ROW ANALYSIS')
print('=' * 70)

for i, row in enumerate(all_data, 1):
    # Cells in A-X (index 0-23)
    valid_cells = [(j, v) for j, v in enumerate(row[:24]) if v.strip()]
    
    # Cells beyond X (index 24+)
    garbage_cells = [(j, v) for j, v in enumerate(row) if j >= 24 and v.strip()]
    
    print(f'\nRow {i}:')
    print(f'  Valid cells (A-X): {len(valid_cells)}')
    print(f'  Garbage cells (Y+): {len(garbage_cells)}')
    
    if garbage_cells:
        print(f'  *** GARBAGE FOUND! ***')
        for col_idx, val in garbage_cells[:8]:
            preview = val[:50] + '...' if len(val) > 50 else val
            print(f'    [{col_letter(col_idx)}] (idx {col_idx}): "{preview}"')
        if len(garbage_cells) > 8:
            print(f'    ... and {len(garbage_cells) - 8} more cells')

# Summary
print()
print('=' * 70)
print('SUMMARY')
print('=' * 70)

total_garbage = sum(1 for row in all_data for j, v in enumerate(row) if j >= 24 and v.strip())
if total_garbage == 0:
    print('NO GARBAGE FOUND - Sheet is clean!')
else:
    print(f'GARBAGE FOUND: {total_garbage} cells beyond column X')
    print('This data may be from old buggy inserts or manual editing.')
