import logging
import sqlite3
from config import DB_PATH, as_path, USE_POSTGRES, FINAL_DB_URL

logger = logging.getLogger(__name__)


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

    pg_schema = """
    CREATE TABLE IF NOT EXISTS public.listings (
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

    logger.info("Initializing DB schema for %s database", "Postgres" if USE_POSTGRES else "SQLite")

    try:
        if USE_POSTGRES:
            with _engine.begin() as conn:
                conn.execute(text(pg_schema))
            logger.info("Database schema ready for Postgres (public.listings)")
            return

        with get_connection() as conn:
            conn.execute(schema)
            conn.commit()
        logger.info("Database schema ready for SQLite at %s", DB_PATH)
    except Exception:
        logger.exception("Database init failed: schema creation or initialization error")
        raise


def is_id_seen(listing_id):
    if not listing_id:
        logger.debug("Skipping duplicate check for empty listing id")
        return True

    try:
        if USE_POSTGRES:
            with _engine.connect() as conn:
                result = conn.execute(text("SELECT 1 FROM public.listings WHERE id = :id"), {"id": listing_id})
                seen = result.fetchone() is not None
            logger.debug("Duplicate check for id=%s -> %s", listing_id, seen)
            return seen

        with get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,))
            seen = cursor.fetchone() is not None
        logger.debug("Duplicate check for id=%s -> %s", listing_id, seen)
        return seen
    except Exception:
        logger.exception("Database duplicate check failed for listing id=%s", listing_id)
        raise


def save_listing(item):
    listing_id = item.get("id", "")
    logger.debug("Saving listing id=%s district=%s", listing_id, item.get("district", ""))

    try:
        if USE_POSTGRES:
            stmt = text(
                """
                INSERT INTO public.listings (
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
                "id": listing_id,
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
            logger.info("Saved listing id=%s to Postgres (public.listings)", listing_id)
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
                    listing_id,
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
        logger.info("Saved listing id=%s to SQLite", listing_id)
    except Exception:
        logger.exception("Database save failed for listing id=%s", listing_id)
        raise


def get_total_saved_count():
    try:
        if USE_POSTGRES:
            with _engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM public.listings"))
                try:
                    count = int(result.scalar())
                except Exception:
                    row = result.fetchone()
                    count = int(row[0]) if row else 0
            logger.debug("Total saved count in Postgres: %s", count)
            return count

        with get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM listings")
            count = cursor.fetchone()[0]
        logger.debug("Total saved count in SQLite: %s", count)
        return count
    except Exception:
        logger.exception("Database count query failed")
        raise
