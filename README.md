# BioScope Ingestion (Backend)

BioScope Ingestion is the data-collection layer for a pharma intelligence platform.

Core objective:

Track pipeline and regulatory momentum of target pharma companies over time by continuously collecting and normalizing source data.

What this project currently does:

- Crawls ClinicalTrials.gov, FDA openFDA, and EMA RSS sources.
- Supports incremental ingestion using source watermarks and conditional HTTP requests.
- Normalizes output records into a common ingestion envelope.
- Publishes events to Kafka (production path) or JSONL (local development path).
- Applies local deduplication using stable IDs with fallback fingerprint dedup when IDs are missing.
- Uses conservative AutoThrottle and retry defaults so crawls stay polite on shared/public sources.
- Persists source crawl state in SQLite so repeated runs are efficient and idempotent.

What this repository does not include yet:

- Downstream NLP/enrichment services.
- Search/indexing APIs.
- Product UI/dashboard.
- Production observability and SLO tooling.

## Repo strategy

Separate repositories by context. This repo is ingestion-only. Other components (processing, APIs, UI, analytics) live in separate repos.

## Current Stage

Stage: Ingestion MVP complete, now entering reliability and production-hardening phase.

- Milestone 1: complete.
- Milestone 2: complete.
- Milestone 3: started (structured metrics/logging + backfill mode in start script).

This means source ingestion correctness is in good shape for development and pilot usage, while production readiness still needs validation, observability, and test coverage work.

## Project Checklist

Completed:

- [x] Scrapy-based ingestion pipeline for BioScope backend
- [x] ClinicalTrials.gov API spider with optional company filtering (`TARGET_COMPANY`)
- [x] FDA openFDA JSON spider for regulatory updates
- [x] EMA RSS spider wired to active feed URL
- [x] Incremental crawling support for FDA JSON + EMA RSS (`ETag`, `If-Modified-Since`, `last_seen`)
- [x] ClinicalTrials incremental crawling with watermark + cursor pagination cutoff
- [x] 304 response handling wired through spider runtime (not dropped by middleware)
- [x] Persistent source-state store (SQLite)
- [x] Local JSONL sink for development
- [x] Optional Kafka publishing path for production-style deployments
- [x] Persistent local deduplication by `identifiers.nct_id`
- [x] Fallback fingerprint dedup for records without stable IDs (`LOCAL_DEDUP_FALLBACK_ENABLED`)
- [x] Company/drug canonicalization helpers with optional alias maps from env
- [x] Structured per-run metrics written to JSONL (`METRICS_OUTPUT_PATH`)
- [x] Structured item-ingestion logs (JSON log lines)
- [x] Backfill execution mode in startup script (`--backfill`)
- [x] Pydantic schema validation in ingestion pipeline (configurable mode)
- [x] AutoThrottle and retry defaults for polite crawling
- [x] Automated startup script with `--all`, `--spider`, `--reset-state`, `--skip-install`
- [x] Docker and GitHub Actions scaffolding

Remaining / upcoming:

- [x] Basic unit tests for schema + normalization utilities
- [ ] Expand unit coverage for spiders/pipeline edge cases
- [ ] Prometheus/monitoring integration for ingestion metrics
- [ ] Better company-focused filtering for FDA/EMA sources
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
│       ├── kafka.py
│       ├── normalization.py
│       └── state_store.py
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

# Backfill run (disables incremental cutoffs for this execution)
bash start.sh --all --backfill

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
- `--backfill`: run current crawl without incremental cutoffs (`INCREMENTAL_ENABLED=false` for the process)
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

4. Run unit tests:
   ```bash
   pytest -q
   ```

The script uses the local JSONL sink by default. To route output to Kafka, set `KAFKA_ENABLED=true` in `.env` and provide `KAFKA_BROKERS`.

## Key environment variables

