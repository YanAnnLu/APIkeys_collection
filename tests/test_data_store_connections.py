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
    mysql_column_signatures,
    mysql_schema_summary_from_cursor,
    mysql_table_schema_summary_from_cursor,
    mysql_table_count,
    mysql_table_exists,
    mysql_table_names,
    postgresql_column_signatures,
    postgresql_schema_summary_from_cursor,
    postgresql_table_schema_summary_from_cursor,
    postgresql_table_count,
    postgresql_table_exists,
    postgresql_table_names,
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

    def test_mysql_information_schema_helpers_build_table_and_column_signatures(self) -> None:
        cursor = FakeCursor(
            fetchone_rows=[(2,), (1,)],
            fetchall_rows=[
                [("observation",), ("station",)],
                [
                    (1, "id", "int", "NO", None, "PRI"),
                    (2, "name", "varchar", "YES", "unknown", ""),
                ],
            ],
        )

        count = mysql_table_count(cursor, "weather")
        names = mysql_table_names(cursor, "weather")
        exists = mysql_table_exists(cursor, "weather", "station")
        signatures = mysql_column_signatures(cursor, "weather", "station")

        self.assertEqual(2, count)
        self.assertEqual(("observation", "station"), names)
        self.assertTrue(exists)
        self.assertEqual(
            (
                "station|1|id|INT|1|1|",
                "station|2|name|VARCHAR|0|0|default",
            ),
            signatures,
        )
        self.assertEqual(("weather", "station"), cursor.executed[-1][1])

    def test_mysql_schema_summary_fingerprints_all_tables(self) -> None:
        cursor = FakeCursor(
            fetchall_rows=[
                [("station",)],
                [(1, "id", "int", "NO", None, "PRI")],
            ],
        )

        summary = mysql_schema_summary_from_cursor(cursor, "weather")

        self.assertEqual("mysql", summary.engine)
        self.assertEqual("weather", summary.database)
        self.assertEqual(("station",), summary.tables)
        self.assertEqual(1, summary.table_count)
        self.assertEqual(64, len(summary.schema_fingerprint))

    def test_mysql_table_schema_summary_reports_missing_table(self) -> None:
        cursor = FakeCursor(fetchone_rows=[None])

        summary = mysql_table_schema_summary_from_cursor(cursor, "weather", "missing_station")

        self.assertEqual(0, summary.table_count)
        self.assertEqual((), summary.tables)
        self.assertEqual(64, len(summary.schema_fingerprint))

    def test_postgresql_information_schema_helpers_build_table_and_column_signatures(self) -> None:
        cursor = FakeCursor(
            fetchone_rows=[(1,), None],
            fetchall_rows=[
                [("station",)],
                [
                    (1, "id", "integer", "NO", None, 1),
                    (2, "name", "text", "YES", None, 0),
                ],
            ],
        )

        count = postgresql_table_count(cursor, "public")
        names = postgresql_table_names(cursor, "public")
        exists = postgresql_table_exists(cursor, "missing_station", "public")
        signatures = postgresql_column_signatures(cursor, "station", "public")

        self.assertEqual(1, count)
        self.assertEqual(("station",), names)
        self.assertFalse(exists)
        self.assertEqual(
            (
                "station|1|id|INTEGER|1|1|",
                "station|2|name|TEXT|0|0|",
            ),
            signatures,
        )
        self.assertEqual(("public", "station"), cursor.executed[-1][1])

    def test_postgresql_schema_summary_fingerprints_public_schema(self) -> None:
        cursor = FakeCursor(
            fetchall_rows=[
                [("station",)],
                [(1, "id", "integer", "NO", None, 1)],
            ],
        )

        summary = postgresql_schema_summary_from_cursor(cursor, database="weather", schema="public")

        self.assertEqual("postgresql", summary.engine)
        self.assertEqual("weather", summary.database)
        self.assertEqual("public", summary.schema)
        self.assertEqual(("station",), summary.tables)
        self.assertEqual(64, len(summary.schema_fingerprint))

    def test_postgresql_table_schema_summary_fingerprints_one_table(self) -> None:
        cursor = FakeCursor(
            fetchone_rows=[(1,)],
            fetchall_rows=[[(1, "id", "integer", "NO", None, 1)]],
        )

        summary = postgresql_table_schema_summary_from_cursor(cursor, "weather", "station", schema="public")

        self.assertEqual(1, summary.table_count)
        self.assertEqual(("station",), summary.tables)
        self.assertEqual(1, len(summary.column_signatures))
        self.assertEqual(64, len(summary.schema_fingerprint))

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


class FakeCursor:
    def __init__(
        self,
        fetchone_rows: list[object] | None = None,
        fetchall_rows: list[list[tuple[object, ...]]] | None = None,
    ):
        self.fetchone_rows = list(fetchone_rows or [])
        self.fetchall_rows = list(fetchall_rows or [])
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executed.append((sql, params))

    def fetchone(self) -> object:
        return self.fetchone_rows.pop(0)

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.fetchall_rows.pop(0)


if __name__ == "__main__":
    unittest.main()
