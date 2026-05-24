from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from api_launcher.crawlers.dataset_sources import SUPPORTED_DATASET_SOURCE_TYPES
from api_launcher.crawlers.pagination import MAX_FULL_CRAWL_PAGES
from api_launcher.crawlers.types import DatasetDiscoverySource
from api_launcher.db import utc_now_iso


ENTRY_LISTING_SOURCE_TYPES = frozenset(
    {
        "erddap_all_datasets",
        "html_file_index",
        "stac_collections",
    }
)
PAGINATED_CATALOG_SOURCE_TYPES = frozenset(
    {
        "ckan_package_search",
        "cmr_collections",
        "datacite_dois",
        "dataverse_search",
        "gbif_dataset_search",
        "ncei_search",
        "ogc_api_records",
        "openalex_works_search",
        "socrata_catalog_search",
        "zenodo_records_search",
    }
)
FULL_SEED_CAPABLE_SOURCE_TYPES = ENTRY_LISTING_SOURCE_TYPES | PAGINATED_CATALOG_SOURCE_TYPES


@dataclass(frozen=True)
class SourceSeedCoverage:
    source_id: str
    provider_id: str
    source_type: str
    configured_mode: str
    inferred_mode: str
    current_seed_scope: str
    full_crawl_supported: bool
    complete_seed_ready: bool
    has_search_terms: bool
    search_term_count: int
    max_results: int
    next_action: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "provider_id": self.provider_id,
            "source_type": self.source_type,
            "configured_mode": self.configured_mode,
            "inferred_mode": self.inferred_mode,
            "current_seed_scope": self.current_seed_scope,
            "full_crawl_supported": self.full_crawl_supported,
            "complete_seed_ready": self.complete_seed_ready,
            "has_search_terms": self.has_search_terms,
            "search_term_count": self.search_term_count,
            "max_results": self.max_results,
            "next_action": self.next_action,
            "notes": self.notes,
        }


def build_dataset_seed_coverage_report(
    sources: Iterable[DatasetDiscoverySource],
    *,
    max_pages: int = 0,
) -> dict[str, object]:
    # 這份稽核只讀取 source 設定，不做網路爬取；展示時可安全重跑。
    source_list = list(sources)
    rows = [source_seed_coverage(source) for source in source_list]
    by_scope = Counter(row.current_seed_scope for row in rows)
    by_action = Counter(row.next_action for row in rows)
    ready_count = sum(1 for row in rows if row.complete_seed_ready)
    capable_count = sum(1 for row in rows if row.full_crawl_supported)
    return {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "role": "dataset discovery source seed coverage audit; metadata only; no network crawl or download executed",
        "source_count": len(rows),
        "showcase_status": (
            "all_sources_have_complete_seed_attempt_path"
            if capable_count == len(rows)
            else "some_sources_need_crawler_handler"
        ),
        "complete_seed_capable_count": capable_count,
        "complete_seed_ready_count": ready_count,
        "needs_complete_seed_action_count": len(rows) - ready_count,
        "full_crawl_supported_count": capable_count,
        "supported_source_type_count": len(SUPPORTED_DATASET_SOURCE_TYPES),
        "max_pages_effective_cap": max_pages if max_pages > 0 else MAX_FULL_CRAWL_PAGES,
        "recommended_showcase_modes": {
            "fast_seed_audit": "--dataset-discovery-seed-coverage-json",
            "write_seed_audit": "--write-dataset-seed-coverage state/showcase/dataset_seed_coverage.json",
            "complete_seed_attempt": (
                "--discover-dataset-candidates --dataset-discovery-complete-seed "
                "--dataset-discovery-max-pages 3"
            ),
        },
        "summary": {
            "by_current_seed_scope": dict(sorted(by_scope.items())),
            "by_next_action": dict(sorted(by_action.items())),
        },
        "sources": [row.to_dict() for row in rows],
    }


