from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.parse
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from api_launcher.asset_verifier import AssetRecord, AssetVerificationResult
from api_launcher.data_store_connections import DataStoreConnectionProfile, test_data_store_connection


@dataclass(frozen=True)
class DatabaseSelfCheckTarget:
    engine: str
    asset_name: str
    path: str = ""
    table_name: str = ""
    database_name: str = ""
    schema_name: str = ""


@dataclass(frozen=True)
class DatabaseSchemaSummary:
    engine: str
    table_count: int
    tables: tuple[str, ...]
    column_signatures: tuple[str, ...]
    schema_fingerprint: str


def database_self_check_target(asset: AssetRecord) -> DatabaseSelfCheckTarget:
    engine = asset.engine.strip().lower()
    if engine == "sqlite":
        return DatabaseSelfCheckTarget(
            engine=engine,
            asset_name=asset.asset_name,
            path=asset.source_uri or asset.asset_name,
            table_name=asset.asset_name if asset.asset_kind == "table" else "",
        )
    if asset.asset_kind == "table":
        schema_name, table_name = split_schema_table_name(asset.asset_name)
        database_name = sql_database_name_for_asset(asset)
        if engine in {"mysql", "mariadb"} and not database_name:
            database_name = schema_name
        return DatabaseSelfCheckTarget(
            engine=engine,
            asset_name=asset.asset_name,
            table_name=table_name,
            database_name=database_name,
            schema_name=schema_name,
        )
    return DatabaseSelfCheckTarget(engine=engine, asset_name=asset.asset_name, database_name=asset.asset_name)


