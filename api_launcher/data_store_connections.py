from __future__ import annotations

import importlib.util
import os
import sqlite3
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataStoreConnectionProfile:
    profile_id: str
    label: str
    store_kind: str
    engine: str
    required_env_vars: tuple[str, ...]
    optional_env_vars: tuple[str, ...] = ()
    status: str = "skeleton"
    notes: str = ""


@dataclass(frozen=True)
class DataStoreConnectionTestResult:
    profile_id: str
    engine: str
    status: str
    message: str
    details: dict[str, object]

    @property
    def ok(self) -> bool:
        return self.status == "ok"


DEFAULT_DATA_STORE_PROFILES = (
    DataStoreConnectionProfile(
        profile_id="mysql_default",
        label="MySQL default",
        store_kind="relational_sql",
        engine="mysql",
        required_env_vars=("APIKEYS_MYSQL_HOST", "APIKEYS_MYSQL_DATABASE", "APIKEYS_MYSQL_USER", "APIKEYS_MYSQL_PASSWORD"),
        optional_env_vars=("APIKEYS_MYSQL_PORT",),
        notes="Relational SQL profile for MySQL self-check and future install/uninstall adapters.",
    ),
    DataStoreConnectionProfile(
        profile_id="postgres_default",
        label="PostgreSQL default",
        store_kind="relational_sql",
        engine="postgresql",
        required_env_vars=("APIKEYS_POSTGRES_HOST", "APIKEYS_POSTGRES_DATABASE", "APIKEYS_POSTGRES_USER", "APIKEYS_POSTGRES_PASSWORD"),
        optional_env_vars=("APIKEYS_POSTGRES_PORT",),
        notes="Reserved for PostgreSQL introspection.",
    ),
    DataStoreConnectionProfile(
        profile_id="sqlite_local",
        label="SQLite local",
        store_kind="embedded_sql",
        engine="sqlite",
        required_env_vars=("APIKEYS_SQLITE_PATH",),
        notes="Local file-backed SQLite path for lightweight testing.",
    ),
    DataStoreConnectionProfile(
        profile_id="mongodb_default",
        label="MongoDB default",
        store_kind="document_nosql",
        engine="mongodb",
        required_env_vars=("APIKEYS_MONGODB_URI",),
        notes="Reserved for document database datasets and imported JSON collections.",
    ),
    DataStoreConnectionProfile(
        profile_id="s3_compatible_default",
        label="S3-compatible object store",
        store_kind="object_storage",
        engine="s3_compatible",
        required_env_vars=("APIKEYS_S3_ENDPOINT", "APIKEYS_S3_BUCKET", "APIKEYS_S3_ACCESS_KEY", "APIKEYS_S3_SECRET_KEY"),
        optional_env_vars=("APIKEYS_S3_REGION",),
        notes="Reserved for object storage, data lakes, and large raw/curated asset buckets.",
    ),
    DataStoreConnectionProfile(
        profile_id="vector_db_default",
        label="Vector DB default",
        store_kind="vector_database",
        engine="generic_vector_db",
        required_env_vars=("APIKEYS_VECTOR_DB_ENDPOINT", "APIKEYS_VECTOR_DB_API_KEY"),
        notes="Reserved for embeddings, semantic dataset search, and future local LLM workflows.",
    ),
)


def data_store_profile_from_mapping(item: Mapping[str, object]) -> DataStoreConnectionProfile:
    required = item.get("required_env_vars") or ()
    optional = item.get("optional_env_vars") or ()
    return DataStoreConnectionProfile(
        profile_id=str(item.get("profile_id") or item.get("id") or "").strip(),
        label=str(item.get("label") or "").strip(),
        store_kind=str(item.get("store_kind") or "").strip(),
        engine=str(item.get("engine") or "").strip().lower(),
        required_env_vars=tuple(str(value).strip() for value in required if str(value).strip()),
        optional_env_vars=tuple(str(value).strip() for value in optional if str(value).strip()),
        status=str(item.get("status") or "configured").strip(),
        notes=str(item.get("notes") or "").strip(),
    )


def data_store_profiles_from_config(config: Mapping[str, object]) -> tuple[DataStoreConnectionProfile, ...]:
    items = config.get("data_store_connection_profiles") or ()
    profiles = tuple(
        profile
        for item in items
        if isinstance(item, Mapping)
        if (profile := data_store_profile_from_mapping(item)).profile_id
    )
    return profiles or DEFAULT_DATA_STORE_PROFILES


def data_store_profile(profile_id: str) -> DataStoreConnectionProfile | None:
    wanted = profile_id.strip().lower()
    return next((profile for profile in DEFAULT_DATA_STORE_PROFILES if profile.profile_id == wanted), None)


def data_store_profiles_by_kind(kind: str) -> tuple[DataStoreConnectionProfile, ...]:
    wanted = kind.strip().lower()
    return tuple(profile for profile in DEFAULT_DATA_STORE_PROFILES if profile.store_kind == wanted)


def test_data_store_connection(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str] | None = None,
) -> DataStoreConnectionTestResult:
    values = env if env is not None else os.environ
    missing = tuple(name for name in profile.required_env_vars if not str(values.get(name) or "").strip())
    if missing:
        return DataStoreConnectionTestResult(
            profile_id=profile.profile_id,
            engine=profile.engine,
            status="missing_env",
            message=f"Missing required environment variables: {', '.join(missing)}",
            details={"missing_env_vars": missing},
        )

    if profile.engine == "sqlite":
        return _test_sqlite_connection(profile, values)
    if profile.engine == "mysql":
        return _test_mysql_connection(profile, values)
    if profile.engine == "postgresql":
        return _test_postgresql_connection(profile, values)
    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="unsupported",
        message=f"No connection tester is implemented for engine: {profile.engine}",
        details={"store_kind": profile.store_kind},
    )


