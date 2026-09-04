import json
import os
import re
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BASE_URL = "https://www.ss.com/lv/real-estate/flats/riga/centre/hand_over/"
BASE_URL_TEMPLATE = "https://www.ss.com/lv/real-estate/flats/riga/{district}/hand_over/"
DEFAULT_DISTRICTS = ["centre"]


CONFIG_PATH = Path(os.getenv("SS_CONFIG_PATH", BASE_DIR / "districts.json"))

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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE").strip()
MAX_NOTIFICATIONS_PER_BATCH = int(os.getenv("MAX_NOTIFICATIONS_PER_BATCH", "10"))
FLUSH_INTERVAL_SECONDS = int(os.getenv("FLUSH_INTERVAL_SECONDS", "30"))


def resolve_db_url(raw_url=None, password=None):
    url = (raw_url if raw_url is not None else os.getenv("DB_URL") or "").strip()
    if not url:
        return None
    pwd = (password if password is not None else os.getenv("DB_PASSWORD") or "").strip()

    # If placeholder is present and password is provided, substitute it
    if "[YOUR-PASSWORD]" in url and pwd:
        encoded_pwd = urllib.parse.quote_plus(pwd)
        url = url.replace("[YOUR-PASSWORD]", encoded_pwd)

    # Automatically and safely encode unencoded special characters in the URL password
    if "://" in url and "@" in url:
        scheme, _, rest = url.partition("://")
        user_info, _, host_info = rest.rpartition("@")
        if ":" in user_info:
            user, _, raw_pwd = user_info.partition(":")
            if raw_pwd and raw_pwd != "[YOUR-PASSWORD]":
                decoded_pwd = urllib.parse.unquote(raw_pwd)
                safe_pwd = urllib.parse.quote_plus(decoded_pwd)
                url = f"{scheme}://{user}:{safe_pwd}@{host_info}"

    return url


DB_URL = os.getenv("DB_URL")
if DB_URL:
    DB_URL = DB_URL.strip()

DB_PASSWORD = os.getenv("DB_PASSWORD")
FINAL_DB_URL = resolve_db_url(DB_URL, DB_PASSWORD)


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


DEFAULT_FILTERS = {
    "rooms_min": "",
    "rooms_max": "",
    "price_min": "",
    "price_max": "",
    "area_min": "",
    "area_max": "",
    "floor_min": "",
    "floor_max": "",
}


def load_config():
    payload = {}
    try:
        from db import db_load_app_config

        db_districts = db_load_app_config("districts")
        db_filters = db_load_app_config("filters")
        if db_districts is not None:
            try:
                payload["districts"] = json.loads(db_districts)
            except Exception:
                pass
        if db_filters is not None:
            try:
                payload["filters"] = json.loads(db_filters)
            except Exception:
                pass
    except Exception:
        pass

    if not payload and CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as file:
                file_payload = json.load(file)
                if isinstance(file_payload, dict):
                    payload = file_payload
        except (json.JSONDecodeError, OSError):
            payload = {}

    districts = normalize_districts(payload.get("districts", DEFAULT_DISTRICTS)) or list(DEFAULT_DISTRICTS)
    raw_filters = payload.get("filters", {})
    if not isinstance(raw_filters, dict):
        raw_filters = {}

    filters = dict(DEFAULT_FILTERS)
    for k in DEFAULT_FILTERS:
        if k in raw_filters and raw_filters[k] is not None:
            filters[k] = str(raw_filters[k]).strip()

    return {"districts": districts, "filters": filters}


def save_config(districts=None, filters=None):
    current = load_config()

    if districts is not None:
        normalized_d = normalize_districts(districts) or list(DEFAULT_DISTRICTS)
        current["districts"] = normalized_d

    if filters is not None:
        updated_f = dict(current["filters"])
        for k, v in filters.items():
            if k in DEFAULT_FILTERS:
                updated_f[k] = str(v).strip() if v is not None else ""
        current["filters"] = updated_f

    # Try saving to PostgreSQL DB
    try:
        from db import db_save_app_config

        db_save_app_config("districts", json.dumps(current["districts"]))
        db_save_app_config("filters", json.dumps(current["filters"]))
    except Exception:
        pass

    # Save to local file backup
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as file:
            json.dump(current, file, indent=2)
    except OSError:
        pass

    return current



def load_districts():
    return load_config()["districts"]


def save_districts(districts):
    return save_config(districts=districts)["districts"]


def load_filters():
    return load_config()["filters"]


def save_filters(filter_updates):
    return save_config(filters=filter_updates)["filters"]


def has_active_filters(filters=None):
    f = filters or load_filters()
    return any(bool(v) for v in f.values())


def build_filter_payload(district, filters=None):
    f = filters or load_filters()
    dist_name = normalize_district_name(district) or "all"
    sid_path = f"/lv/real-estate/flats/riga/{dist_name}/hand_over/"

    return {
        "topt[1][min]": f.get("rooms_min", ""),
        "topt[1][max]": f.get("rooms_max", ""),
        "topt[8][min]": f.get("price_min", ""),
        "topt[8][max]": f.get("price_max", ""),
        "topt[3][min]": f.get("area_min", ""),
        "topt[3][max]": f.get("area_max", ""),
        "topt[4][min]": f.get("floor_min", ""),
        "topt[4][max]": f.get("floor_max", ""),
        "opt[6]": "0",
        "opt[11]": "0",
        "sid": sid_path,
    }


def build_base_url_for_district(district):
    district_name = normalize_district_name(district)
    if not district_name:
        district_name = DEFAULT_DISTRICTS[0]
    return BASE_URL_TEMPLATE.format(district=district_name)


def get_target_urls():
    districts = load_districts()
    return [build_base_url_for_district(district) for district in districts]