def render_dataset_seed_coverage_markdown(report: dict[str, object]) -> str:
    # Markdown 給展示與交接閱讀；JSON 才是 agent/CI 的穩定資料介面。
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    by_scope = summary.get("by_current_seed_scope") if isinstance(summary.get("by_current_seed_scope"), dict) else {}
    by_action = summary.get("by_next_action") if isinstance(summary.get("by_next_action"), dict) else {}
    lines = [
        "# 資料集 seed 覆蓋展示報告",
        "",
        "這份報告只檢查 catalog 裡的 dataset discovery source 設定，"
        "不執行網路爬取、不下載資料，適合展示目前入口爬蟲的 seed 覆蓋狀態。",
        "",
        "## 摘要",
        "",
        f"- 展示狀態：`{report.get('showcase_status', '')}`",
        f"- 來源入口數：{report.get('source_count', 0)}",
        f"- 具備完整 seed 嘗試路徑：{report.get('complete_seed_capable_count', 0)}",
        f"- 目前已是完整入口列表或分頁 catalog：{report.get('complete_seed_ready_count', 0)}",
        f"- 需要展示模式忽略抽樣 `search_terms`：{report.get('needs_complete_seed_action_count', 0)}",
        f"- 展示用 max-pages 安全上限：{report.get('max_pages_effective_cap', 0)}",
        "",
        "## 目前 seed 範圍",
        "",
    ]
    for key, value in sorted(by_scope.items()):
        lines.append(f"- `{key}`：{value}")
    lines.extend(["", "## 下一步分組", ""])
    for key, value in sorted(by_action.items()):
        lines.append(f"- `{key}`：{value}")
    recommended = report.get("recommended_showcase_modes")
    if isinstance(recommended, dict):
        lines.extend(["", "## 建議展示命令", ""])
        for key, value in recommended.items():
            lines.append(f"- `{key}`：`{value}`")
    lines.extend(
        [
            "",
            "## Source 明細",
            "",
            "| Source | Provider | 類型 | 目前 seed 範圍 | 下一步 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("sources", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            f"`{row.get('source_id', '')}` | "
            f"`{row.get('provider_id', '')}` | "
            f"`{row.get('source_type', '')}` | "
            f"`{row.get('current_seed_scope', '')}` | "
            f"`{row.get('next_action', '')}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def source_seed_coverage(source: DatasetDiscoverySource) -> SourceSeedCoverage:
    configured_mode = (source.seed_discovery_mode or "auto").strip() or "auto"
    inferred_mode = infer_seed_discovery_mode(source)
    full_crawl_supported = source.source_type in FULL_SEED_CAPABLE_SOURCE_TYPES
    has_terms = bool(source.search_terms)
    if configured_mode != "auto":
        current_scope = configured_mode
    elif has_terms:
        current_scope = "bounded_search_terms"
    elif source.source_type in ENTRY_LISTING_SOURCE_TYPES:
        current_scope = "entry_listing"
    elif source.source_type in PAGINATED_CATALOG_SOURCE_TYPES:
        current_scope = "paginated_catalog"
    else:
        current_scope = "unsupported_or_unknown"
    complete_ready = full_crawl_supported and current_scope in {"entry_listing", "paginated_catalog", "complete_entry_listing"}
    if complete_ready:
        next_action = "run_full_crawl_or_export_candidates"
    elif full_crawl_supported and has_terms:
        next_action = "run_dataset_discovery_complete_seed_to_ignore_sample_terms"
    elif full_crawl_supported:
        next_action = "run_dataset_discovery_full_crawl"
    else:
        next_action = "add_or_repair_supported_crawler_handler"
    notes = coverage_note(source, current_scope)
    return SourceSeedCoverage(
        source_id=source.source_id,
        provider_id=source.provider_id,
        source_type=source.source_type,
        configured_mode=configured_mode,
        inferred_mode=inferred_mode,
        current_seed_scope=current_scope,
        full_crawl_supported=full_crawl_supported,
        complete_seed_ready=complete_ready,
        has_search_terms=has_terms,
        search_term_count=len(source.search_terms),
        max_results=source.max_results,
        next_action=next_action,
        notes=notes,
    )


def infer_seed_discovery_mode(source: DatasetDiscoverySource) -> str:
    if source.source_type in ENTRY_LISTING_SOURCE_TYPES:
        return "complete_entry_listing_available"
    if source.source_type in PAGINATED_CATALOG_SOURCE_TYPES:
        return "paginated_catalog_available"
    return "unsupported_or_unknown"


def coverage_note(source: DatasetDiscoverySource, current_scope: str) -> str:
    if current_scope == "bounded_search_terms":
        return (
            "目前 catalog 以 `search_terms` 做安全抽樣；若要展示完整 seed 嘗試，"
            "請用 `--dataset-discovery-complete-seed` 讓 crawler 忽略樣本詞，"
            "並用 `--dataset-discovery-max-pages` 保留安全上限。"
        )
    if current_scope in {"entry_listing", "paginated_catalog", "complete_entry_listing"}:
        return (
            "入口已能作為完整 seed 嘗試起點；後續仍需候選審核、"
            "adapter resolver、manifest verification 與 import 才會進入資產生命週期。"
        )
    if source.source_type not in SUPPORTED_DATASET_SOURCE_TYPES:
        return "這個 `source_type` 尚未對應 crawler handler，需要先新增或修復 crawler。"
    return "這個來源需要人工確認完整 seed 嘗試是否可行；請檢查 crawler 類型與安全上限。"
