"""Tk AI summary and AI profile workflows for RuRuKa Asset Launcher.

這個 mixin 管理 AI profile 狀態、啟動時的本機 API key 載入，以及 provider
說明文字生成。主視窗只保留按鈕與顯示區，背景 worker、credential 檢查與
repository 回寫集中在這裡，避免 profile/login 狀態邏輯散落在主視窗類別。
"""

from __future__ import annotations

import os
from tkinter import messagebox

import APIkeys_collection as core
from api_launcher.ai_api_keys import default_api_key_env, load_saved_ai_api_keys, saved_ai_api_key_status
from api_launcher.event_log import log_exception
from api_launcher.oauth_device import oauth_device_config_from_profile, oauth_token_status
from frontends.tk.background_jobs import start_single_flight_thread


MAX_TK_AI_SUMMARY_BACKGROUND_JOBS = 2


class AiSummaryWorkflowMixin:
    """封裝 AI profile 狀態與 provider summary 生成流程。"""

    def notify_ai_summary_queue_full(self) -> None:
        self.status_var.set(
            self.tr(
                "AI 摘要背景工作已達上限，請等待目前工作完成。",
                "AI summary background jobs are at capacity; wait for one to finish.",
            )
        )

    def load_saved_ai_api_keys_for_startup(self) -> None:
        """Startup may read local private API-key state, but must not trigger OAuth/login UI."""
        loaded_api_keys = load_saved_ai_api_keys(core.ai_summary_profiles())
        if loaded_api_keys:
            self.status_var.set(self.tr(f"已載入本機 AI API key：{', '.join(loaded_api_keys[:3])}", f"Loaded local AI API keys: {', '.join(loaded_api_keys[:3])}"))

    def ai_profile_labels(self) -> dict[str, str]:
        return {
            f"{profile.label} ({profile.kind} / {profile.model})": profile.id
            for profile in core.ai_summary_profiles()
        }

    def api_key_env_for_profile(self, profile: core.AiSummaryProfile) -> str:
        return default_api_key_env(profile)

    def profile_has_cloud_credential(self, profile: core.AiSummaryProfile) -> bool:
        load_saved_ai_api_keys([profile])
        api_key_env = self.api_key_env_for_profile(profile)
        if api_key_env and os.environ.get(api_key_env, "").strip():
            return True
        oauth_config = oauth_device_config_from_profile(profile)
        if oauth_config is None:
            return False
        status, _message = oauth_token_status(oauth_config.token_store, label=profile.label)
        return status == "ready"

    def ai_profile_login_status(self, profile: core.AiSummaryProfile) -> str:
        if profile.kind == "ollama":
            return self.tr("本機服務", "Local service")
        api_key_env = self.api_key_env_for_profile(profile)
        if api_key_env and os.environ.get(api_key_env, "").strip():
            return self.tr(f"API key 已載入：{api_key_env}", f"API key ready: {api_key_env}")
        saved_status, _saved_message = saved_ai_api_key_status(profile)
        if saved_status == "stored":
            return self.tr(f"API key 已保存：{api_key_env}", f"API key saved: {api_key_env}")
        oauth_config = oauth_device_config_from_profile(profile)
        if oauth_config is not None:
            if not oauth_config.enabled:
                return self.tr("OAuth 已停用", "OAuth disabled")
            status, _message = oauth_token_status(oauth_config.token_store, label=profile.label)
            if status == "ready":
                return self.tr(f"OAuth 已登入：{status}", f"OAuth signed in: {status}")
        if api_key_env:
            return self.tr(f"需要 API key：{api_key_env}", f"Needs API key: {api_key_env}")
        return self.tr("不需登入", "No login")

    def generate_active_summary(self) -> None:
        row = self.row_by_provider_id(self.active_provider_id)
        if row is None:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        profile = next((item for item in core.ai_summary_profiles() if item.id == self.selected_ai_profile_id), None)
        if profile is None:
            messagebox.showinfo(
                "尚未設定 AI 摘要",
                (
                    "請在「整合 > AI 輔助模型選擇」選擇要使用的模型。"
                    "預設建議可先用本機 Ollama，免登入也不需要雲端 API key。"
                ),
            )
            return
        if not profile.enabled:
            try:
                profile = core.set_active_ai_profile(profile.id)
            except Exception as exc:
                messagebox.showerror("AI 摘要設定失敗", str(exc))
                return
        if profile.kind != "ollama" and not self.profile_has_cloud_credential(profile):
            if not self.configure_ai_api_key_session(profile.id, parent=self.root):
                self.status_var.set("AI 摘要尚未啟動：需要 API key 或已保存的登入 token。")
                return
            profile = next((item for item in core.ai_summary_profiles() if item.id == profile.id), profile)
        self.selected_ai_profile_id = profile.id
        self.status_var.set(f"正在使用 {profile.label} 產生 {row.name} 的說明...")
        job_key = ("ai_summary", row.provider_id, profile.id)
        start_single_flight_thread(
            self,
            job_key,
            self._summary_worker,
            (row.provider_id, profile.id),
            active_jobs_attr="ai_summary_active_jobs",
            active_jobs_lock_attr="ai_summary_active_jobs_lock",
            on_duplicate=lambda: self.status_var.set(
                self.tr("AI 摘要已在執行中，請等待目前工作完成。", "AI summary is already running; please wait for it to finish.")
            ),
            max_active_jobs=MAX_TK_AI_SUMMARY_BACKGROUND_JOBS,
            on_capacity=self.notify_ai_summary_queue_full,
        )

    def _summary_worker(self, provider_id: str, profile_id: str) -> None:
        saved_summary = False
        try:
            conn = self._connect()
            try:
                repository = core.ApiCatalogRepository(conn)
                providers = repository.load_providers([provider_id])
                if not providers:
                    raise RuntimeError(f"Unknown provider_id: {provider_id}")
                provider = providers[0]
                summary = core.generate_provider_summary(provider, profile_id=profile_id)
                if not provider.notes:
                    provider = core.Provider(
                        provider_id=provider.provider_id,
                        name=provider.name,
                        owner=provider.owner,
                        categories=provider.categories,
                        geographic_scope=provider.geographic_scope,
                        docs_url=provider.docs_url,
                        api_base_url=provider.api_base_url,
                        signup_url=provider.signup_url,
                        auth_type=provider.auth_type,
                        key_env_var=provider.key_env_var,
                        license_url=provider.license_url,
                        terms_url=provider.terms_url,
                        notes=summary,
                        crawl_urls=provider.crawl_urls,
                    )
                    repository.upsert_provider(provider)
                    saved_summary = True
            finally:
                conn.close()
        except Exception as exc:
            error = str(exc)
            log_exception(
                "ai_summary_failed",
                exc,
                component="ui.ai_summary",
                context={"provider_id": provider_id, "profile_id": profile_id},
            )
            self.root.after(0, lambda: messagebox.showerror("AI 摘要失敗", error))
            self.root.after(0, lambda: self.status_var.set(f"AI 摘要失敗：{error}"))
            return

        def update_ui() -> None:
            if saved_summary:
                self.reload_data()
                row = self.row_by_provider_id(provider_id)
                self.set_ai_summary_text(summary)
                self.status_var.set(f"AI 說明已寫入：{row.name if row else provider_id}")
            else:
                self.set_ai_summary_text(summary)
                self.status_var.set("AI 摘要已產生；既有描述未被覆蓋。")

        self.root.after(0, update_ui)
