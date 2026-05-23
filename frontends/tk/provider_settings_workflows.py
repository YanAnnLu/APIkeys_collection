"""Tk provider editing and settings workflows for RuRuKa Asset Launcher.

這個 mixin 收攏主視窗中的薄入口流程：新增/編輯 provider、開啟資料庫工具、
開啟專案文件與各種設定 dialog。這些方法主要是 UI glue，抽離後主視窗可以
專注在 layout、table 與 detail lifecycle，而不直接承擔每個設定對話框的啟動細節。
"""

from __future__ import annotations

import webbrowser
from tkinter import messagebox

import APIkeys_collection as core
from api_launcher.event_log import log_exception
from api_launcher.paths import PROJECT_ROOT
from frontends.tk.desktop_integration import reveal_path_in_file_manager
from frontends.tk.dialogs import (
    AiModelSettingsDialog,
    DataStoreConnectionSettingsDialog,
    DatabaseClientSettingsDialog,
    DeveloperCliDialog,
    GoogleGeminiSettingsDialog,
    ProviderEditorDialog,
    RecentEventLogsDialog,
    StartupEnvironmentChecksDialog,
    UiLanguageSettingsDialog,
)
from frontends.tk.provider_models import ProviderRow
from frontends.tk.ui_labels import data_store_next_action_message as data_store_next_action_message_text


class ProviderSettingsWorkflowMixin:
    """封裝 provider 編輯與設定對話框入口。"""

    def add_provider(self) -> None:
        dialog = ProviderEditorDialog(self.root)
        if dialog.result is None:
            return
        self.save_provider(dialog.result)
        self.active_provider_id = dialog.result.provider_id
        self.reload_data()
        self.open_detail_drawer()
        self.status_var.set(f"已新增資料源：{dialog.result.name}")

    def edit_active_provider(self) -> None:
        row = self.row_by_provider_id(self.active_provider_id)
        if row is None:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        dialog = ProviderEditorDialog(self.root, row)
        if dialog.result is None:
            return
        self.save_provider(dialog.result)
        self.active_provider_id = dialog.result.provider_id
        self.reload_data()
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.status_var.set(f"已更新資料源：{dialog.result.name}")

    def save_provider(self, provider: core.Provider) -> None:
        conn = self._connect()
        try:
            core.ApiCatalogRepository(conn).upsert_provider(provider)
        finally:
            conn.close()

    def provider_from_row(self, row: ProviderRow, notes: str | None = None) -> core.Provider:
        return core.Provider(
            provider_id=row.provider_id,
            name=row.name,
            owner=row.owner,
            categories=row.categories,
            geographic_scope=row.geographic_scope,
            docs_url=row.docs_url,
            api_base_url=row.api_base_url,
            signup_url=row.signup_url,
            auth_type=row.auth_type,
            key_env_var=row.key_env_var,
            notes=row.notes if notes is None else notes,
        )

    def open_database_tool(self) -> None:
        try:
            profile = core.open_database_client()
        except Exception as exc:
            log_exception(
                "open_database_tool_failed",
                exc,
                component="ui.database",
                context={"active_provider_id": self.active_provider_id},
            )
            messagebox.showerror(
                "無法開啟資料庫工具",
                (
                    f"{exc}\n\n"
                    "請複製 config/launcher_integrations.example.json 為 "
                    "launcher_integrations.local.json，並調整你的 MySQL Workbench、DBeaver "
                    "或其他資料庫工具路徑。"
                ),
            )
            self.status_var.set(f"資料庫工具啟動失敗：{exc}")
            return
        self.status_var.set(f"已開啟資料庫工具：{profile.label}")

    def open_database_settings(self) -> None:
        DatabaseClientSettingsDialog(self.root)
        profile = core.active_database_client()
        if profile:
            self.status_var.set(f"目前預設資料庫工具：{profile.label}")

    def open_integration_config_file(self) -> None:
        core.ensure_local_integration_config()
        reveal_path_in_file_manager(core.local_integrations_path())
        self.status_var.set(self.tr("已在檔案管理器顯示本機整合設定檔。", "Revealed local integration config in the file manager."))

    def open_doc_file(self, name: str) -> None:
        path = PROJECT_ROOT / "docs" / name
        if not path.exists():
            messagebox.showinfo(self.tr("找不到文件", "Document not found"), str(path))
            return
        webbrowser.open(path.as_uri())

    def open_developer_cli(self) -> None:
        DeveloperCliDialog(self)

    def open_ui_language_settings(self) -> None:
        UiLanguageSettingsDialog(self)

    def open_ai_model_settings(self) -> None:
        AiModelSettingsDialog(self)

    def data_store_next_action_message(self, result: object) -> str:
        return data_store_next_action_message_text(result, self.tr)

    def open_data_store_connection_settings(self) -> None:
        DataStoreConnectionSettingsDialog(self)

    def show_environment_checks(self) -> None:
        StartupEnvironmentChecksDialog(self)

    def show_event_logs(self) -> None:
        RecentEventLogsDialog(self)

    def open_google_gemini_settings(self) -> None:
        GoogleGeminiSettingsDialog(self)
