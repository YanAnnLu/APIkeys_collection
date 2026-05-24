"""Tk download plan and job workflows for RuRuKa Asset Launcher.

這個 mixin 集中下載計畫面板、非同步下載 job 控制、progress callback 與完成後 asset 註冊，
讓主視窗避免同時承擔表格生命週期與下載佇列調度細節。
"""

from __future__ import annotations

import urllib.parse
from pathlib import Path
from tkinter import END, BooleanVar, messagebox

import APIkeys_collection as core
from api_launcher.downloads.jobs import DownloadProgress, JobStatus
from api_launcher.downloads.plan_runner import download_entry_skip_bucket
from api_launcher.event_log import log_event
from api_launcher.manifests import read_manifest
from api_launcher.paths import DOWNLOADS_DIR
from frontends.tk.provider_models import ProviderRow


class DownloadWorkflowMixin:
    """封裝下載計畫與 download queue UI workflow；不改動底層 downloader 行為。"""

    def update_download_plan_panel(self) -> None:
        if not hasattr(self, "cart_tree"):
            return
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
        items = self.selected_plan_items()
        for plan_key, row, version in items:
            version_label = version.menu_label if version else self.localized_download_label(row.download_eligibility)
            self.cart_tree.insert(
                "",
                END,
                iid=plan_key,
                values=(
                    self.plan_item_label(plan_key, row, version),
                    row.auth_type,
                    row.geographic_scope,
                    version_label,
                    self.import_status_label(plan_key, row, version),
                ),
            )
        self.plan_count_var.set(self.tr(f"下載計畫：{len(items)} 個項目", f"Download Plan: {len(items)} items"))

        self.update_download_jobs_panel()

    def on_cart_select(self, _event: object) -> None:
        selection = self.cart_tree.selection()
        if not selection:
            return
        self.active_provider_id = self.provider_id_for_plan_key(str(selection[0]))
        if self.active_provider_id in {row.provider_id for row in self.filtered_rows}:
            self.tree.selection_set(self.active_provider_id)
            self.tree.focus(self.active_provider_id)
        if self.detail_visible:
            self.update_detail_panel(self.row_by_provider_id(self.active_provider_id))
        self.update_primary_download_action_label()

    def on_download_select(self, _event: object) -> None:
        selection = self.download_tree.selection()
        if selection:
            self.active_provider_id = self.provider_id_for_plan_key(str(selection[0]))
        self.update_primary_download_action_label()

    def start_download_plan(self) -> None:
        items = self.selected_plan_items()
        if not items:
            messagebox.showinfo(self.tr("下載計畫是空的", "Download plan is empty"), self.tr("請先加入至少一個資料源。", "Add at least one source to the download plan first."))
            return
        self.start_download_plan_items(items)

    def start_selected_download_plan_item(self, _event: object | None = None) -> None:
        """Double-click one row in the downloader list to queue that item."""

        if not hasattr(self, "cart_tree"):
            return
        selection = self.cart_tree.selection()
        if not selection:
            self.status_var.set(self.tr("請先在下載器清單選擇一筆項目。", "Select one downloader item first."))
            return
        plan_key = str(selection[0])
        for item_key, row, version in self.selected_plan_items():
            if item_key == plan_key:
                self.active_provider_id = plan_key
                self.start_download_plan_items([(item_key, row, version)])
                return
        self.status_var.set(self.tr("下載器清單項目已經不存在，請重新整理計畫。", "Downloader item no longer exists; refresh the plan."))

    def toggle_primary_download_action(self) -> None:
        """用單一主按鈕承接開始/暫停/繼續，降低展示與日常操作的心智負擔。"""

        plan_key = self.active_download_provider_id()
        progress = self.download_progress_by_provider.get(plan_key)
        if progress and progress.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
            self.pause_active_download()
            return
        if progress and progress.status == JobStatus.PAUSED:
            self.resume_active_download()
            return
        self.start_download_plan()

    def start_download_rows(self, rows: list[ProviderRow]) -> None:
        self.start_download_plan_items([(row.provider_id, row, self.plan_version_by_provider.get(row.provider_id)) for row in rows])

    def localized_download_skip_summary(self, skip_summary: dict[str, int]) -> str:
        labels = {
            "adapter_required": self.tr("需 Adapter", "adapter required"),
            "metadata_only": self.tr("僅 metadata", "metadata only"),
            "unavailable": self.tr("不可下載", "unavailable"),
            "missing_download_url": self.tr("缺下載 URL", "missing download URL"),
            "not_direct": self.tr("非直接檔案", "not direct"),
        }
        parts = [f"{labels.get(bucket, bucket)}={count}" for bucket, count in skip_summary.items() if count]
        return "；".join(parts)

    def download_skip_next_action_message(self, summary: str, *, partial: bool) -> str:
        # 下載略過不是單純錯誤：多數是尚未解析的 API/selector/metadata，需要把下一步明確告訴使用者。
        if partial:
            return summary + "\n\n" + self.tr(
                "已啟動的 direct download 會繼續排隊；被略過的項目仍是 API、入口頁、selector 或 metadata。請先開 Adapter 待辦，或按「解析 Adapter 計畫」把可安全界定的小樣本轉成 direct download。",
                "Started direct downloads will stay queued. Skipped items are still APIs, landing pages, selectors, or metadata. Open the adapter review queue or resolve the adapter plan before downloading them.",
            )
        return summary + "\n\n" + self.tr(
            "這些項目目前還是 API、入口頁、selector 或 metadata。請先開 Adapter 待辦，或按「解析 Adapter 計畫」把可安全界定的小樣本轉成 direct download。",
            "These items are still APIs, landing pages, selectors, or metadata. Open the adapter review queue or resolve the adapter plan before downloading.",
        )

    def import_skipped_detail_message(self, skipped: list[str], *, limit: int = 4) -> str:
        if not skipped:
            return ""
        # 匯入流程可能部分成功；把略過原因直接列出，避免使用者誤以為所有 plan item 都已進 SQLite。
        preview_items = skipped[:limit]
        preview = "\n".join(f"- {item}" for item in preview_items)
        remaining = len(skipped) - len(preview_items)
        heading = self.tr(
            f"\n\n會略過：{len(skipped)} 個不支援或未準備好的項目。原因預覽：",
            f"\n\nWill skip {len(skipped)} unsupported or unready items. Reason preview:",
        )
        if remaining:
            tail = self.tr(
                f"\n...還有 {remaining} 個項目未列出；請依原因先處理 Adapter 待辦、解析 Adapter 計畫、下載或 manifest 健康狀態。",
                f"\n...{remaining} more items are not shown; follow the reason to resolve adapter review, adapter-plan resolution, download, or manifest health first.",
            )
        else:
            tail = self.tr(
                "\n請依原因先處理 Adapter 待辦、解析 Adapter 計畫、下載或 manifest 健康狀態。",
                "\nFollow the reason to resolve adapter review, adapter-plan resolution, download, or manifest health first.",
            )
        return f"{heading}\n{preview}{tail}"

    def start_download_plan_items(self, items: list[tuple[str, ProviderRow, core.DatasetVersionOption | None]]) -> None:
        # 這裡只啟動 direct_download；需要 adapter 的項目保留在審核/解析流程，不硬猜 URL。
        started = 0
        skipped = 0
        skip_summary: dict[str, int] = {}
        for plan_key, row, version in items:
            if not self.prepare_provider_for_download(plan_key):
                continue
            plan_entry, build_error = self.plan_entry_for_item(row, version, plan_key=plan_key)
            if plan_entry is None:
                skipped += 1
                skip_summary["not_direct"] = skip_summary.get("not_direct", 0) + 1
                self.download_status_by_provider[plan_key] = ("skipped", "0%", build_error)
                continue
            eligibility = plan_entry.get("download_eligibility", {})
            status = str(eligibility.get("status") if isinstance(eligibility, dict) else "")
            url = str(plan_entry.get("download_url") or "")
            if status != "direct_download" or not url:
                reason = str(eligibility.get("reason") if isinstance(eligibility, dict) else "") or self.tr("需要 adapter 審核後才能下載", "Adapter review is required before download")
                skipped += 1
                bucket = download_entry_skip_bucket(plan_entry) or "not_direct"
                skip_summary[bucket] = skip_summary.get(bucket, 0) + 1
                self.download_status_by_provider[plan_key] = ("skipped", "0%", reason)
                continue
            target_path = Path(str(plan_entry.get("target_path") or self.download_target_for_row(row, url)))
            plan_entry["target_path"] = str(target_path)
            self.import_status_by_plan_key.pop(plan_key, None)
            job = self.download_queue.submit(plan_entry)
            self.download_jobs_by_provider[plan_key] = job.job_id
            self.download_providers_by_job[job.job_id] = plan_key
            self.download_plan_entries_by_provider[plan_key] = dict(plan_entry)
            self.download_status_by_provider[plan_key] = ("queued", "0%", str(target_path))
            started += 1
        self.update_download_jobs_panel()
        skip_detail = self.localized_download_skip_summary(skip_summary)
        summary = self.tr(f"下載工作已開始：{started}；略過：{skipped}", f"Download jobs started: {started}; skipped: {skipped}")
        if skip_detail:
            summary = f"{summary} ({skip_detail})"
        self.status_var.set(summary)
        if started == 0 and skipped:
            # 這個提示把「沒有直接下載」改成可行的下一步，避免 Demo 時看起來像按鈕沒接上。
            messagebox.showinfo(
                self.tr("沒有可直接下載項目", "No direct downloads"),
                self.download_skip_next_action_message(summary, partial=False),
            )
        elif started and skipped:
            # 部分成功仍要提示剩餘項目的下一步，否則使用者會誤以為整份 plan 都已經處理完。
            messagebox.showinfo(
                self.tr("部分項目未啟動下載", "Some items were not started"),
                self.download_skip_next_action_message(summary, partial=True),
            )

    def prepare_provider_for_download(self, plan_key: str) -> bool:
        # 完成/失敗/取消的工作可重排；running/paused 工作不能被同一 plan_key 重複提交。
        job_id = self.download_jobs_by_provider.get(plan_key)
        if not job_id:
            return True
        progress = self.download_progress_by_provider.get(plan_key)
        if progress and progress.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            self.download_jobs_by_provider.pop(plan_key, None)
            self.download_providers_by_job.pop(job_id, None)
            self.download_plan_entries_by_provider.pop(plan_key, None)
            self.registered_completed_downloads.discard(plan_key)
            self.import_status_by_plan_key.pop(plan_key, None)
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
        plan_key = str(selection[0]) if selection else self.active_provider_id
        return self.download_jobs_by_provider.get(plan_key)

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
        plan_key = self.active_download_provider_id()
        provider_id = self.provider_id_for_plan_key(plan_key)
        row = self.row_by_provider_id(provider_id)
        if row is None:
            self.status_var.set(self.tr("沒有可重試的下載工作。", "No active download job to retry."))
            return
        job_id = self.download_jobs_by_provider.get(plan_key)
        progress = self.download_progress_by_provider.get(plan_key)
        if job_id and progress and progress.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
            self.status_var.set(self.tr("只有失敗或取消的下載工作可以重試。", "Only failed or cancelled jobs can be retried."))
            return
        self.download_jobs_by_provider.pop(plan_key, None)
        if job_id:
            self.download_providers_by_job.pop(job_id, None)
        self.download_plan_entries_by_provider.pop(plan_key, None)
        self.registered_completed_downloads.discard(plan_key)
        self.import_status_by_plan_key.pop(plan_key, None)
        self.selected.setdefault(provider_id, BooleanVar(value=False)).set(True)
        self.start_download_plan_items([(plan_key, row, self.plan_version_by_provider.get(plan_key))])

    def active_download_provider_id(self) -> str:
        if hasattr(self, "download_tree"):
            selection = self.download_tree.selection()
            if selection:
                return str(selection[0])
        if hasattr(self, "cart_tree"):
            selection = self.cart_tree.selection()
            if selection:
                return str(selection[0])
        return self.active_provider_id

    def on_download_progress_threadsafe(self, progress: DownloadProgress) -> None:
        # DownloadQueue callback 可能來自 worker thread；Tk 更新必須排到主 thread。
        self.root.after(0, lambda update=progress: self.on_download_progress(update))

    def on_download_progress(self, progress: DownloadProgress) -> None:
        plan_key = self.download_providers_by_job.get(progress.job_id, progress.provider_id)
        self.download_progress_by_provider[plan_key] = progress
        target = self.download_status_by_provider.get(plan_key, ("", "", ""))[2]
        self.download_status_by_provider[plan_key] = (
            progress.status.value,
            self.format_download_percent(progress),
            target or progress.message,
        )
        self.update_download_jobs_panel()
        if progress.status == JobStatus.COMPLETED:
            self.register_completed_download(plan_key, target)
        elif progress.status in {JobStatus.FAILED, JobStatus.CANCELLED}:
            provider_id = self.provider_id_for_plan_key(plan_key)
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
        plan_keys = list(dict.fromkeys([*self.selected_plan_keys(), *self.download_status_by_provider.keys()]))
        for plan_key in plan_keys:
            provider_id = self.provider_id_for_plan_key(plan_key)
            row = self.row_by_provider_id(provider_id)
            status, progress, target = self.download_status_by_provider.get(plan_key, ("planned", "0%", ""))
            self.download_tree.insert(
                "",
                END,
                iid=plan_key,
                values=(self.plan_item_label(plan_key, row), status, progress, self.import_status_label(plan_key, row), target),
            )
        self.update_primary_download_action_label()

    def update_primary_download_action_label(self) -> None:
        if not hasattr(self, "download_primary_action_var"):
            return
        plan_key = self.active_download_provider_id()
        progress = self.download_progress_by_provider.get(plan_key)
        if progress and progress.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
            label = self.tr("暫停", "Pause")
        elif progress and progress.status == JobStatus.PAUSED:
            label = self.tr("繼續", "Resume")
        else:
            label = self.tr("開始", "Start")
        self.download_primary_action_var.set(label)

    def register_completed_download(self, plan_key: str, target: str) -> None:
        if plan_key in self.registered_completed_downloads:
            return
        self.registered_completed_downloads.add(plan_key)
        provider_id = self.provider_id_for_plan_key(plan_key)
        row = self.row_by_provider_id(provider_id)
        plan_entry = self.download_plan_entries_by_provider.get(plan_key, {})
        conn = self._connect()
        try:
            repository = core.ApiCatalogRepository(conn)
            if target:
                # 健康 manifest 走正式 asset registration；沒有 manifest 的舊路徑只保守記 file asset。
                manifest_path = Path(target).with_suffix(Path(target).suffix + ".manifest.json")
                if manifest_path.exists():
                    manifest = read_manifest(manifest_path)
                    repository.upsert_dataset_asset_manifest(manifest, manifest_path, status="ok")
                    repository.register_downloaded_manifest_asset(manifest, manifest_path)
                else:
                    install_id = repository.manage_provider_installation(
                        provider_id,
                        location=target,
                        notes="Downloaded by APIkeys_collection HTTP downloader.",
                    )
                    repository.register_installation_asset(
                        install_id,
                        asset_kind="file",
                        asset_name=Path(target).name,
                        asset_role="source",
                        source_format="unknown",
                        source_uri=str(plan_entry.get("download_url") or (self.download_url_for_row(row) if row else "")),
                        notes="Downloaded source asset.",
                    )
        finally:
            conn.close()
        self.reload_data()
        self.status_var.set(self.tr(f"下載完成：{row.name if row else provider_id}", f"Download completed: {row.name if row else provider_id}"))
