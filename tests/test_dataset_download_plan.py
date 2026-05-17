from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.adapters.gebco import GEBCOTopographyAdapter
from api_launcher.adapters.hyg import HYGStarCatalogAdapter
from api_launcher.core import main
from api_launcher.dataset_versions import version_options_for_dataset
from api_launcher.models import Provider
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry
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
        self.assertEqual("needs_adapter_review", entry["plan_status"])
        self.assertEqual(latest_option.download_url, entry["adapter_review_url"])
        self.assertNotIn("download_url", entry)
        self.assertNotIn("target_path", entry)

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


if __name__ == "__main__":
    unittest.main()
