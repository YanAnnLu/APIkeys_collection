from __future__ import annotations

import sqlite3
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.asset_verifier import AssetRecord
from api_launcher.database_self_check import DatabaseAssetVerifier, database_self_check_target
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


if __name__ == "__main__":
    unittest.main()
