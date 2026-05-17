from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api_launcher.db import utc_now_iso


HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class AssetManifest:
    provider_id: str
    dataset_uid: str
    dataset_id: str
    version: str
    source_url: str
    path: str
    size_bytes: int
    sha256: str
    schema_fingerprint: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "provider_id": self.provider_id,
            "dataset_uid": self.dataset_uid,
            "dataset_id": self.dataset_id,
            "version": self.version,
            "source_url": self.source_url,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "schema_fingerprint": self.schema_fingerprint,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(HASH_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build_asset_manifest(path: str | Path, plan_entry: dict[str, object]) -> AssetManifest:
    target = Path(path)
    dataset_version = plan_entry.get("dataset_version")
    version_data = dataset_version if isinstance(dataset_version, dict) else {}
    metadata = version_data.get("metadata") if isinstance(version_data.get("metadata"), dict) else {}
    return AssetManifest(
        provider_id=str(plan_entry.get("provider_id") or ""),
        dataset_uid=str(version_data.get("dataset_uid") or plan_entry.get("dataset_uid") or ""),
        dataset_id=str(version_data.get("dataset_id") or plan_entry.get("dataset_id") or ""),
        version=str(version_data.get("version") or plan_entry.get("version") or ""),
        source_url=str(version_data.get("download_url") or plan_entry.get("download_url") or plan_entry.get("api_base_url") or ""),
        path=str(target),
        size_bytes=target.stat().st_size,
        sha256=sha256_file(target),
        schema_fingerprint=str(plan_entry.get("schema_fingerprint") or ""),
        metadata=dict(metadata),
    )


def write_manifest(manifest: AssetManifest, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def read_manifest(path: str | Path) -> AssetManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AssetManifest(
        provider_id=str(data.get("provider_id") or ""),
        dataset_uid=str(data.get("dataset_uid") or ""),
        dataset_id=str(data.get("dataset_id") or ""),
        version=str(data.get("version") or ""),
        source_url=str(data.get("source_url") or ""),
        path=str(data.get("path") or ""),
        size_bytes=int(data.get("size_bytes") or 0),
        sha256=str(data.get("sha256") or ""),
        schema_fingerprint=str(data.get("schema_fingerprint") or ""),
        created_at=str(data.get("created_at") or ""),
        metadata=dict(data.get("metadata") or {}),
    )
