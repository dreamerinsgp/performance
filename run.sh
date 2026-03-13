#!/bin/bash
# Run the dashboard. Uses venv if present, else Docker.
set -e
cd "$(dirname "$0")"

run_uvicorn() {
  pip install -q -r requirements.txt
  exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
}

if [ -f venv/bin/activate ]; then
  source venv/bin/activate
  run_uvicorn
elif [ -z "$VIRTUAL_ENV" ]; then
  [ -d venv ] && rm -rf venv
  if python3 -m venv venv 2>/dev/null; then
    source venv/bin/activate
    run_uvicorn
  elif command -v docker &>/dev/null; then
    echo "venv not available (install: sudo apt install python3.12-venv)"
    echo "Running via Docker..."
    exec docker compose up --build
  else
    echo "ERROR: Need either:"
    echo "  1. sudo apt install python3.12-venv   # then ./run.sh again"
    echo "  2. Docker installed                  # docker compose up --build"
    exit 1
  fi
else
  run_uvicorn
fi
