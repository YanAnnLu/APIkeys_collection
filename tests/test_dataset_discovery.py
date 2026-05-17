from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.dataset_discovery import (
    DatasetDiscoverySource,
    erddap_candidates_from_payload,
    html_file_index_candidates_from_text,
    infer_data_family,
    load_dataset_discovery_sources,
    ncei_candidates_from_payload,
    ncei_search_url,
)
from api_launcher.download_eligibility import looks_like_direct_download


class DatasetDiscoveryTests(unittest.TestCase):
    def test_source_loader_reads_configured_dataset_crawlers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sources.json"
            path.write_text(
                """
                {
                  "schema_version": 1,
                  "sources": [
                    {
                      "source_id": "sample_ncei",
                      "provider_id": "noaa_ncei_access_data",
                      "name": "Sample NCEI",
                      "source_type": "ncei_search",
                      "endpoint_url": "https://example.test/search",
                      "search_terms": ["ais"],
                      "categories": ["noaa"],
                      "max_results": 2
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            sources = load_dataset_discovery_sources(path)

        self.assertEqual(1, len(sources))
        self.assertEqual("sample_ncei", sources[0].source_id)
        self.assertEqual(("ais",), sources[0].search_terms)

    def test_ncei_payload_becomes_reviewable_dataset_candidate(self) -> None:
        source = DatasetDiscoverySource(
            source_id="noaa_ncei_dataset_search",
            provider_id="noaa_ncei_access_data",
            name="NOAA NCEI Search",
            source_type="ncei_search",
            endpoint_url="https://example.test/search",
            categories=("noaa", "catalog"),
            geographic_scope="global/us",
        )
        payload = {
            "results": [
                {
                    "id": "automatic-identification-system-ais",
                    "fileId": "gov.noaa.ncdc:C01591",
                    "name": "Automatic Identification System (AIS) Vessel Traffic Data",
                    "description": "Vessel traffic data are AIS positions in U.S. offshore waters.",
                    "formats": [{"name": "csv"}, {"name": "json"}],
                    "observationTypes": [{"name": "Ocean"}],
                    "keywords": [{"name": "VESSEL TRAFFIC"}],
                    "startDate": "2009-01-01",
                    "endDate": "2025-12-31",
                    "links": {
                        "other": [{"url": "https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C01591/html"}],
                        "access": [{"url": "https://marinecadastre.gov/ais/"}],
                    },
                }
            ]
        }

        candidates = ncei_candidates_from_payload(source, payload, "https://example.test/search?text=ais", 5)

        self.assertEqual(1, len(candidates))
        dataset = candidates[0].dataset
        self.assertEqual("noaa_ncei_access_data", dataset.provider_id)
        self.assertEqual("automatic-identification-system-ais", dataset.dataset_id)
        self.assertEqual("spatiotemporal_trajectory", dataset.metadata["data_family"])
        self.assertEqual("csv", dataset.native_format)
        self.assertEqual("needs_review", dataset.metadata["candidate_status"])

    def test_erddap_all_datasets_payload_can_be_filtered_by_terms(self) -> None:
        source = DatasetDiscoverySource(
            source_id="erddap",
            provider_id="noaa_coastwatch_erddap",
            name="ERDDAP",
            source_type="erddap_all_datasets",
            endpoint_url="https://example.test/erddap/allDatasets.json",
            categories=("erddap", "satellite"),
        )
        payload = {
            "table": {
                "columnNames": ["datasetID", "title", "summary", "institution", "cdm_data_type", "griddap", "tabledap", "wms", "infoUrl"],
                "rows": [
                    [
                        "jplMURSST41",
                        "MUR sea surface temperature",
                        "Daily global sea surface temperature grid",
                        "NASA JPL",
                        "Grid",
                        "https://example.test/erddap/griddap/jplMURSST41",
                        "",
                        "",
                        "https://example.test/erddap/info/jplMURSST41/index.html",
                    ],
                    ["unrelated", "Current meters", "Ocean currents", "NOAA", "TimeSeries", "", "", "", ""],
                ],
            }
        }

        candidates = erddap_candidates_from_payload(source, payload, source.endpoint_url, 5, ("sea surface temperature",))

        self.assertEqual(1, len(candidates))
        self.assertEqual("jplmursst41", candidates[0].dataset.dataset_id)
        self.assertEqual("grid_or_array", candidates[0].dataset.metadata["data_family"])

    def test_html_file_index_discovers_versions_without_hardcoded_python_urls(self) -> None:
        source = DatasetDiscoverySource(
            source_id="marinecadastre_ais_daily_index_2025",
            provider_id="noaa_marinecadastre_ais",
            name="AIS index",
            source_type="html_file_index",
            endpoint_url="https://example.test/ais/csv2025/index.html",
            docs_url="https://www.coast.noaa.gov/digitalcoast/data/vesseltraffic.html",
            dataset_id="marinecadastre_ais_daily_shards",
            dataset_title="NOAA MarineCadastre AIS daily vessel-traffic shards",
            data_type="spatiotemporal_trajectory",
            native_format="csv.zst",
            file_url_regex=r"ais-(?P<version>\d{4}-\d{2}-\d{2})\.csv\.zst$",
            categories=("ais", "maritime", "gis", "timeseries"),
        )
        html = """
        <a href="ais-2025-01-01.csv.zst">ais-2025-01-01.csv.zst</a>
        <a href="ais-2025-01-02.csv.zst">ais-2025-01-02.csv.zst</a>
        """

        candidates = html_file_index_candidates_from_text(source, html, source.endpoint_url, 10)

        self.assertEqual(1, len(candidates))
        dataset = candidates[0].dataset
        self.assertEqual("marinecadastre_ais_daily_shards", dataset.dataset_id)
        self.assertEqual("csv.zst", dataset.native_format)
        self.assertEqual(2, len(dataset.metadata["available_versions"]))
        self.assertTrue(looks_like_direct_download(dataset.metadata["available_versions"][0]["download_url"]))

    def test_search_url_and_family_inference_are_stable(self) -> None:
        self.assertIn("text=cloud+moisture", ncei_search_url("https://example.test/search", "cloud moisture", 3))
        self.assertEqual("raster_or_grid", infer_data_family("GOES cloud moisture imagery ABI raster"))
        self.assertEqual("spatiotemporal_trajectory", infer_data_family("AIS vessel trajectory"))


if __name__ == "__main__":
    unittest.main()
