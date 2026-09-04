import os
import sys
import threading
from functools import lru_cache
import logging
from flask import Flask, request, abort

from telegram import flush_pending_notifications, process_telegram_command, send_telegram_message
from main import run_scraper, trigger_scrape


# Configure console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ss_scraper.app")

app = Flask(__name__)

try:
    from db import init_db
    init_db()
except Exception as exc:
    logger.critical("Fatal error: Database initialization failed on app startup: %s", exc)
    sys.exit(1)


try:
    from google.cloud import secretmanager

except Exception:
    secretmanager = None


@lru_cache(maxsize=32)
def _get_secret_from_manager(name: str) -> str | None:
    if not secretmanager:
        return None
    project_id = (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("PROJECT_ID")
        or os.getenv("GCP_PROJECT")
    )
    if not project_id:
        return None
    client = secretmanager.SecretManagerServiceClient()
    name_path = f"projects/{project_id}/secrets/{name}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": name_path})
        return response.payload.data.decode("utf-8")
    except Exception:
        logger.exception("failed to access secret %s from Secret Manager", name)
        return None


def get_secret(name: str) -> str | None:
    # Env var override (useful for local dev)
    env = os.getenv(name)
    if env:
        logger.debug("secret %s loaded from env", name)
        return env
    # Try Secret Manager
    val = _get_secret_from_manager(name)
    if val is not None:
        logger.debug("secret %s loaded from Secret Manager (cached)", name)
    else:
        logger.debug("secret %s not found in env or Secret Manager", name)
    return val


def _validate_secret(req):
    webhook_secret = get_secret("TELEGRAM_WEBHOOK_SECRET")
    if not webhook_secret:
        return True
    secret = req.args.get("secret") or req.headers.get("X-Telegram-Bot-Api-Secret-Token")
    valid = secret == webhook_secret
    if not valid:
        logger.warning("webhook secret validation failed (present=%s)", bool(secret))
    return valid


@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    logger.info("incoming webhook request from %s %s", request.remote_addr, request.path)
    if not _validate_secret(request):
        logger.warning("unauthorized webhook request")
        abort(403)

    raw = request.get_data(as_text=True)
    logger.debug("raw webhook body: %s", raw)

    payload = request.get_json(silent=True)
    logger.debug("parsed webhook payload: %s", payload)
    if payload is None:
        logger.warning("webhook received invalid or empty JSON payload")
        return "", 400

    # Process the update (synchronous)
    processed = process_telegram_command(payload)
    logger.info("processed webhook: processed=%s", bool(processed))
    return ("", 204) if processed else ("", 200)

@app.route("/run-scrape", methods=["POST", "GET"])

def run_scrape():
    # Optional lightweight auth via secret param
    webhook_secret = get_secret("TELEGRAM_WEBHOOK_SECRET")
    if webhook_secret:
        secret = request.args.get("secret") or request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != webhook_secret:
            abort(403)

    chat_id = request.args.get("chat_id")
    logger.info("run-scrape requested by %s (chat_id=%s)", request.remote_addr, chat_id)
    success, msg = trigger_scrape(chat_id=chat_id)
    status_code = 200 if success else 409
    logger.info("run-scrape finished: %s", msg)
    return (msg, status_code)


@app.route("/flush-notifications", methods=["POST", "GET"])
def flush_notifications():
    webhook_secret = get_secret("TELEGRAM_WEBHOOK_SECRET")
    if webhook_secret:
        secret = request.args.get("secret") or request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != webhook_secret:
            abort(403)

    chat_id = request.args.get("chat_id")
    logger.info("flush-notifications requested by %s (chat_id=%s)", request.remote_addr, chat_id)
    flushed = flush_pending_notifications(chat_id=chat_id)
    msg = f"Flushed {flushed} pending notification(s)."
    logger.info("flush-notifications finished: %s", msg)
    return (msg, 200)


@app.route("/sync-sheets", methods=["POST", "GET"])
def sync_sheets():
    webhook_secret = get_secret("TELEGRAM_WEBHOOK_SECRET")
    if webhook_secret:
        secret = request.args.get("secret") or request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != webhook_secret:
            abort(403)

    from sheets import sync_db_listings_to_sheets

    synced, total = sync_db_listings_to_sheets()
    msg = f"Synced {synced}/{total} listing(s) from database to Google Sheets."
    logger.info("sync-sheets finished: %s", msg)
    return (msg, 200)


@app.route("/health", methods=["GET"])
def health():
    logger.debug("health check")
    return ("OK", 200)



if __name__ == "__main__":
    # Local dev: run Flask dev server
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
