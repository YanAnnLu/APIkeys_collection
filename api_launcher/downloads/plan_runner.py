from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from api_launcher.downloads.jobs import JobStatus, NonBlockingDownloadQueue, ProgressCallback
from api_launcher.downloads.policy import PoliteDownloadPolicy
from api_launcher.downloads.http import HTTPDownloadAdapter, download_target_from_plan_entry
from api_launcher.importers.archive_importer import (
    CSV_MEMBER_SOURCE_FORMATS,
    JSON_MEMBER_SOURCE_FORMATS,
    extract_first_supported_member_manifest,
)
from api_launcher.importers.csv_importer import import_csv_manifest_to_sqlite, table_exists, table_name_for_manifest, unique_table_name
from api_launcher.importers.json_importer import import_json_manifest_to_sqlite
from api_launcher.manifests import read_manifest
from api_launcher.downloads.repair import verify_manifest_file
from api_launcher.paths import default_local_curated_db_path
from api_launcher.repository import ApiCatalogRepository


@dataclass(frozen=True)
class DownloadPlanRunResult:
    # runner result 要同時回報下載與匯入狀態，讓 CLI/UI 不必解析 log 才知道結果。
    entry_count: int
    submitted: int
    completed: int
    failed: int
    skipped: int
    registered_assets: int
    imported: int = 0
    import_skipped: int = 0
    import_failed: int = 0
    skip_summary: dict[str, int] = field(default_factory=dict)
    errors: tuple[str, ...] = field(default_factory=tuple)
    callback_errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_count": self.entry_count,
            "submitted": self.submitted,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "registered_assets": self.registered_assets,
            "imported": self.imported,
            "import_skipped": self.import_skipped,
            "import_failed": self.import_failed,
            "skip_summary": dict(self.skip_summary),
            "errors": list(self.errors),
            "callback_errors": list(self.callback_errors),
        }


