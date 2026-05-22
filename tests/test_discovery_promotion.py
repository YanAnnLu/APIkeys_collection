# 這份測試鎖定 local discovery promotion guard，避免未通過 audit 的來源被正式提升。
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from api_launcher.crawlers.dataset_sources import DatasetDiscoverySource, append_dataset_discovery_source, load_dataset_discovery_sources
from api_launcher.crawlers.orchestrator import DatasetCrawlResult, DatasetSourceCrawlResult
from api_launcher.discovery import ProviderSeed, append_discovery_seed
from api_launcher.discovery_promotion import promote_local_discovery_catalog
from api_launcher.registry import load_provider_catalog


class DiscoveryPromotionTests(unittest.TestCase):
    def test_promotes_passing_local_source_and_provider_to_official_catalogs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            local_seed_path = tmp / "config" / "provider_discovery_seeds.local.json"
            local_source_path = tmp / "config" / "dataset_discovery_sources.local.json"
            provider_catalog_path = tmp / "catalog" / "APIkeys_collection_catalog.json"
            source_catalog_path = tmp / "catalog" / "dataset_discovery_sources.json"
            append_discovery_seed(
                local_seed_path,
                ProviderSeed(
                    provider_id="example_data",
                    name="Example Data",
                    owner="Example Org",
                    categories=("open_data",),
                    geographic_scope="global",
                    homepage_url="https://example.test",
                    api_base_url="https://example.test/api",
                    expected_auth_type="no_key_for_public_data",
                ),
            )
            append_dataset_discovery_source(local_source_path, source("example_data", "example_data_ckan"))
            provider_catalog_path.parent.mkdir(parents=True, exist_ok=True)
            provider_catalog_path.write_text("[]\n", encoding="utf-8")
            source_catalog_path.write_text('{"schema_version": 1, "sources": []}\n', encoding="utf-8")
            original = patch_crawl_result(
                DatasetCrawlResult(
                    candidates=(),
                    source_results=(
                        DatasetSourceCrawlResult(
                            source_id="example_data_ckan",
                            provider_id="example_data",
                            source_type="ckan_package_search",
                            candidate_count=3,
                            unique_candidate_count=3,
                        ),
                    ),
                )
            )
            try:
                result = promote_local_discovery_catalog(
                    local_seed_path,
                    local_source_path,
                    provider_catalog_path,
                    source_catalog_path,
                )
            finally:
                restore_crawl_result(original)

            providers = load_provider_catalog(provider_catalog_path)
            sources = load_dataset_discovery_sources(source_catalog_path)

        self.assertEqual(1, result.promoted_provider_count)
        self.assertEqual(1, result.promoted_source_count)
        self.assertEqual("example_data", providers[0].provider_id)
        self.assertEqual("example_data_ckan", sources[0].source_id)
        self.assertEqual("review_or_upsert_dataset_candidates", result.audit["next_action"])
        self.assertEqual("review_candidates", result.audit["sources"][0]["next_action"])

    def test_skips_source_when_audit_has_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            local_seed_path = tmp / "provider_discovery_seeds.local.json"
            local_source_path = tmp / "dataset_discovery_sources.local.json"
            provider_catalog_path = tmp / "APIkeys_collection_catalog.json"
            source_catalog_path = tmp / "dataset_discovery_sources.json"
            append_discovery_seed(
                local_seed_path,
                ProviderSeed(
                    provider_id="example_data",
                    name="Example Data",
                    owner="Example Org",
                    categories=("open_data",),
                    geographic_scope="global",
                    homepage_url="https://example.test",
                ),
            )
            append_dataset_discovery_source(local_source_path, source("example_data", "example_data_ckan"))
            provider_catalog_path.write_text("[]\n", encoding="utf-8")
            source_catalog_path.write_text('{"schema_version": 1, "sources": []}\n', encoding="utf-8")
            original = patch_crawl_result(
                DatasetCrawlResult(
                    candidates=(),
                    source_results=(
                        DatasetSourceCrawlResult(
                            source_id="example_data_ckan",
                            provider_id="example_data",
                            source_type="ckan_package_search",
                            candidate_count=0,
                            warnings=("zero_candidates",),
                        ),
                    ),
                )
            )
            try:
                result = promote_local_discovery_catalog(
                    local_seed_path,
                    local_source_path,
                    provider_catalog_path,
                    source_catalog_path,
                )
            finally:
                restore_crawl_result(original)
            provider_catalog = json.loads(provider_catalog_path.read_text(encoding="utf-8"))

        self.assertEqual(0, result.promoted_provider_count)
        self.assertEqual(0, result.promoted_source_count)
        self.assertEqual(1, result.skipped_count)
        self.assertEqual([], provider_catalog)
        self.assertEqual("inspect_source_audit_results_before_upsert_or_promotion", result.audit["next_action"])
        self.assertEqual("warning", result.audit["audit_summary"]["status"])
        self.assertEqual({"zero_candidates": 1}, result.audit["audit_summary"]["by_warning_code"])
        self.assertEqual(["example_data_ckan"], [item["source_id"] for item in result.audit["audit_summary"]["problem_sources"]])
        self.assertEqual(["zero_candidates"], result.audit["sources"][0]["warning_codes"])
        self.assertEqual("repair_crawler_query_or_parser", result.audit["sources"][0]["next_action"])


def source(provider_id: str, source_id: str) -> DatasetDiscoverySource:
    return DatasetDiscoverySource(
        source_id=source_id,
        provider_id=provider_id,
        name="Example CKAN",
        source_type="ckan_package_search",
        endpoint_url="https://example.test/api/3/action/package_search",
        categories=("open_data",),
        geographic_scope="global",
        min_expected_candidates=1,
    )


def patch_crawl_result(result: DatasetCrawlResult):
    import api_launcher.discovery_promotion as discovery_promotion

    original = discovery_promotion.crawl_dataset_sources
    discovery_promotion.crawl_dataset_sources = lambda *_args, **_kwargs: result
    return original


def restore_crawl_result(original) -> None:
    import api_launcher.discovery_promotion as discovery_promotion

    discovery_promotion.crawl_dataset_sources = original


if __name__ == "__main__":
    unittest.main()
