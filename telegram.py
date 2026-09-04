import html
import logging
import threading
import time

import requests
from functools import lru_cache
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from config import (
    DEFAULT_DISTRICTS,
    DEFAULT_FILTERS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    load_districts,
    load_filters,
    save_districts,
    save_filters,
)

logger = logging.getLogger("ss_scraper.telegram")


def format_telegram_card(item):
    """Formats a listing dict into an HTML Telegram card."""
    city = html.escape(str(item.get("city", "") or "").title())
    district = html.escape(str(item.get("district", "") or "").title())
    address = html.escape(str(item.get("address", "") or ""))
    price_monthly = html.escape(str(item.get("price_monthly", "") or ""))
    price_per_sqm = html.escape(str(item.get("price_per_sqm", "") or ""))
    rooms = html.escape(str(item.get("rooms", "") or ""))
    area_sqm = html.escape(str(item.get("area_sqm", "") or ""))
    floor = html.escape(str(item.get("floor", "") or ""))
    series = html.escape(str(item.get("series", "") or ""))
    url = html.escape(str(item.get("url", "") or ""), quote=True)

    return (
        f"<b>🏢 New Listing ({city} - {district})</b>\n\n"
        f"<b>📍 Address:</b> {address}\n"
        f"<b>💰 Price:</b> {price_monthly} ({price_per_sqm})\n"
        f"<b>📐 Details:</b> {rooms} room(s) | {area_sqm} m² | Floor {floor}\n"
        f"<b>🏗️ Series:</b> {series}\n\n"
        f"🔗 <a href=\"{url}\">View on SS.com</a>"
    )



def flush_pending_notifications(chat_id=None, limit=None):
    from config import MAX_NOTIFICATIONS_PER_BATCH
    from db import get_unnotified_listings, mark_listing_notified

    batch_limit = limit if limit is not None else MAX_NOTIFICATIONS_PER_BATCH
    pending_items = get_unnotified_listings(limit=batch_limit)
    if not pending_items:
        return 0

    sent_count = 0
    for item in pending_items:
        message = format_telegram_card(item)
        success = send_telegram_message(message, chat_id=chat_id)
        if success:
            mark_listing_notified(item["id"])
            sent_count += 1
        else:
            logger.warning("Failed to send Telegram notification for item id=%s", item.get("id"))
    return sent_count


def format_filter_summary(filters):
    lines = ["<b>Current Search Filters:</b>\n"]
    lines.append(f"• <b>Rooms:</b> {filters.get('rooms_min') or 'Any'} - {filters.get('rooms_max') or 'Any'}")
    lines.append(f"• <b>Price:</b> {filters.get('price_min') or 'Any'} - {filters.get('price_max') or 'Any'} €")
    lines.append(f"• <b>Area:</b> {filters.get('area_min') or 'Any'} - {filters.get('area_max') or 'Any'} m²")
    lines.append(f"• <b>Floor:</b> {filters.get('floor_min') or 'Any'} - {filters.get('floor_max') or 'Any'}")
    return "\n".join(lines)


def handle_district_command(command_text, chat_id=None):
    text = (command_text or "").strip()
    if not text:
        return "Please provide a command. Use /help for available commands."

    command, _, args = text.partition(" ")
    cmd = command.partition("@")[0].lower()
    args_str = args.strip()

    if cmd in {"/districts", "/district"}:
        if not args_str:
            current = ", ".join(load_districts()) or ", ".join(DEFAULT_DISTRICTS)
            return f"Current districts: {current}"

        districts = save_districts(args_str)
        return f"Updated districts: {', '.join(districts)}"

    if cmd in {"/reset_districts", "/resetdistricts"}:
        districts = save_districts(DEFAULT_DISTRICTS)
        return f"Reset districts to: {', '.join(districts)}"

    if cmd in {"/filter", "/filters", "/set_filter", "/setfilter"}:
        if not args_str:
            return format_filter_summary(load_filters())

        parts = args_str.split()
        param = parts[0].lower()

        if param in {"clear", "reset"}:
            updated = save_filters(DEFAULT_FILTERS)
            return f"✅ Cleared all filters.\n\n{format_filter_summary(updated)}"

        if len(parts) >= 2 and param in {"rooms", "room", "price", "area", "floor"}:
            min_val = parts[1] if parts[1] != "-" else ""
            max_val = parts[2] if len(parts) >= 3 and parts[2] != "-" else ""

            updates = {}
            if param in {"rooms", "room"}:
                updates["rooms_min"] = min_val
                updates["rooms_max"] = max_val
            elif param == "price":
                updates["price_min"] = min_val
                updates["price_max"] = max_val
            elif param == "area":
                updates["area_min"] = min_val
                updates["area_max"] = max_val
            elif param == "floor":
                updates["floor_min"] = min_val
                updates["floor_max"] = max_val

            updated = save_filters(updates)
            return f"✅ Updated filter!\n\n{format_filter_summary(updated)}"

        return (
            "Usage:\n"
            "• <code>/filter</code> - View current filters\n"
            "• <code>/filter price &lt;min&gt; [max]</code> (e.g. <code>/filter price 300 800</code>)\n"
            "• <code>/filter rooms &lt;min&gt; [max]</code> (e.g. <code>/filter rooms 1 3</code>)\n"
            "• <code>/filter area &lt;min&gt; [max]</code> (e.g. <code>/filter area 40</code>)\n"
            "• <code>/filter floor &lt;min&gt; [max]</code>\n"
            "• <code>/filter clear</code> - Reset filters"
        )

    if cmd in {"/reset_filters", "/resetfilters"}:
        updated = save_filters(DEFAULT_FILTERS)
        return f"✅ Reset filters to default.\n\n{format_filter_summary(updated)}"

    if cmd in {"/scrape", "/run", "/run_scrape"}:
        from main import trigger_scrape

        _, msg = trigger_scrape(chat_id=chat_id, async_run=True)
        return msg


    if cmd in {"/help", "/start"}:
        return (
            "<b>SS Scraper Bot Commands:</b>\n\n"
            "• <code>/scrape</code> - Trigger scraper manually\n"
            "• <code>/districts</code> - View or update monitored districts\n"
            "• <code>/reset_districts</code> - Reset districts to default\n"
            "• <code>/filter</code> - View or set search filters (price, rooms, area, floor)\n"
            "• <code>/reset_filters</code> - Clear all search filters\n"
            "• <code>/help</code> - Show this help message"
        )

    return "Unknown command. Use /scrape, /districts, /filter, or /help."


