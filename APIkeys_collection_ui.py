#!/usr/bin/env python3
"""
Tk control panel for APIkeys_collection.

This UI is a lightweight data source manager: it lists provider/database entries,
lets you select sources, runs metadata crawls, and writes a JSON download plan for
future crawler stages. It does not download bulk datasets.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import urllib.parse
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, Y, BooleanVar, Menu, StringVar, Text, Tk, Toplevel, messagebox
from tkinter import ttk

import APIkeys_collection as core
from api_launcher.download_jobs import DownloadProgress, JobStatus, NonBlockingDownloadQueue
from api_launcher.event_log import log_event, log_exception
from api_launcher.http_downloader import HTTPDownloadAdapter
from api_launcher.manifests import read_manifest
from api_launcher.paths import DOWNLOADS_DIR, catalog_file, state_file


SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = state_file(core.DB_NAME)
DOWNLOAD_PLAN_NAME = "APIkeys_collection_download_plan.json"


COLORS = {
    "bg": "#141a23",
    "sidebar": "#2a2f39",
    "panel": "#20252f",
    "header": "#3b4654",
    "text": "#e7edf6",
    "muted": "#9ba6b5",
    "accent": "#2da8ff",
    "accent_dark": "#1d5d8d",
    "border": "#4a5362",
}


TABLE_COLUMNS = (
    ("star", "★", 0.04, 44, 64, "center", False),
    ("install", "計畫", 0.055, 58, 78, "center", False),
    ("name", "名稱", 0.24, 180, 420, "w", True),
    ("category", "類別", 0.18, 150, 320, "w", True),
    ("auth", "認證", 0.17, 145, 300, "w", True),
    ("status", "狀態", 0.08, 82, 120, "center", False),
    ("update", "遠端更新", 0.09, 92, 135, "center", False),
    ("local", "本地納管", 0.09, 92, 135, "center", False),
    ("scope", "範圍", 0.09, 95, 160, "w", False),
    ("action", "操作", 0.075, 82, 120, "center", False),
)

LAYOUT = {
    "initial_width_ratio": 0.82,
    "initial_height_ratio": 0.78,
    "min_width_ratio": 0.58,
    "min_height_ratio": 0.52,
    "sidebar_ratio": 0.145,
    "sidebar_min": 220,
    "sidebar_max": 320,
    "outer_pad_ratio": 0.018,
    "rowheight_ratio": 0.052,
    "detail_ratio": 0.34,
    "detail_min": 420,
    "detail_max": 680,
}


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


class ProviderRow:
    def __init__(self, entry: core.ProviderCatalogEntry):
        self.provider_id = entry.provider_id
        self.name = entry.name
        self.owner = entry.owner
        self.categories = entry.categories
        self.geographic_scope = entry.geographic_scope
        self.docs_url = entry.docs_url
        self.api_base_url = entry.api_base_url
        self.signup_url = entry.signup_url
        self.auth_type = entry.auth_type
        self.key_env_var = entry.key_env_var
        self.notes = entry.notes
        self.latest_status = entry.latest_status
        self.latest_fetched_at = entry.latest_fetched_at
        self.latest_error = entry.latest_error
        self.remote_status = entry.remote_status
        self.local_status = entry.local_status
        self.update_status = entry.update_status
        self.last_downloaded_at = entry.last_downloaded_at
        self.dataset_path = entry.dataset_path
        self.install_id = entry.install_id
        self.install_fingerprint = entry.install_fingerprint
        self.is_starred = entry.is_starred
        self.download_eligibility = core.assess_provider_download(self.as_provider())

    @property
    def category_label(self) -> str:
        return ", ".join(self.categories)

    @property
    def star_label(self) -> str:
        return "★" if self.is_starred else "☆"

    @property
    def status_label(self) -> str:
        if self.latest_status is None:
            return "未檢查"
        if self.latest_error:
            return "錯誤"
        return str(self.latest_status)

    @property
    def update_label(self) -> str:
        labels = {
            "remote_updated": "有更新",
            "current": "未變動",
            "checked_no_hash": "已檢查",
            "unknown": "未知",
        }
        return labels.get(self.update_status, self.update_status)

    @property
    def local_label(self) -> str:
        labels = {
            "not_imported": "未納管",
            "imported": "已納管",
            "downloaded": "已下載",
            "missing": "本地遺失",
            "error": "錯誤",
        }
        return labels.get(self.local_status, self.local_status)

    @property
    def action_label(self) -> str:
        if self.update_status == "remote_updated":
            return "Refresh"
        if self.remote_status == "error":
            return "Retry"
        if self.remote_status == "unchecked":
            return "Check"
        return ""

    @property
    def download_label(self) -> str:
        label = self.download_eligibility.label
        if self.download_eligibility.requires_api_key:
            return f"{label}+Key"
        return label

    def as_provider(self) -> core.Provider:
        return core.Provider(
            provider_id=self.provider_id,
            name=self.name,
            owner=self.owner,
            categories=self.categories,
            geographic_scope=self.geographic_scope,
            docs_url=self.docs_url,
            api_base_url=self.api_base_url,
            signup_url=self.signup_url,
            auth_type=self.auth_type,
            key_env_var=self.key_env_var,
            notes=self.notes,
        )


class ProviderEditorDialog:
    def __init__(self, parent: Tk, row: ProviderRow | None = None):
        self.parent = parent
        self.row = row
        self.result: core.Provider | None = None
        self.window = Toplevel(parent)
        self.window.title("編輯資料源" if row else "新增資料源")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(620, 640)

        self.vars = {
            "provider_id": StringVar(value=row.provider_id if row else ""),
            "name": StringVar(value=row.name if row else ""),
            "owner": StringVar(value=row.owner if row else ""),
            "categories": StringVar(value=row.category_label if row else ""),
            "geographic_scope": StringVar(value=row.geographic_scope if row else "global"),
            "docs_url": StringVar(value=row.docs_url if row else ""),
            "api_base_url": StringVar(value=row.api_base_url if row else ""),
            "signup_url": StringVar(value=row.signup_url if row else ""),
            "auth_type": StringVar(value=row.auth_type if row else "unknown"),
            "key_env_var": StringVar(value=row.key_env_var if row else ""),
        }

        self._build()
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        fields = [
            ("Provider ID", "provider_id"),
            ("名稱", "name"),
            ("Owner", "owner"),
            ("類別（逗號分隔）", "categories"),
            ("範圍", "geographic_scope"),
            ("Docs URL", "docs_url"),
            ("API Base URL", "api_base_url"),
            ("Signup URL", "signup_url"),
            ("Auth Type", "auth_type"),
            ("Key Env Var", "key_env_var"),
        ]
        for label, key in fields:
            ttk.Label(frame, text=label, style="DetailSection.TLabel").pack(anchor="w", pady=(8, 2))
            entry = ttk.Entry(frame, textvariable=self.vars[key], font=("Helvetica", 12))
            entry.pack(fill=X)
            if key == "provider_id" and self.row is not None:
                entry.configure(state="disabled")

        ttk.Label(frame, text="Launcher 描述", style="DetailSection.TLabel").pack(anchor="w", pady=(12, 2))
        self.notes_text = Text(
            frame,
            height=7,
            wrap=WORD,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            padx=10,
            pady=10,
            font=("Helvetica", 11),
        )
        self.notes_text.pack(fill=BOTH, expand=True)
        if self.row and self.row.notes:
            self.notes_text.insert("1.0", self.row.notes)

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(16, 0))
        ttk.Button(buttons, text="儲存", style="Action.TButton", command=self.save).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(buttons, text="取消", style="Action.TButton", command=self.cancel).pack(side=RIGHT)

    def save(self) -> None:
        provider_id = self.vars["provider_id"].get().strip()
        name = self.vars["name"].get().strip()
        owner = self.vars["owner"].get().strip()
        docs_url = self.vars["docs_url"].get().strip()
        if not provider_id or not name or not owner or not docs_url:
            messagebox.showerror("資料不足", "Provider ID、名稱、Owner、Docs URL 都必須填寫。", parent=self.window)
            return
        categories = tuple(
            value.strip()
            for value in self.vars["categories"].get().split(",")
            if value.strip()
        )
        self.result = core.Provider(
            provider_id=provider_id,
            name=name,
            owner=owner,
            categories=categories or ("custom",),
            geographic_scope=self.vars["geographic_scope"].get().strip() or "global",
            docs_url=docs_url,
            api_base_url=self.vars["api_base_url"].get().strip(),
            signup_url=self.vars["signup_url"].get().strip(),
            auth_type=self.vars["auth_type"].get().strip() or "unknown",
            key_env_var=self.vars["key_env_var"].get().strip(),
            notes=self.notes_text.get("1.0", END).strip(),
        )
        self.window.destroy()

    def cancel(self) -> None:
        self.result = None
        self.window.destroy()


class DatabaseClientSettingsDialog:
    def __init__(self, parent: Tk):
        self.parent = parent
        self.window = Toplevel(parent)
        self.window.title("資料庫工具接口設定")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg=COLORS["panel"])
        self.window.minsize(620, 420)
        core.ensure_local_integration_config()
        self.profiles = core.database_client_profiles()
        self.profile_var = StringVar()
        self.detail_var = StringVar()

        self._build()
        self.window.bind("<Escape>", lambda _event: self.window.destroy())
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)
        self.window.wait_window()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, style="Panel.TFrame")
        frame.pack(fill=BOTH, expand=True, padx=22, pady=22)

        ttk.Label(frame, text="資料庫工具接口", style="DetailTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="選擇這台電腦預設要開啟的資料庫管理工具；實際路徑存放在本機設定檔，不會提交到 Git。",
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, pady=(8, 16))

        active = core.active_database_client()
        values = [self._profile_label(profile) for profile in self.profiles]
        current = self._profile_label(active) if active else (values[0] if values else "")
        self.profile_var.set(current)

        ttk.Label(frame, text="預設工具", style="DetailSection.TLabel").pack(anchor="w", pady=(0, 4))
        self.combo = ttk.Combobox(frame, values=values, textvariable=self.profile_var, state="readonly", font=("Helvetica", 12))
        self.combo.pack(fill=X)
        self.combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_details())

        ttk.Label(frame, text="目前接口", style="DetailSection.TLabel").pack(anchor="w", pady=(16, 4))
        self.detail_box = Text(
            frame,
            height=9,
            wrap=WORD,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            padx=12,
            pady=10,
            font=("Consolas", 11),
        )
        self.detail_box.pack(fill=BOTH, expand=True)
        self.refresh_details()

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=X, pady=(16, 0))
        ttk.Button(buttons, text="開啟本機設定檔", style="Action.TButton", command=self.open_config_file).pack(side=LEFT)
        ttk.Button(buttons, text="測試開啟", style="Action.TButton", command=self.open_selected_client).pack(side=LEFT, padx=(10, 0))
        ttk.Button(buttons, text="設為預設", style="Action.TButton", command=self.save_active_client).pack(side=RIGHT)
        ttk.Button(buttons, text="關閉", style="Action.TButton", command=self.window.destroy).pack(side=RIGHT, padx=(0, 10))

    def _profile_label(self, profile: core.DatabaseClientProfile | None) -> str:
        if profile is None:
            return ""
        enabled = "enabled" if profile.enabled else "disabled"
        return f"{profile.id} - {profile.label} ({enabled})"

    def selected_profile(self) -> core.DatabaseClientProfile | None:
        selected_id = self.profile_var.get().split(" - ", 1)[0].strip()
        return next((profile for profile in self.profiles if profile.id == selected_id), None)

    def refresh_details(self) -> None:
        profile = self.selected_profile()
        self.detail_box.configure(state="normal")
        self.detail_box.delete("1.0", END)
        if profile is None:
            self.detail_box.insert("1.0", "尚未設定資料庫工具。")
        else:
            self.detail_box.insert(
                "1.0",
                "\n".join(
                    [
                        f"id: {profile.id}",
                        f"label: {profile.label}",
                        f"kind: {profile.kind}",
                        f"enabled: {profile.enabled}",
                        f"command: {' '.join(profile.command)}",
                        "",
                        profile.notes or "notes: none",
                    ]
                ),
            )
        self.detail_box.configure(state="disabled")

    def save_active_client(self) -> None:
        profile = self.selected_profile()
        if profile is None:
            messagebox.showinfo("尚未選擇", "請先選擇一個資料庫工具接口。", parent=self.window)
            return
        try:
            core.set_active_database_client(profile.id)
        except Exception as exc:
            messagebox.showerror("無法儲存接口設定", str(exc), parent=self.window)
            return
        messagebox.showinfo("已更新", f"預設資料庫工具已設為：{profile.label}", parent=self.window)

    def open_selected_client(self) -> None:
        profile = self.selected_profile()
        if profile is None:
            messagebox.showinfo("尚未選擇", "請先選擇一個資料庫工具接口。", parent=self.window)
            return
        try:
            core.open_database_client(profile.id)
        except Exception as exc:
            messagebox.showerror("無法開啟資料庫工具", str(exc), parent=self.window)

    def open_config_file(self) -> None:
        path = core.local_integrations_path()
        core.ensure_local_integration_config()
        webbrowser.open(path.as_uri())


class ApiCollectionUi:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("APIkeys_collection")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        initial_w = clamp(int(screen_w * LAYOUT["initial_width_ratio"]), 1080, 1680)
        initial_h = clamp(int(screen_h * LAYOUT["initial_height_ratio"]), 720, 980)
        min_w = max(980, int(screen_w * LAYOUT["min_width_ratio"]))
        min_h = max(640, int(screen_h * LAYOUT["min_height_ratio"]))
        self.root.geometry(f"{initial_w}x{initial_h}")
        self.root.minsize(min_w, min_h)
        self.root.configure(bg=COLORS["bg"])

        self.search_var = StringVar()
        self.category_var = StringVar(value="all")
        self.status_var = StringVar(value="準備就緒")
        self.plan_name_var = StringVar(value="Untitled download plan")
        self.plan_count_var = StringVar(value="Download Plan：0 個資料源")
        self.selected: dict[str, BooleanVar] = {}
        self.rows: list[ProviderRow] = []
        self.filtered_rows: list[ProviderRow] = []
        self.active_provider_id = ""
        self.detail_visible = False
        self.resize_after_id: str | None = None
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
        self.plan_version_by_provider: dict[str, core.DatasetVersionOption] = {}
        self.registered_completed_downloads: set[str] = set()

        self._init_database()
        self._setup_style()
        self._build_layout()
        self.root.bind("<Configure>", self.on_root_configure)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.reload_data()
        self.run_startup_environment_checks()

    def _init_database(self) -> None:
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
        for job_id in list(self.download_providers_by_job):
            with contextlib_suppress_tcl_error():
                self.download_queue.cancel(job_id)
        self.download_queue.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

    def run_startup_environment_checks(self) -> None:
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
            self.status_var.set(f"Startup environment checks need attention: {summary}")
            if any(check.status == "error" for check in problems):
                details = "\n".join(f"[{check.status}] {check.name}: {check.detail}" for check in problems)
                messagebox.showwarning("Startup environment check", details)

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
        rowheight = clamp(int(self.root.winfo_height() * LAYOUT["rowheight_ratio"]), 42, 62)
        style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["text"], rowheight=rowheight, font=("Helvetica", 12))
        style.configure("Treeview.Heading", background=COLORS["header"], foreground=COLORS["text"], font=("Helvetica", 12, "bold"), padding=(10, 12))
        style.map("Treeview", background=[("selected", COLORS["accent_dark"])])

    def _build_layout(self) -> None:
        sidebar_width = clamp(int(self.root.winfo_width() * LAYOUT["sidebar_ratio"]), LAYOUT["sidebar_min"], LAYOUT["sidebar_max"])
        outer_pad = self.scaled_pad()

        sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=sidebar_width)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text="API DATA\nCOLLECTION", style="SidebarTitle.TLabel", justify=LEFT).pack(anchor="w", padx=28, pady=(34, 32))
        for label, category in [
            ("★ 置頂資料源", "starred"),
            ("全部資料源", "all"),
            ("NOAA", "noaa"),
            ("氣象 / 氣候", "weather"),
            ("海洋", "ocean"),
            ("衛星 / 遙測", "satellite"),
            ("地形 / 地理", "geospatial"),
            ("地震", "earthquake"),
            ("金融", "finance"),
            ("航運 / 航空", "aviation"),
            ("需要 API Key", "requires_key"),
        ]:
            ttk.Button(sidebar, text=label, style="Sidebar.TButton", command=lambda c=category: self.set_category(c)).pack(fill=X, padx=18, pady=3)

        main = ttk.Frame(self.root, style="App.TFrame")
        main.pack(side=RIGHT, fill=BOTH, expand=True)

        header = ttk.Frame(main, style="App.TFrame")
        header.pack(fill=X, padx=outer_pad, pady=(outer_pad, max(12, outer_pad // 2)))
        ttk.Label(header, text="Database Sources", style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text="選取資料源，建立未來爬蟲與 taichi_global_bathymetry.py 的資料下載計畫。", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

        controls = ttk.Frame(main, style="App.TFrame")
        controls.pack(fill=X, padx=outer_pad, pady=(0, max(12, outer_pad // 2)))
        ttk.Button(controls, text="刷新清單", style="Action.TButton", command=self.reload_data).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="自檢狀態", style="Action.TButton", command=self.self_check_selected).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="爬取選取 Metadata", style="Action.TButton", command=self.crawl_selected).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="匯出下載計畫", style="Action.TButton", command=self.export_download_plan).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="開啟文件", style="Action.TButton", command=self.open_selected_docs).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="開啟資料庫工具", style="Action.TButton", command=self.open_database_tool).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="資料庫工具設定", style="Action.TButton", command=self.open_database_settings).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="資料源詳情", style="Action.TButton", command=self.open_detail_drawer).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="新增來源", style="Action.TButton", command=self.add_provider).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="編輯來源", style="Action.TButton", command=self.edit_active_provider).pack(side=LEFT, padx=(0, 12))
        ttk.Entry(controls, textvariable=self.search_var, font=("Helvetica", 14)).pack(side=RIGHT, fill=X, expand=True)
        self.search_var.trace_add("write", lambda *_: self.apply_filter())

        content = ttk.Frame(main, style="App.TFrame")
        content.pack(fill=BOTH, expand=True, padx=outer_pad, pady=(0, max(14, outer_pad // 2)))

        table_frame = ttk.Frame(content, style="Panel.TFrame")
        table_frame.pack(side=LEFT, fill=BOTH, expand=True)
        columns = tuple(column[0] for column in TABLE_COLUMNS)
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        for name, label, _ratio, min_width, _max_width, anchor, stretch in TABLE_COLUMNS:
            self.tree.heading(name, text=label)
            self.tree.column(name, width=min_width, anchor=anchor, stretch=stretch)
        self.tree.tag_configure("has_action", foreground=COLORS["text"])
        self.tree.tag_configure("remote_updated", foreground=COLORS["accent"])
        self.tree.tag_configure("starred", foreground=COLORS["accent"])
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.on_tree_context_menu)
        self.tree.bind("<Control-Button-1>", self.on_tree_context_menu)

        self._build_detail_panel(content)

        self._build_download_plan_panel(main, outer_pad)

        bottom = ttk.Frame(main, style="App.TFrame")
        bottom.pack(fill=X, padx=outer_pad, pady=(0, max(14, outer_pad // 2)))
        ttk.Label(bottom, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w")

    def _build_detail_panel(self, parent: ttk.Frame) -> None:
        self.detail_parent = parent
        self.detail = ttk.Frame(parent, style="Panel.TFrame", width=self.detail_width())
        self.detail.pack_propagate(False)

        self.detail_star_var = StringVar(value="☆")
        self.detail_title_var = StringVar(value="選取一個資料源")
        self.detail_owner_var = StringVar(value="像 Steam 商店頁一樣查看用途、狀態與官方入口。")
        self.detail_category_var = StringVar(value="")
        self.detail_auth_var = StringVar(value="")
        self.detail_status_var = StringVar(value="")
        self.detail_scope_var = StringVar(value="")
        self.detail_urls_var = StringVar(value="")

        hero = ttk.Frame(self.detail, style="Panel.TFrame")
        hero.pack(fill=X, padx=18, pady=(18, 12))
        ttk.Button(hero, textvariable=self.detail_star_var, width=3, command=self.toggle_active_star).pack(side=LEFT, padx=(0, 10))
        ttk.Label(hero, textvariable=self.detail_title_var, style="DetailTitle.TLabel").pack(side=LEFT, fill=X, expand=True)
        ttk.Button(hero, text="×", width=3, command=self.close_detail_drawer).pack(side=RIGHT)
        ttk.Label(self.detail, textvariable=self.detail_owner_var, style="DetailMuted.TLabel").pack(anchor="w", fill=X, padx=18)

        self.preview_box = Text(
            self.detail,
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
        self.preview_box.insert("1.0", "Preview metadata will appear here after OpenGraph/official-page extraction.")
        self.preview_box.configure(state="disabled")

        for label, var in [
            ("TAGS", self.detail_category_var),
            ("ACCESS", self.detail_auth_var),
            ("STATUS", self.detail_status_var),
            ("SCOPE", self.detail_scope_var),
            ("OFFICIAL LINKS", self.detail_urls_var),
        ]:
            ttk.Label(self.detail, text=label, style="DetailSection.TLabel").pack(anchor="w", padx=18, pady=(10, 2))
            ttk.Label(self.detail, textvariable=var, style="DetailText.TLabel").pack(anchor="w", fill=X, padx=18)

        actions = ttk.Frame(self.detail, style="Panel.TFrame")
        actions.pack(fill=X, padx=18, pady=(18, 0))
        ttk.Button(actions, text="開啟文件", style="Action.TButton", command=self.open_active_docs).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="AI 產生說明", style="Action.TButton", command=self.generate_active_summary).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="開啟資料庫工具", style="Action.TButton", command=self.open_database_tool).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="資料庫工具設定", style="Action.TButton", command=self.open_database_settings).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="檢查 Metadata", style="Action.TButton", command=self.check_active_metadata).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="驗證本地資產", style="Action.TButton", command=self.verify_active_assets).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="加入下載計畫", style="Action.TButton", command=self.select_active_provider).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="標記已納管", style="Action.TButton", command=self.manage_active_provider).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="解除納管", style="Action.TButton", command=self.unmanage_active_provider).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="移除本地資料", style="Action.TButton", command=self.uninstall_active_provider).pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="編輯描述", style="Action.TButton", command=self.edit_active_provider).pack(fill=X)

    def _build_download_plan_panel(self, parent: ttk.Frame, outer_pad: int) -> None:
        plan = ttk.Frame(parent, style="Panel.TFrame")
        plan.pack(fill=X, padx=outer_pad, pady=(0, max(14, outer_pad // 2)))

        header = ttk.Frame(plan, style="Panel.TFrame")
        header.pack(fill=X, padx=14, pady=(12, 8))
        ttk.Label(header, textvariable=self.plan_count_var, style="DetailSection.TLabel").pack(side=LEFT)
        ttk.Entry(header, textvariable=self.plan_name_var, font=("Helvetica", 12), width=34).pack(side=LEFT, padx=(14, 8))
        ttk.Button(header, text="Start", style="Action.TButton", command=self.start_download_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text="Pause", style="Action.TButton", command=self.pause_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text="Resume", style="Action.TButton", command=self.resume_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text="Cancel", style="Action.TButton", command=self.cancel_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text="Retry", style="Action.TButton", command=self.retry_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text="移除", style="Action.TButton", command=self.remove_selected_from_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text="清空", style="Action.TButton", command=self.clear_download_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text="匯出計畫", style="Action.TButton", command=self.export_download_plan).pack(side=RIGHT)

        columns = ("name", "auth", "scope", "status")
        self.cart_tree = ttk.Treeview(plan, columns=columns, show="headings", height=4, selectmode="browse")
        for name, label, width, anchor in [
            ("name", "資料源", 280, "w"),
            ("auth", "認證", 180, "w"),
            ("scope", "範圍", 130, "w"),
            ("status", "計畫狀態", 140, "center"),
        ]:
            self.cart_tree.heading(name, text=label)
            self.cart_tree.column(name, width=width, anchor=anchor, stretch=True)
        self.cart_tree.pack(fill=X, padx=14, pady=(0, 12))
        self.cart_tree.bind("<<TreeviewSelect>>", self.on_cart_select)

        job_columns = ("name", "status", "progress", "target")
        self.download_tree = ttk.Treeview(plan, columns=job_columns, show="headings", height=4, selectmode="browse")
        for name, label, width, anchor in [
            ("name", "Download Job", 260, "w"),
            ("status", "Status", 120, "center"),
            ("progress", "Progress", 120, "center"),
            ("target", "Target", 420, "w"),
        ]:
            self.download_tree.heading(name, text=label)
            self.download_tree.column(name, width=width, anchor=anchor, stretch=True)
        self.download_tree.pack(fill=X, padx=14, pady=(0, 12))
        self.download_tree.bind("<<TreeviewSelect>>", self.on_download_select)

    def open_detail_drawer(self) -> None:
        if not self.active_provider_id and self.filtered_rows:
            self.active_provider_id = self.filtered_rows[0].provider_id
        self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.detail.configure(width=self.detail_width())
        if not self.detail_visible:
            self.detail.pack(side=RIGHT, fill=Y, padx=(18, 0))
            self.detail_visible = True

    def close_detail_drawer(self) -> None:
        if self.detail_visible:
            self.detail.pack_forget()
            self.detail_visible = False

    def scaled_pad(self) -> int:
        return clamp(int(self.root.winfo_width() * LAYOUT["outer_pad_ratio"]), 18, 40)

    def detail_width(self) -> int:
        return clamp(
            int(self.root.winfo_width() * LAYOUT["detail_ratio"]),
            LAYOUT["detail_min"],
            LAYOUT["detail_max"],
        )

    def on_root_configure(self, event: object) -> None:
        if getattr(event, "widget", None) is not self.root:
            return
        if self.resize_after_id:
            self.root.after_cancel(self.resize_after_id)
        self.resize_after_id = self.root.after(80, self.apply_responsive_layout)

    def apply_responsive_layout(self) -> None:
        self.resize_after_id = None
        width = max(self.root.winfo_width(), 1)
        height = max(self.root.winfo_height(), 1)
        rowheight = clamp(int(height * LAYOUT["rowheight_ratio"]), 42, 62)
        ttk.Style(self.root).configure("Treeview", rowheight=rowheight)
        if self.detail_visible:
            self.detail.configure(width=self.detail_width())
        self.resize_table_columns()

    def resize_table_columns(self) -> None:
        table_width = max(self.tree.winfo_width(), 1)
        reserved = 24
        available = max(table_width - reserved, 1)
        for name, _label, ratio, min_width, max_width, _anchor, _stretch in TABLE_COLUMNS:
            width = clamp(int(available * ratio), min_width, max_width)
            self.tree.column(name, width=width)

    def set_category(self, category: str) -> None:
        self.category_var.set(category)
        self.apply_filter()

    def reload_data(self) -> None:
        conn = self._connect()
        try:
            entries = core.ApiCatalogRepository(conn).list_provider_catalog_entries()
        finally:
            conn.close()
        self.rows = [ProviderRow(entry) for entry in entries]
        for row in self.rows:
            self.selected.setdefault(row.provider_id, BooleanVar(value=False))
        known_ids = {row.provider_id for row in self.rows}
        for provider_id in list(self.selected):
            if provider_id not in known_ids:
                del self.selected[provider_id]
        self.apply_filter()
        if self.active_provider_id not in {row.provider_id for row in self.rows}:
            self.active_provider_id = self.rows[0].provider_id if self.rows else ""
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.update_download_plan_panel()
        self.status_var.set(f"已載入 {len(self.rows)} 個資料源。")

    def apply_filter(self) -> None:
        query = self.search_var.get().strip().lower()
        category = self.category_var.get()
        filtered = []
        for row in self.rows:
            if category == "starred" and not row.is_starred:
                continue
            if category == "noaa" and "noaa" not in row.provider_id.lower() and "noaa" not in row.owner.lower():
                continue
            if category == "requires_key" and not row.key_env_var:
                continue
            if category not in ("all", "starred", "noaa", "requires_key") and category not in row.categories:
                continue
            haystack = " ".join([row.provider_id, row.name, row.owner, row.category_label, row.auth_type, row.notes]).lower()
            if query and query not in haystack:
                continue
            filtered.append(row)
        self.filtered_rows = filtered
        self.render_table()

    def render_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.filtered_rows:
            checked = "✓" if self.selected[row.provider_id].get() else ""
            tags = []
            if row.is_starred:
                tags.append("starred")
            if row.action_label:
                tags.append("has_action")
            if row.update_status == "remote_updated":
                tags.append("remote_updated")
            self.tree.insert(
                "",
                END,
                iid=row.provider_id,
                values=(
                    row.star_label,
                    checked,
                    row.name,
                    row.category_label,
                    row.auth_type,
                    row.status_label,
                    row.update_label,
                    row.local_label,
                    row.geographic_scope,
                    row.action_label,
                ),
                tags=tuple(tags),
            )
        if self.active_provider_id in {row.provider_id for row in self.filtered_rows}:
            self.tree.selection_set(self.active_provider_id)
            self.tree.focus(self.active_provider_id)
        self.resize_table_columns()
        self.update_download_plan_panel()
        self.status_var.set(f"顯示 {len(self.filtered_rows)} / {len(self.rows)} 個資料源。")

    def on_tree_click(self, event: object) -> None:
        region = self.tree.identify("region", getattr(event, "x", 0), getattr(event, "y", 0))
        if region != "cell":
            return
        column = self.tree.identify_column(getattr(event, "x", 0))
        item = self.tree.identify_row(getattr(event, "y", 0))
        if not item:
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
        self.add_provider_to_plan(item)

    def on_tree_context_menu(self, event: object) -> None:
        item = self.tree.identify_row(getattr(event, "y", 0))
        if not item:
            return
        self.active_provider_id = str(item)
        self.tree.selection_set(item)
        self.tree.focus(item)
        menu = Menu(self.root, tearoff=0)
        menu.add_command(label="Add latest/default to plan", command=lambda provider_id=item: self.add_provider_to_plan(provider_id))
        version_options = self.version_options_for_provider(item)
        if version_options:
            version_menu = Menu(menu, tearoff=0)
            for option in version_options:
                version_menu.add_command(
                    label=option.menu_label,
                    command=lambda provider_id=item, selected=option: self.add_provider_version_to_plan(provider_id, selected),
                )
            menu.add_cascade(label="Add dataset version", menu=version_menu)
        else:
            menu.add_command(label="No dataset versions discovered", state="disabled")
        menu.add_separator()
        menu.add_command(label="Open details", command=self.open_detail_drawer)
        menu.add_command(label="Open official docs", command=self.open_active_docs)
        menu.tk_popup(getattr(event, "x_root", 0), getattr(event, "y_root", 0))
        menu.grab_release()

    def on_tree_select(self, _event: object) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.active_provider_id = str(selection[0])
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        row = self.row_by_provider_id(self.active_provider_id)
        if row:
            self.status_var.set(f"已選取資料源：{row.name}")

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
        self.plan_version_by_provider.pop(provider_id, None)
        var = self.selected.setdefault(provider_id, BooleanVar(value=False))
        already_selected = var.get()
        var.set(True)
        self.active_provider_id = provider_id
        self.render_table()
        self.status_var.set(
            f"{'已在下載計畫中' if already_selected else '已加入下載計畫'}：{row.name}"
        )

    def add_provider_version_to_plan(self, provider_id: str, option: core.DatasetVersionOption) -> None:
        row = self.row_by_provider_id(provider_id)
        if row is None:
            return
        self.plan_version_by_provider[provider_id] = option
        self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
        self.active_provider_id = provider_id
        self.render_table()
        self.status_var.set(f"Added {row.name} {option.menu_label} to download plan")

    def version_options_for_provider(self, provider_id: str) -> list[core.DatasetVersionOption]:
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
        rows = self.selected_rows()
        for row in rows:
            version = self.plan_version_by_provider.get(row.provider_id)
            version_label = version.menu_label if version else row.download_label
            self.cart_tree.insert(
                "",
                END,
                iid=row.provider_id,
                values=(row.name, row.auth_type, row.geographic_scope, version_label),
            )
        self.plan_count_var.set(f"Download Plan：{len(rows)} 個資料源")

        self.update_download_jobs_panel()

    def on_cart_select(self, _event: object) -> None:
        selection = self.cart_tree.selection()
        if not selection:
            return
        self.active_provider_id = str(selection[0])
        if self.active_provider_id in {row.provider_id for row in self.filtered_rows}:
            self.tree.selection_set(self.active_provider_id)
            self.tree.focus(self.active_provider_id)
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))

    def on_download_select(self, _event: object) -> None:
        selection = self.download_tree.selection()
        if selection:
            self.active_provider_id = str(selection[0])

    def start_download_plan(self) -> None:
        rows = self.selected_rows()
        if not rows:
            messagebox.showinfo("Download plan is empty", "Add at least one source to the download plan first.")
            return
        self.start_download_rows(rows)

    def start_download_rows(self, rows: list[ProviderRow]) -> None:
        started = 0
        skipped = 0
        for row in rows:
            if not self.prepare_provider_for_download(row.provider_id):
                continue
            eligibility = row.download_eligibility
            url = eligibility.direct_url
            if eligibility.status != "direct_download" or not url:
                version = self.plan_version_by_provider.get(row.provider_id)
                if version and version.download_url:
                    url = version.download_url
                else:
                    skipped += 1
                    self.download_status_by_provider[row.provider_id] = ("skipped", "0%", eligibility.reason)
                    continue
            target_path = self.download_target_for_row(row, url)
            plan_entry = core.provider_plan_entry(self.provider_from_row(row))
            version = self.plan_version_by_provider.get(row.provider_id)
            if version:
                plan_entry["dataset_version"] = version.to_plan_metadata()
            plan_entry["download_url"] = url
            plan_entry["target_path"] = str(target_path)
            job = self.download_queue.submit(plan_entry)
            self.download_jobs_by_provider[row.provider_id] = job.job_id
            self.download_providers_by_job[job.job_id] = row.provider_id
            self.download_status_by_provider[row.provider_id] = ("queued", "0%", str(target_path))
            started += 1
        self.update_download_jobs_panel()
        self.status_var.set(f"Download jobs started: {started}; skipped: {skipped}")

    def prepare_provider_for_download(self, provider_id: str) -> bool:
        job_id = self.download_jobs_by_provider.get(provider_id)
        if not job_id:
            return True
        progress = self.download_progress_by_provider.get(provider_id)
        if progress and progress.status in {JobStatus.FAILED, JobStatus.CANCELLED}:
            self.download_jobs_by_provider.pop(provider_id, None)
            self.download_providers_by_job.pop(job_id, None)
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
        provider_id = str(selection[0]) if selection else self.active_provider_id
        return self.download_jobs_by_provider.get(provider_id)

    def pause_active_download(self) -> None:
        job_id = self.active_download_job_id()
        if not job_id:
            self.status_var.set("No active download job to pause.")
            return
        self.download_queue.pause(job_id)

    def resume_active_download(self) -> None:
        job_id = self.active_download_job_id()
        if not job_id:
            self.status_var.set("No active download job to resume.")
            return
        self.download_queue.resume(job_id)

    def cancel_active_download(self) -> None:
        job_id = self.active_download_job_id()
        if not job_id:
            self.status_var.set("No active download job to cancel.")
            return
        self.download_queue.cancel(job_id)

    def retry_active_download(self) -> None:
        provider_id = self.active_download_provider_id()
        row = self.row_by_provider_id(provider_id)
        if row is None:
            self.status_var.set("No active download job to retry.")
            return
        job_id = self.download_jobs_by_provider.get(provider_id)
        progress = self.download_progress_by_provider.get(provider_id)
        if job_id and progress and progress.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
            self.status_var.set("Only failed or cancelled jobs can be retried.")
            return
        self.download_jobs_by_provider.pop(provider_id, None)
        if job_id:
            self.download_providers_by_job.pop(job_id, None)
        self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
        self.start_download_rows([row])

    def active_download_provider_id(self) -> str:
        selection = self.download_tree.selection()
        return str(selection[0]) if selection else self.active_provider_id

    def on_download_progress_threadsafe(self, progress: DownloadProgress) -> None:
        self.root.after(0, lambda update=progress: self.on_download_progress(update))

    def on_download_progress(self, progress: DownloadProgress) -> None:
        provider_id = self.download_providers_by_job.get(progress.job_id, progress.provider_id)
        self.download_progress_by_provider[provider_id] = progress
        target = self.download_status_by_provider.get(provider_id, ("", "", ""))[2]
        self.download_status_by_provider[provider_id] = (
            progress.status.value,
            self.format_download_percent(progress),
            target or progress.message,
        )
        self.update_download_jobs_panel()
        if progress.status == JobStatus.COMPLETED:
            self.register_completed_download(provider_id, target)
        elif progress.status in {JobStatus.FAILED, JobStatus.CANCELLED}:
            log_event(
                "download_job_problem",
                progress.error or progress.message,
                level="error" if progress.status == JobStatus.FAILED else "warning",
                component="ui.download",
                context={"provider_id": provider_id, "job_id": progress.job_id, "status": progress.status.value, "target": target},
            )
            self.status_var.set(f"Download {progress.status.value}: {provider_id} {progress.error}")

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
        provider_ids = list(dict.fromkeys([*self.selected_provider_ids(), *self.download_status_by_provider.keys()]))
        for provider_id in provider_ids:
            row = self.row_by_provider_id(provider_id)
            status, progress, target = self.download_status_by_provider.get(provider_id, ("planned", "0%", ""))
            self.download_tree.insert(
                "",
                END,
                iid=provider_id,
                values=(row.name if row else provider_id, status, progress, target),
            )

    def register_completed_download(self, provider_id: str, target: str) -> None:
        if provider_id in self.registered_completed_downloads:
            return
        self.registered_completed_downloads.add(provider_id)
        row = self.row_by_provider_id(provider_id)
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            install_id = repository.manage_provider_installation(
                provider_id,
                location=target,
                notes="Downloaded by APIkeys_collection HTTP downloader.",
            )
            if target:
                manifest_path = Path(target).with_suffix(Path(target).suffix + ".manifest.json")
                repository.register_installation_asset(
                    install_id,
                    asset_kind="file",
                    asset_name=Path(target).name,
                    asset_role="source",
                    source_format="unknown",
                    source_uri=self.download_url_for_row(row) if row else "",
                    notes="Downloaded source asset.",
                )
                if manifest_path.exists():
                    repository.upsert_dataset_asset_manifest(read_manifest(manifest_path), manifest_path, status="ok")
        finally:
            conn.close()
        self.reload_data()
        self.status_var.set(f"Download completed: {row.name if row else provider_id}")

    def remove_selected_from_plan(self) -> None:
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showinfo("尚未選取", "請先在下載計畫中選取一個資料源。")
            return
        provider_id = str(selection[0])
        self.selected.setdefault(provider_id, BooleanVar(value=False)).set(False)
        self.plan_version_by_provider.pop(provider_id, None)
        self.render_table()
        row = self.row_by_provider_id(provider_id)
        self.status_var.set(f"已移出下載計畫：{row.name if row else provider_id}")

    def clear_download_plan(self) -> None:
        if not self.selected_provider_ids():
            self.status_var.set("下載計畫已經是空的。")
            return
        for var in self.selected.values():
            var.set(False)
        self.plan_version_by_provider.clear()
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
            self.set_preview_text("Preview metadata will appear here after OpenGraph/official-page extraction.")
            return

        self.detail_star_var.set(row.star_label)
        self.detail_title_var.set(row.name)
        self.detail_owner_var.set(row.owner)
        self.detail_category_var.set(row.category_label)
        access = row.auth_type
        if row.key_env_var:
            access = f"{access}\nEnv: {row.key_env_var}"
        self.detail_auth_var.set(access)
        self.detail_status_var.set(
            f"Remote: {row.status_label} / {row.update_label}\n"
            f"Local: {row.local_label}\n"
            f"Install ID: {row.install_id or 'not managed'}\n"
            f"Download: {row.download_eligibility.label} - {row.download_eligibility.reason}"
        )
        self.detail_scope_var.set(row.geographic_scope)
        links = [
            f"Docs: {row.docs_url}" if row.docs_url else "",
            f"API: {row.api_base_url}" if row.api_base_url else "",
            f"Signup: {row.signup_url}" if row.signup_url else "",
        ]
        self.detail_urls_var.set("\n".join(link for link in links if link))
        self.set_preview_text(self.provider_description(row))

    def provider_description(self, row: ProviderRow) -> str:
        if row.notes:
            return row.notes
        category_hint = row.category_label or "data"
        return (
            f"{row.name} is an official {category_hint} source from {row.owner}. "
            "A richer description and visual preview will be populated from official metadata pages."
        )

    def set_preview_text(self, text: str) -> None:
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", END)
        self.preview_box.insert("1.0", text)
        self.preview_box.configure(state="disabled")

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

    def generate_active_summary(self) -> None:
        row = self.row_by_provider_id(self.active_provider_id)
        if row is None:
            messagebox.showinfo("尚未選取", "請先選取一個資料源。")
            return
        profile = core.active_ai_profile()
        if profile is None:
            messagebox.showinfo(
                "尚未設定 AI 摘要",
                (
                    "請在 launcher_integrations.local.json 啟用一個 ai_summary_profiles。"
                    "預設建議使用本機 Ollama，免登入也不需要雲端 API key。"
                ),
            )
            return
        self.status_var.set(f"正在使用 {profile.label} 產生 {row.name} 的說明...")
        thread = threading.Thread(target=self._summary_worker, args=(row.provider_id,), daemon=True)
        thread.start()

    def _summary_worker(self, provider_id: str) -> None:
        saved_summary = False
        try:
            conn = self._connect()
            try:
                repository = core.ApiCatalogRepository(conn)
                providers = repository.load_providers([provider_id])
                if not providers:
                    raise RuntimeError(f"Unknown provider_id: {provider_id}")
                provider = providers[0]
                summary = core.generate_provider_summary(provider)
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
                context={"provider_id": provider_id},
            )
            self.root.after(0, lambda: messagebox.showerror("AI 摘要失敗", error))
            self.root.after(0, lambda: self.status_var.set(f"AI 摘要失敗：{error}"))
            return

        def update_ui() -> None:
            if saved_summary:
                self.reload_data()
                row = self.row_by_provider_id(provider_id)
                self.status_var.set(f"AI 說明已寫入：{row.name if row else provider_id}")
            else:
                self.set_preview_text(summary)
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
        conn = self._connect()
        try:
            summary = core.ApiCatalogRepository(conn).verify_provider_assets([self.active_provider_id])
        finally:
            conn.close()
        self.reload_data()
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.status_var.set(
            f"已驗證本地資產：{row.name if row else self.active_provider_id} "
            f"(present={summary['present']}, missing={summary['missing']}, error={summary['error']})"
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

    def export_download_plan(self) -> None:
        rows = self.selected_rows()
        if not rows:
            messagebox.showinfo("下載計畫是空的", "請先把至少一個資料源加入下載計畫。")
            return
        plan_name = self.plan_name_var.get().strip() or "Untitled download plan"
        payload = core.build_download_plan(
            [self.provider_from_row(row) for row in rows],
            plan_name=plan_name,
        )
        for entry in payload["providers"]:
            if not isinstance(entry, dict):
                continue
            option = self.plan_version_by_provider.get(str(entry.get("provider_id") or ""))
            if option:
                entry["dataset_version"] = option.to_plan_metadata()
                entry["download_url"] = option.download_url
        output_path = state_file(DOWNLOAD_PLAN_NAME)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.status_var.set(f"已匯出下載計畫：{plan_name} ({len(rows)} 個資料源)")
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


class contextlib_suppress_tcl_error:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return exc_type is not None


def main() -> int:
    root = Tk()
    ApiCollectionUi(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
