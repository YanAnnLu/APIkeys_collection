from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from api_launcher.crawler_asset_download import run_crawler_asset_download_import, run_crawler_seed_download_import
from api_launcher.crawlers.orchestrator import DatasetCrawlResult, DatasetSourceCrawlResult
from api_launcher.crawlers.types import DatasetCandidate
from api_launcher.db import connect_db
from api_launcher.downloads.plan_runner import DownloadPlanRunResult
from api_launcher.ingestion_pipeline import DownloadImportPipelineRun
from api_launcher.models import Dataset, Provider
from api_launcher.repository import ApiCatalogRepository


class CrawlerAssetDownloadImportTest(unittest.TestCase):
    def test_service_builds_formal_crawler_asset_plan_and_runs_pipeline(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "sources.json"
            local_path = root / "local_sources.json"
            source_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "sources": [
                            {
                                "source_id": "demo_index",
                                "provider_id": "demo_provider",
                                "name": "Demo Index",
                                "source_type": "html_file_index",
                                "endpoint_url": "https://example.test/index.html",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            conn = connect_db(root / "catalog.sqlite")
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
                        api_url="https://example.test/data.csv",
                        landing_url="https://example.test/data",
                        metadata={"download_url": "https://example.test/data.csv"},
                    ),
                    source_id="demo_index",
                    source_type="html_file_index",
                    source_url="https://example.test/index.html",
                    confidence=0.9,
                    evidence=("unit-test",),
                )
                fake_crawl = DatasetCrawlResult(
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
                fake_pipeline = DownloadImportPipelineRun(
                    result=DownloadPlanRunResult(
                        entry_count=1,
                        submitted=1,
                        completed=1,
                        failed=0,
                        skipped=0,
                        registered_assets=1,
                        imported=1,
                    ),
                    stage="download_import_completed",
                    import_requested=True,
                )
                plan_path = root / "plans" / "demo_index.json"
                with patch("api_launcher.source_download.crawl_dataset_sources", return_value=fake_crawl):
                    with patch("api_launcher.crawler_asset_download.run_download_import_slice", return_value=fake_pipeline) as runner:
                        result = run_crawler_asset_download_import(
                            "demo_index",
                            repo,
                            root / "downloads",
                            import_sqlite_path=root / "curated.sqlite",
                            plan_path=plan_path,
                            primary_path=source_path,
                            local_path=local_path,
                        )
                        self.assertTrue(result.succeeded)
                        self.assertEqual("ready_to_download", result.plan_result.outcome_bucket)
                        self.assertEqual(1, result.plan_result.direct_download_count)
                        self.assertTrue(plan_path.exists())
                        runner.assert_called_once()
                        called_plan = runner.call_args.args[0]
                        self.assertEqual("source_discovery_download_plan", called_plan["plan_name"])
                        self.assertEqual("https://example.test/data.csv", called_plan["providers"][0]["download_url"])
                        payload = result.to_dict()
                        self.assertEqual("download_import_completed", payload["stage"])
                        self.assertEqual(str(root / "downloads"), payload["artifacts"]["downloads_root"])
                        self.assertEqual(str(root / "curated.sqlite"), payload["artifacts"]["curated_sqlite"])
            finally:
                conn.close()

    def test_service_downloads_one_visible_seed_without_recrawling_source(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "sources.json"
            local_path = root / "local_sources.json"
            source_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "sources": [
                            {
                                "source_id": "demo_index",
                                "provider_id": "demo_provider",
                                "name": "Demo Index",
                                "source_type": "html_file_index",
                                "endpoint_url": "https://example.test/index.html",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            conn = connect_db(root / "catalog.sqlite")
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
                repo.upsert_dataset(
                    Dataset(
                        dataset_uid="demo_provider:dataset_a",
                        provider_id="demo_provider",
                        dataset_id="dataset_a",
                        title="Dataset A",
                        categories=("demo",),
                        native_format="csv",
                        api_url="https://example.test/data.csv",
                        landing_url="https://example.test/data",
                        metadata={
                            "candidate_status": "needs_review",
                            "discovery_source_id": "demo_index",
                            "discovery_source_type": "html_file_index",
                            "download_url": "https://example.test/data.csv",
                        },
                    )
                )
                fake_pipeline = DownloadImportPipelineRun(
                    result=DownloadPlanRunResult(
                        entry_count=1,
                        submitted=1,
                        completed=1,
                        failed=0,
                        skipped=0,
                        registered_assets=1,
                        imported=1,
                    ),
                    stage="download_import_completed",
                    import_requested=True,
                )
                plan_path = root / "plans" / "seed.json"
                with patch("api_launcher.crawler_asset_download.run_download_import_slice", return_value=fake_pipeline) as runner:
                    with patch("api_launcher.source_download.crawl_dataset_sources") as crawler:
                        result = run_crawler_seed_download_import(
                            "demo_index",
                            "demo_provider:dataset_a",
                            repo,
                            root / "downloads",
                            import_sqlite_path=root / "curated.sqlite",
                            plan_path=plan_path,
                            primary_path=source_path,
                            local_path=local_path,
                        )
                        crawler.assert_not_called()
                        runner.assert_called_once()
                self.assertTrue(result.succeeded)
                self.assertEqual("demo_provider:dataset_a", result.dataset_uid)
                self.assertEqual("ready_to_download", result.plan_result.outcome_bucket)
                called_plan = runner.call_args.args[0]
                self.assertEqual("crawler_seed_download_plan", called_plan["plan_name"])
                self.assertEqual("catalog_seed_download_plan", called_plan["source"]["kind"])
                self.assertEqual("demo_provider:dataset_a", called_plan["source"]["dataset_uid"])
                self.assertEqual("https://example.test/data.csv", called_plan["providers"][0]["download_url"])
                payload = result.to_dict()
                self.assertEqual("demo_provider:dataset_a", payload["dataset_uid"])
                self.assertEqual("download_import_completed", payload["stage"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
