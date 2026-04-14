import pytest
from pydantic import ValidationError
from scrapy.exceptions import DropItem

from bioscope_ingestion import pipelines


class _DummySink:
    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)

    def flush(self):
        return None


class _Stats:
    def __init__(self):
        self.values = {}

    def inc_value(self, key: str, count: int = 1):
        self.values[key] = self.values.get(key, 0) + count


class _Crawler:
    def __init__(self):
        self.stats = _Stats()


class _Spider:
    name = "test_spider"

    def __init__(self):
        self.crawler = _Crawler()


def _invalid_item() -> dict:
    return {
        "source": "",
        "record_type": "regulatory_update",
        "observed_at": "2026-04-14T00:00:00Z",
        "raw": {},
        "normalized": {},
        "identifiers": {},
    }


def _valid_item() -> dict:
    return {
        "source": "fda_openfda",
        "record_type": "regulatory_update",
        "observed_at": "2026-04-14T00:00:00Z",
        "raw": {},
        "normalized": {},
        "identifiers": {},
    }


def _build_pipeline(monkeypatch, validation_enabled: str, validation_mode: str):
    sink = _DummySink()
    monkeypatch.setattr(pipelines.KafkaSink, "from_env", staticmethod(lambda: sink))
    monkeypatch.setenv("VALIDATION_ENABLED", validation_enabled)
    monkeypatch.setenv("VALIDATION_MODE", validation_mode)
    monkeypatch.setenv("STRUCTURED_LOGS_ENABLED", "false")
    pipeline = pipelines.KafkaPipeline()
    return pipeline, sink


def test_pipeline_validation_mode_drop(monkeypatch):
    pipeline, sink = _build_pipeline(monkeypatch, validation_enabled="true", validation_mode="drop")
    spider = _Spider()

    with pytest.raises(DropItem):
        pipeline.process_item(_invalid_item(), spider)

    assert sink.sent == []
    assert spider.crawler.stats.values.get("validation/failed") == 1


def test_pipeline_validation_mode_strict(monkeypatch):
    pipeline, sink = _build_pipeline(monkeypatch, validation_enabled="true", validation_mode="strict")
    spider = _Spider()

    with pytest.raises(ValidationError):
        pipeline.process_item(_invalid_item(), spider)

    assert sink.sent == []
    assert spider.crawler.stats.values.get("validation/failed") == 1


def test_pipeline_validation_mode_warn(monkeypatch):
    pipeline, sink = _build_pipeline(monkeypatch, validation_enabled="true", validation_mode="warn")
    spider = _Spider()

    result = pipeline.process_item(_invalid_item(), spider)

    assert result["source"] == ""
    assert len(sink.sent) == 1
    assert spider.crawler.stats.values.get("validation/failed") == 1


def test_pipeline_validation_disabled(monkeypatch):
    pipeline, sink = _build_pipeline(monkeypatch, validation_enabled="false", validation_mode="drop")
    spider = _Spider()

    result = pipeline.process_item(_valid_item(), spider)

    assert result["source"] == "fda_openfda"
    assert "ingested_at" in result
    assert len(sink.sent) == 1
    assert spider.crawler.stats.values.get("validation/passed") is None
    assert spider.crawler.stats.values.get("validation/failed") is None
