"""Tk 對話框元件。

這個模組集中放置可獨立開窗、可用 class 封裝生命週期的對話框。
主畫面 `launcher_ui.py` 只負責何時開啟對話框與如何消費結果，避免把每個
Toplevel 的欄位配置、按鈕行為與本機工具設定都堆在同一個 6000+ 行檔案。
"""

from __future__ import annotations

import json
import shlex
import subprocess
import threading
import webbrowser
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, StringVar, Text, Tk, Toplevel, messagebox
from tkinter import ttk
from typing import Any

import APIkeys_collection as core
from api_launcher.data_store_connections import (
    data_store_profiles_from_config,
    test_data_store_connection,
    write_data_store_env_template,
)
from api_launcher.event_log import EVENT_LOG_NAME, latest_events, log_event, log_exception
from api_launcher.integrations import active_data_store_profile, save_integration_config, set_active_data_store_profile
from api_launcher.paths import PROJECT_ROOT, log_file
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
        self.set_output(f"$ {command}\n\n")
        self.ui.status_var.set(self.ui.tr(f"正在執行 CLI：{command}", f"Running CLI: {command}"))
        threading.Thread(target=lambda: self._run_command_worker(args), daemon=True).start()

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
