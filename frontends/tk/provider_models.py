from __future__ import annotations

import APIkeys_collection as core


def provider_update_status_label(status: object) -> str:
    """Render provider update status without leaking unknown backend ids."""

    labels = {
        "remote_updated": "有更新",
        "current": "未變動",
        "checked_no_hash": "已檢查",
        "unknown": "未知",
    }
    status_id = str(status or "").strip()
    return labels.get(status_id, "更新狀態待確認")


def provider_local_status_label(status: object) -> str:
    """Render provider local install status without leaking unknown backend ids."""

    labels = {
        "not_imported": "未納管",
        "imported": "已納管",
        "downloaded": "已下載",
        "missing": "本地遺失",
        "error": "錯誤",
    }
    status_id = str(status or "").strip()
    return labels.get(status_id, "本地狀態待確認")


class ProviderRow:
    def __init__(self, entry: core.ProviderCatalogEntry):
        # ProviderRow 是 Tk 專用 view-model；後端資料仍以 core.ProviderCatalogEntry 為準。
        self.provider_id = entry.provider_id
        self.name = entry.name
        self.owner = entry.owner
        self.categories = entry.categories
        self.geographic_scope = entry.geographic_scope
        self.docs_url = entry.docs_url
        self.api_base_url = entry.api_base_url
        self.signup_url = entry.signup_url
        self.auth_type = entry.auth_type
        self.key_env_var = entry.key_env_var
        self.notes = entry.notes
        self.latest_status = entry.latest_status
        self.latest_fetched_at = entry.latest_fetched_at
        self.latest_error = entry.latest_error
        self.remote_status = entry.remote_status
        self.local_status = entry.local_status
        self.update_status = entry.update_status
        self.last_downloaded_at = entry.last_downloaded_at
        self.dataset_path = entry.dataset_path
        self.install_id = entry.install_id
        self.install_fingerprint = entry.install_fingerprint
        self.is_starred = entry.is_starred
        self.download_eligibility = core.assess_provider_download(self.as_provider())

    @property
    def category_label(self) -> str:
        return ", ".join(self.categories)

    @property
    def star_label(self) -> str:
        return "★" if self.is_starred else "☆"

    @property
    def status_label(self) -> str:
        if self.latest_status is None:
            return "未檢查"
        if self.latest_error:
            return "錯誤"
        return str(self.latest_status)

    @property
    def update_label(self) -> str:
        return provider_update_status_label(self.update_status)

    @property
    def local_label(self) -> str:
        return provider_local_status_label(self.local_status)

    @property
    def action_label(self) -> str:
        if self.update_status == "remote_updated":
            return "更新"
        if self.remote_status == "error":
            return "重試"
        if self.remote_status == "unchecked":
            return "檢查"
        return ""

    @property
    def download_label(self) -> str:
        label = self.download_eligibility.label
        if self.download_eligibility.requires_api_key:
            return f"{label}+Key"
        return label

    def as_provider(self) -> core.Provider:
        return core.Provider(
            provider_id=self.provider_id,
            name=self.name,
            owner=self.owner,
            categories=self.categories,
            geographic_scope=self.geographic_scope,
            docs_url=self.docs_url,
            api_base_url=self.api_base_url,
            signup_url=self.signup_url,
            auth_type=self.auth_type,
            key_env_var=self.key_env_var,
            notes=self.notes,
        )
