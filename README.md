# SS Scraper

A small scraper for SS.com listings with Telegram notifications and district-based configuration.

## Local directory and path abstraction

The project keeps its default local data files in the project root using a simple path abstraction, so the scraper and database stay relative to the repository instead of hardcoded absolute locations.

- default config file: `districts.json`
- default database file: `ss_listings.db`
- these can still be overridden with `SS_CONFIG_PATH` and `SS_DB_PATH`

## Production setup

1. Create and activate the project virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you do not have a requirements file yet, install the runtime dependencies directly:

```bash
pip install requests beautifulsoup4
```

2. Set the Telegram bot environment variables:

```bash
export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
export TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
```

Optional: use a custom SQLite path or config file location:

```bash
export SS_DB_PATH="/home/emils/Projects/ss-scraper/ss_listings.db"
export SS_CONFIG_PATH="/home/emils/Projects/ss-scraper/districts.json"
```

3. Configure the districts to monitor:

```bash
python -c "from config import save_districts; print(save_districts(['centre', 'mezciems', 'old-town']))"
```

Or send these commands to your Telegram bot once it is running:

- `/districts`
- `/districts centre, mezciems, old-town`
- `/reset_districts`

## Run the scraper in production

Start the scraper process:

```bash
cd /home/emils/Projects/ss-scraper
source .venv/bin/activate
python main.py
```

This will:
- load the configured districts from `districts.json`
- fetch SS.com listings for each configured district
- save new listings to the SQLite database
- send Telegram notifications for new listings
- keep a Telegram polling listener active in the background when a valid token is configured

## Notes

- If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` are not set, Telegram notifications are skipped.
- The default district is `centre`.
- The scraper uses the configured district list as the target set; it does not hardcode only one district anymore.
