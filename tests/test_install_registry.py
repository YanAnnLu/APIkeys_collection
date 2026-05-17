from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from api_launcher.db import connect_db
from api_launcher.models import Provider
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


if __name__ == "__main__":
    unittest.main()
