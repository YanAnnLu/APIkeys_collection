"""Tk yfinance workflow helpers.

這個 mixin 承接 yfinance 相關的 UI workflow：離線 demo plan、guarded live plan、
以及 storage review dry-run。把這些流程移出主視窗類別，可以讓 launcher_ui.py
保留選單與整體生命週期，並避免後續改 yfinance 表單時誤碰主表格或修復面板。
"""

from __future__ import annotations

from tkinter import LEFT, RIGHT, X, BooleanVar, StringVar, Toplevel, messagebox
from tkinter import ttk

from api_launcher.adapters.yfinance import (
    DEFAULT_YFINANCE_QUERY_WINDOW_PRESET,
    DEFAULT_YFINANCE_RETENTION_DAYS,
    DEFAULT_YFINANCE_STORAGE_TARGET,
    YFINANCE_LIVE_WARNING,
    YFINANCE_QUERY_WINDOW_PRESETS,
    YFINANCE_STORAGE_TARGET_PROFILES,
    write_yfinance_demo_plan as write_yfinance_demo_plan_files,
    write_yfinance_live_plan as write_yfinance_live_plan_files,
    write_yfinance_storage_handoff as write_yfinance_storage_handoff_file,
    write_yfinance_storage_review as write_yfinance_storage_review_file,
)
from api_launcher.event_log import log_event, log_exception
from api_launcher.paths import state_file
from frontends.tk.ui_config import (
    COLORS,
    YFINANCE_DEMO_PLAN_NAME,
    YFINANCE_LIVE_PLAN_NAME,
    YFINANCE_STORAGE_HANDOFF_NAME,
    YFINANCE_STORAGE_REVIEW_NAME,
)
from frontends.tk.ui_helpers import (
    yfinance_project_path_from_ui_text,
    yfinance_storage_review_paths_from_ui,
    yfinance_symbols_from_ui_text,
)


