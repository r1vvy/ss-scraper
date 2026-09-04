import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

import db


@pytest.fixture(autouse=True)
def mock_db_engine(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS public"))
    monkeypatch.setattr(db, "get_engine", lambda: engine)
    return engine


def test_init_db_logs_errors(monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise SQLAlchemyError("database is unavailable")

    # Mock get_engine to raise an error
    monkeypatch.setattr(db, "get_engine", boom)

    with caplog.at_level("ERROR"):
        try:
            db.init_db()
        except SQLAlchemyError:
            pass

    assert "Database init failed" in caplog.text


def test_save_listing_and_duplicate_detection():
    db.init_db()

    item = {
        "id": "listing-123",
        "category": "real-estate",
        "subcategory": "flats",
        "city": "riga",
        "district": "centre",
        "address": "Test Street 1",
        "rooms": "2",
        "area_sqm": "50",
        "floor": "3/6",
        "series": "1940",
        "price_per_sqm": "20",
        "price_monthly": "1000",
        "description": "Test listing",
        "url": "https://www.ss.com/test.html",
    }

    assert db.get_total_saved_count() == 0
    assert db.is_id_seen(item["id"]) is False

    db.save_listing(item)
    assert db.get_total_saved_count() == 1
    assert db.is_id_seen(item["id"]) is True

    # Save duplicate listing, should DO NOTHING (no conflict)
    db.save_listing(item)
    assert db.get_total_saved_count() == 1


def test_notified_status_and_helpers():
    db.init_db()

    item1 = {"id": "listing-1", "description": "Item 1"}
    item2 = {"id": "listing-2", "description": "Item 2"}

    db.save_listing(item1, notified=False)
    db.save_listing(item2, notified=True)

    assert db.get_unnotified_count() == 1
    unnotified = db.get_unnotified_listings(limit=10)
    assert len(unnotified) == 1
    assert unnotified[0]["id"] == "listing-1"

    db.mark_listing_notified("listing-1")
    assert db.get_unnotified_count() == 0
    assert len(db.get_unnotified_listings(limit=10)) == 0


def test_db_app_config():
    db.init_db()

    assert db.db_load_app_config("test_key") is None
    db.db_save_app_config("test_key", "test_value")
    assert db.db_load_app_config("test_key") == "test_value"


