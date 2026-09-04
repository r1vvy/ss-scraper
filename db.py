import logging
from sqlalchemy import create_engine, text
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
    schema = """
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
        url TEXT,
        notified BOOLEAN DEFAULT FALSE
    )
    """

    logger.info("Initializing PostgreSQL DB schema (public.listings)")

    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text(schema))
            try:
                conn.execute(text("ALTER TABLE public.listings ADD COLUMN notified BOOLEAN DEFAULT FALSE"))
            except Exception:
                pass
        logger.info("Database schema ready (public.listings)")
    except Exception:
        logger.exception("Database init failed: schema creation or initialization error")
        raise



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


def save_listing(item, notified=False):
    listing_id = item.get("id", "")
    logger.debug("Saving listing id=%s district=%s notified=%s", listing_id, item.get("district", ""), notified)

    stmt = text(
        """
        INSERT INTO public.listings (
            id, category, subcategory, city, district, address, rooms,
            area_sqm, floor, series, price_per_sqm, price_monthly,
            description, url, notified
        ) VALUES (
            :id, :category, :subcategory, :city, :district, :address, :rooms,
            :area_sqm, :floor, :series, :price_per_sqm, :price_monthly,
            :description, :url, :notified
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
        "notified": bool(notified),
    }

    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(stmt, params)
        logger.info("Saved listing id=%s to public.listings (notified=%s)", listing_id, notified)
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


def get_unnotified_listings(limit=10):
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT id, category, subcategory, city, district, address,
                           rooms, area_sqm, floor, series, price_per_sqm,
                           price_monthly, description, url, notified
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

