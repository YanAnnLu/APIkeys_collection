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


if __name__ == "__main__":
    unittest.main()
