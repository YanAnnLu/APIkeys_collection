#!/usr/bin/env python3
"""
Tk control panel for APIkeys_collection.

This UI is a lightweight data source manager: it lists provider/database entries,
lets you select sources, runs metadata crawls, writes download plans, runs direct
downloads, and can import supported CSV/JSON/GeoJSON results into the local MVP SQLite store.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
import webbrowser
from tkinter import BooleanVar, Menu, PhotoImage, StringVar, TclError, Tk, messagebox

import APIkeys_collection as core
from api_launcher.downloads.jobs import DownloadProgress, NonBlockingDownloadQueue
from api_launcher.event_log import log_event, log_exception
from api_launcher.downloads.http import HTTPDownloadAdapter
from frontends.tk.startup_helpers import (
    contextlib_suppress_tcl_error,
    tk_startup_failure_message,
)
from frontends.tk.ui_config import (
    COLORS,
    DB_PATH,
    DOWNLOAD_REPAIR_ACTION_STATUSES,
    LAYOUT,
    PRODUCT_DISPLAY_NAME,
    PRODUCT_SHORT_NAME,
    TABLE_COLUMNS,
    configured_ui_language,
)
from frontends.tk.ui_helpers import (
    clamp,
)
from frontends.tk.ui_labels import (
    localized_database_repair_description as localized_database_repair_description_text,
    localized_database_repair_label as localized_database_repair_label_text,
    localized_download_label as localized_download_label_text,
    localized_download_reason as localized_download_reason_text,
    localized_download_repair_label as localized_download_repair_label_text,
)
from frontends.tk.provider_models import ProviderRow
from frontends.tk.ai_summary_workflows import AiSummaryWorkflowMixin
from frontends.tk.detail_panel_workflows import DetailPanelWorkflowMixin
from frontends.tk.discovery_workflows import DiscoveryWorkflowMixin
from frontends.tk.download_plan_panel_workflows import DownloadPlanPanelWorkflowMixin
from frontends.tk.download_workflows import DownloadWorkflowMixin
from frontends.tk.import_workflows import ImportWorkflowMixin
from frontends.tk.mvp_demo_workflows import MvpDemoWorkflowMixin
from frontends.tk.oauth_workflows import OAuthWorkflowMixin
from frontends.tk.plan_workflows import PlanWorkflowMixin
from frontends.tk.provider_settings_workflows import ProviderSettingsWorkflowMixin
from frontends.tk.sidebar_workflows import SidebarWorkflowMixin
from frontends.tk.table_data_workflows import TableDataWorkflowMixin
from frontends.tk.table_interaction_workflows import TableInteractionWorkflowMixin
from frontends.tk.repair_workflows import RepairWorkflowMixin
from frontends.tk.responsive_layout_workflows import ResponsiveLayoutWorkflowMixin
from frontends.tk.window_layout_workflows import WindowLayoutWorkflowMixin
from frontends.tk.yfinance_workflows import YfinanceWorkflowMixin
from api_launcher.downloads.repair import (
    repair_suggestion_for_result,
    verify_manifest_file,
)
from api_launcher.integrations import save_integration_config
from api_launcher.paths import PROJECT_ROOT, catalog_file
from api_launcher.library_actions import LibraryAction, LibraryContext, library_action_map, library_action_menu_label


class ApiCollectionUi(
    AiSummaryWorkflowMixin,
    DiscoveryWorkflowMixin,
    PlanWorkflowMixin,
    ProviderSettingsWorkflowMixin,
    SidebarWorkflowMixin,
    ResponsiveLayoutWorkflowMixin,
    DetailPanelWorkflowMixin,
    WindowLayoutWorkflowMixin,
    DownloadPlanPanelWorkflowMixin,
    TableDataWorkflowMixin,
    TableInteractionWorkflowMixin,
    ImportWorkflowMixin,
    DownloadWorkflowMixin,
    OAuthWorkflowMixin,
    RepairWorkflowMixin,
    MvpDemoWorkflowMixin,
    YfinanceWorkflowMixin,
):
    def __init__(self, root: Tk):
        self.root = root
        self.root.title(PRODUCT_DISPLAY_NAME)
        # 初始尺寸用螢幕比例推導，避免在筆電或外接螢幕上開成過小/過大的視窗。
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        initial_w = clamp(int(screen_w * LAYOUT["initial_width_ratio"]), 1080, 1680)
        initial_h = clamp(int(screen_h * LAYOUT["initial_height_ratio"]), 720, 980)
        min_w = max(980, int(screen_w * LAYOUT["min_width_ratio"]))
        min_h = max(640, int(screen_h * LAYOUT["min_height_ratio"]))
        self.root.geometry(f"{initial_w}x{initial_h}")
        self.root.minsize(min_w, min_h)
        self.root.configure(bg=COLORS["bg"])

        # 這一組是純 UI 狀態，會影響篩選、選取、抽屜與下載計畫的即時呈現。
        self.ui_language = configured_ui_language()
        self.search_var = StringVar()
        self.search_placeholder_text = self.tr("搜尋資料源、分類、API 或關鍵字", "Search sources, categories, APIs, or keywords")
        self.search_placeholder_active = False
        self.category_var = StringVar(value="all")
        self.sidebar_mode_var = StringVar(value="category")
        self.status_var = StringVar(value="準備就緒")
        self.plan_name_var = StringVar(value=self.tr("未命名下載計畫", "Untitled download plan"))
        self.plan_count_var = StringVar(value=self.tr("下載計畫：0 個項目", "Download Plan: 0 items"))
        self.download_plan_toggle_var = StringVar(value=self.tr("收合下載計畫", "Collapse plan"))
        self.preferred_import_existing_table_policy = self.load_import_existing_table_policy_preference()
        self.plan_import_policy_var = StringVar(value=self.import_existing_table_policy_status_label(self.preferred_import_existing_table_policy))
        active_ai = core.active_ai_profile()
        self.selected_ai_profile_id = active_ai.id if active_ai else ""
        self.selected: dict[str, BooleanVar] = {}
        self.rows: list[ProviderRow] = []
        self.filtered_rows: list[ProviderRow] = []
        self.active_provider_id = ""
        self.detail_visible = False
        self.download_plan_visible = True
        self.resize_after_id: str | None = None
        self.detail_animation_after_id: str | None = None
        self.detail_animating_close = False
        self.detail_current_width = 0
        self.column_width_overrides = self.load_column_width_overrides()
        self.resizing_column_name: str | None = None
        # Tk 各平台支援的 cursor 名稱不同，啟動時先探測可用值。
        self.table_resize_cursor = self.supported_cursor(("sb_h_double_arrow", "resizeleft", "resizeright", "fleur"))
        self.tree_default_cursor = ""
        # favicon 目前是 Tk 可顯示的 bitmap cache；未來 canonical icon 可改為 SVG/vector。
        self.default_provider_icon: PhotoImage | None = None
        self.provider_icon_images: dict[str, PhotoImage] = {}
        self.provider_icon_loading: set[str] = set()
        # 下載 queue 在背景 thread 執行，所有 progress 都要透過 callback 切回 Tk 主執行緒。
        self.download_policy = core.active_download_policy()
        self.download_queue = NonBlockingDownloadQueue(
            HTTPDownloadAdapter(policy=self.download_policy),
            max_workers=self.download_policy.max_parallel_jobs,
        )
        self.download_queue.add_callback(self.on_download_progress_threadsafe)
        self.download_jobs_by_provider: dict[str, str] = {}
        self.download_providers_by_job: dict[str, str] = {}
        self.download_progress_by_provider: dict[str, DownloadProgress] = {}
        self.download_status_by_provider: dict[str, tuple[str, str, str]] = {}
        self.download_plan_entries_by_provider: dict[str, dict[str, object]] = {}
        self.import_status_by_plan_key: dict[str, tuple[str, str]] = {}
        self.ui_ready_announced = False
        self.mvp_demo_smoke_running = False
        # plan_key 讓同一 provider 可同時放多個 dataset/version，不再互相覆蓋購物車列。
        self.plan_version_by_provider: dict[str, core.DatasetVersionOption] = {}
        self.plan_provider_by_key: dict[str, str] = {}
        self.registered_completed_downloads: set[str] = set()
        self.datasets_by_provider: dict[str, list[core.Dataset]] = {}
        self.dataset_table_items: dict[str, core.Dataset] = {}
        self.show_dataset_rows_var = BooleanVar(value=True)
        self.current_filter_query = ""
        self.current_filter_category = "all"

        self._init_database()
        self._setup_style()
        self._build_menu_bar()
        self._build_layout()
        self.root.bind("<Configure>", self.on_root_configure)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        # 啟動順序：先建 schema/seed，再載入資料，最後才做環境檢查與視窗置前。
        self.reload_data()
        self.run_startup_environment_checks()
        self.load_saved_ai_api_keys_for_startup()
        self.root.after(120, self.present_main_window)

    def tr(self, zh_tw: str, en_us: str = "") -> str:
        if self.ui_language == "en-US" and en_us:
            return en_us
        return zh_tw

    def supported_cursor(self, candidates: tuple[str, ...]) -> str:
        original = self.root.cget("cursor")
        for cursor in candidates:
            try:
                self.root.configure(cursor=cursor)
                self.root.configure(cursor=original)
                return cursor
            except TclError:
                continue
        try:
            self.root.configure(cursor=original)
        except TclError:
            pass
        return original or "arrow"

    def present_main_window(self) -> None:
        """Make the launcher window visible when started from an IDE/background shell."""
        # 多個 Tk 呼叫可能在視窗關閉邊界拋 TclError；這裡只吞視窗生命週期錯誤。
        with contextlib_suppress_tcl_error():
            self.root.update_idletasks()
        with contextlib_suppress_tcl_error():
            self.root.deiconify()
        with contextlib_suppress_tcl_error():
            self.root.lift()
        with contextlib_suppress_tcl_error():
            self.root.attributes("-topmost", True)
            self.root.after(700, self.release_topmost)
        with contextlib_suppress_tcl_error():
            self.root.focus_force()
        with contextlib_suppress_tcl_error():
            self.root.update_idletasks()
        self.announce_ui_ready()

    def release_topmost(self) -> None:
        with contextlib_suppress_tcl_error():
            self.root.attributes("-topmost", False)

    def announce_ui_ready(self) -> None:
        if self.ui_ready_announced:
            return
        self.ui_ready_announced = True
        print(
            f"{PRODUCT_DISPLAY_NAME} ({PRODUCT_SHORT_NAME}) UI ready "
            f"(pid={os.getpid()}, window={self.root.winfo_width()}x{self.root.winfo_height()}).",
            flush=True,
        )

    def load_column_width_overrides(self) -> dict[str, int]:
        # 欄寬是使用者偏好；讀取時仍用 TABLE_COLUMNS 正規化，避免舊 config 撐破畫面。
        raw_widths = core.load_integration_config().get("ui_table_column_widths")
        if not isinstance(raw_widths, dict):
            return {}
        widths: dict[str, int] = {}
        valid_names = {column[0] for column in TABLE_COLUMNS}
        for name, value in raw_widths.items():
            if name not in valid_names:
                continue
            try:
                widths[str(name)] = self.normalized_column_width(str(name), int(value))
            except (TypeError, ValueError):
                continue
        return widths

    def save_column_width_overrides(self) -> None:
        config = core.ensure_local_integration_config()
        if self.column_width_overrides:
            config["ui_table_column_widths"] = dict(sorted(self.column_width_overrides.items()))
        else:
            config.pop("ui_table_column_widths", None)
        save_integration_config(config)

    def normalized_column_width(self, name: str, width: int) -> int:
        spec = next((column for column in TABLE_COLUMNS if column[0] == name), None)
        if spec is None:
            return width
        _name, _label, _ratio, min_width, max_width, _anchor, _stretch = spec
        manual_max = max(max_width, LAYOUT["column_manual_max"])
        return clamp(width, min_width, manual_max)

    def localized_download_label(self, eligibility: object) -> str:
        return localized_download_label_text(eligibility, self.ui_language)

    def localized_download_reason(self, eligibility: object) -> str:
        return localized_download_reason_text(eligibility, self.ui_language)

    def localized_download_repair_label(self, suggestion: object) -> str:
        return localized_download_repair_label_text(suggestion, self.ui_language)

    def localized_database_repair_label(self, suggestion: object) -> str:
        return localized_database_repair_label_text(suggestion, self.ui_language)

    def localized_database_repair_description(self, suggestion: object) -> str:
        return localized_database_repair_description_text(suggestion, self.ui_language, self.tr)

    def _init_database(self) -> None:
        # UI 啟動時只初始化本機 catalog schema 與內建 seeds，不執行下載或 OAuth。
        conn = core.connect_db(DB_PATH)
        try:
            repository = core.ApiCatalogRepository(conn)
            repository.init_schema()
            repository.seed_builtin_providers()
            repository.seed_key_reference_if_exists(catalog_file(core.KEY_REFERENCE_NAME))
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        return core.connect_db(DB_PATH)

    def close_app(self) -> None:
        self.cancel_detail_animation()
        if self.resize_after_id:
            self.root.after_cancel(self.resize_after_id)
            self.resize_after_id = None
        for job_id in list(self.download_providers_by_job):
            with contextlib_suppress_tcl_error():
                # 視窗關閉時先要求 worker 取消，避免背景下載繼續寫入已關閉 UI 的 callback。
                self.download_queue.cancel(job_id)
        self.download_queue.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

    def run_startup_environment_checks(self) -> None:
        # 環境檢查只回報/記錄問題；不在 UI 啟動時自動修改使用者機器設定。
        checks = core.run_startup_checks(DB_PATH)
        problems = [check for check in checks if check.status in {"warning", "error"}]
        if problems:
            for check in problems:
                log_event(
                    "startup_check_problem",
                    check.detail,
                    level=check.status,
                    component="ui.startup",
                    context={"name": check.name},
                )
            summary = ", ".join(f"{check.name}:{check.status}" for check in problems[:4])
            self.status_var.set(self.tr(f"啟動環境檢查需要注意：{summary}", f"Startup environment checks need attention: {summary}"))
            if any(check.status == "error" for check in problems):
                details = "\n".join(f"[{check.status}] {check.name}: {check.detail}" for check in problems)
                messagebox.showwarning(self.tr("啟動環境檢查", "Startup environment check"), details)





    def on_tree_click(self, event: object) -> None:
        # 第一欄切 star、第二欄切下載計畫；dataset child row 的第二/動作欄則加入計畫。
        region = self.tree.identify("region", getattr(event, "x", 0), getattr(event, "y", 0))
        if region != "cell":
            return
        column = self.tree.identify_column(getattr(event, "x", 0))
        item = self.tree.identify_row(getattr(event, "y", 0))
        if not item:
            return
        dataset = self.dataset_for_table_item(item)
        if dataset is not None:
            if column in {"#2", f"#{len(TABLE_COLUMNS)}"}:
                self.add_dataset_to_plan(dataset)
            return
        if column == "#1":
            self.toggle_star(item)
        elif column == "#2":
            self.toggle_provider(item)
        elif column == f"#{len(TABLE_COLUMNS)}":
            self.run_row_action(item)

    def on_tree_double_click(self, event: object) -> None:
        region = self.tree.identify("region", getattr(event, "x", 0), getattr(event, "y", 0))
        if region != "cell":
            return
        item = self.tree.identify_row(getattr(event, "y", 0))
        if not item:
            return
        dataset = self.dataset_for_table_item(item)
        if dataset is not None:
            self.add_dataset_to_plan(dataset)
            return
        self.add_provider_to_plan(self.provider_id_for_table_item(item))

    def on_tree_context_menu(self, event: object) -> None:
        item = self.tree.identify_row(getattr(event, "y", 0))
        if not item:
            return
        dataset = self.dataset_for_table_item(item)
        self.active_provider_id = self.provider_id_for_table_item(item)
        self.tree.selection_set(item)
        self.tree.focus(item)
        if dataset is not None:
            menu = Menu(self.root, tearoff=0)
            menu.add_command(label=self.tr("加入資料集到下載計畫", "Add dataset to download plan"), command=lambda selected=dataset: self.add_dataset_to_plan(selected))
            source_url = str(dataset.metadata.get("source_url") or dataset.landing_url or dataset.api_url or "")
            if source_url:
                menu.add_command(label=self.tr("開啟資料集來源", "Open dataset source"), command=lambda url=source_url: webbrowser.open(url))
            menu.add_command(label=self.tr("審核資料集候選", "Review dataset candidates"), command=self.open_dataset_candidate_review_panel)
            menu.add_separator()
            menu.add_command(label=self.tr("資料源詳情", "Dataset details"), command=self.open_detail_drawer)
            menu.tk_popup(getattr(event, "x_root", 0), getattr(event, "y_root", 0))
            menu.grab_release()
            return
        row = self.row_by_provider_id(self.active_provider_id)
        actions = self.library_action_map_for_row(row)
        menu = Menu(self.root, tearoff=0)
        self.add_action_menu_item(menu, actions, "add_to_plan", lambda provider_id=self.active_provider_id: self.add_provider_to_plan(provider_id))
        self.add_action_menu_item(menu, actions, "install", self.manage_active_provider)
        self.add_action_menu_item(menu, actions, "update", lambda provider_id=self.active_provider_id: self.add_provider_to_plan(provider_id))
        self.add_action_menu_item(menu, actions, "repair", self.open_repair_panel)
        version_options = self.version_options_for_provider(self.active_provider_id)
        if version_options:
            version_menu = Menu(menu, tearoff=0)
            for option in version_options:
                version_menu.add_command(
                    label=option.menu_label,
                    command=lambda provider_id=self.active_provider_id, selected=option: self.add_provider_version_to_plan(provider_id, selected),
                )
            menu.add_cascade(label=self.tr("版本 / 舊版下載", "Version / legacy download"), menu=version_menu)
        menu.add_separator()
        self.add_action_menu_item(menu, actions, "open_database", self.open_database_tool)
        self.add_action_menu_item(menu, actions, "render_preview", self.open_detail_drawer)
        menu.add_command(label=self.tr("資料源詳情", "Dataset details"), command=self.open_detail_drawer)
        menu.add_command(label=self.tr("Gemini / AI 說明", "Gemini / AI description"), command=self.generate_active_summary)
        menu.add_command(label=self.tr("開啟官方文件", "Open official docs"), command=self.open_active_docs)
        menu.add_separator()
        self.add_action_menu_item(menu, actions, "uninstall", self.uninstall_active_provider)
        menu.tk_popup(getattr(event, "x_root", 0), getattr(event, "y_root", 0))
        menu.grab_release()

    def add_action_menu_item(self, menu: Menu, actions: dict[str, LibraryAction], action_id: str, command: object) -> None:
        action = actions.get(action_id)
        if action is None:
            return
        menu.add_command(
            label=library_action_menu_label(action, include_status_badge=True, badge_language=self.ui_language),
            command=command,
            state="normal" if action.enabled else "disabled",
        )

    def library_context_for_row(self, row: ProviderRow | None) -> LibraryContext | None:
        if row is None:
            return None
        # library_actions 是共用政策層；UI 只負責把當前 row 轉成 context。
        manifest_health, manifest_path, repair_suggestion = self.download_repair_context_for_provider(row.provider_id)
        return LibraryContext(
            provider_id=row.provider_id,
            local_status=row.local_status,
            remote_status=row.remote_status,
            update_status=row.update_status,
            install_id=row.install_id,
            manifest_health=manifest_health,
            manifest_path=manifest_path,
            repair_suggestion=repair_suggestion,
            has_direct_download=row.download_eligibility.status == "direct_download",
            has_adapter=row.download_eligibility.status == "adapter_required",
            has_render_assets=bool(row.install_id),
        )

    def download_repair_context_for_provider(self, provider_id: str) -> tuple[str, str, dict[str, object]]:
        if not provider_id:
            return "unknown", "", {}
        conn = self._connect()
        try:
            records = core.ApiCatalogRepository(conn).list_dataset_asset_manifests(provider_id)
        finally:
            conn.close()
        for record in records:
            # 只挑需要人類/agent 處理的 manifest 狀態，健康檔案不佔用 action menu。
            if record.status not in DOWNLOAD_REPAIR_ACTION_STATUSES:
                continue
            result = verify_manifest_file(record.manifest_path)
            if result.status not in DOWNLOAD_REPAIR_ACTION_STATUSES:
                continue
            suggestion = repair_suggestion_for_result(result)
            return result.status, str(result.manifest_path), suggestion.as_dict()
        return "unknown", "", {}

    def library_action_map_for_row(self, row: ProviderRow | None) -> dict[str, LibraryAction]:
        context = self.library_context_for_row(row)
        if context is None:
            return {}
        return library_action_map(context)

    def on_tree_select(self, _event: object) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        selected_item = str(selection[0])
        dataset = self.dataset_for_table_item(selected_item)
        self.active_provider_id = self.provider_id_for_table_item(selected_item)
        if not self.detail_visible:
            self.open_detail_drawer()
        else:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        row = self.row_by_provider_id(self.active_provider_id)
        if dataset is not None:
            self.status_var.set(self.tr(f"已選取資料集：{dataset.title}", f"Selected dataset: {dataset.title}"))
        elif row:
            self.status_var.set(self.tr(f"已選取：{row.name}", f"Selected: {row.name}"))

    def toggle_star(self, provider_id: str) -> None:
        conn = self._connect()
        try:
            is_starred = core.ApiCatalogRepository(conn).toggle_provider_starred(provider_id)
        finally:
            conn.close()
        row = self.row_by_provider_id(provider_id)
        label = row.name if row else provider_id
        self.reload_data()
        self.status_var.set(f"{'已置頂' if is_starred else '已取消置頂'}：{label}")

    def toggle_active_star(self) -> None:
        if self.active_provider_id:
            self.toggle_star(self.active_provider_id)

    def row_by_provider_id(self, provider_id: str) -> ProviderRow | None:
        return next((row for row in self.rows if row.provider_id == provider_id), None)

    def run_row_action(self, provider_id: str) -> None:
        row = self.row_by_provider_id(provider_id)
        if row is None or not row.action_label:
            return
        if row.update_status == "remote_updated":
            self.status_var.set(f"正在刷新 {row.name} 的 metadata...")
        elif row.remote_status == "error":
            self.status_var.set(f"正在重試 {row.name} 的 metadata...")
        else:
            self.status_var.set(f"正在檢查 {row.name} 的 metadata...")
        self.crawl_provider_ids([provider_id])

    def check_active_metadata(self) -> None:
        if not self.active_provider_id:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        row = self.row_by_provider_id(self.active_provider_id)
        self.status_var.set(f"正在檢查 {row.name if row else self.active_provider_id} 的 metadata...")
        self.crawl_provider_ids([self.active_provider_id])

    def verify_active_assets(self) -> None:
        if not self.active_provider_id:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        row = self.row_by_provider_id(self.active_provider_id)
        summary, issues = self.sync_database_asset_verification([self.active_provider_id])
        self.reload_data()
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.status_var.set(
            f"已驗證本地資產：{row.name if row else self.active_provider_id} "
            f"(present={summary['present']}, missing={summary['missing']}, error={summary['error']})"
        )
        if issues:
            suggestion = issues[0].repair_suggestion()
            messagebox.showwarning(
                "Database self-check",
                (
                    f"找到 {len(issues)} 個資料庫/資料表問題。\n\n"
                    f"第一個建議：{self.localized_database_repair_label(suggestion)}\n"
                    f"{self.localized_database_repair_description(suggestion)}\n\n"
                    "可以到「工具 > 修復 / 驗證資產」查看完整清單。"
                ),
            )

    def select_active_provider(self) -> None:
        if not self.active_provider_id:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        self.add_provider_to_plan(self.active_provider_id)

    def manage_active_provider(self) -> None:
        if not self.active_provider_id:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        row = self.row_by_provider_id(self.active_provider_id)
        conn = self._connect()
        try:
            install_id = core.ApiCatalogRepository(conn).manage_provider_installation(
                self.active_provider_id,
                location=row.dataset_path if row else "",
                notes="Manually marked as managed from launcher UI.",
            )
        finally:
            conn.close()
        self.reload_data()
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.status_var.set(f"已納管：{row.name if row else self.active_provider_id} ({install_id})")

    def unmanage_active_provider(self) -> None:
        if not self.active_provider_id:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        row = self.row_by_provider_id(self.active_provider_id)
        if row is None or not row.install_id:
            messagebox.showinfo("尚未納管", "這個資料源目前沒有 launcher install_id。")
            return
        if not messagebox.askyesno(
            "解除納管",
            (
                f"要解除納管 {row.name} 嗎？\n\n"
                "這只會移除 launcher 的追蹤狀態，不會刪除你的本地檔案、資料表或資料庫。"
            ),
        ):
            return
        conn = self._connect()
        try:
            install_id = core.ApiCatalogRepository(conn).unmanage_provider_installation(self.active_provider_id)
        finally:
            conn.close()
        self.reload_data()
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.status_var.set(f"已解除納管：{row.name} ({install_id})")

    def uninstall_active_provider(self) -> None:
        if not self.active_provider_id:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        row = self.row_by_provider_id(self.active_provider_id)
        if row is None or not row.install_id:
            messagebox.showinfo("尚未納管", "這個資料源目前沒有 launcher install_id。")
            return
        if not messagebox.askyesno(
            "移除本地資料",
            (
                f"要移除 {row.name} 的本地納管狀態嗎？\n\n"
                "目前版本只會把 launcher registry 中的安裝資產標記為 removed，"
                "不會執行 DROP DATABASE 或刪除檔案。等資料庫 adapter 完成後，"
                "這裡才會只針對已登記的 install_id 安全執行卸載命令。"
            ),
        ):
            return
        conn = self._connect()
        try:
            result = core.ApiCatalogRepository(conn).uninstall_provider_installation(self.active_provider_id)
        finally:
            conn.close()
        self.reload_data()
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        asset_count = len(result.get("assets") or [])
        self.status_var.set(f"已標記移除：{row.name} ({asset_count} 個登記資產)")

    def self_check_selected(self) -> None:
        provider_ids = self.selected_provider_ids()
        conn = self._connect()
        try:
            count = core.ApiCatalogRepository(conn).refresh_provider_download_state(provider_ids or None)
        finally:
            conn.close()
        self.reload_data()
        scope = "下載計畫" if provider_ids else "全部資料源"
        self.status_var.set(f"已完成 {scope} 自檢，更新 {count} 筆狀態。")

    def crawl_selected(self) -> None:
        provider_ids = self.selected_provider_ids()
        if not provider_ids:
            messagebox.showinfo("下載計畫是空的", "請先把至少一個資料源加入下載計畫。")
            return
        self.status_var.set(f"正在爬取下載計畫中 {len(provider_ids)} 個資料源的 metadata...")
        self.crawl_provider_ids(provider_ids)

    def crawl_provider_ids(self, provider_ids: list[str]) -> None:
        thread = threading.Thread(target=self._crawl_worker, args=(provider_ids,), daemon=True)
        thread.start()

    def _crawl_worker(self, provider_ids: list[str]) -> None:
        try:
            conn = self._connect()
            try:
                repository = core.ApiCatalogRepository(conn)
                providers = repository.load_providers(provider_ids)
                core.crawl_providers_nonblocking(
                    conn,
                    providers,
                    max_bytes=65_536,
                    timeout=8.0,
                    delay=0.0,
                    concurrency=8,
                    per_host=2,
                )
            finally:
                conn.close()
        except Exception as exc:
            log_exception(
                "metadata_crawl_failed",
                exc,
                component="ui.crawl",
                context={"provider_ids": provider_ids},
            )
            self.root.after(0, lambda: messagebox.showerror("爬取失敗", str(exc)))
            self.root.after(0, lambda: self.status_var.set(f"爬取失敗：{exc}"))
            return
        self.root.after(0, self.reload_data)
        self.root.after(0, lambda: self.status_var.set("metadata 爬取完成。"))

    def open_selected_docs(self) -> None:
        rows = self.selected_rows()
        if not rows:
            selection = self.tree.selection()
            rows = [row for row in self.rows if row.provider_id in selection]
        if not rows:
            messagebox.showinfo("尚未選取", "請先加入下載計畫或點選一個資料源。")
            return
        for row in rows[:5]:
            webbrowser.open(row.docs_url or row.signup_url or row.api_base_url)
        self.status_var.set(f"已開啟 {min(len(rows), 5)} 個官方文件頁。")

    def open_active_docs(self) -> None:
        row = self.row_by_provider_id(self.active_provider_id)
        if row is None:
            self.open_selected_docs()
            return
        webbrowser.open(row.docs_url or row.signup_url or row.api_base_url)
        self.status_var.set(f"已開啟官方文件頁：{row.name}")


def main() -> int:
    try:
        root = Tk()
    except TclError as exc:
        # 這是 UI runtime/preflight 的最早防線；此時沒有 root，所以只能寫 stderr 與 event log。
        log_exception("ui_tk_startup_failed", exc, component="ui.startup")
        print(tk_startup_failure_message(exc), file=sys.stderr)
        return 2
    ApiCollectionUi(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