- KAFKA_ENABLED: true|false
- KAFKA_BROKERS: comma-separated host:port
- KAFKA_TOPIC: topic name (default: bioscope.ingestion.raw)
- LOCAL_SINK_PATH: JSONL path when Kafka is disabled
- LOCAL_DEDUP_KEY: field path used to deduplicate local output, default `identifiers.nct_id`
- LOCAL_DEDUP_FALLBACK_ENABLED: when `LOCAL_DEDUP_KEY` is missing, dedup using stable fingerprint fallback (default: true)
- LOCAL_DEDUP_STATE_PATH: sidecar file that stores seen dedup keys
- INCREMENTAL_ENABLED: turn source-level incremental crawling on/off
- STATE_STORE_PATH: SQLite state file used for source watermarks and HTTP cache headers
- AUTOTHROTTLE_ENABLED: enable Scrapy AutoThrottle (default: true)
- AUTOTHROTTLE_START_DELAY: initial delay in seconds for AutoThrottle (default: 1)
- AUTOTHROTTLE_MAX_DELAY: max delay in seconds for AutoThrottle (default: 10)
- AUTOTHROTTLE_TARGET_CONCURRENCY: target concurrent requests per server (default: 1)
- DOWNLOAD_DELAY: fixed download delay used alongside AutoThrottle (default: 1)
- CONCURRENT_REQUESTS: total concurrent requests across the crawler (default: 8)
- CONCURRENT_REQUESTS_PER_DOMAIN: concurrent requests per domain (default: 2)

### Source-Specific Throttle Settings

Each data source has customized throttle settings tuned to its API/feed characteristics. Set these in `.env` to override global throttle defaults for each source:

**ClinicalTrials.gov** (large paginated API):

- `CLINICALTRIALS_DOWNLOAD_DELAY`: delay in seconds between requests (default: 2)
- `CLINICALTRIALS_CONCURRENT_REQUESTS_PER_DOMAIN`: concurrent requests (default: 1)

**FDA OpenFDA API** (government API):

- `FDA_DOWNLOAD_DELAY`: delay in seconds (default: 1)
- `FDA_CONCURRENT_REQUESTS_PER_DOMAIN`: concurrent requests (default: 2)

**FDA RSS** (RSS feed):

- `FDA_RSS_DOWNLOAD_DELAY`: delay in seconds (default: 1)
- `FDA_RSS_CONCURRENT_REQUESTS_PER_DOMAIN`: concurrent requests (default: 2)

**EMA RSS** (typically single request per run):

- `EMA_DOWNLOAD_DELAY`: delay in seconds (default: 0)
- `EMA_CONCURRENT_REQUESTS_PER_DOMAIN`: concurrent requests (default: 1)

These settings are applied per-spider in their `custom_settings` and override global throttle defaults when the spider runs.

- RETRY_ENABLED: enable retries for transient HTTP failures (default: true)
- RETRY_TIMES: number of retry attempts for transient HTTP failures (default: 3)
- METRICS_ENABLED: emit per-spider run metrics to JSONL file (default: true)
- METRICS_OUTPUT_PATH: JSONL path for ingestion run metrics
- VALIDATION_ENABLED: enable or disable Pydantic validation in the pipeline (default: true)
- VALIDATION_MODE: behavior on validation error: `drop`, `strict`, or `warn` (default: `drop`)
- STRUCTURED_LOGS_ENABLED: emit JSON structured logs for ingested items (default: true)
- STRUCTURED_LOG_EVERY_N_ITEMS: emit one structured item log every N processed items (default: 100)
- TARGET_COMPANY: optional company filter for ClinicalTrials scraping
- COMPANY_CANONICAL_MAP_JSON: optional JSON object mapping company aliases to canonical names
- DRUG_CANONICAL_MAP_JSON: optional JSON object mapping drug aliases to canonical names
- CLINICALTRIALS_QUERY: default query term (e.g., diabetes)
- CLINICALTRIALS_PAGE_SIZE: number of records requested per ClinicalTrials API page (default: 50)
- CLINICALTRIALS_SORT: ClinicalTrials API sort order, default `LastUpdatePostDate:desc`
- CLINICALTRIALS_PAGINATION_CUTOFF_ENABLED: stop paging when incremental watermark cutoff is reached (default: true)
- FDA_JSON_URL: openFDA JSON endpoint (example: `https://api.fda.gov/drug/enforcement.json?limit=100`)
- EMA_RSS_URL: EMA RSS feed URL (recommended: `https://www.ema.europa.eu/en/news.xml`)
- FDA_RSS_URL: optional legacy RSS URL if you have a valid FDA feed endpoint

