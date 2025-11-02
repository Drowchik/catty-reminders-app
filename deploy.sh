#!/bin/bash
set -e

APP_DIR="$(pwd)"
VENV_DIR="$APP_DIR/.venv"
echo "$APP_DIR"
echo "Deploy Start"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

pkill -f "uvicorn app.main:app" 2>/dev/null || true

nohup uvicorn app.main:app --host 0.0.0.0 --port 8181 > uvicorn.log 2>&1 &

sleep 2

echo "=== uvicorn.log ==="
tail -n 20 uvicorn.log

echo "Deploy completed"