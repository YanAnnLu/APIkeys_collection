#!/usr/bin/env python3
"""
Tk control panel for APIkeys_collection.

This UI is a lightweight data source manager: it lists provider/database entries,
lets you select sources, runs metadata crawls, and writes a JSON download plan for
future crawler stages. It does not download bulk datasets.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import urllib.parse
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, Y, BooleanVar, Menu, StringVar, Text, Tk, Toplevel, messagebox, simpledialog
from tkinter import ttk

import APIkeys_collection as core
from api_launcher.download_jobs import DownloadProgress, JobStatus, NonBlockingDownloadQueue
from api_launcher.event_log import EVENT_LOG_NAME, latest_events, log_event, log_exception
from api_launcher.http_downloader import HTTPDownloadAdapter
from api_launcher.manifests import read_manifest
from api_launcher.repair import repair_summary, repair_suggestion_for_result, scan_download_manifests
from api_launcher.database_self_check import DatabaseAssetVerifier, DatabaseSelfCheckIssue, database_self_check_issues
from api_launcher.integrations import save_integration_config
from api_launcher.paths import DOWNLOADS_DIR, PROJECT_ROOT, catalog_file, log_file, state_file
from api_launcher.library_actions import LibraryAction, LibraryContext, library_action_map, library_action_menu_label
from api_launcher.google_auth import build_google_device_login_request
from api_launcher.account_links import DEFAULT_ACCOUNT_PROVIDERS, DEFAULT_CAPABILITY_ROUTES
from api_launcher.data_store_connections import data_store_profiles_from_config, test_data_store_connection


SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = state_file(core.DB_NAME)
DOWNLOAD_PLAN_NAME = "APIkeys_collection_download_plan.json"
DEFAULT_UI_LANGUAGE = "zh-TW"
UI_LANGUAGES = {
    "zh-TW": "繁體中文",
    "en-US": "English",
}


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
    ("star", "*", 0.045, 44, 64, "center", False),
    ("install", "計畫", 0.06, 58, 82, "center", False),
    ("name", "資料集 / API 來源", 0.32, 220, 520, "w", True),
    ("category", "分類", 0.22, 150, 360, "w", True),
    ("local", "本地庫", 0.11, 95, 150, "center", False),
    ("download", "下載", 0.13, 110, 180, "center", False),
    ("action", "動作", 0.09, 82, 140, "center", False),
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
    "detail_ratio": 0.28,
    "detail_min": 360,
    "detail_max": 560,
    "detail_gap": 18,
    "table_min_with_detail": 620,
    "column_manual_max": 920,
}


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def configured_ui_language() -> str:
    value = str(core.load_integration_config().get("ui_language") or DEFAULT_UI_LANGUAGE)
    return value if value in UI_LANGUAGES else DEFAULT_UI_LANGUAGE


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
            return "更新"
        if self.remote_status == "error":
            return "重試"
        if self.remote_status == "unchecked":
            return "檢查"
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
            ("資料源 ID", "provider_id"),
            ("名稱", "name"),
            ("擁有者", "owner"),
            ("類別（逗號分隔）", "categories"),
            ("範圍", "geographic_scope"),
            ("文件 URL", "docs_url"),
            ("API Base URL", "api_base_url"),
            ("註冊 URL", "signup_url"),
            ("認證類型", "auth_type"),
            ("API key 環境變數", "key_env_var"),
        ]
        for label, key in fields:
            ttk.Label(frame, text=label, style="DetailSection.TLabel").pack(anchor="w", pady=(8, 2))
            entry = ttk.Entry(frame, textvariable=self.vars[key], font=("Helvetica", 12))
            entry.pack(fill=X)
            if key == "provider_id" and self.row is not None:
                entry.configure(state="disabled")

        ttk.Label(frame, text="啟動器描述", style="DetailSection.TLabel").pack(anchor="w", pady=(12, 2))
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
        self.ui_language = configured_ui_language()
        self.plan_name_var = StringVar(value=self.tr("未命名下載計畫", "Untitled download plan"))
        self.plan_count_var = StringVar(value=self.tr("下載計畫：0 個資料源", "Download Plan: 0 sources"))
        self.selected: dict[str, BooleanVar] = {}
        self.rows: list[ProviderRow] = []
        self.filtered_rows: list[ProviderRow] = []
        self.active_provider_id = ""
        self.detail_visible = False
        self.download_plan_visible = True
        self.resize_after_id: str | None = None
        self.column_width_overrides = self.load_column_width_overrides()
        self.resizing_column_name: str | None = None
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
        self._build_menu_bar()
        self._build_layout()
        self.root.bind("<Configure>", self.on_root_configure)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.reload_data()
        self.run_startup_environment_checks()

    def tr(self, zh_tw: str, en_us: str = "") -> str:
        if self.ui_language == "en-US" and en_us:
            return en_us
        return zh_tw

    def load_column_width_overrides(self) -> dict[str, int]:
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
        label = str(getattr(eligibility, "label", ""))
        if self.ui_language != "en-US":
            labels = {
                "direct_download": "直接下載",
                "adapter_required": "需要轉接器",
                "metadata_only": "僅文件",
                "unavailable": "不可用",
            }
            label = labels.get(str(getattr(eligibility, "status", "")), label)
        if bool(getattr(eligibility, "requires_api_key", False)):
            return f"{label}+Key" if self.ui_language == "en-US" else f"{label}+金鑰"
        return label

    def localized_download_reason(self, eligibility: object) -> str:
        reason = str(getattr(eligibility, "reason", ""))
        if self.ui_language == "en-US":
            return reason
        reasons = {
            "direct_download": "這個 API 或下載網址看起來可以直接取得檔案。",
            "adapter_required": "這個來源提供 API，需要資料轉接器把資料整理成本機檔案。",
            "metadata_only": "目前只有文件或註冊頁，還沒有直接資料下載網址。",
            "unavailable": "尚未設定可用的文件、API 或下載網址。",
        }
        return reasons.get(str(getattr(eligibility, "status", "")), reason)

    def localized_download_repair_label(self, suggestion: object) -> str:
        if self.ui_language == "en-US":
            return str(getattr(suggestion, "label", ""))
        labels = {
            "none": "不需處理",
            "inspect_manifest": "檢查 manifest",
            "inspect": "檢查狀態",
            "manual_recover": "需要手動修復",
            "requeue_download": "重新排下載",
        }
        return labels.get(str(getattr(suggestion, "action_id", "")), str(getattr(suggestion, "label", "")))

    def localized_database_repair_label(self, suggestion: object) -> str:
        if self.ui_language == "en-US":
            return str(getattr(suggestion, "label", ""))
        labels = {
            "configure_data_store_env": "設定資料儲存環境變數",
            "install_optional_driver_in_project_env": "安裝選用 SQL driver",
            "fix_data_store_profile_mapping": "修正資料儲存 profile",
            "review_schema_drift": "檢查 schema 變動",
            "restore_or_reimport_table": "還原或重新匯入資料表",
            "restore_or_reimport_sqlite_database": "還原或重新匯入 SQLite",
            "test_data_store_connection": "測試資料儲存連線",
            "implement_database_self_check_adapter": "新增自檢 adapter",
            "fix_registry_asset_kind": "修正 registry 資產種類",
            "inspect_database_asset": "檢查資料庫資產",
        }
        return labels.get(str(getattr(suggestion, "action_id", "")), str(getattr(suggestion, "label", "")))

    def localized_database_repair_description(self, suggestion: object) -> str:
        if self.ui_language == "en-US":
            return str(getattr(suggestion, "description", ""))
        descriptions = {
            "configure_data_store_env": "設定必要的資料庫環境變數，然後重新執行資料庫自檢。",
            "install_optional_driver_in_project_env": "把選用資料庫 driver 安裝在專案 Python 環境，不要裝到 base。",
            "fix_data_store_profile_mapping": "目前 SQL profile 指到的資料庫和 registry 期待的資料庫不同；請修正 profile/env 或資產歸屬資料。",
            "review_schema_drift": "比對 registry 記錄的 schema fingerprint 和實際資料庫結構，再決定要 migrate、重新匯入，或更新 registry fingerprint。",
            "restore_or_reimport_table": "這個納管資料表不存在；請從備份還原，或重新跑擁有這張表的匯入流程。",
            "restore_or_reimport_sqlite_database": "這個納管 SQLite 檔案不存在；請還原檔案，或重新跑建立它的匯入流程。",
            "test_data_store_connection": "先測試資料儲存連線，檢查 host、database、帳密、網路與 driver 相容性。",
            "implement_database_self_check_adapter": "這個資料庫引擎還沒有自檢 adapter；請新增 adapter，或先把此資產標成非納管。",
            "fix_registry_asset_kind": "registry 的資產種類不是 database self-check 支援的類型，請先修正資產 metadata。",
            "inspect_database_asset": "這個錯誤還沒有對應到明確修復規則；請先檢查資產紀錄、資料儲存 profile 與最新錯誤訊息。",
        }
        return descriptions.get(str(getattr(suggestion, "action_id", "")), str(getattr(suggestion, "description", "")))

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
            self.status_var.set(self.tr(f"啟動環境檢查需要注意：{summary}", f"Startup environment checks need attention: {summary}"))
            if any(check.status == "error" for check in problems):
                details = "\n".join(f"[{check.status}] {check.name}: {check.detail}" for check in problems)
                messagebox.showwarning(self.tr("啟動環境檢查", "Startup environment check"), details)

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

    def _build_menu_bar(self) -> None:
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
        library_menu.add_command(label=self.tr("驗證已下載檔案", "Verify downloaded files"), command=self.verify_download_manifests)
        library_menu.add_separator()
        library_menu.add_command(label=self.tr("納管目前資料源", "Manage active source"), command=self.manage_active_provider)
        library_menu.add_command(label=self.tr("解除納管目前資料源", "Unmanage active source"), command=self.unmanage_active_provider)
        library_menu.add_command(label=self.tr("移除目前本地資料", "Uninstall active source"), command=self.uninstall_active_provider)
        menu_bar.add_cascade(label=self.tr("資料庫", "Library"), menu=library_menu)

        integrations_menu = Menu(menu_bar, tearoff=0)
        integrations_menu.add_command(label=self.tr("Google / Gemini 與 AI 設定", "Google / Gemini login and AI"), command=self.open_google_gemini_settings)
        integrations_menu.add_command(label=self.tr("資料庫工具設定", "Database tool settings"), command=self.open_database_settings)
        integrations_menu.add_command(label=self.tr("資料儲存連線", "Data store connections"), command=self.open_data_store_connection_settings)
        integrations_menu.add_command(label=self.tr("開啟資料庫工具", "Open database tool"), command=self.open_database_tool)
        integrations_menu.add_separator()
        integrations_menu.add_command(label=self.tr("開啟本機整合設定檔", "Open integration config"), command=self.open_integration_config_file)
        menu_bar.add_cascade(label=self.tr("整合", "Integrations"), menu=integrations_menu)

        tools_menu = Menu(menu_bar, tearoff=0)
        tools_menu.add_command(label=self.tr("啟動環境檢查", "Startup environment checks"), command=self.show_environment_checks)
        tools_menu.add_command(label=self.tr("最近事件紀錄", "Recent event logs"), command=self.show_event_logs)
        tools_menu.add_command(label=self.tr("修復 / 驗證資產", "Repair / verify assets"), command=self.open_repair_panel)
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
        sidebar_width = clamp(int(self.root.winfo_width() * LAYOUT["sidebar_ratio"]), LAYOUT["sidebar_min"], LAYOUT["sidebar_max"])
        outer_pad = self.scaled_pad()

        sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=sidebar_width)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text=self.tr("科學資料\n收藏庫", "API DATA\nCOLLECTION"), style="SidebarTitle.TLabel", justify=LEFT).pack(anchor="w", padx=28, pady=(34, 32))
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
        ttk.Button(controls, text=self.tr("Gemini / AI 設定", "Gemini / AI"), style="Action.TButton", command=self.open_google_gemini_settings).pack(side=LEFT, padx=(0, 10))
        more_button = ttk.Menubutton(controls, text=self.tr("更多", "More"), style="Action.TButton")
        more_menu = Menu(more_button, tearoff=0)
        more_menu.add_command(label=self.tr("抓取選取 metadata", "Fetch selected metadata"), command=self.crawl_selected)
        more_menu.add_command(label=self.tr("匯出下載計畫", "Export download plan"), command=self.export_download_plan)
        more_menu.add_command(label=self.tr("開啟官方文件", "Open official docs"), command=self.open_selected_docs)
        more_menu.add_separator()
        more_menu.add_command(label=self.tr("開啟資料庫工具", "Open database tool"), command=self.open_database_tool)
        more_menu.add_command(label=self.tr("資料庫工具設定", "Database tool settings"), command=self.open_database_settings)
        more_menu.add_separator()
        more_menu.add_command(label=self.tr("資料源詳情", "Dataset details"), command=self.open_detail_drawer)
        more_menu.add_command(label=self.tr("重設表格欄寬", "Reset table columns"), command=self.reset_table_column_widths)
        more_menu.add_command(label=self.tr("編輯資料源", "Edit source"), command=self.edit_active_provider)
        more_button.configure(menu=more_menu)
        more_button.pack(side=LEFT, padx=(0, 10))
        ttk.Entry(controls, textvariable=self.search_var, font=("Helvetica", 14)).pack(side=RIGHT, fill=X, expand=True)
        self.search_var.trace_add("write", lambda *_: self.apply_filter())

        self.content_frame = ttk.Frame(main, style="App.TFrame")
        self.content_frame.pack(fill=BOTH, expand=True, padx=outer_pad, pady=(0, max(14, outer_pad // 2)))

        self.table_frame = ttk.Frame(self.content_frame, style="Panel.TFrame")
        self.table_frame.pack(side=LEFT, fill=BOTH, expand=True)
        columns = tuple(column[0] for column in TABLE_COLUMNS)
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings", selectmode="extended")
        for name, label, _ratio, min_width, _max_width, anchor, stretch in TABLE_COLUMNS:
            self.tree.heading(name, text=label)
            self.tree.column(name, width=min_width, anchor=anchor, stretch=stretch)
        self.tree.tag_configure("has_action", foreground=COLORS["text"])
        self.tree.tag_configure("remote_updated", foreground=COLORS["accent"])
        self.tree.tag_configure("starred", foreground=COLORS["accent"])
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=x_scrollbar.set)
        x_scrollbar.pack(side="bottom", fill=X)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.bind("<ButtonPress-1>", self.on_tree_button_press, add="+")
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_button_release, add="+")
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

        hero = ttk.Frame(self.detail, style="Panel.TFrame")
        hero.pack(fill=X, padx=18, pady=(18, 12))
        ttk.Button(hero, textvariable=self.detail_star_var, width=3, command=self.toggle_active_star).pack(side=LEFT, padx=(0, 10))
        title_label = ttk.Label(hero, textvariable=self.detail_title_var, style="DetailTitle.TLabel", wraplength=self.detail_content_wraplength())
        title_label.pack(side=LEFT, fill=X, expand=True)
        self.detail_wrap_labels.append(title_label)
        ttk.Button(hero, text="×", width=3, command=self.close_detail_drawer).pack(side=RIGHT)
        owner_label = ttk.Label(self.detail, textvariable=self.detail_owner_var, style="DetailMuted.TLabel", wraplength=self.detail_content_wraplength())
        owner_label.pack(anchor="w", fill=X, padx=18)
        self.detail_wrap_labels.append(owner_label)

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
        self.preview_box.insert("1.0", self.tr("OpenGraph / 官方頁面 metadata 擷取後，預覽會顯示在這裡。", "Preview metadata will appear here after OpenGraph/official-page extraction."))
        self.preview_box.configure(state="disabled")

        for label, var in [
            (self.tr("標籤", "TAGS"), self.detail_category_var),
            (self.tr("存取方式", "ACCESS"), self.detail_auth_var),
            (self.tr("狀態", "STATUS"), self.detail_status_var),
            (self.tr("範圍", "SCOPE"), self.detail_scope_var),
            (self.tr("官方連結", "OFFICIAL LINKS"), self.detail_urls_var),
        ]:
            ttk.Label(self.detail, text=label, style="DetailSection.TLabel").pack(anchor="w", padx=18, pady=(10, 2))
            value_label = ttk.Label(self.detail, textvariable=var, style="DetailText.TLabel", wraplength=self.detail_content_wraplength())
            value_label.pack(anchor="w", fill=X, padx=18)
            self.detail_wrap_labels.append(value_label)

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
        ttk.Button(header, text=self.tr("開始", "Start"), style="Action.TButton", command=self.start_download_plan).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("暫停", "Pause"), style="Action.TButton", command=self.pause_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("繼續", "Resume"), style="Action.TButton", command=self.resume_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("取消", "Cancel"), style="Action.TButton", command=self.cancel_active_download).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(header, text=self.tr("重試", "Retry"), style="Action.TButton", command=self.retry_active_download).pack(side=RIGHT, padx=(8, 0))
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
            ("name", self.tr("下載工作", "Download Job"), 260, "w"),
            ("status", self.tr("狀態", "Status"), 120, "center"),
            ("progress", self.tr("進度", "Progress"), 120, "center"),
            ("target", self.tr("目標", "Target"), 420, "w"),
        ]:
            self.download_tree.heading(name, text=label)
            self.download_tree.column(name, width=width, anchor=anchor, stretch=True)
        self.download_tree.pack(fill=X, padx=14, pady=(0, 12))
        self.download_tree.bind("<<TreeviewSelect>>", self.on_download_select)

    def open_detail_drawer(self) -> None:
        if not self.active_provider_id and self.filtered_rows:
            self.active_provider_id = self.filtered_rows[0].provider_id
        self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        if not self.detail_visible:
            self.detail_visible = True
            self.pack_content_area()
        else:
            self.apply_detail_layout()
        self.root.after_idle(self.resize_table_columns)

    def close_detail_drawer(self) -> None:
        if self.detail_visible:
            self.detail_visible = False
            self.pack_content_area()
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

    def apply_detail_layout(self) -> None:
        if not self.detail_visible:
            return
        self.detail.configure(width=self.detail_width())
        self.apply_detail_wraplength()

    def pack_content_area(self) -> None:
        self.table_frame.pack_forget()
        self.detail.pack_forget()
        if self.detail_visible:
            self.apply_detail_layout()
            self.detail.pack(side=RIGHT, fill=Y, padx=(LAYOUT["detail_gap"], 0))
        self.table_frame.pack(side=LEFT, fill=BOTH, expand=True)

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
        self.apply_detail_layout()
        self.resize_table_columns()

    def resize_table_columns(self) -> None:
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

    def on_tree_button_release(self, _event: object) -> None:
        if not self.resizing_column_name:
            return
        name = self.resizing_column_name
        self.resizing_column_name = None
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
            checked = "?" if self.selected[row.provider_id].get() else ""
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
                    row.local_label,
                    self.localized_download_label(row.download_eligibility),
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
        row = self.row_by_provider_id(item)
        actions = self.library_action_map_for_row(row)
        menu = Menu(self.root, tearoff=0)
        self.add_action_menu_item(menu, actions, "add_to_plan", lambda provider_id=item: self.add_provider_to_plan(provider_id))
        self.add_action_menu_item(menu, actions, "install", self.manage_active_provider)
        self.add_action_menu_item(menu, actions, "update", lambda provider_id=item: self.add_provider_to_plan(provider_id))
        self.add_action_menu_item(menu, actions, "repair", self.verify_active_assets)
        version_options = self.version_options_for_provider(item)
        if version_options:
            version_menu = Menu(menu, tearoff=0)
            for option in version_options:
                version_menu.add_command(
                    label=option.menu_label,
                    command=lambda provider_id=item, selected=option: self.add_provider_version_to_plan(provider_id, selected),
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
            label=library_action_menu_label(action),
            command=command,
            state="normal" if action.enabled else "disabled",
        )

    def library_context_for_row(self, row: ProviderRow | None) -> LibraryContext | None:
        if row is None:
            return None
        return LibraryContext(
            provider_id=row.provider_id,
            local_status=row.local_status,
            remote_status=row.remote_status,
            update_status=row.update_status,
            install_id=row.install_id,
            manifest_health="unknown",
            has_direct_download=row.download_eligibility.status == "direct_download",
            has_adapter=row.download_eligibility.status == "adapter_required",
            has_render_assets=bool(row.install_id),
        )

    def library_action_map_for_row(self, row: ProviderRow | None) -> dict[str, LibraryAction]:
        context = self.library_context_for_row(row)
        if context is None:
            return {}
        return library_action_map(context)

    def on_tree_select(self, _event: object) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.active_provider_id = str(selection[0])
        if not self.detail_visible:
            self.open_detail_drawer()
        else:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        row = self.row_by_provider_id(self.active_provider_id)
        if row:
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
        self.status_var.set(self.tr(f"已加入下載計畫：{row.name} {option.menu_label}", f"Added {row.name} {option.menu_label} to download plan"))

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
            version_label = version.menu_label if version else self.localized_download_label(row.download_eligibility)
            self.cart_tree.insert(
                "",
                END,
                iid=row.provider_id,
                values=(row.name, row.auth_type, row.geographic_scope, version_label),
            )
        self.plan_count_var.set(self.tr(f"下載計畫：{len(rows)} 個資料源", f"Download Plan: {len(rows)} sources"))

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
            messagebox.showinfo(self.tr("下載計畫是空的", "Download plan is empty"), self.tr("請先加入至少一個資料源。", "Add at least one source to the download plan first."))
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
        self.status_var.set(self.tr(f"下載工作已開始：{started}；略過：{skipped}", f"Download jobs started: {started}; skipped: {skipped}"))

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
        provider_id = self.active_download_provider_id()
        row = self.row_by_provider_id(provider_id)
        if row is None:
            self.status_var.set(self.tr("沒有可重試的下載工作。", "No active download job to retry."))
            return
        job_id = self.download_jobs_by_provider.get(provider_id)
        progress = self.download_progress_by_provider.get(provider_id)
        if job_id and progress and progress.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
            self.status_var.set(self.tr("只有失敗或取消的下載工作可以重試。", "Only failed or cancelled jobs can be retried."))
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
        self.status_var.set(self.tr(f"下載完成：{row.name if row else provider_id}", f"Download completed: {row.name if row else provider_id}"))

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
            self.set_preview_text(self.tr("OpenGraph / 官方頁面 metadata 擷取後，預覽會顯示在這裡。", "Preview metadata will appear here after OpenGraph/official-page extraction."))
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
        webbrowser.open(core.local_integrations_path().as_uri())
        self.status_var.set(self.tr("已開啟本機整合設定檔。", "Opened local integration config."))

    def open_doc_file(self, name: str) -> None:
        path = PROJECT_ROOT / "docs" / name
        if not path.exists():
            messagebox.showinfo(self.tr("找不到文件", "Document not found"), str(path))
            return
        webbrowser.open(path.as_uri())

    def open_ui_language_settings(self) -> None:
        dialog = Toplevel(self.root)
        dialog.title(self.tr("介面語言", "Interface language"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("460x220")
        dialog.transient(self.root)
        ttk.Label(dialog, text=self.tr("介面語言", "Interface language"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            dialog,
            text=self.tr(
                "選擇 launcher 顯示語言。新開啟的視窗會立即使用；主畫面完整套用需要重新啟動。",
                "Choose the launcher display language. New dialogs use it immediately; restart for the whole main window.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))
        labels_by_code = UI_LANGUAGES
        codes_by_label = {label: code for code, label in labels_by_code.items()}
        language_var = StringVar(value=labels_by_code.get(self.ui_language, labels_by_code[DEFAULT_UI_LANGUAGE]))
        selector = ttk.Combobox(
            dialog,
            textvariable=language_var,
            values=tuple(labels_by_code.values()),
            state="readonly",
            font=("Helvetica", 12),
        )
        selector.pack(fill=X, padx=24, pady=(0, 18))
        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))

        def save_language() -> None:
            selected_code = codes_by_label.get(language_var.get(), DEFAULT_UI_LANGUAGE)
            config = core.ensure_local_integration_config()
            config["ui_language"] = selected_code
            save_integration_config(config)
            self.ui_language = selected_code
            self._build_menu_bar()
            self.status_var.set(self.tr("介面語言已更新。主畫面完整套用需要重新啟動。", "Interface language updated. Restart for the full main window."))
            messagebox.showinfo(
                self.tr("介面語言", "Interface language"),
                self.tr("已儲存介面語言設定。新開啟的視窗會先套用，主畫面完整套用請重新啟動。", "Language saved. New dialogs will use it now; restart for the full main window."),
                parent=dialog,
            )
            dialog.destroy()

        ttk.Button(actions, text=self.tr("儲存", "Save"), style="Action.TButton", command=save_language).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(actions, text=self.tr("取消", "Cancel"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)

    def open_data_store_connection_settings(self) -> None:
        dialog = Toplevel(self.root)
        dialog.title(self.tr("資料儲存連線", "Data store connections"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("900x520")
        dialog.transient(self.root)
        ttk.Label(dialog, text=self.tr("資料儲存連線", "Data store connections"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            dialog,
            text=self.tr(
                "Launcher 之後可能管理 SQL、NoSQL、物件儲存、向量資料庫與本機檔案資料庫。密碼請放在環境變數或未來的安全憑證庫，不要寫進 Git 檔案。",
                "The launcher may manage SQL, NoSQL, object storage, vector DBs, and file-backed stores. Secrets stay in environment variables or a future credential vault.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))
        table = ttk.Treeview(
            dialog,
            columns=("label", "kind", "engine", "required", "optional", "status"),
            show="headings",
            height=10,
        )
        for name, label, width in [
            ("label", self.tr("設定檔", "Profile"), 160),
            ("kind", self.tr("儲存類型", "Store kind"), 140),
            ("engine", self.tr("引擎", "Engine"), 120),
            ("required", self.tr("必要環境變數", "Required env vars"), 260),
            ("optional", self.tr("選用環境變數", "Optional env vars"), 180),
            ("status", self.tr("狀態", "Status"), 90),
        ]:
            table.heading(name, text=label)
            table.column(name, width=width, anchor="w", stretch=True)
        profiles = data_store_profiles_from_config(core.load_integration_config())
        profiles_by_id = {profile.profile_id: profile for profile in profiles}
        for profile in profiles:
            table.insert(
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
        table.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))

        def test_selected_profile() -> None:
            selection = table.selection()
            if not selection:
                messagebox.showinfo(self.tr("資料儲存連線", "Data store connections"), self.tr("請先選取一個資料儲存設定檔。", "Select a data-store profile first."))
                return
            profile_id = str(selection[0])
            profile = profiles_by_id[profile_id]
            result = test_data_store_connection(profile)
            table.set(profile_id, "status", result.status)
            self.status_var.set(self.tr(f"資料儲存測試：{profile_id} {result.status}", f"Data store test: {profile_id} {result.status}"))
            messagebox.showinfo(self.tr("資料儲存連線測試", "Data store connection test"), f"{profile.label}\n\n{result.status}: {result.message}")

        ttk.Button(actions, text=self.tr("測試選取項目", "Test selected"), style="Action.TButton", command=test_selected_profile).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("開啟本機整合設定檔", "Open local integration config"), style="Action.TButton", command=self.open_integration_config_file).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)

    def show_environment_checks(self) -> None:
        checks = core.run_startup_checks(DB_PATH)
        dialog = Toplevel(self.root)
        dialog.title(self.tr("啟動環境檢查", "Startup environment checks"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("760x520")
        dialog.transient(self.root)
        ttk.Label(dialog, text=self.tr("啟動環境檢查", "Startup environment checks"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        table = ttk.Treeview(dialog, columns=("name", "status", "detail"), show="headings", height=14)
        for name, label, width in [
            ("name", self.tr("檢查項目", "Check"), 190),
            ("status", self.tr("狀態", "Status"), 90),
            ("detail", self.tr("細節", "Detail"), 460),
        ]:
            table.heading(name, text=label)
            table.column(name, width=width, anchor="w", stretch=True)
        for check in checks:
            table.insert("", END, values=(check.name, check.status, check.detail))
        table.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)

    def show_event_logs(self) -> None:
        events = latest_events(100)
        dialog = Toplevel(self.root)
        dialog.title(self.tr("最近事件紀錄", "Recent event logs"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("980x620")
        dialog.transient(self.root)
        ttk.Label(dialog, text=self.tr("最近事件紀錄", "Recent event logs"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            dialog,
            text=self.tr(
                "Launcher 和未來 Agent 會用這些 JSONL 結構化事件做除錯與交接。",
                "Structured JSONL events used by the launcher and future agents for debugging and handoff.",
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))

        body = ttk.Frame(dialog, style="Panel.TFrame")
        body.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        table = ttk.Treeview(body, columns=("time", "level", "component", "event", "message"), show="headings", height=10)
        for name, label, width in [
            ("time", self.tr("時間", "Time"), 180),
            ("level", self.tr("層級", "Level"), 80),
            ("component", self.tr("元件", "Component"), 120),
            ("event", self.tr("事件", "Event"), 180),
            ("message", self.tr("訊息", "Message"), 360),
        ]:
            table.heading(name, text=label)
            table.column(name, width=width, anchor="w", stretch=True)
        detail = Text(body, height=9, bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"], wrap=WORD, relief="flat")
        detail.configure(state="disabled")

        event_by_iid: dict[str, dict[str, object]] = {}
        for index, event in enumerate(events):
            iid = str(index)
            event_by_iid[iid] = event
            table.insert(
                "",
                END,
                iid=iid,
                values=(
                    event.get("timestamp", ""),
                    event.get("level", ""),
                    event.get("component", ""),
                    event.get("event", ""),
                    event.get("message", ""),
                ),
            )

        def show_selected_log(_event: object | None = None) -> None:
            selection = table.selection()
            selected = event_by_iid.get(str(selection[0])) if selection else None
            detail.configure(state="normal")
            detail.delete("1.0", END)
            if selected is None:
                detail.insert(END, self.tr("尚未選取事件。", "No event selected.") if events else self.tr("目前沒有結構化事件紀錄。", "No structured log events yet."))
            else:
                detail.insert(END, json.dumps(selected, ensure_ascii=False, indent=2, sort_keys=True))
            detail.configure(state="disabled")

        table.bind("<<TreeviewSelect>>", show_selected_log)
        table.pack(fill=BOTH, expand=True, pady=(0, 10))
        detail.pack(fill=BOTH, expand=True)
        show_selected_log()

        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))
        event_path = log_file(EVENT_LOG_NAME)
        if event_path.exists():
            ttk.Button(actions, text=self.tr("開啟 JSONL 檔案", "Open JSONL file"), style="Action.TButton", command=lambda: webbrowser.open(event_path.as_uri())).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)

    def open_google_gemini_settings(self) -> None:
        dialog = Toplevel(self.root)
        dialog.title(self.tr("Gemini / Google 連線", "Gemini / Google connection"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("620x420")
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text=self.tr("Gemini / Google 連線", "Gemini / Google connection"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        text = Text(dialog, wrap=WORD, bg=COLORS["bg"], fg=COLORS["text"], relief="flat", padx=16, pady=14, font=("Helvetica", 11))
        text.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        profile = core.active_ai_profile()
        profile_text = self.tr(f"目前 AI profile：{profile.label} ({profile.kind})", f"Current AI profile: {profile.label} ({profile.kind})") if profile else self.tr("目前沒有啟用 AI profile。", "No active AI profile.")
        routes_text = "; ".join(
            f"{route.capability}: {route.preferred_provider} -> {route.target_profile}"
            for route in DEFAULT_CAPABILITY_ROUTES
        )
        message = self.tr(
            "\n".join(
                [
                    "這裡是 Google / Gemini 連線入口。",
                    "",
                    profile_text,
                    f"能力路由：{routes_text or '無'}",
                    "",
                    "目前安全骨架支援：",
                    "1. Gemini API key：到 Google AI Studio 建立 key，設定 GEMINI_API_KEY，並啟用 launcher_integrations.local.json 裡的 gemini profile。",
                    "2. Google OAuth：下一步會加入瀏覽器登入、callback、token vault 與 refresh-token 管理。",
                    "",
                    "這個 UI 目前刻意不儲存 Google token，避免憑證流進 Git 或明文設定檔。",
                ]
            ),
            "\n".join(
                [
                    "This panel is the Google/Gemini connection entry point.",
                    "",
                    profile_text,
                    f"Capability routes: {routes_text or 'none'}",
                    "",
                    "Current safe skeleton supports:",
                    "1. Gemini API key: create a key in Google AI Studio, set GEMINI_API_KEY, and enable the gemini profile in launcher_integrations.local.json.",
                    "2. Google OAuth: a later step should add browser sign-in, callback handling, token vault storage, and refresh-token management.",
                    "",
                    "This UI intentionally does not store Google tokens yet, so credentials do not leak into Git or plain config files.",
                ]
            ),
        )
        text.insert("1.0", message)
        text.configure(state="disabled")
        providers = ttk.Treeview(dialog, columns=("provider", "mode", "status", "targets"), show="headings", height=5)
        for name, label, width in [
            ("provider", self.tr("帳號", "Account"), 110),
            ("mode", self.tr("登入模式", "Login mode"), 140),
            ("status", self.tr("狀態", "Status"), 90),
            ("targets", self.tr("能力目標", "Capability targets"), 230),
        ]:
            providers.heading(name, text=label)
            providers.column(name, width=width, anchor="w", stretch=True)
        for provider in DEFAULT_ACCOUNT_PROVIDERS:
            providers.insert(
                "",
                END,
                values=(provider.label, provider.auth_mode, provider.status, ", ".join(provider.capability_targets)),
            )
        providers.pack(fill=X, padx=24, pady=(0, 14))
        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))
        ttk.Button(actions, text=self.tr("本次 session 使用 Gemini", "Use Gemini this session"), style="Action.TButton", command=self.configure_gemini_session).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("開始 QR 登入", "Start QR login"), style="Action.TButton", command=self.open_google_qr_login_dialog).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("開啟 Google AI Studio", "Open Google AI Studio"), style="Action.TButton", command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey")).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("開啟本機整合設定檔", "Open local integration config"), style="Action.TButton", command=lambda: webbrowser.open(core.local_integrations_path().as_uri())).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)

    def configure_gemini_session(self) -> None:
        api_key = simpledialog.askstring(
            self.tr("Gemini API key", "Gemini API key"),
            self.tr("貼上本次 launcher session 要使用的 Gemini API key。\n它只會存在目前程式環境，不會寫進 Git 或設定檔。", "Paste a Gemini API key for this launcher session.\nIt will be stored only in this process environment."),
            parent=self.root,
            show="*",
        )
        if not api_key:
            return
        os.environ["GEMINI_API_KEY"] = api_key.strip()
        try:
            profile = core.set_active_ai_profile("gemini_flash")
        except Exception as exc:
            messagebox.showerror(self.tr("Gemini 設定失敗", "Gemini setup failed"), str(exc))
            return
        self.status_var.set(self.tr(f"Gemini 已在本次 session 啟用：{profile.label}", f"Gemini enabled for this session: {profile.label}"))
        messagebox.showinfo(
            self.tr("Gemini 已啟用", "Gemini enabled"),
            self.tr(
                "Gemini Flash 現在是本次 launcher session 的 AI 摘要 profile。\nAPI key 沒有寫進 Git 或 integration config。",
                "Gemini Flash is now the active AI summary profile for this launcher session.\nThe API key was not written to Git or the integration config.",
            ),
        )

    def open_google_qr_login_dialog(self) -> None:
        request = build_google_device_login_request()
        dialog = Toplevel(self.root)
        dialog.title(self.tr("Google QR 登入", "Google QR login"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("520x520")
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text=self.tr("Google QR / 裝置登入", "Google QR / device login"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        qr_box = Text(dialog, height=10, wrap=WORD, bg=COLORS["bg"], fg=COLORS["text"], relief="flat", padx=16, pady=14, font=("Consolas", 11))
        qr_box.pack(fill=X, padx=24, pady=(0, 14))
        if request.client_id_available:
            qr_text = "\n".join(
                [
                    self.tr("QR 佔位", "QR placeholder"),
                    "",
                    self.tr(f"開啟：{request.verification_url}", f"Open: {request.verification_url}"),
                    self.tr(f"代碼：{request.user_code}", f"Code: {request.user_code}"),
                    "",
                    self.tr("下一步：交換 device_code、顯示真正 QR 圖，並把 token 存到安全 token vault。", "Next step: exchange device_code, render a real QR image, and save tokens in a secure token vault."),
                ]
            )
        else:
            qr_text = "\n".join(
                [
                    self.tr("QR 登入尚未設定。", "QR login is not configured yet."),
                    "",
                    request.message,
                    "",
                    self.tr("設定 OAuth client id 後，這個面板會顯示可掃描的 QR / device-code 登入。", "After an OAuth client id is configured, this panel will show a scan-ready QR/device-code login."),
                ]
            )
        qr_box.insert("1.0", qr_text)
        qr_box.configure(state="disabled")
        ttk.Label(dialog, text=request.message, style="DetailMuted.TLabel").pack(anchor="w", fill=X, padx=24, pady=(0, 14))
        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))
        ttk.Button(actions, text=self.tr("開啟裝置頁面", "Open device page"), style="Action.TButton", command=lambda: webbrowser.open(request.verification_url)).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("開啟本機設定", "Open local config"), style="Action.TButton", command=lambda: webbrowser.open(core.local_integrations_path().as_uri())).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)

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

    def verify_download_manifests(self) -> None:
        results, summary = self.sync_manifest_verification()
        self.status_var.set(self.tr(f"檔案健康狀態：{summary}", f"File health: {summary}"))
        if any(result.needs_repair for result in results):
            messagebox.showwarning(self.tr("檔案驗證", "File verification"), self.tr(f"需要修復：{summary}", f"Repair needed: {summary}"))

    def sync_manifest_verification(self) -> tuple[list[object], dict[str, int]]:
        results = scan_download_manifests()
        summary = repair_summary(results)
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            for result in results:
                if result.status == "manifest_error":
                    continue
                manifest = read_manifest(result.manifest_path)
                repository.upsert_dataset_asset_manifest(
                    manifest,
                    result.manifest_path,
                    status=result.status,
                    verify_error=result.message if result.needs_repair else "",
                )
        finally:
            conn.close()
        return results, summary

    def sync_database_asset_verification(
        self,
        provider_ids: list[str] | None = None,
    ) -> tuple[dict[str, int], list[DatabaseSelfCheckIssue]]:
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            summary = repository.verify_provider_assets(provider_ids, verifier=DatabaseAssetVerifier())
            issues = database_self_check_issues(conn, provider_ids)
        finally:
            conn.close()
        return summary, issues

    def open_repair_panel(self) -> None:
        results, summary = self.sync_manifest_verification()
        database_summary, database_issues = self.sync_database_asset_verification()
        dialog = Toplevel(self.root)
        dialog.title(self.tr("修復 / 驗證資產", "Repair / verify assets"))
        dialog.configure(bg=COLORS["panel"])
        dialog.geometry("1160x700")
        dialog.transient(self.root)
        ttk.Label(dialog, text=self.tr("修復 / 驗證資產", "Repair / verify assets"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            dialog,
            text=self.tr(
                (
                    f"檔案：正常={summary.get('ok', 0)}, 遺失={summary.get('missing', 0)}, "
                    f"大小錯誤={summary.get('size_mismatch', 0)}, checksum 錯誤={summary.get('checksum_mismatch', 0)}, "
                    f"manifest 錯誤={summary.get('manifest_error', 0)}  |  "
                    f"資料庫：正常={database_summary.get('present', 0)}, "
                    f"遺失={database_summary.get('missing', 0)}, 錯誤={database_summary.get('error', 0)}"
                ),
                (
                    f"Files: ok={summary.get('ok', 0)}, missing={summary.get('missing', 0)}, "
                    f"size={summary.get('size_mismatch', 0)}, checksum={summary.get('checksum_mismatch', 0)}, "
                    f"manifest={summary.get('manifest_error', 0)}  |  "
                    f"Databases: present={database_summary.get('present', 0)}, "
                    f"missing={database_summary.get('missing', 0)}, error={database_summary.get('error', 0)}"
                ),
            ),
            style="DetailMuted.TLabel",
        ).pack(anchor="w", fill=X, padx=24, pady=(0, 14))

        body = ttk.Frame(dialog, style="Panel.TFrame")
        body.pack(fill=BOTH, expand=True, padx=24, pady=(0, 14))
        notebook = ttk.Notebook(body)
        notebook.pack(fill=BOTH, expand=True)
        downloads_tab = ttk.Frame(notebook, style="Panel.TFrame")
        databases_tab = ttk.Frame(notebook, style="Panel.TFrame")
        notebook.add(downloads_tab, text=self.tr("下載檔案", "Downloaded files"))
        notebook.add(databases_tab, text=self.tr("資料庫", "Databases"))

        download_table = ttk.Treeview(
            downloads_tab,
            columns=("status", "provider", "dataset", "version", "suggestion", "message", "payload"),
            show="headings",
            height=13,
        )
        for name, label, width in [
            ("status", self.tr("狀態", "Status"), 130),
            ("provider", self.tr("資料源", "Provider"), 140),
            ("dataset", self.tr("資料集", "Dataset"), 150),
            ("version", self.tr("版本", "Version"), 100),
            ("suggestion", self.tr("建議", "Suggestion"), 170),
            ("message", self.tr("訊息", "Message"), 240),
            ("payload", self.tr("檔案路徑", "Payload"), 300),
        ]:
            download_table.heading(name, text=label)
            download_table.column(name, width=width, anchor="w", stretch=True)

        download_detail = Text(downloads_tab, height=8, bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"], wrap=WORD, relief="flat")
        download_detail.configure(state="disabled")
        download_result_by_iid: dict[str, object] = {}
        for index, result in enumerate(results):
            iid = str(index)
            download_result_by_iid[iid] = result
            suggestion = repair_suggestion_for_result(result)
            download_table.insert(
                "",
                END,
                iid=iid,
                values=(
                    result.status,
                    result.provider_id or "-",
                    result.dataset_uid or result.dataset_id or "-",
                    result.version or "-",
                    self.localized_download_repair_label(suggestion),
                    result.message,
                    str(result.payload_path) if result.payload_path else "-",
                ),
            )

        def show_selected_download_result(_event: object | None = None) -> None:
            selection = download_table.selection()
            selected = download_result_by_iid.get(str(selection[0])) if selection else None
            download_detail.configure(state="normal")
            download_detail.delete("1.0", END)
            if selected is None:
                download_detail.insert(END, self.tr("尚未選取 manifest。", "No manifest selected.") if results else self.tr("沒有找到下載 manifest。", "No download manifests found."))
            else:
                suggestion = repair_suggestion_for_result(selected)
                download_detail.insert(
                    END,
                    "\n".join(
                        [
                            f"status: {selected.status}",
                            f"provider_id: {selected.provider_id or '-'}",
                            f"dataset_uid: {selected.dataset_uid or '-'}",
                            f"dataset_id: {selected.dataset_id or '-'}",
                            f"version: {selected.version or '-'}",
                            f"source_url: {selected.source_url or '-'}",
                            f"message: {selected.message}",
                            f"suggestion: {self.localized_download_repair_label(suggestion)}",
                            f"suggestion_action: {suggestion.action_id}",
                            f"suggestion_detail: {suggestion.description}",
                            f"manifest_path: {selected.manifest_path}",
                            f"payload_path: {selected.payload_path}",
                        ]
                    ),
                )
            download_detail.configure(state="disabled")

        download_table.bind("<<TreeviewSelect>>", show_selected_download_result)
        download_table.pack(fill=BOTH, expand=True, pady=(0, 10))
        download_detail.pack(fill=BOTH, expand=True)
        show_selected_download_result()

        database_table = ttk.Treeview(
            databases_tab,
            columns=("status", "provider", "kind", "engine", "asset", "suggestion", "message"),
            show="headings",
            height=13,
        )
        for name, label, width in [
            ("status", self.tr("狀態", "Status"), 110),
            ("provider", self.tr("資料源", "Provider"), 150),
            ("kind", self.tr("種類", "Kind"), 90),
            ("engine", self.tr("引擎", "Engine"), 100),
            ("asset", self.tr("資產", "Asset"), 190),
            ("suggestion", self.tr("建議", "Suggestion"), 220),
            ("message", self.tr("訊息", "Message"), 360),
        ]:
            database_table.heading(name, text=label)
            database_table.column(name, width=width, anchor="w", stretch=True)

        database_detail = Text(databases_tab, height=8, bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"], wrap=WORD, relief="flat")
        database_detail.configure(state="disabled")
        database_issue_by_iid: dict[str, DatabaseSelfCheckIssue] = {}
        for index, issue in enumerate(database_issues):
            iid = str(index)
            database_issue_by_iid[iid] = issue
            suggestion = issue.repair_suggestion()
            database_table.insert(
                "",
                END,
                iid=iid,
                values=(
                    issue.status,
                    issue.provider_id,
                    issue.asset_kind,
                    issue.engine or "-",
                    issue.asset_name,
                    self.localized_database_repair_label(suggestion),
                    issue.error or "-",
                ),
            )

        def show_selected_database_issue(_event: object | None = None) -> None:
            selection = database_table.selection()
            selected = database_issue_by_iid.get(str(selection[0])) if selection else None
            database_detail.configure(state="normal")
            database_detail.delete("1.0", END)
            if selected is None:
                database_detail.insert(END, self.tr("尚未選取資料庫問題。", "No database issue selected.") if database_issues else self.tr("沒有找到資料庫問題。", "No database issues found."))
            else:
                suggestion = selected.repair_suggestion()
                database_detail.insert(
                    END,
                    "\n".join(
                        [
                            f"status: {selected.status}",
                            f"provider_id: {selected.provider_id}",
                            f"asset_kind: {selected.asset_kind}",
                            f"engine: {selected.engine or '-'}",
                            f"asset_name: {selected.asset_name}",
                            f"asset_id: {selected.asset_id}",
                            f"install_id: {selected.install_id or '-'}",
                            f"message: {selected.error or '-'}",
                            f"suggestion: {self.localized_database_repair_label(suggestion)}",
                            f"suggestion_action: {suggestion.action_id}",
                            f"suggestion_detail: {self.localized_database_repair_description(suggestion)}",
                            f"can_auto_repair: {suggestion.can_auto_repair}",
                            f"install_location: {suggestion.details.get('install_location') or '-'}",
                            f"source_uri: {suggestion.details.get('source_uri') or '-'}",
                        ]
                    ),
                )
            database_detail.configure(state="disabled")

        database_table.bind("<<TreeviewSelect>>", show_selected_database_issue)
        database_table.pack(fill=BOTH, expand=True, pady=(0, 10))
        database_detail.pack(fill=BOTH, expand=True)
        show_selected_database_issue()

        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 18))

        def requeue_selected_result() -> None:
            selection = download_table.selection()
            selected = download_result_by_iid.get(str(selection[0])) if selection else None
            if selected is None:
                messagebox.showinfo(self.tr("修復", "Repair"), self.tr("請先選取一列 manifest。", "Select a manifest row first."))
                return
            suggestion = repair_suggestion_for_result(selected)
            if not suggestion.can_requeue:
                messagebox.showinfo(self.tr("修復", "Repair"), suggestion.description)
                return
            plan_entry = dict(suggestion.plan_entry)
            provider_id = str(plan_entry.get("provider_id") or "")
            if not self.prepare_provider_for_download(provider_id):
                self.status_var.set(self.tr(f"{provider_id} 的修復下載已經在執行。", f"Repair download is already active for {provider_id}."))
                return
            try:
                job = self.download_queue.submit(plan_entry)
            except Exception as exc:
                messagebox.showerror(self.tr("修復", "Repair"), self.tr(f"無法重新排修復下載：{type(exc).__name__}: {exc}", f"Could not requeue repair download: {type(exc).__name__}: {exc}"))
                return
            self.download_jobs_by_provider[provider_id] = job.job_id
            self.download_providers_by_job[job.job_id] = provider_id
            self.download_status_by_provider[provider_id] = ("queued", "0%", str(plan_entry.get("target_path") or ""))
            self.update_download_jobs_panel()
            self.status_var.set(self.tr(f"已重新排修復下載：{provider_id}", f"Repair download queued: {provider_id}"))

        def show_selected_database_suggestion() -> None:
            selection = database_table.selection()
            selected = database_issue_by_iid.get(str(selection[0])) if selection else None
            if selected is None:
                messagebox.showinfo(self.tr("資料庫修復", "Database repair"), self.tr("請先選取一列資料庫問題。", "Select a database row first."))
                return
            suggestion = selected.repair_suggestion()
            next_step = self.localized_database_repair_description(suggestion)
            if suggestion.action_id == "configure_data_store_env":
                next_step += self.tr("\n\n請開啟「資料儲存連線」查看必要環境變數。", "\n\nOpen Data store connections to inspect the required environment variables.")
            elif suggestion.action_id == "install_optional_driver_in_project_env":
                next_step += self.tr("\n\n請把 driver 安裝在專案 Python 環境，不要安裝到 base。", "\n\nInstall the driver in the project Python environment, not the base environment.")
            elif suggestion.action_id == "review_schema_drift":
                next_step += self.tr("\n\n這可能是真實資料或 schema 變動；刷新 registry fingerprint 前請先確認。", "\n\nThis can be a real data/schema change; review before refreshing the registered fingerprint.")
            elif suggestion.action_id.startswith("restore_or_reimport"):
                next_step += self.tr("\n\n在 adapter 能證明 ownership 之前，這個 UI 不會自動刪除或重建 SQL 物件。", "\n\nThis UI will not delete or recreate SQL objects automatically until an adapter proves ownership.")
            messagebox.showinfo(
                self.tr("資料庫修復建議", "Database repair suggestion"),
                f"{selected.provider_id} / {selected.asset_name}\n\n{self.localized_database_repair_label(suggestion)}\n{next_step}",
            )

        ttk.Button(actions, text=self.tr("重新整理", "Refresh"), style="Action.TButton", command=lambda: (dialog.destroy(), self.open_repair_panel())).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("重新排下載", "Requeue selected download"), style="Action.TButton", command=requeue_selected_result).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("顯示資料庫建議", "Show database suggestion"), style="Action.TButton", command=show_selected_database_suggestion).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("資料儲存設定", "Data-store settings"), style="Action.TButton", command=self.open_data_store_connection_settings).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("開啟下載資料夾", "Open downloads folder"), style="Action.TButton", command=lambda: webbrowser.open(DOWNLOADS_DIR.as_uri())).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)
        self.status_var.set(self.tr(f"檔案健康狀態：{summary}；資料庫問題={len(database_issues)}", f"File health: {summary}; database issues={len(database_issues)}"))

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
