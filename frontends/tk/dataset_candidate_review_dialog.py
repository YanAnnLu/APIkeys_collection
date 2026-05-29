"""Tk dialog for reviewing dataset crawler candidates."""

from __future__ import annotations

import json
import webbrowser
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, Y, StringVar, Text, Toplevel, messagebox
from tkinter import ttk
from typing import Any

import APIkeys_collection as core
from frontends.tk.ui_config import COLORS


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
