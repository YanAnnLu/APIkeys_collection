from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

from api_launcher.paths import local_config_file


LOCAL_CRAWLER_ASSET_PROFILES_NAME = "crawler_asset_profiles.local.json"
CRAWLER_ASSET_PLAN_PASSPORT_PROFILE_KEYS = frozenset(
    {
        "asset_id",
        "has_resolved_plan",
        "outcome_bucket",
        "short_label",
        "display_tone",
        "candidate_count",
        "upserted_candidate_count",
        "selected_version_count",
        "filtered_version_count",
        "direct_download_count",
        "review_required_count",
        "adapter_review_count",
        "content_review_count",
        "blocked_credential_count",
        "credential_gate_count",
        "missing_provider_count",
        "next_action",
        "bounds",
    }
)


@dataclass(frozen=True)
class CrawlerAssetProfile:
    """本機 crawler asset 偏好設定；不寫入正式 catalog，也不保存真實密碼。"""

    asset_id: str
    enabled: bool = True
    archived: bool = False
    credential_profile_id: str = ""
    api_key_env_var: str = ""
    account_hint: str = ""
    schedule_policy: str = ""
    rate_limit_policy: str = ""
    retry_policy: str = ""
    seed_scope_policy: str = "bounded"
    status_note: str = ""
    local_logo_path: str = ""
    official_logo_url: str = ""
    favicon_url: str = ""
    logo_source: str = ""
    logo_license_note: str = ""
    latest_plan_passport: dict[str, object] = field(default_factory=dict)

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
            "api_key_env_var": self.api_key_env_var,
            "account_hint": self.account_hint,
            "schedule_policy": self.schedule_policy,
            "rate_limit_policy": self.rate_limit_policy,
            "retry_policy": self.retry_policy,
            "seed_scope_policy": self.seed_scope_policy,
            "status_note": self.status_note,
            "local_logo_path": self.local_logo_path,
            "official_logo_url": self.official_logo_url,
            "favicon_url": self.favicon_url,
            "logo_source": self.logo_source,
            "logo_license_note": self.logo_license_note,
            "latest_plan_passport": dict(self.latest_plan_passport),
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
        api_key_env_var=str(raw.get("api_key_env_var") or "").strip(),
        account_hint=str(raw.get("account_hint") or "").strip(),
        schedule_policy=str(raw.get("schedule_policy") or "").strip(),
        rate_limit_policy=str(raw.get("rate_limit_policy") or "").strip(),
        retry_policy=str(raw.get("retry_policy") or "").strip(),
        seed_scope_policy=str(raw.get("seed_scope_policy") or "bounded").strip() or "bounded",
        status_note=str(raw.get("status_note") or "").strip(),
        local_logo_path=str(raw.get("local_logo_path") or "").strip(),
        official_logo_url=str(raw.get("official_logo_url") or "").strip(),
        favicon_url=str(raw.get("favicon_url") or "").strip(),
        logo_source=str(raw.get("logo_source") or "").strip(),
        logo_license_note=str(raw.get("logo_license_note") or "").strip(),
        latest_plan_passport=compact_crawler_asset_plan_passport(raw.get("latest_plan_passport")),
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


PROFILE_EDITABLE_FIELDS = {
    "enabled",
    "archived",
    "credential_profile_id",
    "api_key_env_var",
    "account_hint",
    "schedule_policy",
    "rate_limit_policy",
    "retry_policy",
    "seed_scope_policy",
    "status_note",
    "local_logo_path",
    "official_logo_url",
    "favicon_url",
    "logo_source",
    "logo_license_note",
}

_ENV_VAR_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def update_crawler_asset_profile(
    asset_id: str,
    path: str | Path | None = None,
    **updates: object,
) -> CrawlerAssetProfile:
    """更新單一爬蟲資產設定檔，供 Tk/Qt/CLI 共用。

    Profile 只保存本機偏好與憑證參照，不保存 token/password 本體。需要帳號的爬蟲
    應透過 `credential_profile_id` 或 `api_key_env_var` 指向外部憑證來源。
    """

    asset_key = asset_id.strip()
    if not asset_key:
        raise ValueError("crawler asset id is required")
    profiles = load_crawler_asset_profiles(path)
    current = profiles.get(asset_key) or default_crawler_asset_profile(asset_key)
    updated = replace(current, **_clean_profile_updates(updates))
    profiles[asset_key] = updated
    save_crawler_asset_profiles(profiles, path)
    return updated


