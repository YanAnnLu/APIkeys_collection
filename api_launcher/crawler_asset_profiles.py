from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from api_launcher.paths import local_config_file


LOCAL_CRAWLER_ASSET_PROFILES_NAME = "crawler_asset_profiles.local.json"


@dataclass(frozen=True)
class CrawlerAssetProfile:
    """本機 crawler asset 偏好設定；不寫入正式 catalog，也不保存真實密碼。"""

    asset_id: str
    enabled: bool = True
    archived: bool = False
    credential_profile_id: str = ""
    schedule_policy: str = ""
    status_note: str = ""
    local_logo_path: str = ""
    official_logo_url: str = ""
    favicon_url: str = ""
    logo_source: str = ""
    logo_license_note: str = ""

    @property
    def active(self) -> bool:
        return self.enabled and not self.archived

    @property
    def profile_state(self) -> str:
        if self.archived:
            return "archived"
        if not self.enabled:
            return "disabled"
        return "active"

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "archived": self.archived,
            "credential_profile_id": self.credential_profile_id,
            "schedule_policy": self.schedule_policy,
            "status_note": self.status_note,
            "local_logo_path": self.local_logo_path,
            "official_logo_url": self.official_logo_url,
            "favicon_url": self.favicon_url,
            "logo_source": self.logo_source,
            "logo_license_note": self.logo_license_note,
        }


def crawler_asset_profiles_path() -> Path:
    return local_config_file(LOCAL_CRAWLER_ASSET_PROFILES_NAME)


def load_crawler_asset_profiles(path: str | Path | None = None) -> dict[str, CrawlerAssetProfile]:
    """讀取本機 crawler profile；檔案不存在時代表全部啟用。"""

    target = Path(path) if path is not None else crawler_asset_profiles_path()
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8-sig"))
    raw_profiles = payload.get("profiles", {})
    if not isinstance(raw_profiles, dict):
        return {}
    profiles: dict[str, CrawlerAssetProfile] = {}
    for asset_id, raw in raw_profiles.items():
        if not isinstance(raw, dict):
            continue
        asset_key = str(asset_id).strip()
        if not asset_key:
            continue
        profiles[asset_key] = crawler_asset_profile_from_dict(asset_key, raw)
    return profiles


def crawler_asset_profile_from_dict(asset_id: str, raw: dict[str, object]) -> CrawlerAssetProfile:
    return CrawlerAssetProfile(
        asset_id=asset_id,
        enabled=bool(raw.get("enabled", True)),
        archived=bool(raw.get("archived", False)),
        credential_profile_id=str(raw.get("credential_profile_id") or "").strip(),
        schedule_policy=str(raw.get("schedule_policy") or "").strip(),
        status_note=str(raw.get("status_note") or "").strip(),
        local_logo_path=str(raw.get("local_logo_path") or "").strip(),
        official_logo_url=str(raw.get("official_logo_url") or "").strip(),
        favicon_url=str(raw.get("favicon_url") or "").strip(),
        logo_source=str(raw.get("logo_source") or "").strip(),
        logo_license_note=str(raw.get("logo_license_note") or "").strip(),
    )


def default_crawler_asset_profile(asset_id: str) -> CrawlerAssetProfile:
    return CrawlerAssetProfile(asset_id=asset_id)


def crawler_asset_profile_for(
    asset_id: str,
    profiles: dict[str, CrawlerAssetProfile] | None = None,
) -> CrawlerAssetProfile:
    if profiles is None:
        profiles = load_crawler_asset_profiles()
    return profiles.get(asset_id) or default_crawler_asset_profile(asset_id)


def save_crawler_asset_profiles(
    profiles: dict[str, CrawlerAssetProfile],
    path: str | Path | None = None,
) -> Path:
    """保存本機 crawler profile；這個檔案由 .gitignore 排除。"""

    target = Path(path) if path is not None else crawler_asset_profiles_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "profiles": {asset_id: profile.to_dict() for asset_id, profile in sorted(profiles.items())},
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def set_crawler_asset_archived(
    asset_id: str,
    archived: bool,
    path: str | Path | None = None,
) -> CrawlerAssetProfile:
    """切換封存狀態；封存等於保留入口但停用自動化與預設執行。"""

    asset_key = asset_id.strip()
    if not asset_key:
        raise ValueError("crawler asset id is required")
    profiles = load_crawler_asset_profiles(path)
    current = profiles.get(asset_key) or default_crawler_asset_profile(asset_key)
    updated = CrawlerAssetProfile(
        asset_id=asset_key,
        enabled=not archived,
        archived=archived,
        credential_profile_id=current.credential_profile_id,
        schedule_policy=current.schedule_policy,
        status_note=current.status_note,
        local_logo_path=current.local_logo_path,
        official_logo_url=current.official_logo_url,
        favicon_url=current.favicon_url,
        logo_source=current.logo_source,
        logo_license_note=current.logo_license_note,
    )
    profiles[asset_key] = updated
    save_crawler_asset_profiles(profiles, path)
    return updated


def toggle_crawler_asset_archived(
    asset_id: str,
    path: str | Path | None = None,
) -> CrawlerAssetProfile:
    current = crawler_asset_profile_for(asset_id, load_crawler_asset_profiles(path))
    return set_crawler_asset_archived(asset_id, not current.archived, path)
