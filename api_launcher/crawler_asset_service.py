from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundPayload
from api_launcher.crawler_asset_profiles import crawler_asset_profile_for, load_crawler_asset_profiles
from api_launcher.crawler_assets import load_crawler_asset_source
from api_launcher.crawlers.orchestrator import DatasetCrawlOptions, DatasetCrawlResult, crawl_dataset_sources
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource, dataset_with_candidate_metadata
from api_launcher.repository import ApiCatalogRepository, load_providers
from api_launcher.source_download import (
    SourceDownloadBounds,
    SourceDownloadOptions,
    SourceDownloadPlanBuild,
    build_source_download_plan,
)


CrawlerRunner = Callable[[list[DatasetDiscoverySource], DatasetCrawlOptions], DatasetCrawlResult]


@dataclass(frozen=True)
class CrawlerAssetListingResult:
    """單一 crawler asset 執行 listing 後，回給 UI/Qt/CLI 的穩定結果。"""

    asset_id: str
    source_found: bool
    blocked_reason: str = ""
    candidate_count: int = 0
    upserted_count: int = 0
    skipped_provider_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    next_action: str = ""
    audit_summary: dict[str, object] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reason)

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "source_found": self.source_found,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
            "candidate_count": self.candidate_count,
            "upserted_count": self.upserted_count,
            "skipped_provider_count": self.skipped_provider_count,
            "duplicate_count": self.duplicate_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "next_action": self.next_action,
            "audit_summary": self.audit_summary,
        }


@dataclass(frozen=True)
class CrawlerAssetDownloadPlanResult:
    """Crawler asset 專用的下載計畫草稿結果。

    這層只負責把一個 source asset、使用者輸入的界域 payload，以及既有
    source-download service 接起來；Tk/Qt 只消費這個結果，不重新判斷 crawler
    或 resolver 規則。
    """

    asset_id: str
    source_found: bool
    blocked_reason: str = ""
    bounds: SourceDownloadBounds = field(default_factory=SourceDownloadBounds)
    plan_build: SourceDownloadPlanBuild | None = None
    next_action: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reason)

    @property
    def resolved_plan(self) -> dict[str, object]:
        return self.plan_build.resolved_plan if self.plan_build is not None else {}

    @property
    def original_plan(self) -> dict[str, object]:
        return self.plan_build.original_plan if self.plan_build is not None else {}

    @property
    def direct_download_count(self) -> int:
        return self.plan_build.direct_download_count if self.plan_build is not None else 0

    @property
    def review_required_count(self) -> int:
        if self.plan_build is None:
            return 0
        summary = self.plan_build.resolved_plan.get("summary")
        if not isinstance(summary, dict):
            return 0
        return int(summary.get("review_required_count") or 0)

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "source_found": self.source_found,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
            "bounds": self.bounds.to_dict(),
            "next_action": self.next_action,
            "plan_build": self.plan_build.to_dict() if self.plan_build is not None else {},
        }


