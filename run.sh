#!/usr/bin/env bash
# Run the API using the project virtualenv (avoids "No module named sqlalchemy").
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

if [[ ! -f .env ]]; then
  echo "Create backend/.env from .env.example before starting."
  exit 1
fi

exec .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
