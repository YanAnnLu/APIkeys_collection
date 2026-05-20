from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_launcher.database_repair_contracts import (
    CSV_REIMPORT_FORMATS,
    JSON_REIMPORT_FORMATS,
    manifest_path_from_notes,
    supported_reimport_source_formats_label,
)
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


def stop_tracking_database_asset(repository: ApiCatalogRepository, asset_id: str) -> DatabaseRegistryRepairResult:
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
