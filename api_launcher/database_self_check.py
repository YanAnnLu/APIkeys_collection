from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from api_launcher.asset_verifier import AssetRecord, AssetVerificationResult
from api_launcher.data_store_connections import DataStoreConnectionProfile, test_data_store_connection


@dataclass(frozen=True)
class DatabaseSelfCheckTarget:
    engine: str
    asset_name: str
    path: str = ""


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
        return DatabaseSelfCheckTarget(engine=engine, asset_name=asset.asset_name, path=asset.source_uri or asset.asset_name)
    return DatabaseSelfCheckTarget(engine=engine, asset_name=asset.asset_name)


class DatabaseAssetVerifier:
    def verify(self, asset: AssetRecord) -> AssetVerificationResult:
        if asset.asset_kind != "database":
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
            )
        )
        if result.status == "ok":
            connected_database = str(result.details.get("database") or "")
            if connected_database and connected_database != target.asset_name:
                return AssetVerificationResult(
                    asset.asset_id,
                    "error",
                    f"MySQL profile connected to {connected_database}, but registry asset expects {target.asset_name}.",
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
            )
        )
        if result.status == "ok":
            connected_database = str(result.details.get("database") or "")
            if connected_database and connected_database != target.asset_name:
                return AssetVerificationResult(
                    asset.asset_id,
                    "error",
                    f"PostgreSQL profile connected to {connected_database}, but registry asset expects {target.asset_name}.",
                )
            return AssetVerificationResult(asset.asset_id, "present")
        return AssetVerificationResult(asset.asset_id, "error", result.message)


def sqlite_schema_summary(path: str | Path) -> DatabaseSchemaSummary:
    db_path = Path(path).expanduser()
    uri = f"file:{urllib.parse.quote(str(db_path.resolve()))}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
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
            columns = conn.execute(f"PRAGMA table_info({quote_sqlite_identifier(table)})").fetchall()
            for cid, name, column_type, notnull, default_value, pk in columns:
                column_signatures.append(
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
                )
    payload = json.dumps(column_signatures, ensure_ascii=True, separators=(",", ":"))
    return DatabaseSchemaSummary(
        engine="sqlite",
        table_count=len(tables),
        tables=tables,
        column_signatures=tuple(column_signatures),
        schema_fingerprint=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )


def quote_sqlite_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
