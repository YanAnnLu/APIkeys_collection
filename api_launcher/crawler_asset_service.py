"""Crawler asset orchestration services.

This module is the backend seam between configured crawler assets and the rest
of the RRKAL pipeline.  It keeps the full MVP path explicit:

``asset -> source listing -> catalog candidates -> download plan -> review gate``

UI shells should call these services and render the returned payloads.  They
should not reimplement source lookup, profile enable/archive guards, crawler
execution, candidate upsert, download-plan resolution, or seed validation.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundPayload
from api_launcher.crawler_asset_bounds import bounds_facets_for_source
from api_launcher.crawler_asset_display import seed_enumeration_display_payload
from api_launcher.crawler_asset_payloads import source_download_options_from_crawler_asset_payload
from api_launcher.crawler_asset_profiles import (
    crawler_asset_bounds_signature,
    crawler_asset_profile_for,
    crawler_asset_source_signature,
    load_crawler_asset_profiles,
)
from api_launcher.crawler_assets import load_crawler_asset_source
from api_launcher.crawler_run_records import crawler_run_record, crawler_run_record_from_result
from api_launcher.adapter_plan_resolver import resolve_adapter_review_plan_payload
from api_launcher.crawler_seed_registry import crawler_seed_belongs_to_asset
from api_launcher.crawlers.orchestrator import (
    DatasetCrawlOptions,
    DatasetCrawlResult,
    DatasetSourceCrawlResult,
    crawl_dataset_sources,
)
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource, dataset_with_candidate_metadata
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry
from api_launcher.repository import ApiCatalogRepository, load_providers
from api_launcher.source_download import (
    apply_source_download_bounds,
    credential_blocked_plan_entry,
    credential_gate_for_provider,
    SourceDownloadBounds,
    SourceDownloadOptions,
    SourceDownloadPlanBuild,
    build_source_download_plan,
    selected_version_options,
    source_candidate_snapshot_signature,
)


CrawlerRunner = Callable[[list[DatasetDiscoverySource], DatasetCrawlOptions], DatasetCrawlResult]


@dataclass(frozen=True)
class CrawlerAssetListingResult:
    """Stable listing result returned to UI/CLI surfaces.

    Listing is the "enumerate seeds into the local catalog" action.  The result
    records both local write counts and remote pagination evidence so a frontend
    can say "show more locally" versus "remote may have more" without guessing.
    """

    asset_id: str
    source_found: bool
    listing_mode: str = "bounded"
    blocked_reason: str = ""
    candidate_count: int = 0
    upserted_count: int = 0
    skipped_provider_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    next_action: str = ""
    audit_summary: dict[str, object] = field(default_factory=dict)
    max_results: int = 1000
    max_pages: int = 0
    full_crawl: bool = True
    complete_seed: bool = False
    search_scope: str = "configured_terms"
    remote_pagination_status: str = "not_reported"
    remote_exhausted: bool | None = None
    remote_next_page_token: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reason)

    def to_dict(self) -> dict[str, object]:
        payload = {
            "asset_id": self.asset_id,
            "source_found": self.source_found,
            "listing_mode": self.listing_mode,
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
            "max_results": self.max_results,
            "max_pages": self.max_pages,
            "full_crawl": self.full_crawl,
            "complete_seed": self.complete_seed,
            "search_scope": self.search_scope,
            "remote_pagination": crawler_remote_pagination_payload(self),
            "seed_enumeration": crawler_seed_enumeration_payload(self),
        }
        payload["run_record"] = crawler_run_record(
            stage="crawler_listing",
            asset_id=self.asset_id,
            status=crawler_listing_record_status(self),
            next_action=self.next_action,
            candidate_count=self.candidate_count,
            error_count=self.error_count,
            warning_count=self.warning_count,
            duplicate_count=self.duplicate_count,
        )
        return payload


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
    source_signature: str = ""
    bounds_signature: str = ""
    previous_candidate_snapshot_signature: str = ""
    candidate_snapshot_changed: bool = False
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

    @property
    def outcome_bucket(self) -> str:
        """回傳穩定狀態桶，讓 Tk/Qt 顯示結果時不用重判下載政策。"""

        if self.blocked:
            return "blocked"
        if self.plan_build is None:
            return "empty_plan"
        if self.direct_download_count > 0 and self.review_required_count > 0:
            return "partial_review_required"
        if self.direct_download_count > 0:
            return "ready_to_download"
        if self.review_required_count > 0:
            return "review_required"
        if self.plan_build.candidate_count == 0:
            return "zero_candidates"
        return "empty_plan"

    @property
    def user_next_action(self) -> str:
        """給 UI 顯示下一步，避免畫面層解析 resolved plan 內部結構。"""

        if self.blocked:
            return self.next_action
        bucket = self.outcome_bucket
        if bucket in {"ready_to_download", "partial_review_required"}:
            return "open_downloader_and_start_or_pause_queue"
        if bucket == "review_required":
            return "open_adapter_review_or_adjust_bounds"
        if bucket == "zero_candidates":
            return "adjust_bounds_or_refresh_source_listing"
        return self.next_action or "review_resolved_download_plan"

    def to_dict(self) -> dict[str, object]:
        payload = {
            "asset_id": self.asset_id,
            "source_found": self.source_found,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
            "outcome_bucket": self.outcome_bucket,
            "bounds": self.bounds.to_dict(),
            "source_signature": self.source_signature,
            "bounds_signature": self.bounds_signature,
            "previous_candidate_snapshot_signature": self.previous_candidate_snapshot_signature,
            "candidate_snapshot_changed": self.candidate_snapshot_changed,
            "next_action": self.next_action,
            "user_next_action": self.user_next_action,
            "plan_build": self.plan_build.to_dict() if self.plan_build is not None else {},
        }
        payload["run_record"] = crawler_run_record(
            stage="download_plan_build",
            asset_id=self.asset_id,
            status=crawler_plan_record_status(self),
            outcome_bucket=self.outcome_bucket,
            next_action=self.user_next_action,
            candidate_count=self.plan_build.candidate_count if self.plan_build is not None else 0,
            direct_download_count=self.direct_download_count,
            review_required_count=self.review_required_count,
            source_signature=self.source_signature,
            bounds_signature=self.bounds_signature,
            candidate_snapshot_signature=(
                self.plan_build.candidate_snapshot_signature if self.plan_build is not None else ""
            ),
            candidate_snapshot_count=self.plan_build.candidate_snapshot_count if self.plan_build is not None else 0,
        )
        return payload


def crawler_listing_record_status(result: CrawlerAssetListingResult) -> str:
    """Collapse listing details into the compact run-record status."""

    if result.blocked:
        return "blocked"
    if result.error_count:
        return "error"
    if result.warning_count:
        return "warning"
    return "completed"


def crawler_seed_enumeration_payload(result: CrawlerAssetListingResult) -> dict[str, object]:
    """Return display-safe seed enumeration status for UI shells.

    Candidate count alone is ambiguous: 1,000 candidates can mean "complete"
    for a small catalog or "local safety limit reached" for a large portal.
    This payload keeps the interpretation in the service layer so Web/Tk/Qt
    do not duplicate count heuristics.
    """

    candidate_count = int(result.candidate_count or 0)
    max_results = int(result.max_results or 0)
    warning_count = int(result.warning_count or 0)
    error_count = int(result.error_count or 0)
    remote_pagination = crawler_remote_pagination_payload(result)
    remote_exhausted = remote_pagination["exhausted"] is True
    remote_has_more = remote_pagination["status"] == "has_more"
    if result.blocked:
        return seed_enumeration_display_payload(
            "blocked",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
            next_action=result.next_action,
        )
    if error_count:
        return seed_enumeration_display_payload(
            "error",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
            next_action=result.next_action,
        )
    if candidate_count <= 0:
        return seed_enumeration_display_payload(
            "empty",
            candidate_count=0,
            max_results=max_results,
            remote_pagination=remote_pagination,
            next_action=result.next_action,
        )
    limited = bool(result.complete_seed and max_results > 0 and candidate_count >= max_results and not remote_exhausted)
    if limited:
        return seed_enumeration_display_payload(
            "local_limit_reached",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
        )
    if warning_count:
        return seed_enumeration_display_payload(
            "warning",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
            warning_count=warning_count,
            next_action=result.next_action,
            completion_confidence=_remote_seed_completion_confidence(
                remote_exhausted=remote_exhausted,
                remote_has_more=remote_has_more,
                default="warning_with_unknown_remote_completion",
            ),
        )
    if result.complete_seed:
        return seed_enumeration_display_payload(
            "within_current_limits",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
            next_action=result.next_action,
            completion_confidence=_remote_seed_completion_confidence(
                remote_exhausted=remote_exhausted,
                remote_has_more=remote_has_more,
                default="within_current_local_limits",
            ),
        )
    return seed_enumeration_display_payload(
        "bounded_sample",
        candidate_count=candidate_count,
        max_results=max_results,
        remote_pagination=remote_pagination,
        next_action=result.next_action,
    )


def _remote_seed_completion_confidence(*, remote_exhausted: bool, remote_has_more: bool, default: str) -> str:
    if remote_exhausted:
        return "remote_reported_exhausted"
    if remote_has_more:
        return "remote_has_more"
    return default


def crawler_remote_pagination_payload(result: CrawlerAssetListingResult) -> dict[str, object]:
    """Return explicit remote pagination evidence without exposing raw tokens."""

    status = str(result.remote_pagination_status or "").strip() or "not_reported"
    token_present = bool(str(result.remote_next_page_token or "").strip())
    exhausted = result.remote_exhausted
    if exhausted is True:
        status = "exhausted"
    elif exhausted is False and token_present and status == "not_reported":
        status = "has_more"
    return {
        "status": status,
        "exhausted": exhausted,
        "next_page_token_present": token_present,
    }


def crawler_plan_record_status(result: CrawlerAssetDownloadPlanResult) -> str:
    """Collapse plan outcome details into the compact run-record status."""

    if result.blocked:
        return "blocked"
    if result.outcome_bucket in {"ready_to_download", "partial_review_required"}:
        return "ready"
    if result.outcome_bucket in {"review_required", "zero_candidates"}:
        return "review"
    return "empty"


def crawler_asset_listing_event_context(result: CrawlerAssetListingResult) -> dict[str, object]:
    """Return the compact listing-event payload shared by Tk/Web/CLI callers.

    Structured events are handoff evidence.  Keep this payload bounded and
    display-safe; do not store full candidate lists or raw remote pagination
    tokens here.
    """

    return {
        "asset_id": str(result.asset_id or ""),
        "listing_mode": str(result.listing_mode or ""),
        "source_found": bool(result.source_found),
        "blocked": bool(result.blocked),
        "blocked_reason": str(result.blocked_reason or ""),
        "candidate_count": int(result.candidate_count or 0),
        "upserted_count": int(result.upserted_count or 0),
        "skipped_provider_count": int(result.skipped_provider_count or 0),
        "duplicate_count": int(result.duplicate_count or 0),
        "error_count": int(result.error_count or 0),
        "warning_count": int(result.warning_count or 0),
        "next_action": str(result.next_action or ""),
        "max_results": int(result.max_results or 0),
        "max_pages": int(result.max_pages or 0),
        "complete_seed": bool(result.complete_seed),
        "search_scope": str(result.search_scope or ""),
        "remote_pagination": crawler_remote_pagination_payload(result),
        "seed_enumeration": crawler_seed_enumeration_payload(result),
        "run_record": crawler_run_record_from_result(result),
    }


def run_crawler_asset_listing(
    asset_id: str,
    conn: sqlite3.Connection,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    timeout: float = 12.0,
    max_results: int = 1000,
    full_crawl: bool = True,
    max_pages: int = 0,
    complete_seed: bool = True,
    search_terms_override: tuple[str, ...] = (),
    crawl_runner: CrawlerRunner = crawl_dataset_sources,
) -> CrawlerAssetListingResult:
    """執行「入口爬蟲資產 -> candidates -> catalog upsert」的單一後端閉環。

    Tk/Qt 不應直接知道 crawler orchestrator 或 repository 寫入細節；它們只需要
    顯示這個 service 回傳的阻擋理由、候選數與 upsert 統計。
    """

    # The three early guards below are intentionally service-side.  UI callers
    # may gray out buttons, but the backend must still protect archived/disabled
    # assets and missing source profiles because CLI/Web/Tk can all reach here.
    asset_key = asset_id.strip()
    if not asset_key:
        return CrawlerAssetListingResult(
            asset_id=asset_id,
            source_found=False,
            listing_mode="complete_seed" if complete_seed else "bounded",
            blocked_reason="missing_asset_id",
            next_action="select_crawler_asset",
            max_results=max_results,
            max_pages=max_pages,
            full_crawl=full_crawl,
            complete_seed=complete_seed,
        )

    source = load_crawler_asset_source(asset_key, primary_path, local_path)
    if source is None:
        return CrawlerAssetListingResult(
            asset_id=asset_key,
            source_found=False,
            listing_mode="complete_seed" if complete_seed else "bounded",
            blocked_reason="source_not_found",
            next_action="refresh_or_repair_crawler_source_catalog",
            max_results=max_results,
            max_pages=max_pages,
            full_crawl=full_crawl,
            complete_seed=complete_seed,
        )

    profile = crawler_asset_profile_for(asset_key, load_crawler_asset_profiles(profile_path))
    if profile.archived:
        return CrawlerAssetListingResult(
            asset_id=asset_key,
            source_found=True,
            listing_mode="complete_seed" if complete_seed else "bounded",
            blocked_reason="archived",
            next_action="unarchive_before_crawl",
            max_results=max_results,
            max_pages=max_pages,
            full_crawl=full_crawl,
            complete_seed=complete_seed,
        )
    if not profile.enabled:
        return CrawlerAssetListingResult(
            asset_id=asset_key,
            source_found=True,
            listing_mode="complete_seed" if complete_seed else "bounded",
            blocked_reason="disabled",
            next_action="enable_before_crawl",
            max_results=max_results,
            max_pages=max_pages,
            full_crawl=full_crawl,
            complete_seed=complete_seed,
        )

    effective_search_terms = search_terms_override
    if complete_seed and not effective_search_terms:
        # 空字串是現有 crawler handler 的「不套關鍵字」哨兵，用來要求入口盡量枚舉所有 seed。
        effective_search_terms = ("",)
    if effective_search_terms:
        search_scope = "complete_seed" if complete_seed else "override_terms"
    else:
        search_scope = "configured_terms" if source.search_terms else "unbounded"

    # Injecting ``crawl_runner`` keeps this orchestration testable without live
    # network.  Production callers use ``crawl_dataset_sources``.
    result = crawl_runner(
        [source],
        DatasetCrawlOptions(
            timeout=timeout,
            max_results_override=max_results,
            search_terms_override=effective_search_terms,
            full_crawl=full_crawl,
            max_pages=max_pages,
            max_workers=1,
        ),
    )
    upserted, skipped = upsert_crawler_asset_candidates(conn, result.candidates)
    source_result = result.source_results[0] if result.source_results else None
    return CrawlerAssetListingResult(
        asset_id=asset_key,
        source_found=True,
        listing_mode="complete_seed" if complete_seed else "bounded",
        candidate_count=result.candidate_count,
        upserted_count=upserted,
        skipped_provider_count=skipped,
        duplicate_count=result.duplicate_count,
        error_count=result.error_count,
        warning_count=result.warning_count,
        next_action=result.next_action,
        audit_summary=result.audit_summary,
        max_results=max_results,
        max_pages=max_pages,
        full_crawl=full_crawl,
        complete_seed=complete_seed,
        search_scope=search_scope,
        remote_pagination_status=source_result.remote_pagination_status if source_result is not None else "not_reported",
        remote_exhausted=source_result.remote_exhausted if source_result is not None else None,
        remote_next_page_token=source_result.remote_next_page_token if source_result is not None else "",
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

    # Plan building mirrors listing guards, but it does not upsert candidates by
    # itself.  It resolves whichever candidates the source-download service
    # returns into direct-download or adapter-review plan entries.
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

    # Bounds payloads come from the dynamic form contract.  The translation into
    # SourceDownloadOptions happens once here so UI shells do not know internal
    # SourceDownloadBounds field names.
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
    # 只在 explicit rebuild 後比較候選 digest；讀取 profile 時不得假裝知道遠端是否更新。
    previous_candidate_snapshot_signature = str(
        profile.latest_plan_passport.get("candidate_snapshot_signature") if profile.latest_plan_passport else ""
    ).strip()
    current_candidate_snapshot_signature = str(plan_build.candidate_snapshot_signature or "").strip()
    candidate_snapshot_changed = bool(
        previous_candidate_snapshot_signature
        and current_candidate_snapshot_signature
        and previous_candidate_snapshot_signature != current_candidate_snapshot_signature
    )
    return CrawlerAssetDownloadPlanResult(
        asset_id=asset_key,
        source_found=True,
        bounds=options.bounds,
        plan_build=plan_build,
        source_signature=crawler_asset_source_signature(source),
        bounds_signature=crawler_asset_bounds_signature(bounds_facets_for_source(source)),
        previous_candidate_snapshot_signature=previous_candidate_snapshot_signature,
        candidate_snapshot_changed=candidate_snapshot_changed,
        next_action=plan_build.crawl_result.next_action,
    )


def build_crawler_seed_download_plan(
    asset_id: str,
    dataset_uid: str,
    conn: sqlite3.Connection,
    *,
    bounds_payload: CrawlerAssetBoundPayload | None = None,
    downloads_root: str | Path = "downloads",
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    timeout: float = 12.0,
) -> CrawlerAssetDownloadPlanResult:
    """Build a formal download plan from one enumerated catalog seed.

    Seed rows are already catalog objects.  This path validates that the seed
    belongs to the selected crawler asset, then reuses the same plan resolver
    and bounds machinery as the asset-level download lane.  It deliberately
    avoids a fresh source crawl so a user can act on the visible seed list.
    """

    # Seed downloads are intentionally catalog-first.  They let the user act on
    # a visible seed row without triggering a new live crawl.
    asset_key = asset_id.strip()
    dataset_key = dataset_uid.strip()
    if not asset_key:
        return CrawlerAssetDownloadPlanResult(
            asset_id=asset_id,
            source_found=False,
            blocked_reason="missing_asset_id",
            next_action="select_crawler_asset",
        )
    if not dataset_key:
        return CrawlerAssetDownloadPlanResult(
            asset_id=asset_key,
            source_found=False,
            blocked_reason="missing_dataset_uid",
            next_action="select_seed",
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
            next_action="unarchive_before_downloading_seed",
        )
    if not profile.enabled:
        return CrawlerAssetDownloadPlanResult(
            asset_id=asset_key,
            source_found=True,
            blocked_reason="disabled",
            next_action="enable_before_downloading_seed",
        )

    repository = ApiCatalogRepository(conn)
    dataset = repository.get_dataset(dataset_key)
    if dataset is None or not crawler_seed_belongs_to_asset(dataset, asset_key):
        return CrawlerAssetDownloadPlanResult(
            asset_id=asset_key,
            source_found=True,
            blocked_reason="seed_not_found_for_asset",
            next_action="refresh_seed_listing_or_select_another_seed",
        )

    providers = {provider.provider_id: provider for provider in repository.load_providers([dataset.provider_id])}
    provider = providers.get(dataset.provider_id)
    if provider is None:
        return CrawlerAssetDownloadPlanResult(
            asset_id=asset_key,
            source_found=True,
            blocked_reason="provider_not_found_for_seed",
            next_action="repair_provider_catalog_before_download",
        )

    options = source_download_options_from_crawler_asset_payload(
        bounds_payload,
        timeout=timeout,
        max_results=1,
        full_crawl=False,
        max_pages=1,
    )
    gate = credential_gate_for_provider(provider)
    version_options = selected_version_options(dataset, options)
    all_version_options = selected_version_options(
        dataset,
        SourceDownloadOptions(bounds=options.bounds, include_all_versions=True),
    )
    entries: list[dict[str, object]] = []
    for option in version_options:
        entry = provider_dataset_version_plan_entry(provider, dataset, option, downloads_root=downloads_root)
        entry = apply_source_download_bounds(entry, options.bounds)
        if not gate.allows_download:
            entry = credential_blocked_plan_entry(entry, gate)
        entries.append(entry)

    original_plan = build_dataset_download_plan(entries, plan_name="crawler_seed_download_plan")
    original_plan["source"] = {
        "kind": "catalog_seed_download_plan",
        "asset_id": asset_key,
        "dataset_uid": dataset.dataset_uid,
        "dataset_id": dataset.dataset_id,
        "provider_id": dataset.provider_id,
        "source_id": source.source_id,
        "source_type": source.source_type,
        "candidate_count": 1,
        "version_policy": {
            "selected_versions": {key: list(value) for key, value in options.selected_versions.items()},
            "selected_version_count": len(version_options),
            "available_version_count": len(all_version_options),
        },
        "bounds": options.bounds.to_dict(),
    }
    resolved_plan, resolution = resolve_adapter_review_plan_payload(original_plan, downloads_root=downloads_root)
    seed_candidate = DatasetCandidate(
        dataset=dataset,
        source_id=source.source_id,
        source_type=source.source_type,
        source_url=source.endpoint_url,
        confidence=1.0,
        evidence=("selected_catalog_seed",),
    )
    crawl_result = DatasetCrawlResult(
        candidates=(seed_candidate,),
        source_results=(
            DatasetSourceCrawlResult(
                source_id=source.source_id,
                provider_id=source.provider_id,
                source_type=source.source_type,
                candidate_count=1,
                unique_candidate_count=1,
                candidates=(seed_candidate,),
            ),
        ),
    )
    plan_build = SourceDownloadPlanBuild(
        crawl_result=crawl_result,
        candidate_count=1,
        upserted_candidate_count=0,
        original_plan=original_plan,
        resolved_plan=resolved_plan,
        resolution=resolution,
        credential_gates=(gate,),
        selected_version_count=len(version_options),
        filtered_version_count=max(0, len(all_version_options) - len(version_options)),
        candidate_snapshot_signature=source_candidate_snapshot_signature((seed_candidate,)),
        candidate_snapshot_count=1,
    )
    previous_candidate_snapshot_signature = str(
        profile.latest_plan_passport.get("candidate_snapshot_signature") if profile.latest_plan_passport else ""
    ).strip()
    current_candidate_snapshot_signature = str(plan_build.candidate_snapshot_signature or "").strip()
    return CrawlerAssetDownloadPlanResult(
        asset_id=asset_key,
        source_found=True,
        bounds=options.bounds,
        plan_build=plan_build,
        source_signature=crawler_asset_source_signature(source),
        bounds_signature=crawler_asset_bounds_signature(bounds_facets_for_source(source)),
        previous_candidate_snapshot_signature=previous_candidate_snapshot_signature,
        candidate_snapshot_changed=bool(
            previous_candidate_snapshot_signature
            and current_candidate_snapshot_signature
            and previous_candidate_snapshot_signature != current_candidate_snapshot_signature
        ),
        next_action="download_selected_seed" if version_options else "adjust_version_selection_for_seed",
    )

def upsert_crawler_asset_candidates(
    conn: sqlite3.Connection,
    candidates: tuple[DatasetCandidate, ...] | list[DatasetCandidate],
) -> tuple[int, int]:
    """把 crawler candidates 收斂進 catalog，並保留 provider 缺失的跳過統計。

    Crawler handlers may find datasets before the provider catalog is complete.
    Skipping unknown providers here keeps listing non-destructive and makes the
    missing-provider count visible to the caller instead of failing the whole
    crawl.
    """

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