def handle_telegram_update(update):
    message = (update or {}).get("message", {})
    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")

    if not text:
        return None

    if not text.startswith("/"):
        return None

    response_text = handle_district_command(text, chat_id=chat_id)
    return {"chat_id": chat_id, "text": response_text}


_last_telegram_send_time = 0.0
_send_lock = threading.Lock()


class TelegramRateLimitError(Exception):
    def __init__(self, retry_after=3):
        self.retry_after = retry_after
        super().__init__(f"Telegram Rate Limit (retry after {retry_after}s)")


def _wait_telegram_retry(retry_state):
    exc = retry_state.outcome.exception()
    if isinstance(exc, TelegramRateLimitError):
        return float(exc.retry_after + 1)
    return 2.0


@retry(
    stop=stop_after_attempt(5),
    wait=_wait_telegram_retry,
    retry=retry_if_exception_type((TelegramRateLimitError, requests.RequestException)),
    reraise=False,
)
def _send_telegram_http_request(url, payload):
    global _last_telegram_send_time

    with _send_lock:
        now = time.time()
        elapsed = now - _last_telegram_send_time
        if elapsed < 1.05:
            time.sleep(1.05 - elapsed)
        _last_telegram_send_time = time.time()

    response = requests.post(url, json=payload, timeout=10)
    if response.status_code == 429:
        retry_after = 3
        try:
            res_json = response.json()
            retry_after = int(res_json.get("parameters", {}).get("retry_after", 3))
        except Exception:
            pass
        logger.warning("Telegram API rate limit (429) encountered. Retrying after %d seconds...", retry_after)
        raise TelegramRateLimitError(retry_after)

    response.raise_for_status()
    return True


def send_telegram_message(text, chat_id=None, max_retries=5):
    """Sends an HTML formatted message to Telegram with 429 rate limit backoff using Tenacity."""
    target_chat_id = chat_id if chat_id is not None else TELEGRAM_CHAT_ID
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or target_chat_id in {None, "YOUR_CHAT_ID_HERE"}:
        logger.warning("Telegram not configured. Skipping message send.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        return bool(_send_telegram_http_request(url, payload))
    except Exception as exc:
        logger.exception("Failed to send Telegram message after retries: %s", exc)
        return False


def process_telegram_command(update):
    command_response = handle_telegram_update(update)
    if not command_response:
        return False

    send_telegram_message(command_response["text"], chat_id=command_response.get("chat_id"))
    return True


def fetch_updates(offset=None):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return []

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 30, "limit": 20}
    if offset is not None:
        params["offset"] = offset

    try:
        response = requests.get(url, params=params, timeout=35)
        response.raise_for_status()
        payload = response.json()
        return payload.get("result", [])
    except requests.RequestException as exc:
        logger.warning("Failed to fetch Telegram updates: %s", exc)
        return []


def run_telegram_listener():
    """Poll Telegram for commands and update district configuration."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.info("Telegram bot token is not configured. Bot listener disabled.")
        return

    last_update_id = None
    logger.info("Starting Telegram bot listener (polling)...")
    while True:
        try:
            updates = fetch_updates(offset=last_update_id)
            for update in updates:
                update_id = update.get("update_id")
                process_telegram_command(update)
                if update_id is not None:
                    last_update_id = update_id + 1
        except Exception as exc:
            logger.exception("Error in Telegram listener polling loop: %s", exc)

        time.sleep(5)
