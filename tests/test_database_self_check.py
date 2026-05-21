# 這份測試鎖定 database self-check 與修復建議，避免誤判可自動修復。
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import io
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_launcher.core import main
from api_launcher.asset_verifier import AssetRecord
from api_launcher.data_store_connections import DataStoreConnectionProfile, DataStoreConnectionTestResult
from api_launcher.database_self_check import (
    DatabaseAssetVerifier,
    database_repair_suggestion,
    database_self_check_issues,
    database_self_check_target,
    sqlite_schema_summary,
    sqlite_table_schema_summary,
)
from api_launcher.db import connect_db
from api_launcher.models import Provider
from api_launcher.repository import ApiCatalogRepository


class DatabaseSelfCheckTests(unittest.TestCase):
    def test_database_repair_suggestion_maps_missing_env(self) -> None:
        suggestion = database_repair_suggestion(
            asset_kind="database",
            engine="mysql",
            asset_name="weather",
            status="error",
            error="Missing required environment variables: APIKEYS_MYSQL_HOST, APIKEYS_MYSQL_DATABASE",
        )

        self.assertEqual("configure_data_store_env", suggestion.action_id)
        self.assertEqual(("APIKEYS_MYSQL_HOST", "APIKEYS_MYSQL_DATABASE"), suggestion.details["missing_env_vars"])

    def test_database_repair_suggestion_maps_missing_driver_to_project_env(self) -> None:
        suggestion = database_repair_suggestion(
            asset_kind="database",
            engine="postgresql",
            asset_name="weather",
            status="error",
            error="Optional Python driver psycopg or psycopg2 is not installed.",
        )

        self.assertEqual("install_optional_driver_in_project_env", suggestion.action_id)
        self.assertEqual("project_python_environment", suggestion.details["install_scope"])

    def test_database_repair_suggestion_maps_schema_drift(self) -> None:
        suggestion = database_repair_suggestion(
            asset_kind="table",
            engine="sqlite",
            asset_name="station",
            status="error",
            error="SQLite table schema fingerprint drift: expected abc, got def; table=station",
        )

        self.assertEqual("review_schema_drift", suggestion.action_id)

    def test_database_repair_suggestion_maps_profile_mismatch(self) -> None:
        suggestion = database_repair_suggestion(
            asset_kind="database",
            engine="mysql",
            asset_name="expected_db",
            status="error",
            error="MySQL profile connected to other_db, but registry asset expects expected_db.",
        )

        self.assertEqual("fix_data_store_profile_mapping", suggestion.action_id)

    def test_database_repair_suggestion_marks_supported_sqlite_table_auto_repairable(self) -> None:
        suggestion = database_repair_suggestion(
            asset_kind="table",
            engine="sqlite",
            asset_name="station",
            status="missing",
            error="SQLite table is missing: station",
            source_format="geojson.gz",
            has_recorded_manifest=True,
        )

        self.assertEqual("restore_or_reimport_table", suggestion.action_id)
        self.assertTrue(suggestion.can_auto_repair)
        self.assertEqual("geojson.gz", suggestion.details["source_format"])
        self.assertTrue(suggestion.details["has_recorded_manifest"])

    def test_sqlite_asset_uses_source_uri_as_check_target(self) -> None:
        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="database",
            engine="sqlite",
            asset_name="logical_name",
            source_uri="/tmp/sample.sqlite",
        )

        target = database_self_check_target(asset)

        self.assertEqual("/tmp/sample.sqlite", target.path)

    def test_sqlite_table_asset_uses_asset_name_as_table_name(self) -> None:
        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="table",
            engine="sqlite",
            asset_name="station",
            source_uri="/tmp/sample.sqlite",
        )

        target = database_self_check_target(asset)

        self.assertEqual("/tmp/sample.sqlite", target.path)
        self.assertEqual("station", target.table_name)

    def test_sql_table_asset_uses_install_location_as_database_owner(self) -> None:
        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="table",
            engine="postgresql",
            asset_name="public.station",
            install_location="postgresql://localhost/weather",
        )

        target = database_self_check_target(asset)

        self.assertEqual("weather", target.database_name)
        self.assertEqual("public", target.schema_name)
        self.assertEqual("station", target.table_name)

    def test_sql_table_asset_prefers_explicit_schema_name(self) -> None:
        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="table",
            engine="postgresql",
            asset_name="station",
            install_location="postgresql://localhost/weather",
            schema_name="archive",
        )

        target = database_self_check_target(asset)

        self.assertEqual("weather", target.database_name)
        self.assertEqual("archive", target.schema_name)
        self.assertEqual("station", target.table_name)

    def test_sqlite_asset_verifier_marks_existing_database_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            asset = AssetRecord(
                asset_id="asset_1",
                install_id="inst_1",
                provider_id="sample",
                asset_kind="database",
                engine="sqlite",
                asset_name="asset.sqlite",
                source_uri=str(db_path),
            )

            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("present", result.status)

    def test_sqlite_schema_summary_fingerprints_table_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")

            summary = sqlite_schema_summary(db_path)

        self.assertEqual(("station",), summary.tables)
        self.assertEqual(2, len(summary.column_signatures))
        self.assertEqual(64, len(summary.schema_fingerprint))

    def test_sqlite_table_schema_summary_fingerprints_one_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
                conn.execute("CREATE TABLE observation (id INTEGER PRIMARY KEY, station_id INTEGER, value REAL)")

            summary = sqlite_table_schema_summary(db_path, "station")

        self.assertEqual(("station",), summary.tables)
        self.assertEqual(2, len(summary.column_signatures))
        self.assertEqual(64, len(summary.schema_fingerprint))

    def test_sqlite_asset_verifier_detects_schema_fingerprint_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY, name TEXT)")
            expected = sqlite_schema_summary(db_path).schema_fingerprint
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("ALTER TABLE station ADD COLUMN elevation REAL")
            asset = AssetRecord(
                asset_id="asset_1",
                install_id="inst_1",
                provider_id="sample",
                asset_kind="database",
                engine="sqlite",
                asset_name="asset.sqlite",
                source_uri=str(db_path),
                schema_fingerprint=expected,
            )

            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("error", result.status)
        self.assertIn("schema fingerprint drift", result.error)

    def test_sqlite_asset_verifier_marks_missing_database_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.sqlite"
            asset = AssetRecord(
                asset_id="asset_1",
                install_id="inst_1",
                provider_id="sample",
                asset_kind="database",
                engine="sqlite",
                asset_name="missing.sqlite",
                source_uri=str(db_path),
            )

            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("missing", result.status)

    def test_sqlite_asset_verifier_marks_existing_table_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY)")
            asset = AssetRecord(
                asset_id="asset_1",
                install_id="inst_1",
                provider_id="sample",
                asset_kind="table",
                engine="sqlite",
                asset_name="station",
                source_uri=str(db_path),
            )

            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("present", result.status)

    def test_sqlite_asset_verifier_marks_missing_table_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY)")
            asset = AssetRecord(
                asset_id="asset_1",
                install_id="inst_1",
                provider_id="sample",
                asset_kind="table",
                engine="sqlite",
                asset_name="observation",
                source_uri=str(db_path),
            )

            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("missing", result.status)
        self.assertIn("SQLite table is missing", result.error)

    def test_sqlite_asset_verifier_detects_table_schema_fingerprint_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY, name TEXT)")
            expected = sqlite_table_schema_summary(db_path, "station").schema_fingerprint
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("ALTER TABLE station ADD COLUMN elevation REAL")
            asset = AssetRecord(
                asset_id="asset_1",
                install_id="inst_1",
                provider_id="sample",
                asset_kind="table",
                engine="sqlite",
                asset_name="station",
                source_uri=str(db_path),
                schema_fingerprint=expected,
            )

            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("error", result.status)
        self.assertIn("table schema fingerprint drift", result.error)

    def test_mysql_database_asset_compares_schema_fingerprint_when_available(self) -> None:
        calls: list[bool] = []

        def fake_test_data_store_connection(profile, env=None, include_schema_summary=False, **kwargs):
            calls.append(include_schema_summary)
            return DataStoreConnectionTestResult(
                profile_id=profile.profile_id,
                engine=profile.engine,
                status="ok",
                message="ok",
                details={"database": "weather", "schema_fingerprint": "expected", "table_count": 1},
            )

        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="database",
            engine="mysql",
            asset_name="weather",
            schema_fingerprint="expected",
        )

        with patch("api_launcher.database_self_check.test_data_store_connection", fake_test_data_store_connection):
            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("present", result.status)
        self.assertEqual([True], calls)

    def test_mysql_table_asset_marks_existing_table_present(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_test_data_store_connection(profile, env=None, include_schema_summary=False, **kwargs):
            calls.append({"include_schema_summary": include_schema_summary, **kwargs})
            return DataStoreConnectionTestResult(
                profile_id=profile.profile_id,
                engine=profile.engine,
                status="ok",
                message="ok",
                details={"database": "weather", "table": "station", "table_exists": True, "table_count": 1},
            )

        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="table",
            engine="mysql",
            asset_name="station",
            install_location="mysql://weather",
        )

        with patch("api_launcher.database_self_check.test_data_store_connection", fake_test_data_store_connection):
            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("present", result.status)
        self.assertEqual("station", calls[0]["schema_summary_table"])
        self.assertTrue(calls[0]["include_schema_summary"])

    def test_mysql_asset_uses_configured_data_store_profile(self) -> None:
        calls: list[str] = []

        def fake_test_data_store_connection(profile, env=None, include_schema_summary=False, **kwargs):
            calls.append(profile.profile_id)
            return DataStoreConnectionTestResult(
                profile_id=profile.profile_id,
                engine=profile.engine,
                status="ok",
                message="ok",
                details={"database": "weather", "table_count": 1},
            )

        profile = DataStoreConnectionProfile(
            profile_id="analytics_mysql",
            label="Analytics MySQL",
            store_kind="relational_sql",
            engine="mysql",
            required_env_vars=("ANALYTICS_MYSQL_HOST", "ANALYTICS_MYSQL_DATABASE"),
        )
        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="database",
            engine="mysql",
            asset_name="weather",
            data_store_profile_id="analytics_mysql",
        )

        with patch("api_launcher.database_self_check.test_data_store_connection", fake_test_data_store_connection):
            result = DatabaseAssetVerifier((profile,)).verify(asset)

        self.assertEqual("present", result.status)
        self.assertEqual(["analytics_mysql"], calls)

    def test_database_asset_reports_unknown_data_store_profile(self) -> None:
        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="database",
            engine="mysql",
            asset_name="weather",
            data_store_profile_id="missing_profile",
        )

        result = DatabaseAssetVerifier(()).verify(asset)

        self.assertEqual("error", result.status)
        self.assertIn("Unknown data-store profile", result.error)

    def test_mysql_table_asset_marks_missing_table_missing(self) -> None:
        def fake_test_data_store_connection(profile, env=None, include_schema_summary=False, **kwargs):
            return DataStoreConnectionTestResult(
                profile_id=profile.profile_id,
                engine=profile.engine,
                status="ok",
                message="ok",
                details={"database": "weather", "table": "station", "table_exists": False, "table_count": 0},
            )

        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="table",
            engine="mysql",
            asset_name="station",
            install_location="mysql://weather",
        )

        with patch("api_launcher.database_self_check.test_data_store_connection", fake_test_data_store_connection):
            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("missing", result.status)
        self.assertIn("MySQL table is missing", result.error)

    def test_postgresql_database_asset_detects_schema_fingerprint_drift(self) -> None:
        def fake_test_data_store_connection(profile, env=None, include_schema_summary=False, **kwargs):
            return DataStoreConnectionTestResult(
                profile_id=profile.profile_id,
                engine=profile.engine,
                status="ok",
                message="ok",
                details={"database": "weather", "schema_fingerprint": "actual", "table_count": 2},
            )

        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="database",
            engine="postgresql",
            asset_name="weather",
            schema_fingerprint="expected",
        )

        with patch("api_launcher.database_self_check.test_data_store_connection", fake_test_data_store_connection):
            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("error", result.status)
        self.assertIn("PostgreSQL schema fingerprint drift", result.error)

    def test_postgresql_table_asset_uses_schema_name_for_table_probe(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_test_data_store_connection(profile, env=None, include_schema_summary=False, **kwargs):
            calls.append({"include_schema_summary": include_schema_summary, **kwargs})
            return DataStoreConnectionTestResult(
                profile_id=profile.profile_id,
                engine=profile.engine,
                status="ok",
                message="ok",
                details={"database": "weather", "schema": "archive", "table": "station", "table_exists": True, "table_count": 1},
            )

        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="table",
            engine="postgresql",
            asset_name="archive.station",
            install_location="postgresql://localhost/weather",
        )

        with patch("api_launcher.database_self_check.test_data_store_connection", fake_test_data_store_connection):
            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("present", result.status)
        self.assertEqual("archive", calls[0]["schema_name"])
        self.assertEqual("station", calls[0]["schema_summary_table"])

    def test_postgresql_table_asset_uses_explicit_schema_name_for_table_probe(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_test_data_store_connection(profile, env=None, include_schema_summary=False, **kwargs):
            calls.append({"include_schema_summary": include_schema_summary, **kwargs})
            return DataStoreConnectionTestResult(
                profile_id=profile.profile_id,
                engine=profile.engine,
                status="ok",
                message="ok",
                details={"database": "weather", "schema": "archive", "table": "station", "table_exists": True, "table_count": 1},
            )

        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="table",
            engine="postgresql",
            asset_name="station",
            install_location="postgresql://localhost/weather",
            schema_name="archive",
        )

        with patch("api_launcher.database_self_check.test_data_store_connection", fake_test_data_store_connection):
            result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("present", result.status)
        self.assertEqual("archive", calls[0]["schema_name"])
        self.assertEqual("station", calls[0]["schema_summary_table"])

    def test_repository_self_check_updates_sqlite_database_asset_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_database_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    source_uri=str(asset_db),
                )

                summary = repo.verify_provider_assets(verifier=DatabaseAssetVerifier())

                asset_status = conn.execute("SELECT status FROM provider_installation_assets").fetchone()["status"]
                local_status = conn.execute(
                    "SELECT local_status FROM provider_download_state WHERE provider_id = 'sample_provider'"
                ).fetchone()["local_status"]
            finally:
                conn.close()

        self.assertEqual({"present": 1, "missing": 0, "error": 0, "checked": 1}, summary)
        self.assertEqual("present", asset_status)
        self.assertEqual("imported", local_status)

    def test_repository_self_check_marks_sqlite_schema_drift_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            expected = sqlite_schema_summary(asset_db).schema_fingerprint
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("ALTER TABLE sample ADD COLUMN value TEXT")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_database_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    source_uri=str(asset_db),
                    schema_fingerprint=expected,
                )

                summary = repo.verify_provider_assets(verifier=DatabaseAssetVerifier())

                row = conn.execute(
                    "SELECT status, last_verify_error FROM provider_installation_assets"
                ).fetchone()
                local_status = conn.execute(
                    "SELECT local_status FROM provider_download_state WHERE provider_id = 'sample_provider'"
                ).fetchone()["local_status"]
            finally:
                conn.close()

        self.assertEqual({"present": 0, "missing": 0, "error": 1, "checked": 1}, summary)
        self.assertEqual("error", row["status"])
        self.assertIn("schema fingerprint drift", row["last_verify_error"])
        self.assertEqual("error", local_status)

    def test_repository_self_check_updates_sqlite_table_asset_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY)")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_table_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    table_name="station",
                    source_uri=str(asset_db),
                )

                summary = repo.verify_provider_assets(verifier=DatabaseAssetVerifier())

                row = conn.execute(
                    "SELECT asset_kind, asset_name, status FROM provider_installation_assets"
                ).fetchone()
                local_status = conn.execute(
                    "SELECT local_status FROM provider_download_state WHERE provider_id = 'sample_provider'"
                ).fetchone()["local_status"]
            finally:
                conn.close()

        self.assertEqual({"present": 1, "missing": 0, "error": 0, "checked": 1}, summary)
        self.assertEqual("table", row["asset_kind"])
        self.assertEqual("station", row["asset_name"])
        self.assertEqual("present", row["status"])
        self.assertEqual("imported", local_status)

    def test_repository_self_check_marks_sqlite_table_schema_drift_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY)")
            expected = sqlite_table_schema_summary(asset_db, "station").schema_fingerprint
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("ALTER TABLE station ADD COLUMN value TEXT")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_table_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    table_name="station",
                    source_uri=str(asset_db),
                    schema_fingerprint=expected,
                )

                summary = repo.verify_provider_assets(verifier=DatabaseAssetVerifier())

                row = conn.execute(
                    "SELECT status, last_verify_error FROM provider_installation_assets"
                ).fetchone()
                local_status = conn.execute(
                    "SELECT local_status FROM provider_download_state WHERE provider_id = 'sample_provider'"
                ).fetchone()["local_status"]
            finally:
                conn.close()

        self.assertEqual({"present": 0, "missing": 0, "error": 1, "checked": 1}, summary)
        self.assertEqual("error", row["status"])
        self.assertIn("table schema fingerprint drift", row["last_verify_error"])
        self.assertEqual("error", local_status)

    def test_cli_self_check_databases_updates_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_database_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    source_uri=str(asset_db),
                )
            finally:
                conn.close()
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(["--db", str(launcher_db), "--self-check-databases"])

        self.assertEqual(0, rc)
        self.assertIn("[database-self-check]", output.getvalue())
        self.assertIn("'present': 1", output.getvalue())

    def test_cli_self_check_databases_prints_schema_drift_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            expected = sqlite_schema_summary(asset_db).schema_fingerprint
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("ALTER TABLE sample ADD COLUMN value TEXT")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_database_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    source_uri=str(asset_db),
                    schema_fingerprint=expected,
                )
            finally:
                conn.close()
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(["--db", str(launcher_db), "--self-check-databases"])

        self.assertEqual(0, rc)
        self.assertIn("'error': 1", output.getvalue())
        self.assertIn("schema fingerprint drift", output.getvalue())

    def test_cli_self_check_databases_prints_table_missing_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY)")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_table_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    table_name="missing_station",
                    source_uri=str(asset_db),
                )
            finally:
                conn.close()
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(["--db", str(launcher_db), "--self-check-databases"])

        self.assertEqual(0, rc)
        self.assertIn("'missing': 1", output.getvalue())
        self.assertIn("table sqlite:missing_station", output.getvalue())
        self.assertIn("suggestion=restore_or_reimport_table", output.getvalue())
        self.assertIn("SQLite table is missing", output.getvalue())

    def test_cli_self_check_databases_json_includes_repair_suggestion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY)")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_table_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    table_name="missing_station",
                    source_uri=str(asset_db),
                )
            finally:
                conn.close()
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(["--db", str(launcher_db), "--self-check-databases-json"])

        self.assertEqual(0, rc)
        payload = json.loads(output.getvalue())
        self.assertEqual(1, payload["issue_count"])
        self.assertEqual("restore_or_reimport_table", payload["issues"][0]["repair_suggestion"]["action_id"])
        self.assertFalse(payload["issues"][0]["repair_suggestion"]["can_auto_repair"])

    def test_database_self_check_issues_marks_manifest_backed_sqlite_table_auto_repairable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            launcher_db = root / "launcher.sqlite"
            asset_db = root / "asset.sqlite"
            manifest_path = root / "stations.geojson.gz.manifest.json"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY)")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_table_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    table_name="missing_station",
                    source_format="geojson.gz",
                    source_uri=str(asset_db),
                    notes=f"manifest={manifest_path} payload={root / 'stations.geojson.gz'}",
                )
                repo.verify_provider_assets(verifier=DatabaseAssetVerifier())

                issues = database_self_check_issues(conn, ["sample_provider"])
            finally:
                conn.close()

        self.assertEqual(1, len(issues))
        self.assertEqual("geojson.gz", issues[0].source_format)
        self.assertTrue(issues[0].has_recorded_manifest)
        self.assertTrue(issues[0].repair_suggestion().can_auto_repair)
        self.assertTrue(issues[0].as_dict()["repair_suggestion"]["can_auto_repair"])

    def test_database_self_check_issues_reads_registry_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with closing(sqlite3.connect(asset_db)) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY)")
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="sample_provider",
                        name="Sample",
                        owner="Sample",
                        categories=("test",),
                        geographic_scope="local",
                        docs_url="https://example.test",
                    )
                )
                repo.register_provider_table_asset(
                    "sample_provider",
                    engine="sqlite",
                    database_name="asset.sqlite",
                    table_name="missing_station",
                    source_uri=str(asset_db),
                )
                repo.verify_provider_assets(verifier=DatabaseAssetVerifier())

                issues = database_self_check_issues(conn, ["sample_provider"])
            finally:
                conn.close()

        self.assertEqual(1, len(issues))
        self.assertEqual("sample_provider", issues[0].provider_id)
        self.assertEqual("restore_or_reimport_table", issues[0].repair_suggestion().action_id)
        self.assertFalse(issues[0].repair_suggestion().can_auto_repair)


if __name__ == "__main__":
    unittest.main()
