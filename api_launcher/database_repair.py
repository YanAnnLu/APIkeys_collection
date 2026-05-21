from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from api_launcher.database_repair_contracts import (
    CSV_REIMPORT_FORMATS,
    JSON_REIMPORT_FORMATS,
    manifest_path_from_notes,
    supported_reimport_source_formats_label,
)
from api_launcher.downloads.repair import verify_manifest_file
from api_launcher.importers.csv_importer import (
    import_csv_manifest_to_sqlite,
    normalized_column_names,
    normalized_row_values,
    open_csv_text,
    table_exists,
)
from api_launcher.importers.json_importer import import_json_manifest_to_sqlite, load_json_records, ordered_keys, row_values
from api_launcher.manifests import read_manifest
from api_launcher.repository import ApiCatalogRepository
from api_launcher.sql_assets import validate_sql_identifier


@dataclass(frozen=True)
class DatabaseRepairResult:
    # repair result 必須說明是否真的修改資料庫，避免 UI 把診斷建議誤當已修復。
    provider_id: str
    asset_id: str
    action_id: str
    manifest_path: str
    sqlite_path: str
    table_name: str
    rows_imported: int
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "asset_id": self.asset_id,
            "action_id": self.action_id,
            "manifest_path": self.manifest_path,
            "sqlite_path": self.sqlite_path,
            "table_name": self.table_name,
            "rows_imported": self.rows_imported,
            "message": self.message,
        }


@dataclass(frozen=True)
class DatabaseRegistryRepairResult:
    provider_id: str
    asset_id: str
    action_id: str
    asset_kind: str
    engine: str
    asset_name: str
    previous_status: str
    status: str
    message: str = ""
    registry_only: bool = True
    database_modified: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "asset_id": self.asset_id,
            "action_id": self.action_id,
            "asset_kind": self.asset_kind,
            "engine": self.engine,
            "asset_name": self.asset_name,
            "previous_status": self.previous_status,
            "status": self.status,
            "message": self.message,
            "registry_only": self.registry_only,
            "database_modified": self.database_modified,
        }


@dataclass(frozen=True)
class DatabaseSqlRepairDryRunResult:
    # 非 SQLite repair 目前只產生可審核 SQL，不連線、不執行，避免誤改使用者真實資料庫。
    provider_id: str
    asset_id: str
    action_id: str
    engine: str
    asset_name: str
    manifest_path: str
    payload_path: str
    sql_path: str
    table_name: str
    columns: tuple[str, ...]
    rows_planned: int
    row_limit: int
    message: str = ""
    dry_run: bool = True
    database_modified: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "asset_id": self.asset_id,
            "action_id": self.action_id,
            "engine": self.engine,
            "asset_name": self.asset_name,
            "manifest_path": self.manifest_path,
            "payload_path": self.payload_path,
            "sql_path": self.sql_path,
            "table_name": self.table_name,
            "columns": list(self.columns),
            "rows_planned": self.rows_planned,
            "row_limit": self.row_limit,
            "message": self.message,
            "dry_run": self.dry_run,
            "database_modified": self.database_modified,
        }


def database_repair_sql_path_for_asset(asset_id: str, output_dir: str | Path = "state/database_repair") -> Path:
    # dry-run SQL 檔名由 registry asset_id 產生；這裡集中處理，避免 CLI/UI 各自實作時漏掉路徑穿越防護。
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", asset_id.strip()).strip("._") or "database_asset"
    return Path(output_dir) / f"{safe_name}.dry_run.sql"


