from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from api_launcher.dataset_discovery import load_all_dataset_discovery_sources
from api_launcher.portal_intake import (
    PORTAL_TABLE_COLUMNS,
    build_portal_intake_payload,
    load_portal_intake_entries,
    promote_portal_intake_payload,
)
from api_launcher.core import main


class PortalIntakeTests(unittest.TestCase):
    def test_markdown_table_becomes_actionable_engineering_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "intake.md"
            path.write_text(
                intake_markdown(
                    [
                        row(
                            "new",
                            "P1",
                            "Sample CKAN Catalog",
                            "https://data.example.gov/api/3/action/package_search",
                            "Example Government",
                            "資料目錄 API",
                            "open data, government, CKAN",
                            "national",
                            "public metadata",
                            "ckan_package_search",
                            "team",
                            "official catalog",
                        ),
                        row(
                            "new",
                            "P2",
                            "Sample Provider",
                            "https://science.example.org",
                            "Example Science Org",
                            "資料商首頁",
                            "weather, climate",
                            "global",
                            "不需要 key",
                            "",
                            "team",
                            "",
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            payload = build_portal_intake_payload(path)

        self.assertEqual(2, payload["summary"]["actionable_count"])
        self.assertEqual(1, payload["summary"]["actions"]["dataset_discovery_source_draft"])
        self.assertEqual(1, payload["summary"]["actions"]["provider_seed_draft"])
        source = payload["entries"][0]["dataset_discovery_source_draft"]
        self.assertEqual("data_example_gov_ckan_package_search", source["source_id"])
        provider = payload["entries"][1]["provider_seed_draft"]
        self.assertEqual("no_key_for_public_data", provider["expected_auth_type"])

    def test_examples_empty_rows_and_incomplete_rows_are_not_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "intake.md"
            path.write_text(
                intake_markdown(
                    [
                        row(
                            "new",
                            "P2",
                            "範例：某國開放資料 CKAN",
                            "https://example.gov/api/3/action/package_search",
                            "某國政府",
                            "資料目錄 API",
                            "open data",
                            "national",
                            "public metadata",
                            "ckan_package_search",
                            "name",
                            "範例列",
                        ),
                        row("new", "P2", "", "", "", "待判斷", "", "", "", "", "", ""),
                        row("new", "P1", "Missing URL", "", "Owner", "資料目錄 API", "climate", "global", "", "ckan_package_search", "team", ""),
                    ]
                ),
                encoding="utf-8",
            )

            payload = build_portal_intake_payload(path)

        actions = [entry["recommended_action"] for entry in payload["entries"]]
        self.assertEqual(["ignore_example", "ignore_empty", "incomplete"], actions)
        self.assertEqual(1, payload["summary"]["actionable_count"])
        self.assertIn("missing_url", payload["entries"][2]["warnings"])

    def test_loader_reports_unexpected_table_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "intake.md"
            path.write_text(
                "# Intake\n\n## 待整理入口\n\n| 狀態 | URL |\n| --- | --- |\n| new | https://example.test |\n",
                encoding="utf-8",
            )

            entries, warnings = load_portal_intake_entries(path)

        self.assertEqual([], entries)
        self.assertTrue(any("Unexpected intake table header" in warning for warning in warnings))

    def test_cli_writes_portal_intake_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            intake_path = Path(tmpdir) / "intake.md"
            output_path = Path(tmpdir) / "portal_intake.json"
            intake_path.write_text(
                intake_markdown(
                    [
                        row(
                            "new",
                            "P1",
                            "Sample STAC",
                            "https://stac.example.test/collections",
                            "Example",
                            "資料目錄 API",
                            "satellite",
                            "global",
                            "public",
                            "stac_collections",
                            "team",
                            "",
                        )
                    ]
                ),
                encoding="utf-8",
            )

            rc = main(
                [
                    "--db",
                    str(Path(tmpdir) / "launcher.sqlite"),
                    "--portal-intake-report",
                    "--portal-intake-path",
                    str(intake_path),
                    "--write-portal-intake-json",
                    str(output_path),
                ]
            )

            self.assertEqual(0, rc)
            self.assertTrue(output_path.exists())
            self.assertIn("dataset_discovery_source_draft", output_path.read_text(encoding="utf-8"))

    def test_promote_clean_drafts_to_ignored_local_configs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            intake_path = Path(tmpdir) / "intake.md"
            provider_seed_path = Path(tmpdir) / "provider_discovery_seeds.local.json"
            dataset_source_path = Path(tmpdir) / "dataset_discovery_sources.local.json"
            intake_path.write_text(
                intake_markdown(
                    [
                        row(
                            "new",
                            "P1",
                            "Sample CKAN Catalog",
                            "https://data.example.gov/api/3/action/package_search",
                            "Example Government",
                            "資料目錄 API",
                            "open data, government, CKAN",
                            "national",
                            "public metadata",
                            "ckan_package_search",
                            "team",
                            "official catalog",
                        ),
                        row(
                            "new",
                            "P2",
                            "Sample Provider",
                            "https://science.example.org",
                            "Example Science Org",
                            "資料商首頁",
                            "weather, climate",
                            "global",
                            "不需要 key",
                            "",
                            "team",
                            "",
                        ),
                    ]
                ),
                encoding="utf-8",
            )
            payload = build_portal_intake_payload(intake_path)

            result = promote_portal_intake_payload(payload, provider_seed_path, dataset_source_path)
            provider_data = json.loads(provider_seed_path.read_text(encoding="utf-8"))
            source_data = json.loads(dataset_source_path.read_text(encoding="utf-8"))

        self.assertEqual(2, result["provider_seed_count"])
        self.assertEqual(1, result["dataset_source_count"])
        self.assertEqual(0, result["skipped_count"])
        self.assertEqual({"data_example_gov", "science_example_org"}, {item["provider_id"] for item in provider_data["seeds"]})
        self.assertEqual("data_example_gov_ckan_package_search", source_data["sources"][0]["source_id"])

    def test_cli_promotes_portal_intake_to_local_configs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            intake_path = Path(tmpdir) / "intake.md"
            provider_seed_path = Path(tmpdir) / "config" / "provider_discovery_seeds.local.json"
            dataset_source_path = Path(tmpdir) / "config" / "dataset_discovery_sources.local.json"
            intake_path.write_text(
                intake_markdown(
                    [
                        row(
                            "new",
                            "P1",
                            "Sample STAC",
                            "https://stac.example.test/collections",
                            "Example",
                            "資料目錄 API",
                            "satellite",
                            "global",
                            "public",
                            "stac_collections",
                            "team",
                            "",
                        )
                    ]
                ),
                encoding="utf-8",
            )

            rc = main(
                [
                    "--db",
                    str(Path(tmpdir) / "launcher.sqlite"),
                    "--portal-intake-path",
                    str(intake_path),
                    "--promote-portal-intake-local",
                    "--portal-intake-provider-seeds",
                    str(provider_seed_path),
                    "--portal-intake-dataset-sources-local",
                    str(dataset_source_path),
                ]
            )
            sources = load_all_dataset_discovery_sources(Path(tmpdir) / "missing.json", dataset_source_path)
            provider_seed_exists = provider_seed_path.exists()

        self.assertEqual(0, rc)
        self.assertEqual(1, len(sources))
        self.assertEqual("stac_example_test_stac_collections", sources[0].source_id)
        self.assertTrue(provider_seed_exists)


def intake_markdown(rows: list[str]) -> str:
    header = "| " + " | ".join(PORTAL_TABLE_COLUMNS) + " |"
    separator = "| " + " | ".join("---" for _ in PORTAL_TABLE_COLUMNS) + " |"
    return "# 資料庫入口網站收集表\n\n## 待整理入口\n\n" + "\n".join([header, separator, *rows]) + "\n"


def row(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |"


if __name__ == "__main__":
    unittest.main()
