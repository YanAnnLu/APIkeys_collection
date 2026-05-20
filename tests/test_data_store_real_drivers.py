from __future__ import annotations

import os
import re
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from api_launcher.data_store_connections import data_store_profile, test_data_store_connection
from api_launcher.database_self_check import DatabaseAssetVerifier
from api_launcher.db import connect_db
from api_launcher.models import Provider
from api_launcher.repository import ApiCatalogRepository


REAL_DB_SMOKE_FLAG = "APIKEYS_RUN_REAL_DB_SMOKE"
REAL_DB_WRITE_FLAG = "APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE"


class RealDataStoreDriverSmokeTests(unittest.TestCase):
    def test_mysql_real_driver_smoke_when_enabled(self) -> None:
        env = _real_db_env_or_skip(
            self,
            (
                REAL_DB_SMOKE_FLAG,
                "APIKEYS_MYSQL_HOST",
                "APIKEYS_MYSQL_DATABASE",
                "APIKEYS_MYSQL_USER",
                "APIKEYS_MYSQL_PASSWORD",
            ),
        )
        profile = data_store_profile("mysql_default")
        self.assertIsNotNone(profile)

        result = test_data_store_connection(profile, env, include_schema_summary=True)

        if result.status == "dependency_missing":
            self.skipTest(result.message)
        self.assertEqual("ok", result.status, result.message)
        self.assertEqual(env["APIKEYS_MYSQL_DATABASE"], result.details["database"])
        self.assertIsInstance(result.details["table_count"], int)
        self.assertEqual(64, len(str(result.details["schema_fingerprint"])))

    def test_mysql_registry_backed_table_self_check_when_enabled(self) -> None:
        env = _real_db_write_env_or_skip(
            self,
            (
                REAL_DB_SMOKE_FLAG,
                REAL_DB_WRITE_FLAG,
                "APIKEYS_MYSQL_HOST",
                "APIKEYS_MYSQL_DATABASE",
                "APIKEYS_MYSQL_USER",
                "APIKEYS_MYSQL_PASSWORD",
            ),
        )
        profile = data_store_profile("mysql_default")
        self.assertIsNotNone(profile)
        table_name = f"apikeys_ci_registry_smoke_{os.getpid()}"
        missing_table_name = f"{table_name}_missing"
        _mysql_drop_table(env, table_name)
        _mysql_drop_table(env, missing_table_name)
        try:
            _mysql_create_smoke_table(env, table_name)
            schema_result = test_data_store_connection(
                profile,
                env,
                include_schema_summary=True,
                schema_summary_table=table_name,
            )
            if schema_result.status == "dependency_missing":
                self.skipTest(schema_result.message)
            self.assertEqual("ok", schema_result.status, schema_result.message)

            summary, rows = _run_registry_self_check(
                database_name=env["APIKEYS_MYSQL_DATABASE"],
                engine="mysql",
                schema_fingerprint=str(schema_result.details["schema_fingerprint"]),
                schema_name="",
                table_name=table_name,
                missing_table_name=missing_table_name,
            )
        finally:
            _mysql_drop_table(env, table_name)
            _mysql_drop_table(env, missing_table_name)

        self.assertEqual({"present": 1, "missing": 1, "error": 0, "checked": 2}, summary)
        self.assertEqual("present", rows[table_name]["status"])
        self.assertEqual("missing", rows[missing_table_name]["status"])
        self.assertIn("MySQL table is missing", rows[missing_table_name]["last_verify_error"])

    def test_postgresql_real_driver_smoke_when_enabled(self) -> None:
        env = _real_db_env_or_skip(
            self,
            (
                REAL_DB_SMOKE_FLAG,
                "APIKEYS_POSTGRES_HOST",
                "APIKEYS_POSTGRES_DATABASE",
                "APIKEYS_POSTGRES_USER",
                "APIKEYS_POSTGRES_PASSWORD",
            ),
        )
        profile = data_store_profile("postgres_default")
        self.assertIsNotNone(profile)
        schema_name = str(env.get("APIKEYS_POSTGRES_SCHEMA") or "public").strip() or "public"

        result = test_data_store_connection(
            profile,
            env,
            include_schema_summary=True,
            schema_name=schema_name,
        )

        if result.status == "dependency_missing":
            self.skipTest(result.message)
        self.assertEqual("ok", result.status, result.message)
        self.assertEqual(env["APIKEYS_POSTGRES_DATABASE"], result.details["database"])
        self.assertEqual(schema_name, result.details["schema"])
        self.assertIsInstance(result.details["table_count"], int)
        self.assertEqual(64, len(str(result.details["schema_fingerprint"])))

    def test_postgresql_registry_backed_table_self_check_when_enabled(self) -> None:
        env = _real_db_write_env_or_skip(
            self,
            (
                REAL_DB_SMOKE_FLAG,
                REAL_DB_WRITE_FLAG,
                "APIKEYS_POSTGRES_HOST",
                "APIKEYS_POSTGRES_DATABASE",
                "APIKEYS_POSTGRES_USER",
                "APIKEYS_POSTGRES_PASSWORD",
            ),
        )
        profile = data_store_profile("postgres_default")
        self.assertIsNotNone(profile)
        schema_name = str(env.get("APIKEYS_POSTGRES_SCHEMA") or "public").strip() or "public"
        _validate_sql_identifier(schema_name)
        table_name = f"apikeys_ci_registry_smoke_{os.getpid()}"
        missing_table_name = f"{table_name}_missing"
        _postgresql_drop_table(env, schema_name, table_name)
        _postgresql_drop_table(env, schema_name, missing_table_name)
        try:
            _postgresql_create_smoke_table(env, schema_name, table_name)
            schema_result = test_data_store_connection(
                profile,
                env,
                include_schema_summary=True,
                schema_summary_table=table_name,
                schema_name=schema_name,
            )
            if schema_result.status == "dependency_missing":
                self.skipTest(schema_result.message)
            self.assertEqual("ok", schema_result.status, schema_result.message)

            summary, rows = _run_registry_self_check(
                database_name=env["APIKEYS_POSTGRES_DATABASE"],
                engine="postgresql",
                schema_fingerprint=str(schema_result.details["schema_fingerprint"]),
                schema_name=schema_name,
                table_name=table_name,
                missing_table_name=missing_table_name,
            )
        finally:
            _postgresql_drop_table(env, schema_name, table_name)
            _postgresql_drop_table(env, schema_name, missing_table_name)

        self.assertEqual({"present": 1, "missing": 1, "error": 0, "checked": 2}, summary)
        self.assertEqual("present", rows[table_name]["status"])
        self.assertEqual("missing", rows[missing_table_name]["status"])
        self.assertIn("PostgreSQL table is missing", rows[missing_table_name]["last_verify_error"])


