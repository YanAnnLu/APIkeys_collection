from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from frontends.tk.dialogs import (
    AiModelSettingsDialog,
    DataStoreConnectionSettingsDialog,
    DatabaseClientSettingsDialog,
    DeveloperCliDialog,
    ProviderEditorDialog,
    RecentEventLogsDialog,
    StartupEnvironmentChecksDialog,
    UiLanguageSettingsDialog,
)


class _FakeVar:
    def __init__(self, value: str):
        self.value = value

    def get(self) -> str:
        return self.value


class TkDialogModuleTest(unittest.TestCase):
    def test_dialog_classes_are_importable(self) -> None:
        # 這個測試保護 launcher_ui.py 拆分後的公開匯入點，不需要真的開 Tk 視窗。
        self.assertTrue(callable(ProviderEditorDialog))
        self.assertTrue(callable(AiModelSettingsDialog))
        self.assertTrue(callable(DatabaseClientSettingsDialog))
        self.assertTrue(callable(DataStoreConnectionSettingsDialog))
        self.assertTrue(callable(DeveloperCliDialog))
        self.assertTrue(callable(UiLanguageSettingsDialog))
        self.assertTrue(callable(StartupEnvironmentChecksDialog))
        self.assertTrue(callable(RecentEventLogsDialog))

    def test_database_client_profile_label_marks_enabled_state(self) -> None:
        # _profile_label 是 dialog 內部資料呈現邊界，可在 headless CI 中直接測。
        dialog = object.__new__(DatabaseClientSettingsDialog)
        enabled_profile = SimpleNamespace(id="sqlitebrowser", label="DB Browser", enabled=True)
        disabled_profile = SimpleNamespace(id="dbeaver", label="DBeaver", enabled=False)

        self.assertEqual(
            "sqlitebrowser - DB Browser (enabled)",
            dialog._profile_label(enabled_profile),
        )
        self.assertEqual(
            "dbeaver - DBeaver (disabled)",
            dialog._profile_label(disabled_profile),
        )
        self.assertEqual("", dialog._profile_label(None))

    def test_database_client_selected_profile_reads_selected_id(self) -> None:
        # selected_profile 只依 combobox 標籤前段 id 配對，避免 label 變動影響 profile 選取。
        dialog = object.__new__(DatabaseClientSettingsDialog)
        sqlite_profile = SimpleNamespace(id="sqlitebrowser", label="DB Browser", enabled=True)
        dbeaver_profile = SimpleNamespace(id="dbeaver", label="DBeaver", enabled=True)
        dialog.profiles = [sqlite_profile, dbeaver_profile]
        dialog.profile_var = _FakeVar("dbeaver - DBeaver (enabled)")

        self.assertIs(dbeaver_profile, dialog.selected_profile())

    def test_data_store_active_profile_label_uses_ui_translation(self) -> None:
        # DataStore dialog 用主 UI 的 tr callback，避免抽出 class 後失去語言設定。
        dialog = object.__new__(DataStoreConnectionSettingsDialog)
        dialog.ui = SimpleNamespace(tr=lambda zh, _en: zh)
        with patch("frontends.tk.dialogs.active_data_store_profile", return_value=SimpleNamespace(profile_id="mysql_local")):
            self.assertEqual("目前作用中 profile：mysql_local", dialog._active_profile_label())

        with patch("frontends.tk.dialogs.active_data_store_profile", return_value=None):
            self.assertEqual("目前作用中 profile：-", dialog._active_profile_label())

    def test_developer_cli_split_command_preserves_quoted_arguments(self) -> None:
        # 開發者 CLI 允許輸入單行命令；quoted argument 必須維持為同一個 argv。
        self.assertEqual(
            ["python", "APIkeys_collection.py", "--summary", "hello world"],
            DeveloperCliDialog.split_command('python APIkeys_collection.py --summary "hello world"'),
        )

    def test_ui_language_codes_by_label_round_trips_display_labels(self) -> None:
        # 語言 combobox 顯示 label，但設定檔需要寫回穩定語言代碼。
        self.assertEqual(
            {"繁體中文": "zh-TW", "English": "en-US"},
            UiLanguageSettingsDialog.language_codes_by_label({"zh-TW": "繁體中文", "en-US": "English"}),
        )

    def test_recent_event_log_row_values_are_stable(self) -> None:
        # 事件表格欄位順序是 UI/測試共享契約，避免後續解耦時插入錯欄。
        event = {
            "timestamp": "2026-05-23T12:00:00Z",
            "level": "info",
            "component": "tk",
            "event": "demo",
            "message": "ok",
        }

        self.assertEqual(
            ("2026-05-23T12:00:00Z", "info", "tk", "demo", "ok"),
            RecentEventLogsDialog.event_row_values(event),
        )

    def test_ai_model_profile_row_values_mark_active_profile(self) -> None:
        # AI profile 表格用同一個 helper 產生 row，避免選用勾選欄位在拆分後失真。
        profile = SimpleNamespace(
            id="gemini_flash",
            label="Gemini Flash",
            kind="gemini",
            model="gemini-2.5-flash",
            enabled=True,
            notes="cloud",
        )

        self.assertEqual(
            ("✓", "Gemini Flash", "gemini", "gemini-2.5-flash", "API key ready", "啟用", "cloud"),
            AiModelSettingsDialog.profile_row_values(
                profile,
                active_profile_id="gemini_flash",
                login_status="API key ready",
                enabled_label="啟用",
                disabled_label="停用",
            ),
        )


if __name__ == "__main__":
    unittest.main()
