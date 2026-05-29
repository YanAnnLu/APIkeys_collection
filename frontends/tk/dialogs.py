"""Tk 對話框元件。

這個模組集中放置可獨立開窗、可用 class 封裝生命週期的對話框。
主畫面 `launcher_ui.py` 只負責何時開啟對話框與如何消費結果，避免把每個
Toplevel 的欄位配置、按鈕行為與本機工具設定都堆在同一個 6000+ 行檔案。
"""

from __future__ import annotations

import json
import webbrowser
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, Y, StringVar, Text, Toplevel, messagebox
from tkinter import ttk
from typing import Any

import APIkeys_collection as core
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
from api_launcher.event_log import log_event, log_exception
from api_launcher.integrations import active_data_store_profile, set_active_data_store_profile
from api_launcher.paths import local_config_file
from frontends.tk.ai_settings_dialogs import AiModelSettingsDialog, GoogleGeminiSettingsDialog
from frontends.tk.database_client_settings_dialog import DatabaseClientSettingsDialog
from frontends.tk.developer_cli_dialog import DeveloperCliDialog
from frontends.tk.import_policy_dialog import ImportExistingTablePolicyDialog
from frontends.tk.language_settings_dialog import UiLanguageSettingsDialog
from frontends.tk.provider_editor_dialog import ProviderEditorDialog
from frontends.tk.recent_event_logs_dialog import RecentEventLogsDialog
from frontends.tk.startup_environment_checks_dialog import StartupEnvironmentChecksDialog
from frontends.tk.ui_config import COLORS
from frontends.tk.ui_helpers import data_store_env_template_path


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
