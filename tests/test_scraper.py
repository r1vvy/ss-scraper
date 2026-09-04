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

    monkeypatch.setattr("main.init_db", lambda: None)
    monkeypatch.setattr("main.get_total_saved_count", lambda: 0)

    def failing_fetch(*args, **kwargs):
        raise requests.RequestException("Simulated connection failure")

    monkeypatch.setattr("main.fetch_page", failing_fetch)
    # Should not raise exception and report 0 new listings with errors
    count, errors = run_scraper()
    assert count == 0
    assert len(errors) > 0


def test_run_scraper_applies_python_filters(monkeypatch):
    from bs4 import BeautifulSoup
    from main import run_scraper

    saved_items = []

    monkeypatch.setattr("main.init_db", lambda: None)
    monkeypatch.setattr("main.get_total_saved_count", lambda: 0)
    monkeypatch.setattr("main.load_districts", lambda: ["centre"])
    monkeypatch.setattr("main.get_target_urls", lambda: ["https://www.ss.com/lv/real-estate/flats/riga/centre/hand_over/"])
    monkeypatch.setattr("main.load_filters", lambda: {"price_max": "800", "area_min": "40"})
    monkeypatch.setattr("main.is_id_seen", lambda item_id: False)
    monkeypatch.setattr("main.save_listing", lambda item, notified=False: saved_items.append(item))
    monkeypatch.setattr("telegram.flush_pending_notifications", lambda chat_id=None: 0)

    html = """
    <table>
      <tr id="head_line"></tr>
      <tr id="tr_101">
        <td>1</td><td>2</td>
        <td><a href="/lv/real-estate/flats/riga/centre/hand_over/101.html">Apt 1</a></td>
        <td>Address 1</td><td>2</td><td>50</td><td>3</td><td>Series</td><td>100</td><td>500 €/mēn.</td>
      </tr>
      <tr id="tr_102">
        <td>1</td><td>2</td>
        <td><a href="/lv/real-estate/flats/riga/centre/hand_over/102.html">Apt 2</a></td>
        <td>Address 2</td><td>2</td><td>50</td><td>3</td><td>Series</td><td>100</td><td>900 €/mēn.</td>
      </tr>
      <tr id="tr_103">
        <td>1</td><td>2</td>
        <td><a href="/lv/real-estate/flats/riga/centre/hand_over/103.html">Apt 3</a></td>
        <td>Address 3</td><td>2</td><td>30</td><td>3</td><td>Series</td><td>100</td><td>400 €/mēn.</td>
      </tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    monkeypatch.setattr("main.post_filter_page", lambda session, url, payload: soup)

    total_new, errors = run_scraper()

    assert total_new == 1
    assert len(saved_items) == 1
    assert saved_items[0]["id"] == "101"

