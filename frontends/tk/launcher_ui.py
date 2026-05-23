#!/usr/bin/env python3
"""
Tk control panel for APIkeys_collection.

This UI is a lightweight data source manager: it lists provider/database entries,
lets you select sources, runs metadata crawls, writes download plans, runs direct
downloads, and can import supported CSV/JSON/GeoJSON results into the local MVP SQLite store.
"""

from __future__ import annotations

import json
import html
import os
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, Y, BooleanVar, Canvas, Menu, PhotoImage, StringVar, TclError, Text, Tk, Toplevel, messagebox, simpledialog
from tkinter import filedialog, ttk

import APIkeys_collection as core
from api_launcher.favicons import download_favicon_png, favicon_cache_path, favicon_url_for_page, provider_home_url
from api_launcher.downloads.jobs import DownloadProgress, JobStatus, NonBlockingDownloadQueue
from api_launcher.event_log import log_event, log_exception
from api_launcher.downloads.http import HTTPDownloadAdapter, download_target_from_plan_entry
from api_launcher.downloads.plan_runner import (
    download_entry_skip_bucket,
)
from api_launcher.importers.csv_importer import import_csv_manifest_to_sqlite, table_exists, table_name_for_manifest, unique_table_name
from api_launcher.importers.json_importer import import_json_manifest_to_sqlite
from api_launcher.ingestion_pipeline import DownloadImportPipelineOptions, run_existing_download_import_slice
from api_launcher.manifests import read_manifest
from api_launcher.manual_import import (
    DEFAULT_MANUAL_LOCAL_PROVIDER_ID,
    ensure_manual_local_file_provider,
    register_local_file_manifest_asset,
    write_local_file_manifest as write_local_file_manifest_file,
)
from frontends.tk.desktop_integration import reveal_path_in_file_manager
from frontends.tk.startup_helpers import (
    contextlib_suppress_tcl_error,
    tk_startup_failure_message,
)
from frontends.tk.ui_config import (
    COLORS,
    CURATED_IMPORTS_NAME,
    DB_PATH,
    DOWNLOAD_PLAN_NAME,
    DOWNLOAD_REPAIR_ACTION_STATUSES,
    LAYOUT,
    MANUAL_IMPORTS_DIR_NAME,
    PRODUCT_DISPLAY_NAME,
    PRODUCT_SHORT_NAME,
    RESOLVED_DOWNLOAD_PLAN_NAME,
    TABLE_COLUMNS,
    configured_ui_language,
)
from frontends.tk.ui_helpers import (
    clamp,
    database_sql_dry_run_available,
    local_file_import_error_message,
    local_file_provenance_review_message,
)
from frontends.tk.ui_labels import (
    crawler_next_action_label as crawler_next_action_label_text,
    data_store_next_action_message as data_store_next_action_message_text,
    localized_database_repair_description as localized_database_repair_description_text,
    localized_database_repair_label as localized_database_repair_label_text,
    localized_download_label as localized_download_label_text,
    localized_download_reason as localized_download_reason_text,
    localized_download_repair_label as localized_download_repair_label_text,
)
from frontends.tk.provider_models import ProviderRow
from frontends.tk.mvp_demo_workflows import MvpDemoWorkflowMixin
from frontends.tk.oauth_workflows import OAuthWorkflowMixin
from frontends.tk.repair_workflows import RepairWorkflowMixin
from frontends.tk.yfinance_workflows import YfinanceWorkflowMixin
from api_launcher.downloads.repair import (
    ManifestVerification,
    RepairSuggestion,
    download_repair_agent_payload,
    log_download_manifest_verification_completed as log_download_manifest_verification_event,
    log_download_requeue_requested as log_download_requeue_event,
    repair_summary,
    repair_suggestion_for_result,
    scan_download_manifests,
    verify_manifest_file,
)
from api_launcher.database_repair import (
    database_repair_sql_path_for_asset,
    reimport_missing_sqlite_table_asset,
    supported_reimport_source_formats_label,
    write_missing_sql_table_repair_dry_run,
)
from api_launcher.database_self_check import DatabaseAssetVerifier, DatabaseSelfCheckIssue, database_self_check_issues
from api_launcher.db import utc_now_iso
from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME
from api_launcher.discovery import DEFAULT_SEEDS_NAME, LOCAL_SEEDS_NAME, discover_provider_candidates, load_all_discovery_seeds
from api_launcher.discovery_promotion import promote_local_discovery_catalog
from frontends.tk.dialogs import (
    AdapterReviewDialog,
    AiModelSettingsDialog,
    DataStoreConnectionSettingsDialog,
    DatabaseClientSettingsDialog,
    DatasetCandidateReviewDialog,
    DeveloperCliDialog,
    GoogleGeminiSettingsDialog,
    ImportExistingTablePolicyDialog,
    ProviderCandidateReviewDialog,
    ProviderEditorDialog,
    RecentEventLogsDialog,
    StartupEnvironmentChecksDialog,
    UiLanguageSettingsDialog,
)
from api_launcher.integrations import save_integration_config
from api_launcher.paths import DOWNLOADS_DIR, PROJECT_ROOT, catalog_file, local_config_file, state_file
from api_launcher.library_actions import LibraryAction, LibraryContext, library_action_map, library_action_menu_label
from api_launcher.registry import PROVIDER_CATALOG_NAME
from api_launcher.oauth_device import activate_saved_oauth_token, build_oauth_device_login_request, exchange_oauth_authorization_code, looks_like_google_oauth_client_id, oauth_authorization_url, oauth_device_config_from_profile, oauth_token_status, pkce_code_challenge, poll_oauth_device_token, save_oauth_config_token, save_oauth_device_token
from api_launcher.ai_api_keys import default_api_key_env, load_saved_ai_api_keys, save_ai_api_key, saved_ai_api_key_status
from api_launcher.data_store_connections import data_store_profiles_from_config
from api_launcher.adapter_review import adapter_review_items
from api_launcher.import_policies import UI_IMPORT_POLICY_CONFIG_KEY, normalized_ui_import_policy


