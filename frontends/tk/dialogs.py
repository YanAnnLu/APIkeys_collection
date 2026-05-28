"""Tk 對話框元件。

這個模組集中放置可獨立開窗、可用 class 封裝生命週期的對話框。
主畫面 `launcher_ui.py` 只負責何時開啟對話框與如何消費結果，避免把每個
Toplevel 的欄位配置、按鈕行為與本機工具設定都堆在同一個 6000+ 行檔案。
"""

from __future__ import annotations

import json
import shlex
import subprocess
import webbrowser
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, Y, StringVar, Text, Tk, Toplevel, messagebox
from tkinter import ttk
from typing import Any

import APIkeys_collection as core
from api_launcher.account_links import DEFAULT_ACCOUNT_PROVIDERS
from api_launcher.adapter_review import AdapterReviewItem
from api_launcher.crawler_asset_display import adapter_review_outcome_label
from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME, append_dataset_discovery_source
from api_launcher.data_store_connections import (
    data_store_profiles_from_config,
    test_data_store_connection,
    write_data_store_env_template,
)
from api_launcher.discovery import LOCAL_SEEDS_NAME, ProviderSeed, append_discovery_seed
from api_launcher.discovery_drafts import dataset_source_from_provider_candidate
from api_launcher.event_log import EVENT_LOG_NAME, latest_events, log_event, log_exception
from api_launcher.google_auth import google_oauth_token_status
from api_launcher.import_policies import normalized_ui_import_policy
from api_launcher.integrations import active_data_store_profile, save_integration_config, set_active_data_store_profile
from api_launcher.oauth_device import oauth_device_config_from_profile, oauth_token_status
from api_launcher.paths import PROJECT_ROOT, local_config_file, log_file
from frontends.tk.background_jobs import single_flight_job_is_active, start_single_flight_thread
from frontends.tk.desktop_integration import reveal_path_in_file_manager
from frontends.tk.provider_models import ProviderRow
from frontends.tk.ui_config import COLORS, DB_PATH, DEFAULT_UI_LANGUAGE, UI_LANGUAGES
from frontends.tk.ui_helpers import data_store_env_template_path


class ProviderEditorDialog:
    def __init__(self, parent: Tk, row: ProviderRow | None = None):
        # Dialog 只產生 core.Provider，真正寫入資料庫交給 ApiCollectionUi.save_provider。
        self.parent = parent
        self.row = row
        self.result: core.Provider | None = None
        self.window = Toplevel(parent)
        self.window.title("編輯資料源" if row else "新增資料源")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(620, 640)

        # 欄位變數集中在 dict，讓 save() 可以用同一份表單狀態組回 core.Provider。
        self.vars = {
            "provider_id": StringVar(value=row.provider_id if row else ""),
            "name": StringVar(value=row.name if row else ""),
            "owner": StringVar(value=row.owner if row else ""),
            "categories": StringVar(value=row.category_label if row else ""),
            "geographic_scope": StringVar(value=row.geographic_scope if row else "global"),
            "docs_url": StringVar(value=row.docs_url if row else ""),
            "api_base_url": StringVar(value=row.api_base_url if row else ""),
            "signup_url": StringVar(value=row.signup_url if row else ""),
            "auth_type": StringVar(value=row.auth_type if row else "unknown"),
            "key_env_var": StringVar(value=row.key_env_var if row else ""),
        }

        self._build()
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        fields = [
            ("資料源 ID", "provider_id"),
            ("名稱", "name"),
            ("擁有者", "owner"),
            ("類別（逗號分隔）", "categories"),
            ("範圍", "geographic_scope"),
            ("文件 URL", "docs_url"),
            ("API Base URL", "api_base_url"),
            ("註冊 URL", "signup_url"),
            ("認證類型", "auth_type"),
            ("API key 環境變數", "key_env_var"),
        ]
        for label, key in fields:
            ttk.Label(frame, text=label, style="DetailSection.TLabel").pack(anchor="w", pady=(8, 2))
            entry = ttk.Entry(frame, textvariable=self.vars[key], font=("Helvetica", 12))
            entry.pack(fill=X)
            if key == "provider_id" and self.row is not None:
                entry.configure(state="disabled")

        ttk.Label(frame, text="啟動器描述", style="DetailSection.TLabel").pack(anchor="w", pady=(12, 2))
        self.notes_text = Text(
            frame,
            height=7,
            wrap=WORD,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            padx=10,
            pady=10,
            font=("Helvetica", 11),
        )
        self.notes_text.pack(fill=BOTH, expand=True)
        if self.row and self.row.notes:
            self.notes_text.insert("1.0", self.row.notes)

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(16, 0))
        ttk.Button(buttons, text="儲存", style="Action.TButton", command=self.save).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(buttons, text="取消", style="Action.TButton", command=self.cancel).pack(side=RIGHT)

    def save(self) -> None:
        provider_id = self.vars["provider_id"].get().strip()
        name = self.vars["name"].get().strip()
        owner = self.vars["owner"].get().strip()
        docs_url = self.vars["docs_url"].get().strip()
        if not provider_id or not name or not owner or not docs_url:
            messagebox.showerror("資料不足", "Provider ID、名稱、Owner、Docs URL 都必須填寫。", parent=self.window)
            return
        categories = tuple(
            value.strip()
            for value in self.vars["categories"].get().split(",")
            if value.strip()
        )
        # 只在驗證通過後建立 Provider；呼叫端拿到 result 後才會決定是否寫入 catalog。
        self.result = core.Provider(
            provider_id=provider_id,
            name=name,
            owner=owner,
            categories=categories or ("custom",),
            geographic_scope=self.vars["geographic_scope"].get().strip() or "global",
            docs_url=docs_url,
            api_base_url=self.vars["api_base_url"].get().strip(),
            signup_url=self.vars["signup_url"].get().strip(),
            auth_type=self.vars["auth_type"].get().strip() or "unknown",
            key_env_var=self.vars["key_env_var"].get().strip(),
            notes=self.notes_text.get("1.0", END).strip(),
        )
        self.window.destroy()

    def cancel(self) -> None:
        self.result = None
        self.window.destroy()


class DatabaseClientSettingsDialog:
    def __init__(self, parent: Tk):
        self.parent = parent
        self.window = Toplevel(parent)
        self.window.title("資料庫工具接口設定")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(620, 420)
        # local integration config 是本機私有設定，開窗前先確保範本存在。
        core.ensure_local_integration_config()
        self.profiles = core.database_client_profiles()
        self.profile_var = StringVar()
        self.detail_var = StringVar()

        self._build()
        self.window.bind("<Escape>", lambda _event: self.window.destroy())
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        ttk.Label(frame, text="資料庫工具接口", style="DetailTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="選擇這台電腦預設要開啟的資料庫管理工具；實際路徑存放在本機設定檔，不會提交到 Git。",
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, pady=(8, 16))

        active = core.active_database_client()
        values = [self._profile_label(profile) for profile in self.profiles]
        current = self._profile_label(active) if active else (values[0] if values else "")
        self.profile_var.set(current)

        ttk.Label(frame, text="預設工具", style="DetailSection.TLabel").pack(anchor="w", pady=(0, 4))
        self.combo = ttk.Combobox(frame, values=values, textvariable=self.profile_var, state="readonly", font=("Helvetica", 12))
        self.combo.pack(fill=X)
        self.combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_details())

        ttk.Label(frame, text="目前接口", style="DetailSection.TLabel").pack(anchor="w", pady=(16, 4))
        self.detail_box = Text(
            frame,
            height=9,
            wrap=WORD,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            padx=12,
            pady=10,
            font=("Consolas", 11),
        )
        self.detail_box.pack(fill=BOTH, expand=True)
        self.refresh_details()

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(16, 0))
        ttk.Button(buttons, text="顯示本機設定檔", style="Action.TButton", command=self.open_config_file).pack(side=LEFT)
        ttk.Button(buttons, text="測試開啟", style="Action.TButton", command=self.open_selected_client).pack(side=LEFT, padx=(10, 0))
        ttk.Button(buttons, text="設為預設", style="Action.TButton", command=self.save_active_client).pack(side=RIGHT)
        ttk.Button(buttons, text="關閉", style="Action.TButton", command=self.window.destroy).pack(side=RIGHT, padx=(0, 10))

    def _profile_label(self, profile: core.DatabaseClientProfile | None) -> str:
        if profile is None:
            return ""
        enabled = "enabled" if profile.enabled else "disabled"
        return f"{profile.id} - {profile.label} ({enabled})"

    def selected_profile(self) -> core.DatabaseClientProfile | None:
        selected_id = self.profile_var.get().split(" - ", 1)[0].strip()
        return next((profile for profile in self.profiles if profile.id == selected_id), None)

    def refresh_details(self) -> None:
        profile = self.selected_profile()
        self.detail_box.configure(state="normal")
        self.detail_box.delete("1.0", END)
        if profile is None:
            self.detail_box.insert("1.0", "尚未設定資料庫工具。")
        else:
            self.detail_box.insert(
                "1.0",
                "\n".join(
                    [
                        f"id: {profile.id}",
                        f"label: {profile.label}",
                        f"kind: {profile.kind}",
                        f"enabled: {profile.enabled}",
                        f"command: {' '.join(profile.command)}",
                        "",
                        profile.notes or "notes: none",
                    ]
                ),
            )
        self.detail_box.configure(state="disabled")

    def save_active_client(self) -> None:
        profile = self.selected_profile()
        if profile is None:
            messagebox.showinfo("尚未選擇", "請先選擇一個資料庫工具接口。", parent=self.window)
            return
        try:
            core.set_active_database_client(profile.id)
        except Exception as exc:
            messagebox.showerror("無法儲存接口設定", str(exc), parent=self.window)
            return
        messagebox.showinfo("已更新", f"預設資料庫工具已設為：{profile.label}", parent=self.window)

    def open_selected_client(self) -> None:
        profile = self.selected_profile()
        if profile is None:
            messagebox.showinfo("尚未選擇", "請先選擇一個資料庫工具接口。", parent=self.window)
            return
        try:
            core.open_database_client(profile.id)
        except Exception as exc:
            messagebox.showerror("無法開啟資料庫工具", str(exc), parent=self.window)

    def open_config_file(self) -> None:
        path = core.local_integrations_path()
        core.ensure_local_integration_config()
        reveal_path_in_file_manager(path)


