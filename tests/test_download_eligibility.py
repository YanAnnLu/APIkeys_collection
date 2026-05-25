# 這份測試鎖定 direct-download 判斷，避免 API endpoint 被誤當可直接抓檔。
from __future__ import annotations

import unittest

from api_launcher.downloads.eligibility import assess_provider_download, looks_like_direct_download
from api_launcher.models import Provider


class DownloadEligibilityTests(unittest.TestCase):
    def test_direct_file_url_is_downloadable(self) -> None:
        provider = Provider(
            provider_id="sample",
            name="Sample",
            owner="Owner",
            categories=("test",),
            geographic_scope="global",
            docs_url="https://example.test/docs",
            api_base_url="https://example.test/data/sample.nc",
            auth_type="no_key",
        )

        eligibility = assess_provider_download(provider)

        self.assertEqual("direct_download", eligibility.status)
        self.assertEqual("https://example.test/data/sample.nc", eligibility.direct_url)
        self.assertFalse(eligibility.requires_adapter)

    def test_api_endpoint_requires_adapter(self) -> None:
        provider = Provider(
            provider_id="api",
            name="API",
            owner="Owner",
            categories=("test",),
            geographic_scope="global",
            docs_url="https://example.test/docs",
            api_base_url="https://example.test/api/v1",
            auth_type="api_key_required",
            key_env_var="SAMPLE_KEY",
        )

        eligibility = assess_provider_download(provider)

        self.assertEqual("adapter_required", eligibility.status)
        self.assertTrue(eligibility.requires_adapter)
        self.assertTrue(eligibility.requires_api_key)

    def test_docs_only_is_metadata_only(self) -> None:
        provider = Provider(
            provider_id="docs",
            name="Docs",
            owner="Owner",
            categories=("test",),
            geographic_scope="global",
            docs_url="https://example.test/docs",
            auth_type="unknown",
        )

        self.assertEqual("metadata_only", assess_provider_download(provider).status)

    def test_direct_download_suffix_detection(self) -> None:
        self.assertTrue(looks_like_direct_download("https://example.test/archive.tar.gz"))
        self.assertTrue(looks_like_direct_download("https://example.test/ais-2025-01-01.csv.zst"))
        self.assertTrue(looks_like_direct_download("https://example.test/data.geojson"))
        self.assertTrue(looks_like_direct_download("https://example.test/boundaries.gpkg"))
        self.assertTrue(looks_like_direct_download("https://example.test/weather/forecast.grib2"))
        self.assertTrue(looks_like_direct_download("https://example.test/ocean/legacy_grid.cdf"))
        self.assertFalse(looks_like_direct_download("https://example.test/api/datasets"))


if __name__ == "__main__":
    unittest.main()