def load_download_plan_file(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Download plan JSON must be an object.")
    return data


def plan_entries(plan_payload: dict[str, Any]) -> list[dict[str, object]]:
    # 舊 schema 把 entries 放在 providers 欄位；這裡集中相容，避免呼叫端重複判斷。
    raw_entries = plan_payload.get("providers") or []
    if not isinstance(raw_entries, list):
        raise ValueError("Download plan must contain a providers list.")
    return [dict(entry) for entry in raw_entries if isinstance(entry, dict)]


def is_direct_download_entry(entry: dict[str, object]) -> bool:
    url = str(entry.get("download_url") or "").strip()
    if not url:
        return False
    eligibility = entry.get("download_eligibility")
    if isinstance(eligibility, dict):
        status = str(eligibility.get("status") or "").strip()
        if status and status != "direct_download":
            return False
    return True


def direct_download_entries(entries: Iterable[dict[str, object]], limit: int = 0) -> list[dict[str, object]]:
    selected = [entry for entry in entries if is_direct_download_entry(entry)]
    if limit > 0:
        return selected[:limit]
    return selected


SKIP_BUCKET_ORDER = (
    "adapter_required",
    "metadata_only",
    "unavailable",
    "missing_download_url",
    "not_direct",
)


def download_entry_skip_bucket(entry: dict[str, object]) -> str:
    if is_direct_download_entry(entry):
        return ""
    eligibility = entry.get("download_eligibility")
    status = str(eligibility.get("status") if isinstance(eligibility, dict) else "").strip()
    url = str(entry.get("download_url") or "").strip()
    if status == "adapter_required" or isinstance(entry.get("adapter_review"), dict):
        # 這類 skipped 不是失敗，而是尚未被 resolver/adapter 轉成可界定的小下載。
        return "adapter_required"
    if status == "metadata_only":
        return "metadata_only"
    if status == "unavailable":
        return "unavailable"
    if not url:
        return "missing_download_url"
    return "not_direct"


def download_skip_summary(entries: Iterable[dict[str, object]]) -> dict[str, int]:
    # skipped 必須說明原因；否則 UI/CLI 會讓使用者誤以為下載按鈕沒有實作。
    summary: dict[str, int] = {}
    for entry in entries:
        bucket = download_entry_skip_bucket(entry)
        if not bucket:
            continue
        summary[bucket] = summary.get(bucket, 0) + 1
    return {bucket: summary[bucket] for bucket in SKIP_BUCKET_ORDER if summary.get(bucket)}


def format_download_skip_summary(summary: dict[str, int]) -> str:
    return " ".join(f"{bucket}={summary[bucket]}" for bucket in SKIP_BUCKET_ORDER if summary.get(bucket))


def run_download_plan_payload(
    plan_payload: dict[str, Any],
    repository: ApiCatalogRepository,
    policy: PoliteDownloadPolicy | None = None,
    timeout: float = 30.0,
    limit: int = 0,
    import_supported_results: bool = False,
    import_sqlite_path: str | Path = default_local_curated_db_path(),
    import_row_limit: int = 0,
    import_replace: bool = False,
    import_existing_table_policy: str = "skip",
    progress_callback: ProgressCallback | None = None,
) -> DownloadPlanRunResult:
    # runner 只處理 direct download entries；adapter review 項目必須先由 resolver 轉成可下載項。
    entries = plan_entries(plan_payload)
    selected = direct_download_entries(entries, limit=limit)
    skip_summary = download_skip_summary(entries)
    skipped = sum(skip_summary.values())
    if not selected:
        return DownloadPlanRunResult(
            entry_count=len(entries),
            submitted=0,
            completed=0,
            failed=0,
            skipped=skipped,
            registered_assets=0,
            skip_summary=skip_summary,
        )

    active_policy = policy or PoliteDownloadPolicy()
    queue = NonBlockingDownloadQueue(
        HTTPDownloadAdapter(timeout=timeout, policy=active_policy),
        max_workers=active_policy.max_parallel_jobs,
    )
    if progress_callback is not None:
        # 展示模式與未來 UI 需要使用 downloader 實際 bytes_done/bytes_total；
        # callback 只讀取進度，不改變 queue 的執行與錯誤語意。
        queue.add_callback(progress_callback)
    jobs = []
    errors: list[str] = []
    completed = 0
    failed = 0
    registered_assets = 0
    imported = 0
    import_skipped = 0
    import_failed = 0
    callback_errors: tuple[str, ...] = ()
    try:
        for entry in selected:
            jobs.append((queue.submit(entry), entry))
        for job, entry in jobs:
            queue.wait(job.job_id)
            final = queue.snapshot(job.job_id)
            if final.status != JobStatus.COMPLETED:
                failed += 1
                errors.append(f"{job.provider_id}: {final.error or final.message}")
                continue
            try:
                registration = register_completed_plan_entry(repository, entry)
            except Exception as exc:
                failed += 1
                errors.append(f"{job.provider_id}: {type(exc).__name__}: {exc}")
                continue
            if registration:
                completed += 1
                registered_assets += 1
                if import_supported_results:
                    import_result = import_completed_plan_entry(
                        repository,
                        entry,
                        registration,
                        sqlite_path=import_sqlite_path,
                        row_limit=import_row_limit,
                        replace=import_replace,
                        existing_table_policy=import_existing_table_policy,
                    )
                    if import_result == "imported":
                        imported += 1
                    elif import_result.startswith("skipped"):
                        import_skipped += 1
                    else:
                        import_failed += 1
                        errors.append(f"{job.provider_id}: import failed for {registration}: {import_result}")
            else:
                failed += 1
                errors.append(f"{job.provider_id}: completed download did not produce a healthy manifest")
    finally:
        callback_errors = tuple(
            f"{item.job_id} {item.callback_name}: {item.error}"
            for item in queue.callback_error_snapshot()
        )
        queue.shutdown()

    return DownloadPlanRunResult(
        entry_count=len(entries),
        submitted=len(selected),
        completed=completed,
        failed=failed,
        skipped=skipped,
        registered_assets=registered_assets,
        imported=imported,
        import_skipped=import_skipped,
        import_failed=import_failed,
        skip_summary=skip_summary,
        errors=tuple(errors),
        callback_errors=callback_errors,
    )


def register_completed_plan_entry(repository: ApiCatalogRepository, entry: dict[str, object]) -> Path | None:
    target = download_target_from_plan_entry(entry)
    manifest_path = target.output_path.with_suffix(target.output_path.suffix + ".manifest.json")
    verification = verify_manifest_file(manifest_path)
    if verification.status != "ok":
        return None
    manifest = read_manifest(manifest_path)
    repository.upsert_dataset_asset_manifest(manifest, manifest_path, status="ok")
    repository.register_downloaded_manifest_asset(manifest, manifest_path)
    return manifest_path


def import_completed_plan_entry(
    repository: ApiCatalogRepository,
    entry: dict[str, object],
    manifest_path: str | Path,
    sqlite_path: str | Path,
    row_limit: int = 0,
    replace: bool = False,
    existing_table_policy: str = "skip",
) -> str:
    import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
    if import_plan.get("status") == "requires_unpack_or_adapter":
        try:
            extracted = extract_first_supported_member_manifest(manifest_path)
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        entry = dict(entry)
        import_plan = dict(import_plan)
        if extracted.source_format in CSV_MEMBER_SOURCE_FORMATS:
            import_plan["status"] = "supported_after_download"
            import_plan["importer"] = "csv_to_sqlite"
        elif extracted.source_format in JSON_MEMBER_SOURCE_FORMATS:
            import_plan["status"] = "supported_after_download"
            import_plan["importer"] = "json_to_sqlite"
        else:
            return "skipped"
        entry["import_plan"] = import_plan
        manifest_path = extracted.manifest_path
    if import_plan.get("status") != "supported_after_download":
        return "skipped"
    importer = str(import_plan.get("importer") or "").strip()
    table_name = str(import_plan.get("table_hint") or "").strip()
    try:
        policy = normalized_existing_table_policy(existing_table_policy, replace=replace)
        manifest = read_manifest(manifest_path)
        resolved_table_name = table_name or table_name_for_manifest(manifest)
        if policy == "skip" and table_exists(sqlite_path, resolved_table_name):
            return "skipped_existing_table"
        if policy == "rename":
            table_name = unique_table_name(sqlite_path, resolved_table_name)
        replace_table = policy == "replace"
        if importer == "csv_to_sqlite":
            import_csv_manifest_to_sqlite(
                manifest_path,
                sqlite_path,
                repository,
                table_name=table_name,
                replace=replace_table,
                row_limit=row_limit,
            )
            return "imported"
        if importer == "json_to_sqlite":
            import_json_manifest_to_sqlite(
                manifest_path,
                sqlite_path,
                repository,
                table_name=table_name,
                replace=replace_table,
                row_limit=row_limit,
            )
            return "imported"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return "skipped"


def normalized_existing_table_policy(policy: str, replace: bool = False) -> str:
    if replace:
        return "replace"
    normalized = str(policy or "skip").strip().lower()
    if normalized not in {"skip", "rename", "replace"}:
        raise ValueError(f"Unsupported existing-table import policy: {policy}")
    return normalized
