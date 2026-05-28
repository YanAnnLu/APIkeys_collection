from __future__ import annotations

import argparse
import json
from typing import Callable

from api_launcher.db import resolve_project_path
from api_launcher.downloads.plan_runner import load_download_plan_file
from api_launcher.ingestion_pipeline import (
    DownloadImportPipelineOptions,
    render_download_import_cli_lines,
    run_download_import_slice,
)
from api_launcher.integrations import active_download_policy
from api_launcher.repository import ApiCatalogRepository

LogEvent = Callable[..., None]


def download_plan_command_active(args: argparse.Namespace) -> bool:
    # 保留既有 cli_flags 行為：JSON/匯入附屬旗標單獨出現時，也不要退回預設 init/seed。
    return bool(args.run_download_plan or args.run_download_plan_json or args.import_supported_plan_results)


def run_download_plan_cli(args: argparse.Namespace, repository: ApiCatalogRepository, log_event_func: LogEvent) -> None:
    if not args.run_download_plan:
        return
    input_path = resolve_project_path(args.run_download_plan)
    payload = load_download_plan_file(input_path)
    run = run_download_import_slice(
        payload,
        repository,
        DownloadImportPipelineOptions(
            policy=active_download_policy(),
            timeout=args.download_timeout,
            limit=args.download_plan_limit,
            import_supported_results=args.import_supported_plan_results,
            import_sqlite_path=resolve_project_path(args.import_sqlite_db),
            import_row_limit=args.import_row_limit,
            import_replace=args.import_replace_table,
            import_existing_table_policy=args.plan_import_existing_table_policy,
        ),
    )
    # 下載計畫執行是 MVP 閉環的核心動作；留下 structured event 讓 handoff/agent 不必重跑或翻文字輸出。
    log_event_func(
        "download_plan_executed",
        "Executed download plan pipeline slice.",
        component="download_plan",
        context={
            "input_plan": str(input_path),
            "stage": run.stage,
            "next_action": run.next_action,
            "import_requested": run.import_requested,
            "entry_count": run.result.entry_count,
            "submitted": run.result.submitted,
            "completed": run.result.completed,
            "failed": run.result.failed,
            "skipped": run.result.skipped,
            "registered_assets": run.result.registered_assets,
            "imported": run.result.imported,
            "import_skipped": run.result.import_skipped,
            "import_failed": run.result.import_failed,
            "skip_summary": run.result.skip_summary,
            "error_count": len(run.result.errors),
            "callback_error_count": len(run.result.callback_errors),
            # Callback errors are observer/UI diagnostics. Keep a bounded
            # preview in event logs so handoff can flag them without turning a
            # successful download into a failed pipeline run.
            "callback_errors": list(run.result.callback_errors[:5]),
        },
    )
    if args.run_download_plan_json:
        # JSON mode 是 heartbeat/agent 的穩定交接格式；人類 CLI 摘要維持在預設路徑。
        print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
        return
    for line in render_download_import_cli_lines(run):
        print(line)
