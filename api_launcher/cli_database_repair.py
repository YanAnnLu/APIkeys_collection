from __future__ import annotations

import argparse
import contextlib
import json
from pathlib import Path
from typing import Callable

from api_launcher.database_repair import (
    database_repair_sql_path_for_asset,
    reimport_missing_sqlite_table_asset,
    stop_tracking_database_asset,
    write_missing_sql_table_repair_dry_run,
)
from api_launcher.db import resolve_project_path
from api_launcher.repository import ApiCatalogRepository

LogEvent = Callable[..., None]


def database_repair_command_active(args: argparse.Namespace) -> bool:
    # 保留舊版 cli_flags 行為：--database-repair-json 即使單獨出現，也只讓 CLI 不走預設 init/seed。
    return bool(
        args.reimport_missing_sqlite_table
        or args.unmanage_database_asset
        or args.write_database_repair_sql
        or args.database_repair_json
    )


def run_database_repairs(
    args: argparse.Namespace,
    repository: ApiCatalogRepository,
    db_path: str | Path,
    log_event_func: LogEvent,
) -> None:
    reimport_asset_ids = tuple(asset_id.strip() for asset_id in args.reimport_missing_sqlite_table if asset_id.strip())
    unmanage_asset_ids = tuple(asset_id.strip() for asset_id in args.unmanage_database_asset if asset_id.strip())
    sql_dry_run_asset_ids = tuple(asset_id.strip() for asset_id in args.write_database_repair_sql if asset_id.strip())
    if not reimport_asset_ids and not unmanage_asset_ids and not sql_dry_run_asset_ids:
        return

    result_payloads: list[dict[str, object]] = []
    actions: list[str] = []

    def remember_action(action_id: str) -> None:
        # 同一個命令可批次處理多個 asset；action 列表只保留唯一值，方便 handoff/event 摘要。
        if action_id not in actions:
            actions.append(action_id)

    for asset_id in reimport_asset_ids:
        result = reimport_missing_sqlite_table_asset(repository, asset_id)
        result_payloads.append(result.to_dict())
        remember_action(result.action_id)
        if not args.database_repair_json:
            print(
                "[database-repair] "
                f"action={result.action_id} asset_id={result.asset_id} "
                f"provider={result.provider_id} table={result.table_name} "
                f"rows={result.rows_imported} sqlite={result.sqlite_path}"
            )

    for asset_id in unmanage_asset_ids:
        result = stop_tracking_database_asset(repository, asset_id)
        result_payloads.append(result.to_dict())
        remember_action(result.action_id)
        if not args.database_repair_json:
            print(
                "[database-repair] "
                f"action={result.action_id} asset_id={result.asset_id} "
                f"provider={result.provider_id} asset={result.asset_kind}:{result.engine}:{result.asset_name} "
                f"status={result.status} database_modified={str(result.database_modified).lower()}"
            )

    for asset_id in sql_dry_run_asset_ids:
        # 非 SQLite 修復只寫 SQL 草稿；實際執行必須由使用者/DBA 審核後手動進行。
        output_path = database_repair_sql_path(asset_id, args)
        result = write_missing_sql_table_repair_dry_run(
            repository,
            asset_id,
            output_path,
            row_limit=args.database_repair_sql_row_limit,
        )
        result_payloads.append(result.to_dict())
        remember_action(result.action_id)
        if not args.database_repair_json:
            print(
                "[database-repair] "
                f"action={result.action_id} asset_id={result.asset_id} "
                f"provider={result.provider_id} table={result.table_name} "
                f"rows={result.rows_planned} sql={result.sql_path} dry_run=true"
            )

    action = actions[0] if len(actions) == 1 else "database_repair"
    if args.database_repair_json:
        payload = {
            "schema_version": 1,
            "action": action,
            "result_count": len(result_payloads),
            "results": result_payloads,
        }
        log_database_repair_completed(db_path, action, result_payloads, log_event_func)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        log_database_repair_completed(db_path, action, result_payloads, log_event_func)


def database_repair_sql_path(asset_id: str, args: argparse.Namespace) -> Path:
    # 路徑正規化交給 database_repair 共用 helper，讓 CLI 與 UI 產生完全相同的 dry-run 檔名。
    output_dir = resolve_project_path(args.database_repair_sql_dir)
    return database_repair_sql_path_for_asset(asset_id, output_dir)


def log_database_repair_completed(
    db_path: str | Path,
    action: str,
    results: list[dict[str, object]],
    log_event_func: LogEvent,
) -> None:
    if not results:
        return
    # 事件紀錄不應讓 repair 主命令失敗；log_event 失敗只代表觀測性遺失，不代表資料修復失敗。
    with contextlib.suppress(Exception):
        log_event_func(
            "database_repair_completed",
            f"Database repair completed: {action}",
            component="database_repair",
            context={
                "db_path": str(db_path),
                "action": action,
                "result_count": len(results),
                "results": results,
            },
        )
