from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

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

    def test_oversized_declared_resource_remains_in_adapter_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {"name": "Huge ZIP", "format": "ZIP", "url": "https://example.test/huge.zip", "size": 250_000_000}
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(0, result.direct_entries_added)
        self.assertEqual(1, result.unresolved_review_entries)
        self.assertIn("oversized_resources=1", result.warnings[0])
        self.assertIn("adapter_review", resolved["providers"][0])

    def test_small_repository_resource_promotes_direct_entry(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "Zenodo metadata CSV",
                "format": "CSV",
                "download_url": "https://zenodo.example.test/api/records/1/files/sample.csv/content",
                "size": 2048,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("https://zenodo.example.test/api/records/1/files/sample.csv/content", entry["download_url"])
        self.assertEqual(2048, entry["adapter_resolution"]["resource_size_bytes"])

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

    def test_erddap_griddap_metadata_promotes_bounded_csv_sample_entry(self) -> None:
        plan = {"providers": [erddap_review_entry("griddap")]}

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=erddap_info_payload()) as fetch:
            resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        fetch.assert_called_once_with("https://erddap.example.test/erddap/info/sample_dataset/index.json")
        entry = resolved["providers"][0]
        self.assertEqual("erddap_bounded_sample_query_resolver", entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("griddap", entry["adapter_resolution"]["protocol"])
        self.assertEqual("csv", entry["source_format"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual(
            "https://erddap.example.test/erddap/griddap/sample_dataset.csv?sea_water_temperature[0:1:0][0:1:0][0:1:0]",
            entry["download_url"],
        )
        self.assertNotIn("adapter_review", entry)

    def test_erddap_tabledap_metadata_promotes_limited_csv_sample_entry(self) -> None:
        plan = {"providers": [erddap_review_entry("tabledap")]}

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=erddap_info_payload()):
            resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("tabledap", entry["adapter_resolution"]["protocol"])
        self.assertEqual(
            "https://erddap.example.test/erddap/tabledap/sample_dataset.csv?time,latitude,longitude,sea_water_temperature,sea_water_salinity&.limit=25",
            entry["download_url"],
        )
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])

    def test_stac_collection_metadata_promotes_bounded_item_sample_entry(self) -> None:
        plan = {"providers": [stac_review_entry()]}

        resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("stac_bounded_item_search_resolver", entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("https://stac.example.test/collections/sentinel-2-l2a/items?limit=1", entry["download_url"])
        self.assertEqual("geojson", entry["source_format"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("json_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual("planned", entry["plan_status"])
        self.assertTrue(entry["target_path"].endswith(".geojson"))
        self.assertNotIn("adapter_review", entry)

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


def erddap_review_entry(protocol: str) -> dict[str, object]:
    protocols = {"tabledap": "", "griddap": ""}
    protocols[protocol] = f"/erddap/{protocol}/sample_dataset"
    return {
        "provider_id": "emodnet_erddap",
        "name": "EMODnet ERDDAP",
        "dataset_uid": "emodnet_erddap:sample_dataset",
        "dataset_id": "sample_dataset",
        "dataset_title": "Sample ERDDAP dataset",
        "categories": ["erddap", "ocean"],
        "geographic_scope": "global",
        "download_eligibility": {"status": "adapter_required", "reason": "ERDDAP query must be bounded first"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "emodnet_erddap_sample_dataset"},
        "dataset_version": {
            "dataset_uid": "emodnet_erddap:sample_dataset",
            "dataset_id": "sample_dataset",
            "label": "discovered",
            "version": "discovered",
            "version_status": "unknown",
            "download_url": f"/erddap/{protocol}/sample_dataset",
            "landing_url": "https://publisher.example.test/dataset-page",
            "metadata": {
                "native_format": "erddap",
                "data_family": "grid" if protocol == "griddap" else "table",
                "source_url": "https://erddap.example.test/erddap/tabledap/allDatasets.json",
                "erddap_dataset_id": "sample_dataset",
                "erddap_protocols": protocols,
            },
        },
        "adapter_review": {
            "adapter_id": "emodnet_erddap_adapter",
            "source_url": f"/erddap/{protocol}/sample_dataset",
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


def stac_review_entry() -> dict[str, object]:
    return {
        "provider_id": "earth_search_stac",
        "name": "Earth Search STAC",
        "dataset_uid": "earth_search_stac:sentinel-2-l2a",
        "dataset_id": "sentinel-2-l2a",
        "dataset_title": "Sentinel-2 Level-2A",
        "categories": ["stac", "satellite", "earth_observation"],
        "geographic_scope": "global",
        "download_eligibility": {"status": "adapter_required", "reason": "STAC item search must be bounded first"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "earth_search_stac_sentinel_2_l2a"},
        "dataset_version": {
            "dataset_uid": "earth_search_stac:sentinel-2-l2a",
            "dataset_id": "sentinel-2-l2a",
            "label": "discovered",
            "version": "1.0.0",
            "version_status": "unknown",
            "download_url": "https://stac.example.test/collections/sentinel-2-l2a/items",
            "landing_url": "https://stac.example.test/collections/sentinel-2-l2a",
            "metadata": {
                "native_format": "stac_collection",
                "data_family": "raster_or_grid",
                "stac_id": "sentinel-2-l2a",
                "asset_keys": ["visual", "red", "green", "blue"],
                "links": [
                    {
                        "rel": "items",
                        "type": "application/geo+json",
                        "href": "https://stac.example.test/collections/sentinel-2-l2a/items",
                    },
                    {"rel": "self", "href": "https://stac.example.test/collections/sentinel-2-l2a"},
                ],
            },
        },
        "adapter_review": {
            "adapter_id": "earth_search_stac_adapter",
            "source_url": "https://stac.example.test/collections/sentinel-2-l2a/items",
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


def erddap_info_payload() -> dict[str, object]:
    return {
        "table": {
            "columnNames": ["Row Type", "Variable Name", "Attribute Name", "Data Type", "Value"],
            "rows": [
                ["dimension", "time", "", "double", ""],
                ["dimension", "latitude", "", "double", ""],
                ["dimension", "longitude", "", "double", ""],
                ["variable", "sea_water_temperature", "", "float", ""],
                ["variable", "sea_water_salinity", "", "float", ""],
            ],
        }
    }


if __name__ == "__main__":
    unittest.main()
