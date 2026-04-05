import os
from datetime import datetime, timezone

from dateutil import parser as date_parser
from scrapy.spiders import XMLFeedSpider

from bioscope_ingestion.items import IngestionRecord


class EmaRssSpider(XMLFeedSpider):
    name = "ema_rss"
    itertag = "item"

    def start_requests(self):
        feed_url = os.getenv("EMA_RSS_URL", "https://www.ema.europa.eu/en/rss.xml")
        yield self.make_requests_from_url(feed_url)

    def parse_node(self, response, node):
        title = node.xpath("title/text()").get()
        link = node.xpath("link/text()").get()
        pub_date = node.xpath("pubDate/text()").get()
        observed_at = self._parse_date(pub_date)

        yield IngestionRecord(
            source="ema",
            record_type="regulatory_update",
            observed_at=observed_at,
            raw={"title": title, "link": link, "pubDate": pub_date},
            normalized={"title": title, "link": link},
            identifiers={"link": link},
        )

    @staticmethod
    def _parse_date(value: str | None) -> str:
        if not value:
            return datetime.now(timezone.utc).isoformat()
        return date_parser.parse(value).astimezone(timezone.utc).isoformat()