def _real_db_env_or_skip(test_case: unittest.TestCase, required_names: tuple[str, ...]) -> dict[str, str]:
    env = {name: str(os.environ.get(name) or "").strip() for name in required_names}
    if env.get(REAL_DB_SMOKE_FLAG) != "1":
        test_case.skipTest(f"Set {REAL_DB_SMOKE_FLAG}=1 to run real database driver smoke tests.")
    missing = tuple(name for name, value in env.items() if not value)
    if missing:
        test_case.skipTest(f"Missing real database smoke env vars: {', '.join(missing)}")
    return dict(os.environ)


def _real_db_write_env_or_skip(test_case: unittest.TestCase, required_names: tuple[str, ...]) -> dict[str, str]:
    env = _real_db_env_or_skip(test_case, required_names)
    if str(env.get(REAL_DB_WRITE_FLAG) or "").strip() != "1":
        test_case.skipTest(f"Set {REAL_DB_WRITE_FLAG}=1 to run registry-backed real database self-check smoke tests.")
    return env


def _run_registry_self_check(
    database_name: str,
    engine: str,
    schema_fingerprint: str,
    schema_name: str,
    table_name: str,
    missing_table_name: str,
) -> tuple[dict[str, int], dict[str, dict[str, str]]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        launcher_db = Path(tmpdir) / "launcher.sqlite"
        conn = connect_db(launcher_db)
        try:
            repo = ApiCatalogRepository(conn)
            repo.init_schema()
            repo.upsert_provider(
                Provider(
                    provider_id=f"real_{engine}_provider",
                    name=f"Real {engine} smoke provider",
                    owner="APIkeys CI",
                    categories=("test",),
                    geographic_scope="local",
                    docs_url="https://example.test",
                )
            )
            for asset_table_name, fingerprint in (
                (table_name, schema_fingerprint),
                (missing_table_name, ""),
            ):
                repo.register_provider_table_asset(
                    f"real_{engine}_provider",
                    engine=engine,
                    database_name=database_name,
                    table_name=asset_table_name,
                    schema_fingerprint=fingerprint,
                    data_store_profile_id=f"{'postgres' if engine == 'postgresql' else engine}_default",
                    schema_name=schema_name,
                )
            summary = repo.verify_provider_assets(verifier=DatabaseAssetVerifier())
            rows = {
                row["asset_name"]: {
                    "status": row["status"],
                    "last_verify_error": row["last_verify_error"] or "",
                }
                for row in conn.execute(
                    """
                    SELECT asset_name, status, last_verify_error
                    FROM provider_installation_assets
                    ORDER BY asset_name
                    """
                ).fetchall()
            }
        finally:
            conn.close()
    return summary, rows


def _mysql_connection(env: dict[str, str]):
    try:
        import mysql.connector  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest("Optional Python driver mysql-connector-python is not installed.") from exc
    return mysql.connector.connect(
        host=env["APIKEYS_MYSQL_HOST"],
        port=int(env.get("APIKEYS_MYSQL_PORT") or 3306),
        database=env["APIKEYS_MYSQL_DATABASE"],
        user=env["APIKEYS_MYSQL_USER"],
        password=env["APIKEYS_MYSQL_PASSWORD"],
        connection_timeout=5,
    )


def _mysql_create_smoke_table(env: dict[str, str], table_name: str) -> None:
    table = _validate_sql_identifier(table_name)
    with closing(_mysql_connection(env)) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f"CREATE TABLE {table} (id INT PRIMARY KEY, name VARCHAR(40) NOT NULL)")
            cursor.execute(f"INSERT INTO {table} (id, name) VALUES (1, 'sample')")
            conn.commit()
        finally:
            cursor.close()


