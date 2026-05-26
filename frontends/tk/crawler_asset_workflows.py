from __future__ import annotations

import json
import threading
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, StringVar, X, Y
from tkinter import messagebox, ttk
from typing import Callable

from api_launcher.adapter_review import adapter_review_items
from api_launcher.crawler_asset_profiles import toggle_crawler_asset_archived, update_crawler_asset_profile
from api_launcher.crawler_assets import BUILD_DOWNLOAD_PLAN, CrawlerAsset, load_crawler_assets, status_label
from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundPayload, build_crawler_asset_bound_form_spec
from api_launcher.crawler_asset_display import (
    adapter_review_content_summary_label,
    adapter_review_display_payload,
    crawler_asset_plan_passport_payload,
    crawler_asset_plan_outcome_payload,
)
from api_launcher.crawler_asset_service import build_crawler_asset_download_plan, run_crawler_asset_listing
from api_launcher.crawlers.source_patterns import DEFAULT_PATTERN_MINIMUM_CONFIDENCE
from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME
from api_launcher.downloads.staging import safe_path_part
from api_launcher.event_log import latest_events, log_event, log_exception
from api_launcher.paths import DOWNLOADS_DIR, local_config_file, state_file
from api_launcher.source_pattern_drafts import write_source_draft_from_url
from frontends.tk.crawler_asset_bound_dialog import CrawlerAssetBoundDialog
from frontends.tk.crawler_asset_profile_dialog import CrawlerAssetProfileDialog
from frontends.tk.dialogs import AdapterReviewDialog
from frontends.tk.source_pattern_draft_dialog import SourcePatternDraftDialog


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

        self.crawler_assets_by_id: dict[str, CrawlerAsset] = {}
        self.crawler_asset_plan_outcomes: dict[str, str] = {}
        self.crawler_asset_content_review_outcomes: dict[str, str] = {}
        self.crawler_asset_resolved_plans: dict[str, dict[str, object]] = {}
        self.crawler_asset_plan_passports: dict[str, dict[str, object]] = {}
        self.load_crawler_asset_plan_outcomes_from_events()
        self.refresh_crawler_asset_tab()

    def load_crawler_asset_plan_outcomes_from_events(self) -> None:
        """從 structured event 恢復最近送進下載器的可視狀態，避免重開 UI 後全部消失。"""

        self.crawler_asset_plan_outcomes = {}
        self.crawler_asset_content_review_outcomes = {}
        self.crawler_asset_resolved_plans = {}
        self.crawler_asset_plan_passports = {}
        for event in latest_events(200):
            if event.get("event") != "crawler_asset_plan_outcome_recorded":
                continue
            context = event.get("context") if isinstance(event.get("context"), dict) else {}
            asset_id = str(context.get("asset_id") or "").strip()
            outcome_label = str(context.get("outcome_label") or "").strip()
            if not asset_id or not outcome_label:
                continue
            self.crawler_asset_plan_outcomes[asset_id] = outcome_label
            content_review_label = str(context.get("content_review_label") or "").strip()
            content_review_payload = context.get("content_review") if isinstance(context.get("content_review"), dict) else {}
            if not content_review_label and isinstance(content_review_payload, dict):
                content_review_label = str(content_review_payload.get("display_label") or "").strip()
            if content_review_label:
                self.crawler_asset_content_review_outcomes[asset_id] = content_review_label
            plan_passport = context.get("plan_passport") if isinstance(context.get("plan_passport"), dict) else {}
            if isinstance(plan_passport, dict) and plan_passport:
                self.crawler_asset_plan_passports[asset_id] = dict(plan_passport)
            resolved_plan_path = str(context.get("resolved_plan") or "").strip()
            if not resolved_plan_path:
                continue
            try:
                payload = json.loads(Path(resolved_plan_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                self.crawler_asset_resolved_plans[asset_id] = payload
                if not content_review_label:
                    label = adapter_review_content_summary_label(adapter_review_display_payload(payload))
                    if label:
                        self.crawler_asset_content_review_outcomes[asset_id] = label

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
        last_plan_outcome = getattr(self, "crawler_asset_plan_outcomes", {}).get(asset.asset_id) or asset.next_action
        content_review = getattr(self, "crawler_asset_content_review_outcomes", {}).get(asset.asset_id, "")
        if content_review:
            last_plan_outcome = f"{last_plan_outcome} / {content_review}"
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
            last_plan_outcome,
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
        last_plan_outcome = getattr(self, "crawler_asset_plan_outcomes", {}).get(asset.asset_id, "")
        content_review = getattr(self, "crawler_asset_content_review_outcomes", {}).get(asset.asset_id, "")
        last_plan_line_zh = f"\n上次送進下載器：{last_plan_outcome}\n" if last_plan_outcome else ""
        last_plan_line_en = f"\nLast send-to-downloader result: {last_plan_outcome}\n" if last_plan_outcome else ""
        content_review_line_zh = f"內容格式待辦：{content_review}\n" if content_review else ""
        content_review_line_en = f"Content review: {content_review}\n" if content_review else ""
        review_count = crawler_asset_review_count_from_plan(getattr(self, "crawler_asset_resolved_plans", {}).get(asset.asset_id))
        review_line_zh = f"本次 Adapter 待辦：{review_count}\n" if review_count else ""
        review_line_en = f"Current adapter queue: {review_count}\n" if review_count else ""
        plan_passport_summary = crawler_asset_plan_passport_summary_text(
            getattr(self, "crawler_asset_plan_passports", {}).get(asset.asset_id),
            self.tr,
        )
        plan_passport_line = f"{plan_passport_summary}\n" if plan_passport_summary else ""
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
                    f"{last_plan_line_zh}"
                    f"{content_review_line_zh}"
                    f"{review_line_zh}"
                    f"{plan_passport_line}"
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
                    f"{last_plan_line_en}"
                    f"{content_review_line_en}"
                    f"{review_line_en}"
                    f"{plan_passport_line}"
                    f"{capability_lines}\n\n"
                    f"Bounds schema: {bounds_summary_en or 'none'}\n\n"
                    "Selected downloads are decorated by bounds: version, time, bbox, columns, and limits."
                ),
            )
        )

    def on_crawler_asset_double_click(self, _event: object | None = None) -> None:
        self.prepare_selected_crawler_asset_download()

    def open_source_pattern_draft_dialog(self) -> None:
        dialog = SourcePatternDraftDialog(getattr(self, "root", None), self.tr)
        if dialog.result is None:
            return
        url = str(dialog.result.get("url") or "")
        self.status_var.set(self.tr(f"正在辨識來源 URL：{url}", f"Detecting source URL: {url}"))
        threading.Thread(target=self._source_pattern_draft_worker, args=(dict(dialog.result),), daemon=True).start()

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
        except Exception as exc:
            log_exception("source_pattern_source_draft_failed", exc, component="ui.crawler_assets", context={"source_url": url})
            self.root.after(0, lambda: messagebox.showerror(self.tr("來源草稿建立失敗", "Source draft failed"), str(exc), parent=getattr(self, "root", None)))
            self.root.after(0, lambda: self.status_var.set(self.tr(f"來源草稿建立失敗：{exc}", f"Source draft failed: {exc}")))
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
        data = summary if isinstance(summary, dict) else {}
        detection = data.get("source_pattern_detection") if isinstance(data.get("source_pattern_detection"), dict) else {}
        sources = data.get("sources") if isinstance(data.get("sources"), list) else []
        source = sources[0] if sources and isinstance(sources[0], dict) else {}
        evidence = detection.get("evidence") if isinstance(detection.get("evidence"), list) else []
        evidence_preview = "\n".join(f"- {item}" for item in evidence[:5]) or "-"
        try:
            confidence_text = f"{float(detection.get('confidence')):.2f}"
        except (TypeError, ValueError):
            confidence_text = "-"
        return self.tr(
            (
                "已建立本機資料源草稿。\n\n"
                "這不是正式 catalog promotion，也不會下載或匯入資料；下一步必須執行本機 discovery audit。\n\n"
                f"Pattern：{detection.get('pattern_id') or '-'}\n"
                f"信心：{confidence_text}\n"
                f"Source type：{detection.get('source_type_hint') or source.get('source_type') or '-'}\n"
                f"Source ID：{source.get('source_id') or '-'}\n"
                f"Endpoint：{source.get('endpoint_url') or '-'}\n\n"
                f"證據：\n{evidence_preview}\n\n"
                f"Local draft：{data.get('dataset_source_path') or '-'}\n"
                f"下一步：{data.get('audit_command') or data.get('next_action') or '-'}"
            ),
            (
                "Local dataset source draft created.\n\n"
                "This is not catalog promotion and does not download or import data; run local discovery audit next.\n\n"
                f"Pattern: {detection.get('pattern_id') or '-'}\n"
                f"Confidence: {confidence_text}\n"
                f"Source type: {detection.get('source_type_hint') or source.get('source_type') or '-'}\n"
                f"Source ID: {source.get('source_id') or '-'}\n"
                f"Endpoint: {source.get('endpoint_url') or '-'}\n\n"
                f"Evidence:\n{evidence_preview}\n\n"
                f"Local draft: {data.get('dataset_source_path') or '-'}\n"
                f"Next: {data.get('audit_command') or data.get('next_action') or '-'}"
            ),
        )

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
            self.crawler_asset_tree.selection_set(asset.asset_id)
            self.crawler_asset_tree.focus(asset.asset_id)
            self.on_crawler_asset_select()
        self.status_var.set(self.tr(f"爬蟲設定已儲存：{asset.display_name}", f"Crawler settings saved: {asset.display_name}"))

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
        bounds_payload = None
        plan_capability = next((item for item in asset.capabilities if item.capability_id == BUILD_DOWNLOAD_PLAN), None)
        if plan_capability is not None and plan_capability.bounds_schema:
            # 這裡只產生來源界域 payload，不直接下載。Tk/Qt 之後都應共用同一份 form spec。
            spec = build_crawler_asset_bound_form_spec(asset.asset_id, plan_capability.bounds_schema)
            dialog = CrawlerAssetBoundDialog(getattr(self, "root", None), spec, self.tr)
            if dialog.result is None:
                self.status_var.set(self.tr("界域設定已取消；尚未送進下載器。", "Bounds setup cancelled; crawler asset was not sent to Downloader."))
                return
            if not hasattr(self, "crawler_asset_bound_payloads"):
                self.crawler_asset_bound_payloads = {}
            self.crawler_asset_bound_payloads[asset.asset_id] = dialog.result.to_dict()
            bounds_payload = dialog.result
        self.active_provider_id = asset.provider_id
        self.status_var.set(
            self.tr(
                f"正在用爬蟲資產建立下載計畫：{asset.display_name}",
                f"Building download plan from crawler asset: {asset.display_name}",
            )
        )
        threading.Thread(
            target=self._crawler_asset_download_plan_worker,
            args=(asset.asset_id, bounds_payload),
            daemon=True,
        ).start()

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
                slug = safe_path_part(asset_id)
                original_path = state_file(f"crawler_asset_plans/{slug}.original.json")
                resolved_path = state_file(f"crawler_asset_plans/{slug}.resolved.json")
                original_path.parent.mkdir(parents=True, exist_ok=True)
                original_path.write_text(json.dumps(result.original_plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                resolved_path.write_text(json.dumps(result.resolved_plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                written_paths = {"original": str(original_path), "resolved": str(resolved_path)}
                log_event(
                    "crawler_asset_download_plan_built",
                    "Tk crawler asset workflow built a bounded download plan.",
                    component="ui.crawler_assets",
                    context={
                        "asset_id": asset_id,
                        "direct_download_count": result.direct_download_count,
                        "review_required_count": result.review_required_count,
                        "resolved_plan": str(resolved_path),
                    },
                )
        except Exception as exc:
            log_exception("crawler_asset_download_plan_failed", exc, component="ui.crawler_assets", context={"asset_id": asset_id})
            self.root.after(0, lambda: messagebox.showerror(self.tr("建立下載計畫失敗", "Build download plan failed"), str(exc), parent=getattr(self, "root", None)))
            self.root.after(0, lambda: self.status_var.set(self.tr(f"建立爬蟲下載計畫失敗：{exc}", f"Crawler download plan failed: {exc}")))
            return

        self.root.after(0, lambda: self._finish_crawler_asset_download_plan(result, written_paths))

    def _finish_crawler_asset_download_plan(self, result, written_paths: dict[str, str]) -> None:
        if not hasattr(self, "crawler_asset_plan_outcomes"):
            self.crawler_asset_plan_outcomes = {}
        if not hasattr(self, "crawler_asset_resolved_plans"):
            self.crawler_asset_resolved_plans = {}
        if not hasattr(self, "crawler_asset_content_review_outcomes"):
            self.crawler_asset_content_review_outcomes = {}
        if not hasattr(self, "crawler_asset_plan_passports"):
            self.crawler_asset_plan_passports = {}
        if result.blocked:
            summary = crawler_asset_download_plan_summary_text(result, 0, "", self.tr)
            self.crawler_asset_plan_outcomes[result.asset_id] = crawler_asset_plan_outcome_label(result, 0)
            self.crawler_asset_content_review_outcomes.pop(result.asset_id, None)
            self.crawler_asset_resolved_plans.pop(result.asset_id, None)
            self.crawler_asset_plan_passports[result.asset_id] = crawler_asset_plan_passport_payload(
                result,
                plan_outcome=crawler_asset_plan_outcome_payload(result, added_count=0),
            )
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
        self.crawler_asset_plan_outcomes[result.asset_id] = crawler_asset_plan_outcome_label(result, added)
        outcome_payload = crawler_asset_plan_outcome_payload(result, added_count=added)
        self.crawler_asset_plan_passports[result.asset_id] = crawler_asset_plan_passport_payload(
            result,
            plan_outcome=outcome_payload,
        )
        content_review_label = str(outcome_payload.get("content_review_label") or "").strip()
        if content_review_label:
            self.crawler_asset_content_review_outcomes[result.asset_id] = content_review_label
        else:
            self.crawler_asset_content_review_outcomes.pop(result.asset_id, None)
        if result.resolved_plan:
            self.crawler_asset_resolved_plans[result.asset_id] = result.resolved_plan
        else:
            self.crawler_asset_resolved_plans.pop(result.asset_id, None)
        self.record_crawler_asset_plan_outcome(result, added, written_paths)
        self.refresh_crawler_asset_plan_row(result.asset_id)
        self.status_var.set(summary.splitlines()[0])
        messagebox.showinfo(self.tr("爬蟲下載計畫已建立", "Crawler download plan built"), summary, parent=getattr(self, "root", None))

    def record_crawler_asset_plan_outcome(self, result: object, added_count: int, written_paths: dict[str, str]) -> None:
        """把 UI 可見結果寫成事件，供 handoff、重開 UI 與後續 agent 讀取。"""

        outcome_payload = crawler_asset_plan_outcome_payload(result, added_count=added_count)
        content_review_payload = (
            outcome_payload.get("content_review") if isinstance(outcome_payload.get("content_review"), dict) else {}
        )
        plan_passport_payload = crawler_asset_plan_passport_payload(result, plan_outcome=outcome_payload)
        log_event(
            "crawler_asset_plan_outcome_recorded",
            "Tk crawler asset workflow recorded the visible send-to-downloader outcome.",
            component="ui.crawler_assets",
            context={
                "asset_id": str(getattr(result, "asset_id", "") or ""),
                "outcome_bucket": str(getattr(result, "outcome_bucket", "") or ""),
                "outcome_label": crawler_asset_plan_outcome_label(result, added_count),
                "added_count": added_count,
                "direct_download_count": int(getattr(result, "direct_download_count", 0) or 0),
                "review_required_count": int(getattr(result, "review_required_count", 0) or 0),
                "review_queue_count": crawler_asset_review_count_from_plan(getattr(result, "resolved_plan", None)),
                "content_review_label": str(outcome_payload.get("content_review_label") or ""),
                "content_review": content_review_payload,
                "plan_passport": plan_passport_payload,
                "resolved_plan": written_paths.get("resolved", ""),
                "user_next_action": str(getattr(result, "user_next_action", "") or getattr(result, "next_action", "") or ""),
            },
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


def crawler_asset_download_plan_summary_text(
    result: object,
    added_count: int,
    resolved_path: str,
    tr: Callable[[str, str], str],
) -> str:
    """把 service outcome bucket 轉成人類可讀文字；Tk 不直接解析 resolved plan。"""

    bucket = str(getattr(result, "outcome_bucket", "") or "")
    direct = int(getattr(result, "direct_download_count", 0) or 0)
    review = int(getattr(result, "review_required_count", 0) or 0)
    blocked = bool(getattr(result, "blocked", False))
    blocked_reason = str(getattr(result, "blocked_reason", "") or "-")
    next_action = str(getattr(result, "user_next_action", "") or getattr(result, "next_action", "") or "-")

    if blocked or bucket == "blocked":
        zh = f"這個爬蟲資產暫時不能建立下載計畫：{blocked_reason}。\n下一步：{next_action}"
        en = f"This crawler asset cannot build a download plan: {blocked_reason}.\nNext: {next_action}"
        return tr(zh, en)
    if bucket == "partial_review_required":
        zh = (
            f"已加入下載器 {added_count} 筆，可先展示或開始下載；另有 {review} 筆需要 Adapter 待辦。\n"
            "下一步：到下載器確認隊列，剩餘項目再進 Adapter review 或調整界域。"
        )
        en = (
            f"Added {added_count} item(s) to Downloader; {review} item(s) still need Adapter review.\n"
            "Next: confirm the queue in Downloader, then review adapters or adjust bounds."
        )
    elif bucket == "ready_to_download":
        zh = (
            f"已建立可下載計畫：直接下載 {direct} 筆，已加入下載器 {added_count} 筆。\n"
            "下一步：到下載器使用開始 / 暫停控制隊列。"
        )
        en = (
            f"Download plan is ready: direct {direct}, added {added_count} item(s) to Downloader.\n"
            "Next: use start / pause in Downloader."
        )
    elif bucket == "review_required":
        zh = (
            f"已建立計畫，但目前沒有可直接下載項目；{review} 筆需要 Adapter 待辦。\n"
            "下一步：開 Adapter review，或回到界域設定調整條件。"
        )
        en = (
            f"Plan built, but no direct downloads are ready; {review} item(s) require Adapter review.\n"
            "Next: open Adapter review or adjust bounds."
        )
    elif bucket == "zero_candidates":
        zh = "沒有找到符合界域的候選資料。\n下一步：放寬時間 / 空間 / 筆數條件，或先重新擷取清單。"
        en = "No candidates matched the selected bounds.\nNext: loosen time / spatial / limit bounds, or refresh the source listing."
    else:
        zh = "已建立下載計畫，但沒有可執行的下載項目。\n下一步：檢查 resolved plan，或調整界域後重試。"
        en = "Plan built, but no executable download item was produced.\nNext: inspect the resolved plan, or adjust bounds and retry."

    content_review_label = str(crawler_asset_plan_outcome_payload(result, added_count=added_count).get("content_review_label") or "").strip()
    if content_review_label:
        zh = f"{zh}\n內容格式待辦：{content_review_label}"
        en = f"{en}\nContent review: {content_review_label}"

    if resolved_path:
        zh = f"{zh}\n\nResolved plan：{resolved_path}"
        en = f"{en}\n\nResolved plan: {resolved_path}"
    return tr(zh, en)


def crawler_asset_plan_outcome_label(result: object, added_count: int) -> str:
    """產生表格用的短狀態；詳細說明仍由 summary text 負責。"""

    # Tk 只取共用 display schema 的短標籤；完整 tone/summary 留給 Web/Qt 或詳情訊息使用。
    payload = crawler_asset_plan_outcome_payload(result, added_count=added_count)
    short_label = str(payload.get("short_label") or "").strip()
    return short_label or str(payload.get("display_label") or "需檢查")


def crawler_asset_plan_passport_summary_text(
    plan_passport: object,
    tr: Callable[[str, str], str],
) -> str:
    """把共用的 compact plan passport 轉成 Tk 側欄短摘要。"""

    if not isinstance(plan_passport, dict) or not plan_passport:
        return ""
    candidates = _plan_passport_count(plan_passport.get("candidate_count"))
    direct = _plan_passport_count(plan_passport.get("direct_download_count"))
    review = _plan_passport_count(plan_passport.get("review_required_count"))
    adapter = _plan_passport_count(plan_passport.get("adapter_review_count"))
    content = _plan_passport_count(plan_passport.get("content_review_count"))
    credentials = _plan_passport_count(plan_passport.get("blocked_credential_count"))
    missing = _plan_passport_count(plan_passport.get("missing_provider_count"))
    has_plan = bool(plan_passport.get("has_resolved_plan"))
    state_zh = "resolved plan 已建立" if has_plan else "resolved plan 尚未建立"
    state_en = "resolved plan available" if has_plan else "resolved plan unavailable"
    zh = (
        f"Plan Passport：{state_zh}；候選 {candidates}；可下載 {direct}；待 Adapter {review}；"
        f"Adapter 佇列 {adapter}；內容待辦 {content}"
    )
    en = (
        f"Plan Passport: {state_en}; candidates {candidates}; direct {direct}; review {review}; "
        f"adapter {adapter}; content {content}"
    )
    if credentials or missing:
        zh = f"{zh}；憑證阻擋 {credentials}；缺 Provider {missing}"
        en = f"{en}; credentials blocked {credentials}; missing providers {missing}"
    return tr(zh, en)


def _plan_passport_count(value: object) -> int:
    """事件紀錄可能來自舊版或外部工具，Tk 顯示層要容忍非數字欄位。"""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def crawler_asset_review_count_from_plan(payload: object) -> int:
    """計算 resolved plan 中仍需要 adapter 接手的項目數，供表格/passport 做短提示。"""

    if not isinstance(payload, dict):
        return 0
    return len(adapter_review_items(payload))


def crawler_asset_state_label(asset: CrawlerAsset) -> str:
    if getattr(asset, "health", None) is not None:
        code = asset.health.status_code
        labels = {
            "archived": "封存",
            "disabled": "停用",
            "missing_handler": "待實作",
            "needs_bounds": "需界域",
            "review_needed": "待審",
            "healthy": "可用",
            "unknown": "未知",
        }
        return f"{asset.health.status_emoji} {labels.get(code, code)}"
    if asset.archived:
        return "📦 封存"
    if not asset.enabled:
        return "⏸ 停用"
    if asset.risk_tier == "needs_handler":
        return "⚙️ 待補"
    if asset.risk_tier == "needs_review":
        return "🟡 待審"
    return "🟢 啟用"
