from __future__ import annotations

import sqlite3
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_launcher.core import main
from api_launcher.asset_verifier import AssetRecord
from api_launcher.data_store_connections import DataStoreConnectionTestResult
from api_launcher.database_self_check import (
    DatabaseAssetVerifier,
    database_self_check_target,
    sqlite_schema_summary,
    sqlite_table_schema_summary,
)
from api_launcher.db import connect_db
from api_launcher.models import Provider
from api_launcher.repository import ApiCatalogRepository


class DatabaseSelfCheckTests(unittest.TestCase):
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

    def test_sqlite_asset_verifier_marks_existing_database_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with sqlite3.connect(db_path) as conn:
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
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")

            summary = sqlite_schema_summary(db_path)

        self.assertEqual(("station",), summary.tables)
        self.assertEqual(2, len(summary.column_signatures))
        self.assertEqual(64, len(summary.schema_fingerprint))

    def test_sqlite_table_schema_summary_fingerprints_one_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
                conn.execute("CREATE TABLE observation (id INTEGER PRIMARY KEY, station_id INTEGER, value REAL)")

            summary = sqlite_table_schema_summary(db_path, "station")

        self.assertEqual(("station",), summary.tables)
        self.assertEqual(2, len(summary.column_signatures))
        self.assertEqual(64, len(summary.schema_fingerprint))

    def test_sqlite_asset_verifier_detects_schema_fingerprint_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asset.sqlite"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY, name TEXT)")
            expected = sqlite_schema_summary(db_path).schema_fingerprint
            with sqlite3.connect(db_path) as conn:
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
            with sqlite3.connect(db_path) as conn:
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
            with sqlite3.connect(db_path) as conn:
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
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY, name TEXT)")
            expected = sqlite_table_schema_summary(db_path, "station").schema_fingerprint
            with sqlite3.connect(db_path) as conn:
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

    def test_non_sqlite_table_assets_report_unimplemented_table_check(self) -> None:
        asset = AssetRecord(
            asset_id="asset_1",
            install_id="inst_1",
            provider_id="sample",
            asset_kind="table",
            engine="postgresql",
            asset_name="station",
        )

        result = DatabaseAssetVerifier().verify(asset)

        self.assertEqual("error", result.status)
        self.assertIn("Table self-check is not implemented", result.error)

    def test_mysql_database_asset_compares_schema_fingerprint_when_available(self) -> None:
        calls: list[bool] = []

        def fake_test_data_store_connection(profile, env=None, include_schema_summary=False):
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

    def test_postgresql_database_asset_detects_schema_fingerprint_drift(self) -> None:
        def fake_test_data_store_connection(profile, env=None, include_schema_summary=False):
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

    def test_repository_self_check_updates_sqlite_database_asset_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            asset_db = Path(tmpdir) / "asset.sqlite"
            with sqlite3.connect(asset_db) as conn:
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
            with sqlite3.connect(asset_db) as conn:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            expected = sqlite_schema_summary(asset_db).schema_fingerprint
            with sqlite3.connect(asset_db) as conn:
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
            with sqlite3.connect(asset_db) as conn:
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
            with sqlite3.connect(asset_db) as conn:
                conn.execute("CREATE TABLE station (id INTEGER PRIMARY KEY)")
            expected = sqlite_table_schema_summary(asset_db, "station").schema_fingerprint
            with sqlite3.connect(asset_db) as conn:
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
            with sqlite3.connect(asset_db) as conn:
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
            with sqlite3.connect(asset_db) as conn:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            expected = sqlite_schema_summary(asset_db).schema_fingerprint
            with sqlite3.connect(asset_db) as conn:
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
            with sqlite3.connect(asset_db) as conn:
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
        self.assertIn("SQLite table is missing", output.getvalue())


if __name__ == "__main__":
    unittest.main()
