from __future__ import annotations

import webbrowser
from tkinter import BOTH, LEFT, RIGHT, X, Y, Menu
from tkinter import ttk

from api_launcher.paths import DOWNLOADS_DIR
from frontends.tk.startup_helpers import contextlib_suppress_tcl_error
from frontends.tk.ui_config import COLORS, LAYOUT, TABLE_COLUMNS
from frontends.tk.ui_helpers import clamp


class WindowLayoutWorkflowMixin:
    """封裝主視窗的樣式、選單列與第一層 layout 組裝。

    這個 mixin 只連接既有 command callback，不改下載、匯入、修復、OAuth 或爬蟲
    的執行策略；目標是讓 `launcher_ui.py` 保留 application shell，而不是堆滿 widget
    組裝細節。
    """

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
