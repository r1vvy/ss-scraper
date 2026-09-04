from unittest.mock import MagicMock, patch
import pytest

from sheets import (
    HEADER_ROW_1,
    HEADER_ROW_2,
    GoogleSheetsClient,
    append_to_sheets_if_enabled,
    format_listing_row,
)


def test_format_listing_row_values():
    item = {
        "id": "bpnni",
        "url": "https://www.ss.com/msg/lv/real-estate/flats/riga/yugla/bpnni.html",
        "price_monthly": "620",
        "area_sqm": "57",
        "rooms": "3",
        "address": "Silciema 11",
        "district": "yugla",
    }

    row = format_listing_row(item, nr=1)

    assert row == [
        1,
        "https://www.ss.com/msg/lv/real-estate/flats/riga/yugla/bpnni.html",
        620,
        57,
        3,
        "Silciema 11",
        "FALSE",
        "FALSE",
        "",
        "",
    ]


def test_sheets_client_is_configured():
    client_empty = GoogleSheetsClient(credentials_json="", credentials_file="")
    assert not client_empty.is_configured()

    client_with_json = GoogleSheetsClient(credentials_json='{"type": "service_account"}')
    assert client_with_json.is_configured()

    client_with_file = GoogleSheetsClient(credentials_file="/path/to/creds.json")
    assert client_with_file.is_configured()


def test_append_to_sheets_unconfigured_does_not_raise():
    item = {
        "id": "101",
        "url": "https://www.ss.com/item.html",
        "district": "centre",
    }
    with patch("sheets.get_sheets_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.is_configured.return_value = False
        mock_get_client.return_value = mock_client

        # Should not raise exception
        append_to_sheets_if_enabled(item)
        mock_client.append_listing.assert_not_called()


def test_google_sheets_client_append_listing_with_mock_gspread():
    mock_ws = MagicMock()
    mock_ws.title = "Yugla"
    mock_ws.get_all_values.return_value = []

    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.return_value = mock_ws
    mock_spreadsheet.title = "SS.com Real Estate Listings"

    mock_gspread_client = MagicMock()
    mock_gspread_client.open.return_value = mock_spreadsheet

    client = GoogleSheetsClient(credentials_json='{"type": "service_account"}')
    client.client = mock_gspread_client
    client.spreadsheet = mock_spreadsheet

    item = {
        "id": "bpnni",
        "url": "https://www.ss.com/msg/lv/real-estate/flats/riga/yugla/bpnni.html",
        "price_monthly": "620",
        "area_sqm": "57",
        "rooms": "3",
        "address": "Silciema 11",
        "district": "yugla",
    }

    result = client.append_listing(item)

    assert result is True
    # Verify calculated Nr is 1
    mock_ws.append_row.assert_called_once_with(
        [
            1,
            "https://www.ss.com/msg/lv/real-estate/flats/riga/yugla/bpnni.html",
            620,
            57,
            3,
            "Silciema 11",
            "FALSE",
            "FALSE",
            "",
            "",
        ],
        value_input_option="USER_ENTERED",
    )


def test_google_sheets_client_creates_blank_worksheet():
    import gspread

    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.side_effect = gspread.WorksheetNotFound
    mock_ws = MagicMock()
    mock_ws.title = "Centre"
    mock_spreadsheet.add_worksheet.return_value = mock_ws

    client = GoogleSheetsClient(credentials_json='{"type": "service_account"}')
    client.spreadsheet = mock_spreadsheet

    ws = client.get_or_create_worksheet("centre")

    assert ws == mock_ws
    mock_spreadsheet.add_worksheet.assert_called_once_with(title="Centre", rows=100, cols=10)
    assert mock_ws.append_row.call_count == 0

