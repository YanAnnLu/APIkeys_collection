# 這份測試鎖定多來源 crawler parser 與 audit，避免 discovery 看似成功但候選失真。
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_launcher.dataset_discovery import (
    DatasetDiscoverySource,
    DatasetCrawlOptions,
    DatasetCrawlerOutput,
    ckan_candidates_from_payload,
    crawl_dataset_sources,
    cmr_candidates_from_payload,
    datacite_candidates_from_payload,
    datacite_dois_search_url,
    dataverse_candidates_from_payload,
    erddap_candidates_from_payload,
    gbif_candidates_from_payload,
    html_file_index_candidates_from_text,
    infer_data_family,
    load_dataset_discovery_sources,
    ncei_candidates_from_payload,
    ncei_search_url,
    ogc_records_candidates_from_payload,
    ogc_records_search_url,
    ogc_wms_candidates_from_xml,
    ogc_wms_capabilities_url,
    openalex_candidates_from_payload,
    openalex_works_search_url,
    socrata_catalog_candidates_from_payload,
    socrata_catalog_search_url,
    stac_candidates_from_payload,
    zenodo_candidates_from_payload,
)
from api_launcher.crawlers import (
    ckan,
    cmr,
    datacite,
    dataset_sources,
    dataverse,
    gbif,
    html_index,
    ncei,
    ogc_records,
    openalex,
    registry as crawler_registry,
    socrata,
    stac,
    zenodo,
)
from api_launcher.crawlers.registry import (
    CrawlerCapabilityMask,
    capability_code_for,
    crawler,
    crawler_specs_by_capability_mask,
)
from api_launcher.crawlers.request_policy import source_request_policy
from api_launcher.dataset_seed_coverage import (
    build_dataset_seed_coverage_report,
    render_dataset_seed_coverage_markdown,
    source_seed_coverage,
)
from api_launcher.downloads.eligibility import looks_like_direct_download
from api_launcher.models import Dataset


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

    def test_source_loader_preserves_optional_seed_discovery_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sources.json"
            path.write_text(
                """
                {
                  "schema_version": 1,
                  "sources": [
                    {
                      "source_id": "sample_index",
                      "provider_id": "sample_provider",
                      "name": "Sample Index",
                      "source_type": "html_file_index",
                      "endpoint_url": "https://example.test/index.html",
                      "seed_discovery_mode": "complete_entry_listing"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            sources = load_dataset_discovery_sources(path)

        self.assertEqual("complete_entry_listing", sources[0].seed_discovery_mode)

    def test_source_loader_preserves_politeness_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sources.json"
            path.write_text(
                """
                {
                  "schema_version": 1,
                  "sources": [
                    {
                      "source_id": "sample_polite_source",
                      "provider_id": "sample_provider",
                      "name": "Sample polite source",
                      "source_type": "html_file_index",
                      "endpoint_url": "https://example.test/index.html",
                      "credential_mode": "user_credential_required",
                      "terms_risk": "terms_review_required",
                      "crawl_timeout_seconds": "3.5",
                      "crawl_max_pages": "7",
                      "crawl_page_size": "25",
                      "crawl_rate_limit_seconds": "0.25"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            sources = load_dataset_discovery_sources(path)

        self.assertEqual(3.5, sources[0].crawl_timeout_seconds)
        self.assertEqual(7, sources[0].crawl_max_pages)
        self.assertEqual(25, sources[0].crawl_page_size)
        self.assertEqual(0.25, sources[0].crawl_rate_limit_seconds)
        self.assertEqual("user_credential_required", sources[0].credential_mode)
        self.assertEqual("terms_review_required", sources[0].terms_risk)
        payload = dataset_sources.source_to_dict(sources[0])
        self.assertEqual(3.5, payload["crawl_timeout_seconds"])
        self.assertEqual(7, payload["crawl_max_pages"])
        self.assertEqual(25, payload["crawl_page_size"])
        self.assertEqual(0.25, payload["crawl_rate_limit_seconds"])
        self.assertEqual("user_credential_required", payload["credential_mode"])
        self.assertEqual("terms_review_required", payload["terms_risk"])

    def test_source_profile_politeness_defaults_reach_default_crawler(self) -> None:
        source = DatasetDiscoverySource(
            source_id="sample_polite_source",
            provider_id="sample_provider",
            name="Sample polite source",
            source_type="unit_politeness",
            endpoint_url="https://example.test/index.html",
            crawl_timeout_seconds=3.5,
            crawl_max_pages=7,
            crawl_page_size=25,
        )
        calls: list[tuple[float, int, int, bool]] = []

        def fake_handler(
            _source: DatasetDiscoverySource,
            timeout: float,
            limit: int,
            _search_terms: tuple[str, ...],
            full_crawl: bool,
            max_pages: int,
        ) -> list[dataset_sources.DatasetCandidate]:
            calls.append((timeout, max_pages, limit, full_crawl))
            return []

        crawler(
            source_type=source.source_type,
            source_family="catalog_search",
            transport="json",
            auth_profile="none",
            result_shape="dataset_list",
        )(fake_handler)
        try:
            crawl_dataset_sources(
                [source],
                DatasetCrawlOptions(
                    timeout=1.0,
                    max_pages=9,
                    full_crawl=True,
                    max_workers=1,
                    min_candidates_per_source_override=0,
                ),
            )
            crawl_dataset_sources(
                [source],
                DatasetCrawlOptions(
                    timeout=1.0,
                    max_pages=2,
                    full_crawl=True,
                    max_workers=1,
                    min_candidates_per_source_override=0,
                ),
            )
        finally:
            crawler_registry._REGISTRY.pop(source.source_type, None)

        self.assertEqual((3.5, 7, 25, True), calls[0])
        self.assertEqual((3.5, 2, 25, True), calls[1])

    def test_paginated_crawler_honors_source_rate_limit_between_pages(self) -> None:
        source = DatasetDiscoverySource(
            source_id="sample_ckan",
            provider_id="sample_provider",
            name="Sample CKAN",
            source_type="ckan_package_search",
            endpoint_url="https://example.test/api/3/action/package_search",
            crawl_rate_limit_seconds=0.25,
        )
        payloads = [
            {
                "result": {
                    "count": 2,
                    "results": [
                        {
                            "name": "dataset-a",
                            "title": "Dataset A",
                            "resources": [],
                        }
                    ],
                }
            },
            {
                "result": {
                    "count": 2,
                    "results": [
                        {
                            "name": "dataset-b",
                            "title": "Dataset B",
                            "resources": [],
                        }
                    ],
                }
            },
        ]

        with patch.object(ckan, "fetch_json", side_effect=payloads), patch.object(ckan, "polite_crawl_delay") as delay:
            output = ckan.paginated_ckan_output(source, "", timeout=1.0, page_size=1, max_pages=2)

        self.assertEqual(2, len(output.candidates))
        delay.assert_called_once_with(0.25)

    def test_source_loader_rejects_unknown_access_policy_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sources.json"
            path.write_text(
                """
                {
                  "schema_version": 1,
                  "sources": [
                    {
                      "source_id": "sample_source",
                      "provider_id": "sample_provider",
                      "name": "Sample Source",
                      "source_type": "ckan_package_search",
                      "endpoint_url": "https://example.test/api/3/action/package_search",
                      "credential_mode": "raw-secret",
                      "terms_risk": "maybe"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            sources = load_dataset_discovery_sources(path)

        self.assertEqual("", sources[0].credential_mode)
        self.assertEqual("", sources[0].terms_risk)
        payload = dataset_sources.source_to_dict(sources[0])
        self.assertNotIn("credential_mode", payload)
        self.assertNotIn("terms_risk", payload)

    def test_source_request_policy_normalizes_request_and_access_fields(self) -> None:
        source = DatasetDiscoverySource(
            source_id="sample_source",
            provider_id="sample_provider",
            name="Sample Source",
            source_type="ckan_package_search",
            endpoint_url="https://example.test/api/3/action/package_search",
            max_results=12,
            crawl_timeout_seconds=5.5,
            crawl_max_pages=3,
            crawl_page_size=25,
            crawl_rate_limit_seconds=0.25,
            credential_mode="user_credential_required",
            terms_risk="terms_review_required",
        )

        policy = source_request_policy(
            source,
            fallback_timeout=20.0,
            fallback_max_pages=10,
            max_results_override=100,
            full_crawl=True,
        )

        self.assertEqual(5.5, policy.timeout_seconds)
        self.assertEqual(3, policy.max_pages)
        self.assertEqual(25, policy.page_size)
        self.assertEqual(0.25, policy.rate_limit_seconds)
        self.assertEqual("user_credential_required", policy.credential_mode)
        self.assertEqual("terms_review_required", policy.terms_risk)

    def test_seed_coverage_marks_search_terms_as_sample_scope(self) -> None:
        source = DatasetDiscoverySource(
            source_id="sample_socrata",
            provider_id="sample_provider",
            name="Sample Socrata",
            source_type="socrata_catalog_search",
            endpoint_url="https://api.us.socrata.com/api/catalog/v1",
            search_terms=("transportation",),
        )

        row = source_seed_coverage(source)

        self.assertEqual("bounded_search_terms", row.current_seed_scope)
        self.assertTrue(row.full_crawl_supported)
        self.assertFalse(row.complete_seed_ready)
        self.assertEqual("run_dataset_discovery_complete_seed_to_ignore_sample_terms", row.next_action)

    def test_seed_coverage_report_counts_complete_entry_sources(self) -> None:
        sources = [
            DatasetDiscoverySource(
                source_id="sample_index",
                provider_id="sample_provider",
                name="Sample Index",
                source_type="html_file_index",
                endpoint_url="https://example.test/index.html",
            ),
            DatasetDiscoverySource(
                source_id="sample_cmr",
                provider_id="sample_provider",
                name="Sample CMR",
                source_type="cmr_collections",
                endpoint_url="https://example.test/cmr",
                search_terms=("cloud",),
            ),
        ]

        report = build_dataset_seed_coverage_report(sources, max_pages=3)

        self.assertEqual(2, report["source_count"])
        self.assertEqual("all_sources_have_complete_seed_attempt_path", report["showcase_status"])
        self.assertEqual(2, report["complete_seed_capable_count"])
        self.assertEqual(1, report["complete_seed_ready_count"])
        self.assertEqual(3, report["max_pages_effective_cap"])
        self.assertEqual(1, report["summary"]["by_current_seed_scope"]["entry_listing"])
        self.assertEqual(1, report["summary"]["by_current_seed_scope"]["bounded_search_terms"])

    def test_seed_coverage_treats_wms_capabilities_as_complete_entry_listing(self) -> None:
        source = DatasetDiscoverySource(
            source_id="sample_wms",
            provider_id="sample_provider",
            name="Sample WMS",
            source_type="ogc_wms_capabilities",
            endpoint_url="https://maps.example.test/wms?service=WMS&request=GetCapabilities",
        )

        row = source_seed_coverage(source)

        self.assertEqual("entry_listing", row.current_seed_scope)
        self.assertTrue(row.full_crawl_supported)
        self.assertTrue(row.complete_seed_ready)
        self.assertEqual("run_full_crawl_or_export_candidates", row.next_action)

    def test_seed_coverage_markdown_renders_showcase_summary(self) -> None:
        source = DatasetDiscoverySource(
            source_id="sample_index",
            provider_id="sample_provider",
            name="Sample Index",
            source_type="html_file_index",
            endpoint_url="https://example.test/index.html",
        )

        markdown = render_dataset_seed_coverage_markdown(build_dataset_seed_coverage_report([source], max_pages=2))

        self.assertIn("資料集 seed 覆蓋展示報告", markdown)
        self.assertIn("具備完整 seed 嘗試路徑", markdown)
        self.assertIn("sample_index", markdown)

    def test_supported_source_types_match_catalog_and_portal_intake(self) -> None:
        from api_launcher.portal_intake import SUPPORTED_CRAWLER_TYPES

        catalog_path = Path(__file__).resolve().parents[1] / "catalog" / "dataset_discovery_sources.json"
        catalog_source_types = {source.source_type for source in load_dataset_discovery_sources(catalog_path)}
        supported_types = set(dataset_sources.SUPPORTED_DATASET_SOURCE_TYPES)

        self.assertTrue(catalog_source_types <= supported_types)
        self.assertEqual(supported_types, SUPPORTED_CRAWLER_TYPES)
        self.assertEqual(set(dataset_sources.SOURCE_CRAWLER_HANDLERS), supported_types)

    def test_crawler_registry_specs_cover_dispatch_table(self) -> None:
        specs = dataset_sources.CRAWLER_SPECS_BY_SOURCE_TYPE
        handlers = dataset_sources.SOURCE_CRAWLER_HANDLERS

        self.assertEqual(set(handlers), set(specs))
        for source_type, handler in handlers.items():
            self.assertIs(handler, specs[source_type].handler)

        catalog_key = ("catalog_search", "json", "none", "dataset_list")
        self.assertIn("ckan_package_search", dataset_sources.CRAWLER_SPEC_MATRIX[catalog_key])
        self.assertEqual("optional_api_key", specs["socrata_catalog_search"].auth_profile)
        self.assertEqual("html", specs["html_file_index"].transport)
        self.assertEqual("layer_list", specs["ogc_wms_capabilities"].result_shape)
        self.assertEqual("api_launcher.crawlers.erddap", specs["erddap_all_datasets"].handler.__module__)
        self.assertEqual("api_launcher.crawlers.html_index", specs["html_file_index"].handler.__module__)

    def test_crawler_registry_partial_dimension_queries(self) -> None:
        catalog_json = dataset_sources.list_crawlers_by_dims(source_family="catalog_search", transport="json")
        catalog_json_types = {spec.source_type for spec in catalog_json}
        self.assertIn("ckan_package_search", catalog_json_types)
        self.assertIn("socrata_catalog_search", catalog_json_types)
        self.assertNotIn("html_file_index", catalog_json_types)
        self.assertNotIn("erddap_all_datasets", catalog_json_types)

        credential_types = {
            spec.source_type
            for spec in dataset_sources.list_crawlers_by_dims(auth_profile="optional_api_key")
        }
        self.assertEqual({"socrata_catalog_search"}, credential_types)

        file_link_types = {
            spec.source_type
            for spec in dataset_sources.list_crawlers_by_dims(result_shape="file_links")
        }
        self.assertEqual({"html_file_index"}, file_link_types)

    def test_crawler_capability_address_groups_existing_handlers(self) -> None:
        index = dataset_sources.CRAWLER_CAPABILITY_INDEX

        self.assertEqual(10, len(index[0b0000]))
        self.assertIn("ckan_package_search", index[0b0000])
        self.assertEqual(("socrata_catalog_search",), index[0b0010])
        self.assertEqual(("erddap_all_datasets",), index[0b1000])
        self.assertEqual(("html_file_index", "ogc_wms_capabilities"), index[0b1101])

        specs = dataset_sources.CRAWLER_SPECS_BY_SOURCE_TYPE
        self.assertEqual("0000", specs["ckan_package_search"].capability_binary)
        self.assertEqual("0010", specs["socrata_catalog_search"].capability_binary)
        self.assertEqual("1101", specs["html_file_index"].capability_binary)

    def test_crawler_capability_mask_supports_prefix_queries(self) -> None:
        catalog_json_mask = CrawlerCapabilityMask.from_prefix(0b0000, prefix_len=2)
        source_types = {spec.source_type for spec in crawler_specs_by_capability_mask(catalog_json_mask)}

        self.assertIn("ckan_package_search", source_types)
        self.assertIn("socrata_catalog_search", source_types)
        self.assertNotIn("html_file_index", source_types)
        self.assertNotIn("erddap_all_datasets", source_types)

        credential_mask = CrawlerCapabilityMask(bits=0b0010, mask=0b0010)
        credential_types = {spec.source_type for spec in crawler_specs_by_capability_mask(credential_mask)}
        self.assertEqual({"socrata_catalog_search"}, credential_types)

    def test_crawler_capability_code_rejects_unknown_dimension(self) -> None:
        with self.assertRaises(ValueError):
            capability_code_for("unknown_family", "json", "none", "dataset_list")

    def test_crawler_registry_rejects_duplicate_source_type(self) -> None:
        with self.assertRaises(ValueError):
            crawler(
                source_type="ncei_search",
                source_family="catalog_search",
                transport="json",
                auth_profile="none",
                result_shape="dataset_list",
            )(ncei_candidates_from_payload)  # type: ignore[arg-type]

    def test_crawler_registry_rejects_handler_signature_mismatch(self) -> None:
        def bad_handler(_source: DatasetDiscoverySource) -> list[dataset_sources.DatasetCandidate]:
            return []

        with self.assertRaisesRegex(TypeError, "six-argument signature"):
            crawler(
                source_type="unit_bad_signature",
                source_family="catalog_search",
                transport="json",
                auth_profile="none",
                result_shape="dataset_list",
            )(bad_handler)  # type: ignore[arg-type]

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

    def test_openalex_payload_becomes_reviewable_dataset_candidate(self) -> None:
        source = DatasetDiscoverySource(
            source_id="openalex_dataset_works_search",
            provider_id="openalex",
            name="OpenAlex dataset works",
            source_type="openalex_works_search",
            endpoint_url="https://api.openalex.org/works",
            categories=("research_metadata", "openalex"),
            geographic_scope="global",
        )
        payload = {
            "meta": {"count": 1, "next_cursor": "abc"},
            "results": [
                {
                    "id": "https://openalex.org/W1650569836",
                    "doi": "https://doi.org/10.1163/example",
                    "display_name": "Climate Change Synthesis Report Dataset",
                    "type": "dataset",
                    "publication_year": 2024,
                    "publication_date": "2024-01-01",
                    "updated_date": "2024-05-01T00:00:00.000Z",
                    "primary_location": {
                        "landing_page_url": "https://doi.org/10.1163/example",
                        "source": {"display_name": "Example Repository"},
                    },
                    "open_access": {"is_oa": True, "oa_status": "gold"},
                    "cited_by_count": 12,
                    "authorships": [
                        {
                            "author": {"display_name": "Ada Researcher"},
                            "institutions": [{"display_name": "Example University"}],
                        }
                    ],
                    "concepts": [{"display_name": "Climate change"}, {"display_name": "Satellite imagery"}],
                    "keywords": [{"keyword": "raster"}, {"keyword": "climate"}],
                }
            ],
        }

        candidates = openalex_candidates_from_payload(source, payload, "https://api.openalex.org/works?filter=type:dataset", 5)

        self.assertEqual(1, len(candidates))
        dataset = candidates[0].dataset
        self.assertEqual("openalex", dataset.provider_id)
        self.assertEqual("10.1163_example", dataset.dataset_id)
        self.assertEqual("raster_or_grid", dataset.metadata["data_family"])
        self.assertEqual("openalex_work", dataset.native_format)
        self.assertEqual("needs_review", dataset.metadata["candidate_status"])
        self.assertEqual("https://api.openalex.org/works/W1650569836", dataset.api_url)
        self.assertEqual(("Ada Researcher",), dataset.metadata["authors"])
        self.assertEqual(("Example University",), dataset.metadata["institutions"])

    def test_openalex_full_crawl_reports_remote_has_more_when_page_cap_stops(self) -> None:
        source = DatasetDiscoverySource(
            source_id="openalex_dataset_works_search",
            provider_id="openalex",
            name="OpenAlex dataset works",
            source_type="openalex_works_search",
            endpoint_url="https://api.openalex.org/works",
        )

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "meta": {"next_cursor": "next-page-cursor"},
                "results": [
                    {
                        "id": "https://openalex.org/W1650569836",
                        "doi": "https://doi.org/10.1163/example",
                        "display_name": "Climate Change Synthesis Report Dataset",
                        "type": "dataset",
                    }
                ],
            }

        with patch("api_launcher.crawlers.openalex.fetch_json", side_effect=fake_fetch_json):
            output = openalex.openalex_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("next-page-cursor", output.remote_next_page_token)

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

    def test_cmr_collections_payload_becomes_dataset_candidates(self) -> None:
        source = DatasetDiscoverySource(
            source_id="nasa_cmr_collections",
            provider_id="nasa_earthdata",
            name="NASA CMR",
            source_type="cmr_collections",
            endpoint_url="https://cmr.example.test/search/collections.json",
            categories=("nasa", "earth_observation"),
        )
        payload = {
            "feed": {
                "entry": [
                    {
                        "id": "C123-PODAAC",
                        "short_name": "MUR-JPL-L4-GLOB-v4.1",
                        "version_id": "4.1",
                        "title": "MUR sea surface temperature",
                        "summary": "Global daily sea surface temperature grid in NetCDF.",
                        "time_start": "2002-06-01T00:00:00Z",
                        "time_end": "2026-01-01T00:00:00Z",
                        "data_center": "PODAAC",
                        "links": [{"rel": "metadata", "href": "https://example.test/metadata"}],
                    }
                ]
            }
        }

        candidates = cmr_candidates_from_payload(source, payload, source.endpoint_url, 3)

        self.assertEqual(1, len(candidates))
        dataset = candidates[0].dataset
        self.assertEqual("nasa_earthdata", dataset.provider_id)
        self.assertEqual("mur-jpl-l4-glob-v4.1-4.1", dataset.dataset_id)
        self.assertEqual("grid_or_array", dataset.metadata["data_family"])
        self.assertIn("collection_concept_id=C123-PODAAC", dataset.api_url)

    def test_cmr_full_crawl_reports_remote_has_more_when_page_cap_stops(self) -> None:
        source = DatasetDiscoverySource(
            source_id="nasa_cmr_collections",
            provider_id="nasa_earthdata",
            name="NASA CMR",
            source_type="cmr_collections",
            endpoint_url="https://cmr.example.test/search/collections.json",
        )

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "feed": {
                    "entry": [
                        {
                            "id": "C123-PODAAC",
                            "short_name": "MUR-JPL-L4-GLOB-v4.1",
                            "version_id": "4.1",
                            "title": "MUR sea surface temperature",
                        }
                    ]
                }
            }

        with patch("api_launcher.crawlers.cmr.fetch_json", side_effect=fake_fetch_json):
            output = cmr.cmr_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("2", output.remote_next_page_token)

    def test_stac_collections_payload_can_be_filtered_by_terms(self) -> None:
        source = DatasetDiscoverySource(
            source_id="planetary_stac",
            provider_id="microsoft_planetary_computer",
            name="Planetary Computer STAC",
            source_type="stac_collections",
            endpoint_url="https://planetary.example.test/collections",
            categories=("stac", "satellite"),
        )
        payload = {
            "collections": [
                {
                    "id": "sentinel-2-l2a",
                    "title": "Sentinel-2 Level-2A",
                    "description": "Satellite imagery and cloud mask assets.",
                    "keywords": ["sentinel", "imagery"],
                    "stac_version": "1.0.0",
                    "extent": {"temporal": {"interval": [["2015-01-01T00:00:00Z", None]]}},
                    "links": [{"rel": "items", "href": "https://example.test/items"}],
                    "assets": {"thumbnail": {}, "visual": {}},
                },
                {"id": "soil", "title": "Soil maps", "description": "Vector soil polygons"},
            ]
        }

        candidates = stac_candidates_from_payload(source, payload, source.endpoint_url, 5, ("cloud",))

        self.assertEqual(1, len(candidates))
        dataset = candidates[0].dataset
        self.assertEqual("sentinel-2-l2a", dataset.dataset_id)
        self.assertEqual("raster_or_grid", dataset.metadata["data_family"])
        self.assertEqual("https://example.test/items", dataset.api_url)

    def test_gbif_dataset_search_payload_becomes_biodiversity_candidate(self) -> None:
        source = DatasetDiscoverySource(
            source_id="gbif_dataset_search",
            provider_id="gbif",
            name="GBIF dataset search",
            source_type="gbif_dataset_search",
            endpoint_url="https://api.gbif.example.test/v1/dataset/search",
            categories=("biodiversity", "species"),
        )
        payload = {
            "results": [
                {
                    "key": "abc-123",
                    "title": "Global species occurrence dataset",
                    "description": "Occurrence records for species observations.",
                    "type": "OCCURRENCE",
                    "license": "CC_BY_4_0",
                    "keywords": ["occurrence"],
                    "recordCount": 42,
                }
            ]
        }

        candidates = gbif_candidates_from_payload(source, payload, source.endpoint_url, 5)

        dataset = candidates[0].dataset
        self.assertEqual("abc-123", dataset.dataset_id)
        self.assertEqual("biodiversity_occurrence", dataset.metadata["data_family"])
        self.assertEqual("https://api.gbif.org/v1/dataset/abc-123", dataset.api_url)

    def test_dataverse_search_payload_becomes_repository_candidate(self) -> None:
        source = DatasetDiscoverySource(
            source_id="harvard_dataverse_search",
            provider_id="harvard_dataverse",
            name="Harvard Dataverse",
            source_type="dataverse_search",
            endpoint_url="https://dataverse.example.test/api/search",
            categories=("research_repository", "dataverse"),
        )
        payload = {
            "data": {
                "total_count": 1,
                "items": [
                    {
                        "name": "Climate survey dataset",
                        "global_id": "doi:10.7910/DVN/ABC123",
                        "description": "Daily climate observations and time series.",
                        "keywords": ["climate"],
                        "subjects": ["Earth and Environmental Sciences"],
                        "url": "https://doi.org/10.7910/DVN/ABC123",
                        "fileCount": 3,
                        "majorVersion": 2,
                        "minorVersion": 1,
                    }
                ],
            }
        }

        candidates = dataverse_candidates_from_payload(source, payload, source.endpoint_url, 5)

        dataset = candidates[0].dataset
        self.assertEqual("doi_10.7910_dvn_abc123", dataset.dataset_id)
        self.assertEqual("dataverse_dataset", dataset.native_format)
        self.assertEqual("timeseries", dataset.metadata["data_family"])
        self.assertEqual(3, dataset.metadata["file_count"])

    def test_zenodo_records_payload_becomes_repository_candidate_without_direct_download(self) -> None:
        source = DatasetDiscoverySource(
            source_id="zenodo_records_search",
            provider_id="zenodo",
            name="Zenodo",
            source_type="zenodo_records_search",
            endpoint_url="https://zenodo.example.test/api/records",
            categories=("research_repository", "zenodo"),
        )
        payload = {
            "hits": {
                "hits": [
                    {
                        "id": 123,
                        "recid": "123",
                        "doi": "10.5281/zenodo.123",
                        "title": "High-resolution climate raster bundle",
                        "modified": "2026-01-02T00:00:00+00:00",
                        "links": {
                            "self": "https://zenodo.example.test/api/records/123",
                            "self_html": "https://zenodo.example.test/records/123",
                            "archive": "https://zenodo.example.test/api/records/123/files-archive",
                        },
                        "metadata": {
                            "title": "High-resolution climate raster bundle",
                            "description": "<p>Satellite cloud imagery and raster grids.</p>",
                            "keywords": ["cloud", "raster"],
                            "resource_type": {"title": "Dataset", "type": "dataset"},
                            "license": {"id": "cc-by-4.0"},
                        },
                        "files": [
                            {
                                "key": "huge.zip",
                                "size": 87000000000,
                                "checksum": "md5:abc",
                                "links": {"self": "https://zenodo.example.test/api/records/123/files/huge.zip/content"},
                            }
                        ],
                    }
                ]
            }
        }

        candidates = zenodo_candidates_from_payload(source, payload, source.endpoint_url, 5)

        dataset = candidates[0].dataset
        self.assertEqual("10.5281_zenodo.123", dataset.dataset_id)
        self.assertEqual("zenodo_record", dataset.native_format)
        self.assertEqual("raster_or_grid", dataset.metadata["data_family"])
        self.assertEqual("https://zenodo.example.test/api/records/123", dataset.api_url)
        self.assertEqual("https://zenodo.example.test/api/records/123/files/huge.zip/content", dataset.metadata["resources"][0]["download_url"])
        self.assertEqual("huge.zip", dataset.metadata["files"][0]["key"])

    def test_zenodo_full_crawl_reports_remote_has_more_when_page_cap_stops(self) -> None:
        source = DatasetDiscoverySource(
            source_id="zenodo_records_search",
            provider_id="zenodo",
            name="Zenodo",
            source_type="zenodo_records_search",
            endpoint_url="https://zenodo.example.test/api/records",
        )

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "hits": {
                    "hits": [
                        {
                            "id": 123,
                            "recid": "123",
                            "title": "High-resolution climate raster bundle",
                            "links": {"self": "https://zenodo.example.test/api/records/123"},
                            "metadata": {"resource_type": {"type": "dataset"}},
                        }
                    ]
                },
                "links": {"next": "https://zenodo.example.test/api/records?page=2"},
            }

        with patch("api_launcher.crawlers.zenodo.fetch_json", side_effect=fake_fetch_json):
            output = zenodo.zenodo_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("https://zenodo.example.test/api/records?page=2", output.remote_next_page_token)

    def test_datacite_dois_payload_becomes_research_dataset_candidate(self) -> None:
        source = DatasetDiscoverySource(
            source_id="datacite_dois_search",
            provider_id="datacite",
            name="DataCite DOI Search",
            source_type="datacite_dois",
            endpoint_url="https://api.datacite.example.test/dois",
            categories=("doi", "research_data", "metadata"),
            geographic_scope="global",
        )
        payload = {
            "data": [
                {
                    "id": "10.1234/example.dataset",
                    "type": "dois",
                    "attributes": {
                        "doi": "10.1234/example.dataset",
                        "titles": [{"title": "Global cloud imagery training dataset"}],
                        "publisher": "Example Repository",
                        "publicationYear": 2026,
                        "subjects": [{"subject": "satellite imagery"}, {"subject": "cloud"}],
                        "formats": ["GeoTIFF", "NetCDF"],
                        "types": {"resourceTypeGeneral": "Dataset", "schemaOrg": "Dataset"},
                        "descriptions": [{"description": "<p>Satellite cloud raster grids for research.</p>"}],
                        "url": "https://example.test/datasets/cloud",
                        "contentUrl": "https://data.example.test/cloud/cloud_sample.nc",
                        "rightsList": [{"rightsUri": "https://creativecommons.org/licenses/by/4.0/"}],
                        "updated": "2026-05-01T00:00:00Z",
                        "state": "findable",
                        "viewCount": 4,
                        "downloadCount": 2,
                    },
                    "relationships": {"client": {"data": {"id": "example.repo", "type": "clients"}}},
                }
            ]
        }

        candidates = datacite_candidates_from_payload(source, payload, source.endpoint_url, 5)

        dataset = candidates[0].dataset
        self.assertEqual("datacite", dataset.provider_id)
        self.assertEqual("10.1234_example.dataset", dataset.dataset_id)
        self.assertEqual("raster_or_grid", dataset.metadata["data_family"])
        self.assertEqual("netcdf", dataset.native_format)
        self.assertEqual("https://api.datacite.example.test/dois/10.1234%2Fexample.dataset", dataset.api_url)
        self.assertEqual("example.repo", dataset.metadata["client_id"])
        self.assertEqual("https://data.example.test/cloud/cloud_sample.nc", dataset.metadata["content_url"])
        self.assertEqual("https://data.example.test/cloud/cloud_sample.nc", dataset.metadata["resources"][0]["download_url"])
        self.assertEqual("nc", dataset.metadata["resources"][0]["format"])

    def test_datacite_full_crawl_reports_remote_has_more_when_page_cap_stops(self) -> None:
        source = DatasetDiscoverySource(
            source_id="datacite_dois_search",
            provider_id="datacite",
            name="DataCite DOI Search",
            source_type="datacite_dois",
            endpoint_url="https://api.datacite.example.test/dois",
        )

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "data": [
                    {
                        "id": "10.1234/example.dataset",
                        "type": "dois",
                        "attributes": {
                            "doi": "10.1234/example.dataset",
                            "titles": [{"title": "Global cloud imagery training dataset"}],
                            "types": {"resourceTypeGeneral": "Dataset"},
                        },
                    }
                ],
                "links": {"next": "https://api.datacite.example.test/dois?page[number]=2"},
            }

        with patch("api_launcher.crawlers.datacite.fetch_json", side_effect=fake_fetch_json):
            output = datacite.datacite_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("https://api.datacite.example.test/dois?page[number]=2", output.remote_next_page_token)

    def test_ncei_full_crawl_reports_remote_has_more_when_page_cap_stops(self) -> None:
        source = DatasetDiscoverySource(
            source_id="noaa_ncei_dataset_search",
            provider_id="noaa_ncei_access_data",
            name="NOAA NCEI Search",
            source_type="ncei_search",
            endpoint_url="https://example.test/search",
        )

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "results": [
                    {
                        "id": "automatic-identification-system-ais",
                        "name": "Automatic Identification System AIS",
                        "description": "AIS vessel traffic data in CSV.",
                        "formats": [{"name": "csv"}],
                    }
                ]
            }

        with patch("api_launcher.crawlers.ncei.fetch_json", side_effect=fake_fetch_json):
            output = ncei.ncei_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("1", output.remote_next_page_token)

    def test_gbif_full_crawl_reports_remote_has_more_when_page_cap_stops(self) -> None:
        source = DatasetDiscoverySource(
            source_id="gbif_dataset_search",
            provider_id="gbif",
            name="GBIF dataset search",
            source_type="gbif_dataset_search",
            endpoint_url="https://api.gbif.example.test/v1/dataset/search",
        )

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "results": [
                    {
                        "key": "abc-123",
                        "title": "Global species occurrence dataset",
                        "type": "OCCURRENCE",
                    }
                ],
                "endOfRecords": False,
            }

        with patch("api_launcher.crawlers.gbif.fetch_json", side_effect=fake_fetch_json):
            output = gbif.gbif_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("1", output.remote_next_page_token)

    def test_dataverse_full_crawl_reports_remote_has_more_when_page_cap_stops(self) -> None:
        source = DatasetDiscoverySource(
            source_id="harvard_dataverse_search",
            provider_id="harvard_dataverse",
            name="Harvard Dataverse",
            source_type="dataverse_search",
            endpoint_url="https://dataverse.example.test/api/search",
        )

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "data": {
                    "total_count": 2,
                    "items": [
                        {
                            "name": "Climate survey dataset",
                            "global_id": "doi:10.7910/DVN/ABC123",
                            "description": "Daily climate observations.",
                        }
                    ],
                }
            }

        with patch("api_launcher.crawlers.dataverse.fetch_json", side_effect=fake_fetch_json):
            output = dataverse.dataverse_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("1", output.remote_next_page_token)

    def test_ogc_records_full_crawl_reports_remote_has_more_when_next_link_hits_page_cap(self) -> None:
        source = DatasetDiscoverySource(
            source_id="ogc_records_search",
            provider_id="sample_geospatial_catalog",
            name="Sample OGC API Records",
            source_type="ogc_api_records",
            endpoint_url="https://records.example.test/collections/metadata/items",
        )

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "cloud-raster-record",
                        "properties": {"title": "Global satellite cloud raster archive"},
                        "links": [{"rel": "self", "href": "https://records.example.test/items/cloud-raster-record"}],
                    }
                ],
                "links": [{"rel": "next", "href": "https://records.example.test/collections/metadata/items?page=2"}],
            }

        with patch("api_launcher.crawlers.ogc_records.fetch_json", side_effect=fake_fetch_json):
            output = ogc_records.ogc_records_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("https://records.example.test/collections/metadata/items?page=2", output.remote_next_page_token)

    def test_stac_full_crawl_reports_remote_has_more_when_next_link_hits_page_cap(self) -> None:
        source = DatasetDiscoverySource(
            source_id="planetary_stac",
            provider_id="microsoft_planetary_computer",
            name="Planetary Computer STAC",
            source_type="stac_collections",
            endpoint_url="https://planetary.example.test/collections",
        )

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "collections": [
                    {
                        "id": "sentinel-2-l2a",
                        "title": "Sentinel-2 Level-2A",
                        "description": "Satellite imagery.",
                    }
                ],
                "links": [{"rel": "next", "href": "https://planetary.example.test/collections?page=2"}],
            }

        with patch("api_launcher.crawlers.stac.fetch_json", side_effect=fake_fetch_json):
            output = stac.stac_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("https://planetary.example.test/collections?page=2", output.remote_next_page_token)

    def test_ogc_api_records_payload_becomes_reviewable_catalog_candidate(self) -> None:
        source = DatasetDiscoverySource(
            source_id="ogc_records_search",
            provider_id="sample_geospatial_catalog",
            name="Sample OGC API Records",
            source_type="ogc_api_records",
            endpoint_url="https://records.example.test/collections/metadata/items",
            categories=("ogc", "records", "geospatial"),
            geographic_scope="global",
        )
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "cloud-raster-record",
                    "geometry": {"type": "Polygon", "coordinates": []},
                    "properties": {
                        "title": "Global satellite cloud raster archive",
                        "description": "Cloud imagery grids distributed as GeoTIFF and NetCDF.",
                        "keywords": ["cloud", "satellite"],
                        "themes": [{"title": "Earth observation"}],
                        "formats": ["GeoTIFF", "NetCDF"],
                        "updated": "2026-05-01T00:00:00Z",
                        "time": {"interval": [["2020-01-01T00:00:00Z", "2026-01-01T00:00:00Z"]]},
                        "license": "https://creativecommons.org/licenses/by/4.0/",
                    },
                    "links": [
                        {"rel": "self", "href": "https://records.example.test/items/cloud-raster-record", "type": "application/geo+json"},
                        {"rel": "alternate", "href": "https://records.example.test/catalog/cloud-raster-record", "type": "text/html"},
                    ],
                }
            ],
        }

        candidates = ogc_records_candidates_from_payload(source, payload, source.endpoint_url, 5)

        dataset = candidates[0].dataset
        self.assertEqual("sample_geospatial_catalog", dataset.provider_id)
        self.assertEqual("cloud-raster-record", dataset.dataset_id)
        self.assertEqual("raster_or_grid", dataset.metadata["data_family"])
        self.assertEqual("netcdf", dataset.native_format)
        self.assertEqual("Polygon", dataset.metadata["geometry_type"])
        self.assertEqual("https://records.example.test/items/cloud-raster-record", dataset.api_url)

    def test_ogc_api_collections_payload_becomes_collection_candidates(self) -> None:
        source = DatasetDiscoverySource(
            source_id="ogc_collections",
            provider_id="sample_ogc_api",
            name="Sample OGC API",
            source_type="ogc_api_records",
            endpoint_url="https://geo.example.test/collections",
            docs_url="https://geo.example.test/docs",
            categories=("ogc", "gis"),
            geographic_scope="regional",
        )
        payload = {
            "collections": [
                {
                    "id": "roads",
                    "title": "Road centerlines",
                    "description": "GIS vector road network features as GeoJSON.",
                    "itemType": "feature",
                    "formats": ["GeoJSON"],
                    "extent": {"temporal": {"interval": [["2020-01-01T00:00:00Z", None]]}},
                    "links": [
                        {
                            "rel": "items",
                            "href": "https://geo.example.test/collections/roads/items",
                            "type": "application/geo+json",
                        },
                        {
                            "rel": "self",
                            "href": "https://geo.example.test/collections/roads",
                            "type": "application/json",
                        },
                    ],
                }
            ],
        }

        candidates = ogc_records_candidates_from_payload(source, payload, source.endpoint_url, 5)

        dataset = candidates[0].dataset
        self.assertEqual("roads", dataset.dataset_id)
        self.assertEqual("gis", dataset.metadata["data_family"])
        self.assertEqual("geojson", dataset.native_format)
        self.assertEqual("https://geo.example.test/collections/roads/items", dataset.api_url)
        self.assertEqual("https://geo.example.test/collections/roads", dataset.landing_url)
        self.assertEqual("roads", dataset.metadata["ogc_collection_id"])
        self.assertEqual("2020-01-01T00:00:00Z", dataset.temporal_coverage)
        self.assertEqual(("OGC API collection", "collection: roads"), candidates[0].evidence)

    def test_ogc_api_records_keeps_non_http_broker_links_out_of_primary_api_url(self) -> None:
        source = DatasetDiscoverySource(
            source_id="wmo_wis2_gdc_records",
            provider_id="wmo_wis2_gdc",
            name="WMO WIS2 Global Discovery Catalogue records",
            source_type="ogc_api_records",
            endpoint_url="https://wis2-gdc.example.test/collections/wis2-discovery-metadata/items",
            docs_url="https://wis2-gdc.example.test/docs",
            categories=("wmo", "wis2", "ogc_api_records", "weather"),
            geographic_scope="global",
        )
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "urn:wmo:md:example:forecast.global",
                    "properties": {
                        "title": "Global model forecast notifications",
                        "description": "Forecast metadata delivered through WIS2 broker notifications.",
                        "formats": ["GRIB2"],
                    },
                    "links": [
                        {
                            "rel": "items",
                            "href": "mqtts://everyone:everyone@example-broker.test:8883",
                            "title": "WIS2 broker notifications",
                            "type": "application/geo+json",
                        },
                        {
                            "rel": "related",
                            "href": "https://example.test/model-docs",
                            "title": "Documentation",
                            "type": "text/html",
                        },
                    ],
                }
            ],
        }

        candidates = ogc_records_candidates_from_payload(source, payload, source.endpoint_url, 5)

        dataset = candidates[0].dataset
        self.assertEqual("urn_wmo_md_example_forecast.global", dataset.dataset_id)
        self.assertEqual("grib2", dataset.native_format)
        self.assertEqual(source.endpoint_url, dataset.api_url)
        self.assertEqual("mqtts://everyone:everyone@example-broker.test:8883", dataset.metadata["links"][0]["href"])

    def test_ogc_api_records_search_url_uses_q_and_limit(self) -> None:
        url = ogc_records_search_url("https://records.example.test/items?f=json", "cloud imagery", 25)

        self.assertIn("f=json", url)
        self.assertIn("limit=25", url)
        self.assertIn("q=cloud+imagery", url)

    def test_ogc_wms_capabilities_xml_becomes_layer_candidates(self) -> None:
        source = DatasetDiscoverySource(
            source_id="sample_wms",
            provider_id="sample_geo",
            name="Sample WMS",
            source_type="ogc_wms_capabilities",
            endpoint_url="https://maps.example.test/wms",
            categories=("gis", "wms"),
            geographic_scope="global",
        )
        xml = """
        <WMS_Capabilities xmlns="http://www.opengis.net/wms"
          xmlns:xlink="http://www.w3.org/1999/xlink">
          <Service>
            <Title>Sample WMS Service</Title>
            <OnlineResource xlink:href="https://maps.example.test/service-info"/>
          </Service>
          <Capability>
            <Request><GetMap><DCPType><HTTP><Get>
              <OnlineResource xlink:href="https://maps.example.test/wms?"/>
            </Get></HTTP></DCPType></GetMap></Request>
            <Layer>
              <Title>Root</Title>
              <Layer>
                <Name>bathymetry_2026</Name>
                <Title>Bathymetry 2026</Title>
                <Abstract>Global ocean bathymetry layer</Abstract>
                <KeywordList><Keyword>bathymetry</Keyword><Keyword>raster</Keyword></KeywordList>
                <EX_GeographicBoundingBox>
                  <westBoundLongitude>-180</westBoundLongitude>
                  <eastBoundLongitude>180</eastBoundLongitude>
                  <southBoundLatitude>-90</southBoundLatitude>
                  <northBoundLatitude>90</northBoundLatitude>
                </EX_GeographicBoundingBox>
              </Layer>
            </Layer>
          </Capability>
        </WMS_Capabilities>
        """

        candidates = ogc_wms_candidates_from_xml(source, xml, "https://maps.example.test/wms?service=WMS&request=GetCapabilities", 5)

        self.assertEqual(1, len(candidates))
        dataset = candidates[0].dataset
        self.assertEqual("sample_geo", dataset.provider_id)
        self.assertEqual("bathymetry_2026", dataset.dataset_id)
        self.assertEqual("wms", dataset.native_format)
        self.assertEqual("gis", dataset.metadata["data_family"])
        self.assertEqual("Sample WMS Service", dataset.metadata["service_title"])
        self.assertEqual("bathymetry_2026", dataset.metadata["wms_layer_name"])
        self.assertEqual("https://maps.example.test/wms?", dataset.metadata["wms_get_map_url"])
        self.assertEqual(-180.0, dataset.metadata["bbox"]["west"])
        self.assertEqual(
            1,
            len(
                ogc_wms_candidates_from_xml(
                    source,
                    xml,
                    "https://maps.example.test/wms?service=WMS&request=GetCapabilities",
                    5,
                    search_terms=("bathymetry",),
                )
            ),
        )
        self.assertEqual(
            [],
            ogc_wms_candidates_from_xml(
                source,
                xml,
                "https://maps.example.test/wms?service=WMS&request=GetCapabilities",
                5,
                search_terms=("roads",),
            ),
        )

    def test_ogc_wms_capabilities_url_preserves_explicit_request(self) -> None:
        explicit = "https://maps.example.test/wms?service=WMS&request=GetCapabilities"
        uppercase = "https://maps.example.test/wms?SERVICE=WMS&REQUEST=GetCapabilities"

        self.assertEqual(explicit, ogc_wms_capabilities_url(explicit))
        self.assertEqual(uppercase, ogc_wms_capabilities_url(uppercase))
        self.assertEqual(
            "https://maps.example.test/wms?service=WMS&request=GetCapabilities",
            ogc_wms_capabilities_url("https://maps.example.test/wms"),
        )
        self.assertEqual(
            "https://maps.example.test/wms?layers=roads&service=WMS&request=GetCapabilities",
            ogc_wms_capabilities_url("https://maps.example.test/wms?layers=roads#preview"),
        )
        self.assertEqual(
            "https://maps.example.test/wms?layers=roads&service=WMS&request=GetCapabilities",
            ogc_wms_capabilities_url(
                "https://maps.example.test/wms?layers=roads&service=WFS&request=GetCapabilities#preview"
            ),
        )

    def test_socrata_catalog_payload_becomes_reviewable_dataset_candidate(self) -> None:
        source = DatasetDiscoverySource(
            source_id="nyc_open_data_socrata_catalog",
            provider_id="nyc_open_data_socrata",
            name="NYC Open Data Socrata catalog",
            source_type="socrata_catalog_search",
            endpoint_url="https://api.us.socrata.com/api/catalog/v1?domains=data.cityofnewyork.us",
            categories=("open_data", "socrata", "city"),
            geographic_scope="nyc/us",
        )
        payload = {
            "results": [
                {
                    "resource": {
                        "id": "t29m-gskq",
                        "name": "2018 Yellow Taxi Trip Data",
                        "description": "Each row is a taxi trip with pickup time, dropoff time, trip distance, fares, and locations.",
                        "type": "dataset",
                        "updatedAt": "2023-12-14T20:46:24.000Z",
                        "data_updated_at": "2019-04-05T15:42:41.000Z",
                        "attribution": "Taxi and Limousine Commission",
                        "columns_name": ["tpep_pickup_datetime", "trip_distance", "PULocationID", "DOLocationID"],
                        "columns_field_name": ["tpep_pickup_datetime", "trip_distance", "pulocationid", "dolocationid"],
                        "columns_datatype": ["Calendar date", "Number", "Number", "Number"],
                    },
                    "metadata": {
                        "domain": "data.cityofnewyork.us",
                        "license": "Public Domain",
                    },
                    "classification": {
                        "domain_category": "Transportation",
                        "domain_tags": ["taxi", "trip", "time series"],
                    },
                    "permalink": "https://data.cityofnewyork.us/d/t29m-gskq",
                    "link": "https://data.cityofnewyork.us/Transportation/2018-Yellow-Taxi-Trip-Data/t29m-gskq",
                }
            ],
            "resultSetSize": 1,
        }

        candidates = socrata_catalog_candidates_from_payload(source, payload, source.endpoint_url, 5)

        dataset = candidates[0].dataset
        self.assertEqual("nyc_open_data_socrata", dataset.provider_id)
        self.assertEqual("t29m-gskq", dataset.dataset_id)
        self.assertEqual("timeseries", dataset.metadata["data_family"])
        self.assertEqual("socrata_resource", dataset.native_format)
        self.assertEqual("https://data.cityofnewyork.us/api/views/t29m-gskq", dataset.api_url)
        self.assertFalse(looks_like_direct_download(dataset.api_url))
        self.assertEqual("https://data.cityofnewyork.us/resource/t29m-gskq.json", dataset.metadata["socrata_resource_url"])
        self.assertEqual(4, dataset.metadata["column_count"])

    def test_socrata_catalog_search_url_overrides_limit_and_adds_offset(self) -> None:
        url = socrata_catalog_search_url(
            "https://api.us.socrata.com/api/catalog/v1?domains=data.cityofnewyork.us&limit=999",
            "taxi trips",
            25,
            offset=50,
        )

        self.assertIn("domains=data.cityofnewyork.us", url)
        self.assertIn("limit=25", url)
        self.assertIn("offset=50", url)
        self.assertIn("only=dataset", url)
        self.assertIn("q=taxi+trips", url)
        self.assertNotIn("limit=999", url)

    def test_socrata_full_crawl_reports_remote_has_more_when_page_cap_stops(self) -> None:
        source = DatasetDiscoverySource(
            source_id="nyc_open_data_socrata_catalog",
            provider_id="nyc_open_data_socrata",
            name="NYC Open Data Socrata catalog",
            source_type="socrata_catalog_search",
            endpoint_url="https://api.us.socrata.com/api/catalog/v1?domains=data.cityofnewyork.us",
        )
        original_fetch_json = socrata.fetch_json

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "results": [
                    {
                        "resource": {
                            "id": "t29m-gskq",
                            "name": "2018 Yellow Taxi Trip Data",
                            "type": "dataset",
                            "columns_name": ["trip_distance"],
                            "columns_field_name": ["trip_distance"],
                            "columns_datatype": ["Number"],
                        },
                        "metadata": {"domain": "data.cityofnewyork.us"},
                    }
                ],
                "resultSetSize": 2,
            }

        socrata.fetch_json = fake_fetch_json
        try:
            output = socrata.socrata_catalog_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )
        finally:
            socrata.fetch_json = original_fetch_json

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("1", output.remote_next_page_token)

    def test_ckan_package_search_payload_extracts_resource_metadata(self) -> None:
        source = DatasetDiscoverySource(
            source_id="data_gov_package_search",
            provider_id="data_gov",
            name="Data.gov CKAN",
            source_type="ckan_package_search",
            endpoint_url="https://api.gsa.example.test/action/package_search",
            categories=("open_data", "government"),
        )
        payload = {
            "result": {
                "results": [
                    {
                        "id": "pkg-1",
                        "name": "ocean-buoy-observations",
                        "title": "Ocean buoy observations",
                        "notes": "Hourly buoy time series in CSV.",
                        "tags": [{"name": "ocean"}, {"display_name": "time series"}],
                        "resources": [{"name": "CSV", "format": "CSV", "url": "https://example.test/buoy.csv"}],
                    }
                ]
            }
        }

        candidates = ckan_candidates_from_payload(source, payload, source.endpoint_url, 5)

        dataset = candidates[0].dataset
        self.assertEqual("ocean-buoy-observations", dataset.dataset_id)
        self.assertEqual("csv", dataset.native_format)
        self.assertEqual("https://example.test/buoy.csv", dataset.api_url)

    def test_ckan_full_crawl_reports_remote_has_more_when_page_cap_stops(self) -> None:
        source = DatasetDiscoverySource(
            source_id="data_gov_package_search",
            provider_id="data_gov",
            name="Data.gov CKAN",
            source_type="ckan_package_search",
            endpoint_url="https://catalog.data.gov/api/3/action/package_search",
        )
        original_fetch_json = ckan.fetch_json

        def fake_fetch_json(_url: str, timeout: float = 0) -> dict[str, object]:
            return {
                "success": True,
                "result": {
                    "count": 2,
                    "results": [
                        {
                            "name": "water-quality",
                            "title": "Water Quality",
                            "tags": [{"name": "water"}],
                            "resources": [{"format": "CSV", "url": "https://example.test/water.csv"}],
                        }
                    ],
                },
            }

        ckan.fetch_json = fake_fetch_json
        try:
            output = ckan.ckan_candidates_for_source(
                source,
                timeout=1.0,
                limit=1,
                search_terms=("",),
                full_crawl=True,
                max_pages=1,
            )
        finally:
            ckan.fetch_json = original_fetch_json

        self.assertEqual(1, len(output.candidates))
        self.assertEqual("has_more", output.remote_pagination_status)
        self.assertFalse(output.remote_exhausted)
        self.assertEqual("1", output.remote_next_page_token)

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

        candidates = html_file_index_candidates_from_text(source, html, source.endpoint_url, 0)

        self.assertEqual(1, len(candidates))
        dataset = candidates[0].dataset
        self.assertEqual("marinecadastre_ais_daily_shards", dataset.dataset_id)
        self.assertEqual("csv.zst", dataset.native_format)
        self.assertEqual(2, len(dataset.metadata["available_versions"]))
        self.assertTrue(looks_like_direct_download(dataset.metadata["available_versions"][0]["download_url"]))

    def test_html_file_index_full_crawl_follows_bounded_same_origin_index_pages(self) -> None:
        source = DatasetDiscoverySource(
            source_id="sample_html_index",
            provider_id="sample_provider",
            name="Sample HTML index",
            source_type="html_file_index",
            endpoint_url="https://files.example.test/index.html",
            dataset_id="sample_shards",
            dataset_title="Sample shards",
            native_format="csv",
            file_url_regex=r"sample-(?P<version>\d{4}-\d{2}-\d{2})\.csv$",
        )
        pages = {
            "https://files.example.test/index.html": (
                """
                <a href="sample-2025-01-01.csv">sample-2025-01-01.csv</a>
                <a href="2025/">2025 folder</a>
                <a href="https://other.example.test/2025/">other domain</a>
                """,
                "https://files.example.test/index.html",
            ),
            "https://files.example.test/2025/": (
                """
                <a href="sample-2025-01-02.csv">sample-2025-01-02.csv</a>
                <a href="01/">January folder</a>
                """,
                "https://files.example.test/2025/",
            ),
            "https://files.example.test/2025/01/": (
                """
                <a href="sample-2025-01-03.csv">sample-2025-01-03.csv</a>
                """,
                "https://files.example.test/2025/01/",
            ),
        }
        calls: list[str] = []
        original_fetch_text = html_index.fetch_text

        def fake_fetch_text(url: str, *, timeout: float) -> tuple[str, str]:
            calls.append(url)
            return pages[url]

        html_index.fetch_text = fake_fetch_text
        try:
            candidates = html_index.html_file_index_candidates_for_source(source, timeout=1.0, limit=1, full_crawl=True, max_pages=3)
        finally:
            html_index.fetch_text = original_fetch_text

        self.assertEqual(
            ["https://files.example.test/index.html", "https://files.example.test/2025/", "https://files.example.test/2025/01/"],
            calls,
        )
        versions = candidates[0].dataset.metadata["available_versions"]
        self.assertEqual(3, len(versions))
        self.assertEqual("2025-01-01", versions[0]["version"])
        self.assertEqual("2025-01-03", versions[2]["version"])

    def test_html_file_index_full_crawl_keeps_candidates_when_linked_page_fails(self) -> None:
        source = DatasetDiscoverySource(
            source_id="sample_html_index",
            provider_id="sample_provider",
            name="Sample HTML index",
            source_type="html_file_index",
            endpoint_url="https://files.example.test/index.html",
            dataset_id="sample_shards",
            dataset_title="Sample shards",
            native_format="csv",
            file_url_regex=r"sample-(?P<version>\d{4}-\d{2}-\d{2})\.csv$",
        )
        pages = {
            "https://files.example.test/index.html": (
                """
                <a href="sample-2025-01-01.csv">sample-2025-01-01.csv</a>
                <a href="broken/">broken folder</a>
                """,
                "https://files.example.test/index.html",
            ),
        }
        original_fetch_text = html_index.fetch_text

        def fake_fetch_text(url: str, *, timeout: float) -> tuple[str, str]:
            if url not in pages:
                raise TimeoutError("simulated linked page timeout")
            return pages[url]

        html_index.fetch_text = fake_fetch_text
        try:
            result = crawl_dataset_sources(
                [source],
                DatasetCrawlOptions(full_crawl=True, max_pages=3, max_workers=1),
            )
        finally:
            html_index.fetch_text = original_fetch_text

        self.assertEqual(1, result.candidate_count)
        self.assertEqual(1, result.warning_count)
        self.assertEqual(("index_page_fetch_failed",), result.source_results[0].warning_codes)
        versions = result.candidates[0].dataset.metadata["available_versions"]
        self.assertEqual(1, len(versions))
        self.assertEqual("2025-01-01", versions[0]["version"])

    def test_dataset_crawler_orchestrator_dedupes_and_captures_errors(self) -> None:
        sources = [
            DatasetDiscoverySource(
                source_id="source_a",
                provider_id="sample_provider",
                name="Source A",
                source_type="sample",
                endpoint_url="https://example.test/a",
            ),
            DatasetDiscoverySource(
                source_id="source_b",
                provider_id="sample_provider",
                name="Source B",
                source_type="sample",
                endpoint_url="https://example.test/b",
            ),
            DatasetDiscoverySource(
                source_id="bad_source",
                provider_id="sample_provider",
                name="Bad Source",
                source_type="sample",
                endpoint_url="https://example.test/bad",
            ),
        ]
        def fake_discover(source: DatasetDiscoverySource, _options: DatasetCrawlOptions):
            if source.source_id == "bad_source":
                raise RuntimeError("network down")
            return [
                dataset_sources.DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid="ds_duplicate",
                        provider_id="sample_provider",
                        dataset_id="same_dataset",
                        title="Same Dataset",
                        categories=("test",),
                        metadata={"candidate_status": "needs_review"},
                    ),
                    source_id=source.source_id,
                    source_type=source.source_type,
                    source_url=source.endpoint_url,
                    confidence=0.9,
                    evidence=("unit test",),
                )
            ]

        result = crawl_dataset_sources(sources, DatasetCrawlOptions(max_workers=3, full_crawl=True), source_crawler=fake_discover)

        self.assertEqual(1, result.candidate_count)
        self.assertEqual(1, result.duplicate_count)
        self.assertEqual(1, result.error_count)
        self.assertEqual(1, result.warning_count)
        self.assertEqual("inspect_source_audit_results_before_upsert_or_promotion", result.next_action)
        summary = result.audit_summary
        self.assertEqual("error", summary["status"])
        self.assertEqual({"pass": 1, "warning": 1, "error": 1}, summary["by_status"])
        self.assertEqual({"all_candidates_duplicate": 1}, summary["by_warning_code"])
        self.assertEqual(2, summary["problem_source_count"])
        self.assertEqual(["bad_source", "source_b"], [item["source_id"] for item in summary["problem_sources"]])
        self.assertIn("network down", [item.error for item in result.source_results if item.source_id == "bad_source"][0])
        bad_result = [item for item in result.source_results if item.source_id == "bad_source"][0]
        self.assertEqual("inspect_crawler_error", bad_result.next_action)
        duplicate_result = [item for item in result.source_results if item.duplicate_candidate_count == 1][0]
        self.assertEqual(0, duplicate_result.unique_candidate_count)
        self.assertEqual(1, duplicate_result.duplicate_candidate_count)
        self.assertIn("all_candidates_duplicate", duplicate_result.warnings[0])
        self.assertEqual(("all_candidates_duplicate",), duplicate_result.warning_codes)
        self.assertEqual("review_source_overlap_or_dedupe", duplicate_result.next_action)

    def test_dataset_crawler_orchestrator_warns_on_duplicate_heavy_output(self) -> None:
        sources = [
            DatasetDiscoverySource(
                source_id="duplicate_heavy_source",
                provider_id="sample_provider",
                name="Duplicate Heavy Source",
                source_type="sample",
                endpoint_url="https://example.test/duplicates",
            )
        ]
        def fake_discover(source: DatasetDiscoverySource, _options: DatasetCrawlOptions):
            # 同一 source 內大量重複通常代表分頁停條件、ID mapping 或 parser shape 壞掉；不能當成正常成功。
            return [
                dataset_sources.DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid=f"ds_duplicate_{index}",
                        provider_id="sample_provider",
                        dataset_id="same_dataset",
                        title="Same Dataset",
                        categories=("test",),
                        metadata={"candidate_status": "needs_review"},
                    ),
                    source_id=source.source_id,
                    source_type=source.source_type,
                    source_url=source.endpoint_url,
                    confidence=0.9,
                    evidence=("unit test",),
                )
                for index in range(3)
            ]

        result = crawl_dataset_sources(sources, DatasetCrawlOptions(max_workers=1), source_crawler=fake_discover)

        source_result = result.source_results[0]
        self.assertEqual(1, result.candidate_count)
        self.assertEqual(2, result.duplicate_count)
        self.assertEqual(1, source_result.unique_candidate_count)
        self.assertEqual(2, source_result.duplicate_candidate_count)
        self.assertIn("duplicate_heavy_output", source_result.warning_codes)
        self.assertEqual("review_source_overlap_or_dedupe", source_result.next_action)

    def test_dataset_crawler_orchestrator_warns_on_empty_success(self) -> None:
        sources = [
            DatasetDiscoverySource(
                source_id="empty_source",
                provider_id="sample_provider",
                name="Empty Source",
                source_type="sample",
                endpoint_url="https://example.test/empty",
            )
        ]
        def fake_discover(_source: DatasetDiscoverySource, _options: DatasetCrawlOptions):
            return []

        result = crawl_dataset_sources(sources, DatasetCrawlOptions(max_workers=1), source_crawler=fake_discover)

        self.assertEqual(0, result.candidate_count)
        self.assertEqual(0, result.error_count)
        self.assertEqual(1, result.warning_count)
        self.assertEqual("warning", result.source_results[0].audit_status)
        self.assertIn("zero_candidates", result.source_results[0].warnings[0])
        self.assertEqual(("zero_candidates",), result.source_results[0].warning_codes)
        self.assertEqual("repair_crawler_query_or_parser", result.source_results[0].next_action)

    def test_dataset_crawler_orchestrator_preserves_remote_pagination_metadata(self) -> None:
        source = DatasetDiscoverySource(
            source_id="paginated_source",
            provider_id="sample_provider",
            name="Paginated Source",
            source_type="sample",
            endpoint_url="https://example.test/page",
        )
        candidate = dataset_sources.DatasetCandidate(
            dataset=Dataset(
                dataset_uid="sample_provider:dataset_a",
                provider_id="sample_provider",
                dataset_id="dataset_a",
                title="Dataset A",
                categories=("test",),
                metadata={"candidate_status": "needs_review"},
            ),
            source_id=source.source_id,
            source_type=source.source_type,
            source_url=source.endpoint_url,
            confidence=0.9,
            evidence=("unit test",),
        )

        def fake_crawler(_source: DatasetDiscoverySource, _options: DatasetCrawlOptions) -> DatasetCrawlerOutput:
            return DatasetCrawlerOutput(
                candidates=(candidate,),
                remote_pagination_status="has_more",
                remote_exhausted=False,
                remote_next_page_token="cursor-2",
            )

        result = crawl_dataset_sources([source], DatasetCrawlOptions(max_workers=1), source_crawler=fake_crawler)
        source_result = result.source_results[0]

        self.assertEqual(1, result.candidate_count)
        self.assertEqual("has_more", source_result.remote_pagination_status)
        self.assertFalse(source_result.remote_exhausted)
        self.assertTrue(source_result.remote_next_page_token_present)
        self.assertEqual("cursor-2", source_result.remote_next_page_token)

    def test_payload_shape_mismatch_is_not_silent_success(self) -> None:
        source = DatasetDiscoverySource(
            source_id="noaa_ncei_dataset_search",
            provider_id="noaa_ncei_access_data",
            name="NOAA NCEI Search",
            source_type="ncei_search",
            endpoint_url="https://example.test/search",
        )

        with self.assertRaisesRegex(ValueError, "results list"):
            ncei_candidates_from_payload(source, {"unexpected": []}, source.endpoint_url, 5)

    def test_search_url_and_family_inference_are_stable(self) -> None:
        self.assertIn("text=cloud+moisture", ncei_search_url("https://example.test/search", "cloud moisture", 3))
        self.assertIn("offset=100", ncei_search_url("https://example.test/search", "cloud moisture", 100, offset=100))
        self.assertIn("filter=type%3Adataset", openalex_works_search_url("https://api.openalex.org/works", "climate", 3))
        self.assertIn("per-page=3", openalex_works_search_url("https://api.openalex.org/works", "climate", 3))
        self.assertIn("query=cloud+moisture", datacite_dois_search_url("https://example.test/dois", "cloud moisture", 3))
        self.assertIn("resource-type-id=dataset", datacite_dois_search_url("https://example.test/dois", "cloud moisture", 3))
        self.assertEqual("raster_or_grid", infer_data_family("GOES cloud moisture imagery ABI raster"))
        self.assertEqual("spatiotemporal_trajectory", infer_data_family("AIS vessel trajectory"))


if __name__ == "__main__":
    unittest.main()
