from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import urllib.parse
from contextlib import closing
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class DatabaseRepairSuggestion:
    action_id: str
    label: str
    description: str
    severity: str = "warning"
    can_auto_repair: bool = False
    details: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "label": self.label,
            "description": self.description,
            "severity": self.severity,
            "can_auto_repair": self.can_auto_repair,
            "details": self.details,
        }


@dataclass(frozen=True)
class DatabaseSelfCheckIssue:
    provider_id: str
    asset_id: str
    asset_kind: str
    engine: str
    asset_name: str
    status: str
    error: str
    install_id: str = ""
    install_location: str = ""
    source_uri: str = ""
    schema_fingerprint: str = ""

    def repair_suggestion(self) -> DatabaseRepairSuggestion:
        return database_repair_suggestion(
            asset_kind=self.asset_kind,
            engine=self.engine,
            asset_name=self.asset_name,
            status=self.status,
            error=self.error,
            provider_id=self.provider_id,
            asset_id=self.asset_id,
            install_location=self.install_location,
            source_uri=self.source_uri,
            schema_fingerprint=self.schema_fingerprint,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "asset_id": self.asset_id,
            "install_id": self.install_id,
            "asset_kind": self.asset_kind,
            "engine": self.engine,
            "asset_name": self.asset_name,
            "status": self.status,
            "error": self.error,
            "install_location": safe_database_location(self.install_location),
            "source_uri": safe_database_location(self.source_uri),
            "has_schema_fingerprint": bool(self.schema_fingerprint),
            "repair_suggestion": self.repair_suggestion().as_dict(),
        }


def database_self_check_agent_payload(
    summary: dict[str, int],
    issues: list[DatabaseSelfCheckIssue],
) -> dict[str, object]:
    issue_payloads = [issue.as_dict() for issue in issues]
    return {
        "summary": dict(summary),
        "issue_count": len(issue_payloads),
        "issues": issue_payloads,
    }


def database_self_check_issues(
    conn: sqlite3.Connection,
    provider_ids: list[str] | tuple[str, ...] | None = None,
) -> list[DatabaseSelfCheckIssue]:
    requested = tuple(provider_id.strip() for provider_id in (provider_ids or ()) if provider_id.strip())
    provider_filter = ""
    params: tuple[str, ...] = ()
    if requested:
        placeholders = ",".join("?" for _ in requested)
        provider_filter = f"AND pi.provider_id IN ({placeholders})"
        params = requested
    rows = conn.execute(
        f"""
        SELECT
            pi.provider_id,
            pia.asset_id,
            pia.install_id,
            pia.asset_kind,
            pia.engine,
            pia.asset_name,
            pia.status,
            COALESCE(pi.location, '') AS install_location,
            COALESCE(pia.source_uri, '') AS source_uri,
            COALESCE(pia.schema_fingerprint, '') AS schema_fingerprint,
            COALESCE(pia.last_verify_error, '') AS last_verify_error
        FROM provider_installation_assets pia
        JOIN provider_installations pi ON pi.install_id = pia.install_id
        WHERE pia.asset_kind IN ('database', 'table')
          AND pia.status IN ('missing', 'error')
          {provider_filter}
        ORDER BY pi.provider_id, pia.asset_kind, pia.engine, pia.asset_name
        """,
        params,
    ).fetchall()
    return [
        DatabaseSelfCheckIssue(
            provider_id=row["provider_id"],
            asset_id=row["asset_id"],
            install_id=row["install_id"],
            asset_kind=row["asset_kind"],
            engine=row["engine"] or "",
            asset_name=row["asset_name"],
            status=row["status"],
            error=row["last_verify_error"] or "",
            install_location=row["install_location"] or "",
            source_uri=row["source_uri"] or "",
            schema_fingerprint=row["schema_fingerprint"] or "",
        )
        for row in rows
    ]


