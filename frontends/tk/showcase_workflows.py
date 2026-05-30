"""Tk showcase-mode workflow helpers.

展示模式只承接已穩定、可重跑、可向外部觀眾操作的功能。這裡先放
dataset discovery seed coverage 稽核：它只讀 catalog/source 設定，不做網路
爬取、不下載資料、不寫入 curated DB，因此適合中午展示或進度說明。
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from tkinter import Toplevel, filedialog, messagebox, simpledialog, ttk
from typing import Callable

from api_launcher.crawlers.dataset_sources import (
    DEFAULT_DATASET_DISCOVERY_SOURCES_NAME,
    LOCAL_DATASET_DISCOVERY_SOURCES_NAME,
    load_all_dataset_discovery_sources,
)
from api_launcher.dataset_seed_coverage import (
    build_dataset_seed_coverage_report,
    render_dataset_seed_coverage_markdown,
)
from api_launcher.event_log import log_event, log_exception
from api_launcher.paths import catalog_file, local_config_file, state_file, user_downloads_dir
from api_launcher.repository import ApiCatalogRepository
from api_launcher.showcase_download import (
    ShowcaseDownloadRun,
    ShowcaseResumablePlan,
    build_showcase_resumable_download_plan,
    run_showcase_download_to_folder,
    seed_showcase_repository,
)
from frontends.tk.background_jobs import start_single_flight_thread
from frontends.tk.background_job_policies import MAX_TK_SHOWCASE_DOWNLOAD_JOBS


SHOWCASE_SEED_COVERAGE_JSON = "showcase/dataset_seed_coverage.json"
SHOWCASE_SEED_COVERAGE_MARKDOWN = "showcase/dataset_seed_coverage.md"
SHOWCASE_MAX_PAGES = 3


def showcase_seed_coverage_message(
    report: dict[str, object],
    json_path: Path,
    markdown_path: Path,
    tr: Callable[[str, str], str],
) -> str:
    """Return a human-facing summary for the stable showcase seed audit."""

    # 報告欄位維持 CLI/agent 可讀的英文 key；展示文字在這裡轉成繁中摘要。
    status = str(report.get("showcase_status") or "-")
    source_count = int(report.get("source_count") or 0)
    capable_count = int(report.get("complete_seed_capable_count") or 0)
    ready_count = int(report.get("complete_seed_ready_count") or 0)
    needs_action_count = int(report.get("needs_complete_seed_action_count") or 0)
    max_pages = int(report.get("max_pages_effective_cap") or SHOWCASE_MAX_PAGES)
    return tr(
        "\n".join(
            [
                "展示模式 seed 覆蓋報告已建立。",
                "",
                f"展示狀態：{status}",
                f"已登錄入口 source：{source_count}",
                f"具備完整 seed 嘗試路徑：{capable_count}",
                f"目前已可直接完整 seed：{ready_count}",
                f"展示時需忽略抽樣 search_terms：{needs_action_count}",
                f"展示用 max-pages 安全上限：{max_pages}",
                "",
                f"JSON：{json_path}",
                f"Markdown：{markdown_path}",
                "",
                "這個展示入口只讀取 metadata，不會執行網路爬蟲、下載資料或寫入資料庫。",
            ]
        ),
        "\n".join(
            [
                "Showcase seed coverage report created.",
                "",
                f"Showcase status: {status}",
                f"Registered source count: {source_count}",
                f"Complete seed capable: {capable_count}",
                f"Complete seed ready now: {ready_count}",
                f"Needs complete-seed action: {needs_action_count}",
                f"Showcase max-pages cap: {max_pages}",
                "",
                f"JSON: {json_path}",
                f"Markdown: {markdown_path}",
                "",
                "This showcase entry reads metadata only; it does not crawl, download, or write databases.",
            ]
        ),
    )


def showcase_download_message(run: ShowcaseDownloadRun, tr: Callable[[str, str], str]) -> str:
    """Return the dialog text for the bounded real-download showcase."""

    # 這段文字刻意說明它是「有界展示下載」，避免被誤讀成所有資料源都已全量完成。
    table_counts = ", ".join(f"{table}={count}" for table, count in run.table_counts.items()) or "-"
    return tr(
        "\n".join(
            [
                "展示下載已完成。" if run.succeeded else "展示下載未完整完成。",
                "",
                f"下載/匯入階段：{run.pipeline.stage}",
                f"樣本筆數上限：{run.sample_limit}",
                f"resolved direct entries：{run.resolution.direct_entries_added}",
                f"SQLite 資料表筆數：{table_counts}",
                "",
                f"輸出資料夾：{run.paths.root}",
                f"下載 payload/manifest：{run.paths.downloads_root}",
                f"本機 SQLite .db：{run.paths.curated_sqlite}",
                f"摘要 JSON：{run.paths.summary_json}",
                "",
                "這是有界公開 demo source 的實際下載/匯入短路徑；完整來源全量下載仍需要逐一補齊轉接器與安全上限。",
            ]
        ),
        "\n".join(
            [
                "Showcase download completed." if run.succeeded else "Showcase download did not fully complete.",
                "",
                f"Download/import stage: {run.pipeline.stage}",
                f"Sample row limit: {run.sample_limit}",
                f"Resolved direct entries: {run.resolution.direct_entries_added}",
                f"SQLite table rows: {table_counts}",
                "",
                f"Output folder: {run.paths.root}",
                f"Payload/manifests: {run.paths.downloads_root}",
                f"Local SQLite .db: {run.paths.curated_sqlite}",
                f"Summary JSON: {run.paths.summary_json}",
                "",
                "This is a bounded public demo-source download/import path; full-source downloads still need adapter and safety hardening per source.",
            ]
        ),
    )


def showcase_resumable_plan_message(plan: ShowcaseResumablePlan, tr: Callable[[str, str], str]) -> str:
    """Return the dialog text for the pause/resume showcase download."""

    return tr(
        "\n".join(
            [
                "續傳展示下載已加入下載面板並開始執行。",
                "",
                f"輸出資料夾：{plan.paths.root}",
                f"CSV 目標檔：{plan.target_path}",
                f"下載計畫 JSON：{plan.plan_path}",
                "",
                "請在下方下載面板選取這個工作，按「暫停」後等待狀態變成 paused，再按「繼續」演示續傳。",
                "這條展示線只下載 CSV/manifest 到本機資料夾，暫時短路 SQL 匯入。",
            ]
        ),
        "\n".join(
            [
                "Resume showcase download was added to the download panel and started.",
                "",
                f"Output folder: {plan.paths.root}",
                f"CSV target: {plan.target_path}",
                f"Plan JSON: {plan.plan_path}",
                "",
                "Select this job in the download panel, click Pause until it becomes paused, then click Resume to demonstrate resume behavior.",
                "This showcase path writes CSV/manifest to the local folder only and intentionally short-circuits SQL import.",
            ]
        ),
    )


def format_showcase_bytes(value: object) -> str:
    """Format byte counts for the showcase progress dialog."""

    try:
        size = int(value or 0)
    except (TypeError, ValueError):
        size = 0
    units = ("B", "KB", "MB", "GB")
    amount = float(size)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{size} B"
        amount /= 1024
    return f"{size} B"


def showcase_download_progress_message(stage: str, context: dict[str, object], tr: Callable[[str, str], str]) -> str:
    """Turn backend showcase progress events into honest user-facing text."""

    if stage == "download":
        bytes_done = int(context.get("bytes_done") or 0)
        bytes_total = context.get("bytes_total")
        download_percent = context.get("download_percent")
        if bytes_total:
            return tr(
                f"下載中：{format_showcase_bytes(bytes_done)} / {format_showcase_bytes(bytes_total)}"
                f"（下載 {float(download_percent or 0):.1f}%）。",
                f"Downloading: {format_showcase_bytes(bytes_done)} / {format_showcase_bytes(bytes_total)}"
                f" ({float(download_percent or 0):.1f}% of download).",
            )
        return tr(
            f"下載中：已接收 {format_showcase_bytes(bytes_done)}；遠端沒有提供總大小，所以不顯示假的下載百分比。",
            f"Downloading: received {format_showcase_bytes(bytes_done)}; remote did not provide total size, so no fake byte percent is shown.",
        )
    if stage == "fallback_public_csv":
        return tr(
            "主要公開來源逾時，改用備援公開 CSV；仍會走真下載、manifest 與 SQLite 匯入。",
            "Primary public source timed out; switching to fallback public CSV with real download, manifest, and SQLite import.",
        )
    messages = {
        "prepare_paths": ("準備輸出資料夾。", "Preparing output folder."),
        "build_review_plan": ("建立展示下載計畫。", "Building showcase download plan."),
        "resolve_adapter_plan": ("解析轉接計畫，確認可直接下載的公開資料。", "Resolving adapter plan and direct-download entries."),
        "seed_repository": ("建立展示用 catalog seed，避免乾淨資料庫外鍵失敗。", "Seeding showcase catalog records."),
        "write_plans": ("寫入 review/resolved plan，保留展示稽核紀錄。", "Writing review/resolved plans for audit."),
        "download_import_pipeline_completed": ("下載、manifest 與 SQLite 匯入流程已完成，正在統計結果。", "Download, manifest, and SQLite import completed; counting results."),
        "count_tables": ("正在讀取本機 .db 表格筆數。", "Reading local .db table counts."),
        "completed": ("展示下載完成。", "Showcase download completed."),
    }
    zh, en = messages.get(stage, (f"目前階段：{stage}", f"Current stage: {stage}"))
    return tr(zh, en)


class ShowcaseWorkflowMixin:
    """封裝穩定展示模式入口，避免把實驗功能直接暴露給現場展示。"""

    def write_showcase_seed_coverage_from_ui(self) -> None:
        # 展示模式走固定 ignored state/showcase 位置，讓它可重跑但不污染 Git。
        json_path = state_file(SHOWCASE_SEED_COVERAGE_JSON)
        markdown_path = state_file(SHOWCASE_SEED_COVERAGE_MARKDOWN)
        try:
            sources = load_all_dataset_discovery_sources(
                catalog_file(DEFAULT_DATASET_DISCOVERY_SOURCES_NAME),
                local_config_file(LOCAL_DATASET_DISCOVERY_SOURCES_NAME),
            )
            report = build_dataset_seed_coverage_report(sources, max_pages=SHOWCASE_MAX_PAGES)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            markdown_path.write_text(render_dataset_seed_coverage_markdown(report), encoding="utf-8")
        except Exception as exc:
            log_exception("ui_showcase_seed_coverage_failed", exc, component="ui.showcase")
            self.status_var.set(self.tr("展示 seed 覆蓋報告建立失敗。", "Showcase seed coverage report failed."))
            messagebox.showerror(self.tr("展示模式失敗", "Showcase mode failed"), str(exc))
            return

        summary = self.tr(
            f"展示 seed 覆蓋報告已建立：{report.get('source_count', 0)} 個 source。",
            f"Showcase seed coverage report created: {report.get('source_count', 0)} sources.",
        )
        self.status_var.set(summary)
        log_event(
            "ui_showcase_seed_coverage_created",
            "Created Tk showcase seed coverage report.",
            component="ui.showcase",
            context={
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
                "source_count": report.get("source_count", 0),
                "showcase_status": report.get("showcase_status", ""),
                "complete_seed_capable_count": report.get("complete_seed_capable_count", 0),
                "complete_seed_ready_count": report.get("complete_seed_ready_count", 0),
                "needs_complete_seed_action_count": report.get("needs_complete_seed_action_count", 0),
            },
        )
        messagebox.showinfo(
            self.tr("展示 seed 覆蓋報告已建立", "Showcase seed coverage report created"),
            showcase_seed_coverage_message(report, json_path, markdown_path, self.tr),
        )

    def run_showcase_download_from_ui(self) -> None:
        # 真下載展示仍走有界 demo source，不把尚未硬化的全來源下載放進穩定展示入口。
        if getattr(self, "showcase_download_running", False):
            messagebox.showinfo(
                self.tr("展示下載進行中", "Showcase download is running"),
                self.tr("目前已經有一個展示下載在執行，請等它完成。", "A showcase download is already running; please wait for it to finish."),
            )
            return
        destination = filedialog.askdirectory(
            parent=self.root,
            title=self.tr("選擇展示下載資料夾", "Choose showcase download folder"),
            initialdir=str(user_downloads_dir()),
            mustexist=True,
        )
        if not destination:
            self.status_var.set(self.tr("已取消展示下載。", "Showcase download cancelled."))
            return
        sample_limit = simpledialog.askinteger(
            self.tr("展示樣本筆數", "Showcase sample rows"),
            self.tr(
                "請輸入要下載並匯入 .db 的 Socrata JSON 筆數上限。\n\n"
                "這不是固定玩具資料；你可以調大或調小。\n"
                "若要展示真正大型/無界下載，請改用「大型 CSV 續傳下載」。",
                "Enter the Socrata JSON row limit to download and import into .db.\n\n"
                "This is not a fixed toy dataset; you can make it larger or smaller.\n"
                "Use the large CSV resume showcase for a truly large/unbounded download.",
            ),
            parent=self.root,
            initialvalue=100,
            minvalue=1,
            maxvalue=50000,
        )
        if sample_limit is None:
            self.status_var.set(self.tr("已取消展示下載。", "Showcase download cancelled."))
            return
        self.showcase_download_running = True
        self.open_showcase_download_progress_dialog(Path(destination), sample_limit)
        self.status_var.set(self.tr(f"正在下載展示資料並建立本機 .db（上限 {sample_limit} 筆）...", f"Downloading showcase data and creating local .db (limit {sample_limit} rows)..."))
        started = start_single_flight_thread(
            self,
            ("showcase_download", "bounded_public", ""),
            self.run_showcase_download_worker,
            (Path(destination), sample_limit),
            active_jobs_attr="showcase_active_jobs",
            active_jobs_lock_attr="showcase_active_jobs_lock",
            max_active_jobs=MAX_TK_SHOWCASE_DOWNLOAD_JOBS,
            on_duplicate=lambda: self.status_var.set(
                self.tr("展示下載已在執行中，請等待目前工作完成。", "Showcase download is already running; please wait for it to finish.")
            ),
        )
        if not started:
            self.showcase_download_running = False
            self.close_showcase_download_progress_dialog()

    def open_showcase_download_progress_dialog(self, destination: Path, sample_limit: int) -> None:
        # 展示模式的進度必須可追溯：整體流程用階段百分比，
        # 下載階段若 HTTP 有總長度才顯示 byte 百分比，避免展示假進度。
        existing = getattr(self, "showcase_download_progress_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return
        dialog = Toplevel(self.root)
        dialog.title(self.tr("展示下載進行中", "Showcase download in progress"))
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=self.tr("正在下載展示資料並建立本機 .db", "Downloading showcase data and creating a local .db"),
            font=("", 12, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=self.tr(
                f"資料夾：{destination}\n樣本筆數上限：{sample_limit}\n請等待完成彈窗，展示過程不要關閉此視窗。",
                f"Folder: {destination}\nSample row limit: {sample_limit}\nWait for the completion dialog; do not close this window during the showcase.",
            ),
            justify="left",
            wraplength=520,
        ).pack(anchor="w", pady=(10, 12))
        progress = ttk.Progressbar(frame, mode="determinate", length=520, maximum=100)
        progress.pack(fill="x")
        percent_label = ttk.Label(frame, text="0.0%")
        percent_label.pack(anchor="e", pady=(4, 0))
        status = ttk.Label(
            frame,
            text=self.tr("步驟：解析展示計畫、下載公開資料、寫入 manifest、匯入 SQLite。", "Step: resolve plan, download public data, write manifest, import SQLite."),
            justify="left",
            wraplength=520,
        )
        status.pack(anchor="w", pady=(12, 0))
        self.showcase_download_progress_window = dialog
        self.showcase_download_progress_bar = progress
        self.showcase_download_progress_percent = percent_label
        self.showcase_download_progress_status = status
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - dialog.winfo_width()) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.lift()

    def update_showcase_download_progress(self, percent: float, message: str) -> None:
        bounded_percent = min(100.0, max(0.0, float(percent)))
        progress = getattr(self, "showcase_download_progress_bar", None)
        if progress is not None:
            progress.configure(value=bounded_percent)
        percent_label = getattr(self, "showcase_download_progress_percent", None)
        if percent_label is not None:
            percent_label.configure(text=f"{bounded_percent:.1f}%")
        status = getattr(self, "showcase_download_progress_status", None)
        if status is not None:
            status.configure(text=message)

    def close_showcase_download_progress_dialog(self) -> None:
        progress = getattr(self, "showcase_download_progress_bar", None)
        with contextlib.suppress(Exception):
            if progress is not None:
                progress.stop()
        dialog = getattr(self, "showcase_download_progress_window", None)
        with contextlib.suppress(Exception):
            if dialog is not None and dialog.winfo_exists():
                dialog.destroy()
        self.showcase_download_progress_window = None
        self.showcase_download_progress_bar = None
        self.showcase_download_progress_percent = None
        self.showcase_download_progress_status = None

    def run_showcase_download_worker(self, destination: Path, sample_limit: int) -> None:
        run: ShowcaseDownloadRun | None = None
        error: Exception | None = None
        conn = None
        try:
            self.root.after(
                0,
                lambda: self.update_showcase_download_progress(
                    2,
                    self.tr("步驟：初始化展示 catalog 與資料庫連線。", "Step: initialize showcase catalog and database connection.")
                ),
            )
            conn = self._connect()
            repository = ApiCatalogRepository(conn)

            def emit_progress(percent: float, stage: str, context: dict[str, object]) -> None:
                # worker thread 只能透過 root.after 回到 Tk 主執行緒更新元件；
                # message 由 stage/context 產生，讓 UI 不需要猜測下載實況。
                message = showcase_download_progress_message(stage, context, self.tr)
                self.root.after(0, lambda p=percent, m=message: self.update_showcase_download_progress(p, m))

            self.root.after(
                0,
                lambda: self.update_showcase_download_progress(
                    35,
                    self.tr("步驟：下載公開資料、寫入 manifest，並匯入展示 .db。", "Step: download public data, write manifest, and import the showcase .db.")
                ),
            )
            run = run_showcase_download_to_folder(
                destination,
                repository,
                policy=self.download_policy,
                sample_limit=sample_limit,
                progress_callback=emit_progress,
            )
            log_event(
                "ui_showcase_download_completed",
                "Ran bounded public showcase download from Tk UI.",
                level="info" if run.succeeded else "warning",
                component="ui.showcase",
                context=run.to_dict(),
            )
        except Exception as exc:  # pragma: no cover - GUI worker returns the exception to the UI thread.
            error = exc
            log_exception("ui_showcase_download_failed", exc, component="ui.showcase", context={"destination": str(destination)})
        finally:
            if conn is not None:
                conn.close()
        self.root.after(0, lambda: self.finish_showcase_download(run, error))

    def finish_showcase_download(self, run: ShowcaseDownloadRun | None, error: Exception | None) -> None:
        self.showcase_download_running = False
        self.close_showcase_download_progress_dialog()
        if error is not None or run is None:
            detail = str(error) if error is not None else "unknown error"
            self.status_var.set(self.tr("展示下載失敗。", "Showcase download failed."))
            messagebox.showerror(self.tr("展示下載失敗", "Showcase download failed"), detail)
            return

        self.reload_data()
        summary = self.tr(
            f"展示下載完成：{run.pipeline.stage}，DB={run.paths.curated_sqlite}",
            f"Showcase download completed: {run.pipeline.stage}, DB={run.paths.curated_sqlite}",
        )
        self.status_var.set(summary)
        message = showcase_download_message(run, self.tr)
        if run.succeeded:
            messagebox.showinfo(self.tr("展示下載完成", "Showcase download completed"), message)
        else:
            messagebox.showwarning(self.tr("展示下載未完整完成", "Showcase download did not fully complete"), message)

    def start_showcase_resumable_download_from_ui(self) -> None:
        # 這條線是「無界/較大資料下載展示」：交給正式 DownloadQueue，讓暫停、繼續、取消、重試與 .part 續傳都可被現場操作。
        destination = filedialog.askdirectory(
            parent=self.root,
            title=self.tr("選擇續傳展示下載資料夾", "Choose resume showcase download folder"),
            initialdir=str(user_downloads_dir()),
            mustexist=True,
        )
        if not destination:
            self.status_var.set(self.tr("已取消續傳展示下載。", "Resume showcase download cancelled."))
            return
        try:
            plan = build_showcase_resumable_download_plan(destination)
            # 續傳展示要能在乾淨 catalog 或剛啟動 UI 時直接操作。先把 plan 內的
            # 最小展示 provider/dataset seed 進 repository，再 reload UI rows，
            # 避免 add_download_plan_entries_from_payload 因找不到 row 而不加入任何下載。
            conn = self._connect()
            try:
                seed_showcase_repository(ApiCatalogRepository(conn), plan.plan_payload)
            finally:
                conn.close()
            self.reload_data()
            before_keys = set(self.plan_version_by_provider)
            added = self.add_download_plan_entries_from_payload(plan.plan_payload)
            new_keys = [plan_key for plan_key in self.plan_version_by_provider if plan_key not in before_keys]
        except Exception as exc:
            log_exception("ui_showcase_resumable_plan_failed", exc, component="ui.showcase", context={"destination": str(destination)})
            self.status_var.set(self.tr("續傳展示下載計畫建立失敗。", "Resume showcase plan failed."))
            messagebox.showerror(self.tr("續傳展示失敗", "Resume showcase failed"), str(exc))
            return
        if added == 0 or not new_keys:
            self.status_var.set(self.tr("續傳展示下載無法加入下載計畫。", "Resume showcase could not be added to the plan."))
            messagebox.showwarning(
                self.tr("續傳展示無法啟動", "Resume showcase could not start"),
                self.tr(
                    "找不到可對應的展示 provider。請先確認 catalog seed 已初始化。",
                    "The showcase provider could not be matched. Please ensure the catalog seed has been initialized.",
                ),
            )
            return

        items = []
        for plan_key in new_keys:
            provider_id = self.provider_id_for_plan_key(plan_key)
            row = self.row_by_provider_id(provider_id)
            option = self.plan_version_by_provider.get(plan_key)
            if row is not None:
                items.append((plan_key, row, option))
        if not items:
            self.status_var.set(self.tr("續傳展示下載沒有可啟動的項目。", "Resume showcase has no startable items."))
            return

        self.plan_name_var.set(self.tr("展示續傳下載：NYC 311 CSV", "Showcase resume download: NYC 311 CSV"))
        self.download_plan_visible = True
        self.apply_download_plan_visibility()
        self.update_download_plan_panel()
        self.start_download_plan_items(items)
        log_event(
            "ui_showcase_resumable_download_started",
            "Started resumable showcase CSV download through the normal Tk download queue.",
            component="ui.showcase",
            context=plan.to_dict(),
        )
        messagebox.showinfo(self.tr("續傳展示已開始", "Resume showcase started"), showcase_resumable_plan_message(plan, self.tr))
