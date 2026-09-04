import pytest
from unittest.mock import MagicMock

from config import (
    DEFAULT_FILTERS,
    build_filter_payload,
    has_active_filters,
    load_filters,
    save_filters,
)
from scraper import post_filter_page
from telegram import handle_district_command


def test_build_filter_payload_format():
    custom_filters = {
        "rooms_min": "1",
        "rooms_max": "3",
        "price_min": "300",
        "price_max": "800",
        "area_min": "40",
        "area_max": "",
        "floor_min": "",
        "floor_max": "",
    }

    payload = build_filter_payload("centre", filters=custom_filters)

    assert payload == {
        "topt[1][min]": "1",
        "topt[1][max]": "3",
        "topt[8][min]": "300",
        "topt[8][max]": "800",
        "topt[3][min]": "40",
        "topt[3][max]": "",
        "topt[4][min]": "",
        "topt[4][max]": "",
        "opt[6]": "0",
        "opt[11]": "0",
        "sid": "/lv/real-estate/flats/riga/centre/hand_over/",
    }


def test_has_active_filters():
    assert has_active_filters(DEFAULT_FILTERS) is False

    active = dict(DEFAULT_FILTERS)
    active["price_max"] = "800"
    assert has_active_filters(active) is True


def test_save_and_load_filters(tmp_path, monkeypatch):
    config_path = tmp_path / "districts.json"
    monkeypatch.setattr("config.CONFIG_PATH", config_path)

    save_filters({"price_min": "300", "price_max": "800", "rooms_min": "2"})
    loaded = load_filters()

    assert loaded["price_min"] == "300"
    assert loaded["price_max"] == "800"
    assert loaded["rooms_min"] == "2"
    assert loaded["area_min"] == ""


def test_telegram_filter_commands(tmp_path, monkeypatch):
    config_path = tmp_path / "districts.json"
    monkeypatch.setattr("config.CONFIG_PATH", config_path)

    # View filters (default empty)
    resp = handle_district_command("/filter")
    assert "Current Search Filters:" in resp

    # Set price
    resp = handle_district_command("/filter price 300 800")
    assert "300 - 800 €" in resp

    # Set rooms
    resp = handle_district_command("/filter rooms 1 3")
    assert "1 - 3" in resp

    # Clear filters
    resp = handle_district_command("/filter clear")
    assert "Cleared all filters" in resp
    assert "Any - Any" in resp


def test_post_filter_page_issues_post_request(monkeypatch):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "<html><body><tr id='head_line'></tr></body></html>"
    mock_session.post.return_value = mock_response

    payload = {"topt[8][min]": "300"}
    soup = post_filter_page(mock_session, "https://www.ss.com/lv/real-estate/flats/riga/centre/hand_over/filter/", payload)

    assert mock_session.post.called
    args, kwargs = mock_session.post.call_args
    assert args[0] == "https://www.ss.com/lv/real-estate/flats/riga/centre/hand_over/filter/"
    assert kwargs["data"] == payload
    assert kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert soup.find("tr", id="head_line") is not None


def test_extract_number():
    from config import extract_number

    assert extract_number("900  €/mēn.") == 900.0
    assert extract_number("1,100  €/mēn.") == 1100.0
    assert extract_number("1 200 €") == 1200.0
    assert extract_number("45 m²") == 45.0
    assert extract_number("45.5") == 45.5
    assert extract_number("5/6") == 5.0
    assert extract_number("2") == 2.0
    assert extract_number(None) is None
    assert extract_number("") is None
    assert extract_number("-") is None


def test_matches_filters():
    from config import matches_filters

    filters = {
        "price_min": "300",
        "price_max": "800",
        "area_min": "40",
        "area_max": "",
        "rooms_min": "1",
        "rooms_max": "3",
        "floor_min": "",
        "floor_max": "",
    }

    # Matches
    item_good = {
        "price_monthly": "500 €/mēn.",
        "area_sqm": "50",
        "rooms": "2",
        "floor": "3/5",
    }
    assert matches_filters(item_good, filters) is True

    # Price too high (900 €) -> Should FAIL
    item_expensive = {
        "price_monthly": "900 €/mēn.",
        "area_sqm": "50",
        "rooms": "2",
        "floor": "3/5",
    }
    assert matches_filters(item_expensive, filters) is False

    # Area too small (35 m²) -> Should FAIL
    item_small = {
        "price_monthly": "500 €/mēn.",
        "area_sqm": "35",
        "rooms": "2",
        "floor": "3/5",
    }
    assert matches_filters(item_small, filters) is False

    # Rooms too high (4 rooms) -> Should FAIL
    item_many_rooms = {
        "price_monthly": "500 €/mēn.",
        "area_sqm": "50",
        "rooms": "4",
        "floor": "3/5",
    }
    assert matches_filters(item_many_rooms, filters) is False


