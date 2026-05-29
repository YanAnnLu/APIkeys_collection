"""Tk dialog for recent structured event logs."""

from __future__ import annotations

import json
import webbrowser
from tkinter import BOTH, END, WORD, X, Toplevel, Text
from tkinter import ttk
from typing import Any

from api_launcher.event_log import EVENT_LOG_NAME, latest_events
from api_launcher.paths import log_file
from frontends.tk.ui_config import COLORS


class RecentEventLogsDialog:
    def __init__(self, ui: Any):
        # 事件紀錄視窗是觀測/交接工具；它只讀 JSONL，不修改產品狀態。
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
            ).pack(side="left", padx=(0, 10))
        ttk.Button(actions, text=self.ui.tr("關閉", "Close"), style="Action.TButton", command=self.dialog.destroy).pack(side="right")

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