class DatabaseAssetVerifier:
    def verify(self, asset: AssetRecord) -> AssetVerificationResult:
        if asset.asset_kind not in {"database", "table"}:
            return AssetVerificationResult(asset.asset_id, "error", f"Unsupported asset kind: {asset.asset_kind}")
        target = database_self_check_target(asset)
        if target.engine == "sqlite":
            return self._verify_sqlite(asset, target)
        if target.engine in {"mysql", "mariadb"}:
            return self._verify_mysql(asset, target)
        if target.engine in {"postgres", "postgresql"}:
            return self._verify_postgresql(asset, target)
        return AssetVerificationResult(asset.asset_id, "error", f"No database self-check adapter for engine: {target.engine or 'unknown'}")

    def _verify_sqlite(self, asset: AssetRecord, target: DatabaseSelfCheckTarget) -> AssetVerificationResult:
        if not target.path:
            return AssetVerificationResult(asset.asset_id, "error", "SQLite asset has no source_uri or path-like asset_name.")
        result = test_data_store_connection(
            DataStoreConnectionProfile(
                profile_id=f"asset_{asset.asset_id}",
                label=f"SQLite asset {asset.asset_name}",
                store_kind="embedded_sql",
                engine="sqlite",
                required_env_vars=("APIKEYS_SQLITE_PATH",),
            ),
            {"APIKEYS_SQLITE_PATH": str(Path(target.path))},
        )
        if result.status == "ok":
            if asset.asset_kind == "table":
                if not sqlite_table_exists(target.path, target.table_name):
                    return AssetVerificationResult(asset.asset_id, "missing", f"SQLite table is missing: {target.table_name}")
                if asset.schema_fingerprint:
                    summary = sqlite_table_schema_summary(target.path, target.table_name)
                    if summary.schema_fingerprint != asset.schema_fingerprint:
                        return AssetVerificationResult(
                            asset.asset_id,
                            "error",
                            "SQLite table schema fingerprint drift: "
                            f"expected {asset.schema_fingerprint}, got {summary.schema_fingerprint}; "
                            f"table={target.table_name}",
                        )
                return AssetVerificationResult(asset.asset_id, "present")
            if asset.schema_fingerprint:
                summary = sqlite_schema_summary(target.path)
                if summary.schema_fingerprint != asset.schema_fingerprint:
                    return AssetVerificationResult(
                        asset.asset_id,
                        "error",
                        "SQLite schema fingerprint drift: "
                        f"expected {asset.schema_fingerprint}, got {summary.schema_fingerprint}; "
                        f"tables={summary.table_count}",
                    )
            return AssetVerificationResult(asset.asset_id, "present")
        if result.status == "missing_target":
            return AssetVerificationResult(asset.asset_id, "missing", result.message)
        return AssetVerificationResult(asset.asset_id, "error", result.message)

    def _verify_mysql(self, asset: AssetRecord, target: DatabaseSelfCheckTarget) -> AssetVerificationResult:
        result = test_data_store_connection(
            DataStoreConnectionProfile(
                profile_id="mysql_default",
                label="MySQL default",
                store_kind="relational_sql",
                engine="mysql",
                required_env_vars=("APIKEYS_MYSQL_HOST", "APIKEYS_MYSQL_DATABASE", "APIKEYS_MYSQL_USER", "APIKEYS_MYSQL_PASSWORD"),
                optional_env_vars=("APIKEYS_MYSQL_PORT",),
            ),
            include_schema_summary=bool(asset.schema_fingerprint or asset.asset_kind == "table"),
            schema_summary_table=target.table_name if asset.asset_kind == "table" else "",
        )
        if result.status == "ok":
            connected_database = str(result.details.get("database") or "")
            expected_database = target.database_name if asset.asset_kind == "table" else target.asset_name
            if connected_database and expected_database and connected_database != expected_database:
                return AssetVerificationResult(
                    asset.asset_id,
                    "error",
                    f"MySQL profile connected to {connected_database}, but registry asset expects {expected_database}.",
                )
            if asset.asset_kind == "table":
                if result.details.get("table_exists") is False:
                    return AssetVerificationResult(asset.asset_id, "missing", f"MySQL table is missing: {target.table_name}")
            if asset.schema_fingerprint:
                actual = str(result.details.get("schema_fingerprint") or "")
                if not actual:
                    return AssetVerificationResult(
                        asset.asset_id,
                        "error",
                        "MySQL schema fingerprint was requested but no schema summary was returned.",
                    )
                if actual != asset.schema_fingerprint:
                    return AssetVerificationResult(
                        asset.asset_id,
                        "error",
                        "MySQL schema fingerprint drift: "
                        f"expected {asset.schema_fingerprint}, got {actual}; "
                        f"tables={result.details.get('table_count', '-')}",
                    )
            return AssetVerificationResult(asset.asset_id, "present")
        return AssetVerificationResult(asset.asset_id, "error", result.message)

    def _verify_postgresql(self, asset: AssetRecord, target: DatabaseSelfCheckTarget) -> AssetVerificationResult:
        result = test_data_store_connection(
            DataStoreConnectionProfile(
                profile_id="postgres_default",
                label="PostgreSQL default",
                store_kind="relational_sql",
                engine="postgresql",
                required_env_vars=("APIKEYS_POSTGRES_HOST", "APIKEYS_POSTGRES_DATABASE", "APIKEYS_POSTGRES_USER", "APIKEYS_POSTGRES_PASSWORD"),
                optional_env_vars=("APIKEYS_POSTGRES_PORT",),
            ),
            include_schema_summary=bool(asset.schema_fingerprint or asset.asset_kind == "table"),
            schema_summary_table=target.table_name if asset.asset_kind == "table" else "",
            schema_name=target.schema_name or "public",
        )
        if result.status == "ok":
            connected_database = str(result.details.get("database") or "")
            expected_database = target.database_name if asset.asset_kind == "table" else target.asset_name
            if connected_database and expected_database and connected_database != expected_database:
                return AssetVerificationResult(
                    asset.asset_id,
                    "error",
                    f"PostgreSQL profile connected to {connected_database}, but registry asset expects {expected_database}.",
                )
            if asset.asset_kind == "table":
                if result.details.get("table_exists") is False:
                    table_label = f"{target.schema_name}.{target.table_name}" if target.schema_name else target.table_name
                    return AssetVerificationResult(asset.asset_id, "missing", f"PostgreSQL table is missing: {table_label}")
            if asset.schema_fingerprint:
                actual = str(result.details.get("schema_fingerprint") or "")
                if not actual:
                    return AssetVerificationResult(
                        asset.asset_id,
                        "error",
                        "PostgreSQL schema fingerprint was requested but no schema summary was returned.",
                    )
                if actual != asset.schema_fingerprint:
                    return AssetVerificationResult(
                        asset.asset_id,
                        "error",
                        "PostgreSQL schema fingerprint drift: "
                        f"expected {asset.schema_fingerprint}, got {actual}; "
                        f"tables={result.details.get('table_count', '-')}",
                    )
            return AssetVerificationResult(asset.asset_id, "present")
        return AssetVerificationResult(asset.asset_id, "error", result.message)


