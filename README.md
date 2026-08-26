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

## Supabase / Postgres (optional)

You can use a Supabase-hosted Postgres database instead of the default local SQLite file. Set the following environment variables:

- `DB_URL` — the Postgres connection URL. Example:

	```bash
	export DB_URL="postgresql://postgres:[YOUR-PASSWORD]@db.wgaziexghcbgvdrzgrxv.supabase.co:5432/postgres"
	```

- `DB_PASSWORD` — the database password to substitute into `DB_URL` when the placeholder `[YOUR-PASSWORD]` is present.

Behavior:
- If `DB_URL` is set, the scraper will use Postgres via SQLAlchemy.
- If `DB_URL` contains the literal substring `[YOUR-PASSWORD]`, it will be replaced with the value of `DB_PASSWORD` before connecting.
- If `DB_URL` already contains a password (no placeholder), it will be used as-is.

Install dependencies with Poetry:

```bash
poetry install
```

Or use pip to install the listed dependencies in `pyproject.toml`:

```bash
pip install SQLAlchemy psycopg2-binary
```

## Deploy to GCP Cloud Run (using Supabase Postgres)

This repository can be deployed to Cloud Run and configured to receive Telegram webhooks.

1. Build and push the image (example):

```bash
# from repo root
gcloud builds submit --tag gcr.io/$PROJECT_ID/ss-scraper
```

2. Deploy to Cloud Run (make the service public so Telegram can call webhooks):

```bash
gcloud run deploy ss-scraper --image gcr.io/$PROJECT_ID/ss-scraper \
	--region=us-central1 --allow-unauthenticated \
	--set-env-vars DB_URL="$DB_URL",TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN",TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID",TELEGRAM_WEBHOOK_SECRET="$TELEGRAM_WEBHOOK_SECRET"
```

3. Set the Telegram webhook (include the secret as query param):

```bash
export CLOUD_RUN_URL="https://SERVICE-URL"
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${CLOUD_RUN_URL}/telegram-webhook?secret=${TELEGRAM_WEBHOOK_SECRET}"
```

4. Trigger a scrape manually (optional):

```bash
curl -X POST "${CLOUD_RUN_URL}/run-scrape?secret=${TELEGRAM_WEBHOOK_SECRET}"
```

Security notes:
- Cloud Run must be publicly reachable for Telegram webhooks. Protect the webhook by requiring a secret (as shown). Store secrets in Secret Manager and inject them during deploy for extra safety.

Runtime Secret Manager (recommended)
-----------------------------------

The app can fetch secrets from Google Secret Manager at runtime. This avoids rebuilding or redeploying just to rotate secret values.

1) Install the Secret Manager client in your runtime environment (add to your deps):

```bash
pip install google-cloud-secret-manager
# or add `google-cloud-secret-manager` to your `pyproject.toml` / requirements
```

2) Grant your Cloud Run runtime service account access to the specific secrets (least privilege):

```bash
PROJECT_ID=ss-scraper-506418
SA_EMAIL=s-scraper-run-sa@${PROJECT_ID}.iam.gserviceaccount.com

# Grant access to TELEGRAM_WEBHOOK_SECRET
gcloud secrets add-iam-policy-binding TELEGRAM_WEBHOOK_SECRET \
	--project="$PROJECT_ID" \
	--member="serviceAccount:${SA_EMAIL}" \
	--role="roles/secretmanager.secretAccessor"

# Grant access to DB_URL
gcloud secrets add-iam-policy-binding DB_URL \
	--project="$PROJECT_ID" \
	--member="serviceAccount:${SA_EMAIL}" \
	--role="roles/secretmanager.secretAccessor"
```

3) How the app uses secrets

- The app will first check for an environment variable named the same as the secret (e.g. `TELEGRAM_WEBHOOK_SECRET`). If present, it will use that value (useful for local dev).
- Otherwise the app will call Secret Manager to read `projects/$PROJECT_ID/secrets/<NAME>/versions/latest` at runtime. The value is cached in-memory for efficiency.

4) When you rotate a secret, add a new secret version:

```bash
echo -n "NEW_VALUE" | gcloud secrets versions add TELEGRAM_WEBHOOK_SECRET --project="$PROJECT_ID" --data-file=-
```

No redeploy is required when secrets are read at runtime; the app will pick up the new value after the in-memory cache expires or if restarted. For immediate propagation you can still create a new Cloud Run revision.

Notes:
- Make sure your runtime service account has `roles/secretmanager.secretAccessor` for the secrets it needs.
- Avoid committing long-lived service account keys; use IAM bindings instead.