def stop_tracking_database_asset(repository: ApiCatalogRepository, asset_id: str) -> DatabaseRegistryRepairResult:
    # stop-tracking 只改 registry 狀態，不執行 DROP/DELETE，適合不確定 ownership 的情境。
    asset_id = asset_id.strip()
    if not asset_id:
        raise ValueError("asset_id is required")
    row = repository.conn.execute(
        """
        SELECT
            pi.provider_id,
            pia.asset_id,
            pia.asset_kind,
            COALESCE(pia.engine, '') AS engine,
            pia.asset_name,
            pia.status
        FROM provider_installation_assets pia
        JOIN provider_installations pi ON pi.install_id = pia.install_id
        WHERE pia.asset_id = ?
          AND pia.asset_kind IN ('database', 'table')
        """,
        (asset_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Database asset was not found: {asset_id}")
    changed = repository.unmanage_database_asset(
        asset_id,
        notes="Unmanaged from CLI database repair workflow; no database object was modified.",
    )
    if not changed:
        raise ValueError(f"Database asset was not updated: {asset_id}")
    return DatabaseRegistryRepairResult(
        provider_id=row["provider_id"],
        asset_id=asset_id,
        action_id="unmanage_database_asset",
        asset_kind=row["asset_kind"],
        engine=row["engine"],
        asset_name=row["asset_name"],
        previous_status=row["status"],
        status="unmanaged",
        message="Marked database asset unmanaged; no database object was modified.",
    )


def write_missing_sql_table_repair_dry_run(
    repository: ApiCatalogRepository,
    asset_id: str,
    output_path: str | Path,
    row_limit: int = 1000,
) -> DatabaseSqlRepairDryRunResult:
    # 這個入口只服務 guided repair：把缺表的重建步驟寫成 SQL 草稿，交由人類審核後自行執行。
    asset_id = asset_id.strip()
    if not asset_id:
        raise ValueError("asset_id is required")
    if row_limit < 0:
        raise ValueError("row_limit must be zero or positive")
    row = _database_repair_asset_row(repository, asset_id)
    engine = str(row["engine"] or "").strip().lower()
    if engine not in {"mysql", "mariadb", "postgres", "postgresql"}:
        raise ValueError("Only MySQL/MariaDB/PostgreSQL table assets can write SQL repair dry-runs.")
    if row["asset_kind"] != "table":
        raise ValueError("Only table assets can write SQL repair dry-runs.")
    if row["status"] not in {"missing", "error"}:
        raise ValueError(f"Asset status is {row['status']}; rerun self-check before writing repair SQL.")

    manifest_path = manifest_path_from_notes(row["notes"])
    if not manifest_path:
        raise ValueError("No source manifest path is recorded for this table asset.")
    source_format = str(row["source_format"] or "").strip().lower()
    if source_format not in CSV_REIMPORT_FORMATS + JSON_REIMPORT_FORMATS:
        raise ValueError(
            f"Unsupported source format for SQL repair dry-run: {source_format or 'unknown'}. "
            f"Supported formats: {supported_reimport_source_formats_label()}"
        )

    manifest_file = Path(manifest_path)
    verification = verify_manifest_file(manifest_file)
    if verification.status != "ok":
        raise ValueError(f"Manifest is not healthy: {verification.status} {verification.message}")
    manifest = read_manifest(manifest_file)
    payload_path = Path(manifest.path)
    table_label = _qualified_sql_table_name(
        engine,
        str(row["asset_name"] or ""),
        str(row["schema_name"] or ""),
    )
    columns, rows = _sql_rows_from_manifest_payload(payload_path, source_format, row_limit)
    sql_text = _render_missing_table_repair_sql(
        engine=engine,
        provider_id=str(row["provider_id"] or ""),
        asset_id=asset_id,
        asset_name=str(row["asset_name"] or ""),
        install_location=str(row["install_location"] or ""),
        manifest_path=manifest_file,
        payload_path=payload_path,
        source_url=manifest.source_url,
        table_label=table_label,
        columns=columns,
        rows=rows,
        row_limit=row_limit,
    )

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(sql_text, encoding="utf-8", newline="\n")
    return DatabaseSqlRepairDryRunResult(
        provider_id=str(row["provider_id"] or ""),
        asset_id=asset_id,
        action_id="write_missing_sql_table_repair_dry_run",
        engine=engine,
        asset_name=str(row["asset_name"] or ""),
        manifest_path=str(manifest_file),
        payload_path=str(payload_path),
        sql_path=str(target),
        table_name=table_label,
        columns=columns,
        rows_planned=len(rows),
        row_limit=row_limit,
        message=f"Wrote dry-run SQL for {table_label}; review before executing against {engine}.",
    )


def _database_repair_asset_row(repository: ApiCatalogRepository, asset_id: str):
    row = repository.conn.execute(
        """
        SELECT
            pi.provider_id,
            COALESCE(pi.location, '') AS install_location,
            pia.asset_id,
            pia.asset_kind,
            COALESCE(pia.engine, '') AS engine,
            pia.asset_name,
            COALESCE(pia.source_format, 'unknown') AS source_format,
            COALESCE(pia.source_uri, '') AS source_uri,
            pia.status,
            COALESCE(pia.schema_name, '') AS schema_name,
            COALESCE(pia.notes, '') AS notes
        FROM provider_installation_assets pia
        JOIN provider_installations pi ON pi.install_id = pia.install_id
        WHERE pia.asset_id = ?
        """,
        (asset_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Database asset was not found: {asset_id}")
    return row


def _sql_rows_from_manifest_payload(
    payload_path: Path,
    source_format: str,
    row_limit: int,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    # SQL dry-run 盡量沿用 SQLite importer 的欄位正規化，避免同一份 manifest 在不同 engine 產生不同欄名。
    if source_format in CSV_REIMPORT_FORMATS:
        with open_csv_text(payload_path) as handle:
            reader = csv.reader(handle)
            try:
                headers = next(reader)
            except StopIteration as exc:
                raise ValueError(f"CSV payload is empty: {payload_path}") from exc
            columns = normalized_column_names(headers)
            rows: list[tuple[str, ...]] = []
            for raw_row in reader:
                if row_limit > 0 and len(rows) >= row_limit:
                    break
                rows.append(normalized_row_values(raw_row, len(columns)))
            return columns, tuple(rows)
    if source_format in JSON_REIMPORT_FORMATS:
        parsed = load_json_records(payload_path, row_limit=row_limit)
        if not parsed.rows:
            raise ValueError(f"JSON payload has no object rows: {payload_path}")
        raw_columns = ordered_keys(parsed.rows)
        columns = normalized_column_names(raw_columns)
        return columns, tuple(tuple(row_values(row, raw_columns)) for row in parsed.rows)
    raise ValueError(
        f"Unsupported source format for SQL repair dry-run: {source_format or 'unknown'}. "
        f"Supported formats: {supported_reimport_source_formats_label()}"
    )


def _render_missing_table_repair_sql(
    engine: str,
    provider_id: str,
    asset_id: str,
    asset_name: str,
    install_location: str,
    manifest_path: Path,
    payload_path: Path,
    source_url: str,
    table_label: str,
    columns: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    row_limit: int,
) -> str:
    quoted_columns = [_quote_identifier(engine, column) for column in columns]
    column_defs = ",\n  ".join(f"{column} TEXT" for column in quoted_columns)
    insert_columns = ", ".join(quoted_columns)
    sql_lines = [
        "-- APIkeys_collection database repair dry-run",
        "-- 這份 SQL 只供人工審核；launcher 沒有替你執行，也沒有修改 registry 或遠端資料庫。",
        f"-- provider_id: {provider_id}",
        f"-- asset_id: {asset_id}",
        f"-- engine: {engine}",
        f"-- asset_name: {asset_name}",
        f"-- expected_location: {install_location}",
        f"-- manifest: {manifest_path}",
        f"-- payload: {payload_path}",
        f"-- source_url: {source_url}",
        f"-- row_limit: {row_limit} (0 means all rows)",
        "",
        f"CREATE TABLE IF NOT EXISTS {table_label} (",
        f"  {column_defs}",
        ");",
        "",
    ]
    for values in rows:
        value_sql = ", ".join(_sql_literal(value) for value in values)
        sql_lines.append(f"INSERT INTO {table_label} ({insert_columns}) VALUES ({value_sql});")
    if row_limit > 0:
        sql_lines.extend(
            [
                "",
                "-- 注意：本檔依 row_limit 產生 bounded INSERT 預覽；若要完整資料，請重新產生 row_limit=0 的 dry-run 後再審核。",
            ]
        )
    return "\n".join(sql_lines).rstrip() + "\n"


def _qualified_sql_table_name(engine: str, asset_name: str, schema_name: str) -> str:
    schema, table = _split_schema_table_name(asset_name)
    selected_schema = schema_name.strip() or schema
    clean_table = validate_sql_identifier(table)
    quoted_table = _quote_identifier(engine, clean_table)
    if selected_schema:
        return f"{_quote_identifier(engine, validate_sql_identifier(selected_schema))}.{quoted_table}"
    return quoted_table


def _split_schema_table_name(value: str) -> tuple[str, str]:
    raw = value.strip()
    if "." not in raw:
        return "", raw
    schema_name, table_name = raw.split(".", 1)
    if not schema_name.strip() or not table_name.strip():
        return "", raw
    return schema_name.strip(), table_name.strip()


def _quote_identifier(engine: str, identifier: str) -> str:
    clean = validate_sql_identifier(identifier)
    if engine in {"mysql", "mariadb"}:
        return f"`{clean}`"
    return f'"{clean}"'


def _sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def reimport_missing_sqlite_table_asset(repository: ApiCatalogRepository, asset_id: str) -> DatabaseRepairResult:
    asset_id = asset_id.strip()
    if not asset_id:
        raise ValueError("asset_id is required")
    row = repository.conn.execute(
        """
        SELECT
            pi.provider_id,
            COALESCE(pi.location, '') AS install_location,
            pia.asset_id,
            pia.asset_kind,
            COALESCE(pia.engine, '') AS engine,
            pia.asset_name,
            COALESCE(pia.source_format, 'unknown') AS source_format,
            COALESCE(pia.source_uri, '') AS source_uri,
            pia.status,
            COALESCE(pia.notes, '') AS notes
        FROM provider_installation_assets pia
        JOIN provider_installations pi ON pi.install_id = pia.install_id
        WHERE pia.asset_id = ?
        """,
        (asset_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Database asset was not found: {asset_id}")
    if row["asset_kind"] != "table" or row["engine"].strip().lower() != "sqlite":
        raise ValueError("Only SQLite table assets can be reimported by this repair action.")
    if row["status"] not in {"missing", "error"}:
        raise ValueError(f"Asset status is {row['status']}; rerun self-check instead of reimporting.")

    manifest_path = manifest_path_from_notes(row["notes"])
    if not manifest_path:
        raise ValueError("No source manifest path is recorded for this table asset.")

    sqlite_path = row["source_uri"] or row["install_location"]
    if not sqlite_path:
        raise ValueError("No SQLite database path is recorded for this table asset.")

    table_name = row["asset_name"]
    if table_exists(sqlite_path, table_name):
        raise ValueError(f"SQLite table already exists: {table_name}. Rerun self-check instead.")

    source_format = row["source_format"].strip().lower()
    if source_format in CSV_REIMPORT_FORMATS:
        result = import_csv_manifest_to_sqlite(
            manifest_path,
            Path(sqlite_path),
            repository,
            table_name=table_name,
            replace=False,
        )
        rows_imported = result.rows_imported
    elif source_format in JSON_REIMPORT_FORMATS:
        result = import_json_manifest_to_sqlite(
            manifest_path,
            Path(sqlite_path),
            repository,
            table_name=table_name,
            replace=False,
        )
        rows_imported = result.rows_imported
    else:
        raise ValueError(
            f"Unsupported source format for table reimport: {source_format or 'unknown'}. "
            f"Supported formats: {supported_reimport_source_formats_label()}"
        )

    return DatabaseRepairResult(
        provider_id=row["provider_id"],
        asset_id=asset_id,
        action_id="reimport_missing_sqlite_table",
        manifest_path=str(manifest_path),
        sqlite_path=str(sqlite_path),
        table_name=table_name,
        rows_imported=rows_imported,
        message=f"Reimported {rows_imported} rows into {table_name}.",
    )
