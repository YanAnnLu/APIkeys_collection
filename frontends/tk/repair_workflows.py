"""Tk repair/verification workflows for RuRuKa Asset Launcher.

這個 mixin 集中下載 manifest 與 database asset 的修復面板，讓主視窗只保留入口。
"""

from __future__ import annotations

import webbrowser
from tkinter import BOTH, END, LEFT, RIGHT, WORD, X, StringVar, Text, Toplevel, messagebox
from tkinter import ttk

import APIkeys_collection as core
from api_launcher.database_repair import (
    database_repair_sql_path_for_asset,
    reimport_missing_sqlite_table_asset,
    supported_reimport_source_formats_label,
    write_missing_sql_table_repair_dry_run,
)
from api_launcher.database_self_check import DatabaseAssetVerifier, DatabaseSelfCheckIssue, database_self_check_issues
from api_launcher.downloads.repair import (
    ManifestVerification,
    RepairSuggestion,
    download_repair_agent_payload,
    log_download_manifest_verification_completed as log_download_manifest_verification_event,
    log_download_requeue_requested as log_download_requeue_event,
    repair_summary,
    repair_suggestion_for_result,
    scan_download_manifests,
)
from api_launcher.event_log import log_event, log_exception
from api_launcher.manifests import read_manifest
from api_launcher.paths import DOWNLOADS_DIR, state_file
from api_launcher.data_store_connections import data_store_profiles_from_config
from frontends.tk.provider_display import provider_display_label
from frontends.tk.ui_config import COLORS, DB_PATH
from frontends.tk.ui_helpers import database_sql_dry_run_available


def repair_provider_label(provider_id: object) -> str:
    """Return the repair-panel provider label without hiding the raw id in detail panes."""

    return provider_display_label(None, str(provider_id or "").strip())


def repair_asset_title(provider_id: object, asset_name: object) -> str:
    """Compose a user-facing repair title while keeping ids explicit as provenance."""

    asset_label = str(asset_name or "").strip() or "-"
    return f"{repair_provider_label(provider_id)} / {asset_label}"


def repair_database_connection_title(provider_id: object, asset_kind: object, asset_name: object) -> str:
    """Compose the short database connection title shown above editable registry fields."""

    kind_label = str(asset_kind or "").strip() or "-"
    asset_label = str(asset_name or "").strip() or "-"
    return f"{repair_provider_label(provider_id)} / {kind_label} / {asset_label}"