class ApiCollectionUi(OAuthWorkflowMixin, RepairWorkflowMixin, MvpDemoWorkflowMixin, YfinanceWorkflowMixin):
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

    def load_import_existing_table_policy_preference(self) -> str:
        return normalized_ui_import_policy(core.load_integration_config().get(UI_IMPORT_POLICY_CONFIG_KEY))

    def save_import_existing_table_policy_preference(self, policy: str) -> None:
        # 匯入同名表策略會影響資料安全，因此保存前一律走 normalized_ui_import_policy。
        normalized = normalized_ui_import_policy(policy)
        self.preferred_import_existing_table_policy = normalized
        if hasattr(self, "plan_import_policy_var"):
            self.plan_import_policy_var.set(self.import_existing_table_policy_status_label(normalized))
        config = core.ensure_local_integration_config()
        config[UI_IMPORT_POLICY_CONFIG_KEY] = normalized
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

    def load_saved_ai_api_keys_for_startup(self) -> None:
        """Startup may read local private API-key state, but must not trigger OAuth/login UI."""
        loaded_api_keys = load_saved_ai_api_keys(core.ai_summary_profiles())
        if loaded_api_keys:
            self.status_var.set(self.tr(f"已載入本機 AI API key：{', '.join(loaded_api_keys[:3])}", f"Loaded local AI API keys: {', '.join(loaded_api_keys[:3])}"))

    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        with contextlib_suppress_tcl_error():
            style.theme_use("clam")
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Sidebar.TFrame", background=COLORS["sidebar"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Header.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Helvetica", 26, "bold"))
        style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Helvetica", 12))
        style.configure("DetailTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Helvetica", 24, "bold"))
        style.configure("DetailSection.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Helvetica", 11, "bold"))
        style.configure("DetailText.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Helvetica", 12), wraplength=540)
        style.configure("DetailMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Helvetica", 11), wraplength=540)
        style.configure("SidebarTitle.TLabel", background=COLORS["sidebar"], foreground=COLORS["accent"], font=("Helvetica", 18, "bold"))
        style.configure("Sidebar.TButton", background=COLORS["sidebar"], foreground=COLORS["text"], anchor="w", padding=(18, 12))
        style.map("Sidebar.TButton", background=[("active", COLORS["header"])])
        style.configure("Action.TButton", background=COLORS["header"], foreground=COLORS["text"], padding=(16, 10), font=("Helvetica", 12, "bold"))
        style.map("Action.TButton", background=[("active", COLORS["accent_dark"])])
        style.configure("Search.TEntry", foreground=COLORS["text"], fieldbackground="#f7f7f7", font=("Helvetica", 14))
        style.configure("SearchPlaceholder.TEntry", foreground="#6f7b8c", fieldbackground="#f7f7f7", font=("Helvetica", 14))
        rowheight = clamp(int(self.root.winfo_height() * LAYOUT["rowheight_ratio"]), 42, 62)
        style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["text"], rowheight=rowheight, font=("Helvetica", 12))
        style.configure("Treeview.Heading", background=COLORS["header"], foreground=COLORS["text"], font=("Helvetica", 12, "bold"), padding=(10, 12))
        style.map("Treeview", background=[("selected", COLORS["accent_dark"])])

    def _build_menu_bar(self) -> None:
        # 頂層 menu 反映產品區塊：檔案、資料庫、整合、工具、設定、說明。
        menu_bar = Menu(self.root)

        file_menu = Menu(menu_bar, tearoff=0)
        file_menu.add_command(label=self.tr("重新整理資料庫", "Refresh library"), command=self.reload_data)
        file_menu.add_command(label=self.tr("匯出下載計畫", "Export download plan"), command=self.export_download_plan)
        file_menu.add_separator()
        file_menu.add_command(label=self.tr("離開", "Exit"), command=self.close_app)
        menu_bar.add_cascade(label=self.tr("檔案", "File"), menu=file_menu)

        library_menu = Menu(menu_bar, tearoff=0)
        library_menu.add_command(label=self.tr("加入選取資料源到下載計畫", "Add selected to download plan"), command=self.select_active_provider)
        library_menu.add_command(label=self.tr("抓取選取資料源 metadata", "Fetch selected metadata"), command=self.crawl_selected)
        library_menu.add_command(label=self.tr("發現 provider 候選", "Discover provider candidates"), command=self.discover_provider_candidates_from_ui)
        library_menu.add_command(label=self.tr("審核 provider 候選", "Review provider candidates"), command=self.open_provider_candidate_review_panel)
        library_menu.add_command(label=self.tr("發現資料集候選", "Discover dataset candidates"), command=self.discover_dataset_candidates_from_ui)
        library_menu.add_command(label=self.tr("審核本機 discovery 草稿", "Audit local discovery drafts"), command=self.audit_local_discovery_from_ui)
        library_menu.add_command(label=self.tr("審核資料集候選", "Review dataset candidates"), command=self.open_dataset_candidate_review_panel)
        library_menu.add_checkbutton(
            label=self.tr("在列表顯示 crawler 資料集", "Show crawler datasets in list"),
            variable=self.show_dataset_rows_var,
            command=self.apply_filter,
        )
        library_menu.add_command(label=self.tr("驗證已下載檔案", "Verify downloaded files"), command=self.verify_download_manifests)
        library_menu.add_command(label=self.tr("匯入可支援下載結果", "Import supported downloaded results"), command=self.import_supported_plan_results_from_ui)
        library_menu.add_command(label=self.tr("匯入本機 CSV/JSON 檔", "Import local CSV/JSON file"), command=self.import_local_file_from_ui)
        library_menu.add_command(label=self.tr("Adapter 待辦", "Adapter review queue"), command=self.open_adapter_review_panel)
        library_menu.add_command(label=self.tr("解析 Adapter 計畫", "Resolve adapter plan"), command=self.resolve_adapter_plan_from_ui)
        library_menu.add_separator()
        library_menu.add_command(label=self.tr("納管目前資料源", "Manage active source"), command=self.manage_active_provider)
        library_menu.add_command(label=self.tr("解除納管目前資料源", "Unmanage active source"), command=self.unmanage_active_provider)
        library_menu.add_command(label=self.tr("移除目前本地資料", "Uninstall active source"), command=self.uninstall_active_provider)
        menu_bar.add_cascade(label=self.tr("資料庫", "Library"), menu=library_menu)

        integrations_menu = Menu(menu_bar, tearoff=0)
        integrations_menu.add_command(label=self.tr("AI / Gemini 串接中心", "AI / Gemini integration hub"), command=self.open_google_gemini_settings)
        integrations_menu.add_command(label=self.tr("保存 Gemini API key", "Save Gemini API key"), command=lambda: self.configure_ai_api_key_session("gemini_flash"))
        integrations_menu.add_command(label=self.tr("AI 輔助模型選擇", "AI assistant model selection"), command=self.open_ai_model_settings)
        google_oauth_menu = Menu(integrations_menu, tearoff=0)
        google_oauth_menu.add_command(label=self.tr("Google 帳號登入（中期正式入口）", "Google account sign-in (mid-term official entry)"), command=self.open_google_browser_login_dialog)
        google_oauth_menu.add_command(label=self.tr("Google QR / 裝置碼（中期正式入口）", "Google QR / device code (mid-term official entry)"), command=self.open_google_qr_login_dialog)
        google_oauth_menu.add_command(label=self.tr("開發者 OAuth 設定", "Developer OAuth setup"), command=self.open_google_oauth_developer_setup)
        integrations_menu.add_cascade(label=self.tr("Google OAuth（中期 / 開發者）", "Google OAuth (mid-term / developer)"), menu=google_oauth_menu)
        integrations_menu.add_separator()
        integrations_menu.add_command(label=self.tr("資料儲存連線", "Data store connections"), command=self.open_data_store_connection_settings)
        integrations_menu.add_command(label=self.tr("資料庫工具設定", "Database tool settings"), command=self.open_database_settings)
        integrations_menu.add_command(label=self.tr("開啟資料庫工具", "Open database tool"), command=self.open_database_tool)
        integrations_menu.add_separator()
        integrations_menu.add_command(label=self.tr("顯示本機整合設定檔", "Reveal integration config"), command=self.open_integration_config_file)
        menu_bar.add_cascade(label=self.tr("整合", "Integrations"), menu=integrations_menu)

        tools_menu = Menu(menu_bar, tearoff=0)
        tools_menu.add_command(label=self.tr("啟動環境檢查", "Startup environment checks"), command=self.show_environment_checks)
        tools_menu.add_command(label=self.tr("最近事件紀錄", "Recent event logs"), command=self.show_event_logs)
        tools_menu.add_command(label=self.tr("修復 / 驗證資產", "Repair / verify assets"), command=self.open_repair_panel)
        tools_menu.add_command(label=self.tr("產生 MVP Demo Flow", "Create MVP demo flow"), command=self.write_mvp_demo_flow_from_ui)
        tools_menu.add_command(label=self.tr("一鍵驗證 MVP Demo Flow", "Run MVP demo smoke"), command=self.run_mvp_demo_smoke_from_ui)
        tools_menu.add_command(label=self.tr("產生 yfinance 離線 Demo plan", "Create yfinance offline demo plan"), command=self.write_yfinance_demo_plan_from_ui)
        tools_menu.add_command(label=self.tr("建立 yfinance live plan（需確認）", "Create yfinance live plan (requires acknowledgement)"), command=self.open_yfinance_live_plan_dialog)
        tools_menu.add_command(label=self.tr("產生 yfinance 儲存審查 dry-run", "Create yfinance storage review dry-run"), command=self.open_yfinance_storage_review_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label=self.tr("開發者 CLI", "Developer CLI"), command=self.open_developer_cli)
        tools_menu.add_separator()
        tools_menu.add_command(label=self.tr("開啟下載資料夾", "Open downloads folder"), command=lambda: webbrowser.open(DOWNLOADS_DIR.as_uri()))
        menu_bar.add_cascade(label=self.tr("工具", "Tools"), menu=tools_menu)

        settings_menu = Menu(menu_bar, tearoff=0)
        settings_menu.add_command(label=self.tr("介面語言", "Interface language"), command=self.open_ui_language_settings)
        menu_bar.add_cascade(label=self.tr("設定", "Settings"), menu=settings_menu)

        help_menu = Menu(menu_bar, tearoff=0)
        help_menu.add_command(label=self.tr("文件索引", "Docs index"), command=lambda: self.open_doc_file("DOCS_INDEX.zh-TW.md"))
        help_menu.add_command(label=self.tr("產品定位", "Product positioning"), command=lambda: self.open_doc_file("PRODUCT_POSITIONING.zh-TW.md"))
        help_menu.add_command(label=self.tr("技術總覽", "Technical overview"), command=lambda: self.open_doc_file("TECHNICAL_OVERVIEW.zh-TW.md"))
        menu_bar.add_cascade(label=self.tr("說明", "Help"), menu=help_menu)

        self.root.configure(menu=menu_bar)

    def _build_layout(self) -> None:
        # 主 layout 固定為 sidebar + main + detail/download panels，方便之後 Qt 前端照同一資訊架構重建。
        sidebar_width = clamp(int(self.root.winfo_width() * LAYOUT["sidebar_ratio"]), LAYOUT["sidebar_min"], LAYOUT["sidebar_max"])
        outer_pad = self.scaled_pad()

        sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=sidebar_width)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text=self.tr("科學資料\n收藏庫", "API DATA\nCOLLECTION"), style="SidebarTitle.TLabel", justify=LEFT).pack(anchor="w", padx=28, pady=(34, 32))
        mode_switch = ttk.Frame(sidebar, style="Sidebar.TFrame")
        mode_switch.pack(fill=X, padx=18, pady=(0, 12))
        ttk.Radiobutton(
            mode_switch,
            text=self.tr("依類型", "By type"),
            variable=self.sidebar_mode_var,
            value="category",
            command=self.refresh_sidebar_filters,
        ).pack(side=LEFT)
        ttk.Radiobutton(
            mode_switch,
            text=self.tr("依提供商", "By provider"),
            variable=self.sidebar_mode_var,
            value="provider",
            command=self.refresh_sidebar_filters,
        ).pack(side=LEFT, padx=(10, 0))
        self.sidebar_filter_frame = ttk.Frame(sidebar, style="Sidebar.TFrame")
        self.sidebar_filter_frame.pack(fill=BOTH, expand=True)
        self.refresh_sidebar_filters()

        main = ttk.Frame(self.root, style="App.TFrame")
        main.pack(side=RIGHT, fill=BOTH, expand=True)

        header = ttk.Frame(main, style="App.TFrame")
        header.pack(fill=X, padx=outer_pad, pady=(outer_pad, max(12, outer_pad // 2)))
        ttk.Label(header, text=self.tr("資料庫來源", "Database Sources"), style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text=self.tr(
                "像 Steam 一樣管理科學資料集：瀏覽、規劃、安裝、更新，並把資料接到 Taichi / Unreal / Agent。",
                "Steam-like scientific dataset launcher: browse, plan, install, update, and bridge data to Taichi/Unreal/Agent.",
            ),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(8, 0))

        controls = ttk.Frame(main, style="App.TFrame")
        controls.pack(fill=X, padx=outer_pad, pady=(0, max(12, outer_pad // 2)))
        ttk.Button(controls, text=self.tr("重新整理", "Refresh"), style="Action.TButton", command=self.reload_data).pack(side=LEFT, padx=(0, 10))
        ttk.Button(controls, text=self.tr("自檢", "Self-check"), style="Action.TButton", command=self.self_check_selected).pack(side=LEFT, padx=(0, 10))
        ttk.Button(controls, text=self.tr("修復 / 驗證", "Repair / verify"), style="Action.TButton", command=self.open_repair_panel).pack(side=LEFT, padx=(0, 10))
        ttk.Button(controls, text=self.tr("新增來源", "Add source"), style="Action.TButton", command=self.add_provider).pack(side=LEFT, padx=(0, 10))
        more_button = ttk.Menubutton(controls, text=self.tr("更多", "More"), style="Action.TButton")
        more_menu = Menu(more_button, tearoff=0)
        more_menu.add_command(label=self.tr("抓取選取 metadata", "Fetch selected metadata"), command=self.crawl_selected)
        more_menu.add_command(label=self.tr("發現資料集候選", "Discover dataset candidates"), command=self.discover_dataset_candidates_from_ui)
        more_menu.add_command(label=self.tr("審核資料集候選", "Review dataset candidates"), command=self.open_dataset_candidate_review_panel)
        more_menu.add_command(label=self.tr("匯出下載計畫", "Export download plan"), command=self.export_download_plan)
        more_menu.add_command(label=self.tr("匯入可支援下載結果", "Import supported downloaded results"), command=self.import_supported_plan_results_from_ui)
        more_menu.add_command(label=self.tr("匯入本機 CSV/JSON 檔", "Import local CSV/JSON file"), command=self.import_local_file_from_ui)
        more_menu.add_command(label=self.tr("Adapter 待辦", "Adapter review queue"), command=self.open_adapter_review_panel)
        more_menu.add_command(label=self.tr("解析 Adapter 計畫", "Resolve adapter plan"), command=self.resolve_adapter_plan_from_ui)
        more_menu.add_command(label=self.tr("產生 MVP Demo Flow", "Create MVP demo flow"), command=self.write_mvp_demo_flow_from_ui)
        more_menu.add_command(label=self.tr("一鍵驗證 MVP Demo Flow", "Run MVP demo smoke"), command=self.run_mvp_demo_smoke_from_ui)
        more_menu.add_command(label=self.tr("開啟官方文件", "Open official docs"), command=self.open_selected_docs)
        more_menu.add_separator()
        more_menu.add_command(label=self.tr("資料源詳情", "Dataset details"), command=self.open_detail_drawer)
        more_menu.add_command(label=self.tr("重設表格欄寬", "Reset table columns"), command=self.reset_table_column_widths)
        more_menu.add_command(label=self.tr("編輯資料源", "Edit source"), command=self.edit_active_provider)
        more_button.configure(menu=more_menu)
        more_button.pack(side=LEFT, padx=(0, 10))
        self.search_entry = ttk.Entry(controls, textvariable=self.search_var, style="Search.TEntry")
        self.search_entry.pack(side=RIGHT, fill=X, expand=True)
        self.search_entry.bind("<FocusIn>", self.on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self.on_search_focus_out)
        self.search_var.trace_add("write", lambda *_: self.apply_filter())
        self.set_search_placeholder()

        self.content_frame = ttk.Frame(main, style="App.TFrame")
        self.content_frame.pack(fill=BOTH, expand=True, padx=outer_pad, pady=(0, max(14, outer_pad // 2)))

        self.table_frame = ttk.Frame(self.content_frame, style="Panel.TFrame")
        self.table_frame.pack(side=LEFT, fill=BOTH, expand=True)
        columns = tuple(column[0] for column in TABLE_COLUMNS)
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings", selectmode="extended")
        for name, label, _ratio, min_width, _max_width, anchor, stretch in TABLE_COLUMNS:
            self.tree.heading(name, text=label)
            self.tree.column(name, width=min_width, anchor=anchor, stretch=stretch)
        self.tree_default_cursor = str(self.tree.cget("cursor") or "")
        self.tree.tag_configure("has_action", foreground=COLORS["text"])
        self.tree.tag_configure("remote_updated", foreground=COLORS["accent"])
        self.tree.tag_configure("starred", foreground=COLORS["accent"])
        self.tree.tag_configure("dataset_row", foreground=COLORS["muted"])
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=x_scrollbar.set)
        x_scrollbar.pack(side="bottom", fill=X)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.bind("<ButtonPress-1>", self.on_tree_button_press, add="+")
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_button_release, add="+")
        self.tree.bind("<Motion>", self.on_tree_motion, add="+")
        self.tree.bind("<Leave>", self.on_tree_leave, add="+")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.on_tree_context_menu)
        self.tree.bind("<Control-Button-1>", self.on_tree_context_menu)

        self._build_detail_panel(self.content_frame)

        self._build_download_plan_panel(main, outer_pad)

        bottom = ttk.Frame(main, style="App.TFrame")
        bottom.pack(fill=X, padx=outer_pad, pady=(0, max(14, outer_pad // 2)))
        ttk.Label(bottom, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w")

    def _build_detail_panel(self, parent: ttk.Frame) -> None:
        # Detail panel 是「商店頁」概念：顯示來源狀態、官方入口、AI 說明與可執行 action。
        self.detail_parent = parent
        self.detail = ttk.Frame(parent, style="Panel.TFrame", width=self.detail_width())
        self.detail.pack_propagate(False)
        self.detail_wrap_labels: list[ttk.Label] = []
        self.detail_star_var = StringVar(value="☆")
        self.detail_title_var = StringVar(value="選取一個資料源")
        self.detail_owner_var = StringVar(value="像 Steam 商店頁一樣查看用途、狀態與官方入口。")
        self.detail_category_var = StringVar(value="")
        self.detail_auth_var = StringVar(value="")
        self.detail_status_var = StringVar(value="")
        self.detail_scope_var = StringVar(value="")
        self.detail_urls_var = StringVar(value="")
        self.ai_summary_placeholder = self.tr("按「AI 產生說明」後，目前選取的 AI profile 產生的描述會顯示在這裡。", "Descriptions generated by the selected AI profile will appear here after you click AI description.")

        header = ttk.Frame(self.detail, style="Panel.TFrame")
        header.pack(fill=X, padx=18, pady=(18, 10))
        ttk.Button(header, text="×", width=3, command=self.close_detail_drawer).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(header, textvariable=self.detail_star_var, width=3, command=self.toggle_active_star).pack(side=LEFT, padx=(0, 10))
        title_label = ttk.Label(header, textvariable=self.detail_title_var, style="DetailTitle.TLabel", wraplength=self.detail_content_wraplength())
        title_label.pack(side=LEFT, fill=X, expand=True)
        self.detail_wrap_labels.append(title_label)

        scroll_area = ttk.Frame(self.detail, style="Panel.TFrame")
        scroll_area.pack(fill=BOTH, expand=True)
        self.detail_canvas = Canvas(scroll_area, bg=COLORS["panel"], highlightthickness=0, borderwidth=0)
        self.detail_scrollbar = ttk.Scrollbar(scroll_area, orient="vertical", command=self.detail_canvas.yview)
        self.detail_canvas.configure(yscrollcommand=self.detail_scrollbar.set)
        self.detail_scrollbar.pack(side=RIGHT, fill=Y)
        self.detail_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.detail_body = ttk.Frame(self.detail_canvas, style="Panel.TFrame")
        self.detail_canvas_window = self.detail_canvas.create_window((0, 0), window=self.detail_body, anchor="nw")
        self.detail_body.bind("<Configure>", self.update_detail_scrollregion)
        self.detail_canvas.bind("<Configure>", self.on_detail_canvas_configure)
        self.detail_canvas.bind("<MouseWheel>", self.on_detail_mousewheel)
        self.detail_body.bind("<MouseWheel>", self.on_detail_mousewheel)

        owner_label = ttk.Label(self.detail_body, textvariable=self.detail_owner_var, style="DetailMuted.TLabel", wraplength=self.detail_content_wraplength())
        owner_label.pack(anchor="w", fill=X, padx=18, pady=(0, 10))
        self.detail_wrap_labels.append(owner_label)

        self.preview_box = Text(
            self.detail_body,
            height=7,
            wrap=WORD,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            relief="flat",
            padx=14,
            pady=12,
            font=("Helvetica", 11),
        )
        self.preview_box.pack(fill=X, padx=18, pady=(18, 14))
        self.preview_box.insert("1.0", self.tr("OpenGraph / 官方頁面 metadata 擷取後，預覽會顯示在這裡。", "Preview metadata will appear here after OpenGraph/official-page extraction."))
        self.preview_box.configure(state="disabled")

        ttk.Label(self.detail_body, text=self.tr("AI 生成描述", "AI generated description"), style="DetailSection.TLabel").pack(anchor="w", padx=18, pady=(4, 2))
        self.ai_summary_box = Text(
            self.detail_body,
            height=7,
            wrap=WORD,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            relief="flat",
            padx=14,
            pady=12,
            font=("Helvetica", 11),
        )
        self.ai_summary_box.pack(fill=X, padx=18, pady=(0, 14))
        self.set_ai_summary_text(self.ai_summary_placeholder)

        for label, var in [
            (self.tr("標籤", "TAGS"), self.detail_category_var),
            (self.tr("存取方式", "ACCESS"), self.detail_auth_var),
            (self.tr("狀態", "STATUS"), self.detail_status_var),
            (self.tr("範圍", "SCOPE"), self.detail_scope_var),
            (self.tr("官方連結", "OFFICIAL LINKS"), self.detail_urls_var),
        ]:
            ttk.Label(self.detail_body, text=label, style="DetailSection.TLabel").pack(anchor="w", padx=18, pady=(10, 2))
            value_label = ttk.Label(self.detail_body, textvariable=var, style="DetailText.TLabel", wraplength=self.detail_content_wraplength())
            value_label.pack(anchor="w", fill=X, padx=18)
            self.detail_wrap_labels.append(value_label)

        actions = ttk.Frame(self.detail, style="Panel.TFrame")
        actions.pack(fill=X, padx=18, pady=(12, 18))
        action_specs = [
            ("開啟文件", self.open_active_docs),
            ("AI 產生說明", self.generate_active_summary),
            ("檢查 Metadata", self.check_active_metadata),
            ("驗證本地資產", self.verify_active_assets),
            ("加入下載計畫", self.select_active_provider),
            ("標記已納管", self.manage_active_provider),
            ("解除納管", self.unmanage_active_provider),
            ("移除本地資料", self.uninstall_active_provider),
            ("編輯描述", self.edit_active_provider),
        ]
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        for index, (label, command) in enumerate(action_specs):
            ttk.Button(actions, text=label, style="Action.TButton", command=command).grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0, 6) if index % 2 == 0 else (6, 0),
                pady=(0, 8),
            )

    def category_sidebar_items(self) -> list[tuple[str, str, str]]:
        return [
            ("★ 置頂資料源", "starred", ""),
            ("全部資料源", "all", ""),
            ("NOAA", "noaa", ""),
            ("氣象 / 氣候", "weather", ""),
            ("海洋", "ocean", ""),
            ("衛星 / 遙測", "satellite", ""),
            ("地形 / 地理", "geospatial", ""),
            ("地震", "earthquake", ""),
            ("金融", "finance", ""),
            ("航運 / 航空", "aviation", ""),
            ("需要 API Key", "requires_key", ""),
        ]

    def provider_sidebar_items(self) -> list[tuple[str, str, str]]:
        owners: dict[str, int] = {}
        for row in self.rows:
            owner = row.owner.strip() or self.tr("未知提供商", "Unknown provider")
            owners[owner] = owners.get(owner, 0) + 1
        items = [(self.tr("全部提供商", "All providers"), "all", "")]
        for owner, count in sorted(owners.items(), key=lambda item: (-item[1], item[0].lower()))[:16]:
            items.append((f"{owner} ({count})", f"provider:{owner}", owner))
        return items

    def refresh_sidebar_filters(self) -> None:
        if not hasattr(self, "sidebar_filter_frame"):
            return
        for child in self.sidebar_filter_frame.winfo_children():
            child.destroy()
        items = self.provider_sidebar_items() if self.sidebar_mode_var.get() == "provider" else self.category_sidebar_items()
        for label, category, owner in items:
            # owner 模式才顯示 favicon，分類模式維持純文字，避免過多遠端 icon fetch。
            image = self.provider_icon_for_owner(owner) if owner else ""
            button_options = {
                "text": label,
                "style": "Sidebar.TButton",
                "command": lambda c=category: self.set_category(c),
            }
            if image:
                button_options["image"] = image
                button_options["compound"] = LEFT
            button = ttk.Button(self.sidebar_filter_frame, **button_options)
            button.pack(fill=X, padx=18, pady=3)

    def provider_icon_for_owner(self, owner: str) -> PhotoImage | str:
        # icon 先讀記憶體，再讀 cache，最後才背景下載，避免 sidebar 重繪時卡住 UI。
        if not owner:
            return ""
        if owner in self.provider_icon_images:
            return self.provider_icon_images[owner]
        cached = self.cached_provider_icon(owner)
        if cached is not None:
            self.provider_icon_images[owner] = cached
            return cached
        self.fetch_provider_icon_async(owner)
        return self.default_provider_icon_image()

    def default_provider_icon_image(self) -> PhotoImage:
        if self.default_provider_icon is None:
            image = PhotoImage(width=16, height=16)
            image.put(COLORS["header"], to=(0, 0, 16, 16))
            image.put(COLORS["accent"], to=(3, 3, 13, 13))
            image.put(COLORS["text"], to=(7, 4, 9, 12))
            self.default_provider_icon = image
        return self.default_provider_icon

    def cached_provider_icon(self, owner: str) -> PhotoImage | None:
        favicon_url = self.favicon_url_for_owner(owner)
        if not favicon_url:
            return None
        path = favicon_cache_path(favicon_url)
        if not path.exists():
            return None
        try:
            return PhotoImage(file=str(path))
        except TclError:
            return None

    def favicon_url_for_owner(self, owner: str) -> str:
        for row in self.rows:
            if (row.owner.strip() or self.tr("未知提供商", "Unknown provider")) != owner:
                continue
            home = provider_home_url(row.docs_url, row.signup_url, row.api_base_url)
            if home:
                return favicon_url_for_page(home)
        return ""

    def fetch_provider_icon_async(self, owner: str) -> None:
        if owner in self.provider_icon_loading:
            return
        favicon_url = self.favicon_url_for_owner(owner)
        if not favicon_url:
            return
        self.provider_icon_loading.add(owner)

        def worker() -> None:
            # 網路下載放背景 thread；Tk PhotoImage 必須回主執行緒建立。
            try:
                path = download_favicon_png(favicon_url, favicon_cache_path(favicon_url))
            except Exception as exc:
                log_event(
                    "provider_favicon_fetch_failed",
                    str(exc),
                    level="warning",
                    component="ui.sidebar",
                    context={"owner": owner, "favicon_url": favicon_url},
                )
                self.after_on_root(lambda: self.provider_icon_loading.discard(owner))
                return

            def apply_icon() -> None:
                self.provider_icon_loading.discard(owner)
                try:
                    self.provider_icon_images[owner] = PhotoImage(file=str(path))
                except TclError:
                    return
                if self.sidebar_mode_var.get() == "provider":
                    self.refresh_sidebar_filters()

            self.after_on_root(apply_icon)

        threading.Thread(target=worker, daemon=True).start()

    def after_on_root(self, callback: object) -> None:
        # 背景 thread 更新 UI 的唯一入口；root 已關閉時忽略排程錯誤。
        try:
            self.root.after(0, callback)
        except (RuntimeError, TclError):
            return

    def _build_download_plan_panel(self, parent: ttk.Frame, outer_pad: int) -> None:
        # Download plan panel 同時顯示購物車與背景工作列，避免下載狀態只藏在 log。
        plan = ttk.Frame(parent, style="Panel.TFrame")
        plan.pack(fill=X, padx=outer_pad, pady=(0, max(14, outer_pad // 2)))
        self.download_plan_panel = plan

        header = ttk.Frame(plan, style="Panel.TFrame")
        header.pack(fill=X, padx=14, pady=(12, 8))
        ttk.Label(header, textvariable=self.plan_count_var, style="DetailSection.TLabel").pack(side=LEFT)
        ttk.Entry(header, textvariable=self.plan_name_var, font=("Helvetica", 12), width=34).pack(side=LEFT, padx=(14, 8))
        ttk.Button(header, textvariable=self.download_plan_toggle_var, style="Action.TButton", command=self.toggle_download_plan_panel).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("開始", "Start"), style="Action.TButton", command=self.start_download_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("匯入", "Import"), style="Action.TButton", command=self.import_supported_plan_results_from_ui).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("暫停", "Pause"), style="Action.TButton", command=self.pause_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("繼續", "Resume"), style="Action.TButton", command=self.resume_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("取消", "Cancel"), style="Action.TButton", command=self.cancel_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("重試", "Retry"), style="Action.TButton", command=self.retry_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("移除", "Remove"), style="Action.TButton", command=self.remove_selected_from_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("清空", "Clear"), style="Action.TButton", command=self.clear_download_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("匯出計畫", "Export plan"), style="Action.TButton", command=self.export_download_plan).pack(side=RIGHT)
        body = ttk.Frame(plan, style="Panel.TFrame")
        body.pack(fill=X)
        self.download_plan_body = body
        ttk.Label(body, textvariable=self.plan_import_policy_var, style="DetailMuted.TLabel").pack(anchor="w", padx=14, pady=(0, 8))

        columns = ("name", "auth", "scope", "status", "import")
        self.cart_tree = ttk.Treeview(body, columns=columns, show="headings", height=4, selectmode="browse")
        for name, label, width, anchor in [
            ("name", self.tr("項目", "Item"), 260, "w"),
            ("auth", self.tr("認證", "Auth"), 150, "w"),
            ("scope", self.tr("範圍", "Scope"), 130, "w"),
            ("status", self.tr("下載狀態", "Download status"), 120, "center"),
            ("import", self.tr("匯入狀態", "Import status"), 210, "w"),
        ]:
            self.cart_tree.heading(name, text=label)
            self.cart_tree.column(name, width=width, anchor=anchor, stretch=True)
        self.cart_tree.pack(fill=X, padx=14, pady=(0, 12))
        self.cart_tree.bind("<<TreeviewSelect>>", self.on_cart_select)

        job_columns = ("name", "status", "progress", "import", "target")
        self.download_tree = ttk.Treeview(body, columns=job_columns, show="headings", height=4, selectmode="browse")
        for name, label, width, anchor in [
            ("name", self.tr("下載工作", "Download Job"), 240, "w"),
            ("status", self.tr("狀態", "Status"), 100, "center"),
            ("progress", self.tr("進度", "Progress"), 95, "center"),
            ("import", self.tr("匯入", "Import"), 190, "w"),
            ("target", self.tr("目標", "Target"), 360, "w"),
        ]:
            self.download_tree.heading(name, text=label)
            self.download_tree.column(name, width=width, anchor=anchor, stretch=True)
        self.download_tree.pack(fill=X, padx=14, pady=(0, 12))
        self.download_tree.bind("<<TreeviewSelect>>", self.on_download_select)
        self.apply_download_plan_visibility()

    def update_download_plan_toggle_label(self) -> None:
        # 收合時仍保留 header 與計數，讓使用者知道 plan 內還有幾個項目。
        label = self.tr("收合下載計畫", "Collapse plan") if self.download_plan_visible else self.tr("展開下載計畫", "Expand plan")
        self.download_plan_toggle_var.set(label)

    def apply_download_plan_visibility(self) -> None:
        # 只收合 plan body，不拆掉 header；下載工作仍在背景 queue 中持續更新。
        if not hasattr(self, "download_plan_body"):
            return
        if self.download_plan_visible:
            self.download_plan_body.pack(fill=X)
        else:
            self.download_plan_body.pack_forget()
        self.update_download_plan_toggle_label()

    def toggle_download_plan_panel(self) -> None:
        self.download_plan_visible = not self.download_plan_visible
        self.apply_download_plan_visibility()
        self.status_var.set(
            self.tr("已展開下載計畫。", "Download plan expanded.")
            if self.download_plan_visible
            else self.tr("已收合下載計畫。", "Download plan collapsed.")
        )

    def open_detail_drawer(self) -> None:
        if not self.active_provider_id and self.filtered_rows:
            self.active_provider_id = self.filtered_rows[0].provider_id
        self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        if not self.detail_visible or self.detail_animating_close:
            self.detail_visible = True
            self.detail_animating_close = False
            self.animate_detail_drawer(opening=True)
        else:
            self.apply_detail_layout()
        self.root.after_idle(self.resize_table_columns)

    def close_detail_drawer(self) -> None:
        if self.detail_visible:
            self.animate_detail_drawer(opening=False)
            self.root.after_idle(self.resize_table_columns)

    def scaled_pad(self) -> int:
        return clamp(int(self.root.winfo_width() * LAYOUT["outer_pad_ratio"]), 18, 40)

    def detail_width(self) -> int:
        container_width = self.content_width()
        gap = LAYOUT["detail_gap"]
        table_min = LAYOUT["table_min_with_detail"]
        if container_width <= table_min + gap:
            return clamp(container_width // 2, 280, LAYOUT["detail_min"])
        max_width = max(280, min(LAYOUT["detail_max"], container_width - table_min - gap))
        min_width = min(LAYOUT["detail_min"], max_width)
        return clamp(int(container_width * LAYOUT["detail_ratio"]), min_width, max_width)

    def content_width(self) -> int:
        container_width = 0
        if hasattr(self, "content_frame"):
            container_width = self.content_frame.winfo_width()
        if container_width <= 1:
            sidebar_width = clamp(int(self.root.winfo_width() * LAYOUT["sidebar_ratio"]), LAYOUT["sidebar_min"], LAYOUT["sidebar_max"])
            container_width = max(self.root.winfo_width() - sidebar_width - (2 * self.scaled_pad()), 1)
        return max(container_width, 1)

    def detail_content_wraplength(self) -> int:
        return max(self.detail_width() - 64, 260)

    def apply_detail_wraplength(self) -> None:
        wraplength = self.detail_content_wraplength()
        for label in getattr(self, "detail_wrap_labels", []):
            label.configure(wraplength=wraplength)
        if hasattr(self, "detail_canvas"):
            canvas_width = max(self.detail_current_width - 18, 260)
            self.detail_canvas.itemconfigure(self.detail_canvas_window, width=canvas_width)

    def update_detail_scrollregion(self, _event: object | None = None) -> None:
        self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all"))

    def on_detail_canvas_configure(self, event: object) -> None:
        width = max(getattr(event, "width", self.detail_width()) - 2, 260)
        self.detail_canvas.itemconfigure(self.detail_canvas_window, width=width)
        self.update_detail_scrollregion()

    def on_detail_mousewheel(self, event: object) -> str:
        delta = getattr(event, "delta", 0)
        if delta:
            self.detail_canvas.yview_scroll(int(-1 * (delta / 120)), "units")
        return "break"

    def apply_detail_layout(self) -> None:
        if not self.detail_visible:
            return
        if not self.detail_animation_after_id:
            self.detail_current_width = self.detail_width()
            self.detail.configure(width=self.detail_current_width)
        self.apply_detail_wraplength()

    def pack_content_area(self, detail_width: int | None = None) -> None:
        self.table_frame.pack_forget()
        self.detail.pack_forget()
        if self.detail_visible:
            if detail_width is None:
                self.apply_detail_layout()
            else:
                self.detail_current_width = max(detail_width, 1)
                self.detail.configure(width=self.detail_current_width)
                self.apply_detail_wraplength()
            self.detail.pack(side=RIGHT, fill=Y, padx=(LAYOUT["detail_gap"], 0))
        self.table_frame.pack(side=LEFT, fill=BOTH, expand=True)

    def cancel_detail_animation(self) -> None:
        if self.detail_animation_after_id:
            with contextlib_suppress_tcl_error():
                self.root.after_cancel(self.detail_animation_after_id)
            self.detail_animation_after_id = None

    def current_detail_width(self) -> int:
        if self.detail.winfo_ismapped():
            width = self.detail.winfo_width()
            if width > 1:
                return width
        if self.detail_current_width > 1:
            return self.detail_current_width
        return self.detail_width()

    def animate_detail_drawer(self, opening: bool) -> None:
        # 抽屜動畫只改寬度，不重建 widget，避免 Text/Treeview 狀態在開關時遺失。
        self.cancel_detail_animation()
        target_width = self.detail_width()
        start_width = self.current_detail_width() if self.detail.winfo_ismapped() else 1
        if opening:
            self.detail_visible = True
            self.detail_animating_close = False
            start_width = min(start_width, target_width)
            self.pack_content_area(detail_width=start_width)
        else:
            self.detail_animating_close = True
            start_width = max(start_width, 1)
            target_width = 1
        self.run_detail_animation(start_width, target_width, opening=opening, step=0)

    def run_detail_animation(self, start_width: int, target_width: int, opening: bool, step: int) -> None:
        steps = max(int(LAYOUT["detail_animation_steps"]), 1)
        progress = min(step / steps, 1.0)
        eased = 1 - ((1 - progress) ** 3)
        width = max(1, int(start_width + ((target_width - start_width) * eased)))
        self.detail_current_width = width
        self.detail.configure(width=width)
        self.apply_detail_wraplength()
        self.resize_table_columns()
        if step < steps:
            self.detail_animation_after_id = self.root.after(
                int(LAYOUT["detail_animation_delay_ms"]),
                lambda: self.run_detail_animation(start_width, target_width, opening=opening, step=step + 1),
            )
            return
        self.detail_animation_after_id = None
        if opening:
            self.detail_current_width = self.detail_width()
            self.apply_detail_layout()
        else:
            self.detail_visible = False
            self.detail_animating_close = False
            self.detail_current_width = 0
            self.pack_content_area()
        self.root.after_idle(self.resize_table_columns)

    def on_root_configure(self, event: object) -> None:
        if getattr(event, "widget", None) is not self.root:
            return
        if self.resize_after_id:
            self.root.after_cancel(self.resize_after_id)
        # resize event 很密集，用 after debounce 避免每個像素都重算欄寬。
        self.resize_after_id = self.root.after(80, self.apply_responsive_layout)

    def apply_responsive_layout(self) -> None:
        self.resize_after_id = None
        width = max(self.root.winfo_width(), 1)
        height = max(self.root.winfo_height(), 1)
        rowheight = clamp(int(height * LAYOUT["rowheight_ratio"]), 42, 62)
        ttk.Style(self.root).configure("Treeview", rowheight=rowheight)
        self.apply_detail_layout()
        self.resize_table_columns()

    def resize_table_columns(self) -> None:
        # 手動欄寬優先，剩餘空間再依比例分配給自動欄位。
        table_width = max(self.tree.winfo_width(), 1)
        reserved = 24
        manual_widths = {
            name: self.normalized_column_width(name, width)
            for name, width in self.column_width_overrides.items()
        }
        manual_total = sum(manual_widths.values())
        auto_columns = [column for column in TABLE_COLUMNS if column[0] not in manual_widths]
        available = max(table_width - reserved - manual_total, 1)
        ratio_base = 1.0 if not manual_widths else max(sum(column[2] for column in auto_columns), 0.01)
        for name, _label, ratio, min_width, max_width, _anchor, _stretch in TABLE_COLUMNS:
            if name in manual_widths:
                width = manual_widths[name]
            else:
                width = clamp(int(available * (ratio / ratio_base)), min_width, max_width)
            self.tree.column(name, width=width)

    def table_column_name_from_event(self, event: object) -> str:
        column_id = self.tree.identify_column(getattr(event, "x", 0))
        if not column_id.startswith("#"):
            return ""
        try:
            index = int(column_id[1:]) - 1
        except ValueError:
            return ""
        if index < 0 or index >= len(TABLE_COLUMNS):
            return ""
        return TABLE_COLUMNS[index][0]

    def on_tree_button_press(self, event: object) -> None:
        region = self.tree.identify("region", getattr(event, "x", 0), getattr(event, "y", 0))
        self.resizing_column_name = self.table_column_name_from_event(event) if region == "separator" else None
        if self.resizing_column_name:
            self.set_tree_cursor(self.table_resize_cursor)

    def on_tree_button_release(self, event: object) -> None:
        if not self.resizing_column_name:
            return
        name = self.resizing_column_name
        self.resizing_column_name = None
        self.on_tree_motion(event)
        self.root.after_idle(lambda column_name=name: self.finish_tree_column_resize(column_name))

    def finish_tree_column_resize(self, name: str) -> None:
        width = self.normalized_column_width(name, int(self.tree.column(name, "width")))
        self.column_width_overrides[name] = width
        self.save_column_width_overrides()
        self.resize_table_columns()
        label = next((column[1] for column in TABLE_COLUMNS if column[0] == name), name)
        self.status_var.set(self.tr(f"已調整欄寬：{label}", f"Column width updated: {label}"))

    def reset_table_column_widths(self) -> None:
        self.column_width_overrides.clear()
        self.save_column_width_overrides()
        self.resize_table_columns()
        self.status_var.set(self.tr("已重設表格欄寬。", "Table column widths reset."))

    def on_tree_motion(self, event: object) -> None:
        if self.resizing_column_name:
            self.set_tree_cursor(self.table_resize_cursor)
            return
        region = self.tree.identify("region", getattr(event, "x", 0), getattr(event, "y", 0))
        cursor = self.table_resize_cursor if region == "separator" else self.tree_default_cursor
        self.set_tree_cursor(cursor)

    def on_tree_leave(self, _event: object) -> None:
        if not self.resizing_column_name:
            self.set_tree_cursor(self.tree_default_cursor)

    def set_tree_cursor(self, cursor: str) -> None:
        if str(self.tree.cget("cursor") or "") == cursor:
            return
        try:
            self.tree.configure(cursor=cursor)
        except TclError:
            self.tree.configure(cursor=self.tree_default_cursor)

    def set_search_placeholder(self) -> None:
        if self.search_var.get():
            return
        self.search_placeholder_active = True
        self.search_var.set(self.search_placeholder_text)
        self.search_entry.configure(style="SearchPlaceholder.TEntry")

    def on_search_focus_in(self, _event: object) -> None:
        if self.search_placeholder_active:
            self.search_placeholder_active = False
            self.search_var.set("")
            self.search_entry.configure(style="Search.TEntry")

    def on_search_focus_out(self, _event: object) -> None:
        if not self.search_var.get().strip():
            self.set_search_placeholder()

    def ai_profile_labels(self) -> dict[str, str]:
        return {
            f"{profile.label} ({profile.kind} / {profile.model})": profile.id
            for profile in core.ai_summary_profiles()
        }

    def set_category(self, category: str) -> None:
        self.category_var.set(category)
        self.apply_filter()

    def reload_data(self) -> None:
        # reload 是 UI 的資料同步點：一次讀 provider、dataset，再重建篩選與下載計畫顯示。
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            entries = repository.list_provider_catalog_entries()
            datasets = repository.list_datasets()
        finally:
            conn.close()
        self.rows = [ProviderRow(entry) for entry in entries]
        self.datasets_by_provider = {}
        for dataset in datasets:
            self.datasets_by_provider.setdefault(dataset.provider_id, []).append(dataset)
        for provider_datasets in self.datasets_by_provider.values():
            provider_datasets.sort(key=lambda item: item.title.lower())
        for row in self.rows:
            self.selected.setdefault(row.provider_id, BooleanVar(value=False))
        known_ids = {row.provider_id for row in self.rows}
        for provider_id in list(self.selected):
            if provider_id not in known_ids:
                del self.selected[provider_id]
        self.apply_filter()
        if self.active_provider_id not in {row.provider_id for row in self.rows}:
            self.active_provider_id = self.rows[0].provider_id if self.rows else ""
        self.refresh_sidebar_filters()
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.update_download_plan_panel()
        self.status_var.set(f"已載入 {len(self.rows)} 個資料源。")

    def apply_filter(self) -> None:
        if not hasattr(self, "tree"):
            return
        # 搜尋會同時命中 provider 欄位與 crawler 發現的 dataset 欄位。
        query = "" if self.search_placeholder_active else self.search_var.get().strip().lower()
        category = self.category_var.get()
        self.current_filter_query = query
        self.current_filter_category = category
        filtered = []
        for row in self.rows:
            provider_datasets = self.datasets_by_provider.get(row.provider_id, [])
            if category == "starred" and not row.is_starred:
                continue
            if category == "noaa" and "noaa" not in row.provider_id.lower() and "noaa" not in row.owner.lower():
                continue
            if category == "requires_key" and not row.key_env_var:
                continue
            if category.startswith("provider:"):
                if row.owner != category.removeprefix("provider:"):
                    continue
            elif category not in ("all", "starred", "noaa", "requires_key"):
                if category not in row.categories and not any(category in dataset.categories for dataset in provider_datasets):
                    continue
            haystack = " ".join([row.provider_id, row.name, row.owner, row.category_label, row.auth_type, row.notes]).lower()
            dataset_haystack = " ".join(
                " ".join(
                    [
                        dataset.dataset_id,
                        dataset.title,
                        ", ".join(dataset.categories),
                        dataset.data_type,
                        dataset.native_format,
                        dataset.geographic_scope,
                        str(dataset.metadata.get("candidate_status") or ""),
                    ]
                )
                for dataset in provider_datasets
            ).lower()
            if query and query not in haystack:
                if query not in dataset_haystack:
                    continue
            filtered.append(row)
        self.filtered_rows = filtered
        self.render_table()

    def render_table(self) -> None:
        # Treeview 不是 virtual list；資料量變大前先用完整重繪保持狀態簡單可預期。
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.dataset_table_items = {}
        for row in self.filtered_rows:
            checked = "?" if self.selected[row.provider_id].get() else ""
            tags = []
            if row.is_starred:
                tags.append("starred")
            if row.action_label:
                tags.append("has_action")
            if row.update_status == "remote_updated":
                tags.append("remote_updated")
            provider_datasets = self.visible_datasets_for_provider(row.provider_id)
            row_name = row.name
            if provider_datasets:
                row_name = self.tr(f"{row.name}（{len(provider_datasets)} 筆資料集）", f"{row.name} ({len(provider_datasets)} datasets)")
            self.tree.insert(
                "",
                END,
                iid=row.provider_id,
                values=(
                    row.star_label,
                    checked,
                    row_name,
                    row.category_label,
                    row.local_label,
                    self.localized_download_label(row.download_eligibility),
                    row.action_label,
                ),
                tags=tuple(tags),
            )
            if self.show_dataset_rows_var.get():
                for dataset in provider_datasets:
                    item_id = self.dataset_tree_iid(dataset)
                    self.dataset_table_items[item_id] = dataset
                    self.tree.insert(
                        "",
                        END,
                        iid=item_id,
                        values=(
                            "",
                            "+",
                            f"  ↳ {dataset.title}",
                            self.dataset_category_label(dataset),
                            self.dataset_candidate_status_label(dataset),
                            self.dataset_download_label(dataset),
                            self.tr("加入", "Add"),
                        ),
                        tags=("dataset_row",),
                    )
        if self.active_provider_id in {row.provider_id for row in self.filtered_rows}:
            self.tree.selection_set(self.active_provider_id)
            self.tree.focus(self.active_provider_id)
        self.resize_table_columns()
        self.update_download_plan_panel()
        self.status_var.set(f"顯示 {len(self.filtered_rows)} / {len(self.rows)} 個資料源。")

    def dataset_tree_iid(self, dataset: core.Dataset) -> str:
        return f"dataset::{dataset.dataset_uid}"

    def dataset_for_table_item(self, item: object) -> core.Dataset | None:
        return self.dataset_table_items.get(str(item))

    def provider_id_for_table_item(self, item: object) -> str:
        dataset = self.dataset_for_table_item(item)
        if dataset is not None:
            return dataset.provider_id
        return str(item)

    def visible_datasets_for_provider(self, provider_id: str) -> list[core.Dataset]:
        # rejected 候選不顯示在主列表，但仍可在候選審核面板查到歷史狀態。
        datasets = self.datasets_by_provider.get(provider_id, [])
        query = self.current_filter_query
        category = self.current_filter_category
        visible = []
        for dataset in datasets:
            if self.dataset_candidate_status(dataset) == "rejected":
                continue
            if category not in ("all", "starred", "noaa", "requires_key") and not category.startswith("provider:"):
                if category not in dataset.categories:
                    continue
            if query and query not in self.dataset_search_text(dataset):
                continue
            visible.append(dataset)
        return visible

    def dataset_search_text(self, dataset: core.Dataset) -> str:
        metadata = dataset.metadata
        return " ".join(
            [
                dataset.dataset_uid,
                dataset.provider_id,
                dataset.dataset_id,
                dataset.title,
                ", ".join(dataset.categories),
                dataset.data_type,
                dataset.native_format,
                dataset.geographic_scope,
                dataset.temporal_coverage,
                str(metadata.get("candidate_status") or ""),
                str(metadata.get("source_url") or ""),
            ]
        ).lower()

    def dataset_candidate_status(self, dataset: core.Dataset) -> str:
        return str(dataset.metadata.get("candidate_status") or "").strip().lower()

    def dataset_candidate_status_label(self, dataset: core.Dataset) -> str:
        labels = {
            "needs_review": self.tr("待審核", "Needs review"),
            "approved": self.tr("可用", "Approved"),
            "planned": self.tr("已排入", "Planned"),
            "rejected": self.tr("已拒絕", "Rejected"),
        }
        return labels.get(self.dataset_candidate_status(dataset), self.tr("已發現", "Discovered"))

    def dataset_category_label(self, dataset: core.Dataset) -> str:
        values = [*dataset.categories]
        if dataset.data_type and dataset.data_type not in values:
            values.append(dataset.data_type)
        if dataset.native_format and dataset.native_format not in values:
            values.append(dataset.native_format)
        return ", ".join(values)

    def dataset_download_label(self, dataset: core.Dataset) -> str:
        options = core.version_options_for_dataset(dataset)
        option = options[0] if options else None
        if option and option.download_url and core.looks_like_direct_download(option.download_url):
            return self.tr("直接下載", "Direct")
        if option and option.download_url:
            return self.tr("需轉接器", "Needs adapter")
        return self.tr("metadata", "metadata")

    def add_dataset_to_plan(self, dataset: core.Dataset) -> None:
        options = core.version_options_for_dataset(dataset)
        if not options:
            self.status_var.set(self.tr(f"這筆資料集沒有版本資訊：{dataset.title}", f"No version metadata for dataset: {dataset.title}"))
            return
        self.add_provider_version_to_plan(dataset.provider_id, options[0])

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

    def toggle_provider(self, provider_id: str) -> None:
        var = self.selected[provider_id]
        var.set(not var.get())
        self.render_table()
        row = self.row_by_provider_id(provider_id)
        label = row.name if row else provider_id
        self.status_var.set(f"{'已加入下載計畫' if var.get() else '已移出下載計畫'}：{label}")

    def add_provider_to_plan(self, provider_id: str) -> None:
        row = self.row_by_provider_id(provider_id)
        if row is None:
            return
        self.remove_provider_version_plan_items(provider_id)
        var = self.selected.setdefault(provider_id, BooleanVar(value=False))
        already_selected = var.get()
        var.set(True)
        self.active_provider_id = provider_id
        self.render_table()
        self.status_var.set(
            f"{'已在下載計畫中' if already_selected else '已加入下載計畫'}：{row.name}"
        )

    def add_provider_version_to_plan(self, provider_id: str, option: core.DatasetVersionOption) -> None:
        # dataset/version plan 使用獨立 plan_key，保留 provider 一對多資料集的購物車語意。
        row = self.row_by_provider_id(provider_id)
        if row is None:
            return
        plan_key = self.plan_key_for_version(provider_id, option)
        self.plan_version_by_provider[plan_key] = option
        self.plan_provider_by_key[plan_key] = provider_id
        self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
        self.active_provider_id = provider_id
        self.render_table()
        self.status_var.set(self.tr(f"已加入下載計畫：{row.name} {option.menu_label}", f"Added {row.name} {option.menu_label} to download plan"))

    def plan_key_for_version(self, provider_id: str, option: core.DatasetVersionOption) -> str:
        version = option.version or option.label or "unversioned"
        return f"{provider_id}::dataset::{option.dataset_uid}::{version}"

    def provider_id_for_plan_key(self, plan_key: str) -> str:
        if plan_key in self.plan_provider_by_key:
            return self.plan_provider_by_key[plan_key]
        if "::dataset::" in plan_key:
            return plan_key.split("::dataset::", 1)[0]
        return plan_key

    def version_plan_keys_for_provider(self, provider_id: str) -> list[str]:
        return [
            plan_key
            for plan_key in self.plan_version_by_provider
            if self.provider_id_for_plan_key(plan_key) == provider_id
        ]

    def remove_provider_version_plan_items(self, provider_id: str) -> None:
        for plan_key in self.version_plan_keys_for_provider(provider_id):
            self.plan_version_by_provider.pop(plan_key, None)
            self.plan_provider_by_key.pop(plan_key, None)

    def selected_plan_items(self) -> list[tuple[str, ProviderRow, core.DatasetVersionOption | None]]:
        # 先列具體 dataset/version，再補 provider-level 選取，避免同 provider 重複產生 plan entry。
        items: list[tuple[str, ProviderRow, core.DatasetVersionOption | None]] = []
        seen_keys: set[str] = set()
        for plan_key, option in self.plan_version_by_provider.items():
            provider_id = self.provider_id_for_plan_key(plan_key)
            row = self.row_by_provider_id(provider_id)
            if row is not None:
                items.append((plan_key, row, option))
                seen_keys.add(plan_key)
        for row in self.selected_rows():
            if self.version_plan_keys_for_provider(row.provider_id):
                continue
            if row.provider_id not in seen_keys:
                items.append((row.provider_id, row, None))
                seen_keys.add(row.provider_id)
        return items

    def selected_plan_keys(self) -> list[str]:
        return [plan_key for plan_key, _row, _option in self.selected_plan_items()]

    def plan_item_label(self, plan_key: str, row: ProviderRow | None = None, option: core.DatasetVersionOption | None = None) -> str:
        provider_id = self.provider_id_for_plan_key(plan_key)
        row = row or self.row_by_provider_id(provider_id)
        label = row.name if row else provider_id
        option = option or self.plan_version_by_provider.get(plan_key)
        if option:
            return f"{label} / {option.dataset_id} {option.version or option.label}"
        return label

    def plan_entry_for_item(
        self,
        row: ProviderRow,
        option: core.DatasetVersionOption | None = None,
        plan_key: str = "",
    ) -> tuple[dict[str, object] | None, str]:
        if plan_key and plan_key in self.download_plan_entries_by_provider:
            # 已排過下載的 entry 保留原 target/import_plan，避免 UI 重繪後改變下載目標。
            return dict(self.download_plan_entries_by_provider[plan_key]), ""
        if option:
            dataset = self.dataset_for_version_option(option)
            if dataset is None:
                return None, self.tr("找不到候選資料集 metadata", "Dataset metadata was not found")
            return (
                core.provider_dataset_version_plan_entry(
                    self.provider_from_row(row),
                    dataset,
                    option,
                    downloads_root=DOWNLOADS_DIR,
                ),
                "",
            )

        entry = core.provider_plan_entry(self.provider_from_row(row))
        eligibility = row.download_eligibility
        if eligibility.status == "direct_download" and eligibility.direct_url:
            target_path = self.download_target_for_row(row, eligibility.direct_url)
            entry["download_url"] = eligibility.direct_url
            entry["target_path"] = str(target_path)
            entry["use_staging"] = True
        return entry, ""

    def import_status_label(
        self,
        plan_key: str,
        row: ProviderRow | None = None,
        option: core.DatasetVersionOption | None = None,
    ) -> str:
        remembered = self.import_status_by_plan_key.get(plan_key)
        if remembered:
            status, detail = remembered
            return f"{status}: {detail}" if detail else status
        entry = dict(self.download_plan_entries_by_provider.get(plan_key) or {})
        if not entry:
            row = row or self.row_by_provider_id(self.provider_id_for_plan_key(plan_key))
            if row is None:
                return self.tr("未準備", "Not ready")
            entry, build_error = self.plan_entry_for_item(row, option or self.plan_version_by_provider.get(plan_key), plan_key=plan_key)
            if entry is None:
                return self.tr(f"metadata 缺失: {build_error}", f"Missing metadata: {build_error}")
        import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
        status = str(import_plan.get("status") or "").strip()
        table_hint = str(import_plan.get("table_hint") or "").strip()
        if status == "supported_after_download":
            target_table = self.unique_import_table_name(state_file(CURATED_IMPORTS_NAME), table_hint) if table_hint else ""
            table_label = f" -> {target_table}" if target_table else ""
            manifest_status = self.plan_entry_manifest_status(entry)
            if manifest_status == "ok":
                return self.tr(f"可匯入{table_label}", f"Ready to import{table_label}")
            if manifest_status:
                return self.tr(f"待下載/驗證{table_label}", f"Needs download/verify{table_label}")
            return self.tr(f"可匯入{table_label}", f"Ready to import{table_label}")
        if status == "adapter_review_required":
            adapter = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
            adapter_id = str(adapter.get("adapter_id") or "").strip()
            return self.tr(f"需 adapter: {adapter_id}" if adapter_id else "需 adapter", f"Adapter needed: {adapter_id}" if adapter_id else "Adapter needed")
        if status == "requires_unpack_or_adapter":
            adapter = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
            adapter_id = str(adapter.get("adapter_id") or "").strip()
            return self.tr(f"需解壓/adapter: {adapter_id}" if adapter_id else "需解壓/adapter", f"Unpack/adapter needed: {adapter_id}" if adapter_id else "Unpack/adapter needed")
        if status:
            return status
        return self.tr("未支援自動匯入", "No auto import")

    def plan_entry_manifest_status(self, entry: dict[str, object]) -> str:
        try:
            target = download_target_from_plan_entry(entry)
        except Exception:
            return ""
        manifest_path = target.output_path.with_suffix(target.output_path.suffix + ".manifest.json")
        if not manifest_path.exists():
            return "missing"
        return verify_manifest_file(manifest_path).status

    def unique_import_table_name(self, sqlite_path: Path, table_name: str) -> str:
        base = table_name.strip() or "imported_dataset"
        if not table_exists(sqlite_path, base):
            return base
        for index in range(2, 1000):
            suffix = f"_{index}"
            candidate = f"{base[:63 - len(suffix)]}{suffix}"
            if not table_exists(sqlite_path, candidate):
                return candidate
        timestamp = time.strftime("%Y%m%d%H%M%S")
        suffix = f"_{timestamp}"
        return f"{base[:63 - len(suffix)]}{suffix}"

    def import_existing_table_policy_label(self, policy: str) -> str:
        labels = {
            "rename": self.tr("保留舊表，匯入成新表", "Keep old table and import as a new table"),
            "skip": self.tr("保留舊表，略過同名項目", "Keep old table and skip same-name items"),
            "replace": self.tr("覆蓋同名表", "Replace same-name table"),
        }
        return labels.get(normalized_ui_import_policy(policy), labels["rename"])

    def import_existing_table_policy_status_label(self, policy: str) -> str:
        return self.tr(
            f"匯入策略：{self.import_existing_table_policy_label(policy)}",
            f"Import policy: {self.import_existing_table_policy_label(policy)}",
        )

    def ask_import_existing_table_policy(self) -> str | None:
        return ImportExistingTablePolicyDialog(self).result

    def version_options_for_provider(self, provider_id: str) -> list[core.DatasetVersionOption]:
        # 若 catalog 尚未有 adapter dataset，右鍵開版本選單時做一次 bounded discovery。
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            datasets = repository.list_datasets(provider_id)
            if not datasets:
                providers = repository.load_providers([provider_id])
                for provider in providers:
                    for adapter in core.adapters_for_provider(provider):
                        for dataset in adapter.discover(provider):
                            repository.upsert_dataset(dataset)
                datasets = repository.list_datasets(provider_id)
            return core.version_options_for_datasets(datasets)
        finally:
            conn.close()

    def dataset_for_version_option(self, option: core.DatasetVersionOption) -> core.Dataset | None:
        conn = self._connect()
        try:
            return core.ApiCatalogRepository(conn).get_dataset(option.dataset_uid)
        finally:
            conn.close()

    def selected_provider_ids(self) -> list[str]:
        return [provider_id for provider_id, var in self.selected.items() if var.get()]

    def selected_rows(self) -> list[ProviderRow]:
        selected_ids = set(self.selected_provider_ids())
        return [row for row in self.rows if row.provider_id in selected_ids]

    def update_download_plan_panel(self) -> None:
        if not hasattr(self, "cart_tree"):
            return
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
        items = self.selected_plan_items()
        for plan_key, row, version in items:
            version_label = version.menu_label if version else self.localized_download_label(row.download_eligibility)
            self.cart_tree.insert(
                "",
                END,
                iid=plan_key,
                values=(
                    self.plan_item_label(plan_key, row, version),
                    row.auth_type,
                    row.geographic_scope,
                    version_label,
                    self.import_status_label(plan_key, row, version),
                ),
            )
        self.plan_count_var.set(self.tr(f"下載計畫：{len(items)} 個項目", f"Download Plan: {len(items)} items"))

        self.update_download_jobs_panel()

    def on_cart_select(self, _event: object) -> None:
        selection = self.cart_tree.selection()
        if not selection:
            return
        self.active_provider_id = self.provider_id_for_plan_key(str(selection[0]))
        if self.active_provider_id in {row.provider_id for row in self.filtered_rows}:
            self.tree.selection_set(self.active_provider_id)
            self.tree.focus(self.active_provider_id)
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))

    def on_download_select(self, _event: object) -> None:
        selection = self.download_tree.selection()
        if selection:
            self.active_provider_id = self.provider_id_for_plan_key(str(selection[0]))

    def start_download_plan(self) -> None:
        items = self.selected_plan_items()
        if not items:
            messagebox.showinfo(self.tr("下載計畫是空的", "Download plan is empty"), self.tr("請先加入至少一個資料源。", "Add at least one source to the download plan first."))
            return
        self.start_download_plan_items(items)

    def start_download_rows(self, rows: list[ProviderRow]) -> None:
        self.start_download_plan_items([(row.provider_id, row, self.plan_version_by_provider.get(row.provider_id)) for row in rows])

    def localized_download_skip_summary(self, skip_summary: dict[str, int]) -> str:
        labels = {
            "adapter_required": self.tr("需 Adapter", "adapter required"),
            "metadata_only": self.tr("僅 metadata", "metadata only"),
            "unavailable": self.tr("不可下載", "unavailable"),
            "missing_download_url": self.tr("缺下載 URL", "missing download URL"),
            "not_direct": self.tr("非直接檔案", "not direct"),
        }
        parts = [f"{labels.get(bucket, bucket)}={count}" for bucket, count in skip_summary.items() if count]
        return "；".join(parts)

    def download_skip_next_action_message(self, summary: str, *, partial: bool) -> str:
        # 下載略過不是單純錯誤：多數是尚未解析的 API/selector/metadata，需要把下一步明確告訴使用者。
        if partial:
            return summary + "\n\n" + self.tr(
                "已啟動的 direct download 會繼續排隊；被略過的項目仍是 API、入口頁、selector 或 metadata。請先開 Adapter 待辦，或按「解析 Adapter 計畫」把可安全界定的小樣本轉成 direct download。",
                "Started direct downloads will stay queued. Skipped items are still APIs, landing pages, selectors, or metadata. Open the adapter review queue or resolve the adapter plan before downloading them.",
            )
        return summary + "\n\n" + self.tr(
            "這些項目目前還是 API、入口頁、selector 或 metadata。請先開 Adapter 待辦，或按「解析 Adapter 計畫」把可安全界定的小樣本轉成 direct download。",
            "These items are still APIs, landing pages, selectors, or metadata. Open the adapter review queue or resolve the adapter plan before downloading.",
        )

    def import_skipped_detail_message(self, skipped: list[str], *, limit: int = 4) -> str:
        if not skipped:
            return ""
        # 匯入流程可能部分成功；把略過原因直接列出，避免使用者誤以為所有 plan item 都已進 SQLite。
        preview_items = skipped[:limit]
        preview = "\n".join(f"- {item}" for item in preview_items)
        remaining = len(skipped) - len(preview_items)
        heading = self.tr(
            f"\n\n會略過：{len(skipped)} 個不支援或未準備好的項目。原因預覽：",
            f"\n\nWill skip {len(skipped)} unsupported or unready items. Reason preview:",
        )
        if remaining:
            tail = self.tr(
                f"\n...還有 {remaining} 個項目未列出；請依原因先處理 Adapter 待辦、解析 Adapter 計畫、下載或 manifest 健康狀態。",
                f"\n...{remaining} more items are not shown; follow the reason to resolve adapter review, adapter-plan resolution, download, or manifest health first.",
            )
        else:
            tail = self.tr(
                "\n請依原因先處理 Adapter 待辦、解析 Adapter 計畫、下載或 manifest 健康狀態。",
                "\nFollow the reason to resolve adapter review, adapter-plan resolution, download, or manifest health first.",
            )
        return f"{heading}\n{preview}{tail}"

    def start_download_plan_items(self, items: list[tuple[str, ProviderRow, core.DatasetVersionOption | None]]) -> None:
        # 這裡只啟動 direct_download；需要 adapter 的項目保留在審核/解析流程，不硬猜 URL。
        started = 0
        skipped = 0
        skip_summary: dict[str, int] = {}
        for plan_key, row, version in items:
            if not self.prepare_provider_for_download(plan_key):
                continue
            plan_entry, build_error = self.plan_entry_for_item(row, version, plan_key=plan_key)
            if plan_entry is None:
                skipped += 1
                skip_summary["not_direct"] = skip_summary.get("not_direct", 0) + 1
                self.download_status_by_provider[plan_key] = ("skipped", "0%", build_error)
                continue
            eligibility = plan_entry.get("download_eligibility", {})
            status = str(eligibility.get("status") if isinstance(eligibility, dict) else "")
            url = str(plan_entry.get("download_url") or "")
            if status != "direct_download" or not url:
                reason = str(eligibility.get("reason") if isinstance(eligibility, dict) else "") or self.tr("需要 adapter 審核後才能下載", "Adapter review is required before download")
                skipped += 1
                bucket = download_entry_skip_bucket(plan_entry) or "not_direct"
                skip_summary[bucket] = skip_summary.get(bucket, 0) + 1
                self.download_status_by_provider[plan_key] = ("skipped", "0%", reason)
                continue
            target_path = Path(str(plan_entry.get("target_path") or self.download_target_for_row(row, url)))
            plan_entry["target_path"] = str(target_path)
            self.import_status_by_plan_key.pop(plan_key, None)
            job = self.download_queue.submit(plan_entry)
            self.download_jobs_by_provider[plan_key] = job.job_id
            self.download_providers_by_job[job.job_id] = plan_key
            self.download_plan_entries_by_provider[plan_key] = dict(plan_entry)
            self.download_status_by_provider[plan_key] = ("queued", "0%", str(target_path))
            started += 1
        self.update_download_jobs_panel()
        skip_detail = self.localized_download_skip_summary(skip_summary)
        summary = self.tr(f"下載工作已開始：{started}；略過：{skipped}", f"Download jobs started: {started}; skipped: {skipped}")
        if skip_detail:
            summary = f"{summary} ({skip_detail})"
        self.status_var.set(summary)
        if started == 0 and skipped:
            # 這個提示把「沒有直接下載」改成可行的下一步，避免 Demo 時看起來像按鈕沒接上。
            messagebox.showinfo(
                self.tr("沒有可直接下載項目", "No direct downloads"),
                self.download_skip_next_action_message(summary, partial=False),
            )
        elif started and skipped:
            # 部分成功仍要提示剩餘項目的下一步，否則使用者會誤以為整份 plan 都已經處理完。
            messagebox.showinfo(
                self.tr("部分項目未啟動下載", "Some items were not started"),
                self.download_skip_next_action_message(summary, partial=True),
            )

    def prepare_provider_for_download(self, plan_key: str) -> bool:
        # 完成/失敗/取消的工作可重排；running/paused 工作不能被同一 plan_key 重複提交。
        job_id = self.download_jobs_by_provider.get(plan_key)
        if not job_id:
            return True
        progress = self.download_progress_by_provider.get(plan_key)
        if progress and progress.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            self.download_jobs_by_provider.pop(plan_key, None)
            self.download_providers_by_job.pop(job_id, None)
            self.download_plan_entries_by_provider.pop(plan_key, None)
            self.registered_completed_downloads.discard(plan_key)
            self.import_status_by_plan_key.pop(plan_key, None)
            return True
        return False

    def download_url_for_row(self, row: ProviderRow) -> str:
        return row.download_eligibility.direct_url

    def download_target_for_row(self, row: ProviderRow, url: str) -> Path:
        parsed = urllib.parse.urlparse(url)
        filename = Path(urllib.parse.unquote(parsed.path)).name
        if not filename or "." not in filename:
            filename = f"{row.provider_id}.download"
        return DOWNLOADS_DIR / row.provider_id / filename

    def active_download_job_id(self) -> str | None:
        selection = self.download_tree.selection()
        plan_key = str(selection[0]) if selection else self.active_provider_id
        return self.download_jobs_by_provider.get(plan_key)

    def pause_active_download(self) -> None:
        job_id = self.active_download_job_id()
        if not job_id:
            self.status_var.set(self.tr("沒有可暫停的下載工作。", "No active download job to pause."))
            return
        self.download_queue.pause(job_id)

    def resume_active_download(self) -> None:
        job_id = self.active_download_job_id()
        if not job_id:
            self.status_var.set(self.tr("沒有可繼續的下載工作。", "No active download job to resume."))
            return
        self.download_queue.resume(job_id)

    def cancel_active_download(self) -> None:
        job_id = self.active_download_job_id()
        if not job_id:
            self.status_var.set(self.tr("沒有可取消的下載工作。", "No active download job to cancel."))
            return
        self.download_queue.cancel(job_id)

    def retry_active_download(self) -> None:
        plan_key = self.active_download_provider_id()
        provider_id = self.provider_id_for_plan_key(plan_key)
        row = self.row_by_provider_id(provider_id)
        if row is None:
            self.status_var.set(self.tr("沒有可重試的下載工作。", "No active download job to retry."))
            return
        job_id = self.download_jobs_by_provider.get(plan_key)
        progress = self.download_progress_by_provider.get(plan_key)
        if job_id and progress and progress.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
            self.status_var.set(self.tr("只有失敗或取消的下載工作可以重試。", "Only failed or cancelled jobs can be retried."))
            return
        self.download_jobs_by_provider.pop(plan_key, None)
        if job_id:
            self.download_providers_by_job.pop(job_id, None)
        self.download_plan_entries_by_provider.pop(plan_key, None)
        self.registered_completed_downloads.discard(plan_key)
        self.import_status_by_plan_key.pop(plan_key, None)
        self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
        self.start_download_plan_items([(plan_key, row, self.plan_version_by_provider.get(plan_key))])

    def active_download_provider_id(self) -> str:
        selection = self.download_tree.selection()
        return str(selection[0]) if selection else self.active_provider_id

    def on_download_progress_threadsafe(self, progress: DownloadProgress) -> None:
        # DownloadQueue callback 可能來自 worker thread；Tk 更新必須排到主 thread。
        self.root.after(0, lambda update=progress: self.on_download_progress(update))

    def on_download_progress(self, progress: DownloadProgress) -> None:
        plan_key = self.download_providers_by_job.get(progress.job_id, progress.provider_id)
        self.download_progress_by_provider[plan_key] = progress
        target = self.download_status_by_provider.get(plan_key, ("", "", ""))[2]
        self.download_status_by_provider[plan_key] = (
            progress.status.value,
            self.format_download_percent(progress),
            target or progress.message,
        )
        self.update_download_jobs_panel()
        if progress.status == JobStatus.COMPLETED:
            self.register_completed_download(plan_key, target)
        elif progress.status in {JobStatus.FAILED, JobStatus.CANCELLED}:
            provider_id = self.provider_id_for_plan_key(plan_key)
            log_event(
                "download_job_problem",
                progress.error or progress.message,
                level="error" if progress.status == JobStatus.FAILED else "warning",
                component="ui.download",
                context={"provider_id": provider_id, "job_id": progress.job_id, "status": progress.status.value, "target": target},
            )
            self.status_var.set(self.tr(f"下載 {progress.status.value}：{provider_id} {progress.error}", f"Download {progress.status.value}: {provider_id} {progress.error}"))

    def format_download_percent(self, progress: DownloadProgress) -> str:
        if progress.percent is not None:
            return f"{progress.percent:.1f}%"
        if progress.bytes_done:
            return f"{progress.bytes_done} bytes"
        return "0%"

    def update_download_jobs_panel(self) -> None:
        if not hasattr(self, "download_tree"):
            return
        for item in self.download_tree.get_children():
            self.download_tree.delete(item)
        plan_keys = list(dict.fromkeys([*self.selected_plan_keys(), *self.download_status_by_provider.keys()]))
        for plan_key in plan_keys:
            provider_id = self.provider_id_for_plan_key(plan_key)
            row = self.row_by_provider_id(provider_id)
            status, progress, target = self.download_status_by_provider.get(plan_key, ("planned", "0%", ""))
            self.download_tree.insert(
                "",
                END,
                iid=plan_key,
                values=(self.plan_item_label(plan_key, row), status, progress, self.import_status_label(plan_key, row), target),
            )

    def register_completed_download(self, plan_key: str, target: str) -> None:
        if plan_key in self.registered_completed_downloads:
            return
        self.registered_completed_downloads.add(plan_key)
        provider_id = self.provider_id_for_plan_key(plan_key)
        row = self.row_by_provider_id(provider_id)
        plan_entry = self.download_plan_entries_by_provider.get(plan_key, {})
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            if target:
                # 健康 manifest 走正式 asset registration；沒有 manifest 的舊路徑只保守記 file asset。
                manifest_path = Path(target).with_suffix(Path(target).suffix + ".manifest.json")
                if manifest_path.exists():
                    manifest = read_manifest(manifest_path)
                    repository.upsert_dataset_asset_manifest(manifest, manifest_path, status="ok")
                    repository.register_downloaded_manifest_asset(manifest, manifest_path)
                else:
                    install_id = repository.manage_provider_installation(
                        provider_id,
                        location=target,
                        notes="Downloaded by APIkeys_collection HTTP downloader.",
                    )
                    repository.register_installation_asset(
                        install_id,
                        asset_kind="file",
                        asset_name=Path(target).name,
                        asset_role="source",
                        source_format="unknown",
                        source_uri=str(plan_entry.get("download_url") or (self.download_url_for_row(row) if row else "")),
                        notes="Downloaded source asset.",
                    )
        finally:
            conn.close()
        self.reload_data()
        self.status_var.set(self.tr(f"下載完成：{row.name if row else provider_id}", f"Download completed: {row.name if row else provider_id}"))

    def import_supported_plan_results_from_ui(self) -> None:
        items = self.selected_plan_items()
        if not items:
            messagebox.showinfo(self.tr("下載計畫是空的", "Download plan is empty"), self.tr("請先加入至少一個資料集/資料源。", "Add at least one dataset/source first."))
            return
        supported: list[tuple[str, dict[str, object], str]] = []
        skipped: list[str] = []
        for plan_key, row, option in items:
            # 匯入前先確認 plan entry 宣告可支援，避免 UI 直接把任意檔案塞進 SQLite。
            label = self.plan_item_label(plan_key, row, option)
            entry = dict(self.download_plan_entries_by_provider.get(plan_key) or {})
            if not entry:
                built_entry, build_error = self.plan_entry_for_item(row, option, plan_key=plan_key)
                if built_entry is None:
                    skipped.append(f"{label}: {build_error}")
                    continue
                entry = built_entry
            import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
            if import_plan.get("status") != "supported_after_download":
                reason = str(import_plan.get("reason") or import_plan.get("status") or self.tr("目前不是 CSV/JSON/GeoJSON 可自動匯入項目", "This item is not an auto-importable CSV/JSON/GeoJSON item"))
                skipped.append(f"{label}: {reason}")
                continue
            supported.append((plan_key, entry, label))

        if not supported:
            messagebox.showinfo(
                self.tr("沒有可匯入項目", "No importable items"),
                self.tr("目前下載計畫中沒有已支援的 CSV/JSON/GeoJSON 匯入項目。", "The current plan has no supported CSV/JSON/GeoJSON import items.")
                + self.import_skipped_detail_message(skipped, limit=6),
            )
            return

        sqlite_path = state_file(CURATED_IMPORTS_NAME)
        existing_table_policy = self.ask_import_existing_table_policy()
        if existing_table_policy is None:
            return
        policy_hint = self.tr(
            f"\n\n同名資料表策略：{self.import_existing_table_policy_label(existing_table_policy)}",
            f"\n\nExisting table policy: {self.import_existing_table_policy_label(existing_table_policy)}",
        )
        confirmed = messagebox.askyesno(
            self.tr("匯入下載結果", "Import downloaded results"),
            self.tr(
                f"將把 {len(supported)} 個已支援項目匯入 SQLite：\n{sqlite_path}\n\n匯入前會先檢查 sidecar manifest 是否健康。",
                f"Import {len(supported)} supported items into SQLite:\n{sqlite_path}\n\nSidecar manifests will be verified before import.",
            )
            + policy_hint
            + self.import_skipped_detail_message(skipped),
        )
        if not confirmed:
            return

        self.status_var.set(self.tr(f"正在匯入 {len(supported)} 個下載結果到 SQLite...", f"Importing {len(supported)} downloaded results into SQLite..."))
        threading.Thread(
            target=self.import_supported_plan_results_worker,
            args=(supported, sqlite_path, existing_table_policy),
            daemon=True,
        ).start()

    def import_supported_plan_results_worker(
        self,
        entries: list[tuple[str, dict[str, object], str]],
        sqlite_path: Path,
        existing_table_policy: str,
    ) -> None:
        # UI worker 只負責 thread 與訊息映射；manifest/register/import 規則統一交給 ingestion_pipeline。
        messages: list[str] = []
        item_statuses: list[tuple[str, str, str]] = []
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            index_to_item = {index: (plan_key, label) for index, (plan_key, _entry, label) in enumerate(entries, start=1)}
            run = run_existing_download_import_slice(
                {"providers": [entry for _plan_key, entry, _label in entries]},
                repository,
                DownloadImportPipelineOptions(
                    import_supported_results=True,
                    import_sqlite_path=sqlite_path,
                    import_row_limit=0,
                    import_replace=existing_table_policy == "replace",
                    import_existing_table_policy=existing_table_policy,
                ),
            )
            imported = run.result.imported
            skipped = run.result.import_skipped
            failed = run.result.import_failed
            for item_status in run.item_statuses:
                plan_key, label = index_to_item.get(item_status.index, ("", item_status.provider_id))
                if item_status.status == "imported":
                    detail = item_status.detail or self.tr("已寫入 SQLite", "Written to SQLite")
                    item_statuses.append((plan_key, self.tr("已匯入", "Imported"), detail))
                elif item_status.status == "skipped":
                    item_statuses.append((plan_key, self.tr("略過", "Skipped"), item_status.detail))
                    messages.append(f"{label}: {item_status.detail}")
                else:
                    item_statuses.append((plan_key, self.tr("失敗", "Failed"), item_status.detail))
                    messages.append(f"{label}: {item_status.detail}")
            for error in run.result.errors:
                if error not in messages:
                    messages.append(error)
        finally:
            conn.close()

        self.root.after(
            0,
            lambda: self.finish_import_supported_plan_results(imported, skipped, failed, tuple(messages), tuple(item_statuses), sqlite_path, existing_table_policy),
        )

    def finish_import_supported_plan_results(
        self,
        imported: int,
        skipped: int,
        failed: int,
        messages: tuple[str, ...],
        item_statuses: tuple[tuple[str, str, str], ...],
        sqlite_path: Path,
        existing_table_policy: str,
    ) -> None:
        for plan_key, status, detail in item_statuses:
            self.import_status_by_plan_key[plan_key] = (status, detail)
        self.reload_data()
        self.update_download_plan_panel()
        summary = self.tr(
            f"匯入完成：成功 {imported}，略過 {skipped}，失敗 {failed}",
            f"Import finished: imported {imported}, skipped {skipped}, failed {failed}",
        )
        self.status_var.set(summary)
        log_event(
            "ui_import_supported_plan_results",
            summary,
            level="error" if failed else "info",
            component="ui.import",
            context={
                "imported": imported,
                "skipped": skipped,
                "failed": failed,
                "sqlite_path": str(sqlite_path),
                "existing_table_policy": existing_table_policy,
            },
        )
        detail = "\n".join(messages[:8])
        body = f"{summary}\n\nSQLite: {sqlite_path}\n{self.tr('同名資料表策略', 'Existing table policy')}: {self.import_existing_table_policy_label(existing_table_policy)}"
        if detail:
            body += f"\n\n{detail}"
        if failed:
            messagebox.showwarning(self.tr("匯入完成但有問題", "Import finished with issues"), body)
        else:
            messagebox.showinfo(self.tr("匯入完成", "Import finished"), body)

    def import_local_file_from_ui(self) -> None:
        # UI 手動匯入只處理使用者明確選取的一個檔案；不掃資料夾、不搬檔、不猜測來源。
        selected = filedialog.askopenfilename(
            parent=self.root,
            title=self.tr("選擇本機 CSV/JSON 檔", "Choose local CSV/JSON file"),
            filetypes=(
                (self.tr("支援的資料檔", "Supported data files"), "*.csv *.csv.gz *.json *.json.gz *.jsonl *.jsonl.gz *.ndjson *.ndjson.gz *.geojson *.geojson.gz"),
                ("CSV", "*.csv *.csv.gz"),
                ("JSON / JSONL / GeoJSON", "*.json *.json.gz *.jsonl *.jsonl.gz *.ndjson *.ndjson.gz *.geojson *.geojson.gz"),
                (self.tr("所有檔案", "All files"), "*.*"),
            ),
        )
        if not selected:
            return
        table_name = simpledialog.askstring(
            self.tr("匯入本機檔案", "Import local file"),
            self.tr(
                "目標資料表名稱（可留空，由檔名推導；若同名已存在會自動改名，不會覆蓋）：",
                "Target table name (optional; inferred from filename if blank; existing names are auto-renamed, not overwritten):",
            ),
            parent=self.root,
        )
        if table_name is None:
            return
        sqlite_path = state_file(CURATED_IMPORTS_NAME)
        confirmed = messagebox.askyesno(
            self.tr("匯入本機檔案", "Import local file"),
            self.tr(
                f"將為這個本機檔案建立 sidecar manifest，然後匯入 SQLite：\n{selected}\n\nSQLite：{sqlite_path}\n\n不會移動、刪除來源檔，也不會覆蓋既有資料表。",
                f"A sidecar manifest will be written for this local file, then imported into SQLite:\n{selected}\n\nSQLite: {sqlite_path}\n\nThe source file will not be moved/deleted and existing tables will not be overwritten.",
            ),
        )
        if not confirmed:
            return
        self.status_var.set(self.tr("正在匯入本機檔案到 SQLite...", "Importing local file into SQLite..."))
        threading.Thread(
            target=self.import_local_file_worker,
            args=(Path(selected), sqlite_path, table_name.strip()),
            daemon=True,
        ).start()

    def import_local_file_worker(self, input_path: Path, sqlite_path: Path, table_name: str) -> None:
        manifest_path = Path("")
        final_table = ""
        rows_imported = 0
        columns_count = 0
        provenance_review: dict[str, object] = {}
        error = ""
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            result = write_local_file_manifest_file(
                input_path,
                None,
                manifest_dir=state_file(MANUAL_IMPORTS_DIR_NAME),
            )
            provenance_review = result.provenance_review
            ensure_manual_local_file_provider(repository, DEFAULT_MANUAL_LOCAL_PROVIDER_ID)
            register_local_file_manifest_asset(repository, result.manifest_path)
            manifest = read_manifest(result.manifest_path)
            requested_table = table_name or table_name_for_manifest(manifest)
            final_table = unique_table_name(sqlite_path, requested_table)
            # 真正匯入仍走既有 importer；UI 只決定 safe table name 與 thread 邊界。
            if result.import_kind == "csv":
                import_result = import_csv_manifest_to_sqlite(
                    result.manifest_path,
                    sqlite_path,
                    repository,
                    table_name=final_table,
                    replace=False,
                )
            elif result.import_kind == "json":
                import_result = import_json_manifest_to_sqlite(
                    result.manifest_path,
                    sqlite_path,
                    repository,
                    table_name=final_table,
                    replace=False,
                )
            else:
                raise ValueError(f"Unsupported local import format: {result.source_format}")
            manifest_path = result.manifest_path
            final_table = import_result.table_name
            rows_imported = import_result.rows_imported
            columns_count = len(import_result.columns)
        except Exception as exc:
            error = local_file_import_error_message(exc)
            log_exception("ui_import_local_file_failed", exc, component="ui.import")
        finally:
            conn.close()
        self.root.after(
            0,
            lambda: self.finish_import_local_file(
                input_path,
                manifest_path,
                sqlite_path,
                final_table,
                rows_imported,
                columns_count,
                provenance_review,
                error,
            ),
        )

    def finish_import_local_file(
        self,
        input_path: Path,
        manifest_path: Path,
        sqlite_path: Path,
        table_name: str,
        rows_imported: int,
        columns_count: int,
        provenance_review: dict[str, object],
        error: str,
    ) -> None:
        if error:
            self.status_var.set(self.tr(f"本機檔案匯入失敗：{error}", f"Local file import failed: {error}"))
            messagebox.showerror(self.tr("本機檔案匯入失敗", "Local file import failed"), error)
            return
        self.reload_data()
        summary = self.tr(
            f"本機檔案已匯入：{table_name}，{rows_imported} rows / {columns_count} columns",
            f"Local file imported: {table_name}, {rows_imported} rows / {columns_count} columns",
        )
        self.status_var.set(summary)
        log_event(
            "ui_import_local_file_completed",
            summary,
            component="ui.import",
            context={
                "input_path": str(input_path),
                "manifest_path": str(manifest_path),
                "sqlite_path": str(sqlite_path),
                "table_name": table_name,
                "rows_imported": rows_imported,
                "columns_count": columns_count,
                "provider_id": DEFAULT_MANUAL_LOCAL_PROVIDER_ID,
                "provenance_review": provenance_review,
            },
        )
        review_message = local_file_provenance_review_message(provenance_review)
        message = self.tr(
            f"{summary}\n\nManifest：{manifest_path}\nSQLite：{sqlite_path}\n\n來源檔未被移動或刪除。",
            f"{summary}\n\nManifest: {manifest_path}\nSQLite: {sqlite_path}\n\nThe source file was not moved or deleted.",
        )
        if review_message:
            message += f"\n\n{review_message}"
        messagebox.showinfo(
            self.tr("本機檔案已匯入", "Local file imported"),
            message,
        )

    def remove_selected_from_plan(self) -> None:
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showinfo("尚未選取", "請先在下載計畫中選取一個資料源。")
            return
        plan_key = str(selection[0])
        provider_id = self.provider_id_for_plan_key(plan_key)
        row = self.row_by_provider_id(provider_id)
        label = self.plan_item_label(plan_key, row)
        self.plan_version_by_provider.pop(plan_key, None)
        self.plan_provider_by_key.pop(plan_key, None)
        self.download_plan_entries_by_provider.pop(plan_key, None)
        self.import_status_by_plan_key.pop(plan_key, None)
        if plan_key == provider_id or not self.version_plan_keys_for_provider(provider_id):
            self.selected.setdefault(provider_id, BooleanVar(value=False)).set(False)
        self.render_table()
        self.status_var.set(f"已移出下載計畫：{label}")

    def clear_download_plan(self) -> None:
        if not self.selected_provider_ids():
            self.status_var.set("下載計畫已經是空的。")
            return
        for var in self.selected.values():
            var.set(False)
        self.plan_version_by_provider.clear()
        self.plan_provider_by_key.clear()
        self.download_plan_entries_by_provider.clear()
        self.import_status_by_plan_key.clear()
        self.render_table()
        self.status_var.set("已清空下載計畫。")

    def row_by_provider_id(self, provider_id: str) -> ProviderRow | None:
        return next((row for row in self.rows if row.provider_id == provider_id), None)

    def update_detail_panel(self, row: ProviderRow | None) -> None:
        if row is None:
            self.detail_star_var.set("☆")
            self.detail_title_var.set("選取一個資料源")
            self.detail_owner_var.set("像 Steam 商店頁一樣查看用途、狀態與官方入口。")
            self.detail_category_var.set("")
            self.detail_auth_var.set("")
            self.detail_status_var.set("")
            self.detail_scope_var.set("")
            self.detail_urls_var.set("")
            self.set_preview_text(self.tr("OpenGraph / 官方頁面 metadata 擷取後，預覽會顯示在這裡。", "Preview metadata will appear here after OpenGraph/official-page extraction."))
            self.set_ai_summary_text(self.ai_summary_placeholder)
            return

        self.detail_star_var.set(row.star_label)
        self.detail_title_var.set(row.name)
        self.detail_owner_var.set(row.owner)
        self.detail_category_var.set(row.category_label)
        access = row.auth_type
        if row.key_env_var:
            access = f"{access}\n{self.tr('環境變數', 'Env')}: {row.key_env_var}"
        self.detail_auth_var.set(access)
        self.detail_status_var.set(
            f"{self.tr('遠端', 'Remote')}: {row.status_label} / {row.update_label}\n"
            f"{self.tr('本地', 'Local')}: {row.local_label}\n"
            f"{self.tr('已發現資料集', 'Discovered datasets')}: {len(self.datasets_by_provider.get(row.provider_id, []))}\n"
            f"{self.tr('安裝 ID', 'Install ID')}: {row.install_id or self.tr('未納管', 'not managed')}\n"
            f"{self.tr('下載', 'Download')}: "
            f"{self.localized_download_label(row.download_eligibility)} - "
            f"{self.localized_download_reason(row.download_eligibility)}"
        )
        self.detail_scope_var.set(row.geographic_scope)
        links = [
            f"{self.tr('文件', 'Docs')}: {row.docs_url}" if row.docs_url else "",
            f"API: {row.api_base_url}" if row.api_base_url else "",
            f"{self.tr('註冊', 'Signup')}: {row.signup_url}" if row.signup_url else "",
        ]
        self.detail_urls_var.set("\n".join(link for link in links if link))
        self.set_preview_text(self.provider_description(row))
        self.set_ai_summary_text(row.notes or self.tr("尚未產生 AI 描述。", "No AI description generated yet."))

    def provider_description(self, row: ProviderRow) -> str:
        if row.notes:
            return row.notes
        category_hint = row.category_label or "data"
        if self.ui_language != "en-US":
            return (
                f"{row.name} 是由 {row.owner} 提供的官方 {category_hint} 資料來源。"
                "之後擷取官方 metadata 後，這裡會顯示更完整的描述與預覽。"
            )
        return (
            f"{row.name} is an official {category_hint} source from {row.owner}. "
            "A richer description and visual preview will be populated from official metadata pages."
        )

    def set_preview_text(self, text: str) -> None:
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", END)
        self.preview_box.insert("1.0", text)
        self.preview_box.configure(state="disabled")

    def set_ai_summary_text(self, text: str) -> None:
        self.ai_summary_box.configure(state="normal")
        self.ai_summary_box.delete("1.0", END)
        self.ai_summary_box.insert("1.0", text)
        self.ai_summary_box.configure(state="disabled")

    def add_provider(self) -> None:
        dialog = ProviderEditorDialog(self.root)
        if dialog.result is None:
            return
        self.save_provider(dialog.result)
        self.active_provider_id = dialog.result.provider_id
        self.reload_data()
        self.open_detail_drawer()
        self.status_var.set(f"已新增資料源：{dialog.result.name}")

    def edit_active_provider(self) -> None:
        row = self.row_by_provider_id(self.active_provider_id)
        if row is None:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        dialog = ProviderEditorDialog(self.root, row)
        if dialog.result is None:
            return
        self.save_provider(dialog.result)
        self.active_provider_id = dialog.result.provider_id
        self.reload_data()
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.status_var.set(f"已更新資料源：{dialog.result.name}")

    def save_provider(self, provider: core.Provider) -> None:
        conn = self._connect()
        try:
            core.ApiCatalogRepository(conn).upsert_provider(provider)
        finally:
            conn.close()

    def provider_from_row(self, row: ProviderRow, notes: str | None = None) -> core.Provider:
        return core.Provider(
            provider_id=row.provider_id,
            name=row.name,
            owner=row.owner,
            categories=row.categories,
            geographic_scope=row.geographic_scope,
            docs_url=row.docs_url,
            api_base_url=row.api_base_url,
            signup_url=row.signup_url,
            auth_type=row.auth_type,
            key_env_var=row.key_env_var,
            notes=row.notes if notes is None else notes,
        )

    def open_database_tool(self) -> None:
        try:
            profile = core.open_database_client()
        except Exception as exc:
            log_exception(
                "open_database_tool_failed",
                exc,
                component="ui.database",
                context={"active_provider_id": self.active_provider_id},
            )
            messagebox.showerror(
                "無法開啟資料庫工具",
                (
                    f"{exc}\n\n"
                    "請複製 config/launcher_integrations.example.json 為 "
                    "launcher_integrations.local.json，並調整你的 MySQL Workbench、DBeaver "
                    "或其他資料庫工具路徑。"
                ),
            )
            self.status_var.set(f"資料庫工具啟動失敗：{exc}")
            return
        self.status_var.set(f"已開啟資料庫工具：{profile.label}")

    def open_database_settings(self) -> None:
        DatabaseClientSettingsDialog(self.root)
        profile = core.active_database_client()
        if profile:
            self.status_var.set(f"目前預設資料庫工具：{profile.label}")

    def open_integration_config_file(self) -> None:
        core.ensure_local_integration_config()
        reveal_path_in_file_manager(core.local_integrations_path())
        self.status_var.set(self.tr("已在檔案管理器顯示本機整合設定檔。", "Revealed local integration config in the file manager."))

    def open_doc_file(self, name: str) -> None:
        path = PROJECT_ROOT / "docs" / name
        if not path.exists():
            messagebox.showinfo(self.tr("找不到文件", "Document not found"), str(path))
            return
        webbrowser.open(path.as_uri())

    def open_developer_cli(self) -> None:
        DeveloperCliDialog(self)

    def open_ui_language_settings(self) -> None:
        UiLanguageSettingsDialog(self)

    def open_ai_model_settings(self) -> None:
        AiModelSettingsDialog(self)

    def api_key_env_for_profile(self, profile: core.AiSummaryProfile) -> str:
        return default_api_key_env(profile)

    def profile_has_cloud_credential(self, profile: core.AiSummaryProfile) -> bool:
        load_saved_ai_api_keys([profile])
        api_key_env = self.api_key_env_for_profile(profile)
        if api_key_env and os.environ.get(api_key_env, "").strip():
            return True
        oauth_config = oauth_device_config_from_profile(profile)
        if oauth_config is None:
            return False
        status, _message = oauth_token_status(oauth_config.token_store, label=profile.label)
        return status == "ready"

    def ai_profile_login_status(self, profile: core.AiSummaryProfile) -> str:
        if profile.kind == "ollama":
            return self.tr("本機服務", "Local service")
        api_key_env = self.api_key_env_for_profile(profile)
        if api_key_env and os.environ.get(api_key_env, "").strip():
            return self.tr(f"API key 已載入：{api_key_env}", f"API key ready: {api_key_env}")
        saved_status, _saved_message = saved_ai_api_key_status(profile)
        if saved_status == "stored":
            return self.tr(f"API key 已保存：{api_key_env}", f"API key saved: {api_key_env}")
        oauth_config = oauth_device_config_from_profile(profile)
        if oauth_config is not None:
            if not oauth_config.enabled:
                return self.tr("OAuth 已停用", "OAuth disabled")
            status, _message = oauth_token_status(oauth_config.token_store, label=profile.label)
            if status == "ready":
                return self.tr(f"OAuth 已登入：{status}", f"OAuth signed in: {status}")
        if api_key_env:
            return self.tr(f"需要 API key：{api_key_env}", f"Needs API key: {api_key_env}")
        return self.tr("不需登入", "No login")

    def data_store_next_action_message(self, result: object) -> str:
        return data_store_next_action_message_text(result, self.tr)

    def open_data_store_connection_settings(self) -> None:
        DataStoreConnectionSettingsDialog(self)

    def open_dataset_candidate_review_panel(self) -> None:
        DatasetCandidateReviewDialog(self)

    def open_provider_candidate_review_panel(self) -> None:
        path = state_file("provider_candidates.ui.json")
        if not path.exists():
            messagebox.showinfo(
                self.tr("Provider 候選", "Provider candidates"),
                self.tr("尚未產生 provider candidate review JSON。請先執行 provider 候選探索。", "No provider candidate review JSON exists yet. Run \"Discover provider candidates\" first."),
            )
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            messagebox.showerror(
                self.tr("Provider 候選", "Provider candidates"),
                self.tr(f"無法讀取 provider 候選 JSON：{exc}", f"Could not read provider candidate JSON: {exc}"),
            )
            return
        candidates = [item for item in payload.get("candidates", []) if isinstance(item, dict)] if isinstance(payload, dict) else []
        ProviderCandidateReviewDialog(self, path, candidates)

    def provider_discovery_message(self, payload: object, output_path: Path) -> str:
        # Provider discovery 是 catalog 入口審查，不是安裝或納管；訊息必須把 review JSON 路徑講清楚。
        data = payload if isinstance(payload, dict) else {}
        candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
        lines = [
            self.tr(
                f"Provider 候選發現完成：{data.get('candidate_count', len(candidates))} 筆。",
                f"Provider discovery complete: {data.get('candidate_count', len(candidates))} candidates.",
            ),
            self.tr(
                "這是 metadata-only review JSON；尚未寫入正式 catalog，也沒有抓取 API key 或登入內容。",
                "This is a metadata-only review JSON; the official catalog was not changed and no API keys or login content were collected.",
            ),
        ]
        if candidates:
            lines.extend(["", self.tr("候選預覽：", "Candidate preview:")])
            for item in candidates[:5]:
                if not isinstance(item, dict):
                    continue
                provider_id = item.get("provider_id") or "-"
                confidence = item.get("confidence", "-")
                lines.append(f"{provider_id}: confidence={confidence}")
        lines.extend(["", self.tr(f"Review JSON：{output_path}", f"Review JSON: {output_path}")])
        return "\n".join(lines)

    def discover_provider_candidates_from_ui(self) -> None:
        self.status_var.set(self.tr("正在發現 provider 候選...", "Discovering provider candidates..."))

        def worker() -> None:
            output_path = state_file("provider_candidates.ui.json")
            try:
                seed_path = catalog_file(DEFAULT_SEEDS_NAME)
                local_seed_path = local_config_file(LOCAL_SEEDS_NAME)
                seeds = load_all_discovery_seeds(seed_path, local_seed_path)
                conn = self._connect()
                try:
                    existing = {provider.provider_id for provider in core.load_providers(conn)}
                finally:
                    conn.close()
                candidates = discover_provider_candidates(seeds, existing_provider_ids=existing, timeout=12.0)
                payload = {
                    "schema_version": 1,
                    "created_at": utc_now_iso(),
                    "role": "reviewable provider/source candidates; metadata only; no API secrets collected",
                    "candidate_count": len(candidates),
                    "candidates": [candidate.to_dict() for candidate in candidates],
                }
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                log_event(
                    "provider_candidates_discovered",
                    "Provider candidate review JSON written from Tk UI.",
                    component="ui.provider_discovery",
                    context={
                        "candidate_count": len(candidates),
                        "output_path": str(output_path),
                    },
                )
            except Exception as exc:
                log_exception(
                    "provider_candidate_discovery_failed",
                    exc,
                    component="ui.provider_discovery",
                )
                self.root.after(0, lambda: messagebox.showerror(self.tr("Provider 候選發現失敗", "Provider discovery failed"), str(exc)))
                self.root.after(0, lambda: self.status_var.set(self.tr(f"Provider 候選發現失敗：{exc}", f"Provider discovery failed: {exc}")))
                return

            def finish() -> None:
                message = self.provider_discovery_message(payload, output_path)
                status = self.tr(
                    f"Provider 候選發現完成：{len(candidates)} 筆",
                    f"Provider discovery complete: {len(candidates)} candidates",
                )
                self.status_var.set(status)
                messagebox.showinfo(self.tr("Provider 候選", "Provider candidates"), message)

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def crawler_next_action_label(self, action: str) -> str:
        return crawler_next_action_label_text(action, self.tr)

    def crawler_audit_summary_lines(self, audit_summary: object, *, limit: int = 6) -> list[str]:
        # audit_summary 是後端提供的穩定總表；UI 只做 bounded 摘要，避免使用者只能從逐 source 明細猜整體狀態。
        if not isinstance(audit_summary, dict):
            return []
        def summary_int(key: str) -> int:
            try:
                return int(audit_summary.get(key) or 0)
            except (TypeError, ValueError):
                return 0

        status = str(audit_summary.get("status") or "-")
        source_count = summary_int("source_count")
        candidate_count = summary_int("candidate_count")
        problem_source_count = summary_int("problem_source_count")
        next_action = str(audit_summary.get("next_action") or "")
        lines = [
            self.tr(
                f"整體狀態：{status}；來源 {source_count}；候選 {candidate_count}；問題來源 {problem_source_count}",
                f"Overall: {status}; sources {source_count}; candidates {candidate_count}; problem sources {problem_source_count}",
            )
        ]
        if next_action:
            lines.append(
                self.tr(
                    f"總體下一步：{self.crawler_next_action_label(next_action)}",
                    f"Overall next step: {self.crawler_next_action_label(next_action)}",
                )
            )
        for label, values in (
            (self.tr("Warning 分組", "Warning groups"), audit_summary.get("by_warning_code")),
            (self.tr("下一步分組", "Next-action groups"), audit_summary.get("by_next_action")),
        ):
            if not isinstance(values, dict) or not values:
                continue
            preview = ", ".join(f"{key}={value}" for key, value in sorted(values.items())[:3])
            lines.append(f"{label}: {preview}")
        problem_sources = audit_summary.get("problem_sources")
        if isinstance(problem_sources, list) and problem_sources:
            # 問題 source 只列前幾個 id；完整 error/warning 仍在下面的逐 source 明細與 JSON audit。
            source_ids = [
                str(item.get("source_id") or "-")
                for item in problem_sources[:3]
                if isinstance(item, dict)
            ]
            if source_ids:
                lines.append(self.tr(f"優先檢查來源：{', '.join(source_ids)}", f"Review first: {', '.join(source_ids)}"))
        return lines[:limit]

    def crawler_audit_issue_lines(self, source_results: object, *, limit: int = 8) -> list[str]:
        # 彈窗空間有限，所以這裡只做 bounded preview；完整 audit 仍由 CLI/JSON 與 candidate review 流程保留。
        lines: list[str] = []
        for item in source_results:
            source_id = str(getattr(item, "source_id", "") or "-")
            error = str(getattr(item, "error", "") or "")
            warnings = tuple(getattr(item, "warnings", ()) or ())
            next_action = str(getattr(item, "next_action", "") or "")
            if not error and not warnings:
                continue
            if next_action:
                lines.append(
                    self.tr(
                        f"{source_id}: 下一步：{self.crawler_next_action_label(next_action)}",
                        f"{source_id}: next step: {self.crawler_next_action_label(next_action)}",
                    )
                )
            if error:
                lines.append(f"{source_id}: {error}")
            for warning in warnings:
                lines.append(f"{source_id}: {warning}")
            if len(lines) >= limit:
                break
        return lines[:limit]

    def discover_dataset_candidates_from_ui(self) -> None:
        selected_provider_ids = tuple(self.selected_provider_ids())
        scope = (
            self.tr(f"{len(selected_provider_ids)} 個選取資料源", f"{len(selected_provider_ids)} selected sources")
            if selected_provider_ids
            else self.tr("所有已設定 crawler 的資料源", "all configured crawler sources")
        )
        self.status_var.set(self.tr(f"正在並行發現資料集候選：{scope}", f"Discovering dataset candidates concurrently: {scope}"))
        thread = threading.Thread(target=self._dataset_candidate_discovery_worker, args=(selected_provider_ids,), daemon=True)
        thread.start()

    def _dataset_candidate_discovery_worker(self, provider_ids: tuple[str, ...]) -> None:
        try:
            sources = core.load_dataset_discovery_sources(catalog_file(core.DEFAULT_DATASET_DISCOVERY_SOURCES_NAME))
            if provider_ids:
                wanted = set(provider_ids)
                sources = [source for source in sources if source.provider_id in wanted]
            result = core.crawl_dataset_sources(
                sources,
                core.DatasetCrawlOptions(
                    timeout=12.0,
                    max_results_override=100,
                    full_crawl=True,
                    max_pages=0,
                    max_workers=4,
                ),
            )
            conn = self._connect()
            try:
                repository = core.ApiCatalogRepository(conn)
                existing_provider_ids = {provider.provider_id for provider in core.load_providers(conn)}
                upserted = 0
                for candidate in result.candidates:
                    if candidate.dataset.provider_id not in existing_provider_ids:
                        continue
                    repository.upsert_dataset(core.dataset_with_candidate_metadata(candidate))
                    upserted += 1
            finally:
                conn.close()
        except Exception as exc:
            log_exception(
                "dataset_candidate_discovery_failed",
                exc,
                component="ui.dataset_discovery",
                context={"provider_ids": provider_ids},
            )
            self.root.after(0, lambda: messagebox.showerror(self.tr("資料集發現失敗", "Dataset discovery failed"), str(exc)))
            self.root.after(0, lambda: self.status_var.set(self.tr(f"資料集發現失敗：{exc}", f"Dataset discovery failed: {exc}")))
            return

        def finish() -> None:
            next_action_label = self.crawler_next_action_label(result.next_action)
            message = self.tr(
                f"資料集候選發現完成：新增/更新 {upserted} 筆；錯誤來源 {result.error_count}；警告 {result.warning_count}；重複 {result.duplicate_count}；下一步：{next_action_label}",
                f"Dataset discovery complete: upserted {upserted}; source errors {result.error_count}; warnings {result.warning_count}; duplicates {result.duplicate_count}; next step: {next_action_label}",
            )
            self.status_var.set(message)
            self.reload_data()
            self.status_var.set(message)
            if result.error_count or result.warning_count:
                summary_lines = self.crawler_audit_summary_lines(result.audit_summary)
                issue_lines = self.crawler_audit_issue_lines(result.source_results)
                messagebox.showwarning(
                    self.tr("部分 crawler 需要檢查", "Some crawlers need review"),
                    message
                    + "\n\n"
                    + self.tr("來源審核摘要：", "Source audit summary:")
                    + "\n"
                    + "\n".join(summary_lines)
                    + "\n\n"
                    + self.tr("逐來源明細：", "Source details:")
                    + "\n"
                    + "\n".join(issue_lines),
                )
            self.open_dataset_candidate_review_panel()

        self.root.after(0, finish)

    def local_discovery_audit_message(self, payload: object, audit_path: Path) -> str:
        # 本機草稿 promotion 是 catalog 前的安全閘；UI 摘要要清楚標示 dry-run，避免被誤會已正式寫入。
        data = payload if isinstance(payload, dict) else {}
        audit = data.get("audit") if isinstance(data.get("audit"), dict) else {}
        summary = audit.get("audit_summary") if isinstance(audit.get("audit_summary"), dict) else {}
        lines = [
            self.tr(
                "本機 discovery 草稿審核完成（dry-run，未寫入正式 catalog）。",
                "Local discovery draft audit completed (dry-run; official catalog was not changed).",
            ),
            self.tr(
                f"審核來源 {data.get('audited_source_count', 0)}；可提升 provider {data.get('promoted_provider_count', 0)}；可提升 source {data.get('promoted_source_count', 0)}；略過 {data.get('skipped_count', 0)}",
                f"Audited sources {data.get('audited_source_count', 0)}; promotable providers {data.get('promoted_provider_count', 0)}; promotable sources {data.get('promoted_source_count', 0)}; skipped {data.get('skipped_count', 0)}",
            ),
        ]
        summary_lines = self.crawler_audit_summary_lines(summary)
        if summary_lines:
            lines.extend(["", self.tr("Crawler 審核摘要：", "Crawler audit summary:"), *summary_lines])
        skipped = data.get("skipped")
        if isinstance(skipped, list) and skipped:
            lines.extend(["", self.tr("略過來源：", "Skipped sources:")])
            for item in skipped[:4]:
                if not isinstance(item, dict):
                    continue
                lines.append(f"{item.get('source_id') or '-'}: {item.get('reason') or '-'}")
        lines.extend(["", self.tr(f"Audit JSON：{audit_path}", f"Audit JSON: {audit_path}")])
        return "\n".join(lines)

    def audit_local_discovery_from_ui(self) -> None:
        self.status_var.set(self.tr("正在審核本機 discovery 草稿（dry-run）...", "Auditing local discovery drafts (dry-run)..."))

        def worker() -> None:
            output_path = state_file("local_discovery_audit.ui.json")
            try:
                result = promote_local_discovery_catalog(
                    local_provider_seed_path=local_config_file(LOCAL_SEEDS_NAME),
                    local_dataset_source_path=local_config_file(LOCAL_DATASET_DISCOVERY_SOURCES_NAME),
                    provider_catalog_path=catalog_file(PROVIDER_CATALOG_NAME),
                    dataset_source_catalog_path=catalog_file(core.DEFAULT_DATASET_DISCOVERY_SOURCES_NAME),
                    options=core.DatasetCrawlOptions(
                        timeout=12.0,
                        max_results_override=25,
                        full_crawl=False,
                        max_pages=1,
                        max_workers=4,
                    ),
                    dry_run=True,
                )
                payload = result.to_dict()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                log_event(
                    "local_discovery_audit_completed",
                    "Local discovery promotion dry-run audit completed.",
                    component="ui.dataset_discovery",
                    context={
                        "audited_source_count": result.audited_source_count,
                        "skipped_count": result.skipped_count,
                        "audit_issue_count": payload.get("audit", {}).get("audit_issue_count", 0),
                        "output_path": str(output_path),
                    },
                )
            except Exception as exc:
                log_exception(
                    "local_discovery_audit_failed",
                    exc,
                    component="ui.dataset_discovery",
                )
                self.root.after(0, lambda: messagebox.showerror(self.tr("本機 discovery 審核失敗", "Local discovery audit failed"), str(exc)))
                self.root.after(0, lambda: self.status_var.set(self.tr(f"本機 discovery 審核失敗：{exc}", f"Local discovery audit failed: {exc}")))
                return

            def finish() -> None:
                message = self.local_discovery_audit_message(payload, output_path)
                status = self.tr(
                    f"本機 discovery 審核完成：來源 {result.audited_source_count}；略過 {result.skipped_count}",
                    f"Local discovery audit complete: sources {result.audited_source_count}; skipped {result.skipped_count}",
                )
                self.status_var.set(status)
                audit_issue_count = int(payload.get("audit", {}).get("audit_issue_count", 0))
                if result.audited_source_count == 0:
                    messagebox.showinfo(self.tr("本機 discovery 審核", "Local discovery audit"), message)
                elif result.skipped_count or audit_issue_count:
                    messagebox.showwarning(self.tr("本機 discovery 審核", "Local discovery audit"), message)
                else:
                    messagebox.showinfo(self.tr("本機 discovery 審核", "Local discovery audit"), message)

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def show_environment_checks(self) -> None:
        StartupEnvironmentChecksDialog(self)

    def show_event_logs(self) -> None:
        RecentEventLogsDialog(self)

    def open_google_gemini_settings(self) -> None:
        GoogleGeminiSettingsDialog(self)

    def generate_active_summary(self) -> None:
        row = self.row_by_provider_id(self.active_provider_id)
        if row is None:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        profile = next((item for item in core.ai_summary_profiles() if item.id == self.selected_ai_profile_id), None)
        if profile is None:
            messagebox.showinfo(
                "尚未設定 AI 摘要",
                (
                    "請在「整合 > AI 輔助模型選擇」選擇要使用的模型。"
                    "預設建議可先用本機 Ollama，免登入也不需要雲端 API key。"
                ),
            )
            return
        if not profile.enabled:
            try:
                profile = core.set_active_ai_profile(profile.id)
            except Exception as exc:
                messagebox.showerror("AI 摘要設定失敗", str(exc))
                return
        if profile.kind != "ollama" and not self.profile_has_cloud_credential(profile):
            if not self.configure_ai_api_key_session(profile.id, parent=self.root):
                self.status_var.set("AI 摘要尚未啟動：需要 API key 或已保存的登入 token。")
                return
            profile = next((item for item in core.ai_summary_profiles() if item.id == profile.id), profile)
        self.selected_ai_profile_id = profile.id
        self.status_var.set(f"正在使用 {profile.label} 產生 {row.name} 的說明...")
        thread = threading.Thread(target=self._summary_worker, args=(row.provider_id, profile.id), daemon=True)
        thread.start()

    def _summary_worker(self, provider_id: str, profile_id: str) -> None:
        saved_summary = False
        try:
            conn = self._connect()
            try:
                repository = core.ApiCatalogRepository(conn)
                providers = repository.load_providers([provider_id])
                if not providers:
                    raise RuntimeError(f"Unknown provider_id: {provider_id}")
                provider = providers[0]
                summary = core.generate_provider_summary(provider, profile_id=profile_id)
                if not provider.notes:
                    provider = core.Provider(
                        provider_id=provider.provider_id,
                        name=provider.name,
                        owner=provider.owner,
                        categories=provider.categories,
                        geographic_scope=provider.geographic_scope,
                        docs_url=provider.docs_url,
                        api_base_url=provider.api_base_url,
                        signup_url=provider.signup_url,
                        auth_type=provider.auth_type,
                        key_env_var=provider.key_env_var,
                        license_url=provider.license_url,
                        terms_url=provider.terms_url,
                        notes=summary,
                        crawl_urls=provider.crawl_urls,
                    )
                    repository.upsert_provider(provider)
                    saved_summary = True
            finally:
                conn.close()
        except Exception as exc:
            error = str(exc)
            log_exception(
                "ai_summary_failed",
                exc,
                component="ui.ai_summary",
                context={"provider_id": provider_id, "profile_id": profile_id},
            )
            self.root.after(0, lambda: messagebox.showerror("AI 摘要失敗", error))
            self.root.after(0, lambda: self.status_var.set(f"AI 摘要失敗：{error}"))
            return

        def update_ui() -> None:
            if saved_summary:
                self.reload_data()
                row = self.row_by_provider_id(provider_id)
                self.set_ai_summary_text(summary)
                self.status_var.set(f"AI 說明已寫入：{row.name if row else provider_id}")
            else:
                self.set_ai_summary_text(summary)
                self.status_var.set("AI 摘要已產生；既有描述未被覆蓋。")

        self.root.after(0, update_ui)

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

    def current_planned_entries(self) -> tuple[list[dict[str, object]], bool]:
        items = self.selected_plan_items()
        planned_entries: list[dict[str, object]] = []
        has_dataset_entries = False
        for plan_key, row, option in items:
            entry, build_error = self.plan_entry_for_item(row, option, plan_key=plan_key)
            if entry is None:
                entry = core.provider_plan_entry(self.provider_from_row(row))
                if option:
                    entry["dataset_version"] = option.to_plan_metadata()
                entry["plan_status"] = "metadata_missing"
                entry["plan_error"] = build_error
            if option:
                has_dataset_entries = True
            planned_entries.append(entry)
        return planned_entries, has_dataset_entries

    def current_download_plan_payload(self) -> tuple[dict[str, object], list[tuple[str, ProviderRow, core.DatasetVersionOption | None]]]:
        items = self.selected_plan_items()
        plan_name = self.plan_name_var.get().strip() or "Untitled download plan"
        planned_entries, has_dataset_entries = self.current_planned_entries()
        if has_dataset_entries:
            payload = core.build_dataset_download_plan(planned_entries, plan_name=plan_name)
        else:
            payload = core.build_download_plan([], plan_name=plan_name)
            payload["providers"] = planned_entries
            payload["summary"]["provider_count"] = len({str(entry.get("provider_id") or "") for entry in planned_entries if isinstance(entry, dict)})
        payload["summary"]["plan_item_count"] = len(planned_entries)
        return payload, items

    def resolve_adapter_plan_from_ui(self) -> None:
        if not self.selected_plan_items():
            messagebox.showinfo(self.tr("下載計畫是空的", "Download plan is empty"), self.tr("請先把資料集或資料源加入下載計畫。", "Add datasets or sources to the download plan first."))
            return
        payload, items = self.current_download_plan_payload()
        index_to_plan_key = {index: plan_key for index, (plan_key, _row, _option) in enumerate(items, start=1)}
        index_has_version = {index: option is not None for index, (_plan_key, _row, option) in enumerate(items, start=1)}
        resolved_payload, result = core.resolve_adapter_review_plan_payload(payload, downloads_root=DOWNLOADS_DIR)
        output_path = state_file(RESOLVED_DOWNLOAD_PLAN_NAME)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(resolved_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        resolved_entries = [
            entry
            for entry in resolved_payload.get("providers", [])
            if isinstance(entry, dict) and isinstance(entry.get("adapter_resolution"), dict)
        ]
        resolved_original_indices = {
            int((entry.get("adapter_resolution") or {}).get("original_plan_index"))
            for entry in resolved_entries
            if isinstance(entry.get("adapter_resolution"), dict) and str((entry.get("adapter_resolution") or {}).get("original_plan_index") or "").isdigit()
        }
        for original_index in resolved_original_indices:
            original_key = index_to_plan_key.get(original_index, "")
            if original_key and index_has_version.get(original_index):
                self.plan_version_by_provider.pop(original_key, None)
                self.plan_provider_by_key.pop(original_key, None)
                self.download_plan_entries_by_provider.pop(original_key, None)
                self.import_status_by_plan_key.pop(original_key, None)

        added = 0
        for entry in resolved_entries:
            provider_id = str(entry.get("provider_id") or "").strip()
            if not provider_id or self.row_by_provider_id(provider_id) is None:
                continue
            option = self.version_option_from_plan_entry(entry)
            if option is None:
                continue
            plan_key = self.plan_key_for_resolved_entry(entry)
            self.plan_version_by_provider[plan_key] = option
            self.plan_provider_by_key[plan_key] = provider_id
            self.download_plan_entries_by_provider[plan_key] = dict(entry)
            self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
            added += 1

        self.render_table()
        summary = self.tr(
            f"Adapter 計畫解析完成：新增 {added} 個可下載項目；仍需 review {result.unresolved_review_entries} 個。",
            f"Adapter plan resolved: added {added} direct items; {result.unresolved_review_entries} still need review.",
        )
        self.status_var.set(summary)
        if added:
            messagebox.showinfo(
                self.tr("解析完成", "Resolve finished"),
                self.tr(
                    f"{summary}\n\n已同步到下方下載計畫，也已輸出：\n{output_path}\n\n接下來可以按「開始」下載新項目。",
                    f"{summary}\n\nThe download plan panel was updated and a resolved plan was written to:\n{output_path}\n\nYou can click Start to download the new items.",
                ),
            )
        else:
            detail = "\n".join(result.warnings[:5])
            message = self.tr(
                f"目前沒有找到可以自動轉成 direct download 的 resource。\n\n已輸出檢查結果：\n{output_path}",
                f"No resource could be safely promoted to direct download.\n\nA checked plan was written to:\n{output_path}",
            )
            if detail:
                message += f"\n\n{detail}"
            messagebox.showinfo(self.tr("沒有可自動解析項目", "No automatic resolution"), message)

    def add_download_plan_entries_from_file(self, plan_path: Path) -> int:
        # 將 adapter 產生的 JSON plan 接回現有下載計畫模型，避免 UI 和 CLI 各自維護一套 plan schema。
        payload = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        added = self.add_download_plan_entries_from_payload(payload)
        self.render_table()
        self.update_download_plan_panel()
        return added

    def add_download_plan_entries_from_payload(self, payload: dict[str, object]) -> int:
        # 從既有 plan JSON 還原 UI 下載計畫時，只接受可對應到 catalog provider 的 direct entries。
        added = 0
        raw_entries = payload.get("providers") if isinstance(payload.get("providers"), list) else []
        for entry in raw_entries:
            if not isinstance(entry, dict):
                continue
            provider_id = str(entry.get("provider_id") or "").strip()
            if not provider_id or self.row_by_provider_id(provider_id) is None:
                continue
            option = self.version_option_from_plan_entry(entry)
            if option is None:
                continue
            plan_key = self.plan_key_for_resolved_entry(entry)
            self.plan_version_by_provider[plan_key] = option
            self.plan_provider_by_key[plan_key] = provider_id
            self.download_plan_entries_by_provider[plan_key] = dict(entry)
            self.import_status_by_plan_key.pop(plan_key, None)
            self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
            self.active_provider_id = provider_id
            added += 1
        return added

    def version_option_from_plan_entry(self, entry: dict[str, object]) -> core.DatasetVersionOption | None:
        version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
        download_url = str(entry.get("download_url") or version_meta.get("download_url") or "").strip()
        if not download_url:
            return None
        metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
        return core.DatasetVersionOption(
            dataset_uid=str(entry.get("dataset_uid") or version_meta.get("dataset_uid") or ""),
            dataset_id=str(entry.get("dataset_id") or version_meta.get("dataset_id") or ""),
            label=str(version_meta.get("label") or entry.get("dataset_title") or entry.get("name") or "resolved resource"),
            version=str(version_meta.get("version") or "resolved"),
            status=str(version_meta.get("version_status") or "resolved_resource"),
            download_url=download_url,
            landing_url=str(entry.get("landing_url") or version_meta.get("landing_url") or entry.get("docs_url") or ""),
            update_strategy=str(version_meta.get("update_strategy") or "full_replace_if_needed"),
            notes=str(version_meta.get("notes") or ""),
            metadata=dict(metadata),
        )

    def plan_key_for_resolved_entry(self, entry: dict[str, object]) -> str:
        version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
        provider_id = str(entry.get("provider_id") or "unknown_provider")
        dataset_uid = str(entry.get("dataset_uid") or version_meta.get("dataset_uid") or entry.get("dataset_id") or "dataset")
        version = str(version_meta.get("version") or "resolved")
        filename = Path(urllib.parse.unquote(urllib.parse.urlparse(str(entry.get("download_url") or "")).path)).name or "resource"
        base = f"{provider_id}::resolved::{dataset_uid}::{version}::{filename}"
        candidate = base
        suffix = 2
        while candidate in self.plan_version_by_provider or candidate in self.plan_provider_by_key:
            candidate = f"{base}::{suffix}"
            suffix += 1
        return candidate

    def open_adapter_review_panel(self) -> None:
        if not self.selected_plan_items():
            messagebox.showinfo(self.tr("下載計畫是空的", "Download plan is empty"), self.tr("請先把資料集或資料源加入下載計畫。", "Add datasets or sources to the download plan first."))
            return
        planned_entries, _has_dataset_entries = self.current_planned_entries()
        review_items = adapter_review_items({"providers": planned_entries})
        if not review_items:
            messagebox.showinfo(self.tr("沒有 Adapter 待辦", "No adapter review items"), self.tr("目前下載計畫沒有需要 adapter 接手的項目。", "The current plan has no adapter-required items."))
            return
        AdapterReviewDialog(self, review_items)

    def export_download_plan(self) -> None:
        items = self.selected_plan_items()
        if not items:
            messagebox.showinfo("下載計畫是空的", "請先把至少一個資料源加入下載計畫。")
            return
        plan_name = self.plan_name_var.get().strip() or "Untitled download plan"
        payload, _items = self.current_download_plan_payload()
        output_path = state_file(DOWNLOAD_PLAN_NAME)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.status_var.set(f"已匯出下載計畫：{plan_name} ({len(items)} 個項目)")
        messagebox.showinfo("匯出完成", f"已建立 {output_path}\n\nPlan: {plan_name}")

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
