from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.dataset_discovery import (
    DatasetDiscoverySource,
    DatasetCrawlOptions,
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
    openalex_candidates_from_payload,
    openalex_works_search_url,
    socrata_catalog_candidates_from_payload,
    socrata_catalog_search_url,
    stac_candidates_from_payload,
    zenodo_candidates_from_payload,
)
from api_launcher.crawlers import dataset_sources
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

    def test_supported_source_types_match_catalog_and_portal_intake(self) -> None:
        from api_launcher.portal_intake import SUPPORTED_CRAWLER_TYPES

        catalog_path = Path(__file__).resolve().parents[1] / "catalog" / "dataset_discovery_sources.json"
        catalog_source_types = {source.source_type for source in load_dataset_discovery_sources(catalog_path)}
        supported_types = set(dataset_sources.SUPPORTED_DATASET_SOURCE_TYPES)

        self.assertTrue(catalog_source_types <= supported_types)
        self.assertEqual(supported_types, SUPPORTED_CRAWLER_TYPES)
        self.assertEqual(set(dataset_sources.SOURCE_CRAWLER_HANDLERS), supported_types)

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

    def test_ogc_api_records_search_url_uses_q_and_limit(self) -> None:
        url = ogc_records_search_url("https://records.example.test/items?f=json", "cloud imagery", 25)

        self.assertIn("f=json", url)
        self.assertIn("limit=25", url)
        self.assertIn("q=cloud+imagery", url)

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
        original = dataset_sources.discover_dataset_candidates_for_source

        def fake_discover(source: DatasetDiscoverySource, **_kwargs: object):
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

        dataset_sources.discover_dataset_candidates_for_source = fake_discover
        try:
            result = crawl_dataset_sources(sources, DatasetCrawlOptions(max_workers=3, full_crawl=True))
        finally:
            dataset_sources.discover_dataset_candidates_for_source = original

        self.assertEqual(1, result.candidate_count)
        self.assertEqual(1, result.duplicate_count)
        self.assertEqual(1, result.error_count)
        self.assertEqual(1, result.warning_count)
        self.assertIn("network down", [item.error for item in result.source_results if item.source_id == "bad_source"][0])
        duplicate_result = [item for item in result.source_results if item.duplicate_candidate_count == 1][0]
        self.assertEqual(0, duplicate_result.unique_candidate_count)
        self.assertEqual(1, duplicate_result.duplicate_candidate_count)
        self.assertIn("all_candidates_duplicate", duplicate_result.warnings[0])

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
        original = dataset_sources.discover_dataset_candidates_for_source

        def fake_discover(source: DatasetDiscoverySource, **_kwargs: object):
            return []

        dataset_sources.discover_dataset_candidates_for_source = fake_discover
        try:
            result = crawl_dataset_sources(sources, DatasetCrawlOptions(max_workers=1))
        finally:
            dataset_sources.discover_dataset_candidates_for_source = original

        self.assertEqual(0, result.candidate_count)
        self.assertEqual(0, result.error_count)
        self.assertEqual(1, result.warning_count)
        self.assertEqual("warning", result.source_results[0].audit_status)
        self.assertIn("zero_candidates", result.source_results[0].warnings[0])

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