def _mysql_drop_table(env: dict[str, str], table_name: str) -> None:
    table = _validate_sql_identifier(table_name)
    with closing(_mysql_connection(env)) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
        finally:
            cursor.close()


def _postgresql_connection(env: dict[str, str]):
    try:
        import psycopg  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest("Optional Python driver psycopg is not installed.") from exc
    return psycopg.connect(
        host=env["APIKEYS_POSTGRES_HOST"],
        port=int(env.get("APIKEYS_POSTGRES_PORT") or 5432),
        dbname=env["APIKEYS_POSTGRES_DATABASE"],
        user=env["APIKEYS_POSTGRES_USER"],
        password=env["APIKEYS_POSTGRES_PASSWORD"],
        connect_timeout=5,
    )


def _postgresql_create_smoke_table(env: dict[str, str], schema_name: str, table_name: str) -> None:
    schema = _validate_sql_identifier(schema_name)
    table = _validate_sql_identifier(table_name)
    with _postgresql_connection(env) as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            cursor.execute(f"CREATE TABLE {schema}.{table} (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            cursor.execute(f"INSERT INTO {schema}.{table} (id, name) VALUES (1, 'sample')")


def _postgresql_drop_table(env: dict[str, str], schema_name: str, table_name: str) -> None:
    schema = _validate_sql_identifier(schema_name)
    table = _validate_sql_identifier(table_name)
    with _postgresql_connection(env) as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {schema}.{table}")


def _validate_sql_identifier(value: str) -> str:
    raw = value.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", raw):
        raise ValueError(f"Unsafe test SQL identifier: {value!r}")
    return raw


if __name__ == "__main__":
    unittest.main()
