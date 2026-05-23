"""Tk 對話框元件。

這個模組集中放置可獨立開窗、可用 class 封裝生命週期的對話框。
主畫面 `launcher_ui.py` 只負責何時開啟對話框與如何消費結果，避免把每個
Toplevel 的欄位配置、按鈕行為與本機工具設定都堆在同一個 6000+ 行檔案。
"""

from __future__ import annotations

from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, StringVar, Text, Tk, Toplevel, messagebox
from tkinter import ttk
from typing import Any

import APIkeys_collection as core
from api_launcher.data_store_connections import (
    data_store_profiles_from_config,
    test_data_store_connection,
    write_data_store_env_template,
)
from api_launcher.event_log import log_event, log_exception
from api_launcher.integrations import active_data_store_profile, set_active_data_store_profile
from frontends.tk.desktop_integration import reveal_path_in_file_manager
from frontends.tk.provider_models import ProviderRow
from frontends.tk.ui_config import COLORS
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
