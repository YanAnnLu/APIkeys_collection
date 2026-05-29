"""Tk dialog for choosing the existing-table import policy.

The dialog owns only the user-facing policy choice. Actual table replacement,
renaming, skipping, and safety guards stay in the importer/pipeline layer.
"""

from __future__ import annotations

from tkinter import BOTH, RIGHT, X, StringVar, Toplevel, messagebox
from tkinter import ttk
from typing import Any

from api_launcher.import_policies import normalized_ui_import_policy
from frontends.tk.ui_config import COLORS


class ImportExistingTablePolicyDialog:
    def __init__(self, ui: Any):
        # This is a risk prompt for import policy only. The importer still owns
        # the destructive/replace behavior and its guards.
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
        # Option values are shared by UI preferences, pipeline params, and tests.
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
                self.ui.tr(
                    "會重建同名資料表；只有確定要刷新資料時才使用。",
                    "This recreates the same-name table; use only when you mean to refresh it.",
                ),
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
            ttk.Label(row, text=description, foreground=COLORS["muted"], wraplength=540).pack(
                anchor="w", padx=(24, 0), pady=(2, 0)
            )

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
