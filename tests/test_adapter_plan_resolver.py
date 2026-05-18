from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.adapter_plan_resolver import (
    direct_resource_entries_for_plan_entry,
    resolve_adapter_review_plan_payload,
)
from api_launcher.core import main


class AdapterPlanResolverTests(unittest.TestCase):
    def test_ckan_resource_metadata_promotes_direct_csv_entry(self) -> None:
        plan = {"providers": [ckan_review_entry()]}

        resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        self.assertEqual(1, resolved["summary"]["direct_download_count"])
        self.assertEqual(0, resolved["summary"]["review_required_count"])
        entry = resolved["providers"][0]
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("https://example.test/buoy.csv", entry["download_url"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual("planned", entry["plan_status"])
        self.assertIn("buoy.csv", entry["target_path"])
        self.assertNotIn("adapter_review", entry)
        self.assertEqual("generic_resource_direct_download_resolver", entry["adapter_resolution"]["resolver_id"])

    def test_non_direct_resources_remain_in_adapter_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [{"name": "HTML landing", "format": "HTML", "url": "https://example.test/page"}]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(0, result.resolved_review_entries)
        self.assertEqual(1, result.unresolved_review_entries)
        self.assertEqual(0, result.direct_entries_added)
        self.assertEqual(1, resolved["summary"]["review_required_count"])
        self.assertIn("no direct downloadable resource URL", result.warnings[0])
        self.assertIn("adapter_review", resolved["providers"][0])

    def test_link_metadata_promotes_direct_geojson_entry(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata.pop("resources", None)
        metadata["links"] = {
            "access": [
                {"rel": "data", "type": "application/geo+json", "url": "https://example.test/boundaries.geojson"},
                {"rel": "documentation", "href": "https://example.test/about"},
            ]
        }

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://example.test/boundaries.geojson", resolved_entry["download_url"])
        self.assertEqual("geojson", resolved_entry["source_format"])
        self.assertEqual("json_to_sqlite", resolved_entry["import_plan"]["importer"])

    def test_direct_resource_entries_can_keep_original_review_entry(self) -> None:
        plan = {"providers": [ckan_review_entry()]}

        resolved, result = resolve_adapter_review_plan_payload(plan, keep_original_review_entries=True)

        self.assertEqual(2, len(resolved["providers"]))
        self.assertEqual(1, result.direct_entries_added)
        self.assertEqual(1, resolved["summary"]["direct_download_count"])
        self.assertEqual(1, resolved["summary"]["review_required_count"])

    def test_cli_writes_resolved_adapter_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "candidate_plan.json"
            output_path = Path(tmpdir) / "candidate_plan.resolved.json"
            input_path.write_text(json.dumps({"providers": [ckan_review_entry()]}), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(Path(tmpdir) / "launcher.sqlite"),
                        "--resolve-adapter-plan",
                        str(input_path),
                        "--write-resolved-adapter-plan",
                        str(output_path),
                    ]
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertIn("[adapter-resolve] wrote", output.getvalue())
        self.assertEqual(1, payload["summary"]["direct_download_count"])
        self.assertEqual(1, payload["adapter_resolution"]["direct_entries_added"])

    def test_entry_without_source_resolution_action_is_ignored(self) -> None:
        entry = ckan_review_entry()
        entry["download_eligibility"] = {"status": "direct_download"}
        entry["adapter_review"] = {"required_action": "unpack_or_transform_downloaded_payload"}

        self.assertEqual([], direct_resource_entries_for_plan_entry(entry, 1))


def ckan_review_entry() -> dict[str, object]:
    return {
        "provider_id": "data_gov",
        "name": "Data.gov",
        "dataset_uid": "data_gov:ocean-buoy-observations",
        "dataset_id": "ocean-buoy-observations",
        "dataset_title": "Ocean buoy observations",
        "categories": ["open_data", "ckan"],
        "geographic_scope": "us",
        "download_eligibility": {"status": "adapter_required", "reason": "package resource review"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "data_gov_ocean_buoy_observations"},
        "dataset_version": {
            "dataset_uid": "data_gov:ocean-buoy-observations",
            "dataset_id": "ocean-buoy-observations",
            "label": "2026-05-18",
            "version": "2026-05-18",
            "version_status": "unknown",
            "download_url": "https://api.example.test/action/package_show?id=ocean-buoy-observations",
            "landing_url": "https://catalog.example.test/ocean-buoy-observations",
            "metadata": {
                "data_family": "timeseries",
                "resources": [
                    {"name": "CSV", "format": "CSV", "url": "https://example.test/buoy.csv"},
                    {"name": "HTML", "format": "HTML", "url": "https://example.test/buoy"},
                ],
            },
        },
        "adapter_review": {
            "adapter_id": "data_gov_adapter",
            "source_url": "https://api.example.test/action/package_show?id=ocean-buoy-observations",
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


if __name__ == "__main__":
    unittest.main()
