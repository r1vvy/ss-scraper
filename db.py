import logging
from sqlalchemy import create_engine, inspect, text

from config import FINAL_DB_URL

logger = logging.getLogger("ss_scraper.db")

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        if not FINAL_DB_URL:
            raise ValueError("DB_URL is not configured. Please provide a Postgres connection URL.")
        _engine = create_engine(FINAL_DB_URL, pool_pre_ping=True)
    return _engine


def init_db():
    schema_listings = """
    CREATE TABLE public.listings (
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
        url TEXT,
        notified BOOLEAN DEFAULT FALSE,
        sheets_synced BOOLEAN DEFAULT FALSE
    )
    """

    schema_config = """
    CREATE TABLE public.app_config (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """

    logger.info("Checking database schema (public.listings & public.app_config)...")

    try:
        engine = get_engine()
        inspector = inspect(engine)

        try:
            existing_tables = set(inspector.get_table_names(schema="public"))
        except Exception:
            existing_tables = set()

        if not existing_tables:
            existing_tables = set(inspector.get_table_names())

        with engine.begin() as conn:
            if "listings" not in existing_tables:
                logger.info("Table 'listings' not found. Creating table public.listings...")
                conn.execute(text(schema_listings))
            else:
                logger.info("Table 'listings' already exists. Skipping creation.")

            if "app_config" not in existing_tables:
                logger.info("Table 'app_config' not found. Creating table public.app_config...")
                conn.execute(text(schema_config))
            else:
                logger.info("Table 'app_config' already exists. Skipping creation.")

        if "listings" in existing_tables:
            try:
                cols = [c["name"] for c in inspector.get_columns("listings", schema="public")]
            except Exception:
                try:
                    cols = [c["name"] for c in inspector.get_columns("listings")]
                except Exception:
                    cols = []

            if cols and "notified" not in cols:
                logger.info("Column 'notified' missing from listings table. Adding...")
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE public.listings ADD COLUMN notified BOOLEAN DEFAULT FALSE"))

            if cols and "sheets_synced" not in cols:
                logger.info("Column 'sheets_synced' missing from listings table. Adding...")
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE public.listings ADD COLUMN sheets_synced BOOLEAN DEFAULT FALSE"))

        logger.info("Database schema check complete. Ready.")
    except Exception:
        logger.exception("Database init failed: schema creation or initialization error")
        raise









def db_load_app_config(key):
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT value FROM public.app_config WHERE key = :key"), {"key": key})
            row = result.fetchone()
            return row[0] if row else None
    except Exception:
        logger.debug("Failed to fetch app_config key=%s from DB", key)
        return None


def db_save_app_config(key, value):
    stmt = text(
        """
        INSERT INTO public.app_config (key, value)
        VALUES (:key, :value)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """
    )
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(stmt, {"key": key, "value": str(value)})
        logger.info("Saved app_config key=%s to database", key)
    except Exception:
        logger.exception("Failed to save app_config key=%s to database", key)


def is_id_seen(listing_id):
    if not listing_id:
        logger.debug("Skipping duplicate check for empty listing id")
        return True

    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 FROM public.listings WHERE id = :id"), {"id": listing_id})
            seen = result.fetchone() is not None
        logger.debug("Duplicate check for id=%s -> %s", listing_id, seen)
        return seen
    except Exception:
        logger.exception("Database duplicate check failed for listing id=%s", listing_id)
        raise


def save_listing(item, notified=False, sheets_synced=False):
    listing_id = item.get("id", "")
    logger.debug("Saving listing id=%s district=%s notified=%s sheets_synced=%s", listing_id, item.get("district", ""), notified, sheets_synced)

    stmt = text(
        """
        INSERT INTO public.listings (
            id, category, subcategory, city, district, address, rooms,
            area_sqm, floor, series, price_per_sqm, price_monthly,
            url, notified, sheets_synced
        ) VALUES (
            :id, :category, :subcategory, :city, :district, :address, :rooms,
            :area_sqm, :floor, :series, :price_per_sqm, :price_monthly,
            :url, :notified, :sheets_synced
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
        "url": item.get("url", ""),
        "notified": bool(notified),
        "sheets_synced": bool(sheets_synced),
    }

    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(stmt, params)
        logger.info("Saved listing id=%s to public.listings (notified=%s, sheets_synced=%s)", listing_id, notified, sheets_synced)
    except Exception:
        logger.exception("Database save failed for listing id=%s", listing_id)
        raise


def mark_listing_notified(listing_id):
    if not listing_id:
        return
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.listings SET notified = TRUE WHERE id = :id"), {"id": listing_id})
        logger.debug("Marked listing id=%s as notified", listing_id)
    except Exception:
        logger.exception("Database update failed for marking listing id=%s as notified", listing_id)
        raise


def mark_listing_sheets_synced(listing_id):
    if not listing_id:
        return
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.listings SET sheets_synced = TRUE WHERE id = :id"), {"id": listing_id})
        logger.debug("Marked listing id=%s as sheets_synced", listing_id)
    except Exception:
        logger.exception("Database update failed for marking listing id=%s as sheets_synced", listing_id)
        raise


def get_unnotified_listings(limit=10):
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT id, category, subcategory, city, district, address,
                           rooms, area_sqm, floor, series, price_per_sqm,
                           price_monthly, url, notified, sheets_synced
                    FROM public.listings
                    WHERE notified = FALSE OR notified IS NULL
                    ORDER BY id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            rows = result.mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        logger.exception("Failed to query unnotified listings from database")
        return []


def get_unnotified_count():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM public.listings WHERE notified = FALSE OR notified IS NULL"))
            try:
                count = int(result.scalar())
            except Exception:
                row = result.fetchone()
                count = int(row[0]) if row else 0
        return count
    except Exception:
        logger.exception("Failed to query unnotified listing count")
        return 0


def get_unsynced_listings(limit=50):
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT id, category, subcategory, city, district, address,
                           rooms, area_sqm, floor, series, price_per_sqm,
                           price_monthly, url, notified, sheets_synced
                    FROM public.listings
                    WHERE sheets_synced = FALSE OR sheets_synced IS NULL
                    ORDER BY id ASC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            rows = result.mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        logger.exception("Failed to query unsynced listings from database")
        return []


def get_total_saved_count():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM public.listings"))
            try:
                count = int(result.scalar())
            except Exception:
                row = result.fetchone()
                count = int(row[0]) if row else 0
        logger.debug("Total saved count in Postgres: %s", count)
        return count
    except Exception:
        logger.exception("Database count query failed")
        raise



