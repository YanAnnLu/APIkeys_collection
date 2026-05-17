from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from api_launcher.manifests import AssetManifest, read_manifest, sha256_file
from api_launcher.paths import DOWNLOADS_DIR


@dataclass(frozen=True)
class ManifestVerification:
    manifest_path: Path
    payload_path: Path
    status: str
    provider_id: str = ""
    dataset_uid: str = ""
    dataset_id: str = ""
    version: str = ""
    source_url: str = ""
    message: str = ""

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
        }


@dataclass(frozen=True)
class RepairSuggestion:
    action_id: str
    label: str
    description: str
    can_requeue: bool = False
    plan_entry: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "label": self.label,
            "description": self.description,
            "can_requeue": self.can_requeue,
            "plan_entry": self.plan_entry,
        }


def verify_manifest_file(path: str | Path) -> ManifestVerification:
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


def repair_suggestion_for_result(result: ManifestVerification) -> RepairSuggestion:
    if result.status == "ok":
        return RepairSuggestion("none", "No action needed", "Payload matches its sidecar manifest.")
    if result.status == "manifest_error":
        return RepairSuggestion(
            "inspect_manifest",
            "Inspect manifest",
            "The manifest could not be parsed, so the launcher cannot safely infer a source URL or target path.",
        )
    if not result.needs_repair:
        return RepairSuggestion("inspect", "Inspect status", "No automatic repair rule is available for this status.")
    if not result.source_url:
        return RepairSuggestion(
            "manual_recover",
            "Manual recovery needed",
            "The manifest does not record a source URL, so the launcher cannot safely requeue this download.",
        )
    if not _is_requeue_source_url(result.source_url):
        return RepairSuggestion(
            "manual_recover",
            "Manual recovery needed",
            f"The recorded source URL is not an HTTP(S) download URL: {result.source_url}",
        )
    if not result.provider_id:
        return RepairSuggestion(
            "manual_recover",
            "Manual recovery needed",
            "The manifest does not record a provider_id, so the download queue cannot safely own the job.",
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
    )


def _is_requeue_source_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
