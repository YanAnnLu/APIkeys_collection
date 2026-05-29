"""Tk workflow for the crawler asset tab.

This mixin is the plain desktop control panel for crawler assets.  It should
collect user intent, call backend services, and render structured results.  The
actual crawler, profile, download-plan, seed paging, credential, and import
rules belong in ``api_launcher`` services.

Keep this file as a workflow adapter: if a branch starts deciding source type,
content parser, provider policy, or download safety, that branch belongs in a
backend contract first.
"""

from __future__ import annotations
from tkinter import BOTH, END, LEFT, RIGHT, StringVar, X, Y
from tkinter import messagebox, ttk
from typing import Callable

from api_launcher.adapter_review import adapter_review_items
from api_launcher.crawler_asset_profiles import (
    crawler_asset_favorite_seed_uids,
    toggle_crawler_asset_archived,
    update_crawler_asset_plan_passport,
    update_crawler_asset_profile,
)
from api_launcher.crawler_assets import CrawlerAsset, load_crawler_asset_source, load_crawler_assets
from api_launcher.crawler_asset_bound_forms import (
    CrawlerAssetBoundPayload,
    build_crawler_asset_bound_form_spec,
)
from api_launcher.crawler_asset_download import run_crawler_seed_download_import
from api_launcher.crawler_asset_schema_probe import crawler_asset_bound_form_schema_probe_result
from api_launcher.crawler_asset_service import (
    build_crawler_asset_download_plan,
    run_crawler_asset_listing,
)
from api_launcher.crawler_seed_registry import crawler_seed_page, save_crawler_seed_favorite
from api_launcher.crawlers.source_patterns import DEFAULT_PATTERN_MINIMUM_CONFIDENCE
from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME
from api_launcher.event_log import latest_events, log_event, log_exception
from api_launcher.local_credentials import (
    crawler_asset_credential_status,
    credential_status_blocks_download,
    update_crawler_asset_credentials,
)
from api_launcher.paths import DOWNLOADS_DIR, local_config_file
from api_launcher.repository import ApiCatalogRepository
from api_launcher.source_pattern_drafts import SourcePatternDraftError, write_source_draft_from_url
from frontends.tk.background_jobs import (
    release_single_flight_job,
    single_flight_job_is_active,
    start_single_flight_thread,
)
from frontends.tk.crawler_asset_bound_dialog import CrawlerAssetBoundDialog
from frontends.tk.crawler_asset_credential_dialog import CrawlerAssetCredentialDialog
from frontends.tk.crawler_asset_profile_dialog import CrawlerAssetProfileDialog
from frontends.tk.crawler_asset_seed_dialog import CrawlerAssetSeedDialog
from frontends.tk.crawler_asset_ui_helpers import (
    cache_crawler_asset_plan_state,
    crawler_asset_credential_event_context,
    crawler_asset_credential_guard_message,
    crawler_asset_bound_payload_from_cache,
    crawler_asset_detail_text,
    crawler_asset_download_plan_bounds_schema,
    crawler_asset_download_plan_summary_text,
    crawler_asset_listing_blocked_status_text,
    crawler_asset_listing_outcome_event_payload,
    crawler_asset_plan_outcome_event_payload,
    crawler_asset_row_values,
    crawler_asset_seed_enumeration_note_text,
    crawler_asset_seed_page_preview_text,
    crawler_asset_seed_page_status_text,
    crawler_asset_state_label,
    crawler_seed_schema_probe_event_context,
    crawler_seed_download_import_target_paths,
    crawler_seed_download_import_ui_message,
    write_crawler_asset_download_plan_artifacts,
)
from frontends.tk.crawler_asset_event_state import (
    crawler_asset_listing_outcomes_from_events,
    crawler_asset_plan_state_from_events,
)
from frontends.tk.dialogs import AdapterReviewDialog
from frontends.tk.source_pattern_draft_dialog import SourcePatternDraftDialog
from frontends.tk.source_pattern_draft_ui_helpers import (
    source_pattern_draft_message,
    source_pattern_draft_review_message,
)

MAX_CRAWLER_ASSET_BACKGROUND_JOBS = 4


