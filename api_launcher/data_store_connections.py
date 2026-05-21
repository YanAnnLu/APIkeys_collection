from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import urllib.parse
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DataStoreConnectionProfile:
    # profile 只描述連線需求與 env 邊界，不保存密碼或連線秘密本身。
    profile_id: str
    label: str
    store_kind: str
    engine: str
    required_env_vars: tuple[str, ...]
    optional_env_vars: tuple[str, ...] = ()
    status: str = "skeleton"
    notes: str = ""
    env_var_map: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DataStoreConnectionTestResult:
    # 測試結果要可被 CLI、Tk 與 agent 共用，所以 details 放結構化診斷資料。
    profile_id: str
    engine: str
    status: str
    message: str
    details: dict[str, object]

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass(frozen=True)
class RelationalSchemaSummary:
    # schema summary 是 registry schema_fingerprint 的來源，欄位順序必須穩定。
    engine: str
    database: str
    schema: str
    table_count: int
    tables: tuple[str, ...]
    column_signatures: tuple[str, ...]
    schema_fingerprint: str


DEFAULT_DATA_STORE_PROFILES = (
    # 內建 profile 只定義常見環境變數名稱；真實值永遠由 os.environ 或本機 config 提供。
    DataStoreConnectionProfile(
        profile_id="mysql_default",
        label="MySQL default",
        store_kind="relational_sql",
        engine="mysql",
        required_env_vars=("APIKEYS_MYSQL_HOST", "APIKEYS_MYSQL_DATABASE", "APIKEYS_MYSQL_USER", "APIKEYS_MYSQL_PASSWORD"),
        optional_env_vars=("APIKEYS_MYSQL_PORT",),
        notes="Relational SQL profile for MySQL self-check and future install/uninstall adapters.",
        env_var_map={
            "host": "APIKEYS_MYSQL_HOST",
            "database": "APIKEYS_MYSQL_DATABASE",
            "user": "APIKEYS_MYSQL_USER",
            "password": "APIKEYS_MYSQL_PASSWORD",
            "port": "APIKEYS_MYSQL_PORT",
        },
    ),
    DataStoreConnectionProfile(
        profile_id="postgres_default",
        label="PostgreSQL default",
        store_kind="relational_sql",
        engine="postgresql",
        required_env_vars=("APIKEYS_POSTGRES_HOST", "APIKEYS_POSTGRES_DATABASE", "APIKEYS_POSTGRES_USER", "APIKEYS_POSTGRES_PASSWORD"),
        optional_env_vars=("APIKEYS_POSTGRES_PORT",),
        notes="Reserved for PostgreSQL introspection.",
        env_var_map={
            "host": "APIKEYS_POSTGRES_HOST",
            "database": "APIKEYS_POSTGRES_DATABASE",
            "user": "APIKEYS_POSTGRES_USER",
            "password": "APIKEYS_POSTGRES_PASSWORD",
            "port": "APIKEYS_POSTGRES_PORT",
        },
    ),
    DataStoreConnectionProfile(
        profile_id="sqlite_local",
        label="SQLite local",
        store_kind="embedded_sql",
        engine="sqlite",
        required_env_vars=("APIKEYS_SQLITE_PATH",),
        notes="Local file-backed SQLite path for lightweight testing.",
        env_var_map={"path": "APIKEYS_SQLITE_PATH"},
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
        profile_id="hadoop_default",
        label="Hadoop / HDFS data lake",
        store_kind="distributed_data_lake",
        engine="hadoop",
        required_env_vars=("APIKEYS_HADOOP_NAMENODE_URI",),
        optional_env_vars=(
            "HADOOP_CONF_DIR",
            "APIKEYS_HDFS_USER",
            "APIKEYS_HIVE_METASTORE_URI",
            "APIKEYS_SPARK_MASTER",
        ),
        notes=(
            "Reserved for the Hadoop team's distributed storage/compute layer. "
            "Use manifests and dataset IDs as the handoff contract before any HDFS/Hive/Spark adapter is implemented."
        ),
        env_var_map={
            "namenode_uri": "APIKEYS_HADOOP_NAMENODE_URI",
            "hadoop_conf_dir": "HADOOP_CONF_DIR",
            "hdfs_user": "APIKEYS_HDFS_USER",
            "hive_metastore_uri": "APIKEYS_HIVE_METASTORE_URI",
            "spark_master": "APIKEYS_SPARK_MASTER",
        },
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
    # 本機設定可能來自手寫 JSON；這裡集中正規化欄位與 env_var_map。
    required = item.get("required_env_vars") or ()
    optional = item.get("optional_env_vars") or ()
    raw_env_var_map = item.get("env_var_map") or item.get("connection_env_vars") or {}
    env_var_map = (
        {
            str(key).strip(): str(value).strip()
            for key, value in raw_env_var_map.items()
            if str(key).strip() and str(value).strip()
        }
        if isinstance(raw_env_var_map, Mapping)
        else {}
    )
    return DataStoreConnectionProfile(
        profile_id=str(item.get("profile_id") or item.get("id") or "").strip(),
        label=str(item.get("label") or "").strip(),
        store_kind=str(item.get("store_kind") or "").strip(),
        engine=str(item.get("engine") or "").strip().lower(),
        required_env_vars=tuple(str(value).strip() for value in required if str(value).strip()),
        optional_env_vars=tuple(str(value).strip() for value in optional if str(value).strip()),
        status=str(item.get("status") or "configured").strip(),
        notes=str(item.get("notes") or "").strip(),
        env_var_map=env_var_map,
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
    include_schema_summary: bool = False,
    schema_summary_table: str = "",
    schema_name: str = "public",
) -> DataStoreConnectionTestResult:
    # 所有連線測試先檢查 env，避免在缺 credential 時載入 driver 或打開網路連線。
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
        return _test_mysql_connection(profile, values, include_schema_summary, schema_summary_table)
    if profile.engine == "postgresql":
        return _test_postgresql_connection(profile, values, include_schema_summary, schema_summary_table, schema_name)
    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="unsupported",
        message=f"No connection tester is implemented for engine: {profile.engine}",
        details={"store_kind": profile.store_kind},
    )


def _connection_env_var(profile: DataStoreConnectionProfile, role: str, fallback: str) -> str:
    return str(profile.env_var_map.get(role) or fallback).strip()


def _test_sqlite_connection(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
) -> DataStoreConnectionTestResult:
    # SQLite 探測只做唯讀/輕量查詢；不要因 self-check 建立新的空資料庫。
    path_var = _connection_env_var(profile, "path", "APIKEYS_SQLITE_PATH")
    path_value = str(env.get(path_var) or "").strip()
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
        with closing(sqlite3.connect(connect_target, **connect_kwargs)) as conn:
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
    include_schema_summary: bool,
    schema_summary_table: str,
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

    host_var = _connection_env_var(profile, "host", "APIKEYS_MYSQL_HOST")
    port_var = _connection_env_var(profile, "port", "APIKEYS_MYSQL_PORT")
    database_var = _connection_env_var(profile, "database", "APIKEYS_MYSQL_DATABASE")
    user_var = _connection_env_var(profile, "user", "APIKEYS_MYSQL_USER")
    password_var = _connection_env_var(profile, "password", "APIKEYS_MYSQL_PASSWORD")
    try:
        conn = mysql.connector.connect(
            host=env[host_var],
            port=int(env.get(port_var) or 3306),
            database=env[database_var],
            user=env[user_var],
            password=env[password_var],
            connection_timeout=5,
        )
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DATABASE()")
            database = cursor.fetchone()[0]
            if include_schema_summary:
                if schema_summary_table:
                    schema_summary = mysql_table_schema_summary_from_cursor(cursor, str(database), schema_summary_table)
                else:
                    schema_summary = mysql_schema_summary_from_cursor(cursor, str(database))
                table_count = schema_summary.table_count
            else:
                schema_summary = None
                table_count = mysql_table_count(cursor, str(database))
        finally:
            conn.close()
    except Exception as exc:
        return DataStoreConnectionTestResult(
            profile_id=profile.profile_id,
            engine=profile.engine,
            status="error",
            message=f"MySQL connection failed: {type(exc).__name__}: {exc}",
            details={"host": env.get(host_var), "database": env.get(database_var)},
        )

    details: dict[str, object] = {
        "host": env.get(host_var),
        "database": database,
        "table_count": table_count,
    }
    if schema_summary is not None:
        details.update(
            {
                "schema_fingerprint": schema_summary.schema_fingerprint,
                "tables": schema_summary.tables,
                "column_count": len(schema_summary.column_signatures),
            }
        )
        if schema_summary_table:
            details["table"] = schema_summary_table
            details["table_exists"] = schema_summary.table_count == 1
    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="ok",
        message="MySQL connection and SELECT DATABASE() succeeded.",
        details=details,
    )


