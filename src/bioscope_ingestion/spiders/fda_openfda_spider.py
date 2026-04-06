from datetime import datetime, timezone

import scrapy

from bioscope_ingestion.items import IngestionRecord
from common.config import env_bool, env_str
from common.state_store import SourceStateStore


class FdaOpenFdaSpider(scrapy.Spider):
    name = "fda_openfda"
    allowed_domains = ["api.fda.gov"]
    handle_httpstatus_list = [304]
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        endpoint = env_str(
            "FDA_JSON_URL",
            "https://api.fda.gov/drug/enforcement.json?limit=100",
        ) or "https://api.fda.gov/drug/enforcement.json?limit=100"
        incremental_enabled = env_bool("INCREMENTAL_ENABLED", True)
        state_store_path = (
            env_str("STATE_STORE_PATH", "./out/source_state.sqlite")
            or "./out/source_state.sqlite"
        )
        source_key = f"fda_openfda:{endpoint}"
        state_store = SourceStateStore(state_store_path)
        state = state_store.get_state(source_key)

        headers = {}
        if incremental_enabled:
            if state.get("etag"):
                headers["If-None-Match"] = state["etag"]
            if state.get("last_modified"):
                headers["If-Modified-Since"] = state["last_modified"]

        yield scrapy.Request(
            url=endpoint,
            callback=self.parse,
            headers=headers,
            cb_kwargs={
                "source_key": source_key,
                "state_store": state_store,
                "previous_state": state,
                "incremental_enabled": incremental_enabled,
            },
        )

    def parse(
        self,
        response,
        source_key,
        state_store,
        previous_state,
        incremental_enabled,
    ):
        if response.status == 304:
            self.logger.info("No FDA openFDA updates (304 Not Modified)")
            return

        payload = response.json()
        results = payload.get("results", [])

        etag = self._decode_header(response.headers.get("ETag"))
        last_modified = self._decode_header(response.headers.get("Last-Modified"))
        previous_last_seen = previous_state.get("last_seen_ts")
        max_seen = previous_last_seen

        for result in results:
            observed_at = self._parse_fda_date(
                result.get("report_date") or result.get("recall_initiation_date")
            )

            if incremental_enabled and previous_last_seen and observed_at <= previous_last_seen:
                continue

            max_seen = self._max_ts(max_seen, observed_at)

            event_id = (
                result.get("event_id")
                or result.get("recall_number")
                or result.get("safetyreportid")
                or result.get("application_number")
            )

            yield IngestionRecord(
                source="fda_openfda",
                record_type="regulatory_update",
                observed_at=observed_at,
                raw=result,
                normalized={
                    "title": result.get("product_description")
                    or result.get("reason_for_recall")
                    or result.get("openfda", {}).get("brand_name", [None])[0],
                    "status": result.get("status"),
                    "classification": result.get("classification"),
                    "report_date": result.get("report_date"),
                },
                identifiers={
                    "event_id": event_id,
                    "recall_number": result.get("recall_number"),
                },
            )

        state_store.upsert_state(
            source_key=source_key,
            etag=etag,
            last_modified=last_modified,
            last_seen_ts=max_seen,
        )

    @staticmethod
    def _parse_fda_date(value: str | None) -> str:
        if not value:
            return datetime.now(timezone.utc).isoformat()

        try:
            if len(value) == 8 and value.isdigit():
                dt = datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
                return dt.isoformat()
        except ValueError:
            pass

        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _decode_header(value: bytes | None) -> str | None:
        if not value:
            return None
        return value.decode("utf-8")

    @staticmethod
    def _max_ts(current: str | None, candidate: str | None) -> str | None:
        if not candidate:
            return current
        if not current:
            return candidate
        return candidate if candidate > current else current