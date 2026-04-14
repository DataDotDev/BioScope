import os
from datetime import datetime, timezone

from dateutil import parser as date_parser
import scrapy

from bioscope_ingestion.items import IngestionRecord
from common.config import env_bool, env_str
from common.state_store import SourceStateStore


class FdaRssSpider(scrapy.Spider):
    name = "fda_rss"
    handle_httpstatus_list = [304]

    async def start(self):
        feed_url = os.getenv("FDA_RSS_URL", "").strip()
        if not feed_url:
            self.logger.info("FDA_RSS_URL is empty; skipping fda_rss spider")
            return

        incremental_enabled = env_bool("INCREMENTAL_ENABLED", True)
        state_store_path = env_str("STATE_STORE_PATH", "./out/source_state.sqlite") or "./out/source_state.sqlite"
        source_key = f"fda_rss:{feed_url}"
        state_store = SourceStateStore(state_store_path)
        state = state_store.get_state(source_key)

        headers = {}
        if incremental_enabled:
            if state.get("etag"):
                headers["If-None-Match"] = state["etag"]
            if state.get("last_modified"):
                headers["If-Modified-Since"] = state["last_modified"]

        yield scrapy.Request(
            url=feed_url,
            callback=self.parse,
            headers=headers,
            cb_kwargs={
                "source_key": source_key,
                "state_store": state_store,
                "previous_state": state,
                "incremental_enabled": incremental_enabled,
            },
        )

    def parse(self, response, source_key, state_store, previous_state, incremental_enabled):
        if response.status == 304:
            self.logger.info("No FDA updates (304 Not Modified)")
            return

        etag = self._decode_header(response.headers.get("ETag"))
        last_modified = self._decode_header(response.headers.get("Last-Modified"))
        previous_last_seen = previous_state.get("last_seen_ts")
        max_seen = previous_last_seen

        for node in response.xpath("//item"):
            title = node.xpath("title/text()").get()
            link = node.xpath("link/text()").get()
            pub_date = node.xpath("pubDate/text()").get()
            observed_at = self._parse_date(pub_date)

            if incremental_enabled and previous_last_seen and observed_at <= previous_last_seen:
                continue

            max_seen = self._max_ts(max_seen, observed_at)

            yield IngestionRecord(
                source="fda",
                record_type="regulatory_update",
                observed_at=observed_at,
                raw={"title": title, "link": link, "pubDate": pub_date},
                normalized={"title": title, "link": link},
                identifiers={"link": link},
            )

        state_store.upsert_state(
            source_key=source_key,
            etag=etag,
            last_modified=last_modified,
            last_seen_ts=max_seen,
        )

    @staticmethod
    def _parse_date(value: str | None) -> str:
        if not value:
            return datetime.now(timezone.utc).isoformat()
        try:
            return date_parser.parse(value).astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
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
