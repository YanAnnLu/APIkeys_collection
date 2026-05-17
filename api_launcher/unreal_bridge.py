from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_launcher.integrations import UnrealProjectProfile, active_unreal_project
from api_launcher.models import RenderBridgeAsset


@dataclass(frozen=True)
class UnrealBridgeTarget:
    asset_id: str
    dataset_uid: str
    asset_role: str
    source_path: str
    target_path: str
    unreal_mount_path: str
    status: str
    message: str = ""


def build_unreal_bridge_targets(
    assets: list[RenderBridgeAsset],
    profile: UnrealProjectProfile | None = None,
) -> list[UnrealBridgeTarget]:
    profile = profile or active_unreal_project()
    if profile is None:
        return [
            UnrealBridgeTarget(
                asset_id=asset.asset_id,
                dataset_uid=asset.dataset_uid,
                asset_role=asset.asset_role,
                source_path=asset.path,
                target_path="",
                unreal_mount_path="",
                status="unconfigured",
                message="No Unreal project profile is configured.",
            )
            for asset in assets
        ]
    content_root = unreal_content_root(profile)
    if content_root is None:
        return [
            UnrealBridgeTarget(
                asset_id=asset.asset_id,
                dataset_uid=asset.dataset_uid,
                asset_role=asset.asset_role,
                source_path=asset.path,
                target_path="",
                unreal_mount_path="",
                status="unconfigured",
                message="Unreal project content root is not configured.",
            )
            for asset in assets
        ]

    targets = []
    for asset in assets:
        source = Path(asset.path)
        filename = source.name or f"{safe_name(asset.asset_id)}.asset"
        target_dir = content_root / profile.bridge_subdir / safe_name(asset.dataset_uid) / safe_name(asset.asset_role)
        target = target_dir / filename
        targets.append(
            UnrealBridgeTarget(
                asset_id=asset.asset_id,
                dataset_uid=asset.dataset_uid,
                asset_role=asset.asset_role,
                source_path=str(source),
                target_path=str(target),
                unreal_mount_path=f"/Game/{profile.bridge_subdir}/{safe_name(asset.dataset_uid)}/{safe_name(asset.asset_role)}/{Path(filename).stem}",
                status="planned",
            )
        )
    return targets


def unreal_content_root(profile: UnrealProjectProfile) -> Path | None:
    if profile.content_root:
        return Path(profile.content_root)
    if profile.project_path:
        project = Path(profile.project_path)
        return project.parent / "Content"
    return None


def safe_name(value: str) -> str:
    clean = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.strip())
    return clean.strip("_") or "Unknown"
