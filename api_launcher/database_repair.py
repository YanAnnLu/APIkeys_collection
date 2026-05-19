from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from api_launcher.importers.csv_importer import import_csv_manifest_to_sqlite, table_exists
from api_launcher.importers.json_importer import import_json_manifest_to_sqlite
from api_launcher.repository import ApiCatalogRepository


@dataclass(frozen=True)
class DatabaseRepairResult:
    provider_id: str
    asset_id: str
    action_id: str
    manifest_path: str
    sqlite_path: str
    table_name: str
    rows_imported: int
    message: str = ""


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
    if source_format == "csv":
        result = import_csv_manifest_to_sqlite(
            manifest_path,
            Path(sqlite_path),
            repository,
            table_name=table_name,
            replace=False,
        )
        rows_imported = result.rows_imported
    elif source_format == "json":
        result = import_json_manifest_to_sqlite(
            manifest_path,
            Path(sqlite_path),
            repository,
            table_name=table_name,
            replace=False,
        )
        rows_imported = result.rows_imported
    else:
        raise ValueError(f"Unsupported source format for table reimport: {source_format or 'unknown'}")

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


def manifest_path_from_notes(notes: str) -> str:
    match = re.search(r"(?:^|\s)manifest=(?P<path>.+?)(?:\s+payload=|\s+source_url=|$)", notes.strip())
    if not match:
        return ""
    return match.group("path").strip().strip("'\"")
