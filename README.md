# BioScope Ingestion (Backend)

This repository handles ingestion and scraping for BioScope, focused on the core insight:

"Track pipeline strength of a company over time."

Scope (MVP):

- Crawl and ingest clinical trials, regulatory updates, and competitor signals
- Normalize records and publish events to Kafka (or local JSONL sink for dev)
- Provide data that downstream processing/analytics can build on

## Repo strategy

Separate repositories by context. This repo is ingestion-only. Other components (processing, APIs, UI, analytics) live in separate repos.

## Current Status

Implemented in this repo today:

- Scrapy-based ingestion pipeline for BioScope backend
- ClinicalTrials.gov API spider with optional company filtering
- FDA and EMA RSS spider scaffolds
- Local JSONL sink for development
- Optional Kafka publishing path for production-style deployments
- Persistent local deduplication by `identifiers.nct_id`
- Docker and GitHub Actions scaffolding
- One-command local startup via `bash start.sh`

This means the repo is now usable as a backend ingestion foundation, but it is still focused on source collection and normalization rather than advanced intelligence or analytics.

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
- TARGET_COMPANY: optional company filter for ClinicalTrials scraping
- CLINICALTRIALS_QUERY: default query term (e.g., diabetes)
- FDA_RSS_URL, EMA_RSS_URL: RSS feed URLs

To scrape only one company, set `TARGET_COMPANY` in `.env`. The ClinicalTrials spider will use that value as the query term and then filter results so only matching trials are emitted.

To prevent repeating the same trial across runs, the local sink now skips records with the same `identifiers.nct_id` and stores seen IDs in `out/ingestion.seen.json` by default.

## Upcoming Features

The next features I would implement in this repo are:

1. Source-level incremental crawling

- Track `last_seen` per source and use `ETag` / `If-Modified-Since` where supported.
- Reduce redundant requests and speed up repeat runs.

2. Better normalization and canonicalization

- Standardize company, drug, condition, and trial identifiers.
- Collapse similar sponsor names into one canonical company record.

3. Stronger deduplication rules

- Deduplicate by `NCT ID`, title, sponsor, and date window when IDs are missing.
- Prevent repeated alerts from near-duplicate updates.

4. Schema validation

- Add Pydantic models for raw and normalized records.
- Fail fast when a source changes shape.

5. Structured logging and observability

- Add JSON logs, crawl metrics, and error traces.
- Make it easier to debug source failures.

6. Company-focused filtering

- Add source-specific rules so each crawl can be constrained to one company or competitor set.
- Make the output directly useful for pipeline-strength tracking.

7. Test coverage

- Add unit tests for parsing, filtering, and dedup logic.
- Add integration tests for spider output and sink behavior.