def _test_sqlite_connection(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
) -> DataStoreConnectionTestResult:
    path_value = str(env.get("APIKEYS_SQLITE_PATH") or "").strip()
    if path_value != ":memory:":
        db_path = Path(path_value).expanduser()
        if not db_path.exists():
            return DataStoreConnectionTestResult(
                profile_id=profile.profile_id,
                engine=profile.engine,
                status="missing_target",
                message=f"SQLite database file does not exist: {db_path}",
                details={"path": str(db_path)},
            )
        uri = f"file:{urllib.parse.quote(str(db_path.resolve()))}?mode=ro"
        connect_kwargs = {"uri": True}
        connect_target = uri
    else:
        connect_kwargs = {}
        connect_target = ":memory:"

    try:
        with sqlite3.connect(connect_target, **connect_kwargs) as conn:
            table_count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
            user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.Error as exc:
        return DataStoreConnectionTestResult(
            profile_id=profile.profile_id,
            engine=profile.engine,
            status="error",
            message=f"SQLite connection failed: {exc}",
            details={"path": path_value},
        )

    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="ok",
        message="SQLite connection opened read-only and introspection query succeeded.",
        details={"path": path_value, "table_count": table_count, "user_version": user_version},
    )


def _test_mysql_connection(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
) -> DataStoreConnectionTestResult:
    if not _module_available("mysql.connector"):
        return DataStoreConnectionTestResult(
            profile_id=profile.profile_id,
            engine=profile.engine,
            status="dependency_missing",
            message="Optional Python driver mysql-connector-python is not installed.",
            details={"driver": "mysql.connector"},
        )
    import mysql.connector  # type: ignore[import-not-found]

    try:
        conn = mysql.connector.connect(
            host=env["APIKEYS_MYSQL_HOST"],
            port=int(env.get("APIKEYS_MYSQL_PORT") or 3306),
            database=env["APIKEYS_MYSQL_DATABASE"],
            user=env["APIKEYS_MYSQL_USER"],
            password=env["APIKEYS_MYSQL_PASSWORD"],
            connection_timeout=5,
        )
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DATABASE()")
            database = cursor.fetchone()[0]
        finally:
            conn.close()
    except Exception as exc:
        return DataStoreConnectionTestResult(
            profile_id=profile.profile_id,
            engine=profile.engine,
            status="error",
            message=f"MySQL connection failed: {type(exc).__name__}: {exc}",
            details={"host": env.get("APIKEYS_MYSQL_HOST"), "database": env.get("APIKEYS_MYSQL_DATABASE")},
        )

    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="ok",
        message="MySQL connection and SELECT DATABASE() succeeded.",
        details={"host": env.get("APIKEYS_MYSQL_HOST"), "database": database},
    )


def _test_postgresql_connection(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
) -> DataStoreConnectionTestResult:
    if _module_available("psycopg"):
        return _test_postgresql_psycopg3(profile, env)
    if _module_available("psycopg2"):
        return _test_postgresql_psycopg2(profile, env)
    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="dependency_missing",
        message="Optional Python driver psycopg or psycopg2 is not installed.",
        details={"driver_options": ("psycopg", "psycopg2")},
    )


def _postgresql_kwargs(env: Mapping[str, str]) -> dict[str, object]:
    return {
        "host": env["APIKEYS_POSTGRES_HOST"],
        "port": int(env.get("APIKEYS_POSTGRES_PORT") or 5432),
        "dbname": env["APIKEYS_POSTGRES_DATABASE"],
        "user": env["APIKEYS_POSTGRES_USER"],
        "password": env["APIKEYS_POSTGRES_PASSWORD"],
        "connect_timeout": 5,
    }


def _test_postgresql_psycopg3(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
) -> DataStoreConnectionTestResult:
    import psycopg  # type: ignore[import-not-found]

    try:
        with psycopg.connect(**_postgresql_kwargs(env)) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                database = cursor.fetchone()[0]
    except Exception as exc:
        return _postgresql_error(profile, env, exc)
    return _postgresql_ok(profile, env, database)


def _test_postgresql_psycopg2(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
) -> DataStoreConnectionTestResult:
    import psycopg2  # type: ignore[import-not-found]

    try:
        conn = psycopg2.connect(**_postgresql_kwargs(env))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT current_database()")
            database = cursor.fetchone()[0]
        finally:
            conn.close()
    except Exception as exc:
        return _postgresql_error(profile, env, exc)
    return _postgresql_ok(profile, env, database)


def _postgresql_error(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
    exc: Exception,
) -> DataStoreConnectionTestResult:
    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="error",
        message=f"PostgreSQL connection failed: {type(exc).__name__}: {exc}",
        details={"host": env.get("APIKEYS_POSTGRES_HOST"), "database": env.get("APIKEYS_POSTGRES_DATABASE")},
    )


def _postgresql_ok(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
    database: object,
) -> DataStoreConnectionTestResult:
    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="ok",
        message="PostgreSQL connection and SELECT current_database() succeeded.",
        details={"host": env.get("APIKEYS_POSTGRES_HOST"), "database": database},
    )


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False
