# BioScope Ingestion (Backend)

This repository handles ingestion and scraping for BioScope, focused on the core insight:

"Track pipeline strength of a company over time."

Scope (MVP):

- Crawl and ingest clinical trials, regulatory updates, and competitor signals
- Normalize records and publish events to Kafka (or local JSONL sink for dev)
- Provide data that downstream processing/analytics can build on

## Repo strategy

Separate repositories by context. This repo is ingestion-only. Other components (processing, APIs, UI, analytics) live in separate repos.

## Project Checklist

Completed:

- [x] Scrapy-based ingestion pipeline for BioScope backend
- [x] ClinicalTrials.gov API spider with optional company filtering (`TARGET_COMPANY`)
- [x] FDA openFDA JSON spider for regulatory updates
- [x] EMA RSS spider wired to active feed URL
- [x] Incremental crawling support for FDA JSON + EMA RSS (`ETag`, `If-Modified-Since`, `last_seen`)
- [x] Persistent source-state store (SQLite)
- [x] Local JSONL sink for development
- [x] Optional Kafka publishing path for production-style deployments
- [x] Persistent local deduplication by `identifiers.nct_id`
- [x] Automated startup script with `--all`, `--spider`, `--reset-state`, `--skip-install`
- [x] Docker and GitHub Actions scaffolding

In progress / upcoming:

- [ ] ClinicalTrials incremental crawling with watermarks/cursor strategy
- [ ] Canonicalization rules for company and drug names
- [ ] Cross-source deduplication beyond NCT ID
- [ ] Pydantic schema validation for normalized records
- [ ] Structured JSON logging + ingestion metrics
- [ ] Better company-focused filtering for FDA/EMA sources
- [ ] Unit tests for parsers/filters/dedup logic
- [ ] Integration tests for spider outputs and sink behavior

## Minimal, expandable structure

```
.
├── .github/workflows/ci.yml
├── dags/                      # Airflow DAGs (optional runtime)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── scrapy.cfg
├── src/
│   ├── bioscope_ingestion/
│   │   ├── __init__.py
│   │   ├── items.py
│   │   ├── pipelines.py
│   │   ├── settings.py
│   │   └── spiders/
│   │       ├── __init__.py
│   │       ├── clinicaltrials_api_spider.py
│   │       ├── ema_rss_spider.py
│   │       ├── fda_openfda_spider.py
│   │       └── fda_rss_spider.py
│   └── common/
│       ├── __init__.py
│       ├── config.py
│       └── kafka.py
└── .env.example
```

## Quickstart

One-command local start:

```bash
bash start.sh
```

Automated script options:

```bash
# Run default spider (clinicaltrials_api)
bash start.sh

# Run all spiders sequentially
bash start.sh --all

# Run one specific spider
bash start.sh --spider ema_rss

# Reset local output/state before running
bash start.sh --all --reset-state

# Skip dependency installation check
bash start.sh --skip-install

# Show help
bash start.sh --help
```

### start.sh options reference

- `--spider <name>`: run one specific spider (default: `clinicaltrials_api`)
- `--all`: run `clinicaltrials_api`, `fda_openfda`, and `ema_rss` sequentially
- `--reset-state`: remove local output and incremental state files before crawling
- `--skip-install`: skip requirements installation/hash check
- `--help`: print script usage and options

1. Create a virtualenv and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy env vars:
   ```bash
   cp .env.example .env
   ```
3. Run a spider:
   ```bash
   PYTHONPATH=src scrapy crawl clinicaltrials_api
   ```

The script uses the local JSONL sink by default. To route output to Kafka, set `KAFKA_ENABLED=true` in `.env` and provide `KAFKA_BROKERS`.

## Key environment variables

- KAFKA_ENABLED: true|false
- KAFKA_BROKERS: comma-separated host:port
- KAFKA_TOPIC: topic name (default: bioscope.ingestion.raw)
- LOCAL_SINK_PATH: JSONL path when Kafka is disabled
- LOCAL_DEDUP_KEY: field path used to deduplicate local output, default `identifiers.nct_id`
- LOCAL_DEDUP_STATE_PATH: sidecar file that stores seen dedup keys
- INCREMENTAL_ENABLED: turn source-level incremental crawling on/off
- STATE_STORE_PATH: SQLite state file used for source watermarks and HTTP cache headers
- TARGET_COMPANY: optional company filter for ClinicalTrials scraping
- CLINICALTRIALS_QUERY: default query term (e.g., diabetes)
- CLINICALTRIALS_SORT: ClinicalTrials API sort order, default `LastUpdatePostDate:desc`
- CLINICALTRIALS_PAGINATION_CUTOFF_ENABLED: stop paging when incremental watermark cutoff is reached (default: true)
- FDA_JSON_URL: openFDA JSON endpoint (example: `https://api.fda.gov/drug/enforcement.json?limit=100`)
- EMA_RSS_URL: EMA RSS feed URL (recommended: `https://www.ema.europa.eu/en/news.xml`)
- FDA_RSS_URL: optional legacy RSS URL if you have a valid FDA feed endpoint

To scrape only one company, set `TARGET_COMPANY` in `.env`. The ClinicalTrials spider will use that value as the query term and then filter results so only matching trials are emitted.

To prevent repeating the same trial across runs, the local sink now skips records with the same `identifiers.nct_id` and stores seen IDs in `out/ingestion.seen.json` by default.

For FDA JSON and EMA RSS, incremental mode stores `ETag`, `Last-Modified`, and `last_seen` timestamps in `STATE_STORE_PATH` and reuses them on subsequent runs.

For ClinicalTrials API, incremental mode stores a `last_seen` watermark in `STATE_STORE_PATH`, filters older/equal records, and follows `nextPageToken` until cutoff when sorted by `LastUpdatePostDate:desc`.

## Active Source Defaults

- FDA JSON (openFDA): `https://api.fda.gov/drug/enforcement.json?limit=100`
- EMA RSS: `https://www.ema.europa.eu/en/news.xml`

These defaults are active in `.env.example` and are recommended for reliable ingestion.

## Milestone Tracker

Milestone 1: Foundation + Incremental RSS/JSON

- [x] Source-state storage in `src/common/state_store.py`
- [x] Conditional fetch (`If-None-Match`, `If-Modified-Since`) for FDA JSON + EMA RSS
- [x] `last_seen` watermark filtering for FDA JSON + EMA RSS
- [x] Config support in `.env` / `.env.example`

Milestone 2: ClinicalTrials Incremental + Canonicalization

- [x] Incremental strategy for ClinicalTrials API (timestamp + cursor pagination)
- [ ] Canonical company normalization map
- [ ] Improved dedup for records without stable IDs

Milestone 3: Reliability + Quality

- [ ] Pydantic schema validation
- [ ] Structured logging and metrics
- [ ] Unit and integration tests
