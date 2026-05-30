"""Tk dialog for adapter review queue items."""

from __future__ import annotations

import webbrowser
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, Text, Toplevel
from tkinter import ttk
from typing import Any

from api_launcher.adapter_review import AdapterReviewItem
from api_launcher.crawler_asset_display import adapter_review_item_display_payload
from frontends.tk.ui_config import COLORS


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
        display = adapter_review_item_display_payload(item)
        return (
            item.adapter_id,
            display["required_action_label"],
            display["outcome_label"],
            item.provider_id,
            item.dataset_id,
            item.version or "-",
            item.source_url or item.landing_url,
        )

    @staticmethod
    def review_item_detail_text(item: Any) -> str:
        # 詳情文字保持 key/value 形狀，方便人類複製給下一位 agent 或比對 JSON payload。
        display = adapter_review_item_display_payload(item)
        return "\n".join(
            [
                f"adapter_id: {item.adapter_id}",
                f"required_action: {display['required_action_label']}",
                f"outcome_bucket: {display['outcome_label']}",
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
                f"content_import_status: {display['content_import_status_label'] or '-'}",
                f"content_review_bucket: {display['content_review_bucket_label'] or '-'}",
                f"content_pipeline_lane: {display['content_pipeline_lane_label'] or '-'}",
                f"content_next_action: {display['content_next_action_label'] or '-'}",
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