def database_repair_suggestion(
    asset_kind: str,
    engine: str,
    asset_name: str,
    status: str,
    error: str,
    provider_id: str = "",
    asset_id: str = "",
    install_location: str = "",
    source_uri: str = "",
    schema_fingerprint: str = "",
) -> DatabaseRepairSuggestion:
    normalized_engine = engine.strip().lower()
    normalized_kind = asset_kind.strip().lower()
    normalized_status = status.strip().lower()
    message = error.strip()
    lowered = message.lower()
    details = {
        "provider_id": provider_id,
        "asset_id": asset_id,
        "asset_kind": normalized_kind,
        "engine": normalized_engine,
        "asset_name": asset_name,
        "status": normalized_status,
        "install_location": safe_database_location(install_location),
        "source_uri": safe_database_location(source_uri),
        "has_schema_fingerprint": bool(schema_fingerprint),
    }
    missing_env_vars = _missing_env_vars(message)
    if missing_env_vars:
        return DatabaseRepairSuggestion(
            "configure_data_store_env",
            "Configure data-store environment",
            "Set the required data-store environment variables in the local launcher environment, then rerun the database self-check.",
            severity="error",
            details={**details, "missing_env_vars": missing_env_vars},
        )
    if "optional python driver" in lowered or "dependency_missing" in lowered or _looks_like_missing_driver(lowered):
        return DatabaseRepairSuggestion(
            "install_optional_driver_in_project_env",
            "Install optional SQL driver",
            "Install the optional database driver in the project Python environment, not the base environment, then rerun the database self-check.",
            severity="error",
            details={**details, "install_scope": "project_python_environment"},
        )
    if "profile connected to" in lowered and "registry asset expects" in lowered:
        return DatabaseRepairSuggestion(
            "fix_data_store_profile_mapping",
            "Fix data-store profile mapping",
            "The active SQL profile points at a different database than the registry asset expects; update the profile/env selection or the asset ownership metadata.",
            severity="error",
            details=details,
        )
    if "schema fingerprint drift" in lowered:
        return DatabaseRepairSuggestion(
            "review_schema_drift",
            "Review schema drift",
            "Compare the registered schema fingerprint with the live database schema, then either migrate/reimport the asset or intentionally refresh the registry fingerprint.",
            severity="warning",
            details=details,
        )
    if "table is missing" in lowered or (normalized_kind == "table" and normalized_status == "missing"):
        return DatabaseRepairSuggestion(
            "restore_or_reimport_table",
            "Restore or reimport table",
            "The managed table is missing; restore it from backup or rerun the provider import path that owns this table.",
            severity="error",
            details=details,
        )
    if normalized_status == "missing" and normalized_engine == "sqlite":
        return DatabaseRepairSuggestion(
            "restore_or_reimport_sqlite_database",
            "Restore or reimport SQLite database",
            "The managed SQLite file is missing; restore the file or rerun the provider import that created it.",
            severity="error",
            details=details,
        )
    if "connection failed" in lowered:
        return DatabaseRepairSuggestion(
            "test_data_store_connection",
            "Test data-store connection",
            "Run the configured data-store connection test and inspect host, database, credentials, network access, and driver compatibility.",
            severity="error",
            details=details,
        )
    if "no database self-check adapter" in lowered:
        return DatabaseRepairSuggestion(
            "implement_database_self_check_adapter",
            "Implement self-check adapter",
            "No verifier exists for this engine yet; add an adapter or mark the asset unmanaged until one exists.",
            severity="warning",
            details=details,
        )
    if "unsupported asset kind" in lowered:
        return DatabaseRepairSuggestion(
            "fix_registry_asset_kind",
            "Fix registry asset kind",
            "The registry asset kind is not supported by database self-check; correct the asset metadata before retrying.",
            severity="error",
            details=details,
        )
    return DatabaseRepairSuggestion(
        "inspect_database_asset",
        "Inspect database asset",
        "No specific automated repair rule matched this failure; inspect the asset record, data-store profile, and latest error before changing registry state.",
        severity="warning" if normalized_status != "error" else "error",
        details=details,
    )


def safe_database_location(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    parsed = urllib.parse.urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw
    if "@" not in parsed.netloc:
        return raw
    host = parsed.hostname or ""
    try:
        port_number = parsed.port
    except ValueError:
        port_number = None
    port = f":{port_number}" if port_number else ""
    redacted_netloc = host + port
    return urllib.parse.urlunparse((parsed.scheme, redacted_netloc, parsed.path, "", "", ""))


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


def _missing_env_vars(message: str) -> tuple[str, ...]:
    match = re.search(r"Missing required environment variables:\s*(.+)$", message)
    if not match:
        return ()
    return tuple(value.strip() for value in match.group(1).split(",") if value.strip())


def _looks_like_missing_driver(message: str) -> bool:
    return ("driver" in message or "mysql-connector-python" in message or "psycopg" in message) and "not installed" in message


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
