"""Tk showcase-mode workflow helpers.

展示模式只承接已穩定、可重跑、可向外部觀眾操作的功能。這裡先放
dataset discovery seed coverage 稽核：它只讀 catalog/source 設定，不做網路
爬取、不下載資料、不寫入 curated DB，因此適合中午展示或進度說明。
"""

from __future__ import annotations

import json
from pathlib import Path
from tkinter import messagebox
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
from api_launcher.paths import catalog_file, local_config_file, state_file


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
