from __future__ import annotations

import urllib.parse
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api_launcher.event_log import log_event
from api_launcher.manifests import AssetManifest, read_manifest, sha256_file
from api_launcher.paths import DOWNLOADS_DIR


@dataclass(frozen=True)
class ManifestVerification:
    # 驗證結果要能同時給 CLI、UI repair panel 與 agent 使用，所以保留 manifest 與 payload 脈絡。
    manifest_path: Path
    payload_path: Path
    status: str
    provider_id: str = ""
    dataset_uid: str = ""
    dataset_id: str = ""
    version: str = ""
    source_url: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def needs_repair(self) -> bool:
        return self.status in {"missing", "size_mismatch", "checksum_mismatch", "manifest_error"}

    def as_dict(self) -> dict[str, object]:
        return {
            "manifest_path": str(self.manifest_path),
            "payload_path": str(self.payload_path) if str(self.payload_path) != "." else "",
            "status": self.status,
            "provider_id": self.provider_id,
            "dataset_uid": self.dataset_uid,
            "dataset_id": self.dataset_id,
            "version": self.version,
            "source_url": self.source_url,
            "message": self.message,
            "needs_repair": self.needs_repair,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RepairSuggestion:
    # repair suggestion 只描述安全候選動作；真正 requeue 仍要由 UI/CLI 明確執行。
    action_id: str
    label: str
    description: str
    can_requeue: bool = False
    plan_entry: dict[str, object] = field(default_factory=dict)
    outcome_bucket: str = ""
    next_action: str = ""
    adapter_id: str = ""
    review_hint: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "label": self.label,
            "description": self.description,
            "can_requeue": self.can_requeue,
            "plan_entry": self.plan_entry,
            "outcome_bucket": self.outcome_bucket,
            "next_action": self.next_action,
            "adapter_id": self.adapter_id,
            "review_hint": self.review_hint,
        }


def verify_manifest_file(path: str | Path) -> ManifestVerification:
    # manifest 是下載完整性的權威來源；payload 缺失、大小、checksum 都在這裡統一判斷。
    manifest_path = Path(path)
    try:
        manifest = read_manifest(manifest_path)
    except Exception as exc:
        return ManifestVerification(
            manifest_path=manifest_path,
            payload_path=Path(""),
            status="manifest_error",
            message=f"{type(exc).__name__}: {exc}",
        )
    payload_path = Path(manifest.path)
    if not payload_path.exists():
        return _result(manifest, manifest_path, payload_path, "missing", "Payload file is missing.")
    actual_size = payload_path.stat().st_size
    if actual_size != manifest.size_bytes:
        return _result(manifest, manifest_path, payload_path, "size_mismatch", f"Expected {manifest.size_bytes}, got {actual_size}.")
    actual_hash = sha256_file(payload_path)
    if actual_hash != manifest.sha256:
        return _result(manifest, manifest_path, payload_path, "checksum_mismatch", "SHA-256 does not match manifest.")
    return _result(manifest, manifest_path, payload_path, "ok", "Payload matches manifest.")


def scan_download_manifests(root: str | Path = DOWNLOADS_DIR) -> list[ManifestVerification]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    return [verify_manifest_file(path) for path in sorted(root_path.rglob("*.manifest.json"))]


def repair_summary(results: list[ManifestVerification]) -> dict[str, int]:
    summary = {"ok": 0, "missing": 0, "size_mismatch": 0, "checksum_mismatch": 0, "manifest_error": 0}
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
    return summary


def download_repair_agent_payload(results: list[ManifestVerification]) -> dict[str, object]:
    # agent payload 把全部結果與問題結果分開，讓自動化可以只處理可重排的項目。
    result_payloads = []
    issue_payloads = []
    requeue_count = 0
    for result in results:
        suggestion = repair_suggestion_for_result(result)
        payload = {
            **result.as_dict(),
            "repair_suggestion": suggestion.as_dict(),
        }
        result_payloads.append(payload)
        if result.needs_repair:
            issue_payloads.append(payload)
        if suggestion.can_requeue:
            requeue_count += 1
    return {
        "summary": repair_summary(results),
        "checked_count": len(results),
        "issue_count": len(issue_payloads),
        "requeue_count": requeue_count,
        "issues": issue_payloads,
        "results": result_payloads,
    }


