from datetime import datetime, timezone
import json
import logging

from common.config import env_bool, env_str
from common.config import env_int
from common.kafka import KafkaSink
from bioscope_ingestion.schemas import validate_ingestion_record
from scrapy.exceptions import DropItem


class KafkaPipeline:
    def __init__(self):
        self.sink = KafkaSink.from_env()
        self.validation_enabled = env_bool("VALIDATION_ENABLED", True)
        self.validation_mode = (env_str("VALIDATION_MODE", "drop") or "drop").strip().lower()
        self.structured_logs_enabled = env_bool("STRUCTURED_LOGS_ENABLED", True)
        self.structured_log_every_n_items = env_int("STRUCTURED_LOG_EVERY_N_ITEMS", 100)
        self._processed_items = 0
        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def close_spider(self, spider):
        self.sink.flush()

    def process_item(self, item, spider):
        record = dict(item)
        record["ingested_at"] = datetime.now(timezone.utc).isoformat()

        if self.validation_enabled:
            validated, validation_error = validate_ingestion_record(record)
            if validation_error:
                self._inc_stat(spider, "validation/failed")
                self._log_validation_error(spider, record, validation_error)

                if self.validation_mode == "strict":
                    raise validation_error

                if self.validation_mode == "drop":
                    raise DropItem("Dropped invalid ingestion record")

            elif validated is not None:
                record = validated
                self._inc_stat(spider, "validation/passed")

        self.sink.send(record)
        self._processed_items += 1

        if (
            self.structured_logs_enabled
            and self.structured_log_every_n_items > 0
            and self._processed_items % self.structured_log_every_n_items == 0
        ):
            self.logger.info(
                json.dumps(
                    {
                        "event": "item_ingested",
                        "spider": spider.name,
                        "source": record.get("source"),
                        "record_type": record.get("record_type"),
                        "observed_at": record.get("observed_at"),
                        "ingested_at": record.get("ingested_at"),
                        "items_processed": self._processed_items,
                    },
                    separators=(",", ":"),
                )
            )

        return record

    def _inc_stat(self, spider, key: str) -> None:
        if spider.crawler and spider.crawler.stats:
            spider.crawler.stats.inc_value(key)

    def _log_validation_error(self, spider, record: dict, validation_error) -> None:
        try:
            serialized_errors = json.loads(validation_error.json())
        except Exception:  # pragma: no cover - defensive fallback
            serialized_errors = validation_error.errors()

        self.logger.warning(
            json.dumps(
                {
                    "event": "validation_failed",
                    "spider": spider.name,
                    "source": record.get("source"),
                    "record_type": record.get("record_type"),
                    "mode": self.validation_mode,
                    "errors": serialized_errors,
                },
                separators=(",", ":"),
                default=str,
            )
        )
