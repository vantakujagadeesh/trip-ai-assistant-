#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add your API keys before using live integrations."
fi

echo "Starting Roam AI API at http://localhost:8000"
echo "Serve the frontend separately with: python3 -m http.server 3000 --directory public"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