def download_manifest_verification_event_context(
    payload: dict[str, object],
    *,
    db_path: str | Path = "",
    downloads_root: str | Path = DOWNLOADS_DIR,
    issue_preview_limit: int = 20,
) -> dict[str, object]:
    checked_count = int(payload.get("checked_count") or 0)
    issue_count = int(payload.get("issue_count") or 0)
    requeue_count = int(payload.get("requeue_count") or 0)
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    issue_preview = []
    for issue in issues[:issue_preview_limit]:
        if not isinstance(issue, dict):
            continue
        suggestion = issue.get("repair_suggestion") if isinstance(issue.get("repair_suggestion"), dict) else {}
        issue_preview.append(
            {
                "status": issue.get("status", ""),
                "provider_id": issue.get("provider_id", ""),
                "dataset_id": issue.get("dataset_id", ""),
                "version": issue.get("version", ""),
                "manifest_path": issue.get("manifest_path", ""),
                "payload_path": issue.get("payload_path", ""),
                "repair_action_id": suggestion.get("action_id", ""),
                "can_requeue": bool(suggestion.get("can_requeue")),
                "repair_outcome_bucket": suggestion.get("outcome_bucket", ""),
                "repair_next_action": suggestion.get("next_action", ""),
                "adapter_id": suggestion.get("adapter_id", ""),
            }
        )
    return {
        "db_path": str(db_path) if db_path else "",
        "downloads_root": str(downloads_root) if downloads_root else "",
        "checked_count": checked_count,
        "issue_count": issue_count,
        "requeue_count": requeue_count,
        "summary": payload.get("summary", {}),
        "issue_preview_count": len(issue_preview),
        "issue_preview_limit": issue_preview_limit,
        "issues": issue_preview,
    }


def log_download_manifest_verification_completed(
    payload: dict[str, object],
    *,
    db_path: str | Path = "",
    downloads_root: str | Path = DOWNLOADS_DIR,
    logger: Callable[..., Any] = log_event,
) -> None:
    context = download_manifest_verification_event_context(
        payload,
        db_path=db_path,
        downloads_root=downloads_root,
    )
    checked_count = int(context.get("checked_count") or 0)
    issue_count = int(context.get("issue_count") or 0)
    requeue_count = int(context.get("requeue_count") or 0)
    with suppress(Exception):
        logger(
            "download_manifest_verification_completed",
            f"Download manifest verification completed: checked={checked_count} issues={issue_count} requeue={requeue_count}",
            level="warning" if issue_count else "info",
            component="download_repair",
            context=context,
        )


def download_requeue_event_context(
    result: ManifestVerification,
    suggestion: RepairSuggestion,
    *,
    outcome: str,
    job_id: str = "",
    error_type: str = "",
    error_message: str = "",
    db_path: str | Path = "",
    downloads_root: str | Path = DOWNLOADS_DIR,
) -> dict[str, object]:
    plan_entry = suggestion.plan_entry if isinstance(suggestion.plan_entry, dict) else {}
    return {
        "outcome": outcome,
        "db_path": str(db_path) if db_path else "",
        "downloads_root": str(downloads_root) if downloads_root else "",
        "provider_id": result.provider_id,
        "dataset_uid": result.dataset_uid,
        "dataset_id": result.dataset_id,
        "version": result.version,
        "status": result.status,
        "source_url": result.source_url,
        "manifest_path": str(result.manifest_path),
        "payload_path": str(result.payload_path) if str(result.payload_path) != "." else "",
        "target_path": str(plan_entry.get("target_path") or result.payload_path or ""),
        "repair_action_id": suggestion.action_id,
        "can_requeue": suggestion.can_requeue,
        "repair_outcome_bucket": suggestion.outcome_bucket,
        "repair_next_action": suggestion.next_action,
        "adapter_id": suggestion.adapter_id,
        "job_id": job_id,
        "error_type": error_type,
        "error_message": error_message,
    }


def log_download_requeue_requested(
    result: ManifestVerification,
    suggestion: RepairSuggestion,
    *,
    outcome: str,
    job_id: str = "",
    error_type: str = "",
    error_message: str = "",
    db_path: str | Path = "",
    downloads_root: str | Path = DOWNLOADS_DIR,
    logger: Callable[..., Any] = log_event,
) -> None:
    level = "info" if outcome == "queued" else "error" if outcome == "failed" else "warning"
    context = download_requeue_event_context(
        result,
        suggestion,
        outcome=outcome,
        job_id=job_id,
        error_type=error_type,
        error_message=error_message,
        db_path=db_path,
        downloads_root=downloads_root,
    )
    provider_id = result.provider_id or str(suggestion.plan_entry.get("provider_id") or "-")
    with suppress(Exception):
        logger(
            "download_repair_requeue_requested",
            f"Download repair requeue {outcome}: {provider_id}",
            level=level,
            component="download_repair",
            context=context,
        )


