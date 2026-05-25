import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_launcher.core import main
from api_launcher.crawlers.dataset_sources import load_dataset_discovery_sources
from api_launcher.crawlers.dataset_sources import SUPPORTED_DATASET_SOURCE_TYPES
from api_launcher.crawlers.source_patterns import SourcePatternDetection
from api_launcher.discovery_drafts import dataset_source_from_provider_candidate
from api_launcher.discovery_drafts import normalize_endpoint_for_source_type
from api_launcher.discovery_drafts import SOURCE_ENDPOINT_NORMALIZERS
from api_launcher.discovery_drafts import write_provider_candidate_source_drafts
from api_launcher.source_pattern_drafts import dataset_source_from_detected_url
from api_launcher.source_pattern_drafts import write_source_draft_from_url


class DiscoveryDraftTests(unittest.TestCase):
    def test_explicit_supported_source_type_becomes_local_dataset_source(self) -> None:
        # 明確標出 crawler type 的候選可以直接變成本機草稿，但仍不代表正式 catalog 已通過審核。
        source = dataset_source_from_provider_candidate(
            {
                "provider_id": "example_data",
                "name": "Example Data",
                "categories": ["open_data", "ckan"],
                "geographic_scope": "global",
                "source_type": "ckan_package_search",
                "endpoint_url": "https://data.example.test/api/3/action/package_search",
                "docs_url": "https://data.example.test/docs",
                "search_terms": ["climate", "transport"],
            }
        )

        self.assertEqual("example_data_ckan_package_search", source.source_id)
        self.assertEqual("example_data", source.provider_id)
        self.assertEqual("ckan_package_search", source.source_type)
        self.assertEqual("https://data.example.test/api/3/action/package_search", source.endpoint_url)
        self.assertEqual(("climate", "transport"), source.search_terms)
        self.assertEqual(("open_data", "ckan"), source.categories)

    def test_stac_api_base_is_normalized_to_collections_endpoint(self) -> None:
        source = dataset_source_from_provider_candidate(
            {
                "provider_id": "planetary_computer",
                "name": "Planetary Computer",
                "categories": ["stac", "satellite"],
                "api_base_url": "https://planetarycomputer.microsoft.com/api/stac/v1",
            }
        )

        self.assertEqual("stac_collections", source.source_type)
        self.assertEqual("https://planetarycomputer.microsoft.com/api/stac/v1/collections", source.endpoint_url)
        self.assertEqual(("stac", "satellite"), source.search_terms)

    def test_unknown_shape_stays_in_review(self) -> None:
        with self.assertRaisesRegex(ValueError, "supported dataset discovery source type"):
            dataset_source_from_provider_candidate(
                {
                    "provider_id": "landing_only",
                    "name": "Landing Only",
                    "source_url": "https://example.test/about",
                }
            )

    def test_missing_boundary_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "provider_id"):
            dataset_source_from_provider_candidate({"name": "No Provider", "endpoint_url": "https://api.example.test"})

    def test_batch_write_keeps_unknown_candidates_in_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "dataset_discovery_sources.local.json"

            summary = write_provider_candidate_source_drafts(provider_candidate_payload(), output_path)
            sources = load_dataset_discovery_sources(output_path)

        self.assertEqual(1, summary["source_draft_count"])
        self.assertEqual(1, summary["skipped_count"])
        self.assertEqual("run_local_discovery_audit_before_catalog_promotion", summary["next_action"])
        self.assertIn("--promote-local-discovery-catalog", summary["audit_command"])
        self.assertEqual(["sample_ckan_ckan_package_search"], summary["audit_source_ids"])
        self.assertEqual("sample_ckan_ckan_package_search", sources[0].source_id)
        self.assertIn("supported dataset discovery source type", summary["skipped"][0]["reason"])

    def test_cli_writes_provider_candidate_source_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "provider_candidates.review.json"
            local_sources_path = Path(tmpdir) / "dataset_discovery_sources.local.json"
            summary_path = Path(tmpdir) / "source_draft_summary.json"
            review_path.write_text(json.dumps(provider_candidate_payload(), ensure_ascii=False), encoding="utf-8")

            rc = main(
                [
                    "--db",
                    str(Path(tmpdir) / "launcher.sqlite"),
                    "--write-provider-candidate-source-drafts",
                    "--provider-candidate-source-drafts-input",
                    str(review_path),
                    "--provider-candidate-source-drafts-local",
                    str(local_sources_path),
                    "--write-provider-candidate-source-drafts-json",
                    str(summary_path),
                ]
            )
            sources = load_dataset_discovery_sources(local_sources_path)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertEqual(1, len(sources))
        self.assertEqual(1, summary["source_draft_count"])
        self.assertEqual(1, summary["skipped_count"])
        self.assertEqual("run_local_discovery_audit_before_catalog_promotion", summary["next_action"])
        self.assertIn("--write-local-discovery-audit-json", summary["audit_command"])

    def test_detected_url_becomes_local_source_draft(self) -> None:
        detection = SourcePatternDetection(
            pattern_id="stac",
            confidence=0.75,
            evidence=("JSON contains stac_version", "Has collections reference"),
            source_type_hint="stac_collections",
        )

        source, returned_detection = dataset_source_from_detected_url(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            provider_id="planetary_computer",
            name="Planetary Computer",
            categories=("satellite",),
            detector=lambda _url: detection,
        )

        self.assertEqual(detection, returned_detection)
        self.assertEqual("planetary_computer_api_stac_v1_stac_collections", source.source_id)
        self.assertEqual("stac_collections", source.source_type)
        self.assertEqual("https://planetarycomputer.microsoft.com/api/stac/v1/collections", source.endpoint_url)
        self.assertEqual(("satellite",), source.categories)
        self.assertIn("pattern=stac", source.notes)
        self.assertIn("JSON contains stac_version", source.notes)

    def test_detected_unknown_source_stays_in_review(self) -> None:
        detection = SourcePatternDetection(pattern_id="unknown", confidence=0.1, evidence=(), source_type_hint="")

        with self.assertRaisesRegex(ValueError, "unknown"):
            dataset_source_from_detected_url("https://example.test/landing", detector=lambda _url: detection)

    def test_write_source_draft_from_url_records_detection_summary(self) -> None:
        detection = SourcePatternDetection(
            pattern_id="ckan",
            confidence=0.5,
            evidence=("CKAN package_search returns success=true",),
            source_type_hint="ckan_package_search",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "dataset_discovery_sources.local.json"
            summary = write_source_draft_from_url(
                "https://data.example.test/api/3/action",
                output_path,
                provider_id="sample_ckan",
                name="Sample CKAN",
                detector=lambda _url: detection,
            )
            sources = load_dataset_discovery_sources(output_path)

        self.assertEqual(1, summary["source_draft_count"])
        self.assertEqual(["sample_ckan_api_3_action_ckan_package_search"], summary["audit_source_ids"])
        self.assertEqual("ckan", summary["source_pattern_detection"]["pattern_id"])
        self.assertEqual("ckan_package_search", sources[0].source_type)
        self.assertEqual("https://data.example.test/api/3/action/package_search", sources[0].endpoint_url)

    def test_ckan_root_and_deep_urls_normalize_to_package_search(self) -> None:
        self.assertEqual(
            "https://catalog.example.test/api/3/action/package_search",
            normalize_endpoint_for_source_type("ckan_package_search", "https://catalog.example.test"),
        )
        self.assertEqual(
            "https://catalog.example.test/api/3/action/package_search",
            normalize_endpoint_for_source_type("ckan_package_search", "https://catalog.example.test/dataset/roads"),
        )
        self.assertEqual(
            "https://catalog.example.test/api/3/action/package_search",
            normalize_endpoint_for_source_type(
                "ckan_package_search",
                "https://catalog.example.test/api/3/action/package_show?id=roads",
            ),
        )

    def test_socrata_portal_urls_normalize_to_catalog_endpoint_with_domain(self) -> None:
        self.assertEqual(
            "https://api.us.socrata.com/api/catalog/v1?domains=data.city.example",
            normalize_endpoint_for_source_type("socrata_catalog_search", "https://data.city.example"),
        )
        self.assertEqual(
            "https://api.us.socrata.com/api/catalog/v1?domains=data.city.example",
            normalize_endpoint_for_source_type(
                "socrata_catalog_search",
                "https://data.city.example/resource/abcd-1234.json",
            ),
        )
        self.assertEqual(
            "https://api.us.socrata.com/api/catalog/v1?domains=data.city.example",
            normalize_endpoint_for_source_type(
                "socrata_catalog_search",
                "https://api.us.socrata.com/api/catalog/v1?domains=data.city.example",
            ),
        )
        self.assertEqual(
            "https://api.us.socrata.com/api/catalog/v1?domains=data.city.example",
            normalize_endpoint_for_source_type(
                "socrata_catalog_search",
                "https://api.us.socrata.com/api/catalog/v1?domains=data.city.example&limit=1#probe",
            ),
        )

    def test_search_style_endpoints_strip_probe_query_before_crawler_adds_bounds(self) -> None:
        self.assertEqual(
            "https://planetarycomputer.microsoft.com/api/stac/v1/collections",
            normalize_endpoint_for_source_type(
                "stac_collections",
                "https://planetarycomputer.microsoft.com/api/stac/v1?f=json#landing",
            ),
        )
        self.assertEqual(
            "https://catalog.example.test/api/3/action/package_search",
            normalize_endpoint_for_source_type(
                "ckan_package_search",
                "https://catalog.example.test/api/3/action/package_search?rows=1#probe",
            ),
        )
        self.assertEqual(
            "https://api.gbif.org/v1/dataset/search",
            normalize_endpoint_for_source_type(
                "gbif_dataset_search",
                "https://api.gbif.org/v1/dataset/search?limit=1",
            ),
        )
        self.assertEqual(
            "https://demo.dataverse.org/api/search",
            normalize_endpoint_for_source_type("dataverse_search", "https://demo.dataverse.org"),
        )
        self.assertEqual(
            "https://zenodo.org/api/records",
            normalize_endpoint_for_source_type("zenodo_records_search", "https://zenodo.org/records?q=ocean"),
        )
        self.assertEqual(
            "https://api.datacite.org/dois",
            normalize_endpoint_for_source_type("datacite_dois", "https://api.datacite.org/dois?query=climate"),
        )
        self.assertEqual(
            "https://api.openalex.org/works",
            normalize_endpoint_for_source_type("openalex_works_search", "https://api.openalex.org/works?search=climate"),
        )
        self.assertEqual(
            "https://www.ncei.noaa.gov/access/services/search/v1/datasets",
            normalize_endpoint_for_source_type(
                "ncei_search",
                "https://www.ncei.noaa.gov/access/services/search/v1/data?dataset=global-hourly&limit=1",
            ),
        )
        self.assertEqual(
            "https://cmr.earthdata.nasa.gov/search/collections.json",
            normalize_endpoint_for_source_type(
                "cmr_collections",
                "https://cmr.earthdata.nasa.gov/search/collections.json?page_size=1#probe",
            ),
        )

    def test_endpoint_normalizer_registry_stays_inside_supported_source_types(self) -> None:
        # Endpoint 正規化是 source draft 的第一道邊界；registry 必須只指向已接 crawler 的 source_type。
        self.assertLessEqual(set(SOURCE_ENDPOINT_NORMALIZERS), set(SUPPORTED_DATASET_SOURCE_TYPES))
        self.assertIn("ckan_package_search", SOURCE_ENDPOINT_NORMALIZERS)
        self.assertIn("socrata_catalog_search", SOURCE_ENDPOINT_NORMALIZERS)
        self.assertIn("erddap_all_datasets", SOURCE_ENDPOINT_NORMALIZERS)
        self.assertEqual(
            "https://example.test/files?keep=true#raw",
            normalize_endpoint_for_source_type("html_file_index", "https://example.test/files?keep=true#raw"),
        )
        self.assertEqual(
            "https://example.test/root?keep=true#raw",
            normalize_endpoint_for_source_type("unknown_source_type", "https://example.test/root?keep=true#raw"),
        )

    def test_cli_writes_detected_source_draft_from_url(self) -> None:
        detection = SourcePatternDetection(
            pattern_id="erddap",
            confidence=0.75,
            evidence=("ERDDAP info/index.json returns table metadata",),
            source_type_hint="erddap_all_datasets",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            local_sources_path = Path(tmpdir) / "dataset_discovery_sources.local.json"
            summary_path = Path(tmpdir) / "source_pattern_summary.json"
            with patch("api_launcher.source_pattern_drafts.detect_source_interface_pattern", return_value=detection):
                rc = main(
                    [
                        "--db",
                        str(Path(tmpdir) / "launcher.sqlite"),
                        "--write-source-draft-from-url",
                        "https://coastwatch.pfeg.noaa.gov/erddap",
                        "--source-draft-provider-id",
                        "noaa_coastwatch",
                        "--source-draft-name",
                        "NOAA CoastWatch",
                        "--source-draft-local",
                        str(local_sources_path),
                        "--write-source-draft-json",
                        str(summary_path),
                    ]
                )
            sources = load_dataset_discovery_sources(local_sources_path)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertEqual(1, len(sources))
        self.assertEqual("erddap_all_datasets", sources[0].source_type)
        self.assertIn("/erddap/tabledap/allDatasets.json", sources[0].endpoint_url)
        self.assertEqual("erddap", summary["source_pattern_detection"]["pattern_id"])
        self.assertEqual("run_local_discovery_audit_before_catalog_promotion", summary["next_action"])

    def test_erddap_deep_dataset_url_normalizes_to_all_datasets_endpoint(self) -> None:
        endpoint = normalize_endpoint_for_source_type(
            "erddap_all_datasets",
            "https://coastwatch.example.test/erddap/griddap/jplMURSST41.html",
        )

        self.assertEqual(
            "https://coastwatch.example.test/erddap/tabledap/allDatasets.json?"
            "datasetID,title,summary,institution,cdm_data_type,griddap,tabledap,wms,fgdc,iso19115,infoUrl",
            endpoint,
        )


def provider_candidate_payload() -> dict[str, object]:
    # 批次測試同時覆蓋可證明的 CKAN 來源，以及必須留在 review 的 landing page。
    return {
        "schema_version": 1,
        "candidates": [
            {
                "provider_id": "sample_ckan",
                "name": "Sample CKAN",
                "categories": ["open_data", "ckan"],
                "geographic_scope": "global",
                "source_type": "ckan_package_search",
                "endpoint_url": "https://data.example.test/api/3/action/package_search",
            },
            {
                "provider_id": "landing_only",
                "name": "Landing Only",
                "source_url": "https://example.test/about",
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