def _test_postgresql_connection(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
    include_schema_summary: bool,
    schema_summary_table: str,
    schema_name: str,
) -> DataStoreConnectionTestResult:
    if _module_available("psycopg"):
        return _test_postgresql_psycopg3(profile, env, include_schema_summary, schema_summary_table, schema_name)
    if _module_available("psycopg2"):
        return _test_postgresql_psycopg2(profile, env, include_schema_summary, schema_summary_table, schema_name)
    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="dependency_missing",
        message="Optional Python driver psycopg or psycopg2 is not installed.",
        details={"driver_options": ("psycopg", "psycopg2")},
    )


def _postgresql_kwargs(profile: DataStoreConnectionProfile, env: Mapping[str, str]) -> dict[str, object]:
    host_var = _connection_env_var(profile, "host", "APIKEYS_POSTGRES_HOST")
    port_var = _connection_env_var(profile, "port", "APIKEYS_POSTGRES_PORT")
    database_var = _connection_env_var(profile, "database", "APIKEYS_POSTGRES_DATABASE")
    user_var = _connection_env_var(profile, "user", "APIKEYS_POSTGRES_USER")
    password_var = _connection_env_var(profile, "password", "APIKEYS_POSTGRES_PASSWORD")
    return {
        "host": env[host_var],
        "port": int(env.get(port_var) or 5432),
        "dbname": env[database_var],
        "user": env[user_var],
        "password": env[password_var],
        "connect_timeout": 5,
    }


