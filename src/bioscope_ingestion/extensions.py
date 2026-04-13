from datetime import datetime, timezone
import json
import logging
from pathlib import Path

from scrapy import signals

from common.config import env_bool, env_str


class IngestionMetricsExtension:
    def __init__(self, enabled: bool, output_path: str):
        self.enabled = enabled
        self.output_path = Path(output_path)
        self.logger = logging.getLogger(self.__class__.__name__)

        if self.enabled:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_crawler(cls, crawler):
        enabled = env_bool("METRICS_ENABLED", True)
        output_path = (
            env_str("METRICS_OUTPUT_PATH", "./out/metrics/ingestion_metrics.jsonl")
            or "./out/metrics/ingestion_metrics.jsonl"
        )

        extension = cls(enabled=enabled, output_path=output_path)
        crawler.signals.connect(extension.spider_closed, signal=signals.spider_closed)
        return extension

    def spider_closed(self, spider, reason):
        if not self.enabled:
            return

        stats = spider.crawler.stats.get_stats() if spider.crawler else {}
        payload = {
            "event": "spider_metrics",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "spider": spider.name,
            "items_scraped": stats.get("item_scraped_count", 0),
            "requests_total": stats.get("downloader/request_count", 0),
            "responses_total": stats.get("downloader/response_count", 0),
            "http_200": stats.get("downloader/response_status_count/200", 0),
            "http_304": stats.get("downloader/response_status_count/304", 0),
            "errors": stats.get("log_count/ERROR", 0),
            "elapsed_seconds": stats.get("elapsed_time_seconds", 0),
            "finish_reason": reason,
        }

        try:
            with self.output_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
        except OSError as exc:
            self.logger.warning(
                "Failed to write metrics to %s: %s", self.output_path, exc
            )
