from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from api_launcher.crawlers import dataset_sources
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource

DatasetCandidateRunner = Callable[[DatasetDiscoverySource, "DatasetCrawlOptions"], list[DatasetCandidate]]


@dataclass(frozen=True)
class DatasetCrawlOptions:
    # options 控制抓取邊界；full_crawl 也必須受 max_pages/MAX_FULL_CRAWL_PAGES 約束。
    timeout: float = 12.0
    max_results_override: int = 0
    search_terms_override: tuple[str, ...] = ()
    full_crawl: bool = False
    max_pages: int = 0
    max_workers: int = 4
    min_candidates_per_source_override: int = -1


@dataclass(frozen=True)
class DatasetSourceCrawlResult:
    # 每個 source 都有獨立 audit 結果，避免單一入口壞掉時掩蓋其他入口成果。
    source_id: str
    provider_id: str
    source_type: str
    candidate_count: int = 0
    unique_candidate_count: int = 0
    duplicate_candidate_count: int = 0
    error: str = ""
    warnings: tuple[str, ...] = ()
    candidates: tuple[DatasetCandidate, ...] = ()

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def warning_codes(self) -> tuple[str, ...]:
        # warning 文字給人看，code 給 CLI/agent 做 routing；兩者共用冒號前綴，避免另建一套枚舉後忘記同步。
        return tuple(warning.split(":", 1)[0].strip() for warning in self.warnings if warning.strip())

    @property
    def audit_status(self) -> str:
        if self.error:
            return "error"
        if self.warnings:
            return "warning"
        return "pass"

    @property
    def next_action(self) -> str:
        # next_action 是給 UI/agent 的短路由；真正原因仍保留在 error/warnings，避免把修復細節藏起來。
        if self.error:
            return "inspect_crawler_error"
        codes = set(self.warning_codes)
        if not codes:
            return "review_candidates" if self.candidate_count else "no_candidates_but_allowed"
        if "candidate_metadata_issue" in codes:
            return "repair_candidate_metadata_mapping"
        if "zero_candidates" in codes:
            return "repair_crawler_query_or_parser"
        if "below_min_candidates" in codes:
            return "adjust_query_or_min_expected_candidates"
        if "all_candidates_duplicate" in codes or "duplicate_heavy_output" in codes:
            return "review_source_overlap_or_dedupe"
        return "inspect_crawler_audit_warnings"


@dataclass(frozen=True)
class DatasetCrawlResult:
    candidates: tuple[DatasetCandidate, ...]
    source_results: tuple[DatasetSourceCrawlResult, ...]
    duplicate_count: int = 0
    error_count: int = 0

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def warning_count(self) -> int:
        return sum(result.warning_count for result in self.source_results)

    @property
    def audit_issue_count(self) -> int:
        return self.error_count + self.warning_count

    @property
    def next_action(self) -> str:
        # 結果層 next_action 只做總體路由；逐 source 的修復方向在 source_results 裡。
        if self.audit_issue_count:
            return "inspect_source_audit_results_before_upsert_or_promotion"
        discovered_count = self.candidate_count or sum(result.candidate_count for result in self.source_results)
        if discovered_count:
            return "review_or_upsert_dataset_candidates"
        return "configure_or_select_dataset_discovery_sources"

    @property
    def audit_summary(self) -> dict[str, Any]:
        return crawl_result_audit_summary(self)


def crawl_result_audit_summary(result: DatasetCrawlResult) -> dict[str, Any]:
    """產生 UI 與 agent handoff 可直接讀取的 crawler audit 摘要。"""
    by_status = {"pass": 0, "warning": 0, "error": 0}
    by_warning_code: dict[str, int] = {}
    by_next_action: dict[str, int] = {}
    problem_sources: list[dict[str, object]] = []

    for source in result.source_results:
        by_status[source.audit_status] = by_status.get(source.audit_status, 0) + 1
        by_next_action[source.next_action] = by_next_action.get(source.next_action, 0) + 1
        for code in source.warning_codes:
            by_warning_code[code] = by_warning_code.get(code, 0) + 1
        if source.audit_status == "pass":
            continue
        # 摘要只做快速分流；完整 warning/error 仍留在 source_results 供人類追查。
        problem_sources.append(
            {
                "source_id": source.source_id,
                "provider_id": source.provider_id,
                "source_type": source.source_type,
                "audit_status": source.audit_status,
                "next_action": source.next_action,
                "warning_codes": list(source.warning_codes),
                "error": source.error,
            }
        )

    if result.error_count:
        status = "error"
    elif result.warning_count:
        status = "warning"
    elif result.candidate_count or any(source.candidate_count for source in result.source_results):
        status = "pass"
    else:
        status = "empty"

    return {
        "status": status,
        "source_count": len(result.source_results),
        "candidate_count": result.candidate_count,
        "duplicate_count": result.duplicate_count,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "audit_issue_count": result.audit_issue_count,
        "next_action": result.next_action,
        "by_status": by_status,
        "by_warning_code": dict(sorted(by_warning_code.items())),
        "by_next_action": dict(sorted(by_next_action.items())),
        "problem_source_count": len(problem_sources),
        "problem_sources": sorted(problem_sources, key=lambda item: str(item["source_id"])),
    }