def _clean_profile_updates(updates: dict[str, object]) -> dict[str, object]:
    unknown = sorted(set(updates) - PROFILE_EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"unsupported crawler asset profile fields: {', '.join(unknown)}")
    cleaned: dict[str, object] = {}
    for key, value in updates.items():
        if key in {"enabled", "archived"}:
            cleaned[key] = bool(value)
            continue
        text = str(value or "").strip()
        if key == "api_key_env_var":
            text = _validate_api_key_env_var(text)
        elif key == "seed_scope_policy" and not text:
            text = "bounded"
        cleaned[key] = text
    return cleaned


def _validate_api_key_env_var(value: str) -> str:
    if not value:
        return ""
    if "=" in value or value.lower().startswith(("sk-", "ghp_", "github_pat_", "eyj")):
        raise ValueError("api_key_env_var must be an environment variable name, not a raw secret")
    if not _ENV_VAR_RE.fullmatch(value):
        raise ValueError("api_key_env_var must look like an uppercase environment variable name")
    return value


def compact_crawler_asset_plan_passport(plan_passport: object) -> dict[str, object]:
    """Keep persisted plan passport status bounded and free of resolved plans."""

    if not isinstance(plan_passport, Mapping):
        return {}
    payload = {
        key: value
        for key, value in plan_passport.items()
        if key in CRAWLER_ASSET_PLAN_PASSPORT_PROFILE_KEYS
    }
    payload["bounds"] = _compact_plan_passport_bounds(payload.get("bounds"))
    return dict(payload)


def _compact_plan_passport_bounds(bounds: object) -> dict[str, object]:
    if not isinstance(bounds, Mapping):
        return {}
    compact: dict[str, object] = {}
    for key, value in bounds.items():
        field = str(key).strip()
        if not field:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            compact[field] = value
        elif isinstance(value, (list, tuple)):
            compact[field] = [
                item
                for item in value
                if isinstance(item, (str, int, float, bool)) or item is None
            ]
    return compact


def update_crawler_asset_plan_passport(
    asset_id: str,
    plan_passport: object,
    path: str | Path | None = None,
) -> CrawlerAssetProfile:
    """Persist only the small UI passport, never the resolved download plan."""

    asset_key = asset_id.strip()
    if not asset_key:
        raise ValueError("crawler asset id is required")
    profiles = load_crawler_asset_profiles(path)
    current = profiles.get(asset_key) or default_crawler_asset_profile(asset_key)
    updated = replace(current, latest_plan_passport=compact_crawler_asset_plan_passport(plan_passport))
    profiles[asset_key] = updated
    save_crawler_asset_profiles(profiles, path)
    return updated


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
    updated = replace(current, enabled=not archived, archived=archived)
    profiles[asset_key] = updated
    save_crawler_asset_profiles(profiles, path)
    return updated


def toggle_crawler_asset_archived(
    asset_id: str,
    path: str | Path | None = None,
) -> CrawlerAssetProfile:
    current = crawler_asset_profile_for(asset_id, load_crawler_asset_profiles(path))
    return set_crawler_asset_archived(asset_id, not current.archived, path)


__all__ = [
    "CrawlerAssetProfile",
    "compact_crawler_asset_plan_passport",
    "crawler_asset_profile_for",
    "crawler_asset_profiles_path",
    "default_crawler_asset_profile",
    "load_crawler_asset_profiles",
    "save_crawler_asset_profiles",
    "set_crawler_asset_archived",
    "toggle_crawler_asset_archived",
    "update_crawler_asset_profile",
    "update_crawler_asset_plan_passport",
]