def run_crawler_asset_listing(
    asset_id: str,
    conn: sqlite3.Connection,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    timeout: float = 12.0,
    max_results: int = 100,
    full_crawl: bool = True,
    max_pages: int = 0,
    crawl_runner: CrawlerRunner = crawl_dataset_sources,
) -> CrawlerAssetListingResult:
    """執行「入口爬蟲資產 -> candidates -> catalog upsert」的單一後端閉環。

    Tk/Qt 不應直接知道 crawler orchestrator 或 repository 寫入細節；它們只需要
    顯示這個 service 回傳的阻擋理由、候選數與 upsert 統計。
    """

    asset_key = asset_id.strip()
    if not asset_key:
        return CrawlerAssetListingResult(
            asset_id=asset_id,
            source_found=False,
            blocked_reason="missing_asset_id",
            next_action="select_crawler_asset",
        )

    source = load_crawler_asset_source(asset_key, primary_path, local_path)
    if source is None:
        return CrawlerAssetListingResult(
            asset_id=asset_key,
            source_found=False,
            blocked_reason="source_not_found",
            next_action="refresh_or_repair_crawler_source_catalog",
        )

    profile = crawler_asset_profile_for(asset_key, load_crawler_asset_profiles(profile_path))
    if profile.archived:
        return CrawlerAssetListingResult(
            asset_id=asset_key,
            source_found=True,
            blocked_reason="archived",
            next_action="unarchive_before_crawl",
        )
    if not profile.enabled:
        return CrawlerAssetListingResult(
            asset_id=asset_key,
            source_found=True,
            blocked_reason="disabled",
            next_action="enable_before_crawl",
        )

    result = crawl_runner(
        [source],
        DatasetCrawlOptions(
            timeout=timeout,
            max_results_override=max_results,
            full_crawl=full_crawl,
            max_pages=max_pages,
            max_workers=1,
        ),
    )
    upserted, skipped = upsert_crawler_asset_candidates(conn, result.candidates)
    return CrawlerAssetListingResult(
        asset_id=asset_key,
        source_found=True,
        candidate_count=result.candidate_count,
        upserted_count=upserted,
        skipped_provider_count=skipped,
        duplicate_count=result.duplicate_count,
        error_count=result.error_count,
        warning_count=result.warning_count,
        next_action=result.next_action,
        audit_summary=result.audit_summary,
    )


def build_crawler_asset_download_plan(
    asset_id: str,
    conn: sqlite3.Connection,
    *,
    bounds_payload: CrawlerAssetBoundPayload | None = None,
    downloads_root: str | Path = "downloads",
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    timeout: float = 12.0,
    max_results: int = 100,
    full_crawl: bool = True,
    max_pages: int = 0,
) -> CrawlerAssetDownloadPlanResult:
    """Build a reviewable download plan from one crawler asset.

    The function intentionally reuses ``build_source_download_plan`` instead of
    rebuilding candidate/resolver rules in the crawler-asset UI.  Bounds are
    carried as backend metadata even when a specific source cannot apply them
    yet; unresolved entries stay in adapter review.
    """

    asset_key = asset_id.strip()
    if not asset_key:
        return CrawlerAssetDownloadPlanResult(
            asset_id=asset_id,
            source_found=False,
            blocked_reason="missing_asset_id",
            next_action="select_crawler_asset",
        )

    source = load_crawler_asset_source(asset_key, primary_path, local_path)
    if source is None:
        return CrawlerAssetDownloadPlanResult(
            asset_id=asset_key,
            source_found=False,
            blocked_reason="source_not_found",
            next_action="refresh_or_repair_crawler_source_catalog",
        )

    profile = crawler_asset_profile_for(asset_key, load_crawler_asset_profiles(profile_path))
    if profile.archived:
        return CrawlerAssetDownloadPlanResult(
            asset_id=asset_key,
            source_found=True,
            blocked_reason="archived",
            next_action="unarchive_before_building_download_plan",
        )
    if not profile.enabled:
        return CrawlerAssetDownloadPlanResult(
            asset_id=asset_key,
            source_found=True,
            blocked_reason="disabled",
            next_action="enable_before_building_download_plan",
        )

    options = source_download_options_from_crawler_asset_payload(
        bounds_payload,
        timeout=timeout,
        max_results=max_results,
        full_crawl=full_crawl,
        max_pages=max_pages,
    )
    plan_build = build_source_download_plan(
        [source],
        ApiCatalogRepository(conn),
        downloads_root,
        options,
    )
    return CrawlerAssetDownloadPlanResult(
        asset_id=asset_key,
        source_found=True,
        bounds=options.bounds,
        plan_build=plan_build,
        next_action=plan_build.crawl_result.next_action,
    )


