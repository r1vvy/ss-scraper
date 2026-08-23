import os
import threading
from flask import Flask, request, abort

from telegram import process_telegram_command, send_telegram_message
from main import run_scraper

app = Flask(__name__)

# Secret to validate webhook requests (passed as query param `?secret=`)
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")


def _validate_secret(req):
    if not WEBHOOK_SECRET:
        return True
    secret = req.args.get("secret")
    return secret == WEBHOOK_SECRET


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
    if WEBHOOK_SECRET:
        secret = request.args.get("secret")
        if secret != WEBHOOK_SECRET:
            abort(403)

    # Run scraper in background thread to return quickly
    thread = threading.Thread(target=run_scraper, daemon=True)
    thread.start()
    return ("Scrape started", 202)


if __name__ == "__main__":
    # Local dev: run Flask dev server
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
