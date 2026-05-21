from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api_launcher.downloads.plan_runner import (
    DownloadPlanRunResult,
    format_download_skip_summary,
    run_download_plan_payload,
)
from api_launcher.downloads.policy import PoliteDownloadPolicy
from api_launcher.repository import ApiCatalogRepository


DOWNLOAD_BLOCKED_NEXT_ACTION = "run_adapter_review_or_resolve_adapter_plan_before_downloading"


@dataclass(frozen=True)
class DownloadImportPipelineOptions:
    # 這個 options 物件先承接既有 CLI flags；之後 UI 可直接傳同一組選項，不必複製 core.py 參數映射。
    policy: PoliteDownloadPolicy | None = None
    timeout: float = 30.0
    limit: int = 0
    import_supported_results: bool = False
    import_sqlite_path: str | Path = "state/curated_imports.sqlite"
    import_row_limit: int = 0
    import_replace: bool = False
    import_existing_table_policy: str = "skip"


@dataclass(frozen=True)
class DownloadImportPipelineRun:
    # stage 是給 UI/agent 讀的穩定狀態，不讓呼叫端靠 submitted/failed/imported 自己猜流程卡在哪。
    result: DownloadPlanRunResult
    stage: str
    import_requested: bool
    next_action: str = ""

    @property
    def blocked(self) -> bool:
        return self.stage == "blocked_before_download"

    @property
    def failed(self) -> bool:
        return self.stage == "failed"

    @property
    def succeeded(self) -> bool:
        return self.stage in {"download_completed", "download_import_completed", "download_completed_import_skipped"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "import_requested": self.import_requested,
            "next_action": self.next_action,
            "blocked": self.blocked,
            "failed": self.failed,
            "succeeded": self.succeeded,
            "result": self.result.to_dict(),
        }


def run_download_import_slice(
    plan_payload: dict[str, Any],
    repository: ApiCatalogRepository,
    options: DownloadImportPipelineOptions | None = None,
) -> DownloadImportPipelineRun:
    # 第一個 pipeline slice 只包住已驗證的 direct download/import 路徑；不把 crawler/resolver 強行塞進抽象。
    active_options = options or DownloadImportPipelineOptions()
    result = run_download_plan_payload(
        plan_payload,
        repository,
        policy=active_options.policy,
        timeout=active_options.timeout,
        limit=active_options.limit,
        import_supported_results=active_options.import_supported_results,
        import_sqlite_path=active_options.import_sqlite_path,
        import_row_limit=active_options.import_row_limit,
        import_replace=active_options.import_replace,
        import_existing_table_policy=active_options.import_existing_table_policy,
    )
    return DownloadImportPipelineRun(
        result=result,
        stage=classify_download_import_stage(result, import_requested=active_options.import_supported_results),
        import_requested=active_options.import_supported_results,
        next_action=download_import_next_action(result),
    )


def classify_download_import_stage(result: DownloadPlanRunResult, import_requested: bool) -> str:
    # 這些 stage 名稱刻意偏產品語意，讓 UI/agent 後續可以直接顯示或路由，不必懂 runner 內部細節。
    if result.entry_count == 0:
        return "empty_plan"
    if result.submitted == 0 and result.skipped:
        return "blocked_before_download"
    if result.failed or result.import_failed:
        return "failed"
    if import_requested and result.imported:
        return "download_import_completed"
    if import_requested and result.import_skipped:
        return "download_completed_import_skipped"
    if result.completed:
        return "download_completed"
    return "no_work_completed"


def download_import_next_action(result: DownloadPlanRunResult) -> str:
    if result.submitted == 0 and result.skipped:
        return DOWNLOAD_BLOCKED_NEXT_ACTION
    return ""


def render_download_import_cli_lines(run: DownloadImportPipelineRun) -> list[str]:
    # CLI 文字集中在 service 層產生，避免 core.py 和未來 subcommands 各自維護一套摘要格式。
    result = run.result
    lines = [
        "[download-plan] "
        f"entries={result.entry_count} submitted={result.submitted} "
        f"completed={result.completed} failed={result.failed} "
        f"skipped={result.skipped} registered_assets={result.registered_assets} "
        f"imported={result.imported} import_skipped={result.import_skipped} import_failed={result.import_failed}"
    ]
    skip_detail = format_download_skip_summary(result.skip_summary)
    if skip_detail:
        lines.append(f"[download-plan] skip_summary {skip_detail}")
    if run.next_action:
        lines.append(f"[download-plan] next_action={run.next_action}")
    lines.extend(f"[download-plan] error {error}" for error in result.errors)
    return lines