class YfinanceWorkflowMixin:
    """封裝 yfinance 工具選單背後的 guarded UI workflow。"""

    def write_yfinance_demo_plan_from_ui(self) -> None:
        # yfinance 離線 demo 是金融時間序列的安全驗收入口：只產生 fixture-backed plan，不安裝套件、不打 Yahoo。
        plan_path = state_file(YFINANCE_DEMO_PLAN_NAME)
        try:
            result = write_yfinance_demo_plan_files(plan_path)
            added = self.add_download_plan_entries_from_file(result.plan_path)
        except Exception as exc:  # pragma: no cover - UI handoff records the concrete failure for users/agents.
            log_exception("ui_yfinance_demo_plan_failed", exc, component="ui.yfinance")
            messagebox.showerror(self.tr("yfinance Demo plan 失敗", "yfinance demo plan failed"), str(exc))
            return

        summary = self.tr(
            f"yfinance 離線 Demo plan 已建立，已加入 {added} 個下載項目。",
            f"yfinance offline demo plan created; added {added} download item(s).",
        )
        self.status_var.set(summary)
        log_event(
            "ui_yfinance_demo_plan_created",
            summary,
            component="ui.yfinance",
            context={
                "plan_path": str(result.plan_path),
                "fixture_path": str(result.fixture_path),
                "symbols": list(result.symbols),
                "added_to_plan": added,
            },
        )
        messagebox.showinfo(
            self.tr("yfinance Demo plan 已建立", "yfinance demo plan created"),
            self.tr(
                f"{summary}\n\nPlan：{result.plan_path}\nFixture CSV：{result.fixture_path}\n\n下一步：在下載計畫按「開始」，完成後再按「匯入」。這條路徑只使用本機 fixture，不會連到 Yahoo。",
                f"{summary}\n\nPlan: {result.plan_path}\nFixture CSV: {result.fixture_path}\n\nNext: click Start in the download plan, then Import after download finishes. This path only uses a local fixture and does not contact Yahoo.",
            ),
        )

    def open_yfinance_live_plan_dialog(self) -> None:
        # live yfinance 是明確 opt-in 的窄入口；UI 先建立 CSV-backed plan，不在背景排程或 crawler 自動抓取。
        dialog = Toplevel(self.root)
        dialog.title(self.tr("建立 yfinance live plan", "Create yfinance live plan"))
        dialog.geometry("820x585")
        dialog.configure(bg=COLORS["panel"])
        dialog.transient(self.root)

        symbols_var = StringVar(value="AAPL")
        period_var = StringVar(value="5d")
        interval_var = StringVar(value="1d")
        query_window_var = StringVar(value=DEFAULT_YFINANCE_QUERY_WINDOW_PRESET)
        storage_target_var = StringVar(value=DEFAULT_YFINANCE_STORAGE_TARGET)
        retention_days_var = StringVar(value=str(DEFAULT_YFINANCE_RETENTION_DAYS))
        acknowledge_var = BooleanVar(value=False)

        ttk.Label(dialog, text=self.tr("建立 yfinance live plan", "Create yfinance live plan"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            dialog,
            text=self.tr(
                "這會呼叫本機 Python 環境中的選用 yfinance 套件，先寫成本機 CSV，再把 file-backed plan 加入下載計畫。它不是官方商用資料授權，也不會自動匯入或背景持續抓取。",
                "This calls the optional yfinance package in the local Python environment, writes a local CSV first, then adds a file-backed plan to the download plan. It is not an official commercial data license and will not auto-import or run in the background.",
            ),
            style="DetailMuted.TLabel",
            wraplength=760,
        ).pack(anchor="w", padx=24, pady=(0, 14))

        form = ttk.Frame(dialog, style="Panel.TFrame")
        form.pack(fill=X, padx=24, pady=(0, 12))
        query_window_row = ttk.Frame(form, style="Panel.TFrame")
        query_window_row.pack(fill=X, pady=5)
        ttk.Label(query_window_row, text=self.tr("查詢視窗", "Query window"), style="DetailMuted.TLabel", width=12).pack(side=LEFT)
        query_window_combo = ttk.Combobox(
            query_window_row,
            textvariable=query_window_var,
            values=tuple(YFINANCE_QUERY_WINDOW_PRESETS),
            state="readonly",
            width=28,
        )
        query_window_combo.pack(side=LEFT, padx=(8, 10))
        ttk.Label(
            query_window_row,
            text=self.tr("預設會帶入 period/interval；手動改欄位仍可覆寫", "Preset fills period/interval; manual edits can override"),
            style="DetailMuted.TLabel",
        ).pack(side=LEFT)

        def apply_query_window_preset(_event: object | None = None) -> None:
            # preset 只幫使用者選擇圖表友善的 period/interval，不代表排程或自動 refresh。
            preset = YFINANCE_QUERY_WINDOW_PRESETS.get(query_window_var.get())
            if preset is None:
                return
            period_var.set(preset.period)
            interval_var.set(preset.interval)

        query_window_combo.bind("<<ComboboxSelected>>", apply_query_window_preset)
        apply_query_window_preset()
        storage_row = ttk.Frame(form, style="Panel.TFrame")
        storage_row.pack(fill=X, pady=5)
        ttk.Label(storage_row, text=self.tr("儲存目標", "Storage target"), style="DetailMuted.TLabel", width=12).pack(side=LEFT)
        ttk.Combobox(
            storage_row,
            textvariable=storage_target_var,
            values=(DEFAULT_YFINANCE_STORAGE_TARGET, *YFINANCE_STORAGE_TARGET_PROFILES),
            state="readonly",
            width=28,
        ).pack(side=LEFT, padx=(8, 10))
        ttk.Label(
            storage_row,
            text=self.tr(
                "只寫入 metadata；不會直接寫 MySQL/Parquet/ClickHouse",
                "Metadata only; does not write MySQL/Parquet/ClickHouse",
            ),
            style="DetailMuted.TLabel",
        ).pack(side=LEFT, fill=X, expand=True)

        for label, variable, hint in [
            (self.tr("股票代號", "Symbols"), symbols_var, self.tr("例：AAPL, MSFT；逗號或空白分隔", "Example: AAPL, MSFT; comma or space separated")),
            (self.tr("查詢期間", "Period"), period_var, self.tr("例：5d、1mo、1y、ytd、max", "Example: 5d, 1mo, 1y, ytd, max")),
            (self.tr("時間間隔", "Interval"), interval_var, self.tr("例：1d、1h、5m", "Example: 1d, 1h, 5m")),
            (self.tr("保留天數", "Retention days"), retention_days_var, self.tr("只寫入 plan metadata，不會自動刪檔", "Metadata only; files are not auto-deleted")),
        ]:
            row = ttk.Frame(form, style="Panel.TFrame")
            row.pack(fill=X, pady=5)
            ttk.Label(row, text=label, style="DetailMuted.TLabel", width=12).pack(side=LEFT)
            ttk.Entry(row, textvariable=variable).pack(side=LEFT, fill=X, expand=True, padx=(8, 10))
            ttk.Label(row, text=hint, style="DetailMuted.TLabel").pack(side=LEFT)

        ttk.Checkbutton(
            dialog,
            text=self.tr(
                "我已理解 Yahoo/yfinance 是非官方 personal/research-only 路徑，並會自行確認使用條款。",
                "I understand Yahoo/yfinance is an unofficial personal/research-only path and will review the terms myself.",
            ),
            variable=acknowledge_var,
        ).pack(anchor="w", padx=24, pady=(0, 10))
        ttk.Label(dialog, text=YFINANCE_LIVE_WARNING, style="DetailMuted.TLabel", wraplength=760).pack(anchor="w", padx=24, pady=(0, 14))

        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))

        def create_live_plan() -> None:
            if not acknowledge_var.get():
                messagebox.showwarning(
                    self.tr("需要明確確認", "Acknowledgement required"),
                    self.tr("請先勾選確認框，表示你理解這是非官方、personal/research-only 的 live fetch。", "Check the acknowledgement first; this is an unofficial personal/research-only live fetch."),
                    parent=dialog,
                )
                return
            try:
                symbols = yfinance_symbols_from_ui_text(symbols_var.get())
                result = write_yfinance_live_plan_files(
                    state_file(YFINANCE_LIVE_PLAN_NAME),
                    symbols=symbols,
                    period=period_var.get(),
                    interval=interval_var.get(),
                    retention_days=int(retention_days_var.get()),
                    query_window_preset=query_window_var.get(),
                    storage_target=storage_target_var.get(),
                    acknowledge_unofficial=True,
                )
                added = self.add_download_plan_entries_from_file(result.plan_path)
            except Exception as exc:  # pragma: no cover - depends on optional yfinance/runtime/network and is surfaced to the UI.
                log_exception("ui_yfinance_live_plan_failed", exc, component="ui.yfinance")
                messagebox.showerror(self.tr("yfinance live plan 失敗", "yfinance live plan failed"), str(exc), parent=dialog)
                return

            summary = self.tr(
                f"yfinance live CSV plan 已建立，已加入 {added} 個下載項目。",
                f"yfinance live CSV plan created; added {added} download item(s).",
            )
            self.status_var.set(summary)
            log_event(
                "ui_yfinance_live_plan_created",
                summary,
                component="ui.yfinance",
                context={
                    "plan_path": str(result.plan_path),
                    "csv_path": str(result.csv_path),
                    "symbols": list(result.symbols),
                    "period": result.period,
                    "interval": result.interval,
                    "retention_days": result.retention_days,
                    "query_window": result.query_window_preset,
                    "storage_target": result.storage_target,
                    "added_to_plan": added,
                },
            )
            messagebox.showinfo(
                self.tr("yfinance live plan 已建立", "yfinance live plan created"),
                self.tr(
                    f"{summary}\n\nPlan：{result.plan_path}\nCSV：{result.csv_path}\n\n下一步：在下載計畫按「開始」，完成後再按「匯入」。UI 不會自動重複抓取或背景排程。",
                    f"{summary}\n\nPlan: {result.plan_path}\nCSV: {result.csv_path}\n\nNext: click Start in the download plan, then Import after download finishes. The UI will not repeat the fetch automatically or schedule background runs.",
                ),
                parent=dialog,
            )
            dialog.destroy()

        ttk.Button(actions, text=self.tr("建立 plan", "Create plan"), style="Action.TButton", command=create_live_plan).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("取消", "Cancel"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)

    def open_yfinance_storage_review_dialog(self) -> None:
        # storage review 是 live plan 之後的「審查交接」入口；這裡只產出 JSON/SQL 草稿，禁止直接觸發資料庫寫入。
        dialog = Toplevel(self.root)
        dialog.title(self.tr("產生 yfinance 儲存審查 dry-run", "Create yfinance storage review dry-run"))
        dialog.geometry("840x500")
        dialog.configure(bg=COLORS["panel"])
        dialog.transient(self.root)

        plan_var = StringVar(value=str(state_file(YFINANCE_LIVE_PLAN_NAME)))
        review_var = StringVar(value=str(state_file(YFINANCE_STORAGE_REVIEW_NAME)))
        handoff_var = StringVar(value=str(state_file(YFINANCE_STORAGE_HANDOFF_NAME)))
        storage_target_var = StringVar(value=DEFAULT_YFINANCE_STORAGE_TARGET)

        ttk.Label(dialog, text=self.tr("產生 yfinance 儲存審查 dry-run", "Create yfinance storage review dry-run"), style="DetailTitle.TLabel").pack(anchor="w", padx=24, pady=(22, 8))
        ttk.Label(
            dialog,
            text=self.tr(
                "這會讀取既有 yfinance plan，輸出 storage review JSON，並在需要時寫出 dry-run SQL/命令草稿。launcher 不會連線、不會建表、不會匯入，也不會把審查檔視為已執行。",
                "This reads an existing yfinance plan and writes a storage review JSON plus dry-run SQL/command sketches when needed. The launcher will not connect, create tables, import rows, or treat the review as executed.",
            ),
            style="DetailMuted.TLabel",
            wraplength=760,
        ).pack(anchor="w", padx=24, pady=(0, 14))

        form = ttk.Frame(dialog, style="Panel.TFrame")
        form.pack(fill=X, padx=24, pady=(0, 12))
        for label, variable, hint in [
            (self.tr("plan 路徑", "Plan path"), plan_var, self.tr("預設讀取剛建立的 yfinance live plan", "Defaults to the yfinance live plan path")),
            (self.tr("review 輸出", "Review output"), review_var, self.tr("若目標需要 SQL，會輸出同名 .dry_run.sql", "If the target needs SQL, a matching .dry_run.sql is written")),
            (self.tr("handoff 輸出", "Handoff output"), handoff_var, self.tr("給人類 / DBA 審查的 Markdown", "Markdown for human / DBA review")),
        ]:
            row = ttk.Frame(form, style="Panel.TFrame")
            row.pack(fill=X, pady=6)
            ttk.Label(row, text=label, style="DetailMuted.TLabel", width=12).pack(side=LEFT)
            ttk.Entry(row, textvariable=variable).pack(side=LEFT, fill=X, expand=True, padx=(8, 10))
            ttk.Label(row, text=hint, style="DetailMuted.TLabel").pack(side=LEFT)

        target_row = ttk.Frame(form, style="Panel.TFrame")
        target_row.pack(fill=X, pady=6)
        ttk.Label(target_row, text=self.tr("審查目標", "Review target"), style="DetailMuted.TLabel", width=12).pack(side=LEFT)
        ttk.Combobox(
            target_row,
            textvariable=storage_target_var,
            values=(DEFAULT_YFINANCE_STORAGE_TARGET, *YFINANCE_STORAGE_TARGET_PROFILES),
            state="readonly",
            width=28,
        ).pack(side=LEFT, padx=(8, 10))
        ttk.Label(
            target_row,
            text=self.tr("auto 會沿用 plan 內建議；其他值只覆寫審查檔，不會執行寫入。", "auto follows the plan suggestion; other values only override the review artifact."),
            style="DetailMuted.TLabel",
        ).pack(side=LEFT, fill=X, expand=True)

        ttk.Label(dialog, text=YFINANCE_LIVE_WARNING, style="DetailMuted.TLabel", wraplength=760).pack(anchor="w", padx=24, pady=(0, 14))

        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.pack(fill=X, padx=24, pady=(0, 20))

        def create_storage_review() -> None:
            try:
                plan_path, review_path = yfinance_storage_review_paths_from_ui(plan_var.get(), review_var.get())
                handoff_path = yfinance_project_path_from_ui_text(handoff_var.get(), "Handoff")
                result = write_yfinance_storage_review_file(
                    plan_path,
                    review_path,
                    storage_target=storage_target_var.get(),
                )
                handoff_result = write_yfinance_storage_handoff_file(result.review_path, handoff_path)
            except Exception as exc:
                log_exception("ui_yfinance_storage_review_failed", exc, component="ui.yfinance")
                messagebox.showerror(self.tr("yfinance 儲存審查失敗", "yfinance storage review failed"), str(exc), parent=dialog)
                return

            sql_message = f"\nDry-run SQL: {result.dry_run_sql_path}" if result.dry_run_sql_path else ""
            summary = self.tr(
                f"yfinance 儲存審查已建立，目標：{result.storage_target}，待審查動作：{result.action_count}，並已產生 handoff。",
                f"yfinance storage review created; target: {result.storage_target}; review actions: {result.action_count}; handoff created.",
            )
            self.status_var.set(summary)
            log_event(
                "ui_yfinance_storage_review_created",
                summary,
                component="ui.yfinance",
                context={
                    "plan_path": str(result.plan_path),
                    "review_path": str(result.review_path),
                    "handoff_path": str(handoff_result.handoff_path),
                    "dry_run_sql_path": str(result.dry_run_sql_path or ""),
                    "storage_target": result.storage_target,
                    "action_count": result.action_count,
                    "dry_run": True,
                    "will_write_database": False,
                },
            )
            messagebox.showinfo(
                self.tr("yfinance 儲存審查已建立", "yfinance storage review created"),
                self.tr(
                    f"{summary}\n\nReview: {result.review_path}\nHandoff: {handoff_result.handoff_path}{sql_message}\n\n下一步是人工審查 handoff / review JSON / dry-run SQL；launcher 這一步不會連線、不會建表、不會匯入。",
                    f"{summary}\n\nReview: {result.review_path}\nHandoff: {handoff_result.handoff_path}{sql_message}\n\nNext: review the handoff / JSON / dry-run SQL manually. This launcher step does not connect, create tables, or import rows.",
                ),
                parent=dialog,
            )
            dialog.destroy()

        ttk.Button(actions, text=self.tr("產生審查檔", "Create review"), style="Action.TButton", command=create_storage_review).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("取消", "Cancel"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)
