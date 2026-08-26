from bs4 import BeautifulSoup

from scraper import get_total_pages, parse_listings_from_page
from telegram import format_telegram_card


def test_get_total_pages_from_prev_link():
    html = """
    <html>
      <body>
        <a name="nav_id" rel="prev" href="/lv/real-estate/flats/riga/centre/hand_over/page12.html">Prev</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert get_total_pages(soup) == 12


def test_parse_listings_from_page_extracts_fields():
    html = """
    <table>
      <tr id="head_line"></tr>
      <tr id="tr_123">
        <td>1</td>
        <td>2</td>
        <td><a href="/lv/real-estate/flats/riga/centre/hand_over/123.html">Apartment</a></td>
        <td>Address 1</td>
        <td>2</td>
        <td>45</td>
        <td>5</td>
        <td>1940</td>
        <td>120</td>
        <td>900</td>
      </tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")

    result = parse_listings_from_page(soup)

    assert result == [{
        "id": "123",
        "category": "real-estate",
        "subcategory": "flats",
        "city": "riga",
        "district": "centre",
        "address": "Address 1",
        "rooms": "2",
        "area_sqm": "45",
        "floor": "5",
        "series": "1940",
        "price_per_sqm": "120",
        "price_monthly": "900",
        "description": "Apartment",
        "url": "https://www.ss.com/lv/real-estate/flats/riga/centre/hand_over/123.html",
    }]


def test_format_telegram_card_includes_summary_and_link():
    item = {
        "city": "riga",
        "district": "centre",
        "address": "Address 1",
        "price_monthly": "900",
        "price_per_sqm": "120",
        "rooms": "2",
        "area_sqm": "45",
        "floor": "5",
        "series": "1940",
        "description": "Nice apartment with balcony",
        "url": "https://www.ss.com/listing.html",
    }

    message = format_telegram_card(item)

    assert "New Listing (Riga - Centre)" in message
    assert "Address 1" in message
    assert "View on SS.com" in message
    assert "https://www.ss.com/listing.html" in message


def test_run_scraper_handles_network_errors(monkeypatch, tmp_path):
    import requests
    from main import run_scraper

    db_path = tmp_path / "test.db"
    monkeypatch.setattr("db.DB_PATH", str(db_path))
    monkeypatch.setattr("config.DB_PATH", str(db_path))

    def failing_fetch(*args, **kwargs):
        raise requests.RequestException("Simulated connection failure")

    monkeypatch.setattr("main.fetch_page", failing_fetch)
    # Should not raise exception
    count = run_scraper()
    assert count == 0