class DeveloperCliDialog:
    def __init__(self, ui: Any):
        # CLI 視窗需要主 UI 的翻譯、status_var 與 Tk after；封裝後主 UI 不再持有
        # subprocess / shlex 細節，避免 launcher_ui.py 持續膨脹。
        self.ui = ui
        self.root = ui.root
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("開發者 CLI", "Developer CLI"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("860x560")
        self.dialog.transient(self.root)

        self.command_var = StringVar(value="python APIkeys_collection.py --help")
        self._build()

    @staticmethod
    def split_command(command: str) -> list[str]:
        # shlex 是 CLI 字串到 argv 的安全邊界；保留成 helper 方便 headless 測試。
        return shlex.split(command)

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("開發者 CLI", "Developer CLI"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            self.dialog,
            text=self.ui.tr(
                f"工作目錄：{PROJECT_ROOT}\n輸入單次命令後按執行，輸出會顯示在下方。",
                f"Working directory: {PROJECT_ROOT}\nEnter a one-shot command and run it; output appears below.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 12))
        self.command_entry = ttk.Entry(self.dialog, textvariable=self.command_var, style="Search.TEntry")
        self.command_entry.pack(fill=X, padx=24, pady=(0, 12))
        self.output = Text(self.dialog, wrap=WORD, bg=COLORS["bg"], fg=COLORS["text"], relief="flat", padx=14, pady=12, font=("Consolas", 11))
        self.output.pack(fill=BOTH, expand=True, padx=24, pady=(0, 12))
        self.output.insert("1.0", self.ui.tr("尚未執行命令。", "No command has been run yet."))
        self.output.configure(state="disabled")

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        self.command_entry.bind("<Return>", lambda _event: self.run_command())
        ttk.Button(actions, text=self.ui.tr("執行", "Run"), style="Action.TButton", command=self.run_command).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("清空", "Clear"), style="Action.TButton", command=lambda: self.set_output("")).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)
        self.command_entry.focus_set()

    def append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert(END, text)
        self.output.see(END)
        self.output.configure(state="disabled")

    def set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", END)
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def run_command(self) -> None:
        command = self.command_var.get().strip()
        if not command:
            return
        try:
            args = self.split_command(command)
        except ValueError as exc:
            self.set_output(self.ui.tr(f"命令解析失敗：{exc}", f"Command parse failed: {exc}"))
            return
        job_key = ("developer_cli", "command", "")
        if single_flight_job_is_active(
            self,
            job_key,
            active_jobs_attr="developer_cli_active_jobs",
            on_duplicate=lambda: self.ui.status_var.set(
                self.ui.tr("CLI 命令仍在執行中，請等待目前命令完成。", "CLI command is still running; wait for it to finish.")
            ),
        ):
            return
        self.set_output(f"$ {command}\n\n")
        self.ui.status_var.set(self.ui.tr(f"正在執行 CLI：{command}", f"Running CLI: {command}"))
        start_single_flight_thread(
            self,
            job_key,
            self._run_command_worker,
            (args,),
            active_jobs_attr="developer_cli_active_jobs",
            active_jobs_lock_attr="developer_cli_active_jobs_lock",
            on_duplicate=lambda: self.ui.status_var.set(
                self.ui.tr("CLI 命令仍在執行中，請等待目前命令完成。", "CLI command is still running; wait for it to finish.")
            ),
        )

    def _run_command_worker(self, args: list[str]) -> None:
        try:
            completed = subprocess.run(
                args,
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                timeout=300,
                check=False,
            )
            text = ""
            if completed.stdout:
                text += completed.stdout
            if completed.stderr:
                text += ("\n[stderr]\n" if text else "[stderr]\n") + completed.stderr
            text += f"\n[exit code] {completed.returncode}\n"
            self.root.after(0, lambda: self.append_output(text))
            self.root.after(
                0,
                lambda: self.ui.status_var.set(
                    self.ui.tr(f"CLI 執行完成：exit {completed.returncode}", f"CLI finished: exit {completed.returncode}")
                ),
            )
        except Exception as exc:
            error = str(exc)
            self.root.after(0, lambda: self.append_output(f"\n[error] {error}\n"))
            self.root.after(0, lambda: self.ui.status_var.set(self.ui.tr(f"CLI 執行失敗：{error}", f"CLI failed: {error}")))


class ImportExistingTablePolicyDialog:
    def __init__(self, ui: Any):
        # 同名資料表策略是匯入流程的風險提示 UI；真正的 import/replace 行為仍在
        # pipeline/importer 層處理，這裡只負責把使用者選擇回傳給主 UI。
        self.ui = ui
        self.root = ui.root
        self.result: str | None = None
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("既有資料表處理方式", "Existing table policy"))
        self.dialog.transient(self.root)
        self.dialog.grab_set()
        self.dialog.geometry("620x340")
        self.dialog.configure(bg=COLORS["panel"])
        self.policy_var = StringVar(value=self.ui.preferred_import_existing_table_policy)

        self._build()
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)
        self.dialog.wait_window()

    @staticmethod
    def policy_option_values() -> tuple[str, str, str]:
        # option value 是 UI preference、pipeline 參數與測試共享的穩定契約。
        return ("rename", "skip", "replace")

    def _policy_options(self) -> tuple[tuple[str, str, str], ...]:
        return (
            (
                "rename",
                self.ui.tr("保留舊表，匯入成新表（建議）", "Keep old table and import as a new table (recommended)"),
                self.ui.tr("例如 table 會變成 table_2，不覆蓋既有資料。", "For example, table becomes table_2 without overwriting existing data."),
            ),
            (
                "skip",
                self.ui.tr("保留舊表，略過同名項目", "Keep old table and skip same-name items"),
                self.ui.tr("適合只想補匯尚未存在的資料。", "Use this when you only want to import missing tables."),
            ),
            (
                "replace",
                self.ui.tr("覆蓋同名表", "Replace same-name table"),
                self.ui.tr("會重建同名資料表；只有確定要刷新資料時才使用。", "This recreates the same-name table; use only when you mean to refresh it."),
            ),
        )

    def _build(self) -> None:
        frame = ttk.Frame(self.dialog, padding=18)
        frame.pack(fill=BOTH, expand=True)
        ttk.Label(
            frame,
            text=self.ui.tr(
                "如果 SQLite 裡已經有同名資料表，要怎麼處理？",
                "What should happen if SQLite already has a table with the same name?",
            ),
            font=("Helvetica", 14, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        for value, title, description in self._policy_options():
            row = ttk.Frame(frame)
            row.pack(fill=X, anchor="w", pady=5)
            ttk.Radiobutton(row, text=title, value=value, variable=self.policy_var).pack(anchor="w")
            ttk.Label(row, text=description, foreground=COLORS["muted"], wraplength=540).pack(anchor="w", padx=(24, 0), pady=(2, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=X, pady=(14, 0))
        ttk.Button(buttons, text=self.ui.tr("取消", "Cancel"), command=self.cancel).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(buttons, text=self.ui.tr("繼續", "Continue"), command=self.accept).pack(side=RIGHT)

    def cancel(self) -> None:
        self.result = None
        self.dialog.destroy()

    def accept(self) -> None:
        policy = normalized_ui_import_policy(self.policy_var.get())
        if policy == "replace":
            confirmed = messagebox.askyesno(
                self.ui.tr("確認覆蓋", "Confirm replace"),
                self.ui.tr(
                    "覆蓋會重建同名資料表。請確認這是你想要的行為。",
                    "Replace recreates the same-name table. Please confirm this is what you want.",
                ),
                parent=self.dialog,
            )
            if not confirmed:
                return
        self.ui.save_import_existing_table_policy_preference(policy)
        self.result = policy
        self.dialog.destroy()


class UiLanguageSettingsDialog:
    def __init__(self, ui: Any):
        # 語言設定會回寫本機 integration config，並通知主 UI 重建選單；
        # 因此用 ui 窄介面保存 callback，不讓 dialogs.py 直接知道主畫面內部布局。
        self.ui = ui
        self.root = ui.root
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("介面語言", "Interface language"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("460x220")
        self.dialog.transient(self.root)

        self.labels_by_code = UI_LANGUAGES
        self.codes_by_label = self.language_codes_by_label(self.labels_by_code)
        self.language_var = StringVar(
            value=self.labels_by_code.get(self.ui.ui_language, self.labels_by_code[DEFAULT_UI_LANGUAGE])
        )
        self._build()

    @staticmethod
    def language_codes_by_label(labels_by_code: dict[str, str]) -> dict[str, str]:
        # Combobox 只顯示人類可讀標籤；保存時必須穩定還原成 config code。
        return {label: code for code, label in labels_by_code.items()}

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("介面語言", "Interface language"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            self.dialog,
            text=self.ui.tr(
                "選擇 launcher 顯示語言。新開啟的視窗會立即使用；主畫面完整套用需要重新啟動。",
                "Choose the launcher display language. New dialogs use it immediately; restart for the whole main window.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))
        selector = ttk.Combobox(
            self.dialog,
            textvariable=self.language_var,
            values=tuple(self.labels_by_code.values()),
            state="readonly",
            font=("Helvetica", 12),
        )
        selector.pack(fill=X, padx=24, pady=(0, 18))
        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        ttk.Button(actions, text=self.ui.tr("儲存", "Save"), style="Action.TButton", command=self.save_language).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(actions, text=self.ui.tr("取消", "Cancel"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)

    def save_language(self) -> None:
        selected_code = self.codes_by_label.get(self.language_var.get(), DEFAULT_UI_LANGUAGE)
        config = core.ensure_local_integration_config()
        config["ui_language"] = selected_code
        save_integration_config(config)
        self.ui.ui_language = selected_code
        if hasattr(self.ui, "plan_import_policy_var"):
            self.ui.plan_import_policy_var.set(
                self.ui.import_existing_table_policy_status_label(self.ui.preferred_import_existing_table_policy)
            )
        self.ui._build_menu_bar()
        self.ui.status_var.set(self.ui.tr("介面語言已更新。主畫面完整套用需要重新啟動。", "Interface language updated. Restart for the full main window."))
        messagebox.showinfo(
            self.ui.tr("介面語言", "Interface language"),
            self.ui.tr(
                "已儲存介面語言設定。新開啟的視窗會先套用，主畫面完整套用請重新啟動。",
                "Language saved. New dialogs will use it now; restart for the full main window.",
            ),
            parent=self.dialog,
        )
        self.dialog.destroy()


class AiModelSettingsDialog:
    def __init__(self, ui: Any):
        # AI profile 選擇視窗只負責表格與按鈕調度；OAuth/API key 的實作仍留在
        # 主 UI 現有方法，避免一次搬動 credential 相關流程造成風險。
        self.ui = ui
        self.root = ui.root
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("AI 輔助模型", "AI assistant model"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("760x460")
        self.dialog.transient(self.root)
        self._build()

    @staticmethod
    def profile_row_values(
        profile: Any,
        *,
        active_profile_id: str,
        login_status: str,
        enabled_label: str,
        disabled_label: str,
    ) -> tuple[str, object, object, object, str, str, object]:
        # Treeview 欄位順序固定在 helper，讓測試能保護 UI row contract。
        return (
            "✓" if active_profile_id and active_profile_id == profile.id else "",
            profile.label,
            profile.kind,
            profile.model,
            login_status,
            enabled_label if profile.enabled else disabled_label,
            profile.notes,
        )

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("AI 輔助模型", "AI assistant model"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            self.dialog,
            text=self.ui.tr(
                "選擇產生資料源描述時要調用的 AI profile。登入或 API key 可以先存在各 profile 裡，但真正使用哪個模型由這裡決定。",
                "Choose which AI profile should be used for dataset descriptions. Login/API keys can be stored per profile, but this setting decides which one is called.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))
        self.table = ttk.Treeview(
            self.dialog,
            columns=("use", "label", "kind", "model", "login", "status", "notes"),
            show="headings",
            height=9,
            selectmode="browse",
        )
        for name, label, width in [
            ("use", self.ui.tr("使用", "Use"), 58),
            ("label", self.ui.tr("AI profile", "AI profile"), 150),
            ("kind", self.ui.tr("服務", "Service"), 110),
            ("model", self.ui.tr("模型", "Model"), 150),
            ("login", self.ui.tr("登入", "Login"), 150),
            ("status", self.ui.tr("狀態", "Status"), 80),
            ("notes", self.ui.tr("備註", "Notes"), 220),
        ]:
            self.table.heading(name, text=label)
            self.table.column(name, width=width, anchor="w", stretch=True)
        active = core.active_ai_profile()
        active_profile_id = active.id if active else ""
        for profile in core.ai_summary_profiles():
            self.table.insert(
                "",
                END,
                iid=profile.id,
                values=self.profile_row_values(
                    profile,
                    active_profile_id=active_profile_id,
                    login_status=self.ui.ai_profile_login_status(profile),
                    enabled_label=self.ui.tr("啟用", "Enabled"),
                    disabled_label=self.ui.tr("停用", "Disabled"),
                ),
            )
        self.table.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        if active:
            self.table.selection_set(active.id)
            self.table.focus(active.id)

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        self.table.bind("<Double-1>", lambda _event: self.use_selected())
        ttk.Button(actions, text=self.ui.tr("使用選取模型", "Use selected model"), style="Action.TButton", command=self.use_selected).pack(side=LEFT, padx=(0, 10))
        ttk.Button(
            actions,
            text=self.ui.tr("開發者 OAuth 設定", "Developer OAuth setup"),
            style="Action.TButton",
            command=lambda: self.ui.configure_oauth_client_for_selected(self.table, parent=self.dialog),
        ).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("未來：帳號登入", "Future: account sign-in"), style="Action.TButton", command=self.login_selected).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("保存 API key", "Save API key"), style="Action.TButton", command=self.paste_key_for_selected).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("顯示本機設定檔", "Reveal local config"), style="Action.TButton", command=self.ui.open_integration_config_file).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)

    def _selected_profile_id(self) -> str | None:
        selection = self.table.selection()
        if not selection:
            return None
        return str(selection[0])

    def _show_missing_selection(self) -> None:
        messagebox.showinfo(
            self.ui.tr("尚未選取", "Nothing selected"),
            self.ui.tr("請先選取一個 AI profile。", "Select an AI profile first."),
            parent=self.dialog,
        )

    def use_selected(self) -> None:
        selected_profile_id = self._selected_profile_id()
        if not selected_profile_id:
            self._show_missing_selection()
            return
        try:
            selected = core.set_active_ai_profile(selected_profile_id)
        except Exception as exc:
            messagebox.showerror(self.ui.tr("AI 模型設定失敗", "AI model setup failed"), str(exc), parent=self.dialog)
            return
        self.ui.selected_ai_profile_id = selected.id
        for item in self.table.get_children():
            values = list(self.table.item(item, "values"))
            values[0] = "✓" if item == selected.id else ""
            self.table.item(item, values=values)
        self.ui.status_var.set(self.ui.tr(f"AI 輔助模型已設定：{selected.label}", f"AI assistant model set: {selected.label}"))

    def login_selected(self) -> None:
        selected_profile_id = self._selected_profile_id()
        if not selected_profile_id:
            self._show_missing_selection()
            return
        self.ui.open_ai_profile_browser_login_dialog(selected_profile_id, parent=self.dialog)

    def paste_key_for_selected(self) -> None:
        selected_profile_id = self._selected_profile_id()
        self.ui.configure_ai_api_key_session(selected_profile_id)
        for item in self.table.get_children():
            profile = next((candidate for candidate in core.ai_summary_profiles() if candidate.id == item), None)
            if profile:
                values = list(self.table.item(item, "values"))
                values[4] = self.ui.ai_profile_login_status(profile)
                self.table.item(item, values=values)


class GoogleGeminiSettingsDialog:
    def __init__(self, ui: Any):
        # 這個 dialog 只負責 Google/Gemini 入口的說明與按鈕編排；credential 寫入、
        # OAuth browser flow 與 API key 儲存仍委派回主 UI，避免拆分時改到登入安全邊界。
        self.ui = ui
        self.root = ui.root
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("Gemini / Google 連線", "Gemini / Google connection"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("840x560")
        self.dialog.transient(self.root)
        self.dialog.grab_set()
        self._build()

    @staticmethod
    def account_provider_row_values(provider: Any) -> tuple[object, object, object, str]:
        # 帳號支援表格的欄位順序固定在 helper，讓 headless 測試不用真的開 Tk 視窗。
        return (
            provider.label,
            provider.auth_mode,
            provider.status,
            ", ".join(provider.capability_targets),
        )

    def _profile_status_texts(self) -> tuple[str, str]:
        profile = core.active_ai_profile()
        profile_text = (
            self.ui.tr(
                f"目前 AI profile：{profile.label} ({profile.kind})",
                f"Current AI profile: {profile.label} ({profile.kind})",
            )
            if profile
            else self.ui.tr("目前沒有啟用 AI profile。", "No active AI profile.")
        )
        gemini_profile = next((item for item in core.ai_summary_profiles() if item.id == "gemini_flash"), None)
        gemini_oauth = oauth_device_config_from_profile(gemini_profile) if gemini_profile else None
        if gemini_oauth:
            token_status, token_message = oauth_token_status(gemini_oauth.token_store, label=gemini_profile.label)
        else:
            token_status, token_message = google_oauth_token_status()
        token_text = self.ui.tr(
            f"Gemini / Google token：{token_status} - {token_message}",
            f"Gemini / Google token: {token_status} - {token_message}",
        )
        return profile_text, token_text

    def _connection_message(self, profile_text: str, token_text: str) -> str:
        # 長說明文字留在 dialog class，主 UI 不需要知道這個產品教育文案如何排版。
        return self.ui.tr(
            "\n".join(
                [
                    "這裡是 Google / Gemini 連線入口。",
                    "白話說：它不是展示用空殼，但 Google 帳號登入還需要專案端把官方 OAuth App 配好。",
                    "一般網站能直接讓你選 Google 帳號，是因為網站已經替使用者處理好 OAuth App 身分；使用者不該被要求貼 Client ID。",
                    "這裡只負責登入、token 與 Google 相關設定；真正要調用哪個 AI，請到「整合 > AI 輔助模型選擇」選。",
                    "",
                    profile_text,
                    token_text,
                    "",
                    "目前支援：",
                    "1. Google 帳號瀏覽器登入：專案 OAuth App 配好後，才會打開 Google 授權頁並把 token 存在本機 private state。",
                    "2. Google QR/device-code：同樣需要官方 OAuth App 與 device-code 端點，不能在缺設定時硬造。",
                    "3. Gemini API key：作為目前 MVP 主路線，保存到本機 private state，下次啟動自動載入。",
                    "",
                    "目前開發版不會要求一般使用者貼 OAuth Client ID；那是專案/開發者要負責配置的事情。",
                ]
            ),
            "\n".join(
                [
                    "This panel is the Google/Gemini connection entry point.",
                    "Plainly: it is not a fake shell, but Google account login still needs the project to provide an official OAuth app.",
                    "Normal web services can let you choose a Google account because the service already owns the OAuth app identity; users should not be asked to paste a Client ID.",
                    "It handles login, tokens, and Google-related setup only. Choose the model under Integrations > AI assistant model selection.",
                    "",
                    profile_text,
                    token_text,
                    "",
                    "Currently supported:",
                    "1. Google browser account login: after the project OAuth app is configured, opens Google's authorization page and stores the token under local private state.",
                    "2. Google QR/device-code: also needs an official OAuth app and device-code endpoint; it cannot be invented when setup is missing.",
                    "3. Gemini API key: the current MVP path, saved under local private state and loaded automatically next launch.",
                    "",
                    "This development build will not ask normal users to paste an OAuth Client ID; that is a project/developer responsibility.",
                ]
            ),
        )

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("Gemini / Google 連線", "Gemini / Google connection"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        profile_text, token_text = self._profile_status_texts()
        readiness_text = self.ui.tr(
            "目前狀態：AI 生成管線已存在；Google 帳號登入需要專案端先配置官方 OAuth App，才會像一般網站一樣開瀏覽器選帳號或掃碼。",
            "Current status: AI generation exists; Google account login needs the project to provide an official OAuth app before it can open a normal browser account chooser or QR flow.",
        )
        ttk.Label(self.dialog, text=readiness_text, style="DetailMuted.TLabel", wraplength=760).pack(anchor="w", padx=24, pady=(0, 10))
        text = Text(self.dialog, height=12, wrap=WORD, bg=COLORS["bg"], fg=COLORS["text"], relief="flat", padx=16, pady=14, font=("Helvetica", 11))
        text.pack(fill=X, expand=False, padx=24, pady=(0, 14))
        text.insert("1.0", self._connection_message(profile_text, token_text))
        text.configure(state="disabled")

        providers = ttk.Treeview(self.dialog, columns=("provider", "mode", "status", "targets"), show="headings", height=3)
        for name, label, width in [
            ("provider", self.ui.tr("帳號", "Account"), 110),
            ("mode", self.ui.tr("登入模式", "Login mode"), 140),
            ("status", self.ui.tr("狀態", "Status"), 90),
            ("targets", self.ui.tr("能力目標", "Capability targets"), 230),
        ]:
            providers.heading(name, text=label)
            providers.column(name, width=width, anchor="w", stretch=True)
        for provider in DEFAULT_ACCOUNT_PROVIDERS:
            providers.insert("", END, values=self.account_provider_row_values(provider))
        providers.pack(fill=X, padx=24, pady=(0, 14))

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))
        primary_actions = ttk.Frame(actions, style="Panel.TFrame")
        primary_actions.pack(fill=X, pady=(0, 8))
        secondary_actions = ttk.Frame(actions, style="Panel.TFrame")
        secondary_actions.pack(fill=X)

        # 主要按鈕走 MVP API key 與模型設定；中期 OAuth 按鈕仍保留但交由既有安全流程處理。
        ttk.Button(primary_actions, text=self.ui.tr("保存 Gemini API key 並啟用", "Save Gemini API key and enable"), style="Action.TButton", command=lambda: self.ui.configure_ai_api_key_session("gemini_flash", parent=self.dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(primary_actions, text=self.ui.tr("AI 模型設定", "AI model settings"), style="Action.TButton", command=self.ui.open_ai_model_settings).pack(side=LEFT, padx=(0, 10))
        ttk.Button(primary_actions, text=self.ui.tr("產生目前資料源描述", "Generate selected source description"), style="Action.TButton", command=self.ui.generate_active_summary).pack(side=LEFT, padx=(0, 10))
        ttk.Button(primary_actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)
        ttk.Button(secondary_actions, text=self.ui.tr("中期：Google 帳號登入", "Mid-term: Google account login"), style="Action.TButton", command=lambda: self.ui.open_ai_profile_browser_login_dialog("gemini_flash", parent=self.dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(secondary_actions, text=self.ui.tr("中期：QR / 裝置碼", "Mid-term: QR / device code"), style="Action.TButton", command=lambda: self.ui.open_ai_profile_login_dialog("gemini_flash", parent=self.dialog)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(secondary_actions, text=self.ui.tr("開發期備用：Google AI Studio", "Development fallback: Google AI Studio"), style="Action.TButton", command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey")).pack(side=LEFT, padx=(0, 10))
        ttk.Button(secondary_actions, text=self.ui.tr("顯示本機整合設定檔", "Reveal local integration config"), style="Action.TButton", command=self.ui.open_integration_config_file).pack(side=LEFT, padx=(0, 10))


class StartupEnvironmentChecksDialog:
    def __init__(self, ui: Any):
        # 啟動環境檢查只讀取 core startup checks，適合維持成薄 dialog。
        self.ui = ui
        self.root = ui.root
        self.checks = core.run_startup_checks(DB_PATH)
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("啟動環境檢查", "Startup environment checks"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("760x520")
        self.dialog.transient(self.root)
        self._build()

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("啟動環境檢查", "Startup environment checks"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        table = ttk.Treeview(self.dialog, columns=("name", "status", "detail"), show="headings", height=14)
        for name, label, width in [
            ("name", self.ui.tr("檢查項目", "Check"), 190),
            ("status", self.ui.tr("狀態", "Status"), 90),
            ("detail", self.ui.tr("細節", "Detail"), 460),
        ]:
            table.heading(name, text=label)
            table.column(name, width=width, anchor="w", stretch=True)
        for check in self.checks:
            table.insert("", END, values=(check.name, check.status, check.detail))
        table.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)


class RecentEventLogsDialog:
    def __init__(self, ui: Any):
        # 事件紀錄視窗是觀測/交接工具；抽出後 launcher_ui.py 不再知道 JSONL 表格細節。
        self.ui = ui
        self.root = ui.root
        self.events = latest_events(100)
        self.event_by_iid: dict[str, dict[str, object]] = {}
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("最近事件紀錄", "Recent event logs"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("980x620")
        self.dialog.transient(self.root)
        self._build()

    @staticmethod
    def event_row_values(event: dict[str, object]) -> tuple[object, object, object, object, object]:
        # Treeview 欄位順序集中在這裡，避免未來調整欄位時漏改測試與插入邏輯。
        return (
            event.get("timestamp", ""),
            event.get("level", ""),
            event.get("component", ""),
            event.get("event", ""),
            event.get("message", ""),
        )

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("最近事件紀錄", "Recent event logs"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            self.dialog,
            text=self.ui.tr(
                "Launcher 和未來 Agent 會用這些 JSONL 結構化事件做除錯與交接。",
                "Structured JSONL events used by the launcher and future agents for debugging and handoff.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))

        body = ttk.Frame(self.dialog, style="Panel.TFrame")
        body.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        self.table = ttk.Treeview(body, columns=("time", "level", "component", "event", "message"), show="headings", height=10)
        for name, label, width in [
            ("time", self.ui.tr("時間", "Time"), 180),
            ("level", self.ui.tr("層級", "Level"), 80),
            ("component", self.ui.tr("元件", "Component"), 120),
            ("event", self.ui.tr("事件", "Event"), 180),
            ("message", self.ui.tr("訊息", "Message"), 360),
        ]:
            self.table.heading(name, text=label)
            self.table.column(name, width=width, anchor="w", stretch=True)
        self.detail = Text(body, height=9, bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"], wrap=WORD, relief="flat")
        self.detail.configure(state="disabled")

        for index, event in enumerate(self.events):
            iid = str(index)
            self.event_by_iid[iid] = event
            self.table.insert("", END, iid=iid, values=self.event_row_values(event))

        self.table.bind("<<TreeviewSelect>>", self.show_selected_log)
        self.table.pack(fill=BOTH, expand=True, pady=(0, 10))
        self.detail.pack(fill=BOTH, expand=True)
        self.show_selected_log()

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        event_path = log_file(EVENT_LOG_NAME)
        if event_path.exists():
            ttk.Button(
                actions,
                text=self.ui.tr("開啟 JSONL 檔案", "Open JSONL file"),
                style="Action.TButton",
                command=lambda: webbrowser.open(event_path.as_uri()),
            ).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)

    def show_selected_log(self, _event: object | None = None) -> None:
        selection = self.table.selection()
        selected = self.event_by_iid.get(str(selection[0])) if selection else None
        self.detail.configure(state="normal")
        self.detail.delete("1.0", END)
        if selected is None:
            self.detail.insert(
                END,
                self.ui.tr("尚未選取事件。", "No event selected.") if self.events else self.ui.tr("目前沒有結構化事件紀錄。", "No structured log events yet."),
            )
        else:
            self.detail.insert(END, json.dumps(selected, ensure_ascii=False, indent=2, sort_keys=True))
        self.detail.configure(state="disabled")


class DatasetCandidateReviewDialog:
    def __init__(self, ui: Any):
        # 資料集候選審核會改變 registry 內的 candidate_status，但不下載、不匯入、
        # 也不把 crawler 結果直接升格成正式 catalog；這個 class 固定住 review-only 邊界。
        self.ui = ui
        self.root = ui.root
        self.status_filter_var = StringVar(value="needs_review")
        self.summary_var = StringVar(value="")
        self.candidates_by_uid: dict[str, core.Dataset] = {}
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("資料集候選審核", "Dataset candidate review"))
        self.dialog.geometry("1180x720")
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.transient(self.root)
        self._build()

    @staticmethod
    def candidate_row_values(dataset: core.Dataset) -> tuple[object, object, object, object, object, object]:
        # Treeview 欄位是審核列表與測試共用的穩定契約；調整欄位順序前要同步 UI 測試。
        metadata = dataset.metadata
        return (
            metadata.get("candidate_status", ""),
            dataset.provider_id,
            dataset.title,
            metadata.get("data_family", dataset.data_type),
            dataset.native_format,
            str(metadata.get("confidence", "")),
        )

    @staticmethod
    def candidate_detail_text(dataset: core.Dataset, tr: Any) -> str:
        # detail pane 要把 crawler evidence 原樣攤開，讓人類可以判斷來源是否可信，
        # 不要只顯示漂亮標題，否則候選審核會變成無法追溯的黑盒子。
        metadata = dataset.metadata
        evidence = metadata.get("evidence")
        evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2) if evidence else "-"
        details = [
            f"{tr('標題', 'Title')}: {dataset.title}",
            f"{tr('提供商', 'Provider')}: {dataset.provider_id}",
            f"{tr('資料集 ID', 'Dataset ID')}: {dataset.dataset_id}",
            f"{tr('審核狀態', 'Review status')}: {metadata.get('candidate_status', '-')}",
            f"{tr('資料類型', 'Data family')}: {metadata.get('data_family', dataset.data_type or '-')}",
            f"{tr('建議儲存', 'Storage hint')}: {metadata.get('storage_hint', '-')}",
            f"{tr('分析提示', 'Analysis hint')}: {metadata.get('analysis_hint', '-')}",
            f"{tr('檢視提示', 'Viewer hint')}: {metadata.get('viewer_hint', '-')}",
            f"{tr('格式', 'Format')}: {dataset.native_format or '-'}",
            f"{tr('範圍', 'Scope')}: {dataset.geographic_scope or '-'}",
            f"{tr('來源', 'Source')}: {metadata.get('source_url') or dataset.landing_url or dataset.api_url or '-'}",
            "",
            tr("證據 / crawler 摘要:", "Evidence / crawler summary:"),
            evidence_text,
        ]
        return "\n".join(details)

    def _build(self) -> None:
        frame = ttk.Frame(self.dialog, style="App.TFrame", padding=24)
        frame.pack(fill=BOTH, expand=True)
        ttk.Label(frame, text=self.ui.tr("資料集候選審核", "Dataset candidate review"), style="DetailTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=self.ui.tr(
                "Crawler 找到的是候選 metadata；審核只會改 launcher registry 狀態，不會下載或改動資料本體。",
                "Crawler results are metadata candidates; review changes launcher registry state only, without downloading or editing source data.",
            ),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(8, 16))

        controls = ttk.Frame(frame, style="App.TFrame")
        controls.pack(fill=X, pady=(0, 12))
        ttk.Label(controls, text=self.ui.tr("狀態", "Status"), style="DetailSection.TLabel").pack(side=LEFT, padx=(0, 8))
        status_box = ttk.Combobox(
            controls,
            textvariable=self.status_filter_var,
            values=("needs_review", "approved", "planned", "rejected", "all"),
            state="readonly",
            width=18,
        )
        status_box.pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text=self.ui.tr("重新載入", "Reload"), style="Action.TButton", command=self.load_candidates).pack(side=LEFT)
        ttk.Label(controls, textvariable=self.summary_var, style="Muted.TLabel").pack(side=LEFT, padx=(16, 0))

        body = ttk.Frame(frame, style="App.TFrame")
        body.pack(fill=BOTH, expand=True)
        table_wrap = ttk.Frame(body, style="Panel.TFrame")
        table_wrap.pack(side=LEFT, fill=BOTH, expand=True)
        columns = ("status", "provider", "title", "family", "format", "confidence")
        self.candidate_tree = ttk.Treeview(table_wrap, columns=columns, show="headings", selectmode="browse")
        for name, label, width, anchor in [
            ("status", self.ui.tr("審核狀態", "Status"), 120, "center"),
            ("provider", self.ui.tr("提供商", "Provider"), 190, "w"),
            ("title", self.ui.tr("資料集", "Dataset"), 360, "w"),
            ("family", self.ui.tr("資料類型", "Data family"), 170, "w"),
            ("format", self.ui.tr("格式", "Format"), 100, "center"),
            ("confidence", self.ui.tr("信心", "Confidence"), 80, "center"),
        ]:
            self.candidate_tree.heading(name, text=label)
            self.candidate_tree.column(name, width=width, anchor=anchor, stretch=True)
        candidate_scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.candidate_tree.yview)
        self.candidate_tree.configure(yscrollcommand=candidate_scroll.set)
        self.candidate_tree.pack(side=LEFT, fill=BOTH, expand=True)
        candidate_scroll.pack(side=RIGHT, fill=Y)

        detail_wrap = ttk.Frame(body, style="Panel.TFrame", width=420)
        detail_wrap.pack(side=RIGHT, fill=Y, padx=(16, 0))
        detail_wrap.pack_propagate(False)
        ttk.Label(detail_wrap, text=self.ui.tr("候選細節", "Candidate details"), style="DetailSection.TLabel").pack(anchor="w", padx=16, pady=(16, 8))
        self.detail_box = Text(
            detail_wrap,
            height=22,
            wrap=WORD,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            relief="flat",
            padx=14,
            pady=12,
            font=("Helvetica", 11),
        )
        self.detail_box.pack(fill=BOTH, expand=True, padx=16, pady=(0, 12))

        actions = ttk.Frame(detail_wrap, style="Panel.TFrame")
        actions.pack(fill=X, padx=16, pady=(0, 16))
        ttk.Button(actions, text=self.ui.tr("開啟來源", "Open source"), style="Action.TButton", command=self.open_selected_source).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text=self.ui.tr("標記可用", "Approve"), style="Action.TButton", command=lambda: self.mark_selected("approved")).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text=self.ui.tr("加入下載計畫", "Add to plan"), style="Action.TButton", command=self.add_selected_to_plan).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text=self.ui.tr("拒絕候選", "Reject"), style="Action.TButton", command=lambda: self.mark_selected("rejected")).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(fill=X)

        status_box.bind("<<ComboboxSelected>>", lambda _event: self.load_candidates())
        self.candidate_tree.bind("<<TreeviewSelect>>", lambda _event: self.render_candidate_detail(self.selected_candidate()))
        self.load_candidates()

    def selected_candidate(self) -> core.Dataset | None:
        selection = self.candidate_tree.selection()
        if not selection:
            return None
        return self.candidates_by_uid.get(str(selection[0]))

    def render_candidate_detail(self, dataset: core.Dataset | None) -> None:
        self.detail_box.configure(state="normal")
        self.detail_box.delete("1.0", END)
        if dataset is None:
            self.detail_box.insert("1.0", self.ui.tr("請先選取一個候選資料集。", "Select a dataset candidate first."))
            self.detail_box.configure(state="disabled")
            return
        self.detail_box.insert("1.0", self.candidate_detail_text(dataset, self.ui.tr))
        self.detail_box.configure(state="disabled")

    def load_candidates(self) -> None:
        conn = self.ui._connect()
        try:
            candidates = core.ApiCatalogRepository(conn).list_dataset_candidates(self.status_filter_var.get())
        except Exception as exc:
            messagebox.showerror(self.ui.tr("無法讀取候選", "Could not load candidates"), str(exc), parent=self.dialog)
            return
        finally:
            conn.close()
        self.candidates_by_uid.clear()
        for item in self.candidate_tree.get_children():
            self.candidate_tree.delete(item)
        for dataset in candidates:
            self.candidates_by_uid[dataset.dataset_uid] = dataset
            self.candidate_tree.insert("", END, iid=dataset.dataset_uid, values=self.candidate_row_values(dataset))
        self.summary_var.set(self.ui.tr(f"共 {len(candidates)} 個候選", f"{len(candidates)} candidates"))
        first = self.candidate_tree.get_children()
        if first:
            self.candidate_tree.selection_set(first[0])
            self.candidate_tree.focus(first[0])
            self.render_candidate_detail(self.candidates_by_uid.get(str(first[0])))
        else:
            self.render_candidate_detail(None)

    def mark_selected(self, status: str) -> None:
        dataset = self.selected_candidate()
        if dataset is None:
            messagebox.showinfo(self.ui.tr("尚未選取", "Nothing selected"), self.ui.tr("請先選取一個候選資料集。", "Select a dataset candidate first."), parent=self.dialog)
            return
        conn = self.ui._connect()
        try:
            core.ApiCatalogRepository(conn).mark_dataset_candidate_status(dataset.dataset_uid, status, reviewed_by="tk-ui")
        finally:
            conn.close()
        self.ui.status_var.set(self.ui.tr(f"已更新候選狀態：{dataset.title} -> {status}", f"Candidate updated: {dataset.title} -> {status}"))
        self.load_candidates()

    def add_selected_to_plan(self) -> None:
        dataset = self.selected_candidate()
        if dataset is None:
            messagebox.showinfo(self.ui.tr("尚未選取", "Nothing selected"), self.ui.tr("請先選取一個候選資料集。", "Select a dataset candidate first."), parent=self.dialog)
            return
        row = self.ui.row_by_provider_id(dataset.provider_id)
        if row is None:
            messagebox.showerror(
                self.ui.tr("缺少提供商", "Missing provider"),
                self.ui.tr("這個候選資料集的提供商不在目前 catalog 裡，請先同步或新增提供商。", "This candidate's provider is not in the current catalog. Sync or add the provider first."),
                parent=self.dialog,
            )
            return
        options = core.version_options_for_dataset(dataset)
        if not options:
            messagebox.showinfo(self.ui.tr("沒有版本", "No version"), self.ui.tr("這個候選資料集還沒有可加入計畫的版本資訊。", "This candidate does not expose a plannable version yet."), parent=self.dialog)
            return
        self.ui.add_provider_version_to_plan(dataset.provider_id, options[0])
        conn = self.ui._connect()
        try:
            core.ApiCatalogRepository(conn).mark_dataset_candidate_status(
                dataset.dataset_uid,
                "planned",
                reviewed_by="tk-ui",
                note="Added to current UI download plan.",
            )
        finally:
            conn.close()
        self.ui.update_download_plan_panel()
        self.ui.status_var.set(self.ui.tr(f"已加入下載計畫：{dataset.title}", f"Added to download plan: {dataset.title}"))
        self.load_candidates()

    def open_selected_source(self) -> None:
        dataset = self.selected_candidate()
        if dataset is None:
            return
        metadata = dataset.metadata
        url = str(metadata.get("source_url") or dataset.landing_url or dataset.api_url or "").strip()
        if not url:
            messagebox.showinfo(self.ui.tr("沒有來源連結", "No source URL"), self.ui.tr("這個候選資料集沒有可開啟的來源連結。", "This candidate does not have an openable source URL."), parent=self.dialog)
            return
        webbrowser.open(url)


class ProviderCandidateReviewDialog:
    def __init__(self, ui: Any, path: Any, candidates: list[dict[str, object]]):
        # Provider candidate review 只能寫入 ignored local config；正式 catalog promotion 仍必須走 crawler audit。
        # 這個 class 接手 Toplevel 與 callback，讓 launcher_ui.py 保留入口調度，不再承載整個視窗生命週期。
        self.ui = ui
        self.root = ui.root
        self.path = path
        self.candidates = candidates
        self.candidate_by_iid: dict[str, dict[str, object]] = {}
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("Provider 候選審核", "Provider candidate review"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("1100x660")
        self.dialog.transient(self.root)
        self._build()

    @staticmethod
    def candidate_row_values(candidate: dict[str, object]) -> tuple[object, object, object, object, object]:
        # Treeview 欄位順序固定，讓 headless tests 可以檢查 UI table 不會因顯示文案調整而破壞。
        return (
            candidate.get("provider_id", ""),
            candidate.get("name", ""),
            candidate.get("confidence", ""),
            candidate.get("auth_type", ""),
            candidate.get("docs_url", ""),
        )

    @staticmethod
    def candidate_detail_text(candidate: object, tr: Any) -> str:
        # Detail pane 明確標示 review-only 邊界，避免使用者誤以為 candidate 已經被安裝或驗證。
        data = candidate if isinstance(candidate, dict) else {}
        categories = data.get("categories", [])
        if isinstance(categories, (list, tuple)):
            category_text = ", ".join(str(value) for value in categories) or "-"
        else:
            category_text = str(categories or "-")
        fields = [
            (tr("Provider ID", "Provider ID"), data.get("provider_id")),
            (tr("名稱", "Name"), data.get("name")),
            (tr("Owner", "Owner"), data.get("owner")),
            (tr("分類", "Categories"), category_text),
            (tr("地理範圍", "Geographic scope"), data.get("geographic_scope")),
            (tr("信心分數", "Confidence"), data.get("confidence")),
            (tr("來源 URL", "Source URL"), data.get("source_url")),
            (tr("文件 URL", "Docs URL"), data.get("docs_url")),
            (tr("API Base URL", "API Base URL"), data.get("api_base_url")),
            (tr("申請 URL", "Signup URL"), data.get("signup_url")),
            (tr("Auth type", "Auth type"), data.get("auth_type")),
            (tr("Key env var", "Key env var"), data.get("key_env_var")),
            (tr("備註", "Notes"), data.get("notes")),
        ]
        lines = [f"{label}: {value or '-'}" for label, value in fields]
        evidence = data.get("evidence")
        if isinstance(evidence, (list, tuple)) and evidence:
            lines.extend(["", tr("證據：", "Evidence:")])
            lines.extend(f"- {item}" for item in evidence[:8])
        lines.extend(
            [
                "",
                tr(
                    "這只是 provider/source 候選審核資料，不代表 provider 已被納管、安裝或通過授權。",
                    "This is provider/source candidate review information only; it does not mean the provider is managed, installed, or authenticated.",
                ),
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def provider_seed_from_candidate(candidate: object) -> ProviderSeed:
        # 只把具備最低邊界資訊的 candidate 轉成 ignored local seed；缺少 owner/source 等欄位就留在 review。
        data = candidate if isinstance(candidate, dict) else {}
        provider_id = str(data.get("provider_id") or "").strip()
        name = str(data.get("name") or "").strip()
        owner = str(data.get("owner") or "").strip()
        homepage_url = str(data.get("source_url") or data.get("docs_url") or data.get("api_base_url") or "").strip()
        missing = [
            label
            for label, value in (
                ("provider_id", provider_id),
                ("name", name),
                ("owner", owner),
                ("source_url/docs_url/api_base_url", homepage_url),
            )
            if not value
        ]
        if missing:
            raise ValueError("missing required candidate fields: " + ", ".join(missing))
        categories = tuple(str(value).strip() for value in data.get("categories", []) if str(value).strip())
        return ProviderSeed(
            provider_id=provider_id,
            name=name,
            owner=owner,
            categories=categories or ("custom",),
            geographic_scope=str(data.get("geographic_scope") or "global").strip() or "global",
            homepage_url=homepage_url,
            docs_url=str(data.get("docs_url") or "").strip(),
            api_base_url=str(data.get("api_base_url") or "").strip(),
            signup_url=str(data.get("signup_url") or "").strip(),
            expected_auth_type=str(data.get("auth_type") or "unknown").strip() or "unknown",
        )

    @staticmethod
    def provider_dataset_source_from_candidate(candidate: object):
        # source draft 比 provider seed 更嚴格，必須能推導出 crawler type 與 endpoint 才能寫入 ignored local config。
        data = candidate if isinstance(candidate, dict) else {}
        return dataset_source_from_provider_candidate(data)

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("Provider 候選審核", "Provider candidate review"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            self.dialog,
            text=self.ui.tr(
                f"來源：{self.path}；候選 {len(self.candidates)} 筆。此面板只做 review，不寫入正式 catalog。",
                f"Source: {self.path}; {len(self.candidates)} candidates. This panel is review-only and does not write the official catalog.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))

        body = ttk.Frame(self.dialog, style="Panel.TFrame")
        body.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        self.tree = ttk.Treeview(body, columns=("provider_id", "name", "confidence", "auth_type", "docs_url"), show="headings", height=12)
        for name, label, width in [
            ("provider_id", self.ui.tr("Provider ID", "Provider ID"), 190),
            ("name", self.ui.tr("名稱", "Name"), 250),
            ("confidence", self.ui.tr("信心", "Confidence"), 80),
            ("auth_type", self.ui.tr("Auth", "Auth"), 120),
            ("docs_url", self.ui.tr("文件", "Docs"), 360),
        ]:
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, anchor="w", stretch=True)
        self.detail = Text(body, height=12, bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"], wrap=WORD, relief="flat")
        self.detail.configure(state="disabled")
        self.tree.pack(fill=BOTH, expand=True, side=LEFT, padx=(0, 12))
        self.detail.pack(fill=BOTH, expand=True, side=LEFT)

        for index, candidate in enumerate(self.candidates):
            iid = str(index)
            self.candidate_by_iid[iid] = candidate
            self.tree.insert("", END, iid=iid, values=self.candidate_row_values(candidate))

        self.tree.bind("<<TreeviewSelect>>", self.render_selected)
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
        self.render_selected()

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        ttk.Button(actions, text=self.ui.tr("寫入 source 草稿", "Write source draft"), style="Action.TButton", command=self.write_selected_local_source).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("寫入本機 seed", "Write local seed"), style="Action.TButton", command=self.write_selected_local_seed).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("開來源", "Open source"), style="Action.TButton", command=lambda: self.open_selected_url("source_url")).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("開文件", "Open docs"), style="Action.TButton", command=lambda: self.open_selected_url("docs_url")).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("開 Review JSON", "Open review JSON"), style="Action.TButton", command=lambda: webbrowser.open(self.path.as_uri())).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)

    def selected_candidate(self) -> dict[str, object] | None:
        selection = self.tree.selection()
        return self.candidate_by_iid.get(str(selection[0])) if selection else None

    def render_selected(self, _event: object | None = None) -> None:
        candidate = self.selected_candidate()
        self.detail.configure(state="normal")
        self.detail.delete("1.0", END)
        self.detail.insert(END, self.candidate_detail_text(candidate or {}, self.ui.tr))
        self.detail.configure(state="disabled")

    def open_selected_url(self, key: str) -> None:
        candidate = self.selected_candidate()
        url = str((candidate or {}).get(key) or "").strip()
        if not url:
            messagebox.showinfo(
                self.ui.tr("Provider 候選", "Provider candidates"),
                self.ui.tr("這個候選沒有可開啟的 URL。", "This candidate does not have an openable URL."),
                parent=self.dialog,
            )
            return
        webbrowser.open(url)

    def write_selected_local_seed(self) -> None:
        candidate = self.selected_candidate()
        if candidate is None:
            messagebox.showinfo(self.ui.tr("Provider 候選", "Provider candidates"), self.ui.tr("請先選取一筆 provider 候選。", "Select a provider candidate first."), parent=self.dialog)
            return
        try:
            seed = self.provider_seed_from_candidate(candidate)
        except ValueError as exc:
            messagebox.showerror(self.ui.tr("Provider 候選", "Provider candidates"), self.ui.tr(f"無法寫入本機 seed：{exc}", f"Could not write local seed: {exc}"), parent=self.dialog)
            return
        output_path = local_config_file(LOCAL_SEEDS_NAME)
        append_discovery_seed(output_path, seed)
        log_event(
            "provider_candidate_local_seed_written",
            "Provider candidate written to ignored local discovery seed.",
            component="ui.provider_discovery",
            context={"provider_id": seed.provider_id, "output_path": str(output_path)},
        )
        self.ui.status_var.set(self.ui.tr(f"已寫入本機 provider seed：{seed.provider_id}", f"Local provider seed written: {seed.provider_id}"))
        messagebox.showinfo(
            self.ui.tr("Provider 候選", "Provider candidates"),
            self.ui.tr(
                f"已寫入 ignored seed：{output_path}\n\n正式 catalog 尚未變更；下一步請先執行本機 discovery 草稿審核。",
                f"Wrote ignored local seed: {output_path}\n\nThe official catalog was not changed; next run \"Audit local discovery drafts\" before promotion.",
            ),
            parent=self.dialog,
        )

    def write_selected_local_source(self) -> None:
        candidate = self.selected_candidate()
        if candidate is None:
            messagebox.showinfo(self.ui.tr("Provider 候選", "Provider candidates"), self.ui.tr("請先選取一筆 provider 候選。", "Select a provider candidate first."), parent=self.dialog)
            return
        try:
            source = self.provider_dataset_source_from_candidate(candidate)
        except ValueError as exc:
            messagebox.showerror(
                self.ui.tr("Provider 候選", "Provider candidates"),
                self.ui.tr(
                    f"無法寫入 source 草稿：{exc}\n\n這個候選尚未有支援的 crawler type 與 endpoint，所以保留在 review。",
                    f"Could not write local source draft: {exc}\n\nThis candidate does not yet have a supported crawler type and endpoint, so it stays in review.",
                ),
                parent=self.dialog,
            )
            return
        output_path = local_config_file(LOCAL_DATASET_DISCOVERY_SOURCES_NAME)
        append_dataset_discovery_source(output_path, source)
        log_event(
            "provider_candidate_local_source_written",
            "Provider candidate written to ignored local dataset discovery source draft.",
            component="ui.provider_discovery",
            context={"provider_id": source.provider_id, "source_id": source.source_id, "source_type": source.source_type, "output_path": str(output_path)},
        )
        self.ui.status_var.set(self.ui.tr(f"已寫入本機 source 草稿：{source.source_id}", f"Local source draft written: {source.source_id}"))
        messagebox.showinfo(
            self.ui.tr("Provider 候選", "Provider candidates"),
            self.ui.tr(
                f"已寫入 ignored dataset source 草稿：{output_path}\n\nSource: {source.source_id}\nType: {source.source_type}\n\n正式 catalog 尚未變更；下一步請先執行本機 discovery 草稿審核。",
                f"Wrote ignored local dataset source draft: {output_path}\n\nSource: {source.source_id}\nType: {source.source_type}\n\nThe official catalog was not changed; next run \"Audit local discovery drafts\" before promotion.",
            ),
            parent=self.dialog,
        )


class AdapterReviewDialog:
    def __init__(self, ui: Any, review_items: list[AdapterReviewItem]):
        # Adapter review panel 是 review-only 視窗；它只呈現待辦與開 URL，
        # 真正解析 plan 的流程仍委派回主 UI 的既有 resolver 入口。
        self.ui = ui
        self.root = ui.root
        self.review_items = review_items
        self.item_by_iid: dict[str, AdapterReviewItem] = {}
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("Adapter 待辦", "Adapter review queue"))
        self.dialog.geometry("980x560")
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.transient(self.root)
        self._build()

    @staticmethod
    def review_item_row_values(item: Any) -> tuple[object, object, object, object, object, object, object]:
        # 表格欄位順序是 UI / agent review 的顯示契約，抽成 helper 方便測試保護。
        return (
            item.adapter_id,
            item.required_action,
            adapter_review_outcome_label(str(item.outcome_bucket)),
            item.provider_id,
            item.dataset_id,
            item.version or "-",
            item.source_url or item.landing_url,
        )

    @staticmethod
    def review_item_detail_text(item: Any) -> str:
        # 詳情文字保持 key/value 形狀，方便人類複製給下一位 agent 或比對 JSON payload。
        return "\n".join(
            [
                f"adapter_id: {item.adapter_id}",
                f"required_action: {item.required_action}",
                f"outcome_bucket: {item.outcome_bucket}",
                f"expected_output: {item.expected_output}",
                f"provider_id: {item.provider_id}",
                f"dataset_uid: {item.dataset_uid or '-'}",
                f"dataset_id: {item.dataset_id or '-'}",
                f"version: {item.version or '-'}",
                f"source_url: {item.source_url or '-'}",
                f"landing_url: {item.landing_url or '-'}",
                f"download_status: {item.download_status or '-'}",
                f"import_status: {item.import_status or '-'}",
                f"content_source_format: {getattr(item, 'content_source_format', '') or '-'}",
                f"content_family: {getattr(item, 'content_family', '') or '-'}",
                f"content_parser_id: {getattr(item, 'content_parser_id', '') or '-'}",
                f"content_import_status: {getattr(item, 'content_import_status', '') or '-'}",
                f"content_review_bucket: {getattr(item, 'content_review_bucket', '') or '-'}",
                f"content_pipeline_lane: {getattr(item, 'content_pipeline_lane', '') or '-'}",
                f"content_next_action: {getattr(item, 'content_next_action', '') or '-'}",
                f"reason: {item.reason or '-'}",
                f"content_reason: {getattr(item, 'content_reason', '') or '-'}",
            ]
        )

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("Adapter 待辦", "Adapter review queue"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 6))
        ttk.Label(
            self.dialog,
            text=self.ui.tr(
                f"目前有 {len(self.review_items)} 個項目需要 adapter 把 API、頁面、選擇器或壓縮格式轉成可下載/可匯入流程。",
                f"{len(self.review_items)} items need an adapter to turn APIs, pages, selectors, or packed formats into downloadable/importable flows.",
            ),
            style="DetailMuted.TLabel",
            wraplength=900,
        ).pack(anchor="w", padx=24, pady=(0, 12))

        self.table = ttk.Treeview(
            self.dialog,
            columns=("adapter", "action", "outcome", "provider", "dataset", "version", "source"),
            show="headings",
            height=10,
            selectmode="browse",
        )
        for name, label, width in [
            ("adapter", self.ui.tr("Adapter", "Adapter"), 180),
            ("action", self.ui.tr("下一步", "Next action"), 200),
            ("outcome", self.ui.tr("結果分類", "Outcome"), 170),
            ("provider", self.ui.tr("資料源", "Provider"), 150),
            ("dataset", self.ui.tr("資料集", "Dataset"), 180),
            ("version", self.ui.tr("版本", "Version"), 90),
            ("source", self.ui.tr("來源 URL", "Source URL"), 240),
        ]:
            self.table.heading(name, text=label)
            self.table.column(name, width=width, anchor="w", stretch=True)

        for index, item in enumerate(self.review_items):
            iid = str(index)
            self.item_by_iid[iid] = item
            self.table.insert("", END, iid=iid, values=self.review_item_row_values(item))

        self.detail = Text(self.dialog, height=9, bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"], wrap=WORD, relief="flat")
        self.detail.configure(state="disabled")
        self.table.bind("<<TreeviewSelect>>", self.show_selected)
        self.table.pack(fill=BOTH, expand=True, padx=24, pady=(0, 10))
        self.detail.pack(fill=BOTH, expand=True, padx=24, pady=(0, 12))
        self.show_selected()

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        ttk.Button(actions, text=self.ui.tr("開來源 URL", "Open source URL"), style="Action.TButton", command=lambda: self.open_item_url("source")).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("開 landing 頁", "Open landing page"), style="Action.TButton", command=lambda: self.open_item_url("landing")).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("解析可下載 resources", "Resolve downloadable resources"), style="Action.TButton", command=self.resolve_from_ui).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)

    def selected_item(self) -> AdapterReviewItem | None:
        selection = self.table.selection()
        return self.item_by_iid.get(str(selection[0])) if selection else None

    def show_selected(self, _event: object | None = None) -> None:
        item = self.selected_item()
        self.detail.configure(state="normal")
        self.detail.delete("1.0", END)
        if item is None:
            self.detail.insert(END, self.ui.tr("請選取一個 adapter 待辦項目。", "Select an adapter review item."))
        else:
            self.detail.insert(END, self.review_item_detail_text(item))
        self.detail.configure(state="disabled")

    def open_item_url(self, kind: str) -> None:
        item = self.selected_item()
        if item is None:
            return
        url = item.source_url if kind == "source" else item.landing_url
        if url:
            webbrowser.open(url)

    def resolve_from_ui(self) -> None:
        self.dialog.destroy()
        self.ui.resolve_adapter_plan_from_ui()


class DataStoreConnectionSettingsDialog:
    def __init__(self, ui: Any):
        # 這個 dialog 仍需要主 UI 的 tr/status/open-config callback；先用窄介面接住，
        # 後續若要抽 controller，可把這三個需求正式化為 protocol。
        self.ui = ui
        self.root = ui.root
        self.dialog = Toplevel(self.root)
        self.dialog.title(self.ui.tr("資料儲存連線", "Data store connections"))
        self.dialog.configure(bg=COLORS["panel"])
        self.dialog.geometry("900x520")
        self.dialog.transient(self.root)

        self.active_var = StringVar(value=self._active_profile_label())
        self.profiles = data_store_profiles_from_config(core.load_integration_config())
        self.profiles_by_id = {profile.profile_id: profile for profile in self.profiles}

        self._build()

    def _active_profile_label(self) -> str:
        active_profile = active_data_store_profile()
        return self.ui.tr(
            f"目前作用中 profile：{active_profile.profile_id if active_profile else '-'}",
            f"Active profile: {active_profile.profile_id if active_profile else '-'}",
        )

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("資料儲存連線", "Data store connections"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            self.dialog,
            text=self.ui.tr(
                "Launcher 之後可能管理 SQL、NoSQL、物件儲存、向量資料庫與本機檔案資料庫。密碼請放在環境變數或未來的安全憑證庫，不要寫進 Git 檔案。",
                "The launcher may manage SQL, NoSQL, object storage, vector DBs, and file-backed stores. Secrets stay in environment variables or a future credential vault.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))
        ttk.Label(self.dialog, textvariable=self.active_var, style="DetailMuted.TLabel").pack(anchor="w", fill=X, padx=24, pady=(0, 10))

        self.table = ttk.Treeview(
            self.dialog,
            columns=("label", "kind", "engine", "required", "optional", "status"),
            show="headings",
            height=10,
        )
        for name, label, width in [
            ("label", self.ui.tr("設定檔", "Profile"), 160),
            ("kind", self.ui.tr("儲存類型", "Store kind"), 140),
            ("engine", self.ui.tr("引擎", "Engine"), 120),
            ("required", self.ui.tr("必要環境變數", "Required env vars"), 260),
            ("optional", self.ui.tr("選用環境變數", "Optional env vars"), 180),
            ("status", self.ui.tr("狀態", "Status"), 90),
        ]:
            self.table.heading(name, text=label)
            self.table.column(name, width=width, anchor="w", stretch=True)

        active_profile = active_data_store_profile()
        for profile in self.profiles:
            self.table.insert(
                "",
                END,
                iid=profile.profile_id,
                values=(
                    profile.label,
                    profile.store_kind,
                    profile.engine,
                    ", ".join(profile.required_env_vars),
                    ", ".join(profile.optional_env_vars) or "-",
                    profile.status,
                ),
            )
        if active_profile and active_profile.profile_id in self.profiles_by_id:
            self.table.selection_set(active_profile.profile_id)
            self.table.focus(active_profile.profile_id)
        self.table.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))

        actions = ttk.Frame(self.dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        ttk.Button(actions, text=self.ui.tr("測試選取項目", "Test selected"), style="Action.TButton", command=self.test_selected_profile).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("設為作用中", "Set active"), style="Action.TButton", command=self.set_selected_active_profile).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("寫出 env 範本", "Write env template"), style="Action.TButton", command=self.write_selected_env_template).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("顯示本機整合設定檔", "Reveal local integration config"), style="Action.TButton", command=self.ui.open_integration_config_file).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side=RIGHT)

    def _selected_profile_id(self) -> str | None:
        selection = self.table.selection()
        if not selection:
            return None
        return str(selection[0])

    def _selected_profile(self):
        profile_id = self._selected_profile_id()
        if profile_id is None:
            return None
        return self.profiles_by_id.get(profile_id)

    def _show_missing_selection(self) -> None:
        messagebox.showinfo(
            self.ui.tr("資料儲存連線", "Data store connections"),
            self.ui.tr("請先選取一個資料儲存設定檔。", "Select a data-store profile first."),
            parent=self.dialog,
        )

    def test_selected_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            self._show_missing_selection()
            return
        result = test_data_store_connection(profile)
        self.table.set(profile.profile_id, "status", result.status)
        self.ui.status_var.set(self.ui.tr(f"資料儲存測試：{profile.profile_id} {result.status}", f"Data store test: {profile.profile_id} {result.status}"))
        hint = self.ui.data_store_next_action_message(result)
        message = f"{profile.label}\n\n{result.status}: {result.message}"
        if hint:
            message = f"{message}\n\n{hint}"
        messagebox.showinfo(self.ui.tr("資料儲存連線測試", "Data store connection test"), message, parent=self.dialog)

    def write_selected_env_template(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            self._show_missing_selection()
            return
        output_path = data_store_env_template_path(profile.profile_id)
        try:
            # 範本只寫 env var 名稱與空值，協助本機 MySQL/PostgreSQL 設定，不保存任何密碼。
            result = write_data_store_env_template((profile,), output_path)
        except Exception as exc:
            log_exception("data_store_env_template_failed", exc, component="tk", context={"profile_id": profile.profile_id})
            messagebox.showerror(self.ui.tr("資料儲存 env 範本", "Data-store env template"), f"{type(exc).__name__}: {exc}", parent=self.dialog)
            return
        log_event(
            "data_store_env_template_written",
            component="tk",
            context={"profile_id": profile.profile_id, "path": str(result.path), "env_vars": list(result.env_vars)},
        )
        self.ui.status_var.set(self.ui.tr(f"已寫出資料儲存 env 範本：{result.path}", f"Wrote data-store env template: {result.path}"))
        messagebox.showinfo(
            self.ui.tr("資料儲存 env 範本", "Data-store env template"),
            self.ui.tr(
                f"已寫出：\n{result.path}\n\n請只在本機填入密碼，不要提交到 Git。",
                f"Wrote:\n{result.path}\n\nFill secrets locally only; do not commit them to Git.",
            ),
            parent=self.dialog,
        )

    def set_selected_active_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            self._show_missing_selection()
            return
        try:
            # active profile 是本機偏好設定，不含密碼；真實 credential 還是由 env/private store 負責。
            active_profile = set_active_data_store_profile(profile.profile_id)
        except Exception as exc:
            log_exception("data_store_active_profile_failed", exc, component="tk", context={"profile_id": profile.profile_id})
            messagebox.showerror(self.ui.tr("資料儲存 profile", "Data-store profile"), f"{type(exc).__name__}: {exc}", parent=self.dialog)
            return
        self.active_var.set(self.ui.tr(f"目前作用中 profile：{active_profile.profile_id}", f"Active profile: {active_profile.profile_id}"))
        log_event("data_store_active_profile_set", component="tk", context={"profile_id": active_profile.profile_id})
        self.ui.status_var.set(self.ui.tr(f"已設定作用中資料儲存 profile：{active_profile.profile_id}", f"Active data-store profile set: {active_profile.profile_id}"))
