#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

PORT=3000   # <-- change this per app

if lsof -i :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo ""
  echo "  WARNING: Port $PORT is already in use."
  echo ""
  exit 1
fi

echo "==> Installing backend dependencies..."
cd "$ROOT/backend" && npm install --silent

echo "==> Installing frontend dependencies..."
cd "$ROOT/frontend" && npm install --silent

echo "==> Building frontend..."
cd "$ROOT/frontend" && npm run build

echo ""
echo "==> Starting APP_NAME at http://localhost:$PORT"
echo "    Press Ctrl+C to stop."
echo ""

cd "$ROOT/backend" && node server.js
