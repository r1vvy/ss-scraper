import sqlite3

import db


def test_init_db_logs_errors(monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise sqlite3.DatabaseError("database is unavailable")

    monkeypatch.setattr(db.sqlite3, "connect", boom, raising=False)

    with caplog.at_level("ERROR"):
        try:
            db.init_db()
        except sqlite3.DatabaseError:
            pass

    assert "Database init failed" in caplog.text


def test_save_listing_and_duplicate_detection(tmp_path, monkeypatch):
    db_file = tmp_path / "ss_test.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_file), raising=False)

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

    db.save_listing(item)
    assert db.get_total_saved_count() == 1
