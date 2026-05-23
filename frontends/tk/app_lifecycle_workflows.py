#!/usr/bin/env python3
"""Tk 主程式的啟動、關閉與本機連線生命週期。"""

from __future__ import annotations

import os
import sqlite3
from tkinter import TclError, messagebox

import APIkeys_collection as core
from api_launcher.event_log import log_event
from api_launcher.paths import catalog_file
from frontends.tk.startup_helpers import contextlib_suppress_tcl_error
from frontends.tk.ui_config import DB_PATH, PRODUCT_DISPLAY_NAME, PRODUCT_SHORT_NAME


class AppLifecycleWorkflowMixin:
    """封裝主視窗生命週期，避免 layout / row action 與啟動關閉流程混在一起。"""

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
        """讓 IDE 或背景 shell 啟動的 Tk 視窗穩定浮出並取得焦點。"""
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
