# 這份測試鎖定 adapter-review plan resolver，避免未受限 API 被誤轉成下載工作。
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
    resource_mappings_from_candidate,
)
from api_launcher.core import main


class AdapterPlanResolverTests(unittest.TestCase):
    def test_resource_mapping_recursion_depth_is_bounded(self) -> None:
        nested: dict[str, object] = {}
        cursor = nested
        for index in range(20):
            next_node: dict[str, object] = {}
            cursor[f"level_{index}"] = next_node
            cursor = next_node
        cursor["resources"] = [{"format": "CSV", "url": "https://example.test/deep.csv"}]

        self.assertEqual([], resource_mappings_from_candidate(nested, max_depth=4))
        resources = resource_mappings_from_candidate(nested, max_depth=30)

        self.assertEqual(1, len(resources))
        self.assertEqual("https://example.test/deep.csv", resources[0]["url"])

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

        with patch("api_launcher.adapter_plan_resolver.fetch_json", side_effect=AssertionError("unexpected fetch")):
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

        with patch("api_launcher.adapter_plan_resolver.fetch_json", side_effect=AssertionError("unexpected fetch")):
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

    def test_dcat_download_url_promotes_direct_csv_entry(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "DCAT CSV export",
                "format": "text/csv",
                "downloadURL": "https://data.example.test/exports/sample.csv",
                "byteSize": 2048,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/exports/sample.csv", resolved_entry["download_url"])
        self.assertEqual("csv", resolved_entry["source_format"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])
        self.assertEqual(2048, resolved_entry["adapter_resolution"]["resource_size_bytes"])

    def test_schema_org_content_url_promotes_direct_json_entry(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "Schema.org JSON sample",
                "encodingFormat": "application/json",
                "contentUrl": "https://data.example.test/exports/sample.json",
                "contentSize": "4096",
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/exports/sample.json", resolved_entry["download_url"])
        self.assertEqual("json", resolved_entry["source_format"])
        self.assertEqual("json_to_sqlite", resolved_entry["import_plan"]["importer"])
        self.assertEqual(4096, resolved_entry["adapter_resolution"]["resource_size_bytes"])

    def test_compound_geojson_gz_resource_keeps_supported_import_plan(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "Compressed GeoJSON export",
                "encodingFormat": "application/gzip",
                "contentUrl": "https://data.example.test/exports/boundaries.geojson.gz",
                "contentSize": "4096",
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/exports/boundaries.geojson.gz", resolved_entry["download_url"])
        self.assertEqual("geojson.gz", resolved_entry["source_format"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])
        self.assertEqual("json_to_sqlite", resolved_entry["import_plan"]["importer"])
        self.assertTrue(resolved_entry["target_path"].endswith(".geojson.gz"))

    def test_extensionless_ndjson_resource_uses_declared_format(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "NDJSON API export",
                "format": "application/x-ndjson",
                "downloadURL": "https://data.example.test/api/download?id=events",
                "byteSize": "2048",
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/api/download?id=events", resolved_entry["download_url"])
        self.assertEqual("ndjson", resolved_entry["source_format"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])
        self.assertEqual("json_to_sqlite", resolved_entry["import_plan"]["importer"])
        self.assertTrue(resolved_entry["target_path"].endswith(".ndjson"))

    def test_dcat_download_url_list_object_promotes_direct_csv_entry(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "DCAT object-valued CSV export",
                "format": ["text/csv"],
                "downloadURL": [{"@id": "https://data.example.test/exports/object-sample.csv"}],
                "byteSize": {"@value": "2048"},
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/exports/object-sample.csv", resolved_entry["download_url"])
        self.assertEqual("csv", resolved_entry["source_format"])
        self.assertEqual("csv_to_sqlite", resolved_entry["import_plan"]["importer"])
        self.assertEqual(2048, resolved_entry["adapter_resolution"]["resource_size_bytes"])

    def test_dcat_media_type_promotes_extensionless_csv_url(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "DCAT API CSV export",
                "mediaType": {"@value": "text/csv"},
                "downloadURL": "https://data.example.test/api/download?id=sample",
                "byteSize": 2048,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/api/download?id=sample", resolved_entry["download_url"])
        self.assertEqual("csv", resolved_entry["source_format"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", resolved_entry["import_plan"]["importer"])
        self.assertEqual("csv", resolved_entry["content_detection"]["source_format"])
        self.assertEqual("csv_to_sqlite", resolved_entry["content_parser"]["parser_id"])
        self.assertEqual("supported_after_download", resolved_entry["content_parser"]["import_status"])
        self.assertEqual("text/csv", resolved_entry["adapter_resolution"]["resource_format"])

    def test_geotiff_media_type_promotes_direct_asset_for_parser_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "COG export",
                "mediaType": "image/tiff; application=geotiff",
                "downloadURL": "https://data.example.test/api/download?id=geotiff",
                "byteSize": 2048,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/api/download?id=geotiff", resolved_entry["download_url"])
        self.assertEqual("geotiff", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertEqual("geospatial_asset_review", resolved_entry["content_parser"]["parser_id"])
        self.assertEqual("content_parser_required", resolved_entry["content_parser"]["review_bucket"])
        self.assertTrue(resolved_entry["target_path"].endswith(".tif"))

    def test_geopackage_media_type_promotes_direct_asset_for_parser_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "GeoPackage export",
                "mediaType": "application/geopackage+sqlite3",
                "downloadURL": "https://data.example.test/api/download?id=gpkg",
                "byteSize": 4096,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/api/download?id=gpkg", resolved_entry["download_url"])
        self.assertEqual("geopackage", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertEqual("geospatial_asset_review", resolved_entry["content_parser"]["parser_id"])
        self.assertEqual("content_parser_required", resolved_entry["content_parser"]["review_bucket"])
        self.assertTrue(resolved_entry["target_path"].endswith(".gpkg"))

    def test_netcdf_url_suffix_promotes_direct_asset_for_parser_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "NetCDF export",
                "downloadURL": "https://data.example.test/ocean/sample.nc",
                "byteSize": 4096,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/ocean/sample.nc", resolved_entry["download_url"])
        self.assertEqual("netcdf", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertEqual("scientific_grid_review", resolved_entry["content_parser"]["parser_id"])
        self.assertEqual("content_parser_required", resolved_entry["content_parser"]["review_bucket"])
        self.assertTrue(resolved_entry["target_path"].endswith(".nc"))

    def test_grib2_url_suffix_promotes_direct_asset_for_parser_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "GRIB2 forecast",
                "downloadURL": "https://data.example.test/weather/forecast.grib2",
                "byteSize": 4096,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/weather/forecast.grib2", resolved_entry["download_url"])
        self.assertEqual("grib", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertEqual("scientific_grid_review", resolved_entry["content_parser"]["parser_id"])
        self.assertEqual("content_parser_required", resolved_entry["content_parser"]["review_bucket"])
        self.assertTrue(resolved_entry["target_path"].endswith(".grib2"))

    def test_h5_url_suffix_promotes_direct_asset_as_hdf5_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "HDF5 swath",
                "downloadURL": "https://data.example.test/science/orbit_swath.h5",
                "byteSize": 4096,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/science/orbit_swath.h5", resolved_entry["download_url"])
        self.assertEqual("hdf5", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertEqual("scientific_grid_review", resolved_entry["content_parser"]["parser_id"])
        self.assertEqual("content_parser_required", resolved_entry["content_parser"]["review_bucket"])
        self.assertTrue(resolved_entry["target_path"].endswith(".h5"))

    def test_geopackage_url_suffix_promotes_direct_asset_for_parser_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "GeoPackage export",
                "downloadURL": "https://data.example.test/gis/boundaries.gpkg",
                "byteSize": 4096,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/gis/boundaries.gpkg", resolved_entry["download_url"])
        self.assertEqual("geopackage", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertEqual("geospatial_asset_review", resolved_entry["content_parser"]["parser_id"])
        self.assertEqual("content_parser_required", resolved_entry["content_parser"]["review_bucket"])
        self.assertTrue(resolved_entry["target_path"].endswith(".gpkg"))

    def test_gis_archive_and_tile_suffixes_promote_direct_assets_for_parser_review(self) -> None:
        cases = [
            ("Shapefile ZIP", "https://data.example.test/gis/boundaries.shp.zip", "shapefile", ".shp.zip"),
            ("FlatGeobuf", "https://data.example.test/gis/roads.fgb", "flatgeobuf", ".fgb"),
            ("PMTiles", "https://data.example.test/gis/basemap.pmtiles", "pmtiles", ".pmtiles"),
            ("MBTiles", "https://data.example.test/gis/offline.mbtiles", "mbtiles", ".mbtiles"),
        ]

        for name, url, expected_format, expected_suffix in cases:
            with self.subTest(source_format=expected_format):
                entry = ckan_review_entry()
                metadata = entry["dataset_version"]["metadata"]
                metadata["resources"] = [{"name": name, "downloadURL": url, "byteSize": 4096}]
                metadata.pop("links", None)

                resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

                self.assertEqual(1, result.direct_entries_added)
                resolved_entry = resolved["providers"][0]
                self.assertEqual(url, resolved_entry["download_url"])
                self.assertEqual(expected_format, resolved_entry["source_format"])
                self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
                self.assertEqual("geospatial_asset_review", resolved_entry["content_parser"]["parser_id"])
                self.assertEqual("content_parser_required", resolved_entry["content_parser"]["review_bucket"])
                self.assertTrue(resolved_entry["target_path"].endswith(expected_suffix))

    def test_sqlite_url_suffix_promotes_direct_asset_for_database_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "SQLite catalog",
                "downloadURL": "https://data.example.test/database/catalog.sqlite3",
                "byteSize": 4096,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/database/catalog.sqlite3", resolved_entry["download_url"])
        self.assertEqual("sqlite", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertEqual("database_snapshot_review", resolved_entry["content_parser"]["parser_id"])
        self.assertEqual("content_parser_required", resolved_entry["content_parser"]["review_bucket"])
        self.assertTrue(resolved_entry["target_path"].endswith(".sqlite3"))

    def test_dcat_distribution_object_promotes_direct_json_entry(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata.pop("resources", None)
        metadata.pop("links", None)
        metadata["distribution"] = {
            "name": "DCAT distribution JSON",
            "encodingFormat": "application/json",
            "downloadURL": {"@id": "https://data.example.test/distribution/sample.json"},
            "byteSize": {"@value": "4096"},
        }

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/distribution/sample.json", resolved_entry["download_url"])
        self.assertEqual("json", resolved_entry["source_format"])
        self.assertEqual("json_to_sqlite", resolved_entry["import_plan"]["importer"])
        self.assertEqual(4096, resolved_entry["adapter_resolution"]["resource_size_bytes"])

    def test_namespaced_dcat_distribution_promotes_extensionless_csv_entry(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata.pop("resources", None)
        metadata.pop("links", None)
        metadata["dcat:distribution"] = {
            "name": "Namespaced DCAT distribution",
            "dct:format": {"@value": "text/csv"},
            "dcat:downloadURL": {"@id": "https://data.example.test/download?id=namespaced"},
            "dcat:byteSize": {"@value": "2048"},
        }

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/download?id=namespaced", resolved_entry["download_url"])
        self.assertEqual("csv", resolved_entry["source_format"])
        self.assertEqual("csv_to_sqlite", resolved_entry["import_plan"]["importer"])
        self.assertEqual("text/csv", resolved_entry["adapter_resolution"]["resource_format"])
        self.assertEqual(2048, resolved_entry["adapter_resolution"]["resource_size_bytes"])

    def test_jsonld_graph_promotes_downloadable_distribution_node(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata.pop("resources", None)
        metadata.pop("links", None)
        metadata["@graph"] = [
            {
                "@id": "https://data.example.test/dataset/sample",
                "@type": "dcat:Dataset",
                "accessURL": "https://data.example.test/catalog/sample",
            },
            {
                "@id": "https://data.example.test/dataset/sample#csv",
                "@type": "dcat:Distribution",
                "name": "Graph CSV distribution",
                "dcat:downloadURL": {"@id": "https://data.example.test/download?id=graph-csv"},
                "dct:format": {"@value": "text/csv"},
                "dcat:byteSize": {"@value": "2048"},
            },
        ]

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/download?id=graph-csv", resolved_entry["download_url"])
        self.assertEqual("csv", resolved_entry["source_format"])
        self.assertEqual("csv_to_sqlite", resolved_entry["import_plan"]["importer"])
        self.assertEqual("text/csv", resolved_entry["adapter_resolution"]["resource_format"])
        self.assertEqual(2048, resolved_entry["adapter_resolution"]["resource_size_bytes"])

    def test_direct_link_object_without_url_stays_in_review(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {
                "name": "Catalog distribution",
                "format": "text/csv",
                "downloadURL": {"label": "CSV download"},
                "byteSize": 2048,
            }
        ]
        metadata.pop("links", None)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(0, result.direct_entries_added)
        self.assertEqual(1, result.unresolved_review_entries)
        self.assertIn("adapter_review", resolved["providers"][0])

    def test_datacite_doi_lookup_promotes_content_url_resource(self) -> None:
        entry = datacite_doi_review_entry()

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=datacite_doi_payload()) as fetch:
            resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        fetch.assert_called_once_with("https://api.datacite.example.test/dois/10.1234%2Fexample.dataset")
        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("datacite_doi_content_url_resolver", resolved_entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("single_datacite_doi_metadata_content_url_lookup", resolved_entry["adapter_resolution"]["policy"])
        self.assertEqual("https://data.example.test/cloud/cloud_sample.nc", resolved_entry["download_url"])
        self.assertEqual("netcdf", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertNotIn("adapter_review", resolved_entry)

    def test_openalex_doi_lookup_uses_datacite_metadata_content_url(self) -> None:
        entry = openalex_work_review_entry()

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=datacite_doi_payload()) as fetch:
            resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        fetch.assert_called_once_with("https://api.datacite.org/dois/10.1163%2Fexample")
        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("datacite_doi_content_url_resolver", resolved_entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("https://data.example.test/cloud/cloud_sample.nc", resolved_entry["download_url"])

    def test_datacite_doi_lookup_without_content_url_stays_in_review(self) -> None:
        entry = datacite_doi_review_entry()

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=datacite_doi_payload(content_url="")):
            resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(0, result.direct_entries_added)
        self.assertEqual(1, result.unresolved_review_entries)
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

    def test_ogc_records_metadata_links_stay_in_adapter_review(self) -> None:
        entry = ogc_records_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["links"] = [
            {
                "rel": "self",
                "type": "application/geo+json",
                "href": "https://records.example.test/items/cloud-raster-record.geojson",
            },
            {
                "rel": "alternate",
                "type": "text/html",
                "href": "https://records.example.test/catalog/cloud-raster-record",
            },
        ]

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(0, result.direct_entries_added)
        self.assertEqual(1, result.unresolved_review_entries)
        self.assertEqual(1, resolved["summary"]["review_required_count"])
        self.assertIn("adapter_review", resolved["providers"][0])
        self.assertIn("resources=2", result.warnings[0])

    def test_ogc_records_data_link_can_promote_direct_geojson_entry(self) -> None:
        entry = ogc_records_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["links"] = [
            {
                "rel": "self",
                "type": "application/geo+json",
                "href": "https://records.example.test/items/cloud-raster-record.geojson",
            },
            {
                "rel": "data",
                "type": "application/geo+json",
                "href": "https://data.example.test/cloud-raster-sample.geojson",
            },
        ]

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/cloud-raster-sample.geojson", resolved_entry["download_url"])
        self.assertEqual("geojson", resolved_entry["source_format"])
        self.assertEqual("json_to_sqlite", resolved_entry["import_plan"]["importer"])

    def test_ckan_package_show_api_promotes_direct_resource_entry(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata.pop("resources", None)
        metadata.pop("links", None)
        metadata["ckan_id"] = "ocean-buoy-observations"

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=ckan_package_show_payload()) as fetch:
            resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        fetch.assert_called_once_with("https://api.example.test/action/package_show?id=ocean-buoy-observations")
        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("ckan_package_show_resource_resolver", resolved_entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("https://api.example.test/files/buoy.csv", resolved_entry["download_url"])
        self.assertEqual("csv", resolved_entry["source_format"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])

    def test_ckan_package_search_url_can_be_turned_into_package_show_lookup(self) -> None:
        entry = ckan_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata.pop("resources", None)
        metadata.pop("links", None)
        entry["adapter_review"]["source_url"] = "https://api.example.test/action/package_search"
        entry["dataset_version"]["download_url"] = "https://api.example.test/action/package_search"

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=ckan_package_show_payload()) as fetch:
            resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        fetch.assert_called_once_with("https://api.example.test/action/package_show?id=ocean-buoy-observations")
        self.assertEqual(1, result.direct_entries_added)
        self.assertEqual("https://api.example.test/files/buoy.csv", resolved["providers"][0]["download_url"])

    def test_dataverse_latest_version_promotes_small_csv_file_entry(self) -> None:
        plan = {"providers": [dataverse_review_entry()]}

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=dataverse_latest_version_payload()) as fetch:
            resolved, result = resolve_adapter_review_plan_payload(plan)

        fetch.assert_called_once_with(
            "https://dataverse.example.test/api/datasets/:persistentId/versions/:latest?persistentId=doi%3A10.7910%2FDVN%2FABC123"
        )
        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("dataverse_latest_version_file_resolver", entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("https://dataverse.example.test/api/access/datafile/12345", entry["download_url"])
        self.assertEqual("csv", entry["source_format"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual(4096, entry["adapter_resolution"]["resource_size_bytes"])
        self.assertTrue(entry["target_path"].endswith(".csv"))
        self.assertNotIn("adapter_review", entry)

    def test_dataverse_oversized_or_restricted_files_stay_in_adapter_review(self) -> None:
        payload = {
            "data": {
                "files": [
                    {
                        "restricted": True,
                        "dataFile": {
                            "id": 1,
                            "filename": "secret.csv",
                            "contentType": "text/csv",
                            "filesize": 1024,
                        },
                    },
                    {
                        "dataFile": {
                            "id": 2,
                            "filename": "huge.csv",
                            "contentType": "text/csv",
                            "filesize": 250_000_000,
                        },
                    },
                ]
            }
        }

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=payload):
            resolved, result = resolve_adapter_review_plan_payload({"providers": [dataverse_review_entry()]})

        self.assertEqual(0, result.direct_entries_added)
        self.assertEqual(1, result.unresolved_review_entries)
        self.assertIn("adapter_review", resolved["providers"][0])

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

    def test_cmr_collection_metadata_promotes_bounded_granule_metadata_sample_entry(self) -> None:
        plan = {"providers": [cmr_review_entry()]}

        resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("cmr_bounded_granule_search_resolver", entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual(
            "https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id=C1234567890-POCLOUD&page_size=1",
            entry["download_url"],
        )
        self.assertEqual("json", entry["source_format"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("json_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual("C1234567890-POCLOUD", entry["adapter_resolution"]["cmr_concept_id"])
        self.assertEqual(1, entry["adapter_resolution"]["sample_limit"])
        self.assertTrue(entry["target_path"].endswith(".json"))
        self.assertNotIn("adapter_review", entry)

    def test_cmr_metadata_links_stay_in_adapter_review(self) -> None:
        entry = cmr_granule_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["links"] = [
            {
                "rel": "http://esipfed.org/ns/fedsearch/1.1/metadata#",
                "type": "application/json",
                "href": "https://cmr.earthdata.nasa.gov/search/concepts/G1234567890-POCLOUD.json",
            },
            {
                "rel": "http://esipfed.org/ns/fedsearch/1.1/documentation#",
                "type": "text/html",
                "href": "https://earthdata.example.test/granules/G1234567890-POCLOUD",
            },
        ]

        with patch("api_launcher.adapter_plan_resolver.fetch_json", side_effect=AssertionError("unexpected fetch")):
            resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(0, result.direct_entries_added)
        self.assertEqual(1, result.unresolved_review_entries)
        self.assertEqual(1, resolved["summary"]["review_required_count"])
        self.assertIn("adapter_review", resolved["providers"][0])
        self.assertIn("resources=2", result.warnings[0])

    def test_cmr_data_link_can_promote_direct_asset_entry(self) -> None:
        entry = cmr_granule_review_entry()
        metadata = entry["dataset_version"]["metadata"]
        metadata["links"] = [
            {
                "rel": "http://esipfed.org/ns/fedsearch/1.1/metadata#",
                "type": "application/json",
                "href": "https://cmr.earthdata.nasa.gov/search/concepts/G1234567890-POCLOUD.json",
            },
            {
                "rel": "http://esipfed.org/ns/fedsearch/1.1/data#",
                "title": "NetCDF granule asset",
                "type": "application/x-netcdf",
                "href": "https://data.example.test/granules/S6A_P4_2__LR_STD__sample.nc",
                "size": 4096,
            },
        ]

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("direct_download", resolved_entry["download_eligibility"]["status"])
        self.assertEqual(
            "https://data.example.test/granules/S6A_P4_2__LR_STD__sample.nc",
            resolved_entry["download_url"],
        )
        self.assertEqual("netcdf", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertEqual("netcdf", resolved_entry["content_detection"]["source_format"])
        self.assertEqual("scientific_grid_review", resolved_entry["content_parser"]["parser_id"])
        self.assertEqual("content_parser_required", resolved_entry["content_parser"]["review_bucket"])
        self.assertEqual("generic_resource_direct_download_resolver", resolved_entry["adapter_resolution"]["resolver_id"])
        self.assertNotIn("adapter_review", resolved_entry)

    def test_cmr_granule_concept_lookup_promotes_explicit_data_asset(self) -> None:
        entry = cmr_granule_review_entry()

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=cmr_granule_concept_payload()) as fetch:
            resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        fetch.assert_called_once_with("https://cmr.earthdata.nasa.gov/search/concepts/G1234567890-POCLOUD.json")
        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("cmr_granule_asset_link_resolver", resolved_entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("explicit_cmr_granule_data_links_under_size_limit", resolved_entry["adapter_resolution"]["policy"])
        self.assertEqual("direct_download", resolved_entry["download_eligibility"]["status"])
        self.assertEqual("https://data.example.test/granules/S6A_P4_2__LR_STD__sample", resolved_entry["download_url"])
        self.assertEqual("netcdf", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertNotIn("adapter_review", resolved_entry)

    def test_cmr_granule_concept_lookup_skips_oversized_data_asset(self) -> None:
        entry = cmr_granule_review_entry()
        payload = cmr_granule_concept_payload(size_bytes=250_000_000)

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=payload):
            resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(0, result.direct_entries_added)
        self.assertEqual(1, result.unresolved_review_entries)
        self.assertIn("adapter_review", resolved["providers"][0])

    def test_socrata_resource_url_promotes_bounded_json_sample_entry(self) -> None:
        plan = {"providers": [socrata_review_entry("https://data.example.test/resource/abcd-1234.json?$select=name")]}

        resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("socrata_bounded_sample_query_resolver", entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("https://data.example.test/resource/abcd-1234.json?$select=name&$limit=25", entry["download_url"])
        self.assertEqual("json", entry["source_format"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("json_to_sqlite", entry["import_plan"]["importer"])
        self.assertTrue(entry["target_path"].endswith(".json"))
        self.assertNotIn("adapter_review", entry)

    def test_socrata_api_view_url_promotes_resource_json_sample(self) -> None:
        plan = {"providers": [socrata_review_entry("https://data.example.test/api/views/abcd-1234")]}

        with patch("api_launcher.adapter_plan_resolver.fetch_json", side_effect=AssertionError("unexpected fetch")):
            resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/resource/abcd-1234.json?$limit=25", entry["download_url"])
        self.assertEqual("abcd-1234", entry["adapter_resolution"]["socrata_dataset_id"])
        self.assertEqual(25, entry["adapter_resolution"]["sample_limit"])

    def test_socrata_domain_metadata_promotes_resource_json_sample(self) -> None:
        plan = {"providers": [socrata_review_entry("")]}

        resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("https://data.example.test/resource/abcd-1234.json?$limit=25", entry["download_url"])
        self.assertEqual("socrata_bounded_sample_query_resolver", entry["adapter_resolution"]["resolver_id"])

    def test_socrata_resource_metadata_is_bounded_before_direct_download(self) -> None:
        entry = socrata_review_entry("")
        metadata = entry["dataset_version"]["metadata"]
        metadata["resources"] = [
            {"name": "SODA JSON API", "format": "JSON", "url": "https://data.example.test/resource/abcd-1234.json"}
        ]

        resolved, result = resolve_adapter_review_plan_payload({"providers": [entry]})

        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("socrata_bounded_sample_query_resolver", resolved_entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("https://data.example.test/resource/abcd-1234.json?$limit=25", resolved_entry["download_url"])

    def test_ncei_dataset_search_promotes_bounded_data_search_sample(self) -> None:
        plan = {"providers": [ncei_review_entry("https://www.ncei.noaa.gov/access/services/search/v1/datasets?limit=5&available=true&text=ais")]}

        resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("ncei_bounded_search_query_resolver", entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual(
            "https://www.ncei.noaa.gov/access/services/search/v1/data?dataset=automatic-identification-system-ais&limit=25&offset=0",
            entry["download_url"],
        )
        self.assertEqual("json", entry["source_format"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("json_to_sqlite", entry["import_plan"]["importer"])
        self.assertTrue(entry["target_path"].endswith(".json"))
        self.assertNotIn("adapter_review", entry)

    def test_ncei_data_search_url_is_limited_to_small_json_sample(self) -> None:
        plan = {
            "providers": [
                ncei_review_entry(
                    "https://www.ncei.noaa.gov/access/services/search/v1/data?dataset=global-hourly&datatypes=TMP&limit=500&offset=90"
                )
            ]
        }

        resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual(
            "https://www.ncei.noaa.gov/access/services/search/v1/data?dataset=global-hourly&dataTypes=TMP&limit=25&offset=0",
            entry["download_url"],
        )
        self.assertEqual("data", entry["adapter_resolution"]["endpoint_kind"])
        self.assertEqual(25, entry["adapter_resolution"]["sample_limit"])

    def test_ncei_data_search_lookup_promotes_small_direct_file(self) -> None:
        plan = {
            "providers": [
                ncei_review_entry(
                    "https://www.ncei.noaa.gov/access/services/search/v1/data"
                    "?dataset=daily-summaries&stations=USW00013880&startDate=2024-01-01"
                    "&endDate=2024-01-03&dataTypes=TMAX&limit=999"
                )
            ]
        }

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=ncei_search_data_file_payload()) as fetch:
            resolved, result = resolve_adapter_review_plan_payload(plan)

        fetch.assert_called_once_with(
            "https://www.ncei.noaa.gov/access/services/search/v1/data"
            "?dataset=daily-summaries&stations=USW00013880&startDate=2024-01-01"
            "&endDate=2024-01-03&dataTypes=TMAX&limit=1&offset=0"
        )
        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("ncei_search_data_file_resolver", entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("single_bounded_ncei_search_data_file_under_size_limit", entry["adapter_resolution"]["policy"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("https://www.ncei.noaa.gov/data/daily-summaries/access/USW00013880.csv", entry["download_url"])
        self.assertEqual("csv", entry["source_format"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual(13_912_122, entry["adapter_resolution"]["resource_size_bytes"])
        self.assertTrue(entry["target_path"].endswith(".csv"))
        self.assertNotIn("adapter_review", entry)

    def test_ncei_data_search_lookup_skips_oversized_direct_file(self) -> None:
        plan = {
            "providers": [
                ncei_review_entry(
                    "https://www.ncei.noaa.gov/access/services/search/v1/data"
                    "?dataset=daily-summaries&stations=USW00013880&startDate=2024-01-01"
                    "&endDate=2024-01-03&dataTypes=TMAX"
                )
            ]
        }

        with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=ncei_search_data_file_payload(file_size=250_000_000)):
            resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("ncei_bounded_search_query_resolver", entry["adapter_resolution"]["resolver_id"])
        self.assertEqual(
            "https://www.ncei.noaa.gov/access/services/search/v1/data?dataset=daily-summaries&stations=USW00013880&startDate=2024-01-01&endDate=2024-01-03&dataTypes=TMAX&limit=25&offset=0",
            entry["download_url"],
        )
        self.assertEqual("json", entry["source_format"])

    def test_ncei_access_data_query_promotes_bounded_sample_entry(self) -> None:
        plan = {
            "providers": [
                ncei_access_data_review_entry(
                    "https://www.ncei.noaa.gov/access/services/data/v1"
                    "?dataset=daily-summaries&stations=USW00094728&startDate=2024-01-01"
                    "&endDate=2024-01-03&dataTypes=TMAX&format=csv&limit=999&unexpected=yes"
                )
            ]
        }

        resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(1, result.resolved_review_entries)
        self.assertEqual(0, result.unresolved_review_entries)
        self.assertEqual(1, result.direct_entries_added)
        entry = resolved["providers"][0]
        self.assertEqual("ncei_bounded_access_data_query_resolver", entry["adapter_resolution"]["resolver_id"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual(
            "https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00094728&startDate=2024-01-01&endDate=2024-01-03&dataTypes=TMAX&format=csv",
            entry["download_url"],
        )
        self.assertEqual("csv", entry["source_format"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual(["stations"], entry["adapter_resolution"]["bounds"]["spatial_keys"])
        self.assertEqual(2, entry["adapter_resolution"]["bounds"]["days"])
        self.assertTrue(entry["target_path"].endswith(".csv"))
        self.assertNotIn("adapter_review", entry)

    def test_unbounded_ncei_access_data_query_stays_in_adapter_review(self) -> None:
        plan = {
            "providers": [
                ncei_access_data_review_entry(
                    "https://www.ncei.noaa.gov/access/services/data/v1"
                    "?dataset=daily-summaries&startDate=2024-01-01&endDate=2024-02-01&format=json"
                )
            ]
        }

        resolved, result = resolve_adapter_review_plan_payload(plan)

        self.assertEqual(0, result.direct_entries_added)
        self.assertEqual(1, result.unresolved_review_entries)
        self.assertEqual(1, resolved["summary"]["review_required_count"])
        self.assertIn("adapter_review", resolved["providers"][0])

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

            with patch("api_launcher.core.log_event") as log_event_mock, redirect_stdout(output):
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
            self.assertEqual("adapter_plan_resolved", log_event_mock.call_args.args[0])
            self.assertEqual(1, log_event_mock.call_args.kwargs["context"]["direct_entries_added"])

        self.assertEqual(0, rc)
        self.assertIn("[adapter-resolve] wrote", output.getvalue())
        self.assertEqual(1, payload["summary"]["direct_download_count"])
        self.assertEqual(1, payload["adapter_resolution"]["direct_entries_added"])

    def test_cli_emits_resolved_adapter_plan_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "candidate_plan.json"
            output_path = Path(tmpdir) / "candidate_plan.resolved.json"
            input_path.write_text(json.dumps({"providers": [ckan_review_entry()]}), encoding="utf-8")
            output = io.StringIO()

            with patch("api_launcher.core.log_event"), redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(Path(tmpdir) / "launcher.sqlite"),
                        "--resolve-adapter-plan",
                        str(input_path),
                        "--write-resolved-adapter-plan",
                        str(output_path),
                        "--resolve-adapter-plan-json",
                    ]
                )

            summary = json.loads(output.getvalue())

        self.assertEqual(0, rc)
        self.assertEqual(str(output_path), summary["output_path"])
        self.assertEqual(1, summary["direct_entries_added"])
        self.assertEqual(1, summary["plan_summary"]["direct_download_count"])
        self.assertNotIn("[adapter-resolve]", output.getvalue())

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


def ogc_records_review_entry() -> dict[str, object]:
    return {
        "provider_id": "wmo_wis2_gdc",
        "name": "WMO WIS2 Global Discovery Catalogue",
        "dataset_uid": "wmo_wis2_gdc:cloud-raster-record",
        "dataset_id": "cloud-raster-record",
        "dataset_title": "Global satellite cloud raster archive",
        "categories": ["wmo", "wis2", "ogc_api_records", "weather"],
        "geographic_scope": "global",
        "source_format": "ogc_record",
        "download_eligibility": {"status": "adapter_required", "reason": "OGC record links must be reviewed first"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "wmo_wis2_cloud_raster_record"},
        "dataset_version": {
            "dataset_uid": "wmo_wis2_gdc:cloud-raster-record",
            "dataset_id": "cloud-raster-record",
            "label": "discovered",
            "version": "discovered",
            "version_status": "unknown",
            "download_url": "https://records.example.test/collections/wis2-discovery-metadata/items?limit=1&q=cloud",
            "landing_url": "https://records.example.test/catalog/cloud-raster-record",
            "metadata": {
                "native_format": "ogc_record",
                "data_family": "raster_or_grid",
                "discovery_source_type": "ogc_api_records",
                "source_url": "https://records.example.test/collections/wis2-discovery-metadata/items?limit=1&q=cloud",
            },
        },
        "adapter_review": {
            "adapter_id": "wmo_wis2_gdc_adapter",
            "source_url": "https://records.example.test/collections/wis2-discovery-metadata/items?limit=1&q=cloud",
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


def dataverse_review_entry() -> dict[str, object]:
    return {
        "provider_id": "harvard_dataverse",
        "name": "Harvard Dataverse",
        "dataset_uid": "harvard_dataverse:doi_10.7910_dvn_abc123",
        "dataset_id": "doi_10.7910_dvn_abc123",
        "dataset_title": "Example Dataverse dataset",
        "categories": ["dataverse", "research_data"],
        "geographic_scope": "global",
        "download_eligibility": {"status": "adapter_required", "reason": "Dataverse files must be selected first"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "harvard_dataverse_example"},
        "dataset_version": {
            "dataset_uid": "harvard_dataverse:doi_10.7910_dvn_abc123",
            "dataset_id": "doi_10.7910_dvn_abc123",
            "label": "discovered",
            "version": "1.0",
            "version_status": "unknown",
            "download_url": "https://dataverse.example.test/dataset.xhtml?persistentId=doi:10.7910/DVN/ABC123",
            "landing_url": "https://dataverse.example.test/dataset.xhtml?persistentId=doi:10.7910/DVN/ABC123",
            "metadata": {
                "native_format": "dataverse_dataset",
                "data_family": "table",
                "discovery_source_type": "dataverse_search",
                "source_url": "https://dataverse.example.test/api/search?q=ocean&type=dataset",
                "global_id": "doi:10.7910/DVN/ABC123",
                "file_count": 2,
            },
        },
        "adapter_review": {
            "adapter_id": "harvard_dataverse_adapter",
            "source_url": "https://dataverse.example.test/dataset.xhtml?persistentId=doi:10.7910/DVN/ABC123",
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


def cmr_review_entry() -> dict[str, object]:
    return {
        "provider_id": "nasa_earthdata",
        "name": "NASA Earthdata",
        "dataset_uid": "nasa_earthdata:sentinel_6_jason_cs_s6a",
        "dataset_id": "sentinel_6_jason_cs_s6a",
        "dataset_title": "Sentinel-6 Jason-CS L2 Sea Surface Height",
        "categories": ["nasa", "cmr", "satellite", "earth_observation"],
        "geographic_scope": "global",
        "download_eligibility": {"status": "adapter_required", "reason": "CMR granule search must be bounded first"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "nasa_earthdata_sentinel_6"},
        "dataset_version": {
            "dataset_uid": "nasa_earthdata:sentinel_6_jason_cs_s6a",
            "dataset_id": "sentinel_6_jason_cs_s6a",
            "label": "discovered",
            "version": "discovered",
            "version_status": "unknown",
            "download_url": "https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id=C1234567890-POCLOUD",
            "landing_url": "https://cmr.earthdata.nasa.gov/search/concepts/C1234567890-POCLOUD.html",
            "metadata": {
                "native_format": "cmr_collection",
                "data_family": "raster_or_grid",
                "discovery_source_type": "cmr_collections",
                "source_url": "https://cmr.earthdata.nasa.gov/search/collections.json?keyword=altimetry&page_size=10",
                "cmr_concept_id": "C1234567890-POCLOUD",
            },
        },
        "adapter_review": {
            "adapter_id": "nasa_earthdata_cmr_adapter",
            "source_url": "https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id=C1234567890-POCLOUD",
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


def cmr_granule_review_entry() -> dict[str, object]:
    return {
        "provider_id": "nasa_earthdata",
        "name": "NASA Earthdata",
        "dataset_uid": "nasa_earthdata:s6a_granule_sample",
        "dataset_id": "s6a_granule_sample",
        "dataset_title": "Sentinel-6 Jason-CS sample granule",
        "categories": ["nasa", "cmr", "satellite", "earth_observation"],
        "geographic_scope": "global",
        "source_format": "cmr_granule",
        "download_eligibility": {"status": "adapter_required", "reason": "CMR granule links must be selected first"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "nasa_earthdata_s6a_granule"},
        "dataset_version": {
            "dataset_uid": "nasa_earthdata:s6a_granule_sample",
            "dataset_id": "s6a_granule_sample",
            "label": "discovered granule",
            "version": "discovered",
            "version_status": "unknown",
            "download_url": "https://cmr.earthdata.nasa.gov/search/concepts/G1234567890-POCLOUD.json",
            "landing_url": "https://cmr.earthdata.nasa.gov/search/concepts/G1234567890-POCLOUD.html",
            "metadata": {
                "native_format": "cmr_granule",
                "data_family": "raster_or_grid",
                "discovery_source_type": "cmr_granules",
                "source_url": "https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id=C1234567890-POCLOUD&page_size=1",
                "granule_concept_id": "G1234567890-POCLOUD",
            },
        },
        "adapter_review": {
            "adapter_id": "nasa_earthdata_cmr_adapter",
            "source_url": "https://cmr.earthdata.nasa.gov/search/concepts/G1234567890-POCLOUD.json",
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


def cmr_granule_concept_payload(size_bytes: int = 4096) -> dict[str, object]:
    return {
        "concept-id": "G1234567890-POCLOUD",
        "links": [
            {
                "rel": "http://esipfed.org/ns/fedsearch/1.1/metadata#",
                "type": "application/json",
                "href": "https://cmr.earthdata.nasa.gov/search/concepts/G1234567890-POCLOUD.json",
            },
            {
                "rel": "http://esipfed.org/ns/fedsearch/1.1/data#",
                "title": "Sentinel-6 sample NetCDF",
                "type": "application/x-netcdf",
                "href": "https://data.example.test/granules/S6A_P4_2__LR_STD__sample",
                "sizeInBytes": size_bytes,
            },
        ],
    }


def socrata_review_entry(source_url: str) -> dict[str, object]:
    return {
        "provider_id": "socrata_demo",
        "name": "Socrata Demo",
        "dataset_uid": "socrata_demo:abcd-1234",
        "dataset_id": "abcd-1234",
        "dataset_title": "Socrata sample permits",
        "categories": ["open_data", "socrata"],
        "geographic_scope": "city",
        "download_eligibility": {"status": "adapter_required", "reason": "SODA query must be bounded first"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "socrata_demo_abcd_1234"},
        "dataset_version": {
            "dataset_uid": "socrata_demo:abcd-1234",
            "dataset_id": "abcd-1234",
            "label": "discovered",
            "version": "discovered",
            "version_status": "unknown",
            "download_url": source_url,
            "landing_url": "https://data.example.test/d/GHIJ-5678",
            "metadata": {
                "native_format": "socrata",
                "data_family": "table",
                "socrata_dataset_id": "abcd-1234",
                "socrata_domain": "data.example.test",
            },
        },
        "adapter_review": {
            "adapter_id": "socrata_demo_adapter",
            "source_url": source_url,
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


def ncei_review_entry(source_url: str) -> dict[str, object]:
    return {
        "provider_id": "noaa_ncei_access_data",
        "name": "NOAA NCEI Common Access Search Service",
        "dataset_uid": "noaa_ncei_access_data:automatic-identification-system-ais",
        "dataset_id": "automatic-identification-system-ais",
        "dataset_title": "Automatic Identification System (AIS) Vessel Traffic Data",
        "categories": ["noaa", "catalog", "metadata"],
        "geographic_scope": "global/us",
        "download_eligibility": {"status": "adapter_required", "reason": "NCEI search query must be bounded first"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "noaa_ncei_access_data_ais"},
        "dataset_version": {
            "dataset_uid": "noaa_ncei_access_data:automatic-identification-system-ais",
            "dataset_id": "automatic-identification-system-ais",
            "label": "discovered",
            "version": "discovered",
            "version_status": "unknown",
            "download_url": source_url,
            "landing_url": "https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C01591/html",
            "metadata": {
                "native_format": "ncei_search",
                "data_family": "spatiotemporal_trajectory",
                "discovery_source_type": "ncei_search",
                "source_url": source_url,
                "ncei_result_id": "automatic-identification-system-ais",
                "ncei_file_id": "gov.noaa.ncdc:C01591",
            },
        },
        "adapter_review": {
            "adapter_id": "noaa_ncei_search_adapter",
            "source_url": source_url,
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


def ncei_access_data_review_entry(source_url: str) -> dict[str, object]:
    return {
        "provider_id": "noaa_ncei_access_data",
        "name": "NOAA NCEI Access Data Service",
        "dataset_uid": "noaa_ncei_access_data:daily-summaries",
        "dataset_id": "daily-summaries",
        "dataset_title": "Daily Summaries",
        "categories": ["noaa", "weather", "observations"],
        "geographic_scope": "global/us",
        "download_eligibility": {"status": "adapter_required", "reason": "NCEI data query must be bounded first"},
        "import_plan": {"status": "adapter_review_required", "table_hint": "noaa_ncei_daily_summaries"},
        "dataset_version": {
            "dataset_uid": "noaa_ncei_access_data:daily-summaries",
            "dataset_id": "daily-summaries",
            "label": "bounded station sample",
            "version": "discovered",
            "version_status": "unknown",
            "download_url": source_url,
            "landing_url": "https://www.ncei.noaa.gov/access/search/data-search/daily-summaries",
            "metadata": {
                "native_format": "ncei_access_data",
                "data_family": "timeseries",
                "ncei_dataset_id": "daily-summaries",
            },
        },
        "adapter_review": {
            "adapter_id": "noaa_ncei_access_data_adapter",
            "source_url": source_url,
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


def ncei_search_data_file_payload(file_size: int = 13_912_122) -> dict[str, object]:
    return {
        "count": 1,
        "totalFileSize": file_size,
        "results": [
            {
                "id": "daily-summaries-latest.tar.gz:USW00013880.csv",
                "name": "USW00013880.csv",
                "filePath": "/data/daily-summaries/access/USW00013880.csv",
                "fileSize": file_size,
                "tar": "daily-summaries-latest.tar.gz",
                "startDate": "1937-03-01T00:00:00",
                "endDate": "2026-05-16T23:59:59",
            }
        ],
    }


def datacite_doi_review_entry() -> dict[str, object]:
    return {
        "provider_id": "datacite",
        "name": "DataCite DOI Search",
        "dataset_uid": "datacite:10.1234_example.dataset",
        "dataset_id": "10.1234_example.dataset",
        "dataset_title": "Global cloud imagery training dataset",
        "categories": ["doi", "research_data", "metadata"],
        "geographic_scope": "global",
        "download_eligibility": {
            "status": "adapter_required",
            "reason": "DOI/OpenAlex research metadata points at a repository landing page or API record",
        },
        "import_plan": {"status": "adapter_review_required", "table_hint": "datacite_10_1234_example_dataset"},
        "dataset_version": {
            "dataset_uid": "datacite:10.1234_example.dataset",
            "dataset_id": "10.1234_example.dataset",
            "label": "discovered",
            "version": "2026",
            "version_status": "unknown",
            "download_url": "https://api.datacite.example.test/dois/10.1234%2Fexample.dataset",
            "landing_url": "https://doi.org/10.1234/example.dataset",
            "metadata": {
                "native_format": "datacite_doi",
                "data_family": "raster_or_grid",
                "discovery_source_type": "datacite_dois",
                "doi": "10.1234/example.dataset",
            },
        },
        "adapter_review": {
            "adapter_id": "datacite_adapter",
            "source_url": "https://api.datacite.example.test/dois/10.1234%2Fexample.dataset",
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


def openalex_work_review_entry() -> dict[str, object]:
    return {
        "provider_id": "openalex",
        "name": "OpenAlex",
        "dataset_uid": "openalex:10.1163_example",
        "dataset_id": "10.1163_example",
        "dataset_title": "OpenAlex dataset work",
        "categories": ["research_metadata", "openalex"],
        "geographic_scope": "global",
        "download_eligibility": {
            "status": "adapter_required",
            "reason": "DOI/OpenAlex research metadata points at a repository landing page or API record",
        },
        "import_plan": {"status": "adapter_review_required", "table_hint": "openalex_10_1163_example"},
        "dataset_version": {
            "dataset_uid": "openalex:10.1163_example",
            "dataset_id": "10.1163_example",
            "label": "discovered",
            "version": "2026-05-01",
            "version_status": "unknown",
            "download_url": "https://api.openalex.org/works/W1650569836",
            "landing_url": "https://doi.org/10.1163/example",
            "metadata": {
                "native_format": "openalex_work",
                "data_family": "document_or_metadata",
                "discovery_source_type": "openalex_works_search",
                "doi": "https://doi.org/10.1163/example",
                "openalex_id": "https://openalex.org/W1650569836",
            },
        },
        "adapter_review": {
            "adapter_id": "openalex_adapter",
            "source_url": "https://api.openalex.org/works/W1650569836",
            "required_action": "resolve_source_to_direct_download_entries",
        },
    }


def datacite_doi_payload(content_url: str = "https://data.example.test/cloud/cloud_sample.nc") -> dict[str, object]:
    attributes: dict[str, object] = {
        "doi": "10.1234/example.dataset",
        "titles": [{"title": "Global cloud imagery training dataset"}],
        "formats": ["NetCDF"],
    }
    if content_url:
        attributes["contentUrl"] = content_url
    return {"data": {"id": "10.1234/example.dataset", "type": "dois", "attributes": attributes}}


def ckan_package_show_payload() -> dict[str, object]:
    return {
        "success": True,
        "result": {
            "id": "pkg-1",
            "name": "ocean-buoy-observations",
            "resources": [
                {
                    "id": "res-1",
                    "name": "Hourly buoy CSV",
                    "format": "CSV",
                    "mimetype": "text/csv",
                    "url": "https://api.example.test/files/buoy.csv",
                    "size": 2048,
                },
                {
                    "id": "res-2",
                    "name": "Documentation page",
                    "format": "HTML",
                    "url": "https://api.example.test/dataset/ocean-buoy-observations",
                },
            ],
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


def dataverse_latest_version_payload() -> dict[str, object]:
    return {
        "status": "OK",
        "data": {
            "id": 99,
            "versionNumber": 1,
            "versionMinorNumber": 0,
            "files": [
                {
                    "label": "observations.csv",
                    "restricted": False,
                    "dataFile": {
                        "id": 12345,
                        "filename": "observations.csv",
                        "contentType": "text/csv",
                        "filesize": 4096,
                        "persistentId": "doi:10.7910/DVN/ABC123/FILE1",
                    },
                },
                {
                    "label": "readme.html",
                    "restricted": False,
                    "dataFile": {
                        "id": 23456,
                        "filename": "readme.html",
                        "contentType": "text/html",
                        "filesize": 2048,
                    },
                },
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
