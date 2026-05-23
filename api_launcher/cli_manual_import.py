from __future__ import annotations

import argparse
import json
from pathlib import Path

from api_launcher.db import resolve_project_path
from api_launcher.importers.csv_importer import import_csv_manifest_to_sqlite
from api_launcher.importers.json_importer import import_json_manifest_to_sqlite
from api_launcher.manual_import import (
    DEFAULT_MANUAL_LOCAL_PROVIDER_ID,
    ensure_manual_local_file_provider,
    register_local_file_manifest_asset,
    write_local_file_manifest as write_local_file_manifest_file,
)
from api_launcher.repository import ApiCatalogRepository


def manual_import_command_active(args: argparse.Namespace) -> bool:
    # manual-import-json 是輸出格式旗標；保留舊行為，單獨出現時也不退回預設 init/seed。
    return bool(args.write_local_file_manifest or args.import_local_file or args.manual_import_json)


def validate_manual_import_args(args: argparse.Namespace) -> None:
    # JSON 輸出是手動匯入流程的附加格式；單獨使用會讓 agent 收不到任何可解析結果。
    if args.manual_import_json and not (args.write_local_file_manifest or args.import_local_file):
        raise RuntimeError("--manual-import-json requires --write-local-file-manifest or --import-local-file.")


def write_local_file_manifest_cli(args: argparse.Namespace, repository: ApiCatalogRepository) -> None:
    if not args.write_local_file_manifest:
        return
    if not args.local_file:
        raise ValueError("--write-local-file-manifest requires --local-file.")
    result = write_local_file_manifest_file(
        resolve_project_path(args.local_file),
        resolve_project_path(args.write_local_file_manifest),
        manifest_dir=resolve_project_path(args.local_file_manifest_dir),
        provider_id=args.local_file_provider_id,
        dataset_id=args.local_file_dataset_id,
        dataset_uid=args.local_file_dataset_uid,
        version=args.local_file_version,
        source_url=args.local_file_source_url,
    )
    ensure_local_file_manifest_provider(repository, result.provider_id)
    raw_asset_id = register_local_file_manifest(repository, result.manifest_path)
    if args.manual_import_json:
        print(json.dumps(local_file_manifest_payload(args, result, raw_asset_id), ensure_ascii=False, indent=2))
        return
    print(
        "[local-manifest] "
        f"wrote {result.manifest_path} file={result.payload_path} "
        f"format={result.source_format} dataset={result.dataset_id} version={result.version}"
    )
    if result.next_command:
        print(
            "[local-manifest] "
            f"next={result.next_command} --import-sqlite-db {resolve_project_path(args.import_sqlite_db)}"
        )


def import_local_file_cli(args: argparse.Namespace, repository: ApiCatalogRepository) -> None:
    if not args.import_local_file:
        return
    result = write_local_file_manifest_file(
        resolve_project_path(args.import_local_file),
        None,
        manifest_dir=resolve_project_path(args.local_file_manifest_dir),
        provider_id=args.local_file_provider_id,
        dataset_id=args.local_file_dataset_id,
        dataset_uid=args.local_file_dataset_uid,
        version=args.local_file_version,
        source_url=args.local_file_source_url,
    )
    ensure_local_file_manifest_provider(repository, result.provider_id)
    raw_asset_id = register_local_file_manifest(repository, result.manifest_path)
    # 手動匯入仍走既有 CSV/JSON importer，確保 checksum、schema fingerprint、registry asset 邊界一致。
    if result.import_kind == "csv":
        import_result = import_csv_manifest_to_sqlite(
            result.manifest_path,
            resolve_project_path(args.import_sqlite_db),
            repository,
            table_name=args.import_table,
            replace=args.import_replace_table,
            row_limit=args.import_row_limit,
        )
    elif result.import_kind == "json":
        import_result = import_json_manifest_to_sqlite(
            result.manifest_path,
            resolve_project_path(args.import_sqlite_db),
            repository,
            table_name=args.import_table,
            replace=args.import_replace_table,
            row_limit=args.import_row_limit,
        )
    else:
        raise ValueError(f"Unsupported local-file import kind for {result.source_format}: {result.payload_path}")
    if args.manual_import_json:
        print(
            json.dumps(
                local_file_import_payload(result, raw_asset_id, import_result.to_dict()),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    print(
        "[local-import] "
        f"manifest={result.manifest_path} provider={import_result.provider_id} "
        f"table={import_result.table_name} rows={import_result.rows_imported} "
        f"columns={len(import_result.columns)} sqlite={import_result.sqlite_path} "
        f"asset={import_result.table_asset_id}"
    )


def register_local_file_manifest(repository: ApiCatalogRepository, manifest_path: str | Path) -> str:
    # 手動檔案不是下載結果，但仍要登錄 raw file manifest，後續 manifest-health / repair / asset registry 才看得到它。
    return register_local_file_manifest_asset(repository, manifest_path)


def local_file_manifest_payload(args: argparse.Namespace, result, raw_asset_id: str) -> dict[str, object]:
    # 給 heartbeat/外部 agent 使用的穩定摘要：同時指出 raw file 已登記與下一個可執行匯入動作。
    return {
        "action": "write_local_file_manifest",
        "status": "ok",
        "manifest": result.as_dict(),
        "raw_asset_id": raw_asset_id,
        "raw_asset_registered": True,
        "next_action": {
            "kind": f"import_{result.import_kind}_manifest" if result.import_kind else "manual_review",
            "command": result.next_command,
            "sqlite_db": str(resolve_project_path(args.import_sqlite_db)),
        },
    }


def local_file_import_payload(result, raw_asset_id: str, import_result: dict[str, object]) -> dict[str, object]:
    # 匯入完成 payload 把 raw manifest 與 curated table 連在一起，方便後續 agent 接 database self-check。
    return {
        "action": "import_local_file",
        "status": "ok",
        "manifest": result.as_dict(),
        "raw_asset_id": raw_asset_id,
        "raw_asset_registered": True,
        "import": import_result,
        "next_action": {
            "kind": "database_self_check",
            "command": "--self-check-databases --self-check-databases-json",
        },
    }


def ensure_local_file_manifest_provider(repository: ApiCatalogRepository, provider_id: str) -> None:
    # 預設 synthetic provider 可自動建立；若使用者指定真實 provider，則要求 DB 內已有該 provider 以保護 provenance。
    if provider_id == DEFAULT_MANUAL_LOCAL_PROVIDER_ID:
        ensure_manual_local_file_provider(repository, provider_id)
        return
    if not repository.load_providers([provider_id]):
        raise ValueError(
            f"Unknown --local-file-provider-id '{provider_id}'. Run --seed for built-in providers, "
            f"or omit the flag to use {DEFAULT_MANUAL_LOCAL_PROVIDER_ID}."
        )