def _test_postgresql_psycopg3(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
    include_schema_summary: bool,
    schema_summary_table: str,
    schema_name: str,
) -> DataStoreConnectionTestResult:
    import psycopg  # type: ignore[import-not-found]

    try:
        with psycopg.connect(**_postgresql_kwargs(profile, env)) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                database = cursor.fetchone()[0]
                if include_schema_summary:
                    if schema_summary_table:
                        schema_summary = postgresql_table_schema_summary_from_cursor(
                            cursor,
                            str(database),
                            schema_summary_table,
                            schema=schema_name,
                        )
                    else:
                        schema_summary = postgresql_schema_summary_from_cursor(cursor, str(database), schema=schema_name)
                    table_count = schema_summary.table_count
                else:
                    schema_summary = None
                    table_count = postgresql_table_count(cursor, schema=schema_name)
    except Exception as exc:
        return _postgresql_error(profile, env, exc)
    return _postgresql_ok(profile, env, database, table_count, schema_summary, schema_name, schema_summary_table)


def _test_postgresql_psycopg2(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
    include_schema_summary: bool,
    schema_summary_table: str,
    schema_name: str,
) -> DataStoreConnectionTestResult:
    import psycopg2  # type: ignore[import-not-found]

    try:
        conn = psycopg2.connect(**_postgresql_kwargs(profile, env))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT current_database()")
            database = cursor.fetchone()[0]
            if include_schema_summary:
                if schema_summary_table:
                    schema_summary = postgresql_table_schema_summary_from_cursor(
                        cursor,
                        str(database),
                        schema_summary_table,
                        schema=schema_name,
                    )
                else:
                    schema_summary = postgresql_schema_summary_from_cursor(cursor, str(database), schema=schema_name)
                table_count = schema_summary.table_count
            else:
                schema_summary = None
                table_count = postgresql_table_count(cursor, schema=schema_name)
        finally:
            conn.close()
    except Exception as exc:
        return _postgresql_error(profile, env, exc)
    return _postgresql_ok(profile, env, database, table_count, schema_summary, schema_name, schema_summary_table)


