from __future__ import annotations

import csv
import gzip
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from api_launcher.database_self_check import sqlite_table_schema_summary
from api_launcher.manifests import AssetManifest, read_manifest
from api_launcher.downloads.repair import verify_manifest_file
from api_launcher.repository import ApiCatalogRepository
from api_launcher.sql_assets import validate_sql_identifier


@dataclass(frozen=True)
class CsvImportResult:
    provider_id: str
    manifest_path: str
    sqlite_path: str
    table_name: str
    columns: tuple[str, ...]
    rows_imported: int
    schema_fingerprint: str
    table_asset_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "manifest_path": self.manifest_path,
            "sqlite_path": self.sqlite_path,
            "table_name": self.table_name,
            "columns": list(self.columns),
            "rows_imported": self.rows_imported,
            "schema_fingerprint": self.schema_fingerprint,
            "table_asset_id": self.table_asset_id,
        }


@dataclass(frozen=True)
class CsvBatchImportResult:
    checked: int
    imported: int
    skipped_non_csv: int
    skipped_unhealthy: int
    skipped_existing: int
    failed: int
    results: tuple[CsvImportResult, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def skipped(self) -> int:
        return self.skipped_non_csv + self.skipped_unhealthy + self.skipped_existing

    def to_dict(self) -> dict[str, object]:
        return {
            "checked": self.checked,
            "imported": self.imported,
            "skipped": self.skipped,
            "skipped_non_csv": self.skipped_non_csv,
            "skipped_unhealthy": self.skipped_unhealthy,
            "skipped_existing": self.skipped_existing,
            "failed": self.failed,
            "results": [result.to_dict() for result in self.results],
            "errors": list(self.errors),
        }


def import_csv_manifest_to_sqlite(
    manifest_path: str | Path,
    sqlite_path: str | Path,
    repository: ApiCatalogRepository,
    table_name: str = "",
    replace: bool = False,
    row_limit: int = 0,
) -> CsvImportResult:
    manifest_file = Path(manifest_path)
    verification = verify_manifest_file(manifest_file)
    if verification.status != "ok":
        raise ValueError(f"Manifest is not healthy: {verification.status} {verification.message}")

    manifest = read_manifest(manifest_file)
    payload_path = Path(manifest.path)
    if not is_csv_payload(payload_path):
        raise ValueError(f"Only .csv and .csv.gz payloads are supported for this MVP import: {payload_path}")

    target_db = Path(sqlite_path)
    target_db.parent.mkdir(parents=True, exist_ok=True)
    clean_table = validate_sql_identifier(table_name.strip() or table_name_for_manifest(manifest))

    with open_csv_text(payload_path) as handle:
        reader = csv.reader(handle)
        try:
            raw_headers = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV payload is empty: {payload_path}") from exc
        columns = normalized_column_names(raw_headers)
        rows_imported = import_rows_to_sqlite(
            target_db,
            clean_table,
            columns,
            reader,
            replace=replace,
            row_limit=row_limit,
        )

    fingerprint = sqlite_table_schema_summary(target_db, clean_table).schema_fingerprint
    table_asset_id = repository.register_provider_table_asset(
        manifest.provider_id,
        engine="sqlite",
        database_name=target_db.name,
        table_name=clean_table,
        location=str(target_db),
        asset_role="curated",
        source_format="csv",
        source_uri=str(target_db),
        schema_fingerprint=fingerprint,
        notes=(
            "Curated SQLite table imported from verified CSV manifest. "
            f"manifest={manifest_file} payload={manifest.path} source_url={manifest.source_url}"
        ),
    )
    return CsvImportResult(
        provider_id=manifest.provider_id,
        manifest_path=str(manifest_file),
        sqlite_path=str(target_db),
        table_name=clean_table,
        columns=columns,
        rows_imported=rows_imported,
        schema_fingerprint=fingerprint,
        table_asset_id=table_asset_id,
    )


def import_verified_csv_manifests_to_sqlite(
    repository: ApiCatalogRepository,
    sqlite_path: str | Path,
    provider_ids: Iterable[str] | None = None,
    replace: bool = False,
    row_limit: int = 0,
    skip_existing: bool = True,
) -> CsvBatchImportResult:
    records = []
    provider_list = tuple(provider_id for provider_id in (provider_ids or ()) if provider_id)
    if provider_list:
        for provider_id in provider_list:
            records.extend(repository.list_dataset_asset_manifests(provider_id))
    else:
        records = repository.list_dataset_asset_manifests()

    target_db = Path(sqlite_path)
    results: list[CsvImportResult] = []
    errors: list[str] = []
    skipped_non_csv = 0
    skipped_unhealthy = 0
    skipped_existing = 0
    failed = 0

    for record in records:
        if record.status != "ok":
            skipped_unhealthy += 1
            continue
        payload_path = Path(record.path)
        if not is_csv_payload(payload_path):
            skipped_non_csv += 1
            continue
        try:
            manifest = read_manifest(record.manifest_path)
            table_name = table_name_for_manifest(manifest)
            if skip_existing and not replace and table_exists(target_db, table_name):
                skipped_existing += 1
                continue
            result = import_csv_manifest_to_sqlite(
                record.manifest_path,
                target_db,
                repository,
                replace=replace,
                row_limit=row_limit,
            )
        except Exception as exc:
            failed += 1
            errors.append(f"{record.provider_id}:{record.dataset_id}:{record.version}: {type(exc).__name__}: {exc}")
            continue
        results.append(result)

    return CsvBatchImportResult(
        checked=len(records),
        imported=len(results),
        skipped_non_csv=skipped_non_csv,
        skipped_unhealthy=skipped_unhealthy,
        skipped_existing=skipped_existing,
        failed=failed,
        results=tuple(results),
        errors=tuple(errors),
    )


def import_rows_to_sqlite(
    sqlite_path: Path,
    table_name: str,
    columns: tuple[str, ...],
    rows: Iterable[list[str]],
    replace: bool,
    row_limit: int,
) -> int:
    quoted_table = quote_identifier(table_name)
    quoted_columns = ", ".join(f"{quote_identifier(column)} TEXT" for column in columns)
    insert_columns = ", ".join(quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    with closing(sqlite3.connect(sqlite_path)) as conn:
        if replace:
            conn.execute(f"DROP TABLE IF EXISTS {quoted_table}")
        conn.execute(f"CREATE TABLE {quoted_table} ({quoted_columns})")
        count = 0
        for row in rows:
            if row_limit > 0 and count >= row_limit:
                break
            values = normalized_row_values(row, len(columns))
            conn.execute(f"INSERT INTO {quoted_table} ({insert_columns}) VALUES ({placeholders})", values)
            count += 1
        conn.commit()
        return count


def table_exists(sqlite_path: str | Path, table_name: str) -> bool:
    path = Path(sqlite_path)
    if not path.exists():
        return False
    with closing(sqlite3.connect(path)) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (validate_sql_identifier(table_name),),
        ).fetchone()
    return row is not None


def normalized_row_values(row: list[str], width: int) -> tuple[str, ...]:
    padded = [*row, *([""] * max(0, width - len(row)))]
    return tuple(str(value) for value in padded[:width])


def normalized_column_names(headers: Iterable[str]) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    columns: list[str] = []
    for index, header in enumerate(headers, start=1):
        base = sql_identifier_from_text(header, fallback=f"column_{index}")
        count = counts.get(base, 0) + 1
        counts[base] = count
        suffix = f"_{count}" if count > 1 else ""
        name = f"{base[:63 - len(suffix)]}{suffix}"
        columns.append(validate_sql_identifier(name))
    if not columns:
        raise ValueError("CSV payload has no header columns.")
    return tuple(columns)


def sql_identifier_from_text(value: str, fallback: str) -> str:
    clean = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    if not clean:
        clean = fallback
    if clean[0].isdigit():
        clean = f"col_{clean}"
    return validate_sql_identifier(clean[:63].rstrip("_") or fallback)


def table_name_for_manifest(manifest: AssetManifest) -> str:
    parts = [manifest.dataset_id or manifest.provider_id, manifest.version]
    return sql_identifier_from_text("_".join(part for part in parts if part), fallback="imported_csv")


def quote_identifier(identifier: str) -> str:
    return f'"{validate_sql_identifier(identifier)}"'


def is_csv_payload(path: Path) -> bool:
    suffixes = [suffix.lower() for suffix in path.suffixes]
    return suffixes[-1:] == [".csv"] or suffixes[-2:] == [".csv", ".gz"]


def open_csv_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", errors="replace", newline="")
    return path.open("r", encoding="utf-8-sig", errors="replace", newline="")
