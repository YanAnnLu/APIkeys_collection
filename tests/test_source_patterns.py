from __future__ import annotations

import unittest

from api_launcher.crawlers.source_patterns import (
    PatternProbeResponse,
    detect_source_interface_pattern,
)


class SourcePatternDetectorTest(unittest.TestCase):
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

        self.assertEqual("unknown", result.pattern_id)
        self.assertLess(result.confidence, 0.35)
        self.assertEqual("", result.source_type_hint)
        self.assertEqual("stac", result.candidates[0].pattern_id)


if __name__ == "__main__":
    unittest.main()