def _postgresql_error(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
    exc: Exception,
) -> DataStoreConnectionTestResult:
    host_var = _connection_env_var(profile, "host", "APIKEYS_POSTGRES_HOST")
    database_var = _connection_env_var(profile, "database", "APIKEYS_POSTGRES_DATABASE")
    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="error",
        message=f"PostgreSQL connection failed: {type(exc).__name__}: {exc}",
        details={"host": env.get(host_var), "database": env.get(database_var)},
    )


def _postgresql_ok(
    profile: DataStoreConnectionProfile,
    env: Mapping[str, str],
    database: object,
    table_count: int,
    schema_summary: RelationalSchemaSummary | None,
    schema_name: str,
    schema_summary_table: str,
) -> DataStoreConnectionTestResult:
    host_var = _connection_env_var(profile, "host", "APIKEYS_POSTGRES_HOST")
    details: dict[str, object] = {
        "host": env.get(host_var),
        "database": database,
        "schema": schema_name,
        "table_count": table_count,
    }
    if schema_summary is not None:
        details.update(
            {
                "schema_fingerprint": schema_summary.schema_fingerprint,
                "tables": schema_summary.tables,
                "column_count": len(schema_summary.column_signatures),
            }
        )
        if schema_summary_table:
            details["table"] = schema_summary_table
            details["table_exists"] = schema_summary.table_count == 1
    return DataStoreConnectionTestResult(
        profile_id=profile.profile_id,
        engine=profile.engine,
        status="ok",
        message="PostgreSQL connection and SELECT current_database() succeeded.",
        details=details,
    )


def mysql_schema_summary_from_cursor(cursor: object, database: str) -> RelationalSchemaSummary:
    database_name = database.strip()
    tables = mysql_table_names(cursor, database_name)
    column_signatures: list[str] = []
    for table in tables:
        column_signatures.extend(mysql_column_signatures(cursor, database_name, table))
    fingerprint = schema_fingerprint_from_signatures(column_signatures)
    return RelationalSchemaSummary(
        engine="mysql",
        database=database_name,
        schema=database_name,
        table_count=len(tables),
        tables=tables,
        column_signatures=tuple(column_signatures),
        schema_fingerprint=fingerprint,
    )


def mysql_table_schema_summary_from_cursor(cursor: object, database: str, table: str) -> RelationalSchemaSummary:
    database_name = database.strip()
    table_name = table.strip()
    if mysql_table_exists(cursor, database_name, table_name):
        tables = (table_name,)
        column_signatures = mysql_column_signatures(cursor, database_name, table_name)
    else:
        tables = ()
        column_signatures = ()
    fingerprint = schema_fingerprint_from_signatures(column_signatures)
    return RelationalSchemaSummary(
        engine="mysql",
        database=database_name,
        schema=database_name,
        table_count=len(tables),
        tables=tables,
        column_signatures=tuple(column_signatures),
        schema_fingerprint=fingerprint,
    )


def mysql_table_count(cursor: object, database: str) -> int:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
        """,
        (database,),
    )
    return int(cursor.fetchone()[0])


def mysql_table_names(cursor: object, database: str) -> tuple[str, ...]:
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        (database,),
    )
    return tuple(str(row[0]) for row in cursor.fetchall())


def mysql_table_exists(cursor: object, database: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_name = %s
          AND table_type = 'BASE TABLE'
        LIMIT 1
        """,
        (database, table),
    )
    return cursor.fetchone() is not None


