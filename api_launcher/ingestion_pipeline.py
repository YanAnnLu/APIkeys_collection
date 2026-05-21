from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api_launcher.downloads.plan_runner import (
    DownloadPlanRunResult,
    direct_download_entries,
    format_download_skip_summary,
    download_skip_summary,
    import_completed_plan_entry,
    normalized_existing_table_policy,
    plan_entries,
    register_completed_plan_entry,
    run_download_plan_payload,
)
from api_launcher.downloads.policy import PoliteDownloadPolicy
from api_launcher.downloads.http import download_target_from_plan_entry
from api_launcher.downloads.repair import verify_manifest_file
from api_launcher.importers.csv_importer import unique_table_name
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
class DownloadImportPipelineItemStatus:
    # UI 需要逐列回填狀態；index 對應輸入 plan 裡第幾個 entry，避免 service 認識 Tk 的 plan_key。
    index: int
    provider_id: str
    dataset_id: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "provider_id": self.provider_id,
            "dataset_id": self.dataset_id,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DownloadImportPipelineRun:
    # stage 是給 UI/agent 讀的穩定狀態，不讓呼叫端靠 submitted/failed/imported 自己猜流程卡在哪。
    result: DownloadPlanRunResult
    stage: str
    import_requested: bool
    next_action: str = ""
    item_statuses: tuple[DownloadImportPipelineItemStatus, ...] = ()

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
            "item_statuses": [item.to_dict() for item in self.item_statuses],
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


def run_existing_download_import_slice(
    plan_payload: dict[str, Any],
    repository: ApiCatalogRepository,
    options: DownloadImportPipelineOptions | None = None,
) -> DownloadImportPipelineRun:
    # 這條路徑服務 Tk「匯入已下載結果」：只檢查既有 manifest 並匯入，不重新下載檔案。
    active_options = options or DownloadImportPipelineOptions(import_supported_results=True)
    entries = plan_entries(plan_payload)
    selected = direct_download_entries(entries, limit=active_options.limit)
    skip_summary = download_skip_summary(entries)
    skipped = sum(skip_summary.values())
    completed = 0
    registered_assets = 0
    imported = 0
    import_skipped = 0
    import_failed = 0
    errors: list[str] = []
    item_statuses: list[DownloadImportPipelineItemStatus] = []

    for index, entry in enumerate(selected, start=1):
        provider_id = str(entry.get("provider_id") or f"entry_{index}")
        dataset_id = str(entry.get("dataset_id") or entry.get("dataset_uid") or "")
        try:
            target = download_target_from_plan_entry(entry)
            manifest_path = target.output_path.with_suffix(target.output_path.suffix + ".manifest.json")
            verification = verify_manifest_file(manifest_path)
            if verification.status != "ok":
                # manifest 是 raw 檔案進 curated SQLite 的安全閘門；不健康就只回報，不做猜測匯入。
                import_skipped += 1
                detail = f"manifest {verification.status} {verification.message}".strip()
                item_statuses.append(DownloadImportPipelineItemStatus(index, provider_id, dataset_id, "skipped", detail))
                continue

            registered_manifest = register_completed_plan_entry(repository, entry)
            if not registered_manifest:
                import_skipped += 1
                detail = "completed download did not produce a healthy manifest"
                item_statuses.append(DownloadImportPipelineItemStatus(index, provider_id, dataset_id, "skipped", detail))
                continue

            completed += 1
            registered_assets += 1
            prepared_entry, display_table = prepare_import_entry_for_existing_table_policy(
                entry,
                active_options.import_sqlite_path,
                active_options.import_existing_table_policy,
                replace=active_options.import_replace,
            )
            import_result = import_completed_plan_entry(
                repository,
                prepared_entry,
                registered_manifest,
                sqlite_path=active_options.import_sqlite_path,
                row_limit=active_options.import_row_limit,
                replace=active_options.import_replace,
                existing_table_policy=active_options.import_existing_table_policy,
            )
        except Exception as exc:
            import_failed += 1
            detail = f"{type(exc).__name__}: {exc}"
            errors.append(f"{provider_id}: {detail}")
            item_statuses.append(DownloadImportPipelineItemStatus(index, provider_id, dataset_id, "failed", detail))
            continue

        if import_result == "imported":
            imported += 1
            item_statuses.append(DownloadImportPipelineItemStatus(index, provider_id, dataset_id, "imported", display_table))
        elif import_result.startswith("skipped"):
            import_skipped += 1
            item_statuses.append(DownloadImportPipelineItemStatus(index, provider_id, dataset_id, "skipped", import_result))
        else:
            import_failed += 1
            errors.append(f"{provider_id}: import failed for {registered_manifest}: {import_result}")
            item_statuses.append(DownloadImportPipelineItemStatus(index, provider_id, dataset_id, "failed", import_result))

    result = DownloadPlanRunResult(
        entry_count=len(entries),
        submitted=len(selected),
        completed=completed,
        failed=0,
        skipped=skipped,
        registered_assets=registered_assets,
        imported=imported,
        import_skipped=import_skipped,
        import_failed=import_failed,
        skip_summary=skip_summary,
        errors=tuple(errors),
    )
    return DownloadImportPipelineRun(
        result=result,
        stage=classify_existing_download_import_stage(result),
        import_requested=True,
        next_action=download_import_next_action(result),
        item_statuses=tuple(item_statuses),
    )


def prepare_import_entry_for_existing_table_policy(
    entry: dict[str, object],
    sqlite_path: str | Path,
    existing_table_policy: str,
    replace: bool = False,
) -> tuple[dict[str, object], str]:
    # rename 的實際 table 名稱要在 service 層決定，UI 才不用複製資料表命名規則。
    import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
    table_hint = str(import_plan.get("table_hint") or "").strip()
    if normalized_existing_table_policy(existing_table_policy, replace=replace) != "rename" or not table_hint:
        return entry, table_hint
    resolved_table = unique_table_name(sqlite_path, table_hint)
    if resolved_table == table_hint:
        return entry, resolved_table
    prepared_entry = dict(entry)
    prepared_plan = dict(import_plan)
    prepared_plan["table_hint"] = resolved_table
    prepared_entry["import_plan"] = prepared_plan
    return prepared_entry, resolved_table


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


def classify_existing_download_import_stage(result: DownloadPlanRunResult) -> str:
    # import-only stage 與下載 stage 分開判斷，避免 manifest 缺失被誤寫成 download completed。
    if result.entry_count == 0:
        return "empty_plan"
    if result.submitted == 0 and result.skipped:
        return "blocked_before_download"
    if result.import_failed:
        return "failed"
    if result.imported:
        return "download_import_completed"
    if result.import_skipped:
        return "import_skipped"
    if result.registered_assets:
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
