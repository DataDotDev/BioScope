BOT_NAME = "bioscope_ingestion"

SPIDER_MODULES = ["bioscope_ingestion.spiders"]
NEWSPIDER_MODULE = "bioscope_ingestion.spiders"

ROBOTSTXT_OBEY = True

ITEM_PIPELINES = {
    "bioscope_ingestion.pipelines.KafkaPipeline": 300,
}

LOG_LEVEL = "INFO"
