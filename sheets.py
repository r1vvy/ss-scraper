import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ss_scraper.sheets")

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    gspread = None
    Credentials = None
    GSPREAD_AVAILABLE = False


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW_1 = ["Nr", "Links", "Cena, EUR", "Platība, m2", "Istabas", "Adrese", "Apskatits", "", "Komentari", ""]
HEADER_ROW_2 = ["", "", "", "", "", "", "Emils", "Estere", "Emils", "Estere"]


def format_listing_row(item: Dict[str, Any], nr: int) -> List[Any]:
    """Formats listing item dictionary into Google Sheet row values."""
    return [
        nr,
        item.get("url", ""),
        item.get("price_monthly", ""),
        item.get("area_sqm", ""),
        item.get("rooms", ""),
        item.get("address", ""),
        "FALSE",
        "FALSE",
        "",
        "",
    ]


class GoogleSheetsClient:
    def __init__(
        self,
        credentials_json: Optional[str] = None,
        credentials_file: Optional[str] = None,
        folder_name: Optional[str] = None,
        folder_id: Optional[str] = None,
        spreadsheet_name: Optional[str] = None,
        spreadsheet_id: Optional[str] = None,
    ):
        from config import (
            GOOGLE_CREDENTIALS_FILE,
            GOOGLE_SHEETS_CREDENTIALS,
            GOOGLE_SHEETS_FOLDER_ID,
            GOOGLE_SHEETS_FOLDER_NAME,
            GOOGLE_SPREADSHEET_ID,
            GOOGLE_SPREADSHEET_NAME,
        )

        self.credentials_json = credentials_json or GOOGLE_SHEETS_CREDENTIALS
        self.credentials_file = credentials_file or GOOGLE_CREDENTIALS_FILE
        self.folder_name = folder_name or GOOGLE_SHEETS_FOLDER_NAME
        self.folder_id = folder_id or GOOGLE_SHEETS_FOLDER_ID
        self.spreadsheet_name = spreadsheet_name or GOOGLE_SPREADSHEET_NAME or "SS.com Real Estate Listings"
        self.spreadsheet_id = spreadsheet_id or GOOGLE_SPREADSHEET_ID

        self.client = None
        self.spreadsheet = None
        self._worksheets_cache = {}

    def is_configured(self) -> bool:
        return bool(self.credentials_json or self.credentials_file)

    def _get_credentials(self):
        if not GSPREAD_AVAILABLE:
            raise RuntimeError("gspread or google-auth package is not installed.")

        # Try raw JSON or Secret string
        cred_data = self.credentials_json
        if not cred_data and not self.credentials_file:
            # Try secret manager fallback if available
            try:
                from app import get_secret
                cred_data = get_secret("GOOGLE_SHEETS_CREDENTIALS")
            except Exception:
                cred_data = None

        if cred_data:
            try:
                info = json.loads(cred_data)
                return Credentials.from_service_account_info(info, scopes=SCOPES)
            except Exception as err:
                logger.error("Failed to parse GOOGLE_SHEETS_CREDENTIALS JSON: %s", err)

        if self.credentials_file and os.path.exists(self.credentials_file):
            return Credentials.from_service_account_file(self.credentials_file, scopes=SCOPES)

        raise ValueError("No valid Google credentials provided via JSON string or file path.")

    def connect(self) -> bool:
        if not self.is_configured():
            logger.debug("Google Sheets credentials not configured. Client disabled.")
            return False

        try:
            creds = self._get_credentials()
            self.client = gspread.authorize(creds)
            self.spreadsheet = self._open_spreadsheet()
            logger.info("Successfully connected to Google Sheet: '%s'", self.spreadsheet.title)
            return True
        except Exception as exc:
            logger.error("Failed to connect to Google Sheets: %s", exc)
            self.client = None
            self.spreadsheet = None
            return False

    def _open_spreadsheet(self):
        if self.spreadsheet_id:
            logger.info("Opening Google Sheet by ID: %s", self.spreadsheet_id)
            return self.client.open_by_key(self.spreadsheet_id)

        if self.spreadsheet_name:
            logger.info("Opening Google Sheet by title: '%s'", self.spreadsheet_name)
            return self.client.open(self.spreadsheet_name)

        raise ValueError("Neither GOOGLE_SPREADSHEET_ID nor GOOGLE_SPREADSHEET_NAME is configured.")

    def get_or_create_worksheet(self, district_name: str):
        if not self.spreadsheet:
            return None

        title = district_name.strip().title() if district_name else "General"
        if title in self._worksheets_cache:
            return self._worksheets_cache[title]

        try:
            ws = self.spreadsheet.worksheet(title)
            self._worksheets_cache[title] = ws
            return ws
        except gspread.WorksheetNotFound:
            pass

        try:
            # Create worksheet and write initial headers
            ws = self.spreadsheet.add_worksheet(title=title, rows=100, cols=10)
            ws.append_row(HEADER_ROW_1, value_input_option="USER_ENTERED")
            ws.append_row(HEADER_ROW_2, value_input_option="USER_ENTERED")
            self._worksheets_cache[title] = ws
            logger.info("Created new worksheet tab '%s' with headers.", title)

            # If default "Sheet1" exists and is blank, delete it if there are other sheets
            try:
                sheet1 = self.spreadsheet.worksheet("Sheet1")
                if len(self.spreadsheet.worksheets()) > 1 and len(sheet1.get_all_values()) == 0:
                    self.spreadsheet.del_worksheet(sheet1)
            except Exception:
                pass

            return ws
        except Exception as exc:
            logger.error("Failed to create worksheet tab '%s': %s", title, exc)
            return None

    def append_listing(self, item: Dict[str, Any]) -> bool:
        if not self.client or not self.spreadsheet:
            if not self.connect():
                return False

        district = item.get("district", "General") or "General"
        ws = self.get_or_create_worksheet(district)
        if not ws:
            return False

        try:
            all_values = ws.get_all_values()
            if not all_values:
                ws.append_row(HEADER_ROW_1, value_input_option="USER_ENTERED")
                ws.append_row(HEADER_ROW_2, value_input_option="USER_ENTERED")
                all_values = [HEADER_ROW_1, HEADER_ROW_2]

            # Check if URL already exists in this worksheet to avoid duplicates
            url = item.get("url", "").strip()
            if url:
                existing_urls = {row[1].strip() for row in all_values if len(row) > 1 and row[1]}
                if url in existing_urls:
                    logger.debug("Listing url=%s already exists in worksheet '%s'. Skipping duplicate append.", url, ws.title)
                    return True

            # Calculate Nr based on current data rows (excluding 2 header rows)
            data_row_count = max(0, len(all_values) - 2)
            nr = data_row_count + 1

            row_data = format_listing_row(item, nr)
            ws.append_row(row_data, value_input_option="USER_ENTERED")
            logger.info("Appended listing id=%s (Nr=%d) to sheet '%s'", item.get("id"), nr, ws.title)
            return True
        except Exception as exc:
            logger.error("Failed to append listing id=%s to Google Sheet: %s", item.get("id"), exc)
            return False

    def append_listings(self, items: List[Dict[str, Any]]) -> int:
        if not items:
            return 0
        success_count = 0
        for item in items:
            if self.append_listing(item):
                success_count += 1
        return success_count


