#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/5] Checking environment files"

if [[ ! -f "$ROOT_DIR/.env" && -f "$ROOT_DIR/.env.example" ]]; then
  echo "Creating .env from .env.example"
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

echo "[2/5] Ensuring virtual environment exists"
if [[ ! -d "$ROOT_DIR/.venv" ]]; then
  echo "Creating .venv"
  python3 -m venv "$ROOT_DIR/.venv"
fi

echo "[3/5] Activating virtual environment"
source "$ROOT_DIR/.venv/bin/activate"

echo "[4/5] Checking Python dependencies"
if [[ ! -f "$ROOT_DIR/.venv/.requirements-installed" ]]; then
  echo "Installing requirements"
  pip install -r "$ROOT_DIR/requirements.txt"
  touch "$ROOT_DIR/.venv/.requirements-installed"
else
  echo "Dependencies already installed"
fi

echo "[5/5] Starting Scrapy spider: clinicaltrials_api"
export PYTHONPATH="$ROOT_DIR/src"
cd "$ROOT_DIR"
scrapy crawl clinicaltrials_api