def crawl_dataset_sources(
    sources: list[DatasetDiscoverySource],
    options: DatasetCrawlOptions | None = None,
    source_crawler: DatasetCandidateRunner | None = None,
) -> DatasetCrawlResult:
    """Run configured dataset-source crawlers concurrently and dedupe results.

    Each source crawler is still responsible for its own pagination and parsing.
    The orchestrator only coordinates parallel execution, error collection, and
    cross-source dedupe.
    """
    options = options or DatasetCrawlOptions()
    source_crawler = source_crawler or default_source_crawler
    if not sources:
        return DatasetCrawlResult(candidates=(), source_results=())

    max_workers = max(1, min(options.max_workers, len(sources)))
    source_order = {source.source_id: index for index, source in enumerate(sources)}
    source_results: list[DatasetSourceCrawlResult] = []
    completed_results: list[DatasetSourceCrawlResult] = []
    candidates: list[DatasetCandidate] = []
    seen: set[tuple[str, str]] = set()
    duplicate_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dataset-crawler") as executor:
        futures = {
            executor.submit(_crawl_one_source, source, options, source_crawler): source
            for source in sources
        }
        for future in concurrent.futures.as_completed(futures):
            completed_results.append(future.result())

    # 並行完成順序會受平台與網路抖動影響；去重歸屬必須回到 catalog 設定順序才穩定。
    for result in sorted(completed_results, key=lambda item: (source_order.get(item.source_id, len(source_order)), item.source_id)):
        source_unique_count = 0
        source_duplicate_count = 0
        for candidate in result.candidates:
            key = (candidate.dataset.provider_id, candidate.dataset.dataset_id)
            if key in seen:
                duplicate_count += 1
                source_duplicate_count += 1
                continue
            seen.add(key)
            source_unique_count += 1
            candidates.append(candidate)
        warnings = result.warnings
        if result.candidate_count > 0 and source_unique_count == 0:
            warnings = warnings + (
                "all_candidates_duplicate: source returned candidates, but every candidate was already seen "
                "from another source; verify source overlap, search terms, or provider mapping",
            )
        elif source_duplicate_count and source_duplicate_count >= source_unique_count:
            warnings = warnings + (
                "duplicate_heavy_output: source returned "
                f"{source_duplicate_count} duplicate candidates and only {source_unique_count} unique candidates; "
                "verify pagination, parser IDs, search terms, or overlapping source configuration",
            )
        source_results.append(
            replace(
                result,
                unique_candidate_count=source_unique_count,
                duplicate_candidate_count=source_duplicate_count,
                warnings=warnings,
            )
        )

    source_results.sort(key=lambda item: item.source_id)
    candidates.sort(key=lambda item: (item.dataset.provider_id, item.dataset.dataset_id, item.dataset.title.lower()))
    return DatasetCrawlResult(
        candidates=tuple(candidates),
        source_results=tuple(source_results),
        duplicate_count=duplicate_count,
        error_count=sum(1 for result in source_results if result.error),
    )


def default_source_crawler(source: DatasetDiscoverySource, options: DatasetCrawlOptions) -> list[DatasetCandidate]:
    """執行正式 crawler handler；測試/contract smoke 可注入替身而不碰 live 網路。"""

    return dataset_sources.discover_dataset_candidates_for_source(
        source,
        timeout=options.timeout,
        max_results_override=options.max_results_override,
        search_terms_override=options.search_terms_override,
        full_crawl=options.full_crawl,
        max_pages=options.max_pages,
    )


def _crawl_one_source(
    source: DatasetDiscoverySource,
    options: DatasetCrawlOptions,
    source_crawler: DatasetCandidateRunner,
) -> DatasetSourceCrawlResult:
    try:
        candidates = source_crawler(source, options)
    except Exception as exc:
        return DatasetSourceCrawlResult(
            source_id=source.source_id,
            provider_id=source.provider_id,
            source_type=source.source_type,
            error=f"{type(exc).__name__}: {exc}",
        )
    warnings = audit_source_candidates(source, candidates, options)
    return DatasetSourceCrawlResult(
        source_id=source.source_id,
        provider_id=source.provider_id,
        source_type=source.source_type,
        candidate_count=len(candidates),
        warnings=warnings,
        candidates=tuple(candidates),
    )


def audit_source_candidates(
    source: DatasetDiscoverySource,
    candidates: list[DatasetCandidate],
    options: DatasetCrawlOptions,
) -> tuple[str, ...]:
    min_expected = (
        options.min_candidates_per_source_override
        if options.min_candidates_per_source_override >= 0
        else source.min_expected_candidates
    )
    warnings: list[str] = []
    if min_expected > 0 and not candidates:
        warnings.append(
            "zero_candidates: crawler finished without an exception but returned 0 candidates; "
            "verify the endpoint, search terms, pagination, and parser shape"
        )
    elif min_expected > 0 and len(candidates) < min_expected:
        warnings.append(f"below_min_candidates: expected at least {min_expected}, got {len(candidates)}")

    invalid_reasons: set[str] = set()
    for candidate in candidates:
        dataset = candidate.dataset
        if dataset.provider_id != source.provider_id:
            invalid_reasons.add("provider_mismatch")
        if not dataset.dataset_id:
            invalid_reasons.add("missing_dataset_id")
        if not dataset.title:
            invalid_reasons.add("missing_title")
        if not candidate.source_url:
            invalid_reasons.add("missing_source_url")
        if not candidate.evidence:
            invalid_reasons.add("missing_evidence")
        if candidate.confidence <= 0:
            invalid_reasons.add("missing_confidence")
    if invalid_reasons:
        warnings.append("candidate_metadata_issue: " + ", ".join(sorted(invalid_reasons)))
    return tuple(warnings)
