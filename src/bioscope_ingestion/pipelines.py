from datetime import datetime, timezone

from common.kafka import KafkaSink


class KafkaPipeline:
    def __init__(self):
        self.sink = KafkaSink.from_env()

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def close_spider(self, spider):
        self.sink.flush()

    def process_item(self, item, spider):
        item["ingested_at"] = datetime.now(timezone.utc).isoformat()
        self.sink.send(item)
        return item
