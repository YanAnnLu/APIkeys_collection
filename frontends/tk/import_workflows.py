"""Tk import workflows for RuRuKa Asset Launcher.

這個 mixin 集中下載後匯入、本機檔案匯入、同名資料表策略與匯入狀態文案。
主視窗仍負責 widget 生命週期；真正的 manifest 驗證與 SQLite 匯入規則維持在 backend。
"""

from __future__ import annotations

import time
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import APIkeys_collection as core
from api_launcher.downloads.http import download_target_from_plan_entry
from api_launcher.downloads.repair import verify_manifest_file
from api_launcher.event_log import log_event, log_exception
from api_launcher.import_policies import UI_IMPORT_POLICY_CONFIG_KEY, normalized_ui_import_policy
from api_launcher.importers.csv_importer import (
    import_csv_manifest_to_sqlite,
    table_exists,
    table_name_for_manifest,
    unique_table_name,
)
from api_launcher.importers.json_importer import import_json_manifest_to_sqlite
from api_launcher.ingestion_pipeline import DownloadImportPipelineOptions, run_existing_download_import_slice
from api_launcher.integrations import save_integration_config
from api_launcher.manifests import read_manifest
from api_launcher.manual_import import (
    DEFAULT_MANUAL_LOCAL_PROVIDER_ID,
    ensure_manual_local_file_provider,
    register_local_file_manifest_asset,
    write_local_file_manifest as write_local_file_manifest_file,
)
from api_launcher.paths import state_file
from api_launcher.crawler_asset_display import plan_entry_content_status_payload
from frontends.tk.dialogs import ImportExistingTablePolicyDialog
from frontends.tk.background_jobs import single_flight_job_is_active, start_single_flight_thread
from frontends.tk.background_job_policies import MAX_TK_SQLITE_IMPORT_JOBS
from frontends.tk.provider_models import ProviderRow
from frontends.tk.ui_config import MANUAL_IMPORTS_DIR_NAME, curated_imports_path
from frontends.tk.ui_helpers import local_file_import_error_message, local_file_provenance_review_message


def import_plan_status_label(status: object, tr: object) -> str:
    """Render unknown import-plan statuses without exposing backend ids in Tk."""

    status_id = str(status or "").strip()
    labels = {
        "supported_after_download": ("可下載後匯入", "Import after download"),
        "adapter_review_required": ("需 Adapter 審核", "Adapter review needed"),
        "requires_unpack_or_adapter": ("需解壓或 Adapter", "Unpack or adapter needed"),
        "manual_review_required": ("需內容 Parser review", "Content parser review needed"),
    }
    zh, en = labels.get(status_id, ("匯入狀態待確認", "Import status pending"))
    return tr(zh, en) if callable(tr) else zh


