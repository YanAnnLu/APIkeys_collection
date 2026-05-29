"""Tk dialog for local data-store connection settings."""

from __future__ import annotations

from tkinter import BOTH, END, LEFT, RIGHT, X, StringVar, Toplevel, messagebox
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
from frontends.tk.ui_config import COLORS
from frontends.tk.ui_helpers import data_store_env_template_path


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