def source_download_options_from_crawler_asset_payload(
    payload: CrawlerAssetBoundPayload | None,
    *,
    timeout: float = 12.0,
    max_results: int = 100,
    full_crawl: bool = True,
    max_pages: int = 0,
) -> SourceDownloadOptions:
    """Translate frontend-neutral crawler bounds into source-download options."""

    bounds = source_download_bounds_from_crawler_asset_payload(payload)
    effective_max_results = bounds.candidate_limit or max_results
    effective_max_pages = bounds.max_pages or max_pages
    return SourceDownloadOptions(
        bounds=bounds,
        timeout=timeout,
        max_results_override=effective_max_results,
        search_terms_override=bounds.search_terms,
        full_crawl=full_crawl or bounds.full_crawl,
        max_pages=effective_max_pages,
        max_workers=1,
    )


def source_download_bounds_from_crawler_asset_payload(payload: CrawlerAssetBoundPayload | None) -> SourceDownloadBounds:
    """Convert crawler asset bounds payload into the backend bounds contract."""

    if payload is None:
        return SourceDownloadBounds()
    values = dict(payload.maps_to_values)
    facets = dict(payload.facet_values)
    candidate_limit = int_bound(values.get("SourceDownloadBounds.candidate_limit"), default=0)
    sample_limit = int_bound(values.get("SourceDownloadBounds.sample_limit"), default=25)
    max_pages = int_bound(values.get("SourceDownloadBounds.max_pages"), default=0)
    version_limit = int_bound(values.get("SourceDownloadBounds.version_limit"), default=1)
    bbox = bbox_bound(values.get("SourceDownloadBounds.bbox") or facets.get("bbox"))
    time_values = facets.get("time") if isinstance(facets.get("time"), dict) else {}
    search_terms = tuple_bound(values.get("SourceDownloadBounds.search_terms"))
    if not search_terms:
        search_terms = selector_terms_from_facets(facets)
    required_columns = tuple_bound(values.get("SourceDownloadBounds.required_columns"))
    return SourceDownloadBounds(
        candidate_limit=candidate_limit,
        version_limit=version_limit,
        sample_limit=sample_limit,
        max_pages=max_pages,
        full_crawl=bool_bound(values.get("SourceDownloadBounds.full_crawl"), default=False),
        start_date=str(values.get("SourceDownloadBounds.start_date") or time_values.get("start_date") or "").strip(),
        end_date=str(values.get("SourceDownloadBounds.end_date") or time_values.get("end_date") or "").strip(),
        bbox=bbox,
        search_terms=search_terms,
        required_columns=required_columns,
        time_field=str(values.get("SourceDownloadBounds.time_field") or time_values.get("time_field") or "").strip(),
        longitude_field=str(values.get("SourceDownloadBounds.longitude_field") or "").strip(),
        latitude_field=str(values.get("SourceDownloadBounds.latitude_field") or "").strip(),
        schema_probe_required=True,
    )


def selector_terms_from_facets(facets: dict[str, object]) -> tuple[str, ...]:
    terms: list[str] = []
    for key in ("dataset", "collection", "package", "resource", "file_pattern", "format"):
        terms.extend(tuple_bound(facets.get(key)))
    return tuple(dict.fromkeys(terms))


def int_bound(value: object, *, default: int) -> int:
    if value in ("", None, (), []):
        return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def bool_bound(value: object, *, default: bool) -> bool:
    if value in ("", None, (), []):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def tuple_bound(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    if not text:
        return ()
    return (text,)


def bbox_bound(value: object) -> tuple[float, float, float, float] | None:
    if value in ("", None, (), []):
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return tuple(float(item) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def upsert_crawler_asset_candidates(
    conn: sqlite3.Connection,
    candidates: tuple[DatasetCandidate, ...] | list[DatasetCandidate],
) -> tuple[int, int]:
    """把 crawler candidates 收斂進 catalog，並保留 provider 缺失的跳過統計。"""

    existing_provider_ids = {provider.provider_id for provider in load_providers(conn)}
    repository = ApiCatalogRepository(conn)
    upserted = 0
    skipped_provider = 0
    for candidate in candidates:
        if candidate.dataset.provider_id not in existing_provider_ids:
            skipped_provider += 1
            continue
        repository.upsert_dataset(dataset_with_candidate_metadata(candidate))
        upserted += 1
    return upserted, skipped_provider
