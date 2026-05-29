"""Tk dialog for displaying startup environment checks."""

from __future__ import annotations

from tkinter import BOTH, END, RIGHT, X, Toplevel
from tkinter import ttk
from typing import Any

import APIkeys_collection as core
from frontends.tk.ui_config import COLORS, DB_PATH


class StartupEnvironmentChecksDialog:
    def __init__(self, ui: Any):
        # Startup checks are read-only diagnostics. The dialog displays core
        # check results and does not repair, write config, or mutate app state.
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
        ttk.Label(
            self.dialog,
            text=self.ui.tr("啟動環境檢查", "Startup environment checks"),
            style="DetailTitle.TLabel",
        ).pack(anchor="w", padx=24, pady=(22, 8))
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
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(
            side=RIGHT
        )
