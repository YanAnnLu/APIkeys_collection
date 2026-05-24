#!/usr/bin/env python3
"""
Tk control panel for APIkeys_collection.

This UI is a lightweight data source manager: it lists provider/database entries,
lets you select sources, runs metadata crawls, writes download plans, runs direct
downloads, and can import supported CSV/JSON/GeoJSON results into the local MVP SQLite store.
"""

from __future__ import annotations

import sys
from tkinter import BooleanVar, PhotoImage, StringVar, TclError, Tk, messagebox

import APIkeys_collection as core
from api_launcher.downloads.jobs import DownloadProgress, NonBlockingDownloadQueue
from api_launcher.event_log import log_exception
from api_launcher.downloads.http import HTTPDownloadAdapter
from frontends.tk.startup_helpers import (
    tk_startup_failure_message,
)
from frontends.tk.ui_config import (
    COLORS,
    LAYOUT,
    PRODUCT_DISPLAY_NAME,
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
from frontends.tk.app_lifecycle_workflows import AppLifecycleWorkflowMixin
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
from frontends.tk.source_action_workflows import SourceActionWorkflowMixin
from frontends.tk.table_data_workflows import TableDataWorkflowMixin
from frontends.tk.table_interaction_workflows import TableInteractionWorkflowMixin
from frontends.tk.repair_workflows import RepairWorkflowMixin
from frontends.tk.responsive_layout_workflows import ResponsiveLayoutWorkflowMixin
from frontends.tk.showcase_workflows import ShowcaseWorkflowMixin
from frontends.tk.window_layout_workflows import WindowLayoutWorkflowMixin
from frontends.tk.yfinance_workflows import YfinanceWorkflowMixin
from api_launcher.paths import PROJECT_ROOT


class ApiCollectionUi(
    AppLifecycleWorkflowMixin,
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
    SourceActionWorkflowMixin,
    ImportWorkflowMixin,
    DownloadWorkflowMixin,
    OAuthWorkflowMixin,
    RepairWorkflowMixin,
    MvpDemoWorkflowMixin,
    ShowcaseWorkflowMixin,
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
