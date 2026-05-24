from __future__ import annotations

import threading
from tkinter import BOTH, END, LEFT, RIGHT, StringVar, X, Y
from tkinter import messagebox, ttk

from api_launcher.crawler_asset_profiles import toggle_crawler_asset_archived
from api_launcher.crawler_assets import BUILD_DOWNLOAD_PLAN, CrawlerAsset, load_crawler_assets, status_label
from api_launcher.crawler_asset_service import run_crawler_asset_listing
from api_launcher.event_log import log_exception


class CrawlerAssetWorkflowMixin:
    """爬蟲資產分頁：先管理入口與能力，再把任務交給下載器。"""

    def _build_crawler_asset_tab(self, parent: ttk.Frame, outer_pad: int) -> None:
        # 這個分頁只呈現入口爬蟲資產，不直接塞來源特例，避免 Tk 再變成巨型流程檔。
        toolbar = ttk.Frame(parent, style="App.TFrame")
        toolbar.pack(fill=X, padx=outer_pad, pady=(10, 8))
        ttk.Label(
            toolbar,
            text=self.tr("爬蟲資產：入口、能力與界域", "Crawler assets: sources, capabilities, and bounds"),
            style="DetailSection.TLabel",
        ).pack(side=LEFT)
        ttk.Button(
            toolbar,
            text=self.tr("重新載入", "Reload"),
            style="Action.TButton",
            command=self.refresh_crawler_asset_tab,
        ).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(
            toolbar,
            text=self.tr("清單擷取", "List datasets"),
            style="Action.TButton",
            command=self.run_selected_crawler_asset_listing,
        ).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(
            toolbar,
            text=self.tr("元資料爬取", "Fetch metadata"),
            style="Action.TButton",
            command=self.run_selected_crawler_asset_metadata,
        ).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(
            toolbar,
            text=self.tr("封存 / 啟用", "Archive / Enable"),
            style="Action.TButton",
            command=self.toggle_selected_crawler_asset_archive,
        ).pack(side=RIGHT, padx=(8, 0))

        body = ttk.Frame(parent, style="App.TFrame")
        body.pack(fill=BOTH, expand=True, padx=outer_pad, pady=(0, 10))

        table_frame = ttk.Frame(body, style="Panel.TFrame")
        table_frame.pack(side=LEFT, fill=BOTH, expand=True)
        columns = ("name", "state", "provider", "type", "metadata", "listing", "download", "seed_count", "trust", "seed", "next")
        self.crawler_asset_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = [
            ("name", self.tr("入口爬蟲", "Crawler asset"), 270, "w"),
            ("state", self.tr("狀態", "State"), 82, "center"),
            ("provider", self.tr("Provider", "Provider"), 150, "w"),
            ("type", self.tr("入口類型", "Source type"), 145, "w"),
            ("metadata", self.tr("元資料", "Metadata"), 70, "center"),
            ("listing", self.tr("清單", "Listing"), 70, "center"),
            ("download", self.tr("下載", "Download"), 80, "center"),
            ("seed_count", self.tr("Seed", "Seeds"), 85, "center"),
            ("trust", self.tr("信任", "Trust"), 70, "center"),
            ("seed", self.tr("Seed 範圍", "Seed scope"), 150, "w"),
            ("next", self.tr("下一步", "Next action"), 260, "w"),
        ]
        for name, label, width, anchor in headings:
            self.crawler_asset_tree.heading(name, text=label)
            self.crawler_asset_tree.column(name, width=width, anchor=anchor, stretch=True)
        self.crawler_asset_tree.tag_configure("normal", foreground="#e7edf6")
        self.crawler_asset_tree.tag_configure("needs_review", foreground="#ffd166")
        self.crawler_asset_tree.tag_configure("needs_handler", foreground="#ff7b7b")
        self.crawler_asset_tree.tag_configure("archived", foreground="#8a95a6")
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.crawler_asset_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.crawler_asset_tree.xview)
        self.crawler_asset_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        x_scrollbar.pack(side="bottom", fill=X)
        self.crawler_asset_tree.pack(side=LEFT, fill=BOTH, expand=True)
        y_scrollbar.pack(side=RIGHT, fill=Y)
        self.crawler_asset_tree.bind("<<TreeviewSelect>>", self.on_crawler_asset_select)
        self.crawler_asset_tree.bind("<Double-1>", self.on_crawler_asset_double_click)

        detail = ttk.Frame(body, style="Panel.TFrame", width=360)
        detail.pack(side=RIGHT, fill=Y, padx=(12, 0))
        detail.pack_propagate(False)
        self.crawler_asset_detail_var = StringVar(value=self.tr("選擇一個入口爬蟲，查看能力與界域狀態。", "Select a crawler asset."))
        ttk.Label(detail, text=self.tr("Crawler Passport", "Crawler Passport"), style="DetailSection.TLabel").pack(anchor="w", padx=14, pady=(14, 8))
        ttk.Label(detail, textvariable=self.crawler_asset_detail_var, style="DetailText.TLabel", wraplength=320).pack(anchor="w", padx=14)
        ttk.Button(
            detail,
            text=self.tr("送到下載器 / 設定界域", "Send to downloader / bounds"),
            style="Action.TButton",
            command=self.prepare_selected_crawler_asset_download,
        ).pack(anchor="w", padx=14, pady=(16, 0))
        self.crawler_asset_archive_button_var = StringVar(value=self.tr("封存爬蟲", "Archive crawler"))
        ttk.Button(
            detail,
            textvariable=self.crawler_asset_archive_button_var,
            style="Action.TButton",
            command=self.toggle_selected_crawler_asset_archive,
        ).pack(anchor="w", padx=14, pady=(8, 0))

        self.crawler_assets_by_id: dict[str, CrawlerAsset] = {}
        self.refresh_crawler_asset_tab()

    def refresh_crawler_asset_tab(self) -> None:
        if not hasattr(self, "crawler_asset_tree"):
            return
        try:
            assets = load_crawler_assets()
        except Exception as exc:  # pragma: no cover - Tk surface guard
            self.status_var.set(self.tr(f"爬蟲資產載入失敗：{exc}", f"Failed to load crawler assets: {exc}"))
            return
        self.crawler_assets_by_id = {asset.asset_id: asset for asset in assets}
        for item in self.crawler_asset_tree.get_children():
            self.crawler_asset_tree.delete(item)
        for asset in assets:
            self.crawler_asset_tree.insert(
                "",
                END,
                iid=asset.asset_id,
                values=self.crawler_asset_row_values(asset),
                tags=(asset.risk_tier,),
            )
        self.status_var.set(self.tr(f"已載入 {len(assets)} 個爬蟲資產。", f"Loaded {len(assets)} crawler assets."))

    def crawler_asset_row_values(self, asset: CrawlerAsset) -> tuple[object, ...]:
        return (
            asset.display_name,
            crawler_asset_state_label(asset),
            asset.provider_id,
            asset.source_type,
            status_label(asset.capability_status("fetch_metadata")),
            status_label(asset.capability_status("list_datasets")),
            status_label(asset.capability_status(BUILD_DOWNLOAD_PLAN)),
            asset.seed_summary,
            f"{asset.trust_score}%",
            asset.current_seed_scope,
            asset.next_action,
        )

    def selected_crawler_asset(self) -> CrawlerAsset | None:
        if not hasattr(self, "crawler_asset_tree"):
            return None
        selected = self.crawler_asset_tree.selection()
        if not selected:
            return None
        return self.crawler_assets_by_id.get(str(selected[0]))

    def on_crawler_asset_select(self, _event: object | None = None) -> None:
        asset = self.selected_crawler_asset()
        if asset is None:
            return
        if hasattr(self, "crawler_asset_archive_button_var"):
            self.crawler_asset_archive_button_var.set(
                self.tr("解除封存 / 啟用" if asset.archived else "封存爬蟲", "Unarchive / Enable" if asset.archived else "Archive crawler")
            )
        capability_lines = "\n".join(
            f"- {item.label}：{status_label(item.status)}；{item.detail}" for item in asset.capabilities
        )
        plan_capability = next((item for item in asset.capabilities if item.capability_id == BUILD_DOWNLOAD_PLAN), None)
        bounds_schema = plan_capability.bounds_schema if plan_capability is not None else ()
        bounds_summary_zh = "、".join(f"{facet.label_zh_TW}({facet.group})" for facet in bounds_schema)
        bounds_summary_en = ", ".join(f"{facet.label_en}({facet.group})" for facet in bounds_schema)
        self.crawler_asset_detail_var.set(
            self.tr(
                (
                    f"{asset.display_name}\n\n"
                    f"入口：{asset.source_surface} / {asset.source_type}\n"
                    f"狀態：{crawler_asset_state_label(asset)}\n"
                    f"存取邊界：{asset.access_requirement}\n"
                    f"成熟度：{asset.maturity}；風險：{asset.risk_tier}；信任：{asset.trust_score}%\n"
                    f"Seed：{asset.seed_summary} / {asset.current_seed_scope}\n\n"
                    f"{capability_lines}\n\n"
                    f"界域 schema：{bounds_summary_zh or '無'}\n\n"
                    "下載指定資料庫會套用界域裝飾器：版本、時間、bbox、欄位與筆數上限。"
                ),
                (
                    f"{asset.display_name}\n\n"
                    f"Surface: {asset.source_surface} / {asset.source_type}\n"
                    f"State: {crawler_asset_state_label(asset)}\n"
                    f"Access: {asset.access_requirement}\n"
                    f"Maturity: {asset.maturity}; risk: {asset.risk_tier}; trust: {asset.trust_score}%\n"
                    f"Seed: {asset.seed_summary} / {asset.current_seed_scope}\n\n"
                    f"{capability_lines}\n\n"
                    f"Bounds schema: {bounds_summary_en or 'none'}\n\n"
                    "Selected downloads are decorated by bounds: version, time, bbox, columns, and limits."
                ),
            )
        )

    def on_crawler_asset_double_click(self, _event: object | None = None) -> None:
        self.prepare_selected_crawler_asset_download()

    def run_selected_crawler_asset_metadata(self) -> None:
        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        if asset.archived:
            self.status_var.set(self.tr("這個爬蟲已封存；請先解除封存再執行。", "This crawler is archived; unarchive it before running."))
            return
        self.active_provider_id = asset.provider_id
        self.status_var.set(self.tr(f"切到 {asset.provider_id}，執行既有 metadata 爬取。", f"Fetching metadata for {asset.provider_id}."))
        self.crawl_selected()

    def run_selected_crawler_asset_listing(self) -> None:
        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        if asset.archived:
            self.status_var.set(self.tr("這個爬蟲已封存；請先解除封存再執行。", "This crawler is archived; unarchive it before running."))
            return
        self.active_provider_id = asset.provider_id
        self.status_var.set(
            self.tr(
                f"正在擷取入口清單；入口：{asset.asset_id}。",
                f"Listing datasets for source: {asset.asset_id}.",
            )
        )
        threading.Thread(target=self._crawler_asset_listing_worker, args=(asset.asset_id,), daemon=True).start()

    def _crawler_asset_listing_worker(self, asset_id: str) -> None:
        # UI 只負責排 thread 與更新畫面；crawler/repository 寫入由 service 統一管理，
        # 讓未來 Qt 版可以直接重用同一個 crawler asset 閉環。
        try:
            conn = self._connect()
            try:
                result = run_crawler_asset_listing(asset_id, conn)
            finally:
                conn.close()
        except Exception as exc:
            log_exception("crawler_asset_listing_failed", exc, component="ui.crawler_assets", context={"asset_id": asset_id})
            self.root.after(0, lambda: messagebox.showerror(self.tr("清單擷取失敗", "Listing failed"), str(exc)))
            self.root.after(0, lambda: self.status_var.set(self.tr(f"入口清單擷取失敗：{exc}", f"Source listing failed: {exc}")))
            return

        def finish() -> None:
            if result.blocked:
                self.status_var.set(
                    self.tr(
                        f"爬蟲資產暫停執行：{result.blocked_reason}；下一步：{result.next_action}",
                        f"Crawler asset blocked: {result.blocked_reason}; next action: {result.next_action}",
                    )
                )
                return
            self.reload_data()
            self.refresh_crawler_asset_tab()
            self.status_var.set(
                self.tr(
                    f"入口清單擷取完成：候選 {result.candidate_count}，寫入 {result.upserted_count}，跳過 provider {result.skipped_provider_count}；下一步可到下載器選版本與界域。",
                    f"Source listing complete: candidates {result.candidate_count}, upserted {result.upserted_count}, skipped providers {result.skipped_provider_count}; select version and bounds in Downloader next.",
                )
            )
            if hasattr(self, "main_notebook") and hasattr(self, "downloader_tab"):
                self.main_notebook.select(self.downloader_tab)

        self.root.after(0, finish)

    def prepare_selected_crawler_asset_download(self) -> None:
        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        if asset.archived:
            self.status_var.set(self.tr("這個爬蟲已封存；請先解除封存再送到下載器。", "This crawler is archived; unarchive it before sending it to Downloader."))
            return
        self.active_provider_id = asset.provider_id
        self.status_var.set(
            self.tr(
                "下載指定資料庫需要先在下載器選定資料集/版本，再按「界域」產生動態表單。",
                "Select a dataset/version in Downloader, then use Bounds to generate the dynamic form.",
            )
        )
        if hasattr(self, "main_notebook") and hasattr(self, "downloader_tab"):
            self.main_notebook.select(self.downloader_tab)

    def toggle_selected_crawler_asset_archive(self) -> None:
        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        try:
            profile = toggle_crawler_asset_archived(asset.asset_id)
        except Exception as exc:
            log_exception("crawler_asset_archive_toggle_failed", exc, component="ui.crawler_assets", context={"asset_id": asset.asset_id})
            messagebox.showerror(self.tr("封存爬蟲失敗", "Archive failed"), str(exc), parent=getattr(self, "root", None))
            return
        self.refresh_crawler_asset_tab()
        if hasattr(self, "crawler_asset_tree") and asset.asset_id in self.crawler_asset_tree.get_children():
            self.crawler_asset_tree.selection_set(asset.asset_id)
            self.crawler_asset_tree.focus(asset.asset_id)
            self.on_crawler_asset_select()
        self.status_var.set(
            self.tr(
                f"爬蟲資產已{'封存' if profile.archived else '啟用'}：{asset.display_name}",
                f"Crawler asset {'archived' if profile.archived else 'enabled'}: {asset.display_name}",
            )
        )


def crawler_asset_state_label(asset: CrawlerAsset) -> str:
    if asset.archived:
        return "📦 封存"
    if not asset.enabled:
        return "⏸ 停用"
    if asset.risk_tier == "needs_handler":
        return "⚙️ 待補"
    if asset.risk_tier == "needs_review":
        return "🟡 待審"
    return "🟢 啟用"