class ImportWorkflowMixin:
    """封裝匯入相關 UI workflow；不直接改動 importer / pipeline 的安全規則。"""

    def notify_sqlite_import_busy(self) -> None:
        self.status_var.set(
            self.tr("SQLite 匯入已在執行中，請等待目前工作完成。", "SQLite import is already running; please wait for it to finish.")
        )

    def sqlite_import_queue_is_full(self) -> bool:
        active_jobs = getattr(self, "import_active_jobs", None)
        return isinstance(active_jobs, set) and len(active_jobs) >= MAX_TK_SQLITE_IMPORT_JOBS

    def load_import_existing_table_policy_preference(self) -> str:
        return normalized_ui_import_policy(core.load_integration_config().get(UI_IMPORT_POLICY_CONFIG_KEY))

    def save_import_existing_table_policy_preference(self, policy: str) -> None:
        # 匯入同名表策略會影響資料安全，因此保存前一律走 normalized_ui_import_policy。
        normalized = normalized_ui_import_policy(policy)
        self.preferred_import_existing_table_policy = normalized
        if hasattr(self, "plan_import_policy_var"):
            self.plan_import_policy_var.set(self.import_existing_table_policy_status_label(normalized))
        config = core.ensure_local_integration_config()
        config[UI_IMPORT_POLICY_CONFIG_KEY] = normalized
        save_integration_config(config)

    def import_status_label(
        self,
        plan_key: str,
        row: ProviderRow | None = None,
        option: core.DatasetVersionOption | None = None,
    ) -> str:
        remembered = self.import_status_by_plan_key.get(plan_key)
        if remembered:
            status, detail = remembered
            return f"{status}: {detail}" if detail else status
        entry = dict(self.download_plan_entries_by_provider.get(plan_key) or {})
        if not entry:
            row = row or self.row_by_provider_id(self.provider_id_for_plan_key(plan_key))
            if row is None:
                return self.tr("未準備", "Not ready")
            entry, build_error = self.plan_entry_for_item(row, option or self.plan_version_by_provider.get(plan_key), plan_key=plan_key)
            if entry is None:
                return self.tr(f"metadata 缺失: {build_error}", f"Missing metadata: {build_error}")
        import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
        status = str(import_plan.get("status") or "").strip()
        table_hint = str(import_plan.get("table_hint") or "").strip()
        if status == "supported_after_download":
            target_table = self.unique_import_table_name(curated_imports_path(), table_hint) if table_hint else ""
            table_label = f" -> {target_table}" if target_table else ""
            manifest_status = self.plan_entry_manifest_status(entry)
            if manifest_status == "ok":
                return self.tr(f"可匯入{table_label}", f"Ready to import{table_label}")
            if manifest_status:
                return self.tr(f"待下載/驗證{table_label}", f"Needs download/verify{table_label}")
            return self.tr(f"可匯入{table_label}", f"Ready to import{table_label}")
        if status == "adapter_review_required":
            adapter = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
            adapter_id = str(adapter.get("adapter_id") or "").strip()
            return self.tr(f"需 adapter: {adapter_id}" if adapter_id else "需 adapter", f"Adapter needed: {adapter_id}" if adapter_id else "Adapter needed")
        if status == "requires_unpack_or_adapter":
            adapter = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
            adapter_id = str(adapter.get("adapter_id") or "").strip()
            return self.tr(f"需解壓/adapter: {adapter_id}" if adapter_id else "需解壓/adapter", f"Unpack/adapter needed: {adapter_id}" if adapter_id else "Unpack/adapter needed")
        if status == "manual_review_required":
            content_status = plan_entry_content_status_payload(entry)
            label = str(content_status.get("display_label") or import_plan_status_label(status, self.tr))
            parser_id = str(content_status.get("parser_id") or "").strip()
            source_format = str(content_status.get("source_format") or "").strip()
            detail = " / ".join(part for part in (source_format, parser_id) if part)
            return self.tr(
                f"{label}: {detail}" if detail else label,
                f"Content parser needed: {detail}" if detail else "Content parser needed",
            )
        if status:
            return import_plan_status_label(status, self.tr)
        return self.tr("未支援自動匯入", "No auto import")

    def plan_entry_manifest_status(self, entry: dict[str, object]) -> str:
        try:
            target = download_target_from_plan_entry(entry)
        except Exception:
            return ""
        manifest_path = target.output_path.with_suffix(target.output_path.suffix + ".manifest.json")
        if not manifest_path.exists():
            return "missing"
        return verify_manifest_file(manifest_path).status

    def unique_import_table_name(self, sqlite_path: Path, table_name: str) -> str:
        base = table_name.strip() or "imported_dataset"
        if not table_exists(sqlite_path, base):
            return base
        for index in range(2, 1000):
            suffix = f"_{index}"
            candidate = f"{base[:63 - len(suffix)]}{suffix}"
            if not table_exists(sqlite_path, candidate):
                return candidate
        timestamp = time.strftime("%Y%m%d%H%M%S")
        suffix = f"_{timestamp}"
        return f"{base[:63 - len(suffix)]}{suffix}"

    def import_existing_table_policy_label(self, policy: str) -> str:
        labels = {
            "rename": self.tr("保留舊表，匯入成新表", "Keep old table and import as a new table"),
            "skip": self.tr("保留舊表，略過同名項目", "Keep old table and skip same-name items"),
            "replace": self.tr("覆蓋同名表", "Replace same-name table"),
        }
        return labels.get(normalized_ui_import_policy(policy), labels["rename"])

    def import_existing_table_policy_status_label(self, policy: str) -> str:
        return self.tr(
            f"匯入策略：{self.import_existing_table_policy_label(policy)}",
            f"Import policy: {self.import_existing_table_policy_label(policy)}",
        )

    def ask_import_existing_table_policy(self) -> str | None:
        return ImportExistingTablePolicyDialog(self).result

    def import_supported_plan_results_from_ui(self) -> None:
        items = self.selected_plan_items()
        if not items:
            messagebox.showinfo(self.tr("下載計畫是空的", "Download plan is empty"), self.tr("請先加入至少一個資料集/資料源。", "Add at least one dataset/source first."))
            return
        supported: list[tuple[str, dict[str, object], str]] = []
        skipped: list[str] = []
        for plan_key, row, option in items:
            # 匯入前先確認 plan entry 宣告可支援，避免 UI 直接把任意檔案塞進 SQLite。
            label = self.plan_item_label(plan_key, row, option)
            entry = dict(self.download_plan_entries_by_provider.get(plan_key) or {})
            if not entry:
                built_entry, build_error = self.plan_entry_for_item(row, option, plan_key=plan_key)
                if built_entry is None:
                    skipped.append(f"{label}: {build_error}")
                    continue
                entry = built_entry
            import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
            if import_plan.get("status") != "supported_after_download":
                reason = str(import_plan.get("reason") or import_plan.get("status") or self.tr("目前不是 CSV/JSON/GeoJSON 可自動匯入項目", "This item is not an auto-importable CSV/JSON/GeoJSON item"))
                skipped.append(f"{label}: {reason}")
                continue
            supported.append((plan_key, entry, label))

        if not supported:
            messagebox.showinfo(
                self.tr("沒有可匯入項目", "No importable items"),
                self.tr("目前下載計畫中沒有已支援的 CSV/JSON/GeoJSON 匯入項目。", "The current plan has no supported CSV/JSON/GeoJSON import items.")
                + self.import_skipped_detail_message(skipped, limit=6),
            )
            return

        sqlite_path = curated_imports_path()
        import_job_key = ("sqlite_import", str(sqlite_path), "")
        if single_flight_job_is_active(self, import_job_key, active_jobs_attr="import_active_jobs", on_duplicate=self.notify_sqlite_import_busy):
            return
        if self.sqlite_import_queue_is_full():
            self.notify_sqlite_import_busy()
            return
        existing_table_policy = self.ask_import_existing_table_policy()
        if existing_table_policy is None:
            return
        policy_hint = self.tr(
            f"\n\n同名資料表策略：{self.import_existing_table_policy_label(existing_table_policy)}",
            f"\n\nExisting table policy: {self.import_existing_table_policy_label(existing_table_policy)}",
        )
        confirmed = messagebox.askyesno(
            self.tr("匯入下載結果", "Import downloaded results"),
            self.tr(
                f"將把 {len(supported)} 個已支援項目匯入 SQLite：\n{sqlite_path}\n\n匯入前會先檢查 sidecar manifest 是否健康。",
                f"Import {len(supported)} supported items into SQLite:\n{sqlite_path}\n\nSidecar manifests will be verified before import.",
            )
            + policy_hint
            + self.import_skipped_detail_message(skipped),
        )
        if not confirmed:
            return

        self.status_var.set(self.tr(f"正在匯入 {len(supported)} 個下載結果到 SQLite...", f"Importing {len(supported)} downloaded results into SQLite..."))
        start_single_flight_thread(
            self,
            import_job_key,
            self.import_supported_plan_results_worker,
            (supported, sqlite_path, existing_table_policy),
            active_jobs_attr="import_active_jobs",
            active_jobs_lock_attr="import_active_jobs_lock",
            on_duplicate=self.notify_sqlite_import_busy,
            max_active_jobs=MAX_TK_SQLITE_IMPORT_JOBS,
            on_capacity=self.notify_sqlite_import_busy,
        )

    def import_supported_plan_results_worker(
        self,
        entries: list[tuple[str, dict[str, object], str]],
        sqlite_path: Path,
        existing_table_policy: str,
    ) -> None:
        # UI worker 只負責 thread 與訊息映射；manifest/register/import 規則統一交給 ingestion_pipeline。
        messages: list[str] = []
        item_statuses: list[tuple[str, str, str]] = []
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            index_to_item = {index: (plan_key, label) for index, (plan_key, _entry, label) in enumerate(entries, start=1)}
            run = run_existing_download_import_slice(
                {"providers": [entry for _plan_key, entry, _label in entries]},
                repository,
                DownloadImportPipelineOptions(
                    import_supported_results=True,
                    import_sqlite_path=sqlite_path,
                    import_row_limit=0,
                    import_replace=existing_table_policy == "replace",
                    import_existing_table_policy=existing_table_policy,
                ),
            )
            imported = run.result.imported
            skipped = run.result.import_skipped
            failed = run.result.import_failed
            for item_status in run.item_statuses:
                plan_key, label = index_to_item.get(item_status.index, ("", item_status.provider_id))
                if item_status.status == "imported":
                    detail = item_status.detail or self.tr("已寫入 SQLite", "Written to SQLite")
                    item_statuses.append((plan_key, self.tr("已匯入", "Imported"), detail))
                elif item_status.status == "skipped":
                    item_statuses.append((plan_key, self.tr("略過", "Skipped"), item_status.detail))
                    messages.append(f"{label}: {item_status.detail}")
                else:
                    item_statuses.append((plan_key, self.tr("失敗", "Failed"), item_status.detail))
                    messages.append(f"{label}: {item_status.detail}")
            for error in run.result.errors:
                if error not in messages:
                    messages.append(error)
        finally:
            conn.close()

        self.root.after(
            0,
            lambda: self.finish_import_supported_plan_results(imported, skipped, failed, tuple(messages), tuple(item_statuses), sqlite_path, existing_table_policy),
        )

    def finish_import_supported_plan_results(
        self,
        imported: int,
        skipped: int,
        failed: int,
        messages: tuple[str, ...],
        item_statuses: tuple[tuple[str, str, str], ...],
        sqlite_path: Path,
        existing_table_policy: str,
    ) -> None:
        for plan_key, status, detail in item_statuses:
            self.import_status_by_plan_key[plan_key] = (status, detail)
        self.reload_data()
        self.update_download_plan_panel()
        summary = self.tr(
            f"匯入完成：成功 {imported}，略過 {skipped}，失敗 {failed}",
            f"Import finished: imported {imported}, skipped {skipped}, failed {failed}",
        )
        self.status_var.set(summary)
        log_event(
            "ui_import_supported_plan_results",
            summary,
            level="error" if failed else "info",
            component="ui.import",
            context={
                "imported": imported,
                "skipped": skipped,
                "failed": failed,
                "sqlite_path": str(sqlite_path),
                "existing_table_policy": existing_table_policy,
            },
        )
        detail = "\n".join(messages[:8])
        body = f"{summary}\n\nSQLite: {sqlite_path}\n{self.tr('同名資料表策略', 'Existing table policy')}: {self.import_existing_table_policy_label(existing_table_policy)}"
        if detail:
            body += f"\n\n{detail}"
        if failed:
            messagebox.showwarning(self.tr("匯入完成但有問題", "Import finished with issues"), body)
        else:
            messagebox.showinfo(self.tr("匯入完成", "Import finished"), body)

    def import_local_file_from_ui(self) -> None:
        # UI 手動匯入只處理使用者明確選取的一個檔案；不掃資料夾、不搬檔、不猜測來源。
        sqlite_path = curated_imports_path()
        import_job_key = ("sqlite_import", str(sqlite_path), "")
        if single_flight_job_is_active(self, import_job_key, active_jobs_attr="import_active_jobs", on_duplicate=self.notify_sqlite_import_busy):
            return
        if self.sqlite_import_queue_is_full():
            self.notify_sqlite_import_busy()
            return
        selected = filedialog.askopenfilename(
            parent=self.root,
            title=self.tr("選擇本機 CSV/JSON 檔", "Choose local CSV/JSON file"),
            filetypes=(
                (self.tr("支援的資料檔", "Supported data files"), "*.csv *.csv.gz *.json *.json.gz *.jsonl *.jsonl.gz *.ndjson *.ndjson.gz *.geojson *.geojson.gz"),
                ("CSV", "*.csv *.csv.gz"),
                ("JSON / JSONL / GeoJSON", "*.json *.json.gz *.jsonl *.jsonl.gz *.ndjson *.ndjson.gz *.geojson *.geojson.gz"),
                (self.tr("所有檔案", "All files"), "*.*"),
            ),
        )
        if not selected:
            return
        table_name = simpledialog.askstring(
            self.tr("匯入本機檔案", "Import local file"),
            self.tr(
                "目標資料表名稱（可留空，由檔名推導；若同名已存在會自動改名，不會覆蓋）：",
                "Target table name (optional; inferred from filename if blank; existing names are auto-renamed, not overwritten):",
            ),
            parent=self.root,
        )
        if table_name is None:
            return
        confirmed = messagebox.askyesno(
            self.tr("匯入本機檔案", "Import local file"),
            self.tr(
                f"將為這個本機檔案建立 sidecar manifest，然後匯入 SQLite：\n{selected}\n\nSQLite：{sqlite_path}\n\n不會移動、刪除來源檔，也不會覆蓋既有資料表。",
                f"A sidecar manifest will be written for this local file, then imported into SQLite:\n{selected}\n\nSQLite: {sqlite_path}\n\nThe source file will not be moved/deleted and existing tables will not be overwritten.",
            ),
        )
        if not confirmed:
            return
        self.status_var.set(self.tr("正在匯入本機檔案到 SQLite...", "Importing local file into SQLite..."))
        start_single_flight_thread(
            self,
            import_job_key,
            self.import_local_file_worker,
            (Path(selected), sqlite_path, table_name.strip()),
            active_jobs_attr="import_active_jobs",
            active_jobs_lock_attr="import_active_jobs_lock",
            on_duplicate=self.notify_sqlite_import_busy,
            max_active_jobs=MAX_TK_SQLITE_IMPORT_JOBS,
            on_capacity=self.notify_sqlite_import_busy,
        )

    def import_local_file_worker(self, input_path: Path, sqlite_path: Path, table_name: str) -> None:
        manifest_path = Path("")
        final_table = ""
        rows_imported = 0
        columns_count = 0
        provenance_review: dict[str, object] = {}
        error = ""
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            result = write_local_file_manifest_file(
                input_path,
                None,
                manifest_dir=state_file(MANUAL_IMPORTS_DIR_NAME),
            )
            provenance_review = result.provenance_review
            ensure_manual_local_file_provider(repository, DEFAULT_MANUAL_LOCAL_PROVIDER_ID)
            register_local_file_manifest_asset(repository, result.manifest_path)
            manifest = read_manifest(result.manifest_path)
            requested_table = table_name or table_name_for_manifest(manifest)
            final_table = unique_table_name(sqlite_path, requested_table)
            # 真正匯入仍走既有 importer；UI 只決定 safe table name 與 thread 邊界。
            if result.import_kind == "csv":
                import_result = import_csv_manifest_to_sqlite(
                    result.manifest_path,
                    sqlite_path,
                    repository,
                    table_name=final_table,
                    replace=False,
                )
            elif result.import_kind == "json":
                import_result = import_json_manifest_to_sqlite(
                    result.manifest_path,
                    sqlite_path,
                    repository,
                    table_name=final_table,
                    replace=False,
                )
            else:
                raise ValueError(f"Unsupported local import format: {result.source_format}")
            manifest_path = result.manifest_path
            final_table = import_result.table_name
            rows_imported = import_result.rows_imported
            columns_count = len(import_result.columns)
        except Exception as exc:
            error = local_file_import_error_message(exc)
            log_exception("ui_import_local_file_failed", exc, component="ui.import")
        finally:
            conn.close()
        self.root.after(
            0,
            lambda: self.finish_import_local_file(
                input_path,
                manifest_path,
                sqlite_path,
                final_table,
                rows_imported,
                columns_count,
                provenance_review,
                error,
            ),
        )

    def finish_import_local_file(
        self,
        input_path: Path,
        manifest_path: Path,
        sqlite_path: Path,
        table_name: str,
        rows_imported: int,
        columns_count: int,
        provenance_review: dict[str, object],
        error: str,
    ) -> None:
        if error:
            self.status_var.set(self.tr(f"本機檔案匯入失敗：{error}", f"Local file import failed: {error}"))
            messagebox.showerror(self.tr("本機檔案匯入失敗", "Local file import failed"), error)
            return
        self.reload_data()
        summary = self.tr(
            f"本機檔案已匯入：{table_name}，{rows_imported} rows / {columns_count} columns",
            f"Local file imported: {table_name}, {rows_imported} rows / {columns_count} columns",
        )
        self.status_var.set(summary)
        log_event(
            "ui_import_local_file_completed",
            summary,
            component="ui.import",
            context={
                "input_path": str(input_path),
                "manifest_path": str(manifest_path),
                "sqlite_path": str(sqlite_path),
                "table_name": table_name,
                "rows_imported": rows_imported,
                "columns_count": columns_count,
                "provider_id": DEFAULT_MANUAL_LOCAL_PROVIDER_ID,
                "provenance_review": provenance_review,
            },
        )
        review_message = local_file_provenance_review_message(provenance_review)
        message = self.tr(
            f"{summary}\n\nManifest：{manifest_path}\nSQLite：{sqlite_path}\n\n來源檔未被移動或刪除。",
            f"{summary}\n\nManifest: {manifest_path}\nSQLite: {sqlite_path}\n\nThe source file was not moved or deleted.",
        )
        if review_message:
            message += f"\n\n{review_message}"
        messagebox.showinfo(
            self.tr("本機檔案已匯入", "Local file imported"),
            message,
        )
