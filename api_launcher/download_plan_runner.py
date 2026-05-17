from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from api_launcher.download_jobs import JobStatus, NonBlockingDownloadQueue
from api_launcher.download_policy import PoliteDownloadPolicy
from api_launcher.http_downloader import HTTPDownloadAdapter, download_target_from_plan_entry
from api_launcher.manifests import read_manifest
from api_launcher.repair import verify_manifest_file
from api_launcher.repository import ApiCatalogRepository


@dataclass(frozen=True)
class DownloadPlanRunResult:
    entry_count: int
    submitted: int
    completed: int
    failed: int
    skipped: int
    registered_assets: int
    errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_count": self.entry_count,
            "submitted": self.submitted,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "registered_assets": self.registered_assets,
            "errors": list(self.errors),
        }


def load_download_plan_file(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Download plan JSON must be an object.")
    return data


def plan_entries(plan_payload: dict[str, Any]) -> list[dict[str, object]]:
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


def run_download_plan_payload(
    plan_payload: dict[str, Any],
    repository: ApiCatalogRepository,
    policy: PoliteDownloadPolicy | None = None,
    timeout: float = 30.0,
    limit: int = 0,
) -> DownloadPlanRunResult:
    entries = plan_entries(plan_payload)
    selected = direct_download_entries(entries, limit=limit)
    skipped = len(entries) - len(selected)
    if not selected:
        return DownloadPlanRunResult(
            entry_count=len(entries),
            submitted=0,
            completed=0,
            failed=0,
            skipped=skipped,
            registered_assets=0,
        )

    active_policy = policy or PoliteDownloadPolicy()
    queue = NonBlockingDownloadQueue(
        HTTPDownloadAdapter(timeout=timeout, policy=active_policy),
        max_workers=active_policy.max_parallel_jobs,
    )
    jobs = []
    errors: list[str] = []
    completed = 0
    failed = 0
    registered_assets = 0
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
            else:
                failed += 1
                errors.append(f"{job.provider_id}: completed download did not produce a healthy manifest")
    finally:
        queue.shutdown()

    return DownloadPlanRunResult(
        entry_count=len(entries),
        submitted=len(selected),
        completed=completed,
        failed=failed,
        skipped=skipped,
        registered_assets=registered_assets,
        errors=tuple(errors),
    )


def register_completed_plan_entry(repository: ApiCatalogRepository, entry: dict[str, object]) -> bool:
    target = download_target_from_plan_entry(entry)
    manifest_path = target.output_path.with_suffix(target.output_path.suffix + ".manifest.json")
    verification = verify_manifest_file(manifest_path)
    if verification.status != "ok":
        return False
    manifest = read_manifest(manifest_path)
    repository.upsert_dataset_asset_manifest(manifest, manifest_path, status="ok")
    repository.register_downloaded_manifest_asset(manifest, manifest_path)
    return True
