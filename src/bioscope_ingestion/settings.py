from common.config import env_bool, env_int

BOT_NAME = "bioscope_ingestion"

SPIDER_MODULES = ["bioscope_ingestion.spiders"]
NEWSPIDER_MODULE = "bioscope_ingestion.spiders"

ROBOTSTXT_OBEY = True

AUTOTHROTTLE_ENABLED = env_bool("AUTOTHROTTLE_ENABLED", True)
AUTOTHROTTLE_START_DELAY = env_int("AUTOTHROTTLE_START_DELAY", 1)
AUTOTHROTTLE_MAX_DELAY = env_int("AUTOTHROTTLE_MAX_DELAY", 10)
AUTOTHROTTLE_TARGET_CONCURRENCY = float(env_int("AUTOTHROTTLE_TARGET_CONCURRENCY", 1))
DOWNLOAD_DELAY = float(env_int("DOWNLOAD_DELAY", 1))
CONCURRENT_REQUESTS = env_int("CONCURRENT_REQUESTS", 8)
CONCURRENT_REQUESTS_PER_DOMAIN = env_int("CONCURRENT_REQUESTS_PER_DOMAIN", 2)
RETRY_ENABLED = env_bool("RETRY_ENABLED", True)
RETRY_TIMES = env_int("RETRY_TIMES", 3)
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408]

ITEM_PIPELINES = {
    "bioscope_ingestion.pipelines.KafkaPipeline": 300,
}

EXTENSIONS = {
    "bioscope_ingestion.extensions.IngestionMetricsExtension": 500,
}

LOG_LEVEL = "INFO"
