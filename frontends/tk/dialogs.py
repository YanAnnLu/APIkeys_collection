"""Tk 對話框元件。

這個模組集中放置可獨立開窗、可用 class 封裝生命週期的對話框。
主畫面 `launcher_ui.py` 只負責何時開啟對話框與如何消費結果，避免把每個
Toplevel 的欄位配置、按鈕行為與本機工具設定都堆在同一個 6000+ 行檔案。
"""

from __future__ import annotations

import webbrowser
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, Text, Toplevel, messagebox
from tkinter import ttk
from typing import Any

from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME, append_dataset_discovery_source
from api_launcher.discovery import LOCAL_SEEDS_NAME, ProviderSeed, append_discovery_seed
from api_launcher.discovery_drafts import dataset_source_from_provider_candidate
from api_launcher.event_log import log_event
from api_launcher.paths import local_config_file
from frontends.tk.adapter_review_dialog import AdapterReviewDialog
from frontends.tk.ai_settings_dialogs import AiModelSettingsDialog, GoogleGeminiSettingsDialog
from frontends.tk.data_store_connection_settings_dialog import DataStoreConnectionSettingsDialog
from frontends.tk.database_client_settings_dialog import DatabaseClientSettingsDialog
from frontends.tk.dataset_candidate_review_dialog import DatasetCandidateReviewDialog
from frontends.tk.developer_cli_dialog import DeveloperCliDialog
from frontends.tk.import_policy_dialog import ImportExistingTablePolicyDialog
from frontends.tk.language_settings_dialog import UiLanguageSettingsDialog
from frontends.tk.provider_editor_dialog import ProviderEditorDialog
from frontends.tk.recent_event_logs_dialog import RecentEventLogsDialog
from frontends.tk.startup_environment_checks_dialog import StartupEnvironmentChecksDialog
from frontends.tk.ui_config import COLORS


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
