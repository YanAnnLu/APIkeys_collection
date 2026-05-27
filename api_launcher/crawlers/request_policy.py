from __future__ import annotations

from dataclasses import dataclass

from api_launcher.crawlers.types import (
    DatasetDiscoverySource,
    normalize_source_credential_mode,
    normalize_source_terms_risk,
)


DEFAULT_FULL_CRAWL_PAGE_SIZE = 100


@dataclass(frozen=True)
class SourceRequestPolicy:
    """Effective request/access policy for one crawler source invocation."""

    timeout_seconds: float
    max_pages: int
    page_size: int
    rate_limit_seconds: float
    credential_mode: str
    terms_risk: str

    def to_dict(self) -> dict[str, object]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_pages": self.max_pages,
            "page_size": self.page_size,
            "rate_limit_seconds": self.rate_limit_seconds,
            "credential_mode": self.credential_mode,
            "terms_risk": self.terms_risk,
        }


def source_request_policy(
    source: DatasetDiscoverySource,
    *,
    fallback_timeout: float,
    fallback_max_pages: int,
    max_results_override: int,
    full_crawl: bool,
) -> SourceRequestPolicy:
    # This is the typed staging point for the future middleware/decorator layer.
    return SourceRequestPolicy(
        timeout_seconds=effective_source_crawl_timeout(source, fallback_timeout),
        max_pages=effective_source_crawl_max_pages(source, fallback_max_pages),
        page_size=effective_source_crawl_page_size(source, max_results_override, full_crawl),
        rate_limit_seconds=float(source.crawl_rate_limit_seconds or 0.0),
        credential_mode=normalize_source_credential_mode(source.credential_mode),
        terms_risk=normalize_source_terms_risk(source.terms_risk),
    )


def effective_source_crawl_timeout(source: DatasetDiscoverySource, fallback_timeout: float) -> float:
    # 來源 profile 可宣告自己的 HTTP timeout；未設定時才使用 CLI/UI 全域選項。
    return source.crawl_timeout_seconds if source.crawl_timeout_seconds > 0 else fallback_timeout


def effective_source_crawl_max_pages(source: DatasetDiscoverySource, fallback_max_pages: int) -> int:
    """Return the effective full-crawl page cap for one source.

    `crawl_max_pages` is a source-level safety cap. A lower runtime cap can
    further restrict it, but a runtime cap should not accidentally raise the
    source profile's declared politeness boundary.
    """

    source_cap = source.crawl_max_pages
    runtime_cap = fallback_max_pages
    if source_cap > 0 and runtime_cap > 0:
        return min(source_cap, runtime_cap)
    if source_cap > 0:
        return source_cap
    return runtime_cap


def effective_source_crawl_page_size(
    source: DatasetDiscoverySource,
    max_results_override: int,
    full_crawl: bool,
) -> int:
    """Return the per-request page size for source discovery."""

    source_page_size = source.crawl_page_size
    if max_results_override > 0:
        if source_page_size > 0:
            return min(max_results_override, source_page_size)
        return max_results_override
    if source_page_size > 0:
        return source_page_size
    limit = source.max_results
    if full_crawl:
        return max(limit, DEFAULT_FULL_CRAWL_PAGE_SIZE)
    return limit
