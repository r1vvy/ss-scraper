import os
import threading
from functools import lru_cache
from flask import Flask, request, abort

from telegram import process_telegram_command, send_telegram_message
from main import run_scraper

app = Flask(__name__)

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
        return None


def get_secret(name: str) -> str | None:
    # Env var override (useful for local dev)
    env = os.getenv(name)
    if env:
        return env
    # Try Secret Manager
    return _get_secret_from_manager(name)


def _validate_secret(req):
    webhook_secret = get_secret("TELEGRAM_WEBHOOK_SECRET")
    if not webhook_secret:
        return True
    secret = req.args.get("secret") or req.headers.get("X-Telegram-Bot-Api-Secret-Token")
    return secret == webhook_secret


@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    if not _validate_secret(request):
        abort(403)

    payload = request.get_json(silent=True)
    if not payload:
        return "", 400

    # Process the update (synchronous)
    processed = process_telegram_command(payload)
    return ("", 204) if processed else ("", 200)


@app.route("/run-scrape", methods=["POST", "GET"])
def run_scrape():
    # Optional lightweight auth via secret param
    webhook_secret = get_secret("TELEGRAM_WEBHOOK_SECRET")
    if webhook_secret:
        secret = request.args.get("secret") or request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != webhook_secret:
            abort(403)

    # Run scraper in background thread to return quickly
    thread = threading.Thread(target=run_scraper, daemon=True)
    thread.start()
    return ("Scrape started", 202)


@app.route("/health", methods=["GET"])
def health():
    return ("OK", 200)


if __name__ == "__main__":
    # Local dev: run Flask dev server
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
