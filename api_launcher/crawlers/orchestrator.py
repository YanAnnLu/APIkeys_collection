from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, replace

from api_launcher.crawlers import dataset_sources
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource


@dataclass(frozen=True)
class DatasetCrawlOptions:
    timeout: float = 12.0
    max_results_override: int = 0
    search_terms_override: tuple[str, ...] = ()
    full_crawl: bool = False
    max_pages: int = 0
    max_workers: int = 4
    min_candidates_per_source_override: int = -1


@dataclass(frozen=True)
class DatasetSourceCrawlResult:
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
    def audit_status(self) -> str:
        if self.error:
            return "error"
        if self.warnings:
            return "warning"
        return "pass"


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


def crawl_dataset_sources(
    sources: list[DatasetDiscoverySource],
    options: DatasetCrawlOptions | None = None,
) -> DatasetCrawlResult:
    """Run configured dataset-source crawlers concurrently and dedupe results.

    Each source crawler is still responsible for its own pagination and parsing.
    The orchestrator only coordinates parallel execution, error collection, and
    cross-source dedupe.
    """
    options = options or DatasetCrawlOptions()
    if not sources:
        return DatasetCrawlResult(candidates=(), source_results=())

    max_workers = max(1, min(options.max_workers, len(sources)))
    source_results: list[DatasetSourceCrawlResult] = []
    candidates: list[DatasetCandidate] = []
    seen: set[tuple[str, str]] = set()
    duplicate_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dataset-crawler") as executor:
        futures = {
            executor.submit(_crawl_one_source, source, options): source
            for source in sources
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
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


def _crawl_one_source(source: DatasetDiscoverySource, options: DatasetCrawlOptions) -> DatasetSourceCrawlResult:
    try:
        candidates = dataset_sources.discover_dataset_candidates_for_source(
            source,
            timeout=options.timeout,
            max_results_override=options.max_results_override,
            search_terms_override=options.search_terms_override,
            full_crawl=options.full_crawl,
            max_pages=options.max_pages,
        )
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
