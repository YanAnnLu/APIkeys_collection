from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from api_launcher.db import resolve_project_path
from api_launcher.manifests import AssetManifest, build_asset_manifest, write_manifest
from api_launcher.paths import PROJECT_ROOT, STAGING_DIR


@dataclass(frozen=True)
class StagingPaths:
    # staging 與 final 路徑成對保存，讓下載、manifest、promote 三段流程不必各自推導。
    staging_dir: Path
    payload_path: Path
    part_path: Path
    manifest_path: Path
    final_path: Path
    final_manifest_path: Path


def staging_paths_for_plan_entry(plan_entry: dict[str, object], final_path: str | Path) -> StagingPaths:
    # staging path 以 provider / dataset / version 分層，避免不同下載任務的 .part 檔互相踩到。
    provider_id = safe_path_part(str(plan_entry.get("provider_id") or "unknown_provider"))
    dataset_version = plan_entry.get("dataset_version")
    version = ""
    dataset_id = ""
    if isinstance(dataset_version, dict):
        version = str(dataset_version.get("version") or "")
        dataset_id = str(dataset_version.get("dataset_id") or "")
    version_part = safe_path_part(version or str(plan_entry.get("version") or "unversioned"))
    dataset_part = safe_path_part(dataset_id or str(plan_entry.get("dataset_id") or "provider"))
    # final_path 可能來自 plan JSON；先走 project path resolver，保留跨平台路徑處理規則。
    final = resolve_project_path(final_path)
    staging_root = staging_root_for_final_path(final)
    staging_dir = staging_root / provider_id / dataset_part / version_part
    payload_path = staging_dir / final.name
    return StagingPaths(
        staging_dir=staging_dir,
        payload_path=payload_path,
        part_path=payload_path.with_suffix(payload_path.suffix + ".part"),
        manifest_path=payload_path.with_suffix(payload_path.suffix + ".manifest.json"),
        final_path=final,
        final_manifest_path=final.with_suffix(final.suffix + ".manifest.json"),
    )


def promote_staged_payload(paths: StagingPaths, plan_entry: dict[str, object]) -> AssetManifest:
    paths.final_path.parent.mkdir(parents=True, exist_ok=True)
    # 先對 staging payload 建 manifest，確認內容 hash/size 後才原子替換到 final path。
    manifest = build_asset_manifest(paths.payload_path, plan_entry)
    write_manifest(manifest, paths.manifest_path)
    os.replace(paths.payload_path, paths.final_path)
    # final manifest 重新寫入 final path，但沿用同一份內容 hash，方便後續 repair 驗證。
    write_manifest(
        AssetManifest(
            provider_id=manifest.provider_id,
            dataset_uid=manifest.dataset_uid,
            dataset_id=manifest.dataset_id,
            version=manifest.version,
            source_url=manifest.source_url,
            path=str(paths.final_path),
            size_bytes=manifest.size_bytes,
            sha256=manifest.sha256,
            schema_fingerprint=manifest.schema_fingerprint,
            created_at=manifest.created_at,
            metadata=manifest.metadata,
        ),
        paths.final_manifest_path,
    )
    return manifest


def safe_path_part(value: str) -> str:
    # 下載計畫常含 API dataset id；集中轉成安全路徑片段，避免產生奇怪資料夾。
    clean = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value.strip())
    return clean.strip("._") or "unknown"


def staging_root_for_final_path(final_path: Path) -> Path:
    try:
        final_path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        # 專案外目標不能放進共用 state/staging，改放在 final 旁邊，避免跨磁碟 rename 失敗。
        return final_path.parent / ".apikeys_staging"
    return STAGING_DIR
