import scrapy


class IngestionRecord(scrapy.Item):
    source = scrapy.Field()
    record_type = scrapy.Field()
    observed_at = scrapy.Field()
    ingested_at = scrapy.Field()
    raw = scrapy.Field()
    normalized = scrapy.Field()
    identifiers = scrapy.Field()
