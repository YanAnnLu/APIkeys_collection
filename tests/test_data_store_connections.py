from __future__ import annotations

import sqlite3
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_launcher.core import main
from api_launcher.data_store_connections import (
    DEFAULT_DATA_STORE_PROFILES,
    DataStoreConnectionProfile,
    data_store_profile,
    data_store_profiles_from_config,
    data_store_profiles_by_kind,
    test_data_store_connection,
)


class DataStoreConnectionTests(unittest.TestCase):
    def test_profiles_cover_relational_and_non_relational_stores(self) -> None:
        kinds = {profile.store_kind for profile in DEFAULT_DATA_STORE_PROFILES}

        self.assertIn("relational_sql", kinds)
        self.assertIn("document_nosql", kinds)
        self.assertIn("object_storage", kinds)
        self.assertIn("vector_database", kinds)

    def test_mongodb_profile_uses_uri_env(self) -> None:
        profile = data_store_profile("mongodb_default")

        self.assertIsNotNone(profile)
        self.assertEqual(("APIKEYS_MONGODB_URI",), profile.required_env_vars)

    def test_mysql_profile_keeps_sql_credentials_in_env_contract(self) -> None:
        profile = data_store_profile("mysql_default")

        self.assertIsNotNone(profile)
        self.assertEqual("relational_sql", profile.store_kind)
        self.assertIn("APIKEYS_MYSQL_PASSWORD", profile.required_env_vars)
        self.assertIn("APIKEYS_MYSQL_PORT", profile.optional_env_vars)

    def test_profiles_can_be_filtered_by_kind(self) -> None:
        profiles = data_store_profiles_by_kind("relational_sql")

        self.assertTrue(all(profile.store_kind == "relational_sql" for profile in profiles))

    def test_profiles_can_be_loaded_from_integration_config(self) -> None:
        profiles = data_store_profiles_from_config(
            {
                "data_store_connection_profiles": [
                    {
                        "id": "sqlite_test",
                        "label": "SQLite test",
                        "store_kind": "embedded_sql",
                        "engine": "sqlite",
                        "required_env_vars": ["APIKEYS_SQLITE_PATH"],
                    }
                ]
            }
        )

        self.assertEqual("sqlite_test", profiles[0].profile_id)
        self.assertEqual("sqlite", profiles[0].engine)

    def test_sqlite_connection_test_opens_existing_database_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sample.sqlite"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            profile = data_store_profile("sqlite_local")
            self.assertIsNotNone(profile)

            result = test_data_store_connection(profile, {"APIKEYS_SQLITE_PATH": str(db_path)})

        self.assertTrue(result.ok)
        self.assertEqual("ok", result.status)
        self.assertEqual(1, result.details["table_count"])

    def test_sqlite_connection_test_does_not_create_missing_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.sqlite"
            profile = data_store_profile("sqlite_local")
            self.assertIsNotNone(profile)

            result = test_data_store_connection(profile, {"APIKEYS_SQLITE_PATH": str(db_path)})

            self.assertFalse(db_path.exists())

        self.assertEqual("missing_target", result.status)

    def test_missing_env_is_reported_before_driver_checks(self) -> None:
        profile = data_store_profile("mysql_default")
        self.assertIsNotNone(profile)

        result = test_data_store_connection(profile, {})

        self.assertEqual("missing_env", result.status)
        self.assertIn("APIKEYS_MYSQL_PASSWORD", result.details["missing_env_vars"])

    def test_mysql_missing_optional_driver_is_reported(self) -> None:
        profile = data_store_profile("mysql_default")
        self.assertIsNotNone(profile)

        result = test_data_store_connection(
            profile,
            {
                "APIKEYS_MYSQL_HOST": "localhost",
                "APIKEYS_MYSQL_DATABASE": "sample",
                "APIKEYS_MYSQL_USER": "sample",
                "APIKEYS_MYSQL_PASSWORD": "secret",
            },
        )

        self.assertIn(result.status, {"dependency_missing", "error", "ok"})
        if result.status == "dependency_missing":
            self.assertEqual("mysql.connector", result.details["driver"])

    def test_postgresql_missing_optional_driver_is_reported(self) -> None:
        profile = data_store_profile("postgres_default")
        self.assertIsNotNone(profile)

        result = test_data_store_connection(
            profile,
            {
                "APIKEYS_POSTGRES_HOST": "localhost",
                "APIKEYS_POSTGRES_DATABASE": "sample",
                "APIKEYS_POSTGRES_USER": "sample",
                "APIKEYS_POSTGRES_PASSWORD": "secret",
            },
        )

        self.assertIn(result.status, {"dependency_missing", "error", "ok"})
        if result.status == "dependency_missing":
            self.assertIn("psycopg", result.details["driver_options"])

    def test_unsupported_store_kinds_are_reported(self) -> None:
        profile = DataStoreConnectionProfile(
            profile_id="custom_vector",
            label="Custom vector",
            store_kind="vector_database",
            engine="custom_vector",
            required_env_vars=(),
        )

        result = test_data_store_connection(profile, {})

        self.assertEqual("unsupported", result.status)

    def test_cli_can_run_sqlite_connection_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sample.sqlite"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            output = io.StringIO()

            with patch.dict("os.environ", {"APIKEYS_SQLITE_PATH": str(db_path)}, clear=False):
                with redirect_stdout(output):
                    rc = main(["--db", str(Path(tmpdir) / "launcher.sqlite"), "--test-data-store", "sqlite_local"])

        self.assertEqual(0, rc)
        self.assertIn("[data-store] sqlite_local status=ok", output.getvalue())


if __name__ == "__main__":
    unittest.main()
