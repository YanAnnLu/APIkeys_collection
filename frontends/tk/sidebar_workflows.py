#!/usr/bin/env python3
"""Tk 側欄與 provider favicon 支援流程。"""

from __future__ import annotations

from tkinter import LEFT, X, PhotoImage, TclError
from tkinter import ttk

from api_launcher.event_log import log_event
from api_launcher.favicons import (
    download_favicon_png,
    favicon_cache_path,
    favicon_url_for_page,
    provider_home_url,
)
from frontends.tk.background_jobs import single_flight_job_is_active, start_single_flight_thread
from frontends.tk.ui_config import COLORS


MAX_TK_SIDEBAR_FAVICON_JOBS = 4


class SidebarWorkflowMixin:
    """封裝側欄分類、provider 分組，以及 favicon 快取/下載邏輯。"""

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
        job_key = ("provider_favicon", owner, favicon_url)
        if single_flight_job_is_active(self, job_key, active_jobs_attr="sidebar_active_jobs"):
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

        start_single_flight_thread(
            self,
            job_key,
            worker,
            (),
            active_jobs_attr="sidebar_active_jobs",
            active_jobs_lock_attr="sidebar_active_jobs_lock",
            on_duplicate=lambda: self.provider_icon_loading.discard(owner),
            max_active_jobs=MAX_TK_SIDEBAR_FAVICON_JOBS,
            on_capacity=lambda: self.provider_icon_loading.discard(owner),
        )

    def after_on_root(self, callback: object) -> None:
        # 背景 thread 更新 UI 的唯一入口；root 已關閉時忽略排程錯誤。
        try:
            self.root.after(0, callback)
        except (RuntimeError, TclError):
            return
