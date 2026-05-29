"""Tk dialog for selecting the launcher UI language."""

from __future__ import annotations

from tkinter import RIGHT, X, StringVar, Toplevel, messagebox
from tkinter import ttk
from typing import Any

import APIkeys_collection as core
from api_launcher.integrations import save_integration_config
from frontends.tk.ui_config import COLORS, DEFAULT_UI_LANGUAGE, UI_LANGUAGES


class UiLanguageSettingsDialog:
    def __init__(self, ui: Any):
        # Language settings write only the local integration config and notify
        # the main UI to rebuild menus. The dialog does not own main layout.
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
        # Combobox shows human-readable labels; saving must restore stable codes.
        return {label: code for code, label in labels_by_code.items()}

    def _build(self) -> None:
        ttk.Label(self.dialog, text=self.ui.tr("介面語言", "Interface language"), style="DetailTitle.TLabel").pack(
            anchor="w", padx=24, pady=(22, 8)
        )
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
        ttk.Button(actions, text=self.ui.tr("儲存", "Save"), style="Action.TButton", command=self.save_language).pack(
            side=RIGHT, padx=(10, 0)
        )
        ttk.Button(actions, text=self.ui.tr("取消", "Cancel"), style="Action.TButton", command=self.dialog.destroy).pack(
            side=RIGHT
        )

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
        self.ui.status_var.set(
            self.ui.tr("介面語言已更新。主畫面完整套用需要重新啟動。", "Interface language updated. Restart for the full main window.")
        )
        messagebox.showinfo(
            self.ui.tr("介面語言", "Interface language"),
            self.ui.tr(
                "已儲存介面語言設定。新開啟的視窗會先套用，主畫面完整套用請重新啟動。",
                "Language saved. New dialogs will use it now; restart for the full main window.",
            ),
            parent=self.dialog,
        )
        self.dialog.destroy()