_global_sheets_client = None


def get_sheets_client() -> GoogleSheetsClient:
    global _global_sheets_client
    if _global_sheets_client is None:
        _global_sheets_client = GoogleSheetsClient()
    return _global_sheets_client


def append_to_sheets_if_enabled(item: Dict[str, Any]) -> bool:
    client = get_sheets_client()
    if client.is_configured():
        try:
            success = client.append_listing(item)
            if success and item.get("id"):
                from db import mark_listing_sheets_synced
                mark_listing_sheets_synced(item["id"])
            return success
        except Exception as exc:
            logger.error("Error sending listing to Google Sheets: %s", exc)
    return False


def sync_db_listings_to_sheets(batch_size: int = 50) -> tuple[int, int]:
    """Export unsynced listings from database to Google Sheets in small batches."""
    from db import get_unsynced_listings, mark_listing_sheets_synced

    client = get_sheets_client()
    if not client.is_configured():
        logger.warning("Cannot sync DB to Google Sheets: Client is not configured.")
        return 0, 0

    pending_items = get_unsynced_listings(limit=batch_size)
    if not pending_items:
        logger.info("No unsynced listings found in database.")
        return 0, 0

    logger.info("Syncing batch of %d unsynced listing(s) to Google Sheets...", len(pending_items))
    synced_count = 0
    for item in pending_items:
        if client.append_listing(item):
            if item.get("id"):
                mark_listing_sheets_synced(item["id"])
            synced_count += 1

    logger.info("Sync batch complete. Appended %d/%d listings to Google Sheets.", synced_count, len(pending_items))
    return synced_count, len(pending_items)


