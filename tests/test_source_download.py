from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset, Provider
from api_launcher.repository import ApiCatalogRepository
from api_launcher.db import connect_db
from api_launcher.bound_form import build_bound_form_spec, source_download_bounds_from_form_values
from api_launcher.schema_probe import csv_schema_probe, json_schema_probe, schema_probe_url
from api_launcher.source_download import (
    SourceDownloadBounds,
    SourceDownloadOptions,
    build_source_download_plan,
    credential_gate_for_provider,
)


class SourceDownloadTests(unittest.TestCase):
    def test_bounds_without_known_time_or_spatial_columns_require_schema_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_socrata",
                        name="Sample Socrata",
                        owner="Sample",
                        categories=("open_data",),
                        geographic_scope="sample",
                        docs_url="https://example.test/docs",
                        auth_type="none",
                    )
                )
                source = DatasetDiscoverySource(
                    source_id="sample_source",
                    provider_id="sample_socrata",
                    name="Sample Source",
                    source_type="sample",
                    endpoint_url="https://example.test/catalog",
                )
                candidate = DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid="sample_socrata:events",
                        provider_id="sample_socrata",
                        dataset_id="events",
                        title="Events",
                        categories=("open_data",),
                        native_format="socrata_resource",
                        api_url="https://data.example.test/resource/abcd-1234.json",
                        metadata={
                            "candidate_status": "needs_review",
                            "socrata_resource_url": "https://data.example.test/resource/abcd-1234.json",
                            "socrata_domain": "data.example.test",
                            "socrata_dataset_id": "abcd-1234",
                        },
                    ),
                    source_id="sample_source",
                    source_type="sample",
                    source_url="https://example.test/catalog",
                    confidence=0.9,
                    evidence=("unit test",),
                )
                options = SourceDownloadOptions(
                    bounds=SourceDownloadBounds(
                        sample_limit=10,
                        start_date="2026-01-01",
                        end_date="2026-01-31",
                        bbox=(-122.6, 37.6, -122.3, 37.9),
                    )
                )
                with patch("api_launcher.source_download.crawl_dataset_sources") as crawl_mock:
                    crawl_mock.return_value.candidates = (candidate,)
                    crawl_mock.return_value.candidate_count = 1
                    crawl_mock.return_value.audit_summary = {"status": "pass"}
                    plan = build_source_download_plan([source], repo, tmpdir, options)
            finally:
                conn.close()

        entry = plan.original_plan["providers"][0]
        self.assertEqual("run_schema_probe_before_precise_bounded_download", entry["download_bound_status"]["next_action"])
        self.assertIn("time_range", entry["download_bound_status"]["needs_schema_probe"])
        self.assertIn("bbox", entry["download_bound_status"]["needs_schema_probe"])
        self.assertIn("$limit=10", entry["download_url"])

    def test_bounds_with_known_socrata_columns_apply_required_columns_and_sample_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_socrata",
                        name="Sample Socrata",
                        owner="Sample",
                        categories=("open_data",),
                        geographic_scope="sample",
                        docs_url="https://example.test/docs",
                        auth_type="none",
                    )
                )
                source = DatasetDiscoverySource(
                    source_id="sample_source",
                    provider_id="sample_socrata",
                    name="Sample Source",
                    source_type="sample",
                    endpoint_url="https://example.test/catalog",
                )
                candidate = DatasetCandidate(
                    dataset=Dataset(
                        dataset_uid="sample_socrata:events",
                        provider_id="sample_socrata",
                        dataset_id="events",
                        title="Events",
                        categories=("open_data",),
                        native_format="socrata_resource",
                        api_url="https://data.example.test/resource/abcd-1234.json",
                        metadata={
                            "candidate_status": "needs_review",
                            "socrata_resource_url": "https://data.example.test/resource/abcd-1234.json",
                            "socrata_domain": "data.example.test",
                            "socrata_dataset_id": "abcd-1234",
                            "columns": [
                                {"name": "created_date", "field_name": "created_date"},
                                {"name": "longitude", "field_name": "longitude"},
                                {"name": "latitude", "field_name": "latitude"},
                            ],
                        },
                    ),
                    source_id="sample_source",
                    source_type="sample",
                    source_url="https://example.test/catalog",
                    confidence=0.9,
                    evidence=("unit test",),
                )
                options = SourceDownloadOptions(
                    bounds=SourceDownloadBounds(
                        sample_limit=12,
                        start_date="2026-01-01",
                        end_date="2026-01-31",
                        bbox=(-122.6, 37.6, -122.3, 37.9),
                        time_field="created_date",
                        longitude_field="longitude",
                        latitude_field="latitude",
                        required_columns=("created_date", "longitude"),
                    )
                )
                with patch("api_launcher.source_download.crawl_dataset_sources") as crawl_mock:
                    crawl_mock.return_value.candidates = (candidate,)
                    crawl_mock.return_value.candidate_count = 1
                    crawl_mock.return_value.audit_summary = {"status": "pass"}
                    plan = build_source_download_plan([source], repo, tmpdir, options)
            finally:
                conn.close()

        entry = plan.original_plan["providers"][0]
        self.assertEqual("ready_for_bounded_download_plan", entry["download_bound_status"]["next_action"])
        self.assertIn("time_range", entry["download_bound_status"]["applied"])
        self.assertIn("bbox", entry["download_bound_status"]["applied"])
        self.assertIn("required_columns", entry["download_bound_status"]["applied"])
        self.assertIn("$limit=12", entry["download_url"])

    def test_credential_gate_blocks_missing_api_key_provider(self) -> None:
        provider = Provider(
            provider_id="needs_key",
            name="Needs Key",
            owner="Sample",
            categories=("sample",),
            geographic_scope="sample",
            docs_url="https://example.test/docs",
            auth_type="api_key_required",
            key_env_var="RRKAL_TEST_SOURCE_KEY",
        )

        gate = credential_gate_for_provider(provider)

        self.assertFalse(gate.allows_download)
        self.assertEqual("missing", gate.status)
        self.assertEqual(("RRKAL_TEST_SOURCE_KEY",), gate.required_env_vars)

    def test_schema_probe_url_adds_head5_limit_for_known_api_shapes(self) -> None:
        self.assertIn("$limit=5", schema_probe_url("https://data.example.test/resource/abcd-1234.json?$limit=99", 5))
        self.assertIn("limit=5", schema_probe_url("https://www.ncei.noaa.gov/access/services/search/v1/data?dataset=ais&limit=99", 5))
        self.assertIn("page_size=5", schema_probe_url("https://cmr.earthdata.nasa.gov/search/granules.json?page_size=1", 5))

    def test_csv_head5_probe_extracts_columns(self) -> None:
        result = csv_schema_probe(
            "https://example.test/data.csv",
            "https://example.test/data.csv",
            b"date,longitude,latitude,value\n2026-01-01,121.5,25.0,42\n",
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(["date", "longitude", "latitude", "value"], [column.name for column in result.columns])
        self.assertEqual("date", result.columns[0].inferred_type)
        self.assertEqual("number", result.columns[1].inferred_type)

    def test_json_head5_probe_extracts_columns(self) -> None:
        result = json_schema_probe(
            "https://example.test/data.json",
            "https://example.test/data.json",
            b'[{"created_date":"2026-01-01T00:00:00","count":3}]',
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(["created_date", "count"], [column.name for column in result.columns])
        self.assertEqual("datetime", result.columns[0].inferred_type)
        self.assertEqual("integer", result.columns[1].inferred_type)

    def test_schema_probe_result_builds_dynamic_bounds_form(self) -> None:
        result = json_schema_probe(
            "https://example.test/data.json",
            "https://example.test/data.json",
            b'[{"created_date":"2026-01-01T00:00:00","longitude":121.5,"latitude":25.0,"value":3}]',
        )

        form = build_bound_form_spec(result, default_sample_limit=15)
        fields = {field.field_id: field for field in form.fields}

        self.assertTrue(form.succeeded)
        self.assertEqual(15, fields["sample_limit"].default)
        self.assertEqual("created_date", fields["time_field"].default)
        self.assertEqual("longitude", fields["longitude_field"].default)
        self.assertEqual("latitude", fields["latitude_field"].default)
        self.assertIn("required_columns", fields)
        self.assertIn("created_date", form.inferred_roles["time"])

    def test_dynamic_bounds_form_values_convert_to_download_bounds(self) -> None:
        bounds = source_download_bounds_from_form_values(
            {
                "sample_limit": "50",
                "time_field": "created_date",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "longitude_field": "longitude",
                "latitude_field": "latitude",
                "bbox_west": "120.0",
                "bbox_south": "23.0",
                "bbox_east": "122.0",
                "bbox_north": "25.5",
                "required_columns": "created_date,longitude,latitude",
            }
        )

        self.assertEqual(50, bounds.sample_limit)
        self.assertEqual("created_date", bounds.time_field)
        self.assertEqual((120.0, 23.0, 122.0, 25.5), bounds.bbox)
        self.assertEqual(("created_date", "longitude", "latitude"), bounds.required_columns)


if __name__ == "__main__":
    unittest.main()
