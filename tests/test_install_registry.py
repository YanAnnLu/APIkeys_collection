from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from api_launcher.asset_verifier import AssetVerificationResult
from api_launcher.db import connect_db
from api_launcher.models import Provider
from api_launcher.provenance import schema_fingerprint
from api_launcher.repository import ApiCatalogRepository


class InstallRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.sqlite"
        self.conn = connect_db(self.db_path)
        self.repo = ApiCatalogRepository(self.conn)
        self.repo.init_schema()
        self.provider = Provider(
            provider_id="sample_provider",
            name="Sample Provider",
            owner="Sample Owner",
            categories=("test",),
            geographic_scope="local",
            docs_url="https://example.test/docs",
        )
        self.repo.upsert_provider(self.provider)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmpdir.cleanup()

    def test_manage_unmanage_and_remanage_reuses_install_identity(self) -> None:
        first_id = self.repo.manage_provider_installation("sample_provider", location="mysql://local/sample")
        second_id = self.repo.manage_provider_installation("sample_provider", location="mysql://local/sample")

        self.assertEqual(first_id, second_id)
        self.assertEqual(1, self._count_installations())

        unmanaged_id = self.repo.unmanage_provider_installation("sample_provider")
        self.assertEqual(first_id, unmanaged_id)
        self.assertEqual("unmanaged", self._installation_status(first_id))

        remanaged_id = self.repo.manage_provider_installation("sample_provider", location="mysql://local/sample")
        self.assertEqual(first_id, remanaged_id)
        self.assertEqual(1, self._count_installations())
        self.assertEqual("managed", self._installation_status(first_id))

    def test_assets_are_deduplicated_and_removed_by_uninstall_marker(self) -> None:
        install_id = self.repo.manage_provider_installation("sample_provider", location="mysql://local/sample")
        first_asset = self.repo.register_installation_asset(
            install_id,
            asset_kind="database",
            engine="mysql",
            asset_name="sample",
            uninstall_command="DROP DATABASE `sample`;",
        )
        second_asset = self.repo.register_installation_asset(
            install_id,
            asset_kind="database",
            engine="mysql",
            asset_name="sample",
            uninstall_command="DROP DATABASE `sample`;",
        )

        self.assertEqual(first_asset, second_asset)
        self.assertEqual(1, self._count_assets())

        result = self.repo.uninstall_provider_installation("sample_provider")

        self.assertEqual(install_id, result["install_id"])
        self.assertFalse(result["executed"])
        self.assertEqual(1, len(result["assets"]))
        self.assertEqual("removed", self._installation_status(install_id))
        self.assertEqual("removed", self._asset_status(first_asset))
        self.assertEqual("not_imported", self._local_status())

    def test_destructive_uninstall_execution_is_blocked_until_adapters_exist(self) -> None:
        self.repo.manage_provider_installation("sample_provider", location="mysql://local/sample")

        with self.assertRaises(RuntimeError):
            self.repo.uninstall_provider_installation("sample_provider", execute=True)

    def test_database_assets_store_safe_sql_uninstall_command(self) -> None:
        asset_id = self.repo.register_provider_database_asset(
            "sample_provider",
            engine="mysql",
            database_name="sample_db",
        )
        row = self.conn.execute(
            """
            SELECT engine, asset_name, uninstall_command
            FROM provider_installation_assets
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()

        self.assertEqual("mysql", row["engine"])
        self.assertEqual("sample_db", row["asset_name"])
        self.assertEqual("DROP DATABASE IF EXISTS `sample_db`;", row["uninstall_command"])

    def test_database_asset_rejects_unsafe_sql_identifier(self) -> None:
        with self.assertRaises(ValueError):
            self.repo.register_provider_database_asset(
                "sample_provider",
                engine="mysql",
                database_name="sample; DROP DATABASE mysql;",
            )

    def test_table_assets_share_database_install_but_keep_table_identity(self) -> None:
        db_path = str(Path(self.tmpdir.name) / "asset.sqlite")

        first_asset = self.repo.register_provider_table_asset(
            "sample_provider",
            engine="sqlite",
            database_name="asset.sqlite",
            table_name="station",
            source_uri=db_path,
        )
        second_asset = self.repo.register_provider_table_asset(
            "sample_provider",
            engine="sqlite",
            database_name="asset.sqlite",
            table_name="observation",
            source_uri=db_path,
        )
        rows = self.conn.execute(
            """
            SELECT install_id, asset_kind, asset_name, source_uri, uninstall_command
            FROM provider_installation_assets
            ORDER BY asset_name
            """
        ).fetchall()

        self.assertNotEqual(first_asset, second_asset)
        self.assertEqual(2, len(rows))
        self.assertEqual(1, self._count_installations())
        self.assertEqual({"observation", "station"}, {row["asset_name"] for row in rows})
        self.assertEqual({"table"}, {row["asset_kind"] for row in rows})
        self.assertEqual({db_path}, {row["source_uri"] for row in rows})
        self.assertEqual({""}, {row["uninstall_command"] for row in rows})

    def test_sql_table_asset_uses_database_location_not_source_uri_as_install_owner(self) -> None:
        self.repo.register_provider_table_asset(
            "sample_provider",
            engine="mysql",
            database_name="weather",
            table_name="station",
            source_uri="https://example.test/source.csv",
        )

        asset = self.repo.managed_asset_records("sample_provider")[0]

        self.assertEqual("mysql://weather", asset.install_location)
        self.assertEqual("https://example.test/source.csv", asset.source_uri)

    def test_table_assets_store_profile_and_schema_selection(self) -> None:
        asset_id = self.repo.register_provider_table_asset(
            "sample_provider",
            engine="postgresql",
            database_name="weather",
            table_name="station",
            data_store_profile_id="analytics_postgres",
            schema_name="archive",
        )
        asset = self.repo.managed_asset_records("sample_provider")[0]
        row = self.conn.execute(
            """
            SELECT data_store_profile_id, schema_name
            FROM provider_installation_assets
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()

        self.assertEqual("analytics_postgres", row["data_store_profile_id"])
        self.assertEqual("archive", row["schema_name"])
        self.assertEqual("analytics_postgres", asset.data_store_profile_id)
        self.assertEqual("archive", asset.schema_name)

    def test_update_database_asset_connection_metadata_resets_self_check_error(self) -> None:
        asset_id = self.repo.register_provider_table_asset(
            "sample_provider",
            engine="postgresql",
            database_name="weather",
            table_name="station",
            data_store_profile_id="old_postgres",
            schema_name="archive",
        )
        self.conn.execute(
            """
            UPDATE provider_installation_assets
            SET status = 'error',
                last_verified_at = '2026-05-20T00:00:00Z',
                last_verify_error = 'Unknown data-store profile for asset: old_postgres.'
            WHERE asset_id = ?
            """,
            (asset_id,),
        )
        self.conn.commit()

        changed = self.repo.update_database_asset_connection_metadata(
            asset_id,
            data_store_profile_id="postgres_default",
            schema_name="public",
        )
        row = self.conn.execute(
            """
            SELECT data_store_profile_id, schema_name, status, last_verified_at, last_verify_error
            FROM provider_installation_assets
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()

        self.assertTrue(changed)
        self.assertEqual("postgres_default", row["data_store_profile_id"])
        self.assertEqual("public", row["schema_name"])
        self.assertEqual("managed", row["status"])
        self.assertEqual("", row["last_verified_at"])
        self.assertEqual("", row["last_verify_error"])

    def test_update_database_asset_connection_metadata_rejects_unsafe_schema(self) -> None:
        asset_id = self.repo.register_provider_table_asset(
            "sample_provider",
            engine="postgresql",
            database_name="weather",
            table_name="station",
        )

        with self.assertRaises(ValueError):
            self.repo.update_database_asset_connection_metadata(asset_id, schema_name="public;drop")

    def test_verify_assets_marks_missing_database(self) -> None:
        self.repo.register_provider_database_asset(
            "sample_provider",
            engine="mysql",
            database_name="sample_db",
        )

        summary = self.repo.verify_provider_assets(verifier=StaticVerifier("missing"))

        self.assertEqual({"present": 0, "missing": 1, "error": 0, "checked": 1}, summary)
        self.assertEqual("missing", self._latest_installation_status())
        self.assertEqual("missing", self._local_status())

    def test_verify_assets_marks_present_database(self) -> None:
        self.repo.register_provider_database_asset(
            "sample_provider",
            engine="mysql",
            database_name="sample_db",
        )

        summary = self.repo.verify_provider_assets(verifier=StaticVerifier("present"))

        self.assertEqual({"present": 1, "missing": 0, "error": 0, "checked": 1}, summary)
        self.assertEqual("managed", self._latest_installation_status())
        self.assertEqual("imported", self._local_status())

    def test_verify_assets_can_filter_database_kinds(self) -> None:
        install_id = self.repo.manage_provider_installation("sample_provider", location="downloads/sample.csv")
        file_asset_id = self.repo.register_installation_asset(
            install_id,
            asset_kind="file",
            engine="filesystem",
            asset_name="sample.csv",
        )
        self.repo.register_provider_database_asset(
            "sample_provider",
            engine="mysql",
            database_name="sample_db",
        )

        summary = self.repo.verify_provider_assets(
            verifier=StaticVerifier("missing"),
            asset_kinds=("database", "table"),
        )

        self.assertEqual({"present": 0, "missing": 1, "error": 0, "checked": 1}, summary)
        self.assertEqual("managed", self._asset_status(file_asset_id))

    def test_manual_csv_or_json_imports_keep_provenance_and_schema_fingerprint(self) -> None:
        fingerprint = schema_fingerprint(["station_id", "temperature_c", "observed_at"])
        asset_id = self.repo.register_provider_database_asset(
            "sample_provider",
            engine="mysql",
            database_name="manual_weather_import",
            asset_role="curated",
            source_format="csv",
            source_uri="K:/imports/weather.csv",
            schema_fingerprint=fingerprint,
        )
        asset = self.repo.managed_asset_records("sample_provider")[0]
        row = self.conn.execute(
            """
            SELECT asset_role, source_format, source_uri, schema_fingerprint
            FROM provider_installation_assets
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()

        self.assertEqual("curated", row["asset_role"])
        self.assertEqual("csv", row["source_format"])
        self.assertEqual("K:/imports/weather.csv", row["source_uri"])
        self.assertEqual(fingerprint, row["schema_fingerprint"])
        self.assertEqual("curated", asset.asset_role)
        self.assertEqual("csv", asset.source_format)
        self.assertEqual("mysql://manual_weather_import", asset.install_location)

    def test_derived_assets_are_not_confused_with_upstream_source_assets(self) -> None:
        source_asset_id = self.repo.register_provider_database_asset(
            "sample_provider",
            engine="mysql",
            database_name="noaa_raw",
            asset_role="source",
            source_format="api",
        )
        derived_asset_id = self.repo.register_provider_database_asset(
            "sample_provider",
            engine="mysql",
            database_name="noaa_model_output",
            asset_role="derived",
            derived_from_asset_id=source_asset_id,
            source_format="manual",
        )

        rows = self.conn.execute(
            """
            SELECT asset_name, asset_role, derived_from_asset_id
            FROM provider_installation_assets
            ORDER BY asset_name
            """
        ).fetchall()

        by_name = {row["asset_name"]: row for row in rows}
        self.assertEqual(source_asset_id, by_name["noaa_model_output"]["derived_from_asset_id"])
        self.assertEqual("derived", by_name["noaa_model_output"]["asset_role"])
        self.assertNotEqual(source_asset_id, derived_asset_id)

    def _count_installations(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM provider_installations").fetchone()[0]

    def _count_assets(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM provider_installation_assets").fetchone()[0]

    def _installation_status(self, install_id: str) -> str:
        row = self.conn.execute(
            "SELECT status FROM provider_installations WHERE install_id = ?",
            (install_id,),
        ).fetchone()
        return row["status"]

    def _asset_status(self, asset_id: str) -> str:
        row = self.conn.execute(
            "SELECT status FROM provider_installation_assets WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
        return row["status"]

    def _local_status(self) -> str:
        row = self.conn.execute(
            "SELECT local_status FROM provider_download_state WHERE provider_id = 'sample_provider'",
        ).fetchone()
        return row["local_status"]

    def _latest_installation_status(self) -> str:
        row = self.conn.execute(
            "SELECT status FROM provider_installations ORDER BY updated_at DESC LIMIT 1",
        ).fetchone()
        return row["status"]


class StaticVerifier:
    def __init__(self, status: str):
        self.status = status

    def verify(self, asset):
        return AssetVerificationResult(asset.asset_id, self.status)


if __name__ == "__main__":
    unittest.main()