def mysql_column_signatures(cursor: object, database: str, table: str) -> tuple[str, ...]:
    cursor.execute(
        """
        SELECT ordinal_position, column_name, data_type, is_nullable, column_default, column_key
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (database, table),
    )
    return tuple(_column_signature(table, row) for row in cursor.fetchall())


def postgresql_schema_summary_from_cursor(
    cursor: object,
    database: str = "",
    schema: str = "public",
) -> RelationalSchemaSummary:
    schema_name = schema.strip() or "public"
    tables = postgresql_table_names(cursor, schema_name)
    column_signatures: list[str] = []
    for table in tables:
        column_signatures.extend(postgresql_column_signatures(cursor, table, schema_name))
    fingerprint = schema_fingerprint_from_signatures(column_signatures)
    return RelationalSchemaSummary(
        engine="postgresql",
        database=database.strip(),
        schema=schema_name,
        table_count=len(tables),
        tables=tables,
        column_signatures=tuple(column_signatures),
        schema_fingerprint=fingerprint,
    )


def postgresql_table_schema_summary_from_cursor(
    cursor: object,
    database: str,
    table: str,
    schema: str = "public",
) -> RelationalSchemaSummary:
    schema_name = schema.strip() or "public"
    table_name = table.strip()
    if postgresql_table_exists(cursor, table_name, schema_name):
        tables = (table_name,)
        column_signatures = postgresql_column_signatures(cursor, table_name, schema_name)
    else:
        tables = ()
        column_signatures = ()
    fingerprint = schema_fingerprint_from_signatures(column_signatures)
    return RelationalSchemaSummary(
        engine="postgresql",
        database=database.strip(),
        schema=schema_name,
        table_count=len(tables),
        tables=tables,
        column_signatures=tuple(column_signatures),
        schema_fingerprint=fingerprint,
    )


def postgresql_table_count(cursor: object, schema: str = "public") -> int:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
        """,
        (schema,),
    )
    return int(cursor.fetchone()[0])


def postgresql_table_names(cursor: object, schema: str = "public") -> tuple[str, ...]:
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        (schema,),
    )
    return tuple(str(row[0]) for row in cursor.fetchall())


def postgresql_table_exists(cursor: object, table: str, schema: str = "public") -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_name = %s
          AND table_type = 'BASE TABLE'
        LIMIT 1
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


def postgresql_column_signatures(cursor: object, table: str, schema: str = "public") -> tuple[str, ...]:
    cursor.execute(
        """
        SELECT
            c.ordinal_position,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            CASE WHEN EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_schema = tc.constraint_schema
                 AND kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                 AND kcu.table_name = tc.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = c.table_schema
                  AND tc.table_name = c.table_name
                  AND kcu.column_name = c.column_name
            ) THEN 1 ELSE 0 END AS is_primary_key
        FROM information_schema.columns c
        WHERE c.table_schema = %s
          AND c.table_name = %s
        ORDER BY c.ordinal_position
        """,
        (schema, table),
    )
    return tuple(_column_signature(table, row) for row in cursor.fetchall())


def schema_fingerprint_from_signatures(column_signatures: tuple[str, ...] | list[str]) -> str:
    payload = json.dumps(tuple(column_signatures), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _column_signature(table: str, row: object) -> str:
    ordinal, name, column_type, nullable, default_value, primary_key = row
    return "|".join(
        [
            table,
            str(ordinal),
            str(name).strip().lower(),
            str(column_type or "").strip().upper(),
            "0" if str(nullable).strip().upper() == "YES" else "1",
            str(int(bool(primary_key == "PRI" or primary_key == 1 or primary_key is True))),
            "default" if default_value is not None else "",
        ]
    )


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False
