from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from api_launcher.csv_importer import (
    import_rows_to_sqlite,
    normalized_column_names,
    table_exists,
    table_name_for_manifest,
)
from api_launcher.manifests import AssetManifest, read_manifest
from api_launcher.provenance import schema_fingerprint
from api_launcher.repair import verify_manifest_file
from api_launcher.repository import ApiCatalogRepository
from api_launcher.sql_assets import validate_sql_identifier


@dataclass(frozen=True)
class JsonImportResult:
    provider_id: str
    manifest_path: str
    sqlite_path: str
    table_name: str
    columns: tuple[str, ...]
    rows_imported: int
    schema_fingerprint: str
    table_asset_id: str
    source_shape: str

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
            "source_shape": self.source_shape,
        }


@dataclass(frozen=True)
class JsonBatchImportResult:
    checked: int
    imported: int
    skipped_non_json: int
    skipped_unhealthy: int
    skipped_existing: int
    failed: int
    results: tuple[JsonImportResult, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def skipped(self) -> int:
        return self.skipped_non_json + self.skipped_unhealthy + self.skipped_existing

    def to_dict(self) -> dict[str, object]:
        return {
            "checked": self.checked,
            "imported": self.imported,
            "skipped": self.skipped,
            "skipped_non_json": self.skipped_non_json,
            "skipped_unhealthy": self.skipped_unhealthy,
            "skipped_existing": self.skipped_existing,
            "failed": self.failed,
            "results": [result.to_dict() for result in self.results],
            "errors": list(self.errors),
        }


def import_json_manifest_to_sqlite(
    manifest_path: str | Path,
    sqlite_path: str | Path,
    repository: ApiCatalogRepository,
    table_name: str = "",
    replace: bool = False,
    row_limit: int = 0,
) -> JsonImportResult:
    manifest_file = Path(manifest_path)
    verification = verify_manifest_file(manifest_file)
    if verification.status != "ok":
        raise ValueError(f"Manifest is not healthy: {verification.status} {verification.message}")

    manifest = read_manifest(manifest_file)
    payload_path = Path(manifest.path)
    if not is_json_payload(payload_path):
        raise ValueError(f"Only JSON/JSONL/GeoJSON payloads are supported for this MVP import: {payload_path}")

    target_db = Path(sqlite_path)
    target_db.parent.mkdir(parents=True, exist_ok=True)
    clean_table = validate_sql_identifier(table_name.strip() or table_name_for_manifest(manifest))
    parsed = load_json_records(payload_path, row_limit=row_limit)
    if not parsed.rows:
        raise ValueError(f"JSON payload has no object rows: {payload_path}")

    raw_columns = ordered_keys(parsed.rows)
    columns = normalized_column_names(raw_columns)
    sql_rows = [row_values(row, raw_columns) for row in parsed.rows]
    rows_imported = import_rows_to_sqlite(
        target_db,
        clean_table,
        columns,
        sql_rows,
        replace=replace,
        row_limit=0,
    )

    fingerprint = schema_fingerprint(columns)
    table_asset_id = repository.register_provider_table_asset(
        manifest.provider_id,
        engine="sqlite",
        database_name=target_db.name,
        table_name=clean_table,
        location=str(target_db),
        asset_role="curated",
        source_format="json",
        source_uri=str(target_db),
        schema_fingerprint=fingerprint,
        notes=(
            "Curated SQLite table imported from verified JSON manifest. "
            f"shape={parsed.source_shape} manifest={manifest_file} payload={manifest.path} source_url={manifest.source_url}"
        ),
    )
    return JsonImportResult(
        provider_id=manifest.provider_id,
        manifest_path=str(manifest_file),
        sqlite_path=str(target_db),
        table_name=clean_table,
        columns=columns,
        rows_imported=rows_imported,
        schema_fingerprint=fingerprint,
        table_asset_id=table_asset_id,
        source_shape=parsed.source_shape,
    )


def import_verified_json_manifests_to_sqlite(
    repository: ApiCatalogRepository,
    sqlite_path: str | Path,
    provider_ids: Iterable[str] | None = None,
    replace: bool = False,
    row_limit: int = 0,
    skip_existing: bool = True,
) -> JsonBatchImportResult:
    records = []
    provider_list = tuple(provider_id for provider_id in (provider_ids or ()) if provider_id)
    if provider_list:
        for provider_id in provider_list:
            records.extend(repository.list_dataset_asset_manifests(provider_id))
    else:
        records = repository.list_dataset_asset_manifests()

    target_db = Path(sqlite_path)
    results: list[JsonImportResult] = []
    errors: list[str] = []
    skipped_non_json = 0
    skipped_unhealthy = 0
    skipped_existing = 0
    failed = 0

    for record in records:
        if record.status != "ok":
            skipped_unhealthy += 1
            continue
        payload_path = Path(record.path)
        if not is_json_payload(payload_path):
            skipped_non_json += 1
            continue
        try:
            manifest = read_manifest(record.manifest_path)
            table_name = table_name_for_manifest(manifest)
            if skip_existing and not replace and table_exists(target_db, table_name):
                skipped_existing += 1
                continue
            result = import_json_manifest_to_sqlite(
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

    return JsonBatchImportResult(
        checked=len(records),
        imported=len(results),
        skipped_non_json=skipped_non_json,
        skipped_unhealthy=skipped_unhealthy,
        skipped_existing=skipped_existing,
        failed=failed,
        results=tuple(results),
        errors=tuple(errors),
    )


@dataclass(frozen=True)
class ParsedJsonRows:
    rows: tuple[dict[str, object], ...]
    source_shape: str


def load_json_records(path: Path, row_limit: int = 0) -> ParsedJsonRows:
    if is_json_lines_payload(path):
        return ParsedJsonRows(tuple(limit_rows(read_json_lines(path), row_limit)), "json_lines")

    with open_json_text(path) as handle:
        data = json.load(handle)
    rows, shape = rows_from_json_value(data)
    return ParsedJsonRows(tuple(limit_rows(rows, row_limit)), shape)


def rows_from_json_value(value: object) -> tuple[list[dict[str, object]], str]:
    if isinstance(value, list):
        return [normalize_json_row(item) for item in value], "array"
    if isinstance(value, dict):
        if isinstance(value.get("features"), list):
            return [feature_to_row(item) for item in value["features"]], "geojson_feature_collection"
        for key in ("records", "items", "results", "data"):
            items = value.get(key)
            if isinstance(items, list):
                return [normalize_json_row(item) for item in items], f"object_{key}_array"
        return [normalize_json_row(value)], "object"
    return [normalize_json_row(value)], "scalar"


def read_json_lines(path: Path) -> Iterable[dict[str, object]]:
    with open_json_text(path) as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                yield normalize_json_row(json.loads(text))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON line {line_number} in {path}: {exc}") from exc


def limit_rows(rows: Iterable[dict[str, object]], row_limit: int) -> list[dict[str, object]]:
    limited: list[dict[str, object]] = []
    for row in rows:
        if row_limit > 0 and len(limited) >= row_limit:
            break
        limited.append(row)
    return limited


def normalize_json_row(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return {"value": value}


def feature_to_row(value: object) -> dict[str, object]:
    feature = value if isinstance(value, dict) else {}
    properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    row = dict(properties)
    if "id" in feature:
        row["feature_id"] = feature["id"]
    if "geometry" in feature:
        row["geometry_json"] = feature["geometry"]
    if "type" in feature:
        row["feature_type"] = feature["type"]
    return row or normalize_json_row(value)


def ordered_keys(rows: Iterable[dict[str, object]]) -> tuple[str, ...]:
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            text = str(key)
            if text not in seen:
                seen.add(text)
                keys.append(text)
    if not keys:
        raise ValueError("JSON payload has no columns.")
    return tuple(keys)


def row_values(row: dict[str, object], keys: tuple[str, ...]) -> list[str]:
    return [json_cell_value(row.get(key)) for key in keys]


def json_cell_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def is_json_payload(path: Path) -> bool:
    suffixes = [suffix.lower() for suffix in path.suffixes]
    return suffixes[-1:] in ([".json"], [".jsonl"], [".ndjson"], [".geojson"]) or suffixes[-2:] in (
        [".json", ".gz"],
        [".jsonl", ".gz"],
        [".ndjson", ".gz"],
        [".geojson", ".gz"],
    )


def is_json_lines_payload(path: Path) -> bool:
    suffixes = [suffix.lower() for suffix in path.suffixes]
    return suffixes[-1:] in ([".jsonl"], [".ndjson"]) or suffixes[-2:] in ([".jsonl", ".gz"], [".ndjson", ".gz"])


def open_json_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig")
    return path.open("r", encoding="utf-8-sig")
