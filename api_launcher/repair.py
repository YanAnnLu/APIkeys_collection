from __future__ import annotations

from dataclasses import dataclass
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
    message: str = ""

    @property
    def needs_repair(self) -> bool:
        return self.status in {"missing", "size_mismatch", "checksum_mismatch", "manifest_error"}


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
        message=message,
    )
