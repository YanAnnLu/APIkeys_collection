from __future__ import annotations

import unittest

from api_launcher.content_registry import content_parser_capability, detect_content_format, normalize_content_format
from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.downloads.eligibility import DownloadEligibility
from api_launcher.models import Dataset
from api_launcher.plans import dataset_import_plan_entry


class ContentRegistryTest(unittest.TestCase):
    def test_detector_uses_hints_and_url_suffix_for_netcdf(self) -> None:
        detection = detect_content_format(
            url="https://example.test/ocean/sample.nc",
            media_type="application/x-netcdf",
            format_hint="NetCDF",
        )

        self.assertEqual("netcdf", detection.source_format)
        self.assertEqual("manual_review_required", detection.capability.import_status)
        self.assertEqual("scientific_grid_or_array", detection.capability.content_family)
        self.assertEqual("scientific_grid_review", detection.capability.parser_id)
        self.assertGreaterEqual(detection.confidence, 0.9)
        self.assertIn("format_hint=netcdf", detection.evidence)
        self.assertIn("url_suffix=netcdf", detection.evidence)

    def test_csv_and_json_formats_route_to_current_sqlite_importers(self) -> None:
        csv_capability = content_parser_capability("text/csv")
        geojson_capability = content_parser_capability("example.geojson.gz")

        self.assertEqual("supported_after_download", csv_capability.import_status)
        self.assertEqual("csv_to_sqlite", csv_capability.parser_id)
        self.assertEqual("supported_after_download", geojson_capability.import_status)
        self.assertEqual("json_to_sqlite", geojson_capability.parser_id)

    def test_archive_payloads_stay_in_transform_review(self) -> None:
        capability = content_parser_capability("zip")

        self.assertEqual("requires_unpack_or_adapter", capability.import_status)
        self.assertEqual("downloaded_payload_transform", capability.review_bucket)
        self.assertEqual("archive_review", capability.parser_id)

    def test_dataset_import_plan_uses_content_registry(self) -> None:
        dataset = Dataset(
            dataset_uid="example:science_grid",
            provider_id="example",
            dataset_id="science_grid",
            title="Science grid",
            categories=("science",),
            data_type="raster_or_grid",
            native_format="nc",
            api_url="https://example.test/science_grid.nc",
        )
        option = DatasetVersionOption(
            dataset_uid=dataset.dataset_uid,
            dataset_id=dataset.dataset_id,
            label="sample",
            version="2026",
            status="latest",
            download_url=dataset.api_url,
            landing_url="",
        )
        eligibility = DownloadEligibility(status="direct_download", label="Direct", reason="fixture")

        plan = dataset_import_plan_entry(dataset, option, eligibility)

        self.assertEqual("netcdf", plan["source_format"])
        self.assertEqual("scientific_grid_or_array", plan["content_family"])
        self.assertEqual("scientific_grid_review", plan["content_parser"])
        self.assertEqual("manual_review_required", plan["status"])
        self.assertEqual("content_parser_required", plan["review_bucket"])

    def test_normalize_content_format_keeps_compound_suffixes(self) -> None:
        self.assertEqual("csv.gz", normalize_content_format("text/csv+gzip"))
        self.assertEqual("geotiff", normalize_content_format("tif"))

    def test_geospatial_image_media_types_route_to_geospatial_review(self) -> None:
        detection = detect_content_format(media_type="image/tiff; application=geotiff")

        self.assertEqual("geotiff", detection.source_format)
        self.assertEqual("geospatial_asset", detection.capability.content_family)
        self.assertEqual("geospatial_asset_review", detection.capability.parser_id)
        self.assertEqual("content_parser_required", detection.capability.review_bucket)

    def test_geopackage_media_types_route_to_geospatial_review(self) -> None:
        detection = detect_content_format(media_type="application/geopackage+sqlite3")

        self.assertEqual("geopackage", detection.source_format)
        self.assertEqual("geospatial_asset", detection.capability.content_family)
        self.assertEqual("geospatial_asset_review", detection.capability.parser_id)

    def test_grib2_url_suffix_routes_to_scientific_grid_review(self) -> None:
        detection = detect_content_format(url="https://example.test/weather/forecast.grb2")

        self.assertEqual("grib", detection.source_format)
        self.assertEqual("scientific_grid_or_array", detection.capability.content_family)
        self.assertEqual("scientific_grid_review", detection.capability.parser_id)
        self.assertEqual("content_parser_required", detection.capability.review_bucket)

    def test_legacy_cdf_url_suffix_routes_to_netcdf_review(self) -> None:
        detection = detect_content_format(url="https://example.test/ocean/legacy_grid.cdf")

        self.assertEqual("netcdf", detection.source_format)
        self.assertEqual("scientific_grid_or_array", detection.capability.content_family)
        self.assertEqual("scientific_grid_review", detection.capability.parser_id)
        self.assertEqual("content_parser_required", detection.capability.review_bucket)

    def test_sqlite_database_snapshot_routes_to_database_review(self) -> None:
        detection = detect_content_format(url="https://example.test/database/catalog.sqlite3")

        self.assertEqual("sqlite", detection.source_format)
        self.assertEqual("database_snapshot", detection.capability.content_family)
        self.assertEqual("database_snapshot_review", detection.capability.parser_id)
        self.assertEqual("content_parser_required", detection.capability.review_bucket)


if __name__ == "__main__":
    unittest.main()
