from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_launcher.integrations import UnrealProjectProfile, active_unreal_project
from api_launcher.models import RenderBridgeAsset


@dataclass(frozen=True)
class UnrealBridgeTarget:
    # 這個物件只描述「要把哪個 renderer asset 放到 Unreal 哪裡」，
    # 不在這一層真正複製檔案，避免 UI 預覽和匯出流程不小心改動專案內容。
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
    # Unreal profile 是本機設定；沒有設定時回傳可讀狀態，而不是猜測使用者專案路徑。
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
        # 缺 Content 根目錄時仍保留每個 asset 的來源資訊，讓 UI/agent 能提示下一步。
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
        # 目標路徑固定走 dataset_uid / asset_role，避免不同資料集的同名檔案互相覆蓋。
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
    # content_root 可明確覆蓋；否則從 .uproject 旁邊的 Content 推導，符合 Unreal 慣例。
    if profile.content_root:
        return Path(profile.content_root)
    if profile.project_path:
        project = Path(profile.project_path)
        return project.parent / "Content"
    return None


def safe_name(value: str) -> str:
    # Unreal mount path 和 Windows 檔名都不適合直接吃任意資料集 ID，所以集中正規化。
    clean = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.strip())
    return clean.strip("_") or "Unknown"
