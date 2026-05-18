from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.adapters.gebco import GEBCOTopographyAdapter
from api_launcher.adapters.hyg import HYGStarCatalogAdapter
from api_launcher.adapter_review import adapter_review_agent_payload, adapter_review_items
from api_launcher.core import main
from api_launcher.db import connect_db
from api_launcher.dataset_versions import version_options_for_dataset
from api_launcher.models import Dataset, Provider
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry
from api_launcher.repository import ApiCatalogRepository
from api_launcher.renderer_contracts import GEBCO_PROVIDER_ID, HYG_PROVIDER_ID


class DatasetDownloadPlanTests(unittest.TestCase):
    def test_hyg_dataset_version_becomes_direct_download_plan_entry(self) -> None:
        provider = Provider(
            provider_id=HYG_PROVIDER_ID,
            name="HYG Database",
            owner="Astronexus",
            categories=("astronomy", "stars"),
            geographic_scope="celestial",
            docs_url="https://codeberg.org/astronexus/hyg",
            auth_type="no_key_for_public_data",
        )
        dataset = HYGStarCatalogAdapter().discover(provider)[0]
        option = version_options_for_dataset(dataset)[0]

        entry = provider_dataset_version_plan_entry(provider, dataset, option)

        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("planned", entry["plan_status"])
        self.assertEqual("local_file_asset", entry["target"])
        self.assertTrue(entry["use_staging"])
        self.assertEqual("3.8", entry["dataset_version"]["version"])
        self.assertEqual(option.download_url, entry["download_url"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual(
            "downloads/hyg_database/hyg_v38_bright_star_catalog/3.8/hyg_v38.csv.gz",
            entry["target_path"],
        )

    def test_non_file_dataset_version_requires_adapter_review(self) -> None:
        provider = Provider(
            provider_id=GEBCO_PROVIDER_ID,
            name="GEBCO",
            owner="General Bathymetric Chart of the Oceans",
            categories=("bathymetry",),
            geographic_scope="global",
            docs_url="https://www.gebco.net/data-products/gridded-bathymetry-data",
            auth_type="no_key_for_download_pages",
        )
        dataset = GEBCOTopographyAdapter().discover(provider)[0]
        latest_option = version_options_for_dataset(dataset)[0]

        entry = provider_dataset_version_plan_entry(provider, dataset, latest_option)

        self.assertEqual("2026", entry["dataset_version"]["version"])
        self.assertEqual("adapter_required", entry["download_eligibility"]["status"])
        self.assertEqual("adapter_review_required", entry["import_plan"]["status"])
        self.assertEqual("needs_adapter_review", entry["plan_status"])
        self.assertEqual(latest_option.download_url, entry["adapter_review_url"])
        self.assertEqual("needs_adapter_review", entry["adapter_review"]["status"])
        self.assertEqual("GEBCOTopographyAdapter", entry["adapter_review"]["adapter_id"])
        self.assertEqual("resolve_source_to_direct_download_entries", entry["adapter_review"]["required_action"])
        self.assertEqual(latest_option.download_url, entry["adapter_review"]["source_url"])
        self.assertNotIn("download_url", entry)
        self.assertNotIn("target_path", entry)

    def test_adapter_review_payload_collects_non_direct_entries(self) -> None:
        entry = {
            "provider_id": "example_provider",
            "dataset_id": "selector_dataset",
            "dataset_title": "Selector Dataset",
            "dataset_version": {"version": "2026", "download_url": "https://example.test/select"},
            "download_eligibility": {"status": "adapter_required", "reason": "selector page"},
            "import_plan": {"status": "adapter_review_required", "reason": "needs bounded query"},
            "adapter_review": {
                "adapter_id": "ExampleSelectorAdapter",
                "source_url": "https://example.test/select",
                "required_action": "resolve_source_to_direct_download_entries",
            },
        }

        payload = adapter_review_agent_payload({"providers": [entry]})
        items = adapter_review_items({"providers": [entry]})

        self.assertEqual(1, payload["summary"]["item_count"])
        self.assertEqual({"ExampleSelectorAdapter": 1}, payload["summary"]["by_adapter"])
        self.assertEqual(1, len(items))
        self.assertEqual("ExampleSelectorAdapter", items[0].adapter_id)
        self.assertEqual("resolve_source_to_direct_download_entries", items[0].required_action)

    def test_dataset_plan_summary_counts_direct_and_review_entries(self) -> None:
        entries = [
            {"provider_id": "direct", "download_eligibility": {"status": "direct_download"}},
            {"provider_id": "review", "download_eligibility": {"status": "adapter_required"}},
        ]

        plan = build_dataset_download_plan(entries, plan_name="Dataset Plan")

        self.assertEqual("Dataset Plan", plan["plan_name"])
        self.assertEqual(2, plan["summary"]["provider_count"])
        self.assertEqual(2, plan["summary"]["dataset_version_count"])
        self.assertEqual(1, plan["summary"]["direct_download_count"])
        self.assertEqual(1, plan["summary"]["review_required_count"])

    def test_cli_exports_dataset_plan_from_adapter_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "dataset_plan.json"
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--init-db",
                        "--seed",
                        "--provider",
                        HYG_PROVIDER_ID,
                        "--export-dataset-plan",
                        str(plan_path),
                    ]
                )

            self.assertEqual(0, rc)
            payload = json.loads(plan_path.read_text(encoding="utf-8"))

        self.assertIn("[dataset-plan] wrote", output.getvalue())
        self.assertEqual(1, payload["summary"]["dataset_version_count"])
        self.assertEqual(1, payload["summary"]["direct_download_count"])
        self.assertEqual(HYG_PROVIDER_ID, payload["providers"][0]["provider_id"])
        self.assertEqual("hyg_v38_bright_star_catalog", payload["providers"][0]["dataset_id"])

    def test_cli_lists_adapter_review_items_from_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "providers": [
                            {
                                "provider_id": "gebco",
                                "dataset_id": "gebco_grid",
                                "dataset_version": {"version": "2026"},
                                "download_eligibility": {"status": "adapter_required"},
                                "import_plan": {"status": "adapter_review_required"},
                                "adapter_review": {
                                    "adapter_id": "GEBCOTopographyAdapter",
                                    "source_url": "https://download.gebco.net/downloads",
                                    "required_action": "resolve_source_to_direct_download_entries",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(["--db", str(Path(tmpdir) / "launcher.sqlite"), "--adapter-review-plan", str(plan_path)])

        self.assertEqual(0, rc)
        self.assertIn("[adapter-review] items=1 adapters=1", output.getvalue())
        self.assertIn("adapter=GEBCOTopographyAdapter", output.getvalue())

    def test_cli_exports_candidate_plan_from_reviewable_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "candidate_plan.json"
            conn = connect_db(db_path)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                repo.upsert_dataset(
                    Dataset(
                        dataset_uid="ds_candidate_ais",
                        provider_id="noaa_marinecadastre_ais",
                        dataset_id="marinecadastre_ais_daily_shards",
                        title="NOAA MarineCadastre AIS daily shards",
                        categories=("ais", "maritime"),
                        data_type="spatiotemporal_trajectory",
                        native_format="csv.zst",
                        geographic_scope="us/offshore",
                        landing_url="https://www.coast.noaa.gov/digitalcoast/data/vesseltraffic.html",
                        api_url="https://example.test/ais-2025-01-01.csv.zst",
                        version="2025-01-01",
                        metadata={
                            "candidate_status": "needs_review",
                            "data_family": "spatiotemporal_trajectory",
                            "available_versions": [
                                {
                                    "label": "ais-2025-01-01.csv.zst",
                                    "version": "2025-01-01",
                                    "version_status": "discovered_file_shard",
                                    "download_url": "https://example.test/ais-2025-01-01.csv.zst",
                                    "landing_url": "https://example.test/index.html",
                                },
                                {
                                    "label": "ais-2025-01-02.csv.zst",
                                    "version": "2025-01-02",
                                    "version_status": "discovered_file_shard",
                                    "download_url": "https://example.test/ais-2025-01-02.csv.zst",
                                    "landing_url": "https://example.test/index.html",
                                },
                            ],
                        },
                    )
                )
            finally:
                conn.close()
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--export-candidate-plan",
                        str(plan_path),
                        "--candidate-plan-status",
                        "needs_review",
                        "--candidate-plan-limit",
                        "1",
                        "--mark-candidate-plan-planned",
                    ]
                )
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            conn = connect_db(db_path)
            try:
                planned = ApiCatalogRepository(conn).get_dataset("ds_candidate_ais")
            finally:
                conn.close()

        self.assertEqual(0, rc)
        self.assertIn("[candidate-plan] wrote", output.getvalue())
        self.assertEqual("crawler_dataset_candidates", payload["source"]["kind"])
        self.assertEqual(1, payload["summary"]["dataset_version_count"])
        self.assertEqual(1, payload["summary"]["direct_download_count"])
        self.assertEqual("requires_unpack_or_adapter", payload["providers"][0]["import_plan"]["status"])
        self.assertEqual("unpack_or_transform_downloaded_payload", payload["providers"][0]["adapter_review"]["required_action"])
        self.assertEqual("noaa_marinecadastre_ais", payload["providers"][0]["provider_id"])
        self.assertIsNotNone(planned)
        self.assertEqual("planned", planned.metadata["candidate_status"])


if __name__ == "__main__":
    unittest.main()
