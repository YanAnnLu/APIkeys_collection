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
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, BooleanVar, StringVar, Tk, messagebox
from tkinter import ttk

import APIkeys_collection as core


SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / core.DB_NAME
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

    @property
    def category_label(self) -> str:
        return ", ".join(self.categories)

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


class ApiCollectionUi:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("APIkeys_collection")
        self.root.geometry("1280x820")
        self.root.minsize(1040, 680)
        self.root.configure(bg=COLORS["bg"])

        self.search_var = StringVar()
        self.category_var = StringVar(value="all")
        self.status_var = StringVar(value="準備就緒")
        self.selected: dict[str, BooleanVar] = {}
        self.rows: list[ProviderRow] = []
        self.filtered_rows: list[ProviderRow] = []

        self._init_database()
        self._setup_style()
        self._build_layout()
        self.reload_data()

    def _init_database(self) -> None:
        conn = core.connect_db(DB_PATH)
        try:
            repository = core.ApiCatalogRepository(conn)
            repository.init_schema()
            repository.seed_builtin_providers()
            repository.seed_key_reference_if_exists(SCRIPT_DIR / core.KEY_REFERENCE_NAME)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        return core.connect_db(DB_PATH)

    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        with contextlib_suppress_tcl_error():
            style.theme_use("clam")
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Sidebar.TFrame", background=COLORS["sidebar"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Header.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Helvetica", 26, "bold"))
        style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Helvetica", 12))
        style.configure("SidebarTitle.TLabel", background=COLORS["sidebar"], foreground=COLORS["accent"], font=("Helvetica", 18, "bold"))
        style.configure("Sidebar.TButton", background=COLORS["sidebar"], foreground=COLORS["text"], anchor="w", padding=(18, 12))
        style.map("Sidebar.TButton", background=[("active", COLORS["header"])])
        style.configure("Action.TButton", background=COLORS["header"], foreground=COLORS["text"], padding=(16, 10), font=("Helvetica", 12, "bold"))
        style.map("Action.TButton", background=[("active", COLORS["accent_dark"])])
        style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["text"], rowheight=58, font=("Helvetica", 12))
        style.configure("Treeview.Heading", background=COLORS["header"], foreground=COLORS["text"], font=("Helvetica", 12, "bold"), padding=(10, 12))
        style.map("Treeview", background=[("selected", COLORS["accent_dark"])])

    def _build_layout(self) -> None:
        sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=280)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text="API DATA\nCOLLECTION", style="SidebarTitle.TLabel", justify=LEFT).pack(anchor="w", padx=28, pady=(34, 32))
        for label, category in [
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
        header.pack(fill=X, padx=36, pady=(34, 20))
        ttk.Label(header, text="Database Sources", style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text="選取資料源，建立未來爬蟲與 taichi_global_bathymetry.py 的資料下載計畫。", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

        controls = ttk.Frame(main, style="App.TFrame")
        controls.pack(fill=X, padx=36, pady=(0, 18))
        ttk.Button(controls, text="刷新清單", style="Action.TButton", command=self.reload_data).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="自檢狀態", style="Action.TButton", command=self.self_check_selected).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="爬取選取 Metadata", style="Action.TButton", command=self.crawl_selected).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="匯出下載計畫", style="Action.TButton", command=self.export_download_plan).pack(side=LEFT, padx=(0, 12))
        ttk.Button(controls, text="開啟文件", style="Action.TButton", command=self.open_selected_docs).pack(side=LEFT, padx=(0, 12))
        ttk.Entry(controls, textvariable=self.search_var, font=("Helvetica", 14)).pack(side=RIGHT, fill=X, expand=True)
        self.search_var.trace_add("write", lambda *_: self.apply_filter())

        table_frame = ttk.Frame(main, style="Panel.TFrame")
        table_frame.pack(fill=BOTH, expand=True, padx=36, pady=(0, 20))
        columns = ("install", "name", "category", "auth", "status", "update", "local", "scope", "action")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("install", text="選取")
        self.tree.heading("name", text="名稱")
        self.tree.heading("category", text="類別")
        self.tree.heading("auth", text="認證")
        self.tree.heading("status", text="狀態")
        self.tree.heading("update", text="遠端更新")
        self.tree.heading("local", text="本地納管")
        self.tree.heading("scope", text="範圍")
        self.tree.heading("action", text="操作")
        self.tree.column("install", width=72, anchor="center", stretch=False)
        self.tree.column("name", width=340, anchor="w")
        self.tree.column("category", width=230, anchor="w")
        self.tree.column("auth", width=210, anchor="w")
        self.tree.column("status", width=110, anchor="center", stretch=False)
        self.tree.column("update", width=110, anchor="center", stretch=False)
        self.tree.column("local", width=110, anchor="center", stretch=False)
        self.tree.column("scope", width=130, anchor="w", stretch=False)
        self.tree.column("action", width=96, anchor="center", stretch=False)
        self.tree.tag_configure("has_action", foreground=COLORS["text"])
        self.tree.tag_configure("remote_updated", foreground=COLORS["accent"])
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", lambda _event: self.open_selected_docs())

        bottom = ttk.Frame(main, style="App.TFrame")
        bottom.pack(fill=X, padx=36, pady=(0, 22))
        ttk.Label(bottom, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w")

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
        self.apply_filter()
        self.status_var.set(f"已載入 {len(self.rows)} 個資料源。")

    def apply_filter(self) -> None:
        query = self.search_var.get().strip().lower()
        category = self.category_var.get()
        filtered = []
        for row in self.rows:
            if category == "noaa" and "noaa" not in row.provider_id.lower() and "noaa" not in row.owner.lower():
                continue
            if category == "requires_key" and not row.key_env_var:
                continue
            if category not in ("all", "noaa", "requires_key") and category not in row.categories:
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
            if row.action_label:
                tags.append("has_action")
            if row.update_status == "remote_updated":
                tags.append("remote_updated")
            self.tree.insert(
                "",
                END,
                iid=row.provider_id,
                values=(
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
            self.toggle_provider(item)
        elif column == "#9":
            self.run_row_action(item)

    def toggle_provider(self, provider_id: str) -> None:
        var = self.selected[provider_id]
        var.set(not var.get())
        self.render_table()

    def selected_provider_ids(self) -> list[str]:
        return [provider_id for provider_id, var in self.selected.items() if var.get()]

    def selected_rows(self) -> list[ProviderRow]:
        selected_ids = set(self.selected_provider_ids())
        return [row for row in self.rows if row.provider_id in selected_ids]

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

    def self_check_selected(self) -> None:
        provider_ids = self.selected_provider_ids()
        conn = self._connect()
        try:
            count = core.ApiCatalogRepository(conn).refresh_provider_download_state(provider_ids or None)
        finally:
            conn.close()
        self.reload_data()
        scope = "選取項目" if provider_ids else "全部資料源"
        self.status_var.set(f"已完成 {scope} 自檢，更新 {count} 筆狀態。")

    def crawl_selected(self) -> None:
        provider_ids = self.selected_provider_ids()
        if not provider_ids:
            messagebox.showinfo("尚未選取", "請先勾選至少一個資料源。")
            return
        self.status_var.set(f"正在爬取 {len(provider_ids)} 個資料源的 metadata...")
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
            self.root.after(0, lambda: messagebox.showerror("爬取失敗", str(exc)))
            self.root.after(0, lambda: self.status_var.set(f"爬取失敗：{exc}"))
            return
        self.root.after(0, self.reload_data)
        self.root.after(0, lambda: self.status_var.set("metadata 爬取完成。"))

    def export_download_plan(self) -> None:
        rows = self.selected_rows()
        if not rows:
            messagebox.showinfo("尚未選取", "請先勾選至少一個資料源。")
            return
        payload = {
            "schema_version": 1,
            "created_at": core.utc_now_iso(),
            "role": "download plan only; no bulk data has been downloaded",
            "downstream_renderer": "taichi_global_bathymetry.py",
            "providers": [
                {
                    "provider_id": row.provider_id,
                    "name": row.name,
                    "owner": row.owner,
                    "categories": row.categories,
                    "auth_type": row.auth_type,
                    "key_env_var": row.key_env_var,
                    "docs_url": row.docs_url,
                    "api_base_url": row.api_base_url,
                    "signup_url": row.signup_url,
                    "geographic_scope": row.geographic_scope,
                    "notes": row.notes,
                }
                for row in rows
            ],
        }
        output_path = SCRIPT_DIR / DOWNLOAD_PLAN_NAME
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.status_var.set(f"已匯出下載計畫：{output_path.name}")
        messagebox.showinfo("匯出完成", f"已建立 {output_path}")

    def open_selected_docs(self) -> None:
        rows = self.selected_rows()
        if not rows:
            selection = self.tree.selection()
            rows = [row for row in self.rows if row.provider_id in selection]
        if not rows:
            messagebox.showinfo("尚未選取", "請先勾選或點選一個資料源。")
            return
        for row in rows[:5]:
            webbrowser.open(row.docs_url or row.signup_url or row.api_base_url)
        self.status_var.set(f"已開啟 {min(len(rows), 5)} 個官方文件頁。")


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
