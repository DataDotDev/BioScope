"""Unit tests for source-specific throttle settings."""

import os
import sys
import importlib
import pytest
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def reload_spiders_with_env(monkeypatch):
    """Factory fixture that reloads spider modules with modified env."""
    def _reload(env_vars):
        # Set env vars
        for key, value in env_vars.items():
            monkeypatch.setenv(key, str(value))
        
        # Reload all spider modules
        import bioscope_ingestion.spiders.clinicaltrials_api_spider as ct_module
        import bioscope_ingestion.spiders.fda_openfda_spider as fda_module
        import bioscope_ingestion.spiders.fda_rss_spider as fda_rss_module
        import bioscope_ingestion.spiders.ema_rss_spider as ema_module
        
        importlib.reload(ct_module)
        importlib.reload(fda_module)
        importlib.reload(fda_rss_module)
        importlib.reload(ema_module)
        
        return {
            "clinicaltrials": ct_module.ClinicalTrialsApiSpider,
            "fda_openfda": fda_module.FdaOpenFdaSpider,
            "fda_rss": fda_rss_module.FdaRssSpider,
            "ema_rss": ema_module.EmaRssSpider,
        }
    return _reload


from bioscope_ingestion.spiders.clinicaltrials_api_spider import ClinicalTrialsApiSpider
from bioscope_ingestion.spiders.fda_openfda_spider import FdaOpenFdaSpider
from bioscope_ingestion.spiders.fda_rss_spider import FdaRssSpider
from bioscope_ingestion.spiders.ema_rss_spider import EmaRssSpider


class TestClinicalTrialsThrottle:
    """Test ClinicalTrials spider source-specific throttle settings."""

    def test_default_throttle_settings(self):
        """Verify default throttle settings for ClinicalTrials."""
        spider = ClinicalTrialsApiSpider()
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 2.0
        assert spider.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 1

    def test_env_override_download_delay(self, reload_spiders_with_env):
        """Test that environment variable overrides download delay."""
        spiders = reload_spiders_with_env({"CLINICALTRIALS_DOWNLOAD_DELAY": "3"})
        spider = spiders["clinicaltrials"]()
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 3.0

    def test_env_override_concurrent_requests(self, reload_spiders_with_env):
        """Test that environment variable overrides concurrent requests."""
        spiders = reload_spiders_with_env({"CLINICALTRIALS_CONCURRENT_REQUESTS_PER_DOMAIN": "2"})
        spider = spiders["clinicaltrials"]()
        assert spider.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 2


class TestFdaOpenFdaThrottle:
    """Test FDA OpenFDA spider source-specific throttle settings."""

    def test_default_throttle_settings(self):
        """Verify default throttle settings for FDA OpenFDA."""
        spider = FdaOpenFdaSpider()
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 1.0
        assert spider.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 2

    def test_env_override_download_delay(self, reload_spiders_with_env):
        """Test that environment variable overrides download delay."""
        spiders = reload_spiders_with_env({"FDA_DOWNLOAD_DELAY": "2"})
        spider = spiders["fda_openfda"]()
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 2.0

    def test_env_override_concurrent_requests(self, reload_spiders_with_env):
        """Test that environment variable overrides concurrent requests."""
        spiders = reload_spiders_with_env({"FDA_CONCURRENT_REQUESTS_PER_DOMAIN": "3"})
        spider = spiders["fda_openfda"]()
        assert spider.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 3


class TestFdaRssThrottle:
    """Test FDA RSS spider source-specific throttle settings."""

    def test_default_throttle_settings(self):
        """Verify default throttle settings for FDA RSS."""
        spider = FdaRssSpider()
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 1.0
        assert spider.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 2

    def test_env_override_download_delay(self, reload_spiders_with_env):
        """Test that environment variable overrides download delay."""
        spiders = reload_spiders_with_env({"FDA_RSS_DOWNLOAD_DELAY": "0"})
        spider = spiders["fda_rss"]()
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 0.0

    def test_env_override_concurrent_requests(self, reload_spiders_with_env):
        """Test that environment variable overrides concurrent requests."""
        spiders = reload_spiders_with_env({"FDA_RSS_CONCURRENT_REQUESTS_PER_DOMAIN": "1"})
        spider = spiders["fda_rss"]()
        assert spider.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 1


class TestEmaRssThrottle:
    """Test EMA RSS spider source-specific throttle settings."""

    def test_default_throttle_settings(self):
        """Verify default throttle settings for EMA RSS."""
        spider = EmaRssSpider()
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 0.0
        assert spider.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 1

    def test_env_override_download_delay(self, reload_spiders_with_env):
        """Test that environment variable overrides download delay."""
        spiders = reload_spiders_with_env({"EMA_DOWNLOAD_DELAY": "1"})
        spider = spiders["ema_rss"]()
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 1.0

    def test_env_override_concurrent_requests(self, reload_spiders_with_env):
        """Test that environment variable overrides concurrent requests."""
        spiders = reload_spiders_with_env({"EMA_CONCURRENT_REQUESTS_PER_DOMAIN": "2"})
        spider = spiders["ema_rss"]()
        assert spider.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 2


class TestSourceThrottleComparison:
    """Test that different sources have appropriate throttle differences."""

    def test_clinicaltrials_most_conservative(self):
        """ClinicalTrials should have highest download delay."""
        ct = ClinicalTrialsApiSpider()
        fda = FdaOpenFdaSpider()
        ema = EmaRssSpider()
        
        assert ct.custom_settings["DOWNLOAD_DELAY"] >= fda.custom_settings["DOWNLOAD_DELAY"]
        assert fda.custom_settings["DOWNLOAD_DELAY"] >= ema.custom_settings["DOWNLOAD_DELAY"]

    def test_concurrent_requests_reflect_api_characteristics(self):
        """Verify concurrent requests align with API characteristics."""
        ct = ClinicalTrialsApiSpider()
        fda = FdaOpenFdaSpider()
        ema = EmaRssSpider()
        
        # ClinicalTrials is most restrictive (pagination)
        assert ct.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 1
        # FDA is moderate
        assert fda.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 2
        # EMA is minimal for RSS feed
        assert ema.custom_settings["CONCURRENT_REQUESTS_PER_DOMAIN"] == 1
