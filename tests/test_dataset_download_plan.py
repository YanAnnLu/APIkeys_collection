# 這份測試鎖定 dataset/version download plan 形狀，避免候選資料集無法進購物車。
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_launcher.adapters.gebco import GEBCOTopographyAdapter
from api_launcher.adapters.hyg import HYGStarCatalogAdapter
from api_launcher.adapter_plan_resolver import resolve_adapter_review_plan_payload
from api_launcher.adapter_review import adapter_review_agent_payload, adapter_review_items
from api_launcher.core import main
from api_launcher.db import connect_db
from api_launcher.dataset_versions import version_options_for_dataset
from api_launcher.models import Dataset, Provider
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry
from api_launcher.repository import ApiCatalogRepository
from api_launcher.renderer_contracts import GEBCO_PROVIDER_ID, HYG_PROVIDER_ID


class DatasetDownloadPlanTests(unittest.TestCase):
    def test_hyg_dataset_version_becomes_direct_download_plan_entry(self) -> None:
        provider = Provider(
            provider_id=HYG_PROVIDER_ID,
            name="HYG Database",
            owner="Astronexus",
            categories=("astronomy", "stars"),
            geographic_scope="celestial",
            docs_url="https://codeberg.org/astronexus/hyg",
            auth_type="no_key_for_public_data",
        )
        dataset = HYGStarCatalogAdapter().discover(provider)[0]
        option = version_options_for_dataset(dataset)[0]

        entry = provider_dataset_version_plan_entry(provider, dataset, option)

        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("planned", entry["plan_status"])
        self.assertEqual("local_file_asset", entry["target"])
        self.assertTrue(entry["use_staging"])
        self.assertEqual("3.8", entry["dataset_version"]["version"])
        self.assertEqual(option.download_url, entry["download_url"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual(
            "downloads/hyg_database/hyg_v38_bright_star_catalog/3.8/hyg_v38.csv.gz",
            entry["target_path"],
        )

    def test_non_file_dataset_version_requires_adapter_review(self) -> None:
        provider = Provider(
            provider_id=GEBCO_PROVIDER_ID,
            name="GEBCO",
            owner="General Bathymetric Chart of the Oceans",
            categories=("bathymetry",),
            geographic_scope="global",
            docs_url="https://www.gebco.net/data-products/gridded-bathymetry-data",
            auth_type="no_key_for_download_pages",
        )
        dataset = GEBCOTopographyAdapter().discover(provider)[0]
        latest_option = version_options_for_dataset(dataset)[0]

        entry = provider_dataset_version_plan_entry(provider, dataset, latest_option)

        self.assertEqual("2026", entry["dataset_version"]["version"])
        self.assertEqual("adapter_required", entry["download_eligibility"]["status"])
        self.assertEqual("adapter_review_required", entry["import_plan"]["status"])
        self.assertEqual("needs_adapter_review", entry["plan_status"])
        self.assertEqual(latest_option.download_url, entry["adapter_review_url"])
        self.assertEqual("needs_adapter_review", entry["adapter_review"]["status"])
        self.assertEqual("GEBCOTopographyAdapter", entry["adapter_review"]["adapter_id"])
        self.assertEqual("resolve_source_to_direct_download_entries", entry["adapter_review"]["required_action"])
        self.assertEqual(latest_option.download_url, entry["adapter_review"]["source_url"])
        self.assertNotIn("download_url", entry)
        self.assertNotIn("target_path", entry)

    def test_doi_dataset_id_gets_sql_safe_table_hint(self) -> None:
        provider = Provider(
            provider_id="zenodo",
            name="Zenodo",
            owner="CERN",
            categories=("research_repository",),
            geographic_scope="global",
            docs_url="https://zenodo.org/",
            auth_type="no_key",
        )
        dataset = Dataset(
            dataset_uid="zenodo:10.5281/zenodo.123",
            provider_id="zenodo",
            dataset_id="10.5281_zenodo.123",
            title="Zenodo sample",
            categories=("research_repository",),
            native_format="csv",
            api_url="https://zenodo.example.test/files/sample.csv",
            metadata={"download_url": "https://zenodo.example.test/files/sample.csv"},
        )
        option = version_options_for_dataset(dataset)[0]

        entry = provider_dataset_version_plan_entry(provider, dataset, option)

        self.assertEqual("zenodo_10_5281_zenodo_123", entry["import_plan"]["table_hint"])

    def test_datacite_content_url_resource_can_resolve_to_direct_asset(self) -> None:
        provider = Provider(
            provider_id="datacite",
            name="DataCite",
            owner="DataCite",
            categories=("doi", "research_data", "metadata"),
            geographic_scope="global",
            docs_url="https://datacite.org/",
            auth_type="no_key",
        )
        dataset = Dataset(
            dataset_uid="datacite:10.1234_example.dataset",
            provider_id="datacite",
            dataset_id="10.1234_example.dataset",
            title="Global cloud imagery training dataset",
            categories=("doi", "research_data", "metadata"),
            data_type="raster_or_grid",
            native_format="datacite_doi",
            landing_url="https://doi.org/10.1234/example.dataset",
            api_url="https://api.datacite.example.test/dois/10.1234%2Fexample.dataset",
            version="2026",
            metadata={
                "discovery_source_type": "datacite_dois",
                "doi": "10.1234/example.dataset",
                "data_family": "raster_or_grid",
                "resources": [
                    {
                        "name": "cloud_sample.nc",
                        "format": "nc",
                        "download_url": "https://data.example.test/cloud/cloud_sample.nc",
                        "rel": "contentUrl",
                        "source": "datacite_content_url",
                    }
                ],
            },
        )
        option = version_options_for_dataset(dataset)[0]
        review_entry = provider_dataset_version_plan_entry(provider, dataset, option)

        resolved, result = resolve_adapter_review_plan_payload({"providers": [review_entry]})

        self.assertEqual("adapter_required", review_entry["download_eligibility"]["status"])
        self.assertIn("DOI/OpenAlex research metadata", review_entry["download_eligibility"]["reason"])
        self.assertEqual(1, result.direct_entries_added)
        resolved_entry = resolved["providers"][0]
        self.assertEqual("direct_download", resolved_entry["download_eligibility"]["status"])
        self.assertEqual("https://data.example.test/cloud/cloud_sample.nc", resolved_entry["download_url"])
        self.assertEqual("netcdf", resolved_entry["source_format"])
        self.assertEqual("manual_review_required", resolved_entry["import_plan"]["status"])
        self.assertEqual("generic_resource_direct_download_resolver", resolved_entry["adapter_resolution"]["resolver_id"])

    def test_openalex_work_landing_page_requires_repository_adapter_review(self) -> None:
        provider = Provider(
            provider_id="openalex",
            name="OpenAlex",
            owner="OurResearch",
            categories=("research_metadata", "openalex"),
            geographic_scope="global",
            docs_url="https://docs.openalex.org/",
            auth_type="no_key",
        )
        dataset = Dataset(
            dataset_uid="openalex:10.1163_example",
            provider_id="openalex",
            dataset_id="10.1163_example",
            title="OpenAlex dataset work",
            categories=("research_metadata", "openalex"),
            data_type="document_or_metadata",
            native_format="openalex_work",
            landing_url="https://doi.org/10.1163/example",
            api_url="https://api.openalex.org/works/W1650569836",
            version="2026-05-01",
            metadata={
                "discovery_source_type": "openalex_works_search",
                "doi": "https://doi.org/10.1163/example",
                "openalex_id": "https://openalex.org/W1650569836",
            },
        )
        option = version_options_for_dataset(dataset)[0]

        entry = provider_dataset_version_plan_entry(provider, dataset, option)

        self.assertEqual("adapter_required", entry["download_eligibility"]["status"])
        self.assertIn("DOI/OpenAlex research metadata", entry["download_eligibility"]["reason"])
        self.assertEqual("adapter_review_required", entry["import_plan"]["status"])
        self.assertEqual("needs_adapter_review", entry["adapter_review"]["status"])
        self.assertEqual("resolve_source_to_direct_download_entries", entry["adapter_review"]["required_action"])

    def test_adapter_review_payload_collects_non_direct_entries(self) -> None:
        entry = {
            "provider_id": "example_provider",
            "dataset_id": "selector_dataset",
            "dataset_title": "Selector Dataset",
            "dataset_version": {"version": "2026", "download_url": "https://example.test/select"},
            "download_eligibility": {"status": "adapter_required", "reason": "selector page"},
            "import_plan": {"status": "adapter_review_required", "reason": "needs bounded query"},
            "adapter_review": {
                "adapter_id": "ExampleSelectorAdapter",
                "source_url": "https://example.test/select",
                "required_action": "resolve_source_to_direct_download_entries",
            },
        }

        payload = adapter_review_agent_payload({"providers": [entry]})
        items = adapter_review_items({"providers": [entry]})

        self.assertEqual(1, payload["summary"]["item_count"])
        self.assertEqual({"ExampleSelectorAdapter": 1}, payload["summary"]["by_adapter"])
        self.assertEqual({"source_resolution_required": 1}, payload["summary"]["by_outcome"])
        self.assertEqual(1, len(items))
        self.assertEqual("ExampleSelectorAdapter", items[0].adapter_id)
        self.assertEqual("resolve_source_to_direct_download_entries", items[0].required_action)
        self.assertEqual("source_resolution_required", items[0].outcome_bucket)

    def test_adapter_review_payload_marks_downloaded_transform_outcome(self) -> None:
        entry = {
            "provider_id": "archive_provider",
            "dataset_id": "archive_dataset",
            "download_url": "https://example.test/archive.zip",
            "download_eligibility": {"status": "direct_download"},
            "import_plan": {"status": "requires_unpack_or_adapter", "reason": "archive member selection required"},
            "adapter_review": {"adapter_id": "ArchiveTransformAdapter", "source_kind": "direct_file_needs_transform"},
        }

        payload = adapter_review_agent_payload({"providers": [entry]})
        items = adapter_review_items({"providers": [entry]})

        self.assertEqual({"downloaded_payload_transform": 1}, payload["summary"]["by_outcome"])
        self.assertEqual("unpack_or_transform_downloaded_payload", items[0].required_action)
        self.assertEqual("downloaded_payload_transform", items[0].to_dict()["outcome_bucket"])

    def test_dataset_plan_summary_counts_direct_and_review_entries(self) -> None:
        entries = [
            {"provider_id": "direct", "download_eligibility": {"status": "direct_download"}},
            {"provider_id": "review", "download_eligibility": {"status": "adapter_required"}},
        ]

        plan = build_dataset_download_plan(entries, plan_name="Dataset Plan")

        self.assertEqual("Dataset Plan", plan["plan_name"])
        self.assertEqual(2, plan["summary"]["provider_count"])
        self.assertEqual(2, plan["summary"]["dataset_version_count"])
        self.assertEqual(1, plan["summary"]["direct_download_count"])
        self.assertEqual(1, plan["summary"]["review_required_count"])

    def test_cli_exports_dataset_plan_from_adapter_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "dataset_plan.json"
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--init-db",
                        "--seed",
                        "--provider",
                        HYG_PROVIDER_ID,
                        "--export-dataset-plan",
                        str(plan_path),
                    ]
                )

            self.assertEqual(0, rc)
            payload = json.loads(plan_path.read_text(encoding="utf-8"))

        self.assertIn("[dataset-plan] wrote", output.getvalue())
        self.assertEqual(1, payload["summary"]["dataset_version_count"])
        self.assertEqual(1, payload["summary"]["direct_download_count"])
        self.assertEqual(HYG_PROVIDER_ID, payload["providers"][0]["provider_id"])
        self.assertEqual("hyg_v38_bright_star_catalog", payload["providers"][0]["dataset_id"])

    def test_cli_lists_adapter_review_items_from_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "providers": [
                            {
                                "provider_id": "gebco",
                                "dataset_id": "gebco_grid",
                                "dataset_version": {"version": "2026"},
                                "download_eligibility": {"status": "adapter_required"},
                                "import_plan": {"status": "adapter_review_required"},
                                "adapter_review": {
                                    "adapter_id": "GEBCOTopographyAdapter",
                                    "source_url": "https://download.gebco.net/downloads",
                                    "required_action": "resolve_source_to_direct_download_entries",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(["--db", str(Path(tmpdir) / "launcher.sqlite"), "--adapter-review-plan", str(plan_path)])

        self.assertEqual(0, rc)
        self.assertIn("[adapter-review] items=1 adapters=1", output.getvalue())
        self.assertIn("adapter=GEBCOTopographyAdapter", output.getvalue())
        self.assertIn("outcome=source_resolution_required", output.getvalue())

    def test_cli_exports_candidate_plan_from_reviewable_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "candidate_plan.json"
            conn = connect_db(db_path)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                repo.upsert_dataset(
                    Dataset(
                        dataset_uid="ds_candidate_ais",
                        provider_id="noaa_marinecadastre_ais",
                        dataset_id="marinecadastre_ais_daily_shards",
                        title="NOAA MarineCadastre AIS daily shards",
                        categories=("ais", "maritime"),
                        data_type="spatiotemporal_trajectory",
                        native_format="csv.zst",
                        geographic_scope="us/offshore",
                        landing_url="https://www.coast.noaa.gov/digitalcoast/data/vesseltraffic.html",
                        api_url="https://example.test/ais-2025-01-01.csv.zst",
                        version="2025-01-01",
                        metadata={
                            "candidate_status": "needs_review",
                            "data_family": "spatiotemporal_trajectory",
                            "available_versions": [
                                {
                                    "label": "ais-2025-01-01.csv.zst",
                                    "version": "2025-01-01",
                                    "version_status": "discovered_file_shard",
                                    "download_url": "https://example.test/ais-2025-01-01.csv.zst",
                                    "landing_url": "https://example.test/index.html",
                                },
                                {
                                    "label": "ais-2025-01-02.csv.zst",
                                    "version": "2025-01-02",
                                    "version_status": "discovered_file_shard",
                                    "download_url": "https://example.test/ais-2025-01-02.csv.zst",
                                    "landing_url": "https://example.test/index.html",
                                },
                            ],
                        },
                    )
                )
            finally:
                conn.close()
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--export-candidate-plan",
                        str(plan_path),
                        "--candidate-plan-status",
                        "needs_review",
                        "--candidate-plan-limit",
                        "1",
                        "--mark-candidate-plan-planned",
                    ]
                )
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            conn = connect_db(db_path)
            try:
                planned = ApiCatalogRepository(conn).get_dataset("ds_candidate_ais")
            finally:
                conn.close()

        self.assertEqual(0, rc)
        self.assertIn("[candidate-plan] wrote", output.getvalue())
        self.assertEqual("crawler_dataset_candidates", payload["source"]["kind"])
        self.assertEqual(1, payload["summary"]["dataset_version_count"])
        self.assertEqual(1, payload["summary"]["direct_download_count"])
        self.assertEqual("requires_unpack_or_adapter", payload["providers"][0]["import_plan"]["status"])
        self.assertEqual("unpack_or_transform_downloaded_payload", payload["providers"][0]["adapter_review"]["required_action"])
        self.assertEqual("noaa_marinecadastre_ais", payload["providers"][0]["provider_id"])
        self.assertIsNotNone(planned)
        self.assertEqual("planned", planned.metadata["candidate_status"])

    def test_socrata_candidate_plan_resolves_to_bounded_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "socrata_candidate_plan.json"
            conn = connect_db(db_path)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                repo.upsert_dataset(
                    Dataset(
                        dataset_uid="nyc_open_data_socrata:t29m-gskq",
                        provider_id="nyc_open_data_socrata",
                        dataset_id="t29m-gskq",
                        title="2018 Yellow Taxi Trip Data",
                        categories=("open_data", "socrata", "taxi"),
                        data_type="timeseries",
                        native_format="socrata_resource",
                        geographic_scope="nyc/us",
                        landing_url="https://data.cityofnewyork.us/d/t29m-gskq",
                        api_url="https://data.cityofnewyork.us/api/views/t29m-gskq",
                        version="2019-04-05T15:42:41.000Z",
                        metadata={
                            "candidate_status": "needs_review",
                            "discovery_source_id": "nyc_open_data_socrata_catalog",
                            "discovery_source_type": "socrata_catalog_search",
                            "source_url": "https://api.us.socrata.com/api/catalog/v1?domains=data.cityofnewyork.us&q=taxi",
                            "data_family": "timeseries",
                            "socrata_dataset_id": "t29m-gskq",
                            "socrata_domain": "data.cityofnewyork.us",
                            "socrata_api_view_url": "https://data.cityofnewyork.us/api/views/t29m-gskq",
                            "socrata_resource_url": "https://data.cityofnewyork.us/resource/t29m-gskq.json",
                        },
                    )
                )
            finally:
                conn.close()

            with redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--export-candidate-plan",
                        str(plan_path),
                        "--candidate-plan-status",
                        "needs_review",
                        "--candidate-plan-limit",
                        "1",
                    ]
                )
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            resolved_payload, resolution = resolve_adapter_review_plan_payload(
                payload,
                downloads_root=Path(tmpdir) / "downloads",
            )

        self.assertEqual(0, rc)
        self.assertEqual(1, payload["summary"]["review_required_count"])
        self.assertEqual("adapter_required", payload["providers"][0]["download_eligibility"]["status"])
        self.assertEqual("socrata_catalog_search", payload["providers"][0]["candidate_review"]["discovery_source_type"])
        self.assertEqual(1, resolution.resolved_review_entries)
        self.assertEqual(1, resolution.direct_entries_added)
        resolved_entry = resolved_payload["providers"][0]
        self.assertEqual("direct_download", resolved_entry["download_eligibility"]["status"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])
        self.assertEqual(
            "socrata_bounded_sample_query_resolver",
            resolved_entry["adapter_resolution"]["resolver_id"],
        )
        self.assertIn("/resource/t29m-gskq.json", resolved_entry["download_url"])
        self.assertIn("$limit=25", resolved_entry["download_url"])

    def test_ncei_candidate_plan_resolves_to_bounded_search_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "ncei_candidate_plan.json"
            conn = connect_db(db_path)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                repo.upsert_dataset(
                    Dataset(
                        dataset_uid="noaa_ncei_access_data:automatic-identification-system-ais",
                        provider_id="noaa_ncei_access_data",
                        dataset_id="automatic-identification-system-ais",
                        title="Automatic Identification System (AIS) Vessel Traffic Data",
                        categories=("noaa", "catalog", "ais"),
                        data_type="spatiotemporal_trajectory",
                        native_format="ncei_search",
                        geographic_scope="global/us",
                        landing_url="https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C01591/html",
                        api_url="https://www.ncei.noaa.gov/access/services/search/v1/datasets?limit=5&available=true&text=ais",
                        version="discovered",
                        metadata={
                            "candidate_status": "needs_review",
                            "discovery_source_id": "noaa_ncei_dataset_search",
                            "discovery_source_type": "ncei_search",
                            "source_url": "https://www.ncei.noaa.gov/access/services/search/v1/datasets?limit=5&available=true&text=ais",
                            "data_family": "spatiotemporal_trajectory",
                            "ncei_result_id": "automatic-identification-system-ais",
                            "ncei_file_id": "gov.noaa.ncdc:C01591",
                        },
                    )
                )
            finally:
                conn.close()

            with redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--export-candidate-plan",
                        str(plan_path),
                        "--candidate-plan-status",
                        "needs_review",
                        "--candidate-plan-limit",
                        "1",
                    ]
                )
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            resolved_payload, resolution = resolve_adapter_review_plan_payload(
                payload,
                downloads_root=Path(tmpdir) / "downloads",
            )

        self.assertEqual(0, rc)
        self.assertEqual(1, payload["summary"]["review_required_count"])
        self.assertEqual("adapter_required", payload["providers"][0]["download_eligibility"]["status"])
        self.assertEqual("ncei_search", payload["providers"][0]["candidate_review"]["discovery_source_type"])
        self.assertEqual(1, resolution.resolved_review_entries)
        self.assertEqual(1, resolution.direct_entries_added)
        resolved_entry = resolved_payload["providers"][0]
        self.assertEqual("direct_download", resolved_entry["download_eligibility"]["status"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])
        self.assertEqual(
            "ncei_bounded_search_query_resolver",
            resolved_entry["adapter_resolution"]["resolver_id"],
        )
        self.assertIn("/access/services/search/v1/data", resolved_entry["download_url"])
        self.assertIn("dataset=automatic-identification-system-ais", resolved_entry["download_url"])
        self.assertIn("limit=25", resolved_entry["download_url"])

    def test_cmr_candidate_plan_resolves_to_bounded_granule_metadata_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "cmr_candidate_plan.json"
            conn = connect_db(db_path)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                repo.upsert_dataset(
                    Dataset(
                        dataset_uid="nasa_earthdata:sentinel_6_jason_cs_s6a",
                        provider_id="nasa_earthdata",
                        dataset_id="sentinel_6_jason_cs_s6a",
                        title="Sentinel-6 Jason-CS L2 Sea Surface Height",
                        categories=("nasa", "cmr", "satellite", "earth_observation"),
                        data_type="raster_or_grid",
                        native_format="cmr_collection",
                        geographic_scope="global",
                        landing_url="https://cmr.earthdata.nasa.gov/search/concepts/C1234567890-POCLOUD.html",
                        api_url="https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id=C1234567890-POCLOUD",
                        version="discovered",
                        metadata={
                            "candidate_status": "needs_review",
                            "discovery_source_id": "nasa_earthdata_cmr_collections",
                            "discovery_source_type": "cmr_collections",
                            "source_url": "https://cmr.earthdata.nasa.gov/search/collections.json?keyword=altimetry&page_size=10",
                            "data_family": "raster_or_grid",
                            "cmr_concept_id": "C1234567890-POCLOUD",
                        },
                    )
                )
            finally:
                conn.close()

            with redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--export-candidate-plan",
                        str(plan_path),
                        "--candidate-plan-status",
                        "needs_review",
                        "--candidate-plan-limit",
                        "1",
                    ]
                )
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            resolved_payload, resolution = resolve_adapter_review_plan_payload(
                payload,
                downloads_root=Path(tmpdir) / "downloads",
            )

        self.assertEqual(0, rc)
        self.assertEqual(1, payload["summary"]["review_required_count"])
        self.assertEqual("cmr_collections", payload["providers"][0]["candidate_review"]["discovery_source_type"])
        self.assertEqual(1, resolution.resolved_review_entries)
        self.assertEqual(1, resolution.direct_entries_added)
        resolved_entry = resolved_payload["providers"][0]
        self.assertEqual("direct_download", resolved_entry["download_eligibility"]["status"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])
        self.assertEqual(
            "cmr_bounded_granule_search_resolver",
            resolved_entry["adapter_resolution"]["resolver_id"],
        )
        self.assertIn("/search/granules.json", resolved_entry["download_url"])
        self.assertIn("collection_concept_id=C1234567890-POCLOUD", resolved_entry["download_url"])
        self.assertIn("page_size=1", resolved_entry["download_url"])

    def test_dataverse_candidate_plan_resolves_to_latest_version_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "dataverse_candidate_plan.json"
            conn = connect_db(db_path)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                repo.upsert_dataset(
                    Dataset(
                        dataset_uid="harvard_dataverse:doi_10.7910_dvn_abc123",
                        provider_id="harvard_dataverse",
                        dataset_id="doi_10.7910_dvn_abc123",
                        title="Example Dataverse dataset",
                        categories=("dataverse", "research_data"),
                        data_type="table",
                        native_format="dataverse_dataset",
                        geographic_scope="global",
                        landing_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/ABC123",
                        api_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/ABC123",
                        version="1.0",
                        metadata={
                            "candidate_status": "needs_review",
                            "discovery_source_id": "harvard_dataverse_search",
                            "discovery_source_type": "dataverse_search",
                            "source_url": "https://dataverse.harvard.edu/api/search?q=ocean&type=dataset",
                            "data_family": "table",
                            "global_id": "doi:10.7910/DVN/ABC123",
                            "file_count": 2,
                        },
                    )
                )
            finally:
                conn.close()

            with redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--export-candidate-plan",
                        str(plan_path),
                        "--candidate-plan-status",
                        "needs_review",
                        "--candidate-plan-limit",
                        "1",
                    ]
                )
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            with patch("api_launcher.adapter_plan_resolver.fetch_json", return_value=dataverse_latest_version_payload()):
                resolved_payload, resolution = resolve_adapter_review_plan_payload(
                    payload,
                    downloads_root=Path(tmpdir) / "downloads",
                )

        self.assertEqual(0, rc)
        self.assertEqual(1, payload["summary"]["review_required_count"])
        self.assertEqual("dataverse_search", payload["providers"][0]["candidate_review"]["discovery_source_type"])
        self.assertEqual(1, resolution.resolved_review_entries)
        self.assertEqual(1, resolution.direct_entries_added)
        resolved_entry = resolved_payload["providers"][0]
        self.assertEqual("direct_download", resolved_entry["download_eligibility"]["status"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])
        self.assertEqual(
            "dataverse_latest_version_file_resolver",
            resolved_entry["adapter_resolution"]["resolver_id"],
        )
        self.assertEqual("https://dataverse.harvard.edu/api/access/datafile/12345", resolved_entry["download_url"])
        self.assertTrue(resolved_entry["target_path"].endswith(".csv"))


def dataverse_latest_version_payload() -> dict[str, object]:
    return {
        "status": "OK",
        "data": {
            "files": [
                {
                    "restricted": False,
                    "dataFile": {
                        "id": 12345,
                        "filename": "observations.csv",
                        "contentType": "text/csv",
                        "filesize": 4096,
                    },
                },
                {
                    "restricted": False,
                    "dataFile": {
                        "id": 23456,
                        "filename": "readme.html",
                        "contentType": "text/html",
                        "filesize": 2048,
                    },
                },
            ]
        },
    }


if __name__ == "__main__":
    unittest.main()
