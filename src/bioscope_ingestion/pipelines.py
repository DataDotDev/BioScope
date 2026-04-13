from datetime import datetime, timezone
import json
import logging

from common.config import env_bool, env_str
from common.config import env_int
from common.kafka import KafkaSink


class KafkaPipeline:
    def __init__(self):
        self.sink = KafkaSink.from_env()
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
        item["ingested_at"] = datetime.now(timezone.utc).isoformat()
        self.sink.send(item)
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
                        "source": item.get("source"),
                        "record_type": item.get("record_type"),
                        "observed_at": item.get("observed_at"),
                        "ingested_at": item.get("ingested_at"),
                        "items_processed": self._processed_items,
                    },
                    separators=(",", ":"),
                )
            )

        return item
