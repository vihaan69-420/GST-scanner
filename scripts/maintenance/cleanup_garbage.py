"""
Clean up garbage data from Invoice_Header
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import config
import time

scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(config.GOOGLE_SHEETS_CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
ws = client.open_by_key(config.GOOGLE_SHEET_ID).worksheet('Invoice_Header')

print('=' * 60)
print('CLEANUP GARBAGE DATA')
print('=' * 60)

# Step 1: Clear columns Y onwards (all garbage)
print('\n1. Clearing columns Y onwards (Y1:ZZ1000)...')
ws.batch_clear(['Y1:ZZ1000'])
time.sleep(2)

# Step 2: Delete rows with no data in column A
print('\n2. Finding and deleting empty/garbage rows...')
all_data = ws.get_all_values()

rows_to_delete = []
for i, row in enumerate(all_data, 1):
    if i == 1:  # Skip header
        continue
    # Check if column A is empty
    if not row[0].strip():
        rows_to_delete.append(i)
        print(f'   Row {i}: Empty in column A - will delete')

# Delete from bottom to top to preserve row numbers
if rows_to_delete:
    for row_num in sorted(rows_to_delete, reverse=True):
        print(f'   Deleting row {row_num}...')
        ws.delete_rows(row_num)
        time.sleep(1)
else:
    print('   No empty rows found.')

# Step 3: Verify
print('\n3. Verifying...')
time.sleep(2)
all_data = ws.get_all_values()

print(f'\nFinal state:')
print(f'Total rows: {len(all_data)}')
print(f'Total columns: {len(all_data[0]) if all_data else 0}')

for i, row in enumerate(all_data, 1):
    non_empty = len([v for v in row if v.strip()])
    max_col = max([j for j, v in enumerate(row) if v.strip()], default=-1)
    print(f'Row {i}: {non_empty} cells, max col idx {max_col}')

print('\n' + '=' * 60)
print('CLEANUP COMPLETE!')
print('=' * 60)