def repair_suggestion_for_result(result: ManifestVerification) -> RepairSuggestion:
    adapter_hint = _adapter_repair_hint(result)
    adapter_id = str(adapter_hint.get("adapter_id") or "")
    if result.status == "ok":
        return RepairSuggestion(
            "none",
            "No action needed",
            "Payload matches its sidecar manifest.",
            outcome_bucket="healthy",
            next_action="none",
        )
    if result.status == "manifest_error":
        return RepairSuggestion(
            "inspect_manifest",
            "Inspect manifest",
            "The manifest could not be parsed, so the launcher cannot safely infer a source URL or target path.",
            outcome_bucket="manifest_parse_error",
            next_action="inspect_manifest",
        )
    if not result.needs_repair:
        return RepairSuggestion(
            "inspect",
            "Inspect status",
            "No automatic repair rule is available for this status.",
            outcome_bucket="unsupported_status",
            next_action="inspect_status",
        )
    if not result.source_url:
        if adapter_id:
            return RepairSuggestion(
                "adapter_repair_review",
                "Review adapter repair",
                f"The manifest does not record a source URL; review or rerun adapter output for {adapter_id} before requeue.",
                outcome_bucket="adapter_source_missing",
                next_action="run_adapter_review_or_resolve_adapter_plan",
                adapter_id=adapter_id,
                review_hint=adapter_hint,
            )
        return RepairSuggestion(
            "manual_recover",
            "Manual recovery needed",
            "The manifest does not record a source URL, so the launcher cannot safely requeue this download.",
            outcome_bucket="source_url_missing",
            next_action="inspect_manifest_or_recreate_plan",
        )
    if not _is_requeue_source_url(result.source_url):
        if adapter_id:
            return RepairSuggestion(
                "adapter_repair_review",
                "Review adapter repair",
                f"The recorded source URL is not an HTTP(S) download URL; adapter {adapter_id} must decide the safe recovery path.",
                outcome_bucket="adapter_source_not_requeueable",
                next_action="run_adapter_specific_repair_or_export_review",
                adapter_id=adapter_id,
                review_hint=adapter_hint,
            )
        return RepairSuggestion(
            "manual_recover",
            "Manual recovery needed",
            f"The recorded source URL is not an HTTP(S) download URL: {result.source_url}",
            outcome_bucket="source_url_not_requeueable",
            next_action="inspect_source_url_or_recreate_plan",
        )
    if not result.provider_id:
        return RepairSuggestion(
            "manual_recover",
            "Manual recovery needed",
            "The manifest does not record a provider_id, so the download queue cannot safely own the job.",
            outcome_bucket="provider_id_missing",
            next_action="inspect_manifest_or_recreate_plan",
        )

    plan_entry: dict[str, object] = {
        "provider_id": result.provider_id,
        "dataset_uid": result.dataset_uid,
        "dataset_id": result.dataset_id,
        "version": result.version,
        "download_url": result.source_url,
        "target_path": str(result.payload_path),
        "use_staging": True,
        "repair_status": result.status,
        "repair_manifest_path": str(result.manifest_path),
    }
    if result.dataset_uid or result.dataset_id or result.version:
        plan_entry["dataset_version"] = {
            "dataset_uid": result.dataset_uid,
            "dataset_id": result.dataset_id,
            "version": result.version,
            "download_url": result.source_url,
            "metadata": {"repair_status": result.status},
        }

    return RepairSuggestion(
        "requeue_download",
        "Requeue download",
        "Safely re-download through staging, then atomically promote the payload after the transfer completes.",
        can_requeue=True,
        plan_entry=plan_entry,
        outcome_bucket="requeue_ready",
        next_action="requeue_download",
        adapter_id=adapter_id,
        review_hint=adapter_hint,
    )


def _result(
    manifest: AssetManifest,
    manifest_path: Path,
    payload_path: Path,
    status: str,
    message: str,
) -> ManifestVerification:
    return ManifestVerification(
        manifest_path=manifest_path,
        payload_path=payload_path,
        status=status,
        provider_id=manifest.provider_id,
        dataset_uid=manifest.dataset_uid,
        dataset_id=manifest.dataset_id,
        version=manifest.version,
        source_url=manifest.source_url,
        message=message,
        metadata=dict(manifest.metadata),
    )


def _is_requeue_source_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _adapter_repair_hint(result: ManifestVerification) -> dict[str, object]:
    # manifest metadata 可能保留 adapter_review / adapter_resolution 線索；修復層只回報線索，不自行執行 adapter。
    metadata = result.metadata if isinstance(result.metadata, dict) else {}
    review = metadata.get("adapter_review") if isinstance(metadata.get("adapter_review"), dict) else {}
    resolution = metadata.get("adapter_resolution") if isinstance(metadata.get("adapter_resolution"), dict) else {}
    adapter_id = str(
        review.get("adapter_id")
        or resolution.get("adapter_id")
        or metadata.get("adapter_id")
        or metadata.get("adapter")
        or ""
    )
    if not adapter_id:
        return {}
    return {
        "adapter_id": adapter_id,
        "required_action": str(review.get("required_action") or resolution.get("policy") or metadata.get("required_action") or ""),
        "outcome_bucket": str(review.get("outcome_bucket") or metadata.get("outcome_bucket") or ""),
        "source_kind": str(review.get("source_kind") or metadata.get("source_kind") or ""),
        "source_url": result.source_url,
        "manifest_path": str(result.manifest_path),
    }
