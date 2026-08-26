import html
import logging
import random
import sys
import threading
import time

import requests

from config import HEADERS, REQUEST_DELAY_RANGE, TELEGRAM_BOT_TOKEN, get_target_urls, load_districts
from db import get_total_saved_count, init_db, is_id_seen, save_listing
from scraper import fetch_page, get_total_pages, parse_listings_from_page
from telegram import format_telegram_card, run_telegram_listener, send_telegram_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ss_scraper.main")


def run_scraper(notify_chat_id=None):
    init_db()
    total_saved_before = get_total_saved_count()
    is_first_run = total_saved_before == 0
    target_urls = get_target_urls()

    if not target_urls:
        target_urls = ["https://www.ss.com/lv/real-estate/flats/riga/centre/hand_over/"]

    session = requests.Session()
    session.headers.update(HEADERS)

    total_new_listings = 0
    fetch_errors = []

    logger.info(
        "Starting scrape run (existing_db_listings=%d, is_first_run=%s, districts_count=%d)",
        total_saved_before,
        is_first_run,
        len(target_urls),
    )

    for district_index, base_url in enumerate(target_urls, start=1):
        logger.info("Fetching listings for district %d/%d: %s", district_index, len(target_urls), base_url)

        try:
            first_page = fetch_page(session, base_url)
        except requests.RequestException as err:
            logger.error("Failed to fetch district %s: %s", base_url, err)
            fetch_errors.append(f"{base_url}: {err}")
            continue

        total_pages = get_total_pages(first_page)
        logger.info("District %s: total pages identified = %d", base_url, total_pages)

        for page_number in range(1, total_pages + 1):
            page_url = base_url if page_number == 1 else f"{base_url}page{page_number}.html"
            try:
                soup = first_page if page_number == 1 else fetch_page(session, page_url)
            except requests.RequestException as err:
                logger.error("Failed to fetch page %s: %s", page_url, err)
                fetch_errors.append(f"{page_url}: {err}")
                continue

            page_data = parse_listings_from_page(soup)
            logger.info("Scraped page %d/%d (%s): found %d listings", page_number, total_pages, page_url, len(page_data))

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

    logger.info(
        "Scraping complete. Extracted %d new listings. Errors: %d",
        total_new_listings,
        len(fetch_errors),
    )
    return total_new_listings, fetch_errors


_scrape_lock = threading.Lock()


def is_scraping_running() -> bool:
    return _scrape_lock.locked()


def trigger_scrape(chat_id=None, async_run=False):
    """Executes the scraper (synchronous by default to keep Cloud Run CPU active)."""
    if not _scrape_lock.acquire(blocking=False):
        return False, "⚠️ A scrape is already in progress. Please wait for it to finish."

    districts = load_districts()
    districts_str = ", ".join(districts)

    def _execute():
        try:
            total_new, errors = run_scraper(notify_chat_id=chat_id)
            err_summary = f"\n⚠️ Encountered {len(errors)} fetch error(s) (check logs)." if errors else ""

            if total_new == 0:
                msg = f"✅ Scraping complete for <b>{html.escape(districts_str)}</b>. No new listings found.{err_summary}"
            else:
                msg = f"✅ Scraping complete for <b>{html.escape(districts_str)}</b>. Found <b>{total_new}</b> new listing(s).{err_summary}"
            return True, msg
        except Exception as exc:
            logger.exception("Error during scrape: %s", exc)
            return False, f"❌ Error during scrape: {html.escape(str(exc))}"
        finally:
            _scrape_lock.release()

    if async_run:
        def _worker():
            _, msg = _execute()
            if chat_id:
                send_telegram_message(msg, chat_id=chat_id)

        thread = threading.Thread(target=_worker, name="manual-scrape-worker", daemon=True)
        thread.start()
        return True, f"🚀 Scrape started for districts: <b>{html.escape(districts_str)}</b>"

    return _execute()


def start_background_services():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return

    listener_thread = threading.Thread(
        target=run_telegram_listener,
        name="telegram-listener",
        daemon=True,
    )
    listener_thread.start()
    logger.info("Telegram listener started in background.")


if __name__ == "__main__":
    start_background_services()
    run_scraper()
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
        logger.info("Telegram bot listener active. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")