class RepairWorkflowMixin:
    """封裝修復/驗證資產面板，避免 launcher_ui.py 繼續承擔大型 Toplevel 流程。"""

    def verify_download_manifests(self) -> None:
        results, summary = self.sync_manifest_verification()
        self.status_var.set(self.tr(f"檔案健康狀態：{summary}", f"File health: {summary}"))
        if any(result.needs_repair for result in results):
            messagebox.showwarning(self.tr("檔案驗證", "File verification"), self.tr(f"需要修復：{summary}", f"Repair needed: {summary}"))

    def sync_manifest_verification(self) -> tuple[list[object], dict[str, int]]:
        results = scan_download_manifests()
        summary = repair_summary(results)
        agent_payload = download_repair_agent_payload(results)
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
        self.log_download_manifest_verification_completed(agent_payload)
        return results, summary

    def log_download_manifest_verification_completed(self, payload: dict[str, object]) -> None:
        log_download_manifest_verification_event(
            payload,
            db_path=DB_PATH,
            downloads_root=DOWNLOADS_DIR,
            logger=log_event,
        )

    def log_download_requeue_requested(
        self,
        result: ManifestVerification,
        suggestion: RepairSuggestion,
        *,
        outcome: str,
        job_id: str = "",
        error: BaseException | None = None,
    ) -> None:
        log_download_requeue_event(
            result,
            suggestion,
            outcome=outcome,
            job_id=job_id,
            error_type=type(error).__name__ if error is not None else "",
            error_message=str(error) if error is not None else "",
            db_path=DB_PATH,
            downloads_root=DOWNLOADS_DIR,
            logger=log_event,
        )

    def sync_database_asset_verification(
        self,
        provider_ids: list[str] | None = None,
    ) -> tuple[dict[str, int], list[DatabaseSelfCheckIssue]]:
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            summary = repository.verify_provider_assets(
                provider_ids,
                verifier=DatabaseAssetVerifier(),
                asset_kinds=("database", "table"),
            )
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
                    repair_provider_label(result.provider_id),
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
                    repair_provider_label(issue.provider_id),
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
                dry_run_path = database_repair_sql_path_for_asset(selected.asset_id, state_file("database_repair")) if database_sql_dry_run_available(suggestion) else "-"
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
                            f"sql_dry_run_available: {database_sql_dry_run_available(suggestion)}",
                            f"sql_dry_run_path: {dry_run_path}",
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
                self.log_download_requeue_requested(selected, suggestion, outcome="not_requeueable")
                messagebox.showinfo(self.tr("修復", "Repair"), suggestion.description)
                return
            plan_entry = dict(suggestion.plan_entry)
            provider_id = str(plan_entry.get("provider_id") or "")
            provider_label = repair_provider_label(provider_id)
            if not self.prepare_provider_for_download(provider_id):
                self.log_download_requeue_requested(selected, suggestion, outcome="already_active")
                self.status_var.set(self.tr(f"{provider_label} 的修復下載已經在執行。", f"Repair download is already active for {provider_label}."))
                return
            try:
                job = self.download_queue.submit(plan_entry)
            except Exception as exc:
                self.log_download_requeue_requested(selected, suggestion, outcome="failed", error=exc)
                messagebox.showerror(self.tr("修復", "Repair"), self.tr(f"無法重新排修復下載：{type(exc).__name__}: {exc}", f"Could not requeue repair download: {type(exc).__name__}: {exc}"))
                return
            self.download_jobs_by_provider[provider_id] = job.job_id
            self.download_providers_by_job[job.job_id] = provider_id
            self.download_plan_entries_by_provider[provider_id] = dict(plan_entry)
            self.plan_provider_by_key[provider_id] = provider_id
            self.download_status_by_provider[provider_id] = ("queued", "0%", str(plan_entry.get("target_path") or ""))
            self.update_download_jobs_panel()
            self.log_download_requeue_requested(selected, suggestion, outcome="queued", job_id=job.job_id)
            self.status_var.set(self.tr(f"已重新排修復下載：{provider_label}", f"Repair download queued: {provider_label}"))

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
            elif database_sql_dry_run_available(suggestion):
                next_step += self.tr("\n\n可按「產生 dry-run SQL」輸出審核用 SQL 檔；這不會連線或修改遠端資料庫。", "\n\nUse Write dry-run SQL to write a reviewable SQL file; this will not connect to or modify the remote database.")
            elif suggestion.action_id.startswith("restore_or_reimport"):
                next_step += self.tr("\n\n在 adapter 能證明 ownership 之前，這個 UI 不會自動刪除或重建 SQL 物件。", "\n\nThis UI will not delete or recreate SQL objects automatically until an adapter proves ownership.")
            messagebox.showinfo(
                self.tr("資料庫修復建議", "Database repair suggestion"),
                f"{repair_asset_title(selected.provider_id, selected.asset_name)}\n\n{self.localized_database_repair_label(suggestion)}\n{next_step}",
            )

        def reimport_selected_database_asset() -> None:
            selection = database_table.selection()
            selected = database_issue_by_iid.get(str(selection[0])) if selection else None
            if selected is None:
                messagebox.showinfo(self.tr("資料庫修復", "Database repair"), self.tr("請先選取一列資料庫問題。", "Select a database row first."))
                return
            suggestion = selected.repair_suggestion()
            if suggestion.action_id != "restore_or_reimport_table":
                messagebox.showinfo(
                    self.tr("資料庫修復", "Database repair"),
                    self.tr(
                        f"這個動作目前只支援從已記錄 manifest 重新匯入缺失的 SQLite table。\n支援格式：{supported_reimport_source_formats_label()}",
                        f"This action currently only reimports a missing SQLite table from a recorded manifest.\nSupported formats: {supported_reimport_source_formats_label()}",
                    ),
                    parent=dialog,
                )
                return
            if not suggestion.can_auto_repair:
                messagebox.showinfo(
                    self.tr("資料庫修復", "Database repair"),
                    self.tr(
                        (
                            "這列目前沒有可自動重新匯入的安全條件。\n\n"
                            "只有缺失的 SQLite table，且 registry 裡記錄了健康 manifest 與支援格式時，才會啟用此動作。"
                        ),
                        (
                            "This row does not currently meet the safe auto-reimport conditions.\n\n"
                            "This action is enabled only for a missing SQLite table with a recorded manifest and supported source format."
                        ),
                    ),
                    parent=dialog,
                )
                return
            if not messagebox.askyesno(
                self.tr("重新匯入資料表", "Reimport table"),
                self.tr(
                    (
                        f"要從既有 manifest 重新匯入這張缺失的資料表嗎？\n\n"
                        f"{repair_asset_title(selected.provider_id, selected.asset_name)}\n\n"
                        f"支援格式：{supported_reimport_source_formats_label()}\n\n"
                        "這個動作只會在 table 不存在時建立它；不會 DROP 或覆蓋既有 table。"
                    ),
                    (
                        f"Reimport this missing table from its recorded manifest?\n\n"
                        f"{repair_asset_title(selected.provider_id, selected.asset_name)}\n\n"
                        f"Supported formats: {supported_reimport_source_formats_label()}\n\n"
                        "This only creates the table when it is missing. It will not DROP or replace an existing table.",
                    ),
                ),
                parent=dialog,
            ):
                return
            conn = self._connect()
            try:
                repository = core.ApiCatalogRepository(conn)
                result = reimport_missing_sqlite_table_asset(repository, selected.asset_id)
            except Exception as exc:
                log_exception(
                    "database_table_reimport_failed",
                    exc,
                    component="ui.repair",
                    context={"asset_id": selected.asset_id, "provider_id": selected.provider_id},
                )
                messagebox.showerror(self.tr("重新匯入資料表", "Reimport table"), str(exc), parent=dialog)
                return
            finally:
                conn.close()
            dialog.destroy()
            self.reload_data()
            self.status_var.set(self.tr(
                f"已重新匯入 {result.table_name}，列數 {result.rows_imported}，正在重新自檢。",
                f"Reimported {result.table_name} with {result.rows_imported} rows; rerunning self-check.",
            ))
            self.open_repair_panel()

        def write_selected_database_repair_sql() -> None:
            selection = database_table.selection()
            selected = database_issue_by_iid.get(str(selection[0])) if selection else None
            if selected is None:
                messagebox.showinfo(self.tr("資料庫修復", "Database repair"), self.tr("請先選取一列資料庫問題。", "Select a database row first."))
                return
            suggestion = selected.repair_suggestion()
            if not database_sql_dry_run_available(suggestion):
                messagebox.showinfo(
                    self.tr("產生 dry-run SQL", "Write dry-run SQL"),
                    self.tr(
                        (
                            "這列目前不符合產生 SQL 草稿的條件。\n\n"
                            "只有 MySQL/PostgreSQL 缺失資料表，且 registry 記錄了健康 CSV/JSON/GeoJSON 類 manifest 時，"
                            "才會啟用此動作。"
                        ),
                        (
                            "This row cannot currently write a SQL draft.\n\n"
                            "The action is available only for missing MySQL/PostgreSQL table assets with a healthy recorded CSV/JSON/GeoJSON manifest."
                        ),
                    ),
                    parent=dialog,
                )
                return
            output_path = database_repair_sql_path_for_asset(selected.asset_id, state_file("database_repair"))
            if not messagebox.askyesno(
                self.tr("產生 dry-run SQL", "Write dry-run SQL"),
                self.tr(
                    (
                        f"要為這筆缺失資料表產生 dry-run SQL 嗎？\n\n"
                        f"{repair_asset_title(selected.provider_id, selected.asset_name)}\n\n"
                        f"輸出位置：{output_path}\n\n"
                        "這個動作只會寫出 SQL 檔案供審核；不會連線、不會執行 SQL，也不會修改遠端資料庫。"
                    ),
                    (
                        f"Write dry-run SQL for this missing table?\n\n"
                        f"{repair_asset_title(selected.provider_id, selected.asset_name)}\n\n"
                        f"Output: {output_path}\n\n"
                        "This only writes a SQL file for review. It will not connect, execute SQL, or modify the remote database."
                    ),
                ),
                parent=dialog,
            ):
                return
            try:
                conn = self._connect()
                try:
                    repository = core.ApiCatalogRepository(conn)
                    result = write_missing_sql_table_repair_dry_run(repository, selected.asset_id, output_path)
                finally:
                    conn.close()
            except Exception as exc:
                log_exception(
                    "database_sql_dry_run_failed",
                    exc,
                    component="ui.repair",
                    context={"asset_id": selected.asset_id, "provider_id": selected.provider_id},
                )
                messagebox.showerror(self.tr("產生 dry-run SQL", "Write dry-run SQL"), str(exc), parent=dialog)
                return
            result_payload = result.to_dict()
            log_event(
                "database_repair_completed",
                f"Database repair dry-run SQL written: {selected.asset_id}",
                component="ui.repair",
                context={
                    "action": result.action_id,
                    "result_count": 1,
                    "results": [result_payload],
                },
            )
            self.status_var.set(self.tr(
                f"已產生 dry-run SQL：{result.sql_path}",
                f"Dry-run SQL written: {result.sql_path}",
            ))
            messagebox.showinfo(
                self.tr("已產生 dry-run SQL", "Dry-run SQL written"),
                self.tr(
                    (
                        f"已寫出 SQL 草稿：\n{result.sql_path}\n\n"
                        f"預計列數：{result.rows_planned}\n"
                        "請先人工審核後，再決定是否在目標資料庫執行。"
                    ),
                    (
                        f"Wrote SQL draft:\n{result.sql_path}\n\n"
                        f"Planned rows: {result.rows_planned}\n"
                        "Review it manually before running it against the target database."
                    ),
                ),
                parent=dialog,
            )

        def edit_selected_database_connection() -> None:
            selection = database_table.selection()
            selected = database_issue_by_iid.get(str(selection[0])) if selection else None
            if selected is None:
                messagebox.showinfo(self.tr("資料庫連線設定", "Database connection settings"), self.tr("請先選取一列資料庫問題。", "Select a database row first."))
                return
            profiles = data_store_profiles_from_config(core.load_integration_config())
            engine = selected.engine.strip().lower()

            def profile_matches_asset(profile: object) -> bool:
                profile_engine = str(getattr(profile, "engine", "")).strip().lower()
                if not engine:
                    return True
                if engine in {"postgres", "postgresql"}:
                    return profile_engine in {"postgres", "postgresql"}
                if engine in {"mysql", "mariadb"}:
                    return profile_engine in {"mysql", "mariadb"}
                return profile_engine == engine

            profile_ids = [profile.profile_id for profile in profiles if profile_matches_asset(profile)]
            if selected.data_store_profile_id and selected.data_store_profile_id not in profile_ids:
                profile_ids.insert(0, selected.data_store_profile_id)
            if not profile_ids:
                profile_ids = [profile.profile_id for profile in profiles]

            editor = Toplevel(dialog)
            editor.title(self.tr("資料庫資產連線設定", "Database asset connection"))
            editor.configure(bg=COLORS["panel"])
            editor.transient(dialog)
            editor.grab_set()
            editor.minsize(560, 320)
            frame = ttk.Frame(editor, style="Panel.TFrame")
            frame.pack(fill=BOTH, expand=True, padx=22, pady=22)
            ttk.Label(frame, text=self.tr("資料庫資產連線設定", "Database asset connection"), style="DetailTitle.TLabel").pack(anchor="w")
            ttk.Label(
                frame,
                text=self.tr(
                    (
                        "這只會更新 launcher registry 裡的 profile/schema 指向，"
                        "不會刪除、建立或改寫任何資料庫物件。儲存後會重新跑一次自檢。"
                    ),
                    "This only updates the registry profile/schema pointer. It will not delete, create, or rewrite database objects. A self-check runs again after saving.",
                ),
                style="DetailMuted.TLabel",
                wraplength=500,
            ).pack(anchor="w", fill=X, pady=(8, 16))
            ttk.Label(frame, text=repair_database_connection_title(selected.provider_id, selected.asset_kind, selected.asset_name), style="DetailSection.TLabel").pack(anchor="w", pady=(0, 8))

            profile_var = StringVar(value=selected.data_store_profile_id or profile_ids[0])
            schema_var = StringVar(value=selected.schema_name)
            ttk.Label(frame, text=self.tr("Data-store profile", "Data-store profile"), style="DetailSection.TLabel").pack(anchor="w", pady=(8, 4))
            ttk.Combobox(frame, values=profile_ids, textvariable=profile_var, state="readonly", font=("Helvetica", 12)).pack(fill=X)
            ttk.Label(frame, text=self.tr("Schema 名稱（SQLite 可留白）", "Schema name (leave blank for SQLite)"), style="DetailSection.TLabel").pack(anchor="w", pady=(14, 4))
            ttk.Entry(frame, textvariable=schema_var, font=("Helvetica", 12)).pack(fill=X)

            def save_connection_metadata() -> None:
                try:
                    conn = self._connect()
                    try:
                        repository = core.ApiCatalogRepository(conn)
                        changed = repository.update_database_asset_connection_metadata(
                            selected.asset_id,
                            data_store_profile_id=profile_var.get().strip(),
                            schema_name=schema_var.get().strip(),
                        )
                    finally:
                        conn.close()
                except ValueError as exc:
                    messagebox.showerror(self.tr("資料庫連線設定", "Database connection settings"), str(exc), parent=editor)
                    return
                if not changed:
                    messagebox.showerror(
                        self.tr("資料庫連線設定", "Database connection settings"),
                        self.tr("找不到這筆資料庫資產，可能已被其他流程更新。", "The database asset was not found; it may have been updated elsewhere."),
                        parent=editor,
                    )
                    return
                editor.destroy()
                dialog.destroy()
                self.status_var.set(self.tr("已更新資料庫資產連線設定，正在重新自檢。", "Database asset connection updated; rerunning self-check."))
                self.open_repair_panel()

            buttons = ttk.Frame(frame, style="Panel.TFrame")
            buttons.pack(fill=X, pady=(18, 0))
            ttk.Button(buttons, text=self.tr("儲存並重新自檢", "Save and recheck"), style="Action.TButton", command=save_connection_metadata).pack(side=RIGHT)
            ttk.Button(buttons, text=self.tr("取消", "Cancel"), style="Action.TButton", command=editor.destroy).pack(side=RIGHT, padx=(0, 10))

        def unmanage_selected_database_asset() -> None:
            selection = database_table.selection()
            selected = database_issue_by_iid.get(str(selection[0])) if selection else None
            if selected is None:
                messagebox.showinfo(self.tr("資料庫資產", "Database asset"), self.tr("請先選取一列資料庫問題。", "Select a database row first."))
                return
            if not messagebox.askyesno(
                self.tr("停止追蹤資料庫資產", "Stop tracking database asset"),
                self.tr(
                    (
                        f"要停止追蹤這筆資料庫資產嗎？\n\n"
                        f"{repair_asset_title(selected.provider_id, selected.asset_name)}\n\n"
                        "這只會把 launcher registry 裡的單一資產標成 unmanaged，"
                        "不會刪除資料庫、DROP table，或移動任何檔案。"
                    ),
                    (
                        f"Stop tracking this database asset?\n\n"
                        f"{repair_asset_title(selected.provider_id, selected.asset_name)}\n\n"
                        "This only marks one registry asset as unmanaged. It will not delete a database, DROP a table, or move files."
                    ),
                ),
                parent=dialog,
            ):
                return
            conn = self._connect()
            try:
                repository = core.ApiCatalogRepository(conn)
                changed = repository.unmanage_database_asset(selected.asset_id)
            finally:
                conn.close()
            if not changed:
                messagebox.showerror(
                    self.tr("資料庫資產", "Database asset"),
                    self.tr("找不到這筆資料庫資產，可能已被其他流程更新。", "The database asset was not found; it may have been updated elsewhere."),
                    parent=dialog,
                )
                return
            dialog.destroy()
            self.reload_data()
            self.status_var.set(self.tr("已停止追蹤選取的資料庫資產，正在重新自檢。", "Selected database asset is now unmanaged; rerunning self-check."))
            self.open_repair_panel()

        ttk.Button(actions, text=self.tr("重新整理", "Refresh"), style="Action.TButton", command=lambda: (dialog.destroy(), self.open_repair_panel())).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("重新排下載", "Requeue selected download"), style="Action.TButton", command=requeue_selected_result).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("顯示資料庫建議", "Show database suggestion"), style="Action.TButton", command=show_selected_database_suggestion).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("重新匯入資料表", "Reimport table"), style="Action.TButton", command=reimport_selected_database_asset).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("產生 dry-run SQL", "Write dry-run SQL"), style="Action.TButton", command=write_selected_database_repair_sql).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("調整資料庫連線", "Edit database connection"), style="Action.TButton", command=edit_selected_database_connection).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("停止追蹤", "Stop tracking"), style="Action.TButton", command=unmanage_selected_database_asset).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("資料儲存設定", "Data-store settings"), style="Action.TButton", command=self.open_data_store_connection_settings).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("開啟下載資料夾", "Open downloads folder"), style="Action.TButton", command=lambda: webbrowser.open(DOWNLOADS_DIR.as_uri())).pack(side=LEFT, padx=(0, 10))
        ttk.Button(actions, text=self.tr("關閉", "Close"), style="Action.TButton", command=dialog.destroy).pack(side=RIGHT)
        self.status_var.set(self.tr(f"檔案健康狀態：{summary}；資料庫問題={len(database_issues)}", f"File health: {summary}; database issues={len(database_issues)}"))
