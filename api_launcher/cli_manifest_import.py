from __future__ import annotations

import argparse

from api_launcher.db import resolve_project_path
from api_launcher.importers.csv_importer import import_csv_manifest_to_sqlite, import_verified_csv_manifests_to_sqlite
from api_launcher.importers.json_importer import import_json_manifest_to_sqlite, import_verified_json_manifests_to_sqlite
from api_launcher.manifests import read_manifest
from api_launcher.manual_import import DEFAULT_MANUAL_LOCAL_PROVIDER_ID, ensure_manual_local_file_provider
from api_launcher.repository import ApiCatalogRepository


def manifest_import_command_active(args: argparse.Namespace) -> bool:
    # 這裡只判斷 manifest -> SQLite 匯入族群，讓 core.py 不必知道每個匯入旗標的存在。
    return bool(
        args.import_csv_manifest
        or args.import_verified_csv_manifests
        or args.import_json_manifest
        or args.import_verified_json_manifests
    )


def import_csv_manifest_cli(args: argparse.Namespace, repository: ApiCatalogRepository) -> None:
    if not args.import_csv_manifest:
        return
    manifest_path = resolve_project_path(args.import_csv_manifest)
    manifest = read_manifest(manifest_path)
    # 手動匯入產出的 synthetic provider 需要先補齊，否則 curated table asset 會失去來源歸屬。
    if manifest.provider_id == DEFAULT_MANUAL_LOCAL_PROVIDER_ID:
        ensure_manual_local_file_provider(repository, manifest.provider_id)
    result = import_csv_manifest_to_sqlite(
        manifest_path,
        resolve_project_path(args.import_sqlite_db),
        repository,
        table_name=args.import_table,
        replace=args.import_replace_table,
        row_limit=args.import_row_limit,
    )
    print(
        "[csv-import] "
        f"provider={result.provider_id} table={result.table_name} rows={result.rows_imported} "
        f"columns={len(result.columns)} sqlite={result.sqlite_path} asset={result.table_asset_id}"
    )


def import_verified_csv_manifests_cli(args: argparse.Namespace, repository: ApiCatalogRepository) -> None:
    if not args.import_verified_csv_manifests:
        return
    sqlite_path = resolve_project_path(args.import_sqlite_db)
    result = import_verified_csv_manifests_to_sqlite(
        repository,
        sqlite_path,
        provider_ids=args.provider or None,
        replace=args.import_replace_table,
        row_limit=args.import_row_limit,
    )
    print(
        "[csv-import-batch] "
        f"checked={result.checked} imported={result.imported} skipped={result.skipped} "
        f"non_csv={result.skipped_non_csv} unhealthy={result.skipped_unhealthy} "
        f"existing={result.skipped_existing} failed={result.failed} sqlite={sqlite_path}"
    )
    for item in result.results:
        print(f"[csv-import-batch] imported provider={item.provider_id} table={item.table_name} rows={item.rows_imported}")
    for error in result.errors:
        print(f"[csv-import-batch] error {error}")


def import_json_manifest_cli(args: argparse.Namespace, repository: ApiCatalogRepository) -> None:
    if not args.import_json_manifest:
        return
    manifest_path = resolve_project_path(args.import_json_manifest)
    manifest = read_manifest(manifest_path)
    # 與 CSV 路徑保持同一個來源保護：本機檔案 manifest 也必須有可追蹤的 synthetic provider。
    if manifest.provider_id == DEFAULT_MANUAL_LOCAL_PROVIDER_ID:
        ensure_manual_local_file_provider(repository, manifest.provider_id)
    result = import_json_manifest_to_sqlite(
        manifest_path,
        resolve_project_path(args.import_sqlite_db),
        repository,
        table_name=args.import_table,
        replace=args.import_replace_table,
        row_limit=args.import_row_limit,
    )
    print(
        "[json-import] "
        f"provider={result.provider_id} table={result.table_name} rows={result.rows_imported} "
        f"columns={len(result.columns)} shape={result.source_shape} sqlite={result.sqlite_path} "
        f"asset={result.table_asset_id}"
    )


def import_verified_json_manifests_cli(args: argparse.Namespace, repository: ApiCatalogRepository) -> None:
    if not args.import_verified_json_manifests:
        return
    sqlite_path = resolve_project_path(args.import_sqlite_db)
    result = import_verified_json_manifests_to_sqlite(
        repository,
        sqlite_path,
        provider_ids=args.provider or None,
        replace=args.import_replace_table,
        row_limit=args.import_row_limit,
    )
    print(
        "[json-import-batch] "
        f"checked={result.checked} imported={result.imported} skipped={result.skipped} "
        f"non_json={result.skipped_non_json} unhealthy={result.skipped_unhealthy} "
        f"existing={result.skipped_existing} failed={result.failed} sqlite={sqlite_path}"
    )
    for item in result.results:
        print(
            "[json-import-batch] "
            f"imported provider={item.provider_id} table={item.table_name} "
            f"rows={item.rows_imported} shape={item.source_shape}"
        )
    for error in result.errors:
        print(f"[json-import-batch] error {error}")
