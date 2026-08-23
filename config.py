import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BASE_URL = "https://www.ss.com/lv/real-estate/flats/riga/centre/hand_over/"
BASE_URL_TEMPLATE = "https://www.ss.com/lv/real-estate/flats/riga/{district}/hand_over/"
DEFAULT_DISTRICTS = ["centre"]


def as_path(value):
    return Path(value) if not isinstance(value, Path) else value


CONFIG_PATH = as_path(os.getenv("SS_CONFIG_PATH", BASE_DIR / "districts.json"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "lv,en-US;q=0.9,en;q=0.8",
}

REQUEST_TIMEOUT_SECONDS = 15
REQUEST_DELAY_RANGE = (1.5, 3.0)
DB_PATH = as_path(os.getenv("SS_DB_PATH", BASE_DIR / "ss_listings.db"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

DB_URL = os.getenv("DB_URL")

# If DB_URL is set, use Postgres (Supabase). Otherwise fall back to SQLite.
FINAL_DB_URL = DB_URL
USE_POSTGRES = bool(FINAL_DB_URL)


def normalize_district_name(value):
    if value is None:
        return ""

    cleaned = str(value).strip().lower().replace("_", "-")
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"[^a-z0-9-]+", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned


def normalize_districts(raw_districts):
    if raw_districts is None:
        return []

    if isinstance(raw_districts, str):
        values = [part.strip() for part in raw_districts.split(",")]
    else:
        values = list(raw_districts)

    normalized = []
    seen = set()
    for item in values:
        district = normalize_district_name(item)
        if not district or district in seen:
            continue
        normalized.append(district)
        seen.add(district)

    return normalized


def load_districts():
    config_path = as_path(CONFIG_PATH)
    if not config_path.exists():
        return list(DEFAULT_DISTRICTS)

    try:
        with config_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (json.JSONDecodeError, OSError):
        return list(DEFAULT_DISTRICTS)

    districts = payload.get("districts", DEFAULT_DISTRICTS)
    return normalize_districts(districts) or list(DEFAULT_DISTRICTS)


def save_districts(districts):
    normalized = normalize_districts(districts)
    if not normalized:
        normalized = list(DEFAULT_DISTRICTS)

    payload = {"districts": normalized}
    config_path = as_path(CONFIG_PATH)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    return normalized


def build_base_url_for_district(district):
    district_name = normalize_district_name(district)
    if not district_name:
        district_name = DEFAULT_DISTRICTS[0]
    return BASE_URL_TEMPLATE.format(district=district_name)


def get_target_urls():
    districts = load_districts()
    return [build_base_url_for_district(district) for district in districts]
