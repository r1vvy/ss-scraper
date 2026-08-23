import sqlite3
from config import DB_PATH, as_path, USE_POSTGRES, FINAL_DB_URL


if USE_POSTGRES:
    # Lazy import to avoid requiring SQLAlchemy when not using Postgres
    from sqlalchemy import create_engine, text

    _engine = create_engine(FINAL_DB_URL)


def get_connection():
    """Return a DB connection/context manager.

    For SQLite this returns a `sqlite3.Connection`. For Postgres (SQLAlchemy)
    this returns a SQLAlchemy `Connection` object.
    """
    if USE_POSTGRES:
        return _engine.connect()

    return sqlite3.connect(str(as_path(DB_PATH)))


def init_db():
    schema = """
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

    if USE_POSTGRES:
        with _engine.begin() as conn:
            conn.execute(text(schema))
        return

    with get_connection() as conn:
        conn.execute(schema)
        conn.commit()


def is_id_seen(listing_id):
    if not listing_id:
        return True

    if USE_POSTGRES:
        with _engine.connect() as conn:
            result = conn.execute(text("SELECT 1 FROM listings WHERE id = :id"), {"id": listing_id})
            return result.fetchone() is not None

    with get_connection() as conn:
        cursor = conn.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,))
        return cursor.fetchone() is not None


def save_listing(item):
    if USE_POSTGRES:
        stmt = text(
            """
            INSERT INTO listings (
                id, category, subcategory, city, district, address, rooms,
                area_sqm, floor, series, price_per_sqm, price_monthly,
                description, url
            ) VALUES (
                :id, :category, :subcategory, :city, :district, :address, :rooms,
                :area_sqm, :floor, :series, :price_per_sqm, :price_monthly,
                :description, :url
            ) ON CONFLICT (id) DO NOTHING
            """
        )

        params = {
            "id": item.get("id", ""),
            "category": item.get("category", ""),
            "subcategory": item.get("subcategory", ""),
            "city": item.get("city", ""),
            "district": item.get("district", ""),
            "address": item.get("address", ""),
            "rooms": item.get("rooms", ""),
            "area_sqm": item.get("area_sqm", ""),
            "floor": item.get("floor", ""),
            "series": item.get("series", ""),
            "price_per_sqm": item.get("price_per_sqm", ""),
            "price_monthly": item.get("price_monthly", ""),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
        }

        with _engine.begin() as conn:
            conn.execute(stmt, params)

        return

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
    if USE_POSTGRES:
        with _engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM listings"))
            # SQLAlchemy Row supports scalar() in modern versions; fallback to fetchone
            try:
                return int(result.scalar())
            except Exception:
                row = result.fetchone()
                return int(row[0]) if row else 0

    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM listings")
        return cursor.fetchone()[0]
