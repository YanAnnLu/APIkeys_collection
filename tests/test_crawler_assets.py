from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from api_launcher.crawler_asset_service import run_crawler_asset_listing
from api_launcher.crawler_asset_profiles import (
    crawler_asset_profile_for,
    load_crawler_asset_profiles,
    set_crawler_asset_archived,
    toggle_crawler_asset_archived,
)
from api_launcher.crawler_asset_capabilities import bounds_facets_for_source
from api_launcher.crawler_assets import (
    BUILD_DOWNLOAD_PLAN,
    crawler_asset_from_source,
    load_crawler_asset_source,
    load_crawler_assets,
    status_label,
)
from api_launcher.crawlers.orchestrator import DatasetCrawlOptions, DatasetCrawlResult, DatasetSourceCrawlResult
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.db import connect_db
from api_launcher.models import Dataset, Provider
from api_launcher.repository import ApiCatalogRepository


class CrawlerAssetTest(unittest.TestCase):
    def test_supported_source_exposes_three_capability_slots(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_ckan",
            provider_id="demo_provider",
            name="Demo CKAN",
            source_type="ckan_package_search",
            endpoint_url="https://example.test/api/3/action/package_search",
            search_terms=("ocean",),
            categories=("catalog",),
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("demo_ckan", asset.asset_id)
        self.assertEqual("bounded", asset.maturity)
        self.assertEqual(("fetch_metadata", "list_datasets", BUILD_DOWNLOAD_PLAN), tuple(item.capability_id for item in asset.capabilities))
        self.assertEqual("ready", asset.capability_status("fetch_metadata"))
        self.assertEqual("bounded", asset.capability_status("list_datasets"))
        self.assertEqual("needs_bounds_or_adapter", asset.capability_status(BUILD_DOWNLOAD_PLAN))
        self.assertEqual("needs_bounds_or_adapter", asset.capability_status("download_selected"))
        self.assertEqual(("package", "resource", "format", "limit"), asset.capabilities[2].bounds_facets)
        self.assertEqual("public_or_review", asset.capabilities[2].credential_mode)
        self.assertIn("adapter_required", asset.capabilities[2].error_buckets)
        self.assertEqual(1, asset.seed_count)
        self.assertEqual("1 configured", asset.seed_summary)
        self.assertEqual("public_or_review", asset.access_requirement)
        self.assertGreaterEqual(asset.trust_score, 50)

    def test_file_index_source_can_offer_selectable_download(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo Index",
            source_type="html_file_index",
            endpoint_url="https://example.test/files/index.html",
            file_url_regex=r"demo-(?P<version>\d{4})\.csv$",
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("selectable", asset.capability_status(BUILD_DOWNLOAD_PLAN))
        self.assertIn("下載計畫:可選", asset.capability_summary)
        self.assertEqual(("version", "file_pattern", "limit"), asset.capabilities[2].bounds_facets)
        self.assertEqual("full entry", asset.seed_summary)

    def test_unsupported_source_is_visible_but_marked_as_handler_backlog(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_unknown",
            provider_id="demo_provider",
            name="Demo Unknown",
            source_type="unknown_portal",
            endpoint_url="https://example.test/",
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("unbuilt", asset.maturity)
        self.assertEqual("needs_handler", asset.risk_tier)
        self.assertEqual("needs_handler", asset.capability_status("fetch_metadata"))
        self.assertEqual("待補", status_label("needs_handler"))

    def test_account_requirement_is_assigned_to_crawler_asset(self) -> None:
        source = DatasetDiscoverySource(
            source_id="earthdata_guarded",
            provider_id="nasa_earthdata",
            name="Earthdata guarded source",
            source_type="cmr_collections",
            endpoint_url="https://cmr.earthdata.nasa.gov/search/collections.json",
            notes="Downloads may require Earthdata account login.",
        )

        asset = crawler_asset_from_source(source)

        self.assertEqual("crawler_managed_auth", asset.access_requirement)
        self.assertEqual("user_credential_required", asset.capabilities[0].credential_mode)

    def test_source_type_drives_dynamic_bounds_facets(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
        )

        self.assertEqual(("collection", "time", "bbox", "asset_role", "limit"), bounds_facets_for_source(source))

    def test_load_crawler_asset_source_finds_single_entry(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )

            source = load_crawler_asset_source("demo_index", source_path, None)

        self.assertIsNotNone(source)
        assert source is not None
        self.assertEqual("html_file_index", source.source_type)

    def test_local_profile_can_archive_and_reenable_asset(self) -> None:
        with TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"

            archived = set_crawler_asset_archived("demo_index", True, profile_path)
            profiles = load_crawler_asset_profiles(profile_path)
            current = crawler_asset_profile_for("demo_index", profiles)

            self.assertTrue(archived.archived)
            self.assertFalse(archived.enabled)
            self.assertEqual("archived", current.profile_state)

            enabled = toggle_crawler_asset_archived("demo_index", profile_path)

        self.assertFalse(enabled.archived)
        self.assertTrue(enabled.enabled)
        self.assertEqual("active", enabled.profile_state)

    def test_loaded_assets_apply_archived_profile_without_changing_source(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            set_crawler_asset_archived("demo_index", True, profile_path)

            assets = load_crawler_assets(source_path, None, profile_path)

        self.assertEqual(1, len(assets))
        self.assertTrue(assets[0].archived)
        self.assertEqual("archived", assets[0].risk_tier)
        self.assertEqual("archived_disabled", assets[0].next_action)

    def test_service_blocks_archived_asset_before_crawl(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            local_path = Path(tmp) / "local_sources.json"
            profile_path = Path(tmp) / "crawler_asset_profiles.local.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            set_crawler_asset_archived("demo_index", True, profile_path)
            conn = connect_db(Path(tmp) / "catalog.sqlite")
            try:
                called = False

                def fake_runner(_sources, _options):
                    nonlocal called
                    called = True
                    raise AssertionError("archived crawler asset should not crawl")

                result = run_crawler_asset_listing(
                    "demo_index",
                    conn,
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                    crawl_runner=fake_runner,
                )
            finally:
                conn.close()

        self.assertFalse(called)
        self.assertTrue(result.blocked)
        self.assertEqual("archived", result.blocked_reason)
        self.assertEqual("unarchive_before_crawl", result.next_action)

    def test_service_upserts_candidates_for_single_asset(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "sources.json"
            local_path = Path(tmp) / "local_sources.json"
            source_path.write_text(
                """
{
  "schema_version": 1,
  "sources": [
    {
      "source_id": "demo_index",
      "provider_id": "demo_provider",
      "name": "Demo Index",
      "source_type": "html_file_index",
      "endpoint_url": "https://example.test/index.html"
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            conn = connect_db(Path(tmp) / "catalog.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="demo_provider",
                        name="Demo Provider",
                        owner="Demo",
                        categories=("demo",),
                        geographic_scope="sample",
                        docs_url="https://example.test/docs",
                    )
                )
                candidate = DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid="demo_provider:dataset_a",
                        provider_id="demo_provider",
                        dataset_id="dataset_a",
                        title="Dataset A",
                        categories=("demo",),
                        native_format="csv",
                    ),
                    source_id="demo_index",
                    source_type="html_file_index",
                    source_url="https://example.test/index.html",
                    confidence=0.9,
                    evidence=("unit-test",),
                )

                def fake_runner(sources, options):
                    self.assertEqual(["demo_index"], [source.source_id for source in sources])
                    self.assertIsInstance(options, DatasetCrawlOptions)
                    return DatasetCrawlResult(
                        candidates=(candidate,),
                        source_results=(
                            DatasetSourceCrawlResult(
                                source_id="demo_index",
                                provider_id="demo_provider",
                                source_type="html_file_index",
                                candidate_count=1,
                                candidates=(candidate,),
                            ),
                        ),
                    )

                result = run_crawler_asset_listing(
                    "demo_index",
                    conn,
                    primary_path=source_path,
                    local_path=local_path,
                    crawl_runner=fake_runner,
                )
                datasets = repo.list_datasets("demo_provider")
            finally:
                conn.close()

        self.assertFalse(result.blocked)
        self.assertEqual(1, result.candidate_count)
        self.assertEqual(1, result.upserted_count)
        self.assertEqual(0, result.skipped_provider_count)
        self.assertEqual(1, len(datasets))
        self.assertEqual("Dataset A", datasets[0].title)
        self.assertEqual("demo_index", datasets[0].metadata["discovery_source_id"])


if __name__ == "__main__":
    unittest.main()