class CrawlerAssetWorkflowMixin:
    """爬蟲資產分頁：先管理入口與能力，再把任務交給下載器。

    The mixin owns Tk widgets and background-thread handoff only.  Backend
    services own the semantics of listing, plan building, seed paging, and
    seed download/import.
    """

    def _start_crawler_asset_background_job(
        self,
        job_key: tuple[str, str, str],
        target: Callable[..., None],
        args: tuple[object, ...],
        *,
        duplicate_status_zh: str,
        duplicate_status_en: str,
    ) -> bool:
        """Start one bounded crawler-asset worker unless that job is active.

        Tk remains a thin shell, but it still needs a small single-flight guard:
        repeated clicks on the same seed should not spawn parallel probe/download
        jobs that compete for the same files, SQLite path, or user dialog state.
        """

        return start_single_flight_thread(
            self,
            job_key,
            target,
            args,
            active_jobs_attr="crawler_asset_active_jobs",
            active_jobs_lock_attr="crawler_asset_active_jobs_lock",
            on_duplicate=lambda: self.status_var.set(self.tr(duplicate_status_zh, duplicate_status_en)),
            max_active_jobs=MAX_CRAWLER_ASSET_BACKGROUND_JOBS,
            on_capacity=lambda: self.status_var.set(
                self.tr(
                    "爬蟲資產背景工作已達上限，請等目前工作完成。",
                    "Crawler asset background jobs are at capacity; wait for one to finish.",
                )
            ),
        )

    def _crawler_asset_background_job_is_active(
        self,
        job_key: tuple[str, str, str],
        *,
        duplicate_status_zh: str,
        duplicate_status_en: str,
    ) -> bool:
        """Return whether a Tk crawler-asset job is already active."""

        return single_flight_job_is_active(
            self,
            job_key,
            active_jobs_attr="crawler_asset_active_jobs",
            on_duplicate=lambda: self.status_var.set(self.tr(duplicate_status_zh, duplicate_status_en)),
        )

    def _release_crawler_asset_background_job(self, job_key: tuple[str, str, str]) -> None:
        """Release a previously registered crawler-asset worker key."""

        release_single_flight_job(
            self,
            job_key,
            active_jobs_attr="crawler_asset_active_jobs",
            active_jobs_lock_attr="crawler_asset_active_jobs_lock",
        )

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
        ttk.Button(
            toolbar,
            text=self.tr("爬蟲設定", "Settings"),
            style="Action.TButton",
            command=self.open_selected_crawler_asset_profile_dialog,
        ).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(
            toolbar,
            text=self.tr("貼 URL 建立來源草稿", "Draft source from URL"),
            style="Action.TButton",
            command=self.open_source_pattern_draft_dialog,
        ).pack(side=RIGHT, padx=(8, 0))

        body = ttk.Frame(parent, style="App.TFrame")
        body.pack(fill=BOTH, expand=True, padx=outer_pad, pady=(0, 10))

        table_frame = ttk.Frame(body, style="Panel.TFrame")
        table_frame.pack(side=LEFT, fill=BOTH, expand=True)
        columns = ("name", "state", "login", "provider", "type", "metadata", "listing", "download", "seed_count", "trust", "seed", "next")
        self.crawler_asset_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = [
            ("name", self.tr("入口爬蟲", "Crawler asset"), 270, "w"),
            ("state", self.tr("狀態", "State"), 82, "center"),
            ("login", self.tr("登入", "Login"), 120, "center"),
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
        ttk.Button(
            detail,
            text=self.tr("開本次 Adapter 待辦", "Open current adapter queue"),
            style="Action.TButton",
            command=self.open_selected_crawler_asset_adapter_review,
        ).pack(anchor="w", padx=14, pady=(8, 0))
        self.crawler_asset_archive_button_var = StringVar(value=self.tr("封存爬蟲", "Archive crawler"))
        ttk.Button(
            detail,
            textvariable=self.crawler_asset_archive_button_var,
            style="Action.TButton",
            command=self.toggle_selected_crawler_asset_archive,
        ).pack(anchor="w", padx=14, pady=(8, 0))
        ttk.Button(
            detail,
            text=self.tr("爬蟲設定 / Logo", "Settings / logo"),
            style="Action.TButton",
            command=self.open_selected_crawler_asset_profile_dialog,
        ).pack(anchor="w", padx=14, pady=(8, 0))
        ttk.Button(
            detail,
            text=self.tr("登入設定 / 記住我的帳號", "Login settings / remember account"),
            style="Action.TButton",
            command=self.open_selected_crawler_asset_credential_dialog,
        ).pack(anchor="w", padx=14, pady=(8, 0))
        ttk.Label(detail, text=self.tr("Seed 清單", "Seed list"), style="DetailSection.TLabel").pack(anchor="w", padx=14, pady=(18, 8))
        self.crawler_asset_seed_page_var = StringVar(value=self.tr("尚未讀取 seed。先執行清單擷取，再查看本機 seed 視窗。", "No seed page loaded yet. Run listing first, then inspect local seeds."))
        ttk.Label(detail, textvariable=self.crawler_asset_seed_page_var, style="DetailText.TLabel", wraplength=320).pack(anchor="w", padx=14)
        ttk.Button(
            detail,
            text=self.tr("查看 Seed 清單", "View seeds"),
            style="Action.TButton",
            command=self.load_selected_crawler_asset_seed_page,
        ).pack(anchor="w", padx=14, pady=(8, 0))
        ttk.Button(
            detail,
            text=self.tr("開 Seed 表格 / 下載", "Open seed table / download"),
            style="Action.TButton",
            command=self.open_selected_crawler_asset_seed_dialog,
        ).pack(anchor="w", padx=14, pady=(8, 0))
        ttk.Button(
            detail,
            text=self.tr("顯示更多 Seed", "Show more seeds"),
            style="Action.TButton",
            command=self.show_more_selected_crawler_asset_seeds,
        ).pack(anchor="w", padx=14, pady=(8, 0))

        # These caches are UI state derived from backend payloads or structured
        # events.  They are not the source of truth; reload/rebuild actions must
        # call the backend services again.
        self.crawler_assets_by_id: dict[str, CrawlerAsset] = {}
        self.crawler_asset_plan_outcomes: dict[str, str] = {}
        self.crawler_asset_content_review_outcomes: dict[str, str] = {}
        self.crawler_asset_resolved_plans: dict[str, dict[str, object]] = {}
        self.crawler_asset_plan_passports: dict[str, dict[str, object]] = {}
        self.crawler_asset_seed_pages: dict[str, dict[str, object]] = {}
        self.load_crawler_asset_plan_outcomes_from_events()
        self.load_crawler_asset_listing_outcomes_from_events()
        self.refresh_crawler_asset_tab()

    def load_crawler_asset_plan_outcomes_from_events(self) -> None:
        """從 structured event 恢復最近送進下載器的可視狀態，避免重開 UI 後全部消失。

        Events provide display continuity only.  They should not be treated as a
        fresh resolved plan unless the downstream action explicitly reloads the
        saved plan path.
        """

        restored = crawler_asset_plan_state_from_events(latest_events(200))
        self.crawler_asset_plan_outcomes = restored.plan_outcomes
        self.crawler_asset_content_review_outcomes = restored.content_review_outcomes
        self.crawler_asset_resolved_plans = restored.resolved_plans
        self.crawler_asset_plan_passports = restored.plan_passports

    def load_crawler_asset_listing_outcomes_from_events(self) -> None:
        """Restore the latest listing/seed-enumeration status from structured events."""

        self.crawler_asset_listing_outcomes = crawler_asset_listing_outcomes_from_events(latest_events(200))

    def refresh_crawler_asset_tab(self) -> None:
        """Reload crawler asset cards from profile/source metadata."""

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
        last_plan_outcome = getattr(self, "crawler_asset_plan_outcomes", {}).get(asset.asset_id) or asset.next_action
        content_review = getattr(self, "crawler_asset_content_review_outcomes", {}).get(asset.asset_id, "")
        return crawler_asset_row_values(
            asset,
            credential_status=crawler_asset_credential_status(asset),
            last_plan_outcome=last_plan_outcome,
            content_review=content_review,
        )

    def selected_crawler_asset(self) -> CrawlerAsset | None:
        if not hasattr(self, "crawler_asset_tree"):
            return None
        selected = self.crawler_asset_tree.selection()
        if not selected:
            return None
        return self.crawler_assets_by_id.get(str(selected[0]))

    def on_crawler_asset_select(self, _event: object | None = None) -> None:
        """Render the right-side passport for the selected crawler asset."""

        asset = self.selected_crawler_asset()
        if asset is None:
            return
        if hasattr(self, "crawler_asset_seed_page_var"):
            cached_seed_page = getattr(self, "crawler_asset_seed_pages", {}).get(asset.asset_id)
            latest_listing = getattr(self, "crawler_asset_listing_outcomes", {}).get(asset.asset_id)
            self.crawler_asset_seed_page_var.set(
                crawler_asset_seed_page_preview_text(cached_seed_page, self.tr, listing_outcome=latest_listing)
                if isinstance(cached_seed_page, dict)
                else crawler_asset_seed_page_preview_text(None, self.tr, listing_outcome=latest_listing)
            )
        if hasattr(self, "crawler_asset_archive_button_var"):
            self.crawler_asset_archive_button_var.set(
                self.tr("解除封存 / 啟用" if asset.archived else "封存爬蟲", "Unarchive / Enable" if asset.archived else "Archive crawler")
            )
        last_plan_outcome = getattr(self, "crawler_asset_plan_outcomes", {}).get(asset.asset_id, "")
        content_review = getattr(self, "crawler_asset_content_review_outcomes", {}).get(asset.asset_id, "")
        credential_status = crawler_asset_credential_status(asset)
        self.crawler_asset_detail_var.set(
            crawler_asset_detail_text(
                asset,
                last_plan_outcome=last_plan_outcome,
                content_review=content_review,
                resolved_plan=getattr(self, "crawler_asset_resolved_plans", {}).get(asset.asset_id),
                plan_passport=getattr(self, "crawler_asset_plan_passports", {}).get(asset.asset_id),
                credential_status=credential_status,
                tr=self.tr,
            )
        )

    def on_crawler_asset_double_click(self, _event: object | None = None) -> None:
        """Double-click follows the download-manager mental model: prepare plan."""

        self.prepare_selected_crawler_asset_download()

    def open_source_pattern_draft_dialog(self) -> None:
        """Collect one URL and send it to the backend source-pattern detector."""

        dialog = SourcePatternDraftDialog(getattr(self, "root", None), self.tr)
        if dialog.result is None:
            return
        values = dict(dialog.result)
        url = str(values.get("url") or "")
        started = self._start_crawler_asset_background_job(
            ("source_pattern_draft", url, ""),
            self._source_pattern_draft_worker,
            (values,),
            duplicate_status_zh=f"來源 URL 辨識已在執行：{url}",
            duplicate_status_en=f"Source URL detection is already running: {url}",
        )
        if started:
            self.status_var.set(self.tr(f"正在辨識來源 URL：{url}", f"Detecting source URL: {url}"))

    def _source_pattern_draft_worker(self, values: dict[str, object]) -> None:
        # URL -> local source draft 仍走後端 detector/service；Tk 只負責輸入與呈現，
        # 避免把 STAC/CKAN/ERDDAP 等範式規則重新寫進 UI 層。
        output_path = local_config_file(LOCAL_DATASET_DISCOVERY_SOURCES_NAME)
        url = str(values.get("url") or "")
        try:
            summary = write_source_draft_from_url(
                url,
                output_path,
                provider_id=str(values.get("provider_id") or ""),
                name=str(values.get("name") or ""),
                source_id=str(values.get("source_id") or ""),
                categories=tuple(values.get("categories") or ()),
                geographic_scope=str(values.get("geographic_scope") or "global"),
                max_results=int(values.get("max_results") or 10),
                min_expected_candidates=int(values.get("min_expected_candidates") or 1),
                timeout=float(values.get("timeout") or 8.0),
                minimum_confidence=float(values.get("minimum_confidence") or DEFAULT_PATTERN_MINIMUM_CONFIDENCE),
            )
            log_event(
                "source_pattern_source_draft_written",
                "Tk crawler asset UI wrote a local source draft from a detected URL.",
                component="ui.crawler_assets",
                context={
                    "source_url": url,
                    "output_path": str(output_path),
                    "audit_source_ids": summary.get("audit_source_ids", []),
                    "source_pattern_detection": summary.get("source_pattern_detection", {}),
                },
            )
        except SourcePatternDraftError as exc:
            summary = exc.to_dict()
            log_event(
                "source_pattern_source_draft_blocked",
                "Tk crawler asset UI kept a detected source URL in review.",
                level="warning",
                component="ui.crawler_assets",
                context={
                    "source_url": url,
                    "review_reason": summary.get("review_reason", ""),
                    "source_pattern_detection": summary.get("source_pattern_detection", {}),
                    "next_action": summary.get("next_action", ""),
                },
            )
            review_message = self.source_pattern_draft_review_message(summary)
            review_reason = str(summary.get("review_reason") or exc.reason_code)
            self.root.after(
                0,
                lambda: messagebox.showwarning(
                    self.tr("來源草稿保留審核", "Source draft kept in review"),
                    review_message,
                    parent=getattr(self, "root", None),
                ),
            )
            self.root.after(
                0,
                lambda: self.status_var.set(
                    self.tr(
                        f"來源草稿保留審核：{review_reason}",
                        f"Source draft kept in review: {review_reason}",
                    )
                ),
            )
            return
        except Exception as exc:
            error_message = str(exc)
            log_exception("source_pattern_source_draft_failed", exc, component="ui.crawler_assets", context={"source_url": url})
            self.root.after(0, lambda: messagebox.showerror(self.tr("來源草稿建立失敗", "Source draft failed"), error_message, parent=getattr(self, "root", None)))
            self.root.after(0, lambda: self.status_var.set(self.tr(f"來源草稿建立失敗：{error_message}", f"Source draft failed: {error_message}")))
            return
        def finish() -> None:
            self.refresh_crawler_asset_tab()
            source_ids = ", ".join(str(item) for item in summary.get("audit_source_ids", []) if item)
            self.status_var.set(
                self.tr(
                    f"已建立本機來源草稿：{source_ids or url}；下一步請跑本機 discovery audit。",
                    f"Local source draft created: {source_ids or url}; run local discovery audit next.",
                )
            )
            messagebox.showinfo(
                self.tr("來源草稿已建立", "Source draft created"),
                self.source_pattern_draft_message(summary),
                parent=getattr(self, "root", None),
            )

        self.root.after(0, finish)

    def source_pattern_draft_message(self, summary: object) -> str:
        return source_pattern_draft_message(summary, self.tr)

    def source_pattern_draft_review_message(self, summary: object) -> str:
        return source_pattern_draft_review_message(summary, self.tr)

    def open_selected_crawler_asset_profile_dialog(self) -> None:
        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        dialog = CrawlerAssetProfileDialog(getattr(self, "root", None), asset)
        if dialog.result is None:
            return
        try:
            update_crawler_asset_profile(asset.asset_id, **dialog.result)
        except Exception as exc:
            log_exception("crawler_asset_profile_update_failed", exc, component="ui.crawler_assets", context={"asset_id": asset.asset_id})
            messagebox.showerror(self.tr("爬蟲設定失敗", "Crawler settings failed"), str(exc), parent=getattr(self, "root", None))
            return
        self.refresh_crawler_asset_tab()
        if hasattr(self, "crawler_asset_tree") and asset.asset_id in self.crawler_asset_tree.get_children():
            self.crawler_asset_tree.item(asset.asset_id, values=self.crawler_asset_row_values(asset))
            self.crawler_asset_tree.selection_set(asset.asset_id)
            self.crawler_asset_tree.focus(asset.asset_id)
            self.on_crawler_asset_select()
        self.status_var.set(self.tr(f"爬蟲設定已儲存：{asset.display_name}", f"Crawler settings saved: {asset.display_name}"))

    def open_selected_crawler_asset_credential_dialog(
        self,
        asset: CrawlerAsset | None = None,
        *,
        credential_guard: object | None = None,
        update_cancel_status: bool = True,
    ) -> dict[str, object] | None:
        """Open the local login/settings editor for one crawler asset.

        Tk only collects the credential payload.  The backend local credential
        service owns editable fields, file writes, process-env updates, masking,
        and blocking-state calculation.
        """

        asset = asset or self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return None
        guard = credential_guard if isinstance(credential_guard, dict) else crawler_asset_credential_status(asset)
        dialog = CrawlerAssetCredentialDialog(getattr(self, "root", None), asset, guard)
        if dialog.result is None:
            if update_cancel_status:
                self.status_var.set(self.tr("登入設定未變更。", "Login settings were not changed."))
            return None
        try:
            refreshed = update_crawler_asset_credentials(asset, dict(dialog.result))
        except Exception as exc:
            log_exception("crawler_asset_credentials_update_failed", exc, component="ui.crawler_assets", context={"asset_id": asset.asset_id})
            messagebox.showerror(self.tr("登入設定儲存失敗", "Login settings failed"), str(exc), parent=getattr(self, "root", None))
            return None
        log_event(
            "crawler_asset_credentials_updated",
            "Tk crawler asset workflow updated local credential settings.",
            component="ui.crawler_assets",
            context=crawler_asset_credential_event_context(asset, refreshed),
        )
        label = str(refreshed.get("display_label") or "").strip()
        self.status_var.set(
            self.tr(
                f"登入設定已儲存：{asset.display_name}（{label or '已更新'}）。",
                f"Login settings saved: {asset.display_name} ({label or 'updated'}).",
            )
        )
        if hasattr(self, "crawler_asset_tree") and asset.asset_id in self.crawler_asset_tree.get_children():
            self.crawler_asset_tree.selection_set(asset.asset_id)
            self.crawler_asset_tree.focus(asset.asset_id)
            self.on_crawler_asset_select()
        return dict(refreshed)

    def load_selected_crawler_asset_seed_page(self) -> None:
        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        self.load_crawler_asset_seed_page(asset, page=1)

    def show_more_selected_crawler_asset_seeds(self) -> None:
        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        current = getattr(self, "crawler_asset_seed_pages", {}).get(asset.asset_id)
        summary = current.get("page_summary") if isinstance(current, dict) and isinstance(current.get("page_summary"), dict) else {}
        next_page = int(summary.get("next_page") or 0) if summary else 0
        if next_page <= 0:
            self.status_var.set(self.tr("目前 seed 清單已顯示到本機最後一頁。", "Seed list is already at the final local page."))
            return
        self.load_crawler_asset_seed_page(asset, page=next_page)

    def load_crawler_asset_seed_page(self, asset: CrawlerAsset, *, page: int = 1) -> None:
        """讀取本機 catalog seed page；不重新打遠端 crawler。

        "Show more" expands the local catalog window.  Live enumeration belongs
        to ``run_selected_crawler_asset_listing`` and must remain a separate
        explicit user action.
        """

        provider_id = asset.provider_id
        source = load_crawler_asset_source(asset.asset_id)
        if source is not None:
            provider_id = str(getattr(source, "provider_id", "") or provider_id)
        if not provider_id:
            self.status_var.set(
                self.tr(
                    "這個爬蟲資產缺少 provider_id，無法讀取本機 seed 清單。",
                    "This crawler asset has no provider_id, so its local seed page cannot be read.",
                )
            )
            return
        try:
            conn = self._connect()
            try:
                repository = ApiCatalogRepository(conn)
                payload = crawler_seed_page(
                    repository,
                    asset_id=asset.asset_id,
                    provider_id=provider_id,
                    page=page,
                    favorite_seed_uids=crawler_asset_favorite_seed_uids(asset.asset_id),
                )
            finally:
                conn.close()
        except Exception as exc:  # pragma: no cover - Tk surface guard
            log_exception("crawler_asset_seed_page_failed", exc, component="ui.crawler_assets", context={"asset_id": asset.asset_id})
            self.status_var.set(self.tr(f"Seed 清單讀取失敗：{exc}", f"Failed to load seed page: {exc}"))
            return
        if not hasattr(self, "crawler_asset_seed_pages"):
            self.crawler_asset_seed_pages = {}
        self.crawler_asset_seed_pages[asset.asset_id] = payload
        if hasattr(self, "crawler_asset_seed_page_var"):
            self.crawler_asset_seed_page_var.set(crawler_asset_seed_page_preview_text(payload, self.tr))
        self.status_var.set(crawler_asset_seed_page_status_text(payload, self.tr))

    def open_selected_crawler_asset_seed_dialog(self) -> None:
        """Open the loaded seed page as an actionable seed table."""

        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        payload = getattr(self, "crawler_asset_seed_pages", {}).get(asset.asset_id)
        if not isinstance(payload, dict):
            self.load_crawler_asset_seed_page(asset, page=1)
            payload = getattr(self, "crawler_asset_seed_pages", {}).get(asset.asset_id)
        if not isinstance(payload, dict):
            self.status_var.set(self.tr("尚未取得 seed 清單；請先執行清單擷取。", "No seed list is available yet; run listing first."))
            return
        dialog = CrawlerAssetSeedDialog(getattr(self, "root", None), payload, self.tr)
        if not isinstance(dialog.result, dict):
            return
        action = str(dialog.result.get("action") or "").strip()
        dataset_uid = str(dialog.result.get("dataset_uid") or "").strip()
        if action == "favorite":
            self.toggle_crawler_asset_seed_favorite(
                asset,
                dataset_uid=dataset_uid,
                favorite=bool(dialog.result.get("favorite")),
                current_payload=payload,
            )
        elif action == "download":
            self.run_crawler_asset_seed_download_import_from_ui(asset, dataset_uid=dataset_uid)
        elif action == "schema_probe":
            entry = dialog.result.get("entry")
            self.run_crawler_asset_seed_schema_probe_from_ui(
                asset,
                dataset_uid=dataset_uid,
                entry=dict(entry) if isinstance(entry, dict) else {},
            )

    def toggle_crawler_asset_seed_favorite(
        self,
        asset: CrawlerAsset,
        *,
        dataset_uid: str,
        favorite: bool,
        current_payload: object | None = None,
    ) -> None:
        """Persist seed-level favorite state, then refresh the same local page."""

        if not dataset_uid:
            self.status_var.set(self.tr("這筆 seed 缺少可用 ID，無法收藏。", "This seed has no usable ID to favorite."))
            return
        try:
            result = save_crawler_seed_favorite(asset_id=asset.asset_id, dataset_uid=dataset_uid, favorite=favorite)
            log_event(
                "crawler_seed_favorite_saved",
                "Tk crawler asset workflow saved a seed-level favorite.",
                component="ui.crawler_assets",
                context=result,
            )
        except Exception as exc:  # pragma: no cover - Tk surface guard
            log_exception("crawler_seed_favorite_failed", exc, component="ui.crawler_assets", context={"asset_id": asset.asset_id, "dataset_uid": dataset_uid})
            messagebox.showerror(self.tr("Seed 收藏失敗", "Seed favorite failed"), str(exc), parent=getattr(self, "root", None))
            return
        page = 1
        if isinstance(current_payload, dict):
            try:
                page = int(current_payload.get("page") or 1)
            except (TypeError, ValueError):
                page = 1
        self.load_crawler_asset_seed_page(asset, page=page)
        self.status_var.set(
            self.tr(
                f"Seed 收藏已{'加入' if favorite else '取消'}：{dataset_uid}",
                f"Seed favorite {'saved' if favorite else 'removed'}: {dataset_uid}",
            )
        )

    def run_crawler_asset_seed_schema_probe_from_ui(
        self,
        asset: CrawlerAsset,
        *,
        dataset_uid: str,
        entry: dict[str, object],
    ) -> None:
        """Probe one seed URL, then open the shared bounds form with selectors.

        The seed dialog only chooses the row.  The workflow invokes the same
        backend schema probe used by Web, then renders the returned form spec in
        Tk so source-specific schema rules stay outside the UI shell.
        """

        if not dataset_uid:
            self.status_var.set(self.tr("這筆 seed 缺少可用 ID，無法探測欄位。", "This seed has no usable ID to probe."))
            return
        if asset.archived:
            self.status_var.set(self.tr("這個爬蟲已封存；請先解除封存再探測欄位。", "This crawler is archived; unarchive it before probing fields."))
            return
        if not entry:
            self.status_var.set(self.tr("這筆 seed 缺少可探測 URL。", "This seed has no probeable URL."))
            return
        bounds_schema = crawler_asset_download_plan_bounds_schema(asset)
        if not bounds_schema:
            self.status_var.set(self.tr("這個爬蟲資產沒有可探測的界域表單。", "This crawler asset has no bounds form to enrich."))
            return
        started = self._start_crawler_asset_background_job(
            ("seed_schema_probe", asset.asset_id, dataset_uid),
            self._crawler_asset_seed_schema_probe_worker,
            (asset.asset_id, dataset_uid, dict(entry)),
            duplicate_status_zh=f"Seed 欄位探測已在執行：{dataset_uid}",
            duplicate_status_en=f"Seed field probe is already running: {dataset_uid}",
        )
        if started:
            self.status_var.set(
                self.tr(
                    f"正在探測 seed 欄位：{dataset_uid}",
                    f"Probing seed fields: {dataset_uid}",
                )
            )

    def _crawler_asset_seed_schema_probe_worker(
        self,
        asset_id: str,
        dataset_uid: str,
        entry: dict[str, object],
    ) -> None:
        try:
            result = crawler_asset_bound_form_schema_probe_result(
                asset_id,
                {"entry": entry, "row_limit": 5, "timeout": 8.0},
            )
            probe = result.probe
            spec = result.bound_form
        except Exception as exc:
            log_exception(
                "crawler_seed_schema_probe_failed",
                exc,
                component="ui.crawler_assets",
                context={"asset_id": asset_id, "dataset_uid": dataset_uid},
            )
            self.root.after(0, lambda: messagebox.showerror(self.tr("Seed 欄位探測失敗", "Seed schema probe failed"), str(exc), parent=getattr(self, "root", None)))
            self.root.after(0, lambda: self.status_var.set(self.tr(f"Seed 欄位探測失敗：{exc}", f"Seed schema probe failed: {exc}")))
            return

        log_event(
            "crawler_seed_schema_probe_completed",
            "Tk crawler asset workflow probed one seed and opened the shared bounds form.",
            component="ui.crawler_assets",
            context=crawler_seed_schema_probe_event_context(asset_id, dataset_uid, probe, spec),
        )
        self.root.after(0, lambda: self._finish_crawler_asset_seed_schema_probe(dataset_uid, probe, spec))

    def _finish_crawler_asset_seed_schema_probe(self, dataset_uid: str, probe: object, spec: object) -> None:
        probe_status = str(getattr(probe, "status", "") or "").strip()
        probe_error = str(getattr(probe, "error", "") or "").strip()
        if probe_status != "ok":
            messagebox.showwarning(
                self.tr("Seed 欄位探測未完成", "Seed schema probe incomplete"),
                self.tr(
                    f"未取得欄位清單：{probe_error or probe_status or '-'}\n仍會開啟原本界域表單；你可以套用推薦值或手動輸入。",
                    f"Could not fetch columns: {probe_error or probe_status or '-'}\nThe original bounds form will still open; use recommendations or enter values manually.",
                ),
                parent=getattr(self, "root", None),
            )
        dialog = CrawlerAssetBoundDialog(getattr(self, "root", None), spec, self.tr)
        if dialog.result is None:
            self.status_var.set(self.tr("欄位探測後的界域設定已取消。", "Bounds setup after field probe was cancelled."))
            return
        if not hasattr(self, "crawler_asset_bound_payloads"):
            self.crawler_asset_bound_payloads = {}
        self.crawler_asset_bound_payloads[spec.asset_id] = dialog.result.to_dict()
        self.status_var.set(
            self.tr(
                f"已用 seed 欄位探測更新界域：{dataset_uid}",
                f"Bounds updated from seed schema probe: {dataset_uid}",
            )
        )

    def run_crawler_asset_seed_download_import_from_ui(self, asset: CrawlerAsset, *, dataset_uid: str) -> None:
        """Run formal seed download/import for one selected seed row."""

        if not dataset_uid:
            self.status_var.set(self.tr("這筆 seed 缺少可用 ID，無法下載。", "This seed has no usable ID to download."))
            return
        if asset.archived:
            self.status_var.set(self.tr("這個爬蟲已封存；請先解除封存再下載 seed。", "This crawler is archived; unarchive it before downloading a seed."))
            return
        credential_guard = crawler_asset_credential_status(asset)
        if credential_status_blocks_download(credential_guard):
            title = self.tr("需要登入 / API Key", "Login/API key required")
            self.status_var.set(self.tr("Seed 下載已暫停：請先完成登入設定。", "Seed download paused: finish login settings first."))
            refreshed = self.open_selected_crawler_asset_credential_dialog(
                asset,
                credential_guard=credential_guard,
                update_cancel_status=False,
            )
            if refreshed is None:
                return
            if credential_status_blocks_download(refreshed):
                messagebox.showwarning(
                    title,
                    crawler_asset_credential_guard_message(refreshed, self.tr),
                    parent=getattr(self, "root", None),
                )
                return
            messagebox.showinfo(
                self.tr("登入設定已完成", "Login settings saved"),
                self.tr(
                    "登入設定已保存；請再次按「下載此 seed」開始下載。",
                    "Login settings are saved. Press Download this seed again to start.",
                ),
                parent=getattr(self, "root", None),
            )
            return
        bounds_payload = self.crawler_asset_bound_payload_for_asset(asset.asset_id)
        started = self._start_crawler_asset_background_job(
            ("seed_download_import", asset.asset_id, dataset_uid),
            self._crawler_asset_seed_download_import_worker,
            (asset.asset_id, dataset_uid, bounds_payload),
            duplicate_status_zh=f"Seed 下載 / 匯入已在執行：{dataset_uid}",
            duplicate_status_en=f"Seed download/import is already running: {dataset_uid}",
        )
        if started:
            self.status_var.set(
                self.tr(
                    f"正在下載 / 匯入 seed：{dataset_uid}",
                    f"Downloading / importing seed: {dataset_uid}",
                )
            )

    def crawler_asset_bound_payload_for_asset(self, asset_id: str) -> CrawlerAssetBoundPayload | None:
        """Return the latest bounds payload captured by the Tk bounds dialog."""

        return crawler_asset_bound_payload_from_cache(getattr(self, "crawler_asset_bound_payloads", {}), asset_id)

    def _crawler_asset_seed_download_import_worker(
        self,
        asset_id: str,
        dataset_uid: str,
        bounds_payload: CrawlerAssetBoundPayload | None,
    ) -> None:
        """Background worker for one seed row's formal download/import path.

        The worker only wraps the backend service in a Tk-safe thread.  All plan,
        download, import, and credential behavior stays inside api_launcher.
        """

        try:
            targets = crawler_seed_download_import_target_paths(asset_id, dataset_uid)
            conn = self._connect()
            try:
                repository = ApiCatalogRepository(conn)
                result = run_crawler_seed_download_import(
                    asset_id,
                    dataset_uid,
                    repository,
                    targets.downloads_root,
                    bounds_payload=bounds_payload,
                    import_sqlite_path=targets.import_sqlite_path,
                    plan_path=targets.plan_path,
                    timeout=8.0,
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            log_exception(
                "crawler_seed_download_import_failed",
                exc,
                component="ui.crawler_assets",
                context={"asset_id": asset_id, "dataset_uid": dataset_uid},
            )
            self.root.after(0, lambda: messagebox.showerror(self.tr("Seed 下載 / 匯入失敗", "Seed download/import failed"), str(exc), parent=getattr(self, "root", None)))
            self.root.after(0, lambda: self.status_var.set(self.tr(f"Seed 下載 / 匯入失敗：{exc}", f"Seed download/import failed: {exc}")))
            return

        log_event(
            "crawler_seed_download_import_completed",
            "Tk crawler asset workflow ran the formal seed download/import path.",
            component="ui.crawler_assets",
            context={
                "asset_id": asset_id,
                "dataset_uid": dataset_uid,
                "stage": result.pipeline.stage,
                "succeeded": result.succeeded,
                "download_import": result.pipeline.to_dict(),
                "artifacts": result.to_dict().get("artifacts", {}),
            },
        )
        self.root.after(0, lambda: self._finish_crawler_asset_seed_download_import(result))

    def _finish_crawler_asset_seed_download_import(self, result: object) -> None:
        ui_message = crawler_seed_download_import_ui_message(result, self.tr)
        self.status_var.set(ui_message.status_message)
        if ui_message.succeeded:
            messagebox.showinfo(ui_message.title, ui_message.body, parent=getattr(self, "root", None))
        else:
            messagebox.showwarning(ui_message.title, ui_message.body, parent=getattr(self, "root", None))

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
        started = self._start_crawler_asset_background_job(
            ("asset_listing", asset.asset_id, ""),
            self._crawler_asset_listing_worker,
            (asset.asset_id,),
            duplicate_status_zh=f"入口清單擷取已在執行：{asset.asset_id}",
            duplicate_status_en=f"Dataset listing is already running: {asset.asset_id}",
        )
        if started:
            self.status_var.set(
                self.tr(
                    f"正在擷取入口清單；入口：{asset.asset_id}。",
                    f"Listing datasets for source: {asset.asset_id}.",
                )
            )

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

        self.record_crawler_asset_listing_outcome(result)

        def finish() -> None:
            if result.blocked:
                self.status_var.set(crawler_asset_listing_blocked_status_text(result, self.tr))
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

    def record_crawler_asset_listing_outcome(self, result: object) -> None:
        """把 listing 結果留下 compact event，供 handoff/Web/Qt 讀取。

        清單擷取是 crawler run 的前半段，不能只靠 status bar 呈現；但 event
        也不能塞完整候選清單，所以這裡只保存 counts、next_action 與 run_record。
        """

        try:
            event_payload = crawler_asset_listing_outcome_event_payload(result)
            log_event(
                "crawler_asset_listing_recorded",
                "Tk crawler asset workflow recorded the visible listing outcome.",
                component="ui.crawler_assets",
                context=event_payload.context,
            )
            if not hasattr(self, "crawler_asset_listing_outcomes"):
                self.crawler_asset_listing_outcomes = {}
            if event_payload.asset_id:
                self.crawler_asset_listing_outcomes[event_payload.asset_id] = event_payload.preview
        except Exception:
            # event log 是 handoff 輔助，不應阻斷 UI listing 完成路徑。
            return

    def prepare_selected_crawler_asset_download(self) -> None:
        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        if asset.archived:
            self.status_var.set(self.tr("這個爬蟲已封存；請先解除封存再送到下載器。", "This crawler is archived; unarchive it before sending it to Downloader."))
            return
        job_key = ("asset_download_plan", asset.asset_id, "")
        if self._crawler_asset_background_job_is_active(
            job_key,
            duplicate_status_zh=f"下載計畫建立已在執行：{asset.asset_id}",
            duplicate_status_en=f"Download-plan build is already running: {asset.asset_id}",
        ):
            return
        bounds_payload = None
        bounds_schema = crawler_asset_download_plan_bounds_schema(asset)
        if bounds_schema:
            # 這裡只產生來源界域 payload，不直接下載。Tk/Qt 之後都應共用同一份 form spec。
            spec = build_crawler_asset_bound_form_spec(asset.asset_id, bounds_schema)
            dialog = CrawlerAssetBoundDialog(getattr(self, "root", None), spec, self.tr)
            if dialog.result is None:
                self.status_var.set(self.tr("界域設定已取消；尚未送進下載器。", "Bounds setup cancelled; crawler asset was not sent to Downloader."))
                return
            if not hasattr(self, "crawler_asset_bound_payloads"):
                self.crawler_asset_bound_payloads = {}
            self.crawler_asset_bound_payloads[asset.asset_id] = dialog.result.to_dict()
            bounds_payload = dialog.result
        self.active_provider_id = asset.provider_id
        started = self._start_crawler_asset_background_job(
            job_key,
            self._crawler_asset_download_plan_worker,
            (asset.asset_id, bounds_payload),
            duplicate_status_zh=f"下載計畫建立已在執行：{asset.asset_id}",
            duplicate_status_en=f"Download-plan build is already running: {asset.asset_id}",
        )
        if started:
            self.status_var.set(
                self.tr(
                    f"正在用爬蟲資產建立下載計畫：{asset.display_name}",
                    f"Building download plan from crawler asset: {asset.display_name}",
                )
            )

    def _crawler_asset_download_plan_worker(self, asset_id: str, bounds_payload: CrawlerAssetBoundPayload | None) -> None:
        # crawler asset -> bounds -> plan 的實作放在 service；Tk 只做顯示與 plan 匯入。
        try:
            conn = self._connect()
            try:
                result = build_crawler_asset_download_plan(
                    asset_id,
                    conn,
                    bounds_payload=bounds_payload,
                    downloads_root=DOWNLOADS_DIR,
                )
            finally:
                conn.close()
            written_paths: dict[str, str] = {}
            if result.plan_build is not None:
                written_paths = write_crawler_asset_download_plan_artifacts(
                    asset_id,
                    result.original_plan,
                    result.resolved_plan,
                )
            if written_paths:
                log_event(
                    "crawler_asset_download_plan_built",
                    "Tk crawler asset workflow built a bounded download plan.",
                    component="ui.crawler_assets",
                    context={
                        "asset_id": asset_id,
                        "direct_download_count": result.direct_download_count,
                        "review_required_count": result.review_required_count,
                        "resolved_plan": written_paths.get("resolved", ""),
                    },
                )
        except Exception as exc:
            log_exception("crawler_asset_download_plan_failed", exc, component="ui.crawler_assets", context={"asset_id": asset_id})
            self.root.after(0, lambda: messagebox.showerror(self.tr("建立下載計畫失敗", "Build download plan failed"), str(exc), parent=getattr(self, "root", None)))
            self.root.after(0, lambda: self.status_var.set(self.tr(f"建立爬蟲下載計畫失敗：{exc}", f"Crawler download plan failed: {exc}")))
            return

        self.root.after(0, lambda: self._finish_crawler_asset_download_plan(result, written_paths))

    def _finish_crawler_asset_download_plan(self, result, written_paths: dict[str, str]) -> None:
        if result.blocked:
            summary = crawler_asset_download_plan_summary_text(result, 0, "", self.tr)
            cache_crawler_asset_plan_state(self, result, 0)
            self.record_crawler_asset_plan_outcome(result, 0, written_paths)
            self.refresh_crawler_asset_plan_row(result.asset_id)
            self.status_var.set(summary.replace("\n", " "))
            messagebox.showwarning(
                self.tr("爬蟲下載計畫被擋下", "Crawler download plan blocked"),
                summary,
                parent=getattr(self, "root", None),
            )
            return
        added = self.add_download_plan_entries_from_payload(result.resolved_plan) if result.resolved_plan else 0
        self.render_table()
        self.update_download_plan_panel()
        if added and hasattr(self, "main_notebook") and hasattr(self, "downloader_tab"):
            self.main_notebook.select(self.downloader_tab)
        resolved_path = written_paths.get("resolved", "")
        summary = crawler_asset_download_plan_summary_text(result, added, resolved_path, self.tr)
        cache_crawler_asset_plan_state(self, result, added)
        self.record_crawler_asset_plan_outcome(result, added, written_paths)
        self.refresh_crawler_asset_plan_row(result.asset_id)
        self.status_var.set(summary.splitlines()[0])
        messagebox.showinfo(self.tr("爬蟲下載計畫已建立", "Crawler download plan built"), summary, parent=getattr(self, "root", None))

    def record_crawler_asset_plan_outcome(self, result: object, added_count: int, written_paths: dict[str, str]) -> None:
        """把 UI 可見結果寫成事件，供 handoff、重開 UI 與後續 agent 讀取。"""

        event_payload = crawler_asset_plan_outcome_event_payload(
            result,
            added_count=added_count,
            written_paths=written_paths,
        )
        try:
            update_crawler_asset_plan_passport(event_payload.asset_id, event_payload.plan_passport)
        except Exception as exc:
            log_exception(
                "crawler_asset_plan_passport_persist_failed",
                exc,
                component="ui.crawler_assets",
                context={"asset_id": event_payload.asset_id},
            )
        log_event(
            "crawler_asset_plan_outcome_recorded",
            "Tk crawler asset workflow recorded the visible send-to-downloader outcome.",
            component="ui.crawler_assets",
            context=event_payload.context,
        )

    def refresh_crawler_asset_plan_row(self, asset_id: str) -> None:
        """只更新單列結果，避免送進下載器後整張表閃動或失去選取。"""

        if not hasattr(self, "crawler_asset_tree"):
            return
        asset = getattr(self, "crawler_assets_by_id", {}).get(asset_id)
        if asset is None or asset_id not in self.crawler_asset_tree.get_children():
            return
        self.crawler_asset_tree.item(asset_id, values=self.crawler_asset_row_values(asset))
        self.crawler_asset_tree.selection_set(asset_id)
        self.crawler_asset_tree.focus(asset_id)
        self.on_crawler_asset_select()

    def open_selected_crawler_asset_adapter_review(self) -> None:
        """開啟同一輪 UI session 中由爬蟲資產產生的 adapter 待辦。"""

        asset = self.selected_crawler_asset()
        if asset is None:
            self.status_var.set(self.tr("請先選擇一個爬蟲資產。", "Select a crawler asset first."))
            return
        resolved_plan = getattr(self, "crawler_asset_resolved_plans", {}).get(asset.asset_id)
        if not isinstance(resolved_plan, dict):
            messagebox.showinfo(
                self.tr("沒有本次 Adapter 待辦", "No current adapter queue"),
                self.tr("請先按「送到下載器 / 設定界域」建立本次下載計畫。", "Build a download plan from this crawler asset first."),
                parent=getattr(self, "root", None),
            )
            return
        review_items = adapter_review_items(resolved_plan)
        if not review_items:
            messagebox.showinfo(
                self.tr("沒有 Adapter 待辦", "No adapter review items"),
                self.tr("本次計畫沒有需要 Adapter 接手的項目。", "The current plan has no adapter-required items."),
                parent=getattr(self, "root", None),
            )
            return
        AdapterReviewDialog(self, review_items)

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
