from __future__ import annotations

import unittest
from unittest.mock import patch

from api_launcher.crawlers.source_patterns import (
    DEFAULT_PATTERN_MINIMUM_CONFIDENCE,
    DEFAULT_PATTERN_PROBE_MAX_BYTES,
    PatternProbeResponse,
    SOURCE_TYPE_HINTS,
    UNKNOWN_PATTERN_ID,
    detect_source_interface_pattern,
    fetch_pattern_probe,
)
from api_launcher.crawlers.dataset_sources import SUPPORTED_DATASET_SOURCE_TYPES


class SourcePatternDetectorTest(unittest.TestCase):
    def test_fetch_pattern_probe_uses_named_bounded_read(self) -> None:
        read_sizes: list[int] = []

        class FakeHeaders(dict):
            def get_content_charset(self) -> str:
                return "utf-8"

        class FakeResponse:
            headers = FakeHeaders({"content-type": "application/json"})
            status = 200

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, _exc_type, _exc, _tb) -> None:
                return None

            def read(self, size: int) -> bytes:
                read_sizes.append(size)
                return b'{"ok": true}'

            def geturl(self) -> str:
                return "https://example.test/probe"

        with patch("api_launcher.crawlers.source_patterns.urllib.request.urlopen", return_value=FakeResponse()):
            response = fetch_pattern_probe("https://example.test/probe", timeout=1.0, max_bytes=19)

        self.assertIsNotNone(response)
        self.assertEqual([20], read_sizes)
        self.assertEqual(128 * 1024, DEFAULT_PATTERN_PROBE_MAX_BYTES)
        self.assertEqual({"ok": True}, response.json_payload() if response else None)

    def test_fetch_pattern_probe_rejects_oversized_response(self) -> None:
        class FakeHeaders(dict):
            def get_content_charset(self) -> str:
                return "utf-8"

        class FakeResponse:
            headers = FakeHeaders({"content-type": "application/json"})
            status = 200

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, _exc_type, _exc, _tb) -> None:
                return None

            def read(self, size: int) -> bytes:
                return b"x" * size

            def geturl(self) -> str:
                return "https://example.test/probe"

        with patch("api_launcher.crawlers.source_patterns.urllib.request.urlopen", return_value=FakeResponse()):
            response = fetch_pattern_probe("https://example.test/probe", timeout=1.0, max_bytes=19)

        self.assertIsNone(response)

    def test_stac_pattern_uses_json_evidence_and_source_type_hint(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://example.test/stac":
                return PatternProbeResponse(
                    url=url,
                    text='{"stac_version":"1.0.0","links":[{"rel":"search","href":"./search"}],"collections":[]}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://example.test/stac", fetcher=fetcher)

        self.assertEqual("stac", result.pattern_id)
        self.assertEqual("stac_collections", result.source_type_hint)
        self.assertGreaterEqual(result.confidence, 0.75)
        self.assertIn("json_contains_stac_version", result.evidence)

    def test_stac_pattern_accepts_collections_endpoint(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if url == "https://example.test/stac/collections":
                return PatternProbeResponse(
                    url=url,
                    text='{"collections":[{"id":"example"}],"links":[{"rel":"root","href":"../"}]}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://example.test/stac/collections", fetcher=fetcher)

        self.assertEqual("stac", result.pattern_id)
        self.assertEqual("stac_collections", result.source_type_hint)
        self.assertIn("json_references_collections", result.evidence)
        self.assertIn("stac_collections_endpoint", result.evidence)
        self.assertEqual("https://example.test/stac/collections", calls[0])

    def test_stac_pattern_probes_path_collections_before_url_fragment(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if url == "https://example.test/api/stac/collections":
                return PatternProbeResponse(
                    url=url,
                    text='{"collections":[{"id":"example"}],"links":[{"rel":"root","href":"../"}]}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://example.test/api/stac?f=json#preview", fetcher=fetcher)

        self.assertEqual("stac", result.pattern_id)
        self.assertIn("https://example.test/api/stac/collections", calls)
        self.assertLess(
            calls.index("https://example.test/api/stac/collections"),
            calls.index("https://example.test/collections"),
        )

    def test_erddap_pattern_probes_info_index(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://coastwatch.example.test/erddap/info/index.json":
                return PatternProbeResponse(
                    url=url,
                    text='{"table":{"columnNames":["datasetID"]}}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://coastwatch.example.test/erddap", fetcher=fetcher)

        self.assertEqual("erddap", result.pattern_id)
        self.assertEqual("erddap_all_datasets", result.source_type_hint)
        self.assertIn("erddap_info_index_table", result.evidence)

    def test_erddap_pattern_uses_site_root_for_deep_dataset_urls(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if url == "https://coastwatch.example.test/erddap/info/index.json":
                return PatternProbeResponse(
                    url=url,
                    text='{"table":{"columnNames":["datasetID"]}}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern(
            "https://coastwatch.example.test/ERDDAP/griddap/jplMURSST41.html",
            fetcher=fetcher,
        )

        self.assertEqual("erddap", result.pattern_id)
        self.assertEqual("erddap_all_datasets", result.source_type_hint)
        self.assertIn("https://coastwatch.example.test/erddap/info/index.json", calls)

    def test_ckan_pattern_probes_package_search(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://catalog.example.test/api/3/action/package_search?rows=1":
                return PatternProbeResponse(
                    url=url,
                    text='{"success": true, "result": {"count": 1, "results": []}}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://catalog.example.test", fetcher=fetcher)

        self.assertEqual("ckan", result.pattern_id)
        self.assertEqual("ckan_package_search", result.source_type_hint)
        self.assertIn("ckan_package_search_success", result.evidence)
        self.assertIn("ckan_api_action_endpoint", result.evidence)

    def test_ckan_pattern_falls_back_to_origin_probe_for_deep_urls(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if url == "https://catalog.example.test/api/3/action/package_search?rows=1":
                return PatternProbeResponse(
                    url=url,
                    text='{"success": true, "result": {"count": 1, "results": []}}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://catalog.example.test/dataset/roads", fetcher=fetcher)

        self.assertEqual("ckan", result.pattern_id)
        self.assertIn("https://catalog.example.test/dataset/roads/api/3/action/package_search?rows=1", calls)
        self.assertIn("https://catalog.example.test/api/3/action/package_search?rows=1", calls)

    def test_socrata_pattern_uses_host_and_views_endpoint(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://data.city.example/api/views.json?limit=1":
                return PatternProbeResponse(
                    url=url,
                    text='[{"id":"abcd-1234","name":"Example Dataset"}]',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://data.city.example", fetcher=fetcher)

        self.assertEqual("socrata", result.pattern_id)
        self.assertEqual("socrata_catalog_search", result.source_type_hint)
        self.assertIn("host_looks_like_socrata", result.evidence)
        self.assertIn("socrata_views_returns_list", result.evidence)

    def test_socrata_pattern_falls_back_to_origin_probe_for_resource_urls(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if url == "https://data.city.example/api/views.json?limit=1":
                return PatternProbeResponse(
                    url=url,
                    text='[{"id":"abcd-1234","name":"Example Dataset"}]',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://data.city.example/resource/abcd-1234.json", fetcher=fetcher)

        self.assertEqual("socrata", result.pattern_id)
        self.assertIn("https://data.city.example/resource/abcd-1234.json/api/views.json?limit=1", calls)
        self.assertIn("https://data.city.example/api/views.json?limit=1", calls)

    def test_ogc_pattern_detects_conformance_and_collections(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://geo.example.test/ogc":
                return PatternProbeResponse(
                    url=url,
                    text=(
                        '{"conformsTo":["http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core"],'
                        '"collections":[]}'
                    ),
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://geo.example.test/ogc", fetcher=fetcher)

        self.assertEqual("ogc", result.pattern_id)
        self.assertEqual("ogc_api_records", result.source_type_hint)
        self.assertIn("json_contains_conforms_to", result.evidence)
        self.assertIn("json_contains_collections", result.evidence)
        self.assertIn("conforms_to_mentions_ogc", result.evidence)

    def test_ogc_pattern_probes_conformance_and_collections_endpoints(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if url == "https://geo.example.test/api/conformance":
                return PatternProbeResponse(
                    url=url,
                    text='{"conformsTo":["http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core"]}',
                    headers={"content-type": "application/json"},
                )
            if url == "https://geo.example.test/api/collections":
                return PatternProbeResponse(
                    url=url,
                    text='{"collections":[{"id":"roads"}]}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://geo.example.test/api", fetcher=fetcher)

        self.assertEqual("ogc", result.pattern_id)
        self.assertEqual("ogc_api_records", result.source_type_hint)
        self.assertIn("https://geo.example.test/api/conformance", calls)
        self.assertIn("https://geo.example.test/api/collections", calls)
        self.assertIn("json_contains_conforms_to", result.evidence)
        self.assertIn("json_contains_collections", result.evidence)
        self.assertIn("conforms_to_mentions_ogc", result.evidence)

    def test_ogc_pattern_probes_path_endpoints_before_url_fragment(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if url == "https://geo.example.test/api/conformance":
                return PatternProbeResponse(
                    url=url,
                    text='{"conformsTo":["http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core"]}',
                    headers={"content-type": "application/json"},
                )
            if url == "https://geo.example.test/api/collections":
                return PatternProbeResponse(
                    url=url,
                    text='{"collections":[{"id":"roads"}]}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://geo.example.test/api?f=json#preview", fetcher=fetcher)

        self.assertEqual("ogc", result.pattern_id)
        self.assertIn("https://geo.example.test/api/conformance", calls)
        self.assertIn("https://geo.example.test/api/collections", calls)
        self.assertNotIn("https://geo.example.test/collections", calls)

    def test_ogc_pattern_dedupes_repeated_probe_evidence(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url in {"https://geo.example.test/api", "https://geo.example.test/api/conformance"}:
                return PatternProbeResponse(
                    url=url,
                    text='{"conformsTo":["http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core"]}',
                    headers={"content-type": "application/json"},
                )
            if url == "https://geo.example.test/api/collections":
                return PatternProbeResponse(
                    url=url,
                    text='{"collections":[{"id":"roads"}]}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://geo.example.test/api", fetcher=fetcher)

        self.assertEqual("ogc", result.pattern_id)
        self.assertEqual(1, result.evidence.count("json_contains_conforms_to"))
        self.assertEqual(1, result.evidence.count("conforms_to_mentions_ogc"))

    def test_ogc_wms_capabilities_xml_is_enough_for_pattern_detection(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://maps.example.test/wms?service=WMS&request=GetCapabilities":
                return PatternProbeResponse(
                    url=url,
                    text=(
                        '<WMS_Capabilities xmlns="http://www.opengis.net/wms">'
                        "<Service><Name>WMS</Name></Service></WMS_Capabilities>"
                    ),
                    headers={"content-type": "text/xml"},
                )
            return None

        result = detect_source_interface_pattern("https://maps.example.test/wms", fetcher=fetcher)

        self.assertEqual("ogc_wms", result.pattern_id)
        self.assertEqual("ogc_wms_capabilities", result.source_type_hint)
        self.assertIn("wms_get_capabilities_response", result.evidence)
        self.assertIn("wms_capabilities_document", result.evidence)

    def test_ogc_wms_detector_preserves_explicit_uppercase_capabilities_query(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if url == "https://maps.example.test/wms?SERVICE=WMS&REQUEST=GetCapabilities":
                return PatternProbeResponse(
                    url=url,
                    text=(
                        '<WMS_Capabilities xmlns="http://www.opengis.net/wms">'
                        "<Service><Name>WMS</Name></Service></WMS_Capabilities>"
                    ),
                    headers={"content-type": "text/xml"},
                )
            return None

        result = detect_source_interface_pattern(
            "https://maps.example.test/wms?SERVICE=WMS&REQUEST=GetCapabilities",
            fetcher=fetcher,
        )

        self.assertEqual("ogc_wms", result.pattern_id)
        self.assertIn("https://maps.example.test/wms?SERVICE=WMS&REQUEST=GetCapabilities", calls)
        self.assertNotIn(
            "https://maps.example.test/wms?SERVICE=WMS&REQUEST=GetCapabilities&service=WMS&request=GetCapabilities",
            calls,
        )

    def test_ogc_wms_probe_adds_query_before_url_fragment(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if url == "https://maps.example.test/wms?layers=roads&service=WMS&request=GetCapabilities":
                return PatternProbeResponse(
                    url=url,
                    text=(
                        '<WMS_Capabilities xmlns="http://www.opengis.net/wms">'
                        "<Service><Name>WMS</Name></Service></WMS_Capabilities>"
                    ),
                    headers={"content-type": "text/xml"},
                )
            return None

        result = detect_source_interface_pattern(
            "https://maps.example.test/wms?layers=roads#preview",
            fetcher=fetcher,
        )

        self.assertEqual("ogc_wms", result.pattern_id)
        self.assertIn("https://maps.example.test/wms?layers=roads&service=WMS&request=GetCapabilities", calls)
        self.assertFalse(any("#preview&service=WMS" in url or "#preview?service=WMS" in url for url in calls))

    def test_cmr_detector_does_not_pollute_non_cmr_urls(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            calls.append(url)
            if "cmr.earthdata.nasa.gov" in url:
                return PatternProbeResponse(url=url, text='{"feed":{"entry":[]}}', headers={"content-type": "application/json"})
            return None

        result = detect_source_interface_pattern("https://unknown.example.test/catalog", fetcher=fetcher)

        self.assertNotEqual("cmr", result.pattern_id)
        self.assertNotIn("https://cmr.earthdata.nasa.gov/search/collections.json?page_size=1", calls)

    def test_vendor_science_api_urls_map_to_existing_crawler_handlers(self) -> None:
        def fetcher(_url: str, _timeout: float) -> PatternProbeResponse | None:
            return None

        cases = (
            (
                "https://www.ncei.noaa.gov/access/services/search/v1/datasets",
                "ncei",
                "ncei_search",
                "ncei_search_api_path",
            ),
            (
                "https://api.gbif.org/v1/dataset/search?q=ocean",
                "gbif",
                "gbif_dataset_search",
                "gbif_dataset_api_path",
            ),
            (
                "https://demo.dataverse.org/api/search?q=climate",
                "dataverse",
                "dataverse_search",
                "dataverse_search_api_path",
            ),
            (
                "https://zenodo.org/api/records?q=geodata",
                "zenodo",
                "zenodo_records_search",
                "zenodo_records_api_path",
            ),
            (
                "https://api.datacite.org/dois?query=climate",
                "datacite",
                "datacite_dois",
                "datacite_dois_api_path",
            ),
            (
                "https://api.openalex.org/works?search=gis",
                "openalex",
                "openalex_works_search",
                "openalex_works_api_path",
            ),
        )

        for url, pattern_id, source_type_hint, evidence in cases:
            with self.subTest(url=url):
                result = detect_source_interface_pattern(url, fetcher=fetcher)

                self.assertEqual(pattern_id, result.pattern_id)
                self.assertEqual(source_type_hint, result.source_type_hint)
                self.assertGreaterEqual(result.confidence, DEFAULT_PATTERN_MINIMUM_CONFIDENCE)
                self.assertIn(evidence, result.evidence)

    def test_pattern_source_type_hints_are_supported_crawler_source_types(self) -> None:
        # 「貼 URL 建來源草稿」會先走 source pattern detector；這裡鎖住每個
        # 已接 handler 的 source_type 都至少有一條 detector hint，避免 crawler
        # 明明存在但 UI/CLI URL 入口仍被擋成 unknown。
        self.assertEqual(set(SOURCE_TYPE_HINTS.values()), set(SUPPORTED_DATASET_SOURCE_TYPES))

    def test_fetcher_exceptions_fall_back_to_unknown_pattern(self) -> None:
        def fetcher(_url: str, _timeout: float) -> PatternProbeResponse | None:
            raise RuntimeError("probe failed")

        result = detect_source_interface_pattern("https://unstable.example.test/catalog", fetcher=fetcher)

        self.assertEqual(UNKNOWN_PATTERN_ID, result.pattern_id)
        self.assertEqual(0.0, result.confidence)
        self.assertEqual("", result.source_type_hint)
        self.assertTrue(result.candidates)
        self.assertTrue(all(candidate.confidence == 0.0 for candidate in result.candidates))

    def test_malformed_json_probe_falls_back_to_unknown_pattern(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            return PatternProbeResponse(
                url=url,
                text='{"collections":[',
                headers={"content-type": "application/json"},
            )

        result = detect_source_interface_pattern("https://broken-json.example.test/catalog", fetcher=fetcher)

        self.assertEqual(UNKNOWN_PATTERN_ID, result.pattern_id)
        self.assertEqual(0.0, result.confidence)

    def test_html_file_index_is_fallback_pattern_with_file_links(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://files.example.test/":
                return PatternProbeResponse(
                    url=url,
                    text='<html><a href="sample.csv">sample.csv</a><a href="archive.zip">archive.zip</a></html>',
                    headers={"content-type": "text/html"},
                )
            return None

        result = detect_source_interface_pattern("https://files.example.test/", fetcher=fetcher)

        self.assertEqual("html_file_index", result.pattern_id)
        self.assertEqual("html_file_index", result.source_type_hint)
        self.assertIn("html_contains_links", result.evidence)

    def test_html_file_index_detects_compound_geospatial_file_links(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://geo-files.example.test/":
                return PatternProbeResponse(
                    url=url,
                    text=(
                        '<html><a href="boundary.geojson.gz">boundary.geojson.gz</a>'
                        '<a href="legacy_grid.cdf">legacy_grid.cdf</a>'
                        '<a href="orbit_swath.hdf5">orbit_swath.hdf5</a>'
                        '<a href="tiles.gpkg">tiles.gpkg</a>'
                        '<a href="boundaries.shp.zip">boundaries.shp.zip</a>'
                        '<a href="roads.fgb">roads.fgb</a>'
                        '<a href="basemap.pmtiles">basemap.pmtiles</a>'
                        '<a href="offline.mbtiles">offline.mbtiles</a>'
                        '<a href="forecast.grib2">forecast.grib2</a>'
                        '<a href="catalog.sqlite3">catalog.sqlite3</a>'
                        '<a href="notes.txt">notes.txt</a></html>'
                    ),
                    headers={"content-type": "text/html"},
                )
            return None

        result = detect_source_interface_pattern("https://geo-files.example.test/", fetcher=fetcher)

        self.assertEqual("html_file_index", result.pattern_id)
        self.assertEqual("html_file_index", result.source_type_hint)
        self.assertIn("html_mentions_data_file_extensions:.geojson.gz,.cdf,.hdf5,.gpkg,.shp.zip", result.evidence)

    def test_ambiguous_collections_payload_stays_unknown_below_threshold(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://ambiguous.example.test/catalog":
                return PatternProbeResponse(
                    url=url,
                    text='{"collections":[]}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://ambiguous.example.test/catalog", fetcher=fetcher)

        self.assertEqual(UNKNOWN_PATTERN_ID, result.pattern_id)
        self.assertLess(result.confidence, DEFAULT_PATTERN_MINIMUM_CONFIDENCE)
        self.assertEqual("", result.source_type_hint)
        self.assertEqual("stac", result.candidates[0].pattern_id)

    def test_collections_endpoint_without_stac_links_stays_unknown_below_threshold(self) -> None:
        def fetcher(url: str, _timeout: float) -> PatternProbeResponse | None:
            if url == "https://ambiguous.example.test/collections":
                return PatternProbeResponse(
                    url=url,
                    text='{"collections":[]}',
                    headers={"content-type": "application/json"},
                )
            return None

        result = detect_source_interface_pattern("https://ambiguous.example.test/collections", fetcher=fetcher)

        self.assertEqual(UNKNOWN_PATTERN_ID, result.pattern_id)
        self.assertLess(result.confidence, DEFAULT_PATTERN_MINIMUM_CONFIDENCE)


if __name__ == "__main__":
    unittest.main()
