"""Tk discovery and crawler-audit workflows for RuRuKa Asset Launcher.

這個 mixin 承接 provider candidate、dataset candidate 與本機 discovery dry-run
審核流程。主視窗只負責放置按鈕和持有狀態；這裡保留背景 worker、JSON handoff
與 crawler audit 摘要，讓大型 `launcher_ui.py` 不再承擔 discovery 編排細節。
"""

from __future__ import annotations

import json
from pathlib import Path
from tkinter import messagebox

import APIkeys_collection as core
from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME
from api_launcher.db import utc_now_iso
from api_launcher.discovery import DEFAULT_SEEDS_NAME, LOCAL_SEEDS_NAME, discover_provider_candidates, load_all_discovery_seeds
from api_launcher.discovery_promotion import promote_local_discovery_catalog
from api_launcher.event_log import log_event, log_exception
from api_launcher.paths import catalog_file, local_config_file, state_file
from api_launcher.registry import PROVIDER_CATALOG_NAME
from frontends.tk.background_jobs import start_single_flight_thread
from frontends.tk.dialogs import DatasetCandidateReviewDialog, ProviderCandidateReviewDialog
from frontends.tk.ui_labels import crawler_next_action_label as crawler_next_action_label_text


class DiscoveryWorkflowMixin:
    """封裝 Tk discovery / crawler audit UI workflow。"""

    def open_dataset_candidate_review_panel(self) -> None:
        DatasetCandidateReviewDialog(self)

    def open_provider_candidate_review_panel(self) -> None:
        path = state_file("provider_candidates.ui.json")
        if not path.exists():
            messagebox.showinfo(
                self.tr("Provider 候選", "Provider candidates"),
                self.tr("尚未產生 provider candidate review JSON。請先執行 provider 候選探索。", "No provider candidate review JSON exists yet. Run \"Discover provider candidates\" first."),
            )
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            messagebox.showerror(
                self.tr("Provider 候選", "Provider candidates"),
                self.tr(f"無法讀取 provider 候選 JSON：{exc}", f"Could not read provider candidate JSON: {exc}"),
            )
            return
        candidates = [item for item in payload.get("candidates", []) if isinstance(item, dict)] if isinstance(payload, dict) else []
        ProviderCandidateReviewDialog(self, path, candidates)

    def provider_discovery_message(self, payload: object, output_path: Path) -> str:
        # Provider discovery 是 catalog 入口審查，不是安裝或納管；訊息必須把 review JSON 路徑講清楚。
        data = payload if isinstance(payload, dict) else {}
        candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
        lines = [
            self.tr(
                f"Provider 候選發現完成：{data.get('candidate_count', len(candidates))} 筆。",
                f"Provider discovery complete: {data.get('candidate_count', len(candidates))} candidates.",
            ),
            self.tr(
                "這是 metadata-only review JSON；尚未寫入正式 catalog，也沒有抓取 API key 或登入內容。",
                "This is a metadata-only review JSON; the official catalog was not changed and no API keys or login content were collected.",
            ),
        ]
        if candidates:
            lines.extend(["", self.tr("候選預覽：", "Candidate preview:")])
            for item in candidates[:5]:
                if not isinstance(item, dict):
                    continue
                provider_id = item.get("provider_id") or "-"
                confidence = item.get("confidence", "-")
                lines.append(f"{provider_id}: confidence={confidence}")
        lines.extend(["", self.tr(f"Review JSON：{output_path}", f"Review JSON: {output_path}")])
        return "\n".join(lines)

    def discover_provider_candidates_from_ui(self) -> None:
        self.status_var.set(self.tr("正在發現 provider 候選...", "Discovering provider candidates..."))

        def worker() -> None:
            output_path = state_file("provider_candidates.ui.json")
            try:
                seed_path = catalog_file(DEFAULT_SEEDS_NAME)
                local_seed_path = local_config_file(LOCAL_SEEDS_NAME)
                seeds = load_all_discovery_seeds(seed_path, local_seed_path)
                conn = self._connect()
                try:
                    existing = {provider.provider_id for provider in core.load_providers(conn)}
                finally:
                    conn.close()
                candidates = discover_provider_candidates(seeds, existing_provider_ids=existing, timeout=12.0)
                payload = {
                    "schema_version": 1,
                    "created_at": utc_now_iso(),
                    "role": "reviewable provider/source candidates; metadata only; no API secrets collected",
                    "candidate_count": len(candidates),
                    "candidates": [candidate.to_dict() for candidate in candidates],
                }
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                log_event(
                    "provider_candidates_discovered",
                    "Provider candidate review JSON written from Tk UI.",
                    component="ui.provider_discovery",
                    context={
                        "candidate_count": len(candidates),
                        "output_path": str(output_path),
                    },
                )
            except Exception as exc:
                log_exception(
                    "provider_candidate_discovery_failed",
                    exc,
                    component="ui.provider_discovery",
                )
                self.root.after(0, lambda: messagebox.showerror(self.tr("Provider 候選發現失敗", "Provider discovery failed"), str(exc)))
                self.root.after(0, lambda: self.status_var.set(self.tr(f"Provider 候選發現失敗：{exc}", f"Provider discovery failed: {exc}")))
                return

            def finish() -> None:
                message = self.provider_discovery_message(payload, output_path)
                status = self.tr(
                    f"Provider 候選發現完成：{len(candidates)} 筆",
                    f"Provider discovery complete: {len(candidates)} candidates",
                )
                self.status_var.set(status)
                messagebox.showinfo(self.tr("Provider 候選", "Provider candidates"), message)

            self.root.after(0, finish)

        start_single_flight_thread(
            self,
            ("provider_discovery", "all", ""),
            worker,
            (),
            active_jobs_attr="discovery_active_jobs",
            active_jobs_lock_attr="discovery_active_jobs_lock",
            on_duplicate=lambda: self.status_var.set(
                self.tr("Provider 候選發現已在執行中。", "Provider discovery is already running.")
            ),
        )

    def crawler_next_action_label(self, action: str) -> str:
        return crawler_next_action_label_text(action, self.tr)

    def crawler_audit_summary_lines(self, audit_summary: object, *, limit: int = 6) -> list[str]:
        # audit_summary 是後端提供的穩定總表；UI 只做 bounded 摘要，避免使用者只能從逐 source 明細猜整體狀態。
        if not isinstance(audit_summary, dict):
            return []
        def summary_int(key: str) -> int:
            try:
                return int(audit_summary.get(key) or 0)
            except (TypeError, ValueError):
                return 0

        status = str(audit_summary.get("status") or "-")
        source_count = summary_int("source_count")
        candidate_count = summary_int("candidate_count")
        problem_source_count = summary_int("problem_source_count")
        next_action = str(audit_summary.get("next_action") or "")
        lines = [
            self.tr(
                f"整體狀態：{status}；來源 {source_count}；候選 {candidate_count}；問題來源 {problem_source_count}",
                f"Overall: {status}; sources {source_count}; candidates {candidate_count}; problem sources {problem_source_count}",
            )
        ]
        if next_action:
            lines.append(
                self.tr(
                    f"總體下一步：{self.crawler_next_action_label(next_action)}",
                    f"Overall next step: {self.crawler_next_action_label(next_action)}",
                )
            )
        for label, values in (
            (self.tr("Warning 分組", "Warning groups"), audit_summary.get("by_warning_code")),
            (self.tr("下一步分組", "Next-action groups"), audit_summary.get("by_next_action")),
        ):
            if not isinstance(values, dict) or not values:
                continue
            preview = ", ".join(f"{key}={value}" for key, value in sorted(values.items())[:3])
            lines.append(f"{label}: {preview}")
        problem_sources = audit_summary.get("problem_sources")
        if isinstance(problem_sources, list) and problem_sources:
            # 問題 source 只列前幾個 id；完整 error/warning 仍在下面的逐 source 明細與 JSON audit。
            source_ids = [
                str(item.get("source_id") or "-")
                for item in problem_sources[:3]
                if isinstance(item, dict)
            ]
            if source_ids:
                lines.append(self.tr(f"優先檢查來源：{', '.join(source_ids)}", f"Review first: {', '.join(source_ids)}"))
        return lines[:limit]

    def crawler_audit_issue_lines(self, source_results: object, *, limit: int = 8) -> list[str]:
        # 彈窗空間有限，所以這裡只做 bounded preview；完整 audit 仍由 CLI/JSON 與 candidate review 流程保留。
        lines: list[str] = []
        for item in source_results:
            source_id = str(getattr(item, "source_id", "") or "-")
            error = str(getattr(item, "error", "") or "")
            warnings = tuple(getattr(item, "warnings", ()) or ())
            next_action = str(getattr(item, "next_action", "") or "")
            if not error and not warnings:
                continue
            if next_action:
                lines.append(
                    self.tr(
                        f"{source_id}: 下一步：{self.crawler_next_action_label(next_action)}",
                        f"{source_id}: next step: {self.crawler_next_action_label(next_action)}",
                    )
                )
            if error:
                lines.append(f"{source_id}: {error}")
            for warning in warnings:
                lines.append(f"{source_id}: {warning}")
            if len(lines) >= limit:
                break
        return lines[:limit]

    def discover_dataset_candidates_from_ui(self) -> None:
        selected_provider_ids = tuple(self.selected_provider_ids())
        scope = (
            self.tr(f"{len(selected_provider_ids)} 個選取資料源", f"{len(selected_provider_ids)} selected sources")
            if selected_provider_ids
            else self.tr("所有已設定 crawler 的資料源", "all configured crawler sources")
        )
        self.status_var.set(self.tr(f"正在並行發現資料集候選：{scope}", f"Discovering dataset candidates concurrently: {scope}"))
        job_scope = ",".join(selected_provider_ids) if selected_provider_ids else "all"
        start_single_flight_thread(
            self,
            ("dataset_candidate_discovery", job_scope, ""),
            self._dataset_candidate_discovery_worker,
            (selected_provider_ids,),
            active_jobs_attr="discovery_active_jobs",
            active_jobs_lock_attr="discovery_active_jobs_lock",
            on_duplicate=lambda: self.status_var.set(
                self.tr("資料集候選發現已在執行中。", "Dataset discovery is already running.")
            ),
        )

    def _dataset_candidate_discovery_worker(self, provider_ids: tuple[str, ...]) -> None:
        try:
            sources = core.load_dataset_discovery_sources(catalog_file(core.DEFAULT_DATASET_DISCOVERY_SOURCES_NAME))
            if provider_ids:
                wanted = set(provider_ids)
                sources = [source for source in sources if source.provider_id in wanted]
            result = core.crawl_dataset_sources(
                sources,
                core.DatasetCrawlOptions(
                    timeout=12.0,
                    max_results_override=100,
                    full_crawl=True,
                    max_pages=0,
                    max_workers=4,
                ),
            )
            conn = self._connect()
            try:
                repository = core.ApiCatalogRepository(conn)
                existing_provider_ids = {provider.provider_id for provider in core.load_providers(conn)}
                upserted = 0
                for candidate in result.candidates:
                    if candidate.dataset.provider_id not in existing_provider_ids:
                        continue
                    repository.upsert_dataset(core.dataset_with_candidate_metadata(candidate))
                    upserted += 1
            finally:
                conn.close()
        except Exception as exc:
            log_exception(
                "dataset_candidate_discovery_failed",
                exc,
                component="ui.dataset_discovery",
                context={"provider_ids": provider_ids},
            )
            self.root.after(0, lambda: messagebox.showerror(self.tr("資料集發現失敗", "Dataset discovery failed"), str(exc)))
            self.root.after(0, lambda: self.status_var.set(self.tr(f"資料集發現失敗：{exc}", f"Dataset discovery failed: {exc}")))
            return

        def finish() -> None:
            next_action_label = self.crawler_next_action_label(result.next_action)
            message = self.tr(
                f"資料集候選發現完成：新增/更新 {upserted} 筆；錯誤來源 {result.error_count}；警告 {result.warning_count}；重複 {result.duplicate_count}；下一步：{next_action_label}",
                f"Dataset discovery complete: upserted {upserted}; source errors {result.error_count}; warnings {result.warning_count}; duplicates {result.duplicate_count}; next step: {next_action_label}",
            )
            self.status_var.set(message)
            self.reload_data()
            self.status_var.set(message)
            if result.error_count or result.warning_count:
                summary_lines = self.crawler_audit_summary_lines(result.audit_summary)
                issue_lines = self.crawler_audit_issue_lines(result.source_results)
                messagebox.showwarning(
                    self.tr("部分 crawler 需要檢查", "Some crawlers need review"),
                    message
                    + "\n\n"
                    + self.tr("來源審核摘要：", "Source audit summary:")
                    + "\n"
                    + "\n".join(summary_lines)
                    + "\n\n"
                    + self.tr("逐來源明細：", "Source details:")
                    + "\n"
                    + "\n".join(issue_lines),
                )
            self.open_dataset_candidate_review_panel()

        self.root.after(0, finish)

    def local_discovery_audit_message(self, payload: object, audit_path: Path) -> str:
        # 本機草稿 promotion 是 catalog 前的安全閘；UI 摘要要清楚標示 dry-run，避免被誤會已正式寫入。
        data = payload if isinstance(payload, dict) else {}
        audit = data.get("audit") if isinstance(data.get("audit"), dict) else {}
        summary = audit.get("audit_summary") if isinstance(audit.get("audit_summary"), dict) else {}
        lines = [
            self.tr(
                "本機 discovery 草稿審核完成（dry-run，未寫入正式 catalog）。",
                "Local discovery draft audit completed (dry-run; official catalog was not changed).",
            ),
            self.tr(
                f"審核來源 {data.get('audited_source_count', 0)}；可提升 provider {data.get('promoted_provider_count', 0)}；可提升 source {data.get('promoted_source_count', 0)}；略過 {data.get('skipped_count', 0)}",
                f"Audited sources {data.get('audited_source_count', 0)}; promotable providers {data.get('promoted_provider_count', 0)}; promotable sources {data.get('promoted_source_count', 0)}; skipped {data.get('skipped_count', 0)}",
            ),
        ]
        summary_lines = self.crawler_audit_summary_lines(summary)
        if summary_lines:
            lines.extend(["", self.tr("Crawler 審核摘要：", "Crawler audit summary:"), *summary_lines])
        skipped = data.get("skipped")
        if isinstance(skipped, list) and skipped:
            lines.extend(["", self.tr("略過來源：", "Skipped sources:")])
            for item in skipped[:4]:
                if not isinstance(item, dict):
                    continue
                lines.append(f"{item.get('source_id') or '-'}: {item.get('reason') or '-'}")
        lines.extend(["", self.tr(f"Audit JSON：{audit_path}", f"Audit JSON: {audit_path}")])
        return "\n".join(lines)

    def audit_local_discovery_from_ui(self) -> None:
        self.status_var.set(self.tr("正在審核本機 discovery 草稿（dry-run）...", "Auditing local discovery drafts (dry-run)..."))

        def worker() -> None:
            output_path = state_file("local_discovery_audit.ui.json")
            try:
                result = promote_local_discovery_catalog(
                    local_provider_seed_path=local_config_file(LOCAL_SEEDS_NAME),
                    local_dataset_source_path=local_config_file(LOCAL_DATASET_DISCOVERY_SOURCES_NAME),
                    provider_catalog_path=catalog_file(PROVIDER_CATALOG_NAME),
                    dataset_source_catalog_path=catalog_file(core.DEFAULT_DATASET_DISCOVERY_SOURCES_NAME),
                    options=core.DatasetCrawlOptions(
                        timeout=12.0,
                        max_results_override=25,
                        full_crawl=False,
                        max_pages=1,
                        max_workers=4,
                    ),
                    dry_run=True,
                )
                payload = result.to_dict()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                log_event(
                    "local_discovery_audit_completed",
                    "Local discovery promotion dry-run audit completed.",
                    component="ui.dataset_discovery",
                    context={
                        "audited_source_count": result.audited_source_count,
                        "skipped_count": result.skipped_count,
                        "audit_issue_count": payload.get("audit", {}).get("audit_issue_count", 0),
                        "output_path": str(output_path),
                    },
                )
            except Exception as exc:
                log_exception(
                    "local_discovery_audit_failed",
                    exc,
                    component="ui.dataset_discovery",
                )
                self.root.after(0, lambda: messagebox.showerror(self.tr("本機 discovery 審核失敗", "Local discovery audit failed"), str(exc)))
                self.root.after(0, lambda: self.status_var.set(self.tr(f"本機 discovery 審核失敗：{exc}", f"Local discovery audit failed: {exc}")))
                return

            def finish() -> None:
                message = self.local_discovery_audit_message(payload, output_path)
                status = self.tr(
                    f"本機 discovery 審核完成：來源 {result.audited_source_count}；略過 {result.skipped_count}",
                    f"Local discovery audit complete: sources {result.audited_source_count}; skipped {result.skipped_count}",
                )
                self.status_var.set(status)
                audit_issue_count = int(payload.get("audit", {}).get("audit_issue_count", 0))
                if result.audited_source_count == 0:
                    messagebox.showinfo(self.tr("本機 discovery 審核", "Local discovery audit"), message)
                elif result.skipped_count or audit_issue_count:
                    messagebox.showwarning(self.tr("本機 discovery 審核", "Local discovery audit"), message)
                else:
                    messagebox.showinfo(self.tr("本機 discovery 審核", "Local discovery audit"), message)

            self.root.after(0, finish)

        start_single_flight_thread(
            self,
            ("local_discovery_audit", "dry_run", ""),
            worker,
            (),
            active_jobs_attr="discovery_active_jobs",
            active_jobs_lock_attr="discovery_active_jobs_lock",
            on_duplicate=lambda: self.status_var.set(
                self.tr("本機 discovery 審核已在執行中。", "Local discovery audit is already running.")
            ),
        )