To scrape only one company, set `TARGET_COMPANY` in `.env`. The ClinicalTrials spider will use that value as the query term and then filter results so only matching trials are emitted.

To prevent repeating the same trial across runs, the local sink now skips records with the same `identifiers.nct_id` and stores seen IDs in `out/ingestion.seen.json` by default.

For FDA JSON and EMA RSS, incremental mode stores `ETag`, `Last-Modified`, and `last_seen` timestamps in `STATE_STORE_PATH` and reuses them on subsequent runs.

For ClinicalTrials API, incremental mode stores a `last_seen` watermark in `STATE_STORE_PATH`, filters older/equal records, and follows `nextPageToken` until cutoff when sorted by `LastUpdatePostDate:desc`.

ClinicalTrials normalization now emits `normalized.canonical_lead_sponsor` and `normalized.canonical_drugs` to support downstream entity joins.

Local JSONL dedup now supports a fingerprint fallback when the configured dedup key is missing, improving deduplication across RSS/JSON records that do not carry stable IDs.

Pipeline metrics are written as JSON lines to `METRICS_OUTPUT_PATH` at spider close with counts for requests, responses, 200/304 statuses, items, validation pass/fail counters, elapsed time, and finish reason.

Pipeline schema validation uses Pydantic and validates each normalized ingestion record before sink write.

- `VALIDATION_MODE=drop`: invalid records are logged and skipped
- `VALIDATION_MODE=strict`: invalid records fail the spider run
- `VALIDATION_MODE=warn`: invalid records are logged but still forwarded to sink

`.env.example` includes sample alias-map JSON values (Pfizer and Novo Nordisk variants) to demonstrate canonicalization format.

## VS Code Terminal Note (.env)

If VS Code shows: "An environment file is configured but terminal environment injection is disabled", enable `python.terminal.useEnvFile=true` to auto-inject `.env` into Python terminals.

`start.sh` already sources `.env` directly, so script-based runs use updated environment values regardless of that editor setting.

## Active Source Defaults

- FDA JSON (openFDA): `https://api.fda.gov/drug/enforcement.json?limit=100`
- EMA RSS: `https://www.ema.europa.eu/en/news.xml`

These defaults are active in `.env.example` and are recommended for reliable ingestion.

## Latest Validation (2026-04-06)

Validation commands executed:

- `python -m compileall src`
- `bash ./start.sh --all`

Observed results:

- All changed Python modules compiled successfully.
- ClinicalTrials spider executed with incremental cutoff log and completed cleanly.
- FDA openFDA and EMA RSS spiders received `304 Not Modified` and handled them correctly inside spider parse flow.
- No runtime crashes during end-to-end `--all` execution.

Warning status:

- Previous Scrapy deprecations were resolved by upgrading to Scrapy `2.13.0` and migrating spiders from `start_requests()` to `start()`.

## Milestone Tracker

Milestone 1: Foundation + Incremental RSS/JSON

- [x] Source-state storage in `src/common/state_store.py`
- [x] Conditional fetch (`If-None-Match`, `If-Modified-Since`) for FDA JSON + EMA RSS
- [x] `last_seen` watermark filtering for FDA JSON + EMA RSS
- [x] Config support in `.env` / `.env.example`

Milestone 2: ClinicalTrials Incremental + Canonicalization

- [x] Incremental strategy for ClinicalTrials API (timestamp + cursor pagination + cutoff)
- [x] Canonical company/drug normalization support (with optional alias maps)
- [x] Improved dedup for records without stable IDs

Milestone 3: Reliability + Quality

- [x] Pydantic schema validation
- [x] Structured logging and file-based ingestion metrics
- [x] Basic unit test scaffold (schema + normalization)
- [ ] Prometheus/monitoring integration
- [ ] Broader unit and integration tests

## Summary

This project is currently a functional ingestion backbone for BioScope with incremental crawling, stateful source tracking, canonicalization support, and local/prod sink flexibility. It is ready for continued integration into downstream analytics services, but not yet production-hardened until Milestone 3 items are completed.

<img width="537" height="612" alt="image" src="https://github.com/user-attachments/assets/d457c8c4-8513-4c3e-8d6a-9d460f0d75ee" />
