"""
Order Upload – Google Drive PDF Uploader
=========================================

Uploads generated order PDFs to Google Drive and returns a shareable link.

This is used as a workaround when corporate firewalls (e.g. Zscaler) block
Telegram's sendDocument API but allow Google Drive access.

Guardrails:
- New file, does NOT modify any existing logic.
- Uses the same service account credentials as Google Sheets.
- Uploads to a configurable Drive folder (or root if not set).
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from src import config
except ImportError:
    import config

# Google API imports
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _get_drive_service():
    """Create a Google Drive API service using service account credentials."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_path = config.get_credentials_path()
    if creds_path:
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    else:
        import google.auth
        creds, _ = google.auth.default(scopes=scope)

    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_pdf_to_drive(
    pdf_path: str,
    folder_id: Optional[str] = None,
) -> Optional[str]:
    """
    Upload a PDF file to Google Drive and return a shareable link.

    Args:
        pdf_path: Local path to the PDF file.
        folder_id: Optional Google Drive folder ID. If not provided,
                   uses ORDER_UPLOAD_DRIVE_FOLDER_ID from config, or
                   uploads to the service account's root folder.

    Returns:
        A public web-viewable link, or None if upload fails.
    """
    if not os.path.exists(pdf_path):
        print(f"[DriveUpload] PDF not found: {pdf_path}")
        return None

    try:
        service = _get_drive_service()

        # Determine target folder
        target_folder = folder_id or getattr(config, "ORDER_UPLOAD_DRIVE_FOLDER_ID", None)

        # File metadata
        file_metadata = {
            "name": os.path.basename(pdf_path),
            "mimeType": "application/pdf",
        }
        if target_folder:
            file_metadata["parents"] = [target_folder]

        media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=True)

        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
        ).execute()

        file_id = uploaded.get("id")

        # Make the file viewable by anyone with the link
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()

        web_link = uploaded.get("webViewLink")
        if not web_link:
            web_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

        print(f"[DriveUpload] PDF uploaded: {web_link}")
        return web_link

    except Exception as e:
        print(f"[DriveUpload] Upload failed: {e}")
        return None