def split_schema_table_name(value: str) -> tuple[str, str]:
    raw = value.strip()
    if "." not in raw:
        return "", raw
    schema_name, table_name = raw.split(".", 1)
    if not schema_name.strip() or not table_name.strip():
        return "", raw
    return schema_name.strip(), table_name.strip()


def sql_database_name_for_asset(asset: AssetRecord) -> str:
    for raw in (asset.install_location, asset.source_uri):
        value = raw.strip()
        if not value:
            continue
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme:
            path = parsed.path.strip("/")
            if path:
                return urllib.parse.unquote(path.rsplit("/", 1)[-1])
            if parsed.netloc and "@" not in parsed.netloc and ":" not in parsed.netloc:
                return urllib.parse.unquote(parsed.netloc)
            continue
        return value
    return ""


def sqlite_schema_summary(path: str | Path) -> DatabaseSchemaSummary:
    db_path = Path(path).expanduser()
    uri = f"file:{urllib.parse.quote(str(db_path.resolve()))}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        tables = tuple(str(row[0]) for row in rows)
        column_signatures: list[str] = []
        for table in tables:
            column_signatures.extend(_sqlite_column_signatures(conn, table))
    payload = json.dumps(column_signatures, ensure_ascii=True, separators=(",", ":"))
    return DatabaseSchemaSummary(
        engine="sqlite",
        table_count=len(tables),
        tables=tables,
        column_signatures=tuple(column_signatures),
        schema_fingerprint=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )


def sqlite_table_schema_summary(path: str | Path, table: str) -> DatabaseSchemaSummary:
    db_path = Path(path).expanduser()
    uri = f"file:{urllib.parse.quote(str(db_path.resolve()))}?mode=ro"
    table_name = table.strip()
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        if not _sqlite_table_exists(conn, table_name):
            raise ValueError(f"SQLite table is missing: {table_name}")
        column_signatures = _sqlite_column_signatures(conn, table_name)
    payload = json.dumps(column_signatures, ensure_ascii=True, separators=(",", ":"))
    return DatabaseSchemaSummary(
        engine="sqlite",
        table_count=1,
        tables=(table_name,),
        column_signatures=tuple(column_signatures),
        schema_fingerprint=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )


def sqlite_table_exists(path: str | Path, table: str) -> bool:
    db_path = Path(path).expanduser()
    uri = f"file:{urllib.parse.quote(str(db_path.resolve()))}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        return _sqlite_table_exists(conn, table.strip())


def quote_sqlite_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sqlite_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table,),
    ).fetchone()
    return row is not None


def _sqlite_column_signatures(conn: sqlite3.Connection, table: str) -> list[str]:
    columns = conn.execute(f"PRAGMA table_info({quote_sqlite_identifier(table)})").fetchall()
    return [
        "|".join(
            [
                table,
                str(cid),
                str(name).strip().lower(),
                str(column_type or "").strip().upper(),
                str(int(bool(notnull))),
                str(int(pk or 0)),
                "default" if default_value is not None else "",
            ]
        )
        for cid, name, column_type, notnull, default_value, pk in columns
    ]
