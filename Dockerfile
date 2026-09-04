FROM python:3.10-slim

WORKDIR /app

# Install system deps required for psycopg2 if wheel is not available
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/

RUN python -m pip install --upgrade pip
RUN pip install SQLAlchemy psycopg2-binary requests beautifulsoup4 flask gunicorn tenacity
RUN pip install SQLAlchemy psycopg2-binary requests beautifulsoup4 flask gunicorn tenacity gspread google-auth google-api-python-client

COPY . /app

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "--log-level", "info"]
