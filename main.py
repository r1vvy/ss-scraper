import html
import random
import threading
import time

import requests

from config import HEADERS, REQUEST_DELAY_RANGE, TELEGRAM_BOT_TOKEN, get_target_urls, load_districts
from db import get_total_saved_count, init_db, is_id_seen, save_listing
from scraper import fetch_page, get_total_pages, parse_listings_from_page
from telegram import format_telegram_card, run_telegram_listener, send_telegram_message


def run_scraper(notify_chat_id=None):
    init_db()
    is_first_run = get_total_saved_count() == 0
    target_urls = get_target_urls()

    if not target_urls:
        target_urls = ["https://www.ss.com/lv/real-estate/flats/riga/centre/hand_over/"]

    session = requests.Session()
    session.headers.update(HEADERS)

    total_new_listings = 0

    for district_index, base_url in enumerate(target_urls, start=1):
        print(f"Fetching listings for district {district_index}/{len(target_urls)}: {base_url}")

        try:
            first_page = fetch_page(session, base_url)
        except requests.RequestException as err:
            print(f"Error fetching district {base_url}: {err}")
            continue

        total_pages = get_total_pages(first_page)
        print(f"Total pages identified: {total_pages}")

        for page_number in range(1, total_pages + 1):
            page_url = base_url if page_number == 1 else f"{base_url}page{page_number}.html"
            try:
                soup = first_page if page_number == 1 else fetch_page(session, page_url)
            except requests.RequestException as err:
                print(f"Error fetching page {page_url}: {err}")
                continue

            page_data = parse_listings_from_page(soup)
            print(f"Scraping page {page_number}/{total_pages}: {page_url}")
            print(f"  -> Found {len(page_data)} listings.")

            for item in page_data:
                item_id = item.get("id", "")
                if item_id and is_id_seen(item_id):
                    continue

                save_listing(item)
                total_new_listings += 1

                if not is_first_run:
                    message = format_telegram_card(item)
                    send_telegram_message(message, chat_id=notify_chat_id)
                    time.sleep(1)

            if page_number < total_pages:
                time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

    print(f"Scraping complete. Extracted {total_new_listings} total listings.")
    return total_new_listings


_scrape_lock = threading.Lock()


def is_scraping_running() -> bool:
    return _scrape_lock.locked()


def trigger_scrape(chat_id=None):
    """Starts scraper in a background thread if not already running."""
    if not _scrape_lock.acquire(blocking=False):
        return False, "⚠️ A scrape is already in progress. Please wait for it to finish."

    districts = load_districts()
    districts_str = ", ".join(districts)

    def _worker():
        try:
            total_new = run_scraper(notify_chat_id=chat_id)
            if chat_id:
                if total_new == 0:
                    send_telegram_message("✅ Scraping complete. No new listings found.", chat_id=chat_id)
                else:
                    send_telegram_message(
                        f"✅ Scraping complete. Found <b>{total_new}</b> new listing(s).",
                        chat_id=chat_id,
                    )
        except Exception as exc:
            print(f"Error during scrape: {exc}")
            if chat_id:
                send_telegram_message(f"❌ Error during scrape: {html.escape(str(exc))}", chat_id=chat_id)
        finally:
            _scrape_lock.release()

    thread = threading.Thread(target=_worker, name="manual-scrape-worker", daemon=True)
    thread.start()
    return True, f"🚀 Scrape started for districts: <b>{html.escape(districts_str)}</b>"


def start_background_services():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return

    listener_thread = threading.Thread(
        target=run_telegram_listener,
        name="telegram-listener",
        daemon=True,
    )
    listener_thread.start()
    print("Telegram listener started in background.")


if __name__ == "__main__":
    start_background_services()
    run_scraper()
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
        print("Telegram bot listener active. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")