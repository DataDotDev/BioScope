#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SPIDER="clinicaltrials_api"

show_help() {
  cat <<'EOF'
Usage: bash start.sh [options]

Options:
  --spider <name>      Run a single spider (default: clinicaltrials_api)
  --all                Run all spiders sequentially
  --reset-state        Remove local dedup and incremental state files before run
  --skip-install       Skip dependency installation check
  --help               Show this help message

Examples:
  bash start.sh
  bash start.sh --spider clinicaltrials_api
  bash start.sh --all
  bash start.sh --all --reset-state
EOF
}

RUN_ALL=false
RESET_STATE=false
SKIP_INSTALL=false
SPIDER_NAME="$DEFAULT_SPIDER"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --spider)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --spider"
        exit 1
      fi
      SPIDER_NAME="$2"
      shift 2
      ;;
    --all)
      RUN_ALL=true
      shift
      ;;
    --reset-state)
      RESET_STATE=true
      shift
      ;;
    --skip-install)
      SKIP_INSTALL=true
      shift
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

echo "[1/6] Checking environment files"

if [[ ! -f "$ROOT_DIR/.env" && -f "$ROOT_DIR/.env.example" ]]; then
  echo "Creating .env from .env.example"
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

echo "[2/6] Ensuring virtual environment exists"
if [[ ! -d "$ROOT_DIR/.venv" ]]; then
  echo "Creating .venv"
  python3 -m venv "$ROOT_DIR/.venv"
fi

echo "[3/6] Activating virtual environment"
source "$ROOT_DIR/.venv/bin/activate"

echo "[4/6] Checking Python dependencies"
REQ_MARKER="$ROOT_DIR/.venv/.requirements.sha256"
REQ_HASH="$(shasum -a 256 "$ROOT_DIR/requirements.txt" | awk '{print $1}')"

if [[ "$SKIP_INSTALL" == "true" ]]; then
  echo "Skipping dependency installation check"
else
  if [[ ! -f "$REQ_MARKER" ]] || [[ "$(cat "$REQ_MARKER")" != "$REQ_HASH" ]]; then
    echo "Installing requirements"
    pip install -r "$ROOT_DIR/requirements.txt"
    echo "$REQ_HASH" > "$REQ_MARKER"
  else
    echo "Dependencies already up to date"
  fi
fi

echo "[5/6] Preparing runtime state"
set -a
source "$ROOT_DIR/.env"
set +a

if [[ "$RESET_STATE" == "true" ]]; then
  echo "Resetting local sink and incremental state files"
  rm -f "$ROOT_DIR/out/ingestion.jsonl"
  rm -f "$ROOT_DIR/out/ingestion.seen.json"
  rm -f "$ROOT_DIR/out/source_state.sqlite"
fi

echo "[6/6] Starting crawler run"
export PYTHONPATH="$ROOT_DIR/src"
cd "$ROOT_DIR"

if [[ "$RUN_ALL" == "true" ]]; then
  SPIDERS=("clinicaltrials_api" "fda_openfda" "ema_rss")
else
  SPIDERS=("$SPIDER_NAME")
fi

for spider in "${SPIDERS[@]}"; do
  echo "Running spider: $spider"
  scrapy crawl "$spider"
done

echo "Run completed"