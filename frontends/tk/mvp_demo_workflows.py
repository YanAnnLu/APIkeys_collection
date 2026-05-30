"""Tk MVP Demo workflow helpers.

這個 mixin 封裝 MVP Demo Flow 的 UI 入口與 smoke worker。主視窗仍負責
下載計畫、資料表與整體生命週期；這裡只處理 canonical demo artifacts 的建立、
背景 smoke 執行，以及回到 UI thread 後的結果呈現。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tkinter import messagebox

import APIkeys_collection as core
from api_launcher.event_log import log_event, log_exception
from api_launcher.mvp_demo import (
    run_mvp_demo_offline_smoke,
    write_mvp_demo_flow as write_mvp_demo_flow_files,
)
from api_launcher.paths import catalog_file, state_file
from frontends.tk.background_jobs import start_single_flight_thread
from frontends.tk.background_job_policies import MAX_TK_MVP_DEMO_SMOKE_JOBS
from frontends.tk.ui_config import MVP_DEMO_FLOW_NAME
from frontends.tk.ui_helpers import (
    mvp_demo_smoke_exception_message,
    mvp_demo_smoke_result_message,
)


class MvpDemoWorkflowMixin:
    """封裝 canonical MVP demo 的 Tk 工具流程。"""

    def write_mvp_demo_flow_from_ui(self) -> None:
        # Demo Flow 是可重複驗收用入口；UI 只建立檔案並排入離線 plan，不替使用者自動下載或寫資料庫。
        flow_path = state_file(MVP_DEMO_FLOW_NAME)
        try:
            result = write_mvp_demo_flow_files(flow_path)
            offline_payload = json.loads(result.offline_plan_path.read_text(encoding="utf-8"))
            added = self.add_download_plan_entries_from_payload(offline_payload)
        except Exception as exc:
            log_exception("ui_mvp_demo_flow_failed", exc, component="ui.mvp_demo")
            messagebox.showerror(self.tr("MVP Demo Flow 失敗", "MVP demo flow failed"), str(exc))
            return

        self.render_table()
        summary = self.tr(
            f"MVP Demo Flow 已建立，已加入 {added} 個離線下載項目。",
            f"MVP demo flow created; added {added} offline download item(s).",
        )
        self.status_var.set(summary)
        log_event(
            "ui_mvp_demo_flow_created",
            summary,
            component="ui.mvp_demo",
            context={
                "flow_path": str(result.flow_path),
                "review_plan_path": str(result.review_plan_path),
                "offline_plan_path": str(result.offline_plan_path),
                "offline_sample_path": str(result.offline_sample_path),
                "added_to_plan": added,
            },
        )
        messagebox.showinfo(
            self.tr("MVP Demo Flow 已建立", "MVP demo flow created"),
            self.tr(
                f"{summary}\n\nFlow：{result.flow_path}\nReview plan：{result.review_plan_path}\n離線 plan：{result.offline_plan_path}\n\n下一步：在下方下載計畫按「開始」，完成後按「匯入」。UI 匯入會寫入一般 curated imports SQLite；flow JSON 另保留隔離 CLI 驗收指令。",
                f"{summary}\n\nFlow: {result.flow_path}\nReview plan: {result.review_plan_path}\nOffline plan: {result.offline_plan_path}\n\nNext: click Start in the download plan, then click Import after download finishes. UI import writes to the normal curated imports SQLite; the flow JSON also keeps isolated CLI acceptance commands.",
            ),
        )

    def run_mvp_demo_smoke_from_ui(self) -> None:
        # 一鍵 smoke 是給一般使用者/展示者的閉環按鈕：直接跑 canonical 離線 demo，
        # 並把成功/失敗轉成可讀摘要，而不是要求使用者理解多段 CLI。
        if self.mvp_demo_smoke_running:
            messagebox.showinfo(
                self.tr("MVP Demo Smoke 進行中", "MVP demo smoke is running"),
                self.tr("目前已經有一個 MVP Demo Smoke 在執行，請等它完成。", "An MVP demo smoke run is already in progress. Wait for it to finish."),
            )
            return
        flow_path = state_file(MVP_DEMO_FLOW_NAME)
        started = start_single_flight_thread(
            self,
            ("mvp_demo_smoke", "canonical", ""),
            self.run_mvp_demo_smoke_worker,
            (flow_path,),
            active_jobs_attr="mvp_demo_active_jobs",
            active_jobs_lock_attr="mvp_demo_active_jobs_lock",
            max_active_jobs=MAX_TK_MVP_DEMO_SMOKE_JOBS,
            on_duplicate=lambda: messagebox.showinfo(
                self.tr("MVP Demo Smoke 進行中", "MVP demo smoke is running"),
                self.tr("目前已經有一個 MVP Demo Smoke 在執行，請等它完成。", "An MVP demo smoke run is already in progress. Wait for it to finish."),
            ),
        )
        if not started:
            return
        self.mvp_demo_smoke_running = True
        self.status_var.set(self.tr("正在一鍵驗證 MVP Demo Flow...", "Running MVP demo smoke..."))

    def run_mvp_demo_smoke_worker(self, flow_path: Path) -> None:
        payload: dict[str, object] = {}
        error: Exception | None = None
        conn: sqlite3.Connection | None = None
        try:
            # canonical smoke 使用隔離 demo DB，避免展示/驗收資料污染一般使用者的主 launcher catalog。
            demo_db_path = flow_path.with_name("launcher.sqlite")
            conn = core.connect_db(demo_db_path)
            repository = core.ApiCatalogRepository(conn)
            repository.init_schema()
            repository.seed_builtin_providers()
            repository.seed_key_reference_if_exists(catalog_file(core.KEY_REFERENCE_NAME))
            result = run_mvp_demo_offline_smoke(flow_path, repository)
            payload = result.to_dict()
            log_event(
                "ui_mvp_demo_smoke_completed",
                "Ran canonical MVP demo smoke from Tk UI.",
                level="info" if result.succeeded else "error",
                component="ui.mvp_demo",
                context=payload,
            )
        except Exception as exc:  # pragma: no cover - GUI worker reports the exception through the UI thread.
            error = exc
            log_exception("ui_mvp_demo_smoke_failed", exc, component="ui.mvp_demo", context={"flow_path": str(flow_path)})
        finally:
            if conn is not None:
                conn.close()
        self.root.after(0, lambda: self.finish_mvp_demo_smoke(payload, error, flow_path))

    def finish_mvp_demo_smoke(self, payload: dict[str, object], error: Exception | None, flow_path: Path) -> None:
        self.mvp_demo_smoke_running = False
        if error is not None:
            message = mvp_demo_smoke_exception_message(error, flow_path, self.tr)
            self.status_var.set(self.tr(f"MVP Demo Smoke 失敗：{type(error).__name__}", f"MVP demo smoke failed: {type(error).__name__}"))
            messagebox.showerror(self.tr("MVP Demo Smoke 失敗", "MVP demo smoke failed"), message)
            return

        self.reload_data()
        self.update_download_plan_panel()
        succeeded = bool(payload.get("succeeded"))
        row_count = payload.get("row_count", 0)
        table_name = str(payload.get("table_name") or "-")
        summary = self.tr(
            f"MVP Demo Smoke {'通過' if succeeded else '未通過'}：{table_name}，{row_count} 筆",
            f"MVP demo smoke {'passed' if succeeded else 'did not pass'}: {table_name}, {row_count} rows",
        )
        self.status_var.set(summary)
        message = mvp_demo_smoke_result_message(payload, self.tr)
        if succeeded:
            messagebox.showinfo(self.tr("MVP Demo Smoke 通過", "MVP demo smoke passed"), message)
        else:
            messagebox.showwarning(self.tr("MVP Demo Smoke 未通過", "MVP demo smoke did not pass"), message)
