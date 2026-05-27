from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from api_launcher.crawlers.html_index import html_file_index_candidates_from_text
from api_launcher.crawlers.source_patterns import DEFAULT_PATTERN_MINIMUM_CONFIDENCE, SourcePatternDetection, UNKNOWN_PATTERN_ID
from api_launcher.crawlers.source_type_registry import source_type_is_file_index
from api_launcher.source_pattern_drafts import (
    SourcePatternDraftError,
    dataset_source_from_detected_url,
    write_source_draft_from_url,
)


class SourcePatternDraftTest(unittest.TestCase):
    def test_detected_url_writes_ignored_local_source_draft(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="stac",
                confidence=0.95,
                evidence=("json_contains_stac_version", "json_references_collections"),
                source_type_hint="stac_collections",
            )

        with TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "dataset_discovery_sources.local.json"

            summary = write_source_draft_from_url(
                "https://example.test/stac",
                output_path,
                categories=("satellite", "raster"),
                max_results=5,
                detector=detector,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        source = payload["sources"][0]
        self.assertEqual("local dataset discovery source draft from source pattern detector; ignored local config only", summary["role"])
        self.assertEqual("stac", summary["source_pattern_detection"]["pattern_id"])
        self.assertEqual(["example_test_stac_stac_collections"], summary["audit_source_ids"])
        self.assertEqual("stac_collections", source["source_type"])
        self.assertEqual(["satellite", "raster"], source["categories"])
        self.assertEqual(5, source["max_results"])
        self.assertIn("--promote-local-discovery-dry-run", str(summary["audit_command"]))

    def test_html_file_index_draft_gets_default_file_regex_for_followup_audit(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="html_file_index",
                confidence=0.5,
                evidence=("html_contains_links", "html_mentions_data_file_extensions:.csv"),
                source_type_hint="html_file_index",
            )

        source, _detection = dataset_source_from_detected_url(
            "https://files.example.test/data/",
            provider_id="sample_files",
            name="Sample files",
            detector=detector,
        )
        candidates = html_file_index_candidates_from_text(
            source,
            (
                '<html><a href="dataset_2026.csv.zst">dataset_2026.csv.zst</a>'
                '<a href="boundary.geojson.gz">boundary.geojson.gz</a>'
                '<a href="legacy_grid.cdf">legacy_grid.cdf</a>'
                '<a href="orbit_swath.hdf5">orbit_swath.hdf5</a>'
                '<a href="tiles.gpkg">tiles.gpkg</a>'
                '<a href="boundaries.shp.zip">boundaries.shp.zip</a>'
                '<a href="roads.fgb">roads.fgb</a>'
                '<a href="basemap.pmtiles">basemap.pmtiles</a>'
                '<a href="offline.mbtiles">offline.mbtiles</a>'
                '<a href="archive.zarr">archive.zarr</a>'
                '<a href="forecast.grib2">forecast.grib2</a>'
                '<a href="catalog.sqlite3">catalog.sqlite3</a>'
                '<a href="notes.txt">notes.txt</a></html>'
            ),
            "https://files.example.test/data/",
            12,
        )

        self.assertEqual("html_file_index", source.source_type)
        self.assertTrue(source_type_is_file_index(source.source_type))
        self.assertIn("csv", source.file_url_regex)
        self.assertIn("cdf", source.file_url_regex)
        self.assertIn("hdf5", source.file_url_regex)
        self.assertIn("gpkg", source.file_url_regex)
        self.assertIn("shp", source.file_url_regex)
        self.assertIn("fgb", source.file_url_regex)
        self.assertIn("pmtiles", source.file_url_regex)
        self.assertIn("mbtiles", source.file_url_regex)
        self.assertIn("sqlite", source.file_url_regex)
        self.assertEqual(1, len(candidates))
        versions = candidates[0].dataset.metadata["available_versions"]
        self.assertEqual(12, len(versions))
        self.assertEqual("dataset_2026.csv.zst", versions[0]["label"])
        self.assertEqual("boundary.geojson.gz", versions[1]["label"])
        self.assertEqual("legacy_grid.cdf", versions[2]["label"])
        self.assertEqual("orbit_swath.hdf5", versions[3]["label"])
        self.assertEqual("tiles.gpkg", versions[4]["label"])
        self.assertEqual("boundaries.shp.zip", versions[5]["label"])
        self.assertEqual("roads.fgb", versions[6]["label"])
        self.assertEqual("basemap.pmtiles", versions[7]["label"])
        self.assertEqual("offline.mbtiles", versions[8]["label"])
        self.assertEqual("archive.zarr", versions[9]["label"])
        self.assertEqual("forecast.grib2", versions[10]["label"])
        self.assertEqual("catalog.sqlite3", versions[11]["label"])

    def test_ogc_wms_detection_creates_supported_wms_source_draft(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="ogc_wms",
                confidence=0.5,
                evidence=("wms_get_capabilities_response", "wms_capabilities_document"),
                source_type_hint="ogc_wms_capabilities",
            )

        source, detection = dataset_source_from_detected_url(
            "https://maps.example.test/wms",
            provider_id="sample_maps",
            detector=detector,
        )

        self.assertEqual("ogc_wms", detection.pattern_id)
        self.assertEqual("ogc_wms_capabilities", source.source_type)
        self.assertEqual("https://maps.example.test/wms?service=WMS&request=GetCapabilities", source.endpoint_url)

    def test_ogc_wms_detection_normalizes_conflicting_query_and_fragment(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="ogc_wms",
                confidence=0.5,
                evidence=("wms_get_capabilities_response", "wms_capabilities_document"),
                source_type_hint="ogc_wms_capabilities",
            )

        source, detection = dataset_source_from_detected_url(
            "https://maps.example.test/wms?layers=roads&service=WFS&request=GetCapabilities#preview",
            provider_id="sample_maps",
            detector=detector,
        )

        self.assertEqual("ogc_wms", detection.pattern_id)
        self.assertEqual("ogc_wms_capabilities", source.source_type)
        self.assertEqual(
            "https://maps.example.test/wms?layers=roads&service=WMS&request=GetCapabilities",
            source.endpoint_url,
        )

    def test_ogc_api_detection_normalizes_base_url_to_collections_endpoint(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="ogc",
                confidence=0.75,
                evidence=("ogc_conformance", "json_contains_collections"),
                source_type_hint="ogc_api_records",
            )

        source, detection = dataset_source_from_detected_url(
            "https://geo.example.test/api",
            provider_id="sample_ogc",
            detector=detector,
        )

        self.assertEqual("ogc", detection.pattern_id)
        self.assertEqual("ogc_api_records", source.source_type)
        self.assertEqual("https://geo.example.test/api/collections", source.endpoint_url)

    def test_ckan_detection_normalizes_portal_root_to_package_search_endpoint(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="ckan",
                confidence=0.75,
                evidence=("ckan_package_search_success", "ckan_api_action_endpoint"),
                source_type_hint="ckan_package_search",
            )

        source, detection = dataset_source_from_detected_url(
            "https://catalog.example.test/dataset/roads",
            provider_id="sample_ckan",
            detector=detector,
        )

        self.assertEqual("ckan", detection.pattern_id)
        self.assertEqual("ckan_package_search", source.source_type)
        self.assertEqual("https://catalog.example.test/api/3/action/package_search", source.endpoint_url)

    def test_socrata_detection_normalizes_portal_root_to_catalog_endpoint(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="socrata",
                confidence=0.75,
                evidence=("host_looks_like_socrata", "socrata_views_returns_list"),
                source_type_hint="socrata_catalog_search",
            )

        source, detection = dataset_source_from_detected_url(
            "https://data.city.example/resource/abcd-1234.json",
            provider_id="sample_socrata",
            detector=detector,
        )

        self.assertEqual("socrata", detection.pattern_id)
        self.assertEqual("socrata_catalog_search", source.source_type)
        self.assertEqual(
            "https://api.us.socrata.com/api/catalog/v1?domains=data.city.example",
            source.endpoint_url,
        )

    def test_vendor_api_detection_creates_supported_source_drafts_without_live_fetch(self) -> None:
        def fetcher(_url: str, _timeout: float):
            return None

        cases = (
            (
                "https://www.ncei.noaa.gov/access/services/search/v1/data?dataset=global-hourly",
                "ncei",
                "ncei_search",
                "https://www.ncei.noaa.gov/access/services/search/v1/datasets",
            ),
            (
                "https://api.gbif.org/v1/dataset/search?q=birds",
                "gbif",
                "gbif_dataset_search",
                "https://api.gbif.org/v1/dataset/search",
            ),
            (
                "https://demo.dataverse.org/api/search?q=ocean",
                "dataverse",
                "dataverse_search",
                "https://demo.dataverse.org/api/search",
            ),
            (
                "https://zenodo.org/api/records?q=climate",
                "zenodo",
                "zenodo_records_search",
                "https://zenodo.org/api/records",
            ),
            (
                "https://api.datacite.org/dois?query=geodata",
                "datacite",
                "datacite_dois",
                "https://api.datacite.org/dois",
            ),
            (
                "https://api.openalex.org/works?search=gis",
                "openalex",
                "openalex_works_search",
                "https://api.openalex.org/works",
            ),
        )

        for url, pattern_id, source_type, endpoint_url in cases:
            with self.subTest(source_type=source_type):
                source, detection = dataset_source_from_detected_url(
                    url,
                    provider_id="sample_provider",
                    fetcher=fetcher,
                )

                self.assertEqual(pattern_id, detection.pattern_id)
                self.assertEqual(source_type, source.source_type)
                self.assertEqual(endpoint_url, source.endpoint_url)

    def test_unknown_detection_stays_in_review(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id=UNKNOWN_PATTERN_ID,
                confidence=0.25,
                evidence=("below_minimum_confidence",),
                candidates=(),
            )

        with self.assertRaisesRegex(SourcePatternDraftError, "unknown") as caught:
            dataset_source_from_detected_url("https://example.test/landing", detector=detector)

        payload = caught.exception.to_dict()
        self.assertEqual("source_pattern_unknown", payload["review_reason"])
        self.assertEqual("review_source_profile_or_add_detector", payload["next_action"])
        self.assertEqual(0, payload["source_draft_count"])
        self.assertEqual("unknown", payload["source_pattern_detection"]["pattern_id"])
        self.assertEqual("source_pattern_unknown", payload["skipped"][0]["reason_code"])

    def test_low_confidence_detector_stays_in_review_even_with_source_hint(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="stac",
                confidence=0.25,
                evidence=("weak_collections_hint",),
                source_type_hint="stac_collections",
            )

        with self.assertRaisesRegex(SourcePatternDraftError, "below minimum") as caught:
            dataset_source_from_detected_url("https://example.test/landing", detector=detector)

        payload = caught.exception.to_dict()
        self.assertEqual("source_pattern_below_minimum_confidence", payload["review_reason"])
        self.assertEqual("stac", payload["source_pattern_detection"]["pattern_id"])
        self.assertEqual("stac_collections", payload["source_pattern_detection"]["source_type_hint"])
        self.assertEqual(DEFAULT_PATTERN_MINIMUM_CONFIDENCE, payload["minimum_confidence"])

    def test_missing_source_type_hint_stays_in_structured_review(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="vendor_custom",
                confidence=0.9,
                evidence=("custom_api_shape",),
                source_type_hint="",
            )

        with self.assertRaisesRegex(SourcePatternDraftError, "no supported source type") as caught:
            dataset_source_from_detected_url("https://example.test/api", detector=detector)

        payload = caught.exception.to_dict()
        self.assertEqual("source_pattern_missing_source_type", payload["review_reason"])
        self.assertEqual("vendor_custom", payload["source_pattern_detection"]["pattern_id"])
        self.assertEqual("review_source_profile_or_add_detector", payload["next_action"])

    def test_unsupported_source_type_is_rejected_before_local_draft(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            return SourcePatternDetection(
                pattern_id="vendor_custom",
                confidence=0.9,
                evidence=("custom_api_shape",),
                source_type_hint="unsupported_custom_api",
            )

        with self.assertRaisesRegex(SourcePatternDraftError, "not supported") as caught:
            dataset_source_from_detected_url("https://example.test/api", detector=detector)

        payload = caught.exception.to_dict()
        self.assertEqual("source_pattern_unsupported_source_type", payload["review_reason"])
        self.assertEqual("unsupported_custom_api", payload["skipped"][0]["detected_source_type"])

    def test_non_http_source_url_is_rejected_before_detection(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            raise AssertionError("detector should not run for invalid source URL")

        with self.assertRaisesRegex(ValueError, "absolute http"):
            dataset_source_from_detected_url("file:///K:/private/source.json", detector=detector)

    def test_source_url_with_embedded_credentials_is_rejected_before_detection(self) -> None:
        def detector(_url: str) -> SourcePatternDetection:
            raise AssertionError("detector should not run for credential-bearing source URL")

        with self.assertRaisesRegex(ValueError, "must not embed credentials"):
            dataset_source_from_detected_url("https://user:secret@example.test/catalog", detector=detector)


if __name__ == "__main__":
    unittest.main()
