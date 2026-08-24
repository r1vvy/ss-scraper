import html
import time
import logging

import requests
from functools import lru_cache

from config import DEFAULT_DISTRICTS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, load_districts, save_districts


def fetch_updates(offset=None):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return []

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 30, "limit": 20}
    if offset is not None:
        params["offset"] = offset

    response = requests.get(url, params=params, timeout=35)
    response.raise_for_status()
    payload = response.json()
    return payload.get("result", [])


def format_telegram_card(item):
    """Formats a listing dict into an HTML Telegram card."""
    city = html.escape(str(item.get("city", "")).title())
    district = html.escape(str(item.get("district", "")).title())
    address = html.escape(str(item.get("address", "")))
    price_monthly = html.escape(str(item.get("price_monthly", "")))
    price_per_sqm = html.escape(str(item.get("price_per_sqm", "")))
    rooms = html.escape(str(item.get("rooms", "")))
    area_sqm = html.escape(str(item.get("area_sqm", "")))
    floor = html.escape(str(item.get("floor", "")))
    series = html.escape(str(item.get("series", "")))
    description = html.escape(str(item.get("description", "")))
    url = html.escape(str(item.get("url", "")), quote=True)

    preview = description[:150]
    if len(description) > 150:
        preview = f"{preview}..."

    return (
        f"<b>🏢 New Listing ({city} - {district})</b>\n\n"
        f"<b>📍 Address:</b> {address}\n"
        f"<b>💰 Price:</b> {price_monthly} ({price_per_sqm})\n"
        f"<b>📐 Details:</b> {rooms} room(s) | {area_sqm} m² | Floor {floor}\n"
        f"<b>🏗️ Series:</b> {series}\n"
        f"<b>📝 Desc:</b> {preview}\n\n"
        f"🔗 <a href='{url}'>View on SS.com</a>"
    )


def handle_district_command(command_text):
    text = (command_text or "").strip()
    if not text:
        return "Please provide a district, for example: /districts centre, mezciems"

    command, _, args = text.partition(" ")
    command = command.lower()

    if command in {"/districts", "/district"}:
        if not args.strip():
            current = ", ".join(load_districts()) or ", ".join(DEFAULT_DISTRICTS)
            return f"Current districts: {current}"

        districts = save_districts(args)
        return f"Updated districts: {', '.join(districts)}"

    if command in {"/reset_districts", "/resetdistricts"}:
        districts = save_districts(DEFAULT_DISTRICTS)
        return f"Reset districts to: {', '.join(districts)}"

    return "Unknown command. Use /districts or /reset_districts."


def handle_telegram_update(update):
    message = (update or {}).get("message", {})
    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")

    if not text:
        return None

    if not text.startswith("/"):
        return None

    response_text = handle_district_command(text)
    return {"chat_id": chat_id, "text": response_text}


def send_telegram_message(text, chat_id=None):
    """Sends an HTML formatted message to Telegram."""
    target_chat_id = chat_id if chat_id is not None else TELEGRAM_CHAT_ID
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or target_chat_id in {None, "YOUR_CHAT_ID_HERE"}:
        logger.warning("Telegram not configured. Skipping message send.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        body = exc.response.text if exc.response is not None else ""
        logger.exception("Failed to send Telegram message: %s %s", status, body)
    except requests.RequestException as exc:
        logger.exception("Failed to send Telegram message: %s", exc)


def process_telegram_command(update):
    command_response = handle_telegram_update(update)
    if not command_response:
        return False

    send_telegram_message(command_response["text"], chat_id=command_response.get("chat_id"))
    return True


def run_telegram_listener():
    """Poll Telegram for commands and update district configuration."""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Telegram bot token is not configured. Bot listener disabled.")
        return

    last_update_id = None
    while True:
        updates = fetch_updates(offset=last_update_id)
        for update in updates:
            update_id = update.get("update_id")
            process_telegram_command(update)
            if update_id is not None:
                last_update_id = update_id + 1

        time.sleep(5)
