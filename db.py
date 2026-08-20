import sqlite3

from config import DB_PATH, as_path


def get_connection():
    return sqlite3.connect(str(as_path(DB_PATH)))


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                category TEXT,
                subcategory TEXT,
                city TEXT,
                district TEXT,
                address TEXT,
                rooms TEXT,
                area_sqm TEXT,
                floor TEXT,
                series TEXT,
                price_per_sqm TEXT,
                price_monthly TEXT,
                description TEXT,
                url TEXT
            )
            """
        )
        conn.commit()


def is_id_seen(listing_id):
    if not listing_id:
        return True

    with get_connection() as conn:
        cursor = conn.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,))
        return cursor.fetchone() is not None


def save_listing(item):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO listings (
                id, category, subcategory, city, district, address, rooms,
                area_sqm, floor, series, price_per_sqm, price_monthly,
                description, url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.get("id", ""),
                item.get("category", ""),
                item.get("subcategory", ""),
                item.get("city", ""),
                item.get("district", ""),
                item.get("address", ""),
                item.get("rooms", ""),
                item.get("area_sqm", ""),
                item.get("floor", ""),
                item.get("series", ""),
                item.get("price_per_sqm", ""),
                item.get("price_monthly", ""),
                item.get("description", ""),
                item.get("url", ""),
            ),
        )
        conn.commit()


def get_total_saved_count():
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM listings")
        return cursor.fetchone()[0]
