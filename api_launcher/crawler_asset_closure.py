"""Recommended-seed closure runner for crawler assets.

This module turns the existing crawler asset workflow into one bounded,
agent-readable operation:

``asset -> live listing -> local seed page -> recommended seed -> download/import``

It intentionally reuses the current listing, seed paging, and formal
download/import services.  The goal is not a new crawler path; it is a stable
evidence artifact proving that a public source can complete the small loop.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api_launcher.crawler_asset_download import (
    CrawlerAssetDownloadImportResult,
    run_crawler_seed_download_import,
)
from api_launcher.crawler_asset_profiles import crawler_asset_favorite_seed_uids
from api_launcher.crawler_asset_service import CrawlerAssetListingResult, run_crawler_asset_listing
from api_launcher.crawler_assets import load_crawler_asset_source
from api_launcher.crawler_seed_registry import DEFAULT_CRAWLER_SEED_PAGE_SIZE, crawler_seed_page
from api_launcher.repository import ApiCatalogRepository


ListingRunner = Callable[..., CrawlerAssetListingResult]
SeedDownloadRunner = Callable[..., CrawlerAssetDownloadImportResult]


@dataclass(frozen=True)
class CrawlerAssetRecommendedSeedClosureResult:
    """Structured result for the recommended-seed closure operation."""

    asset_id: str
    provider_id: str
    source_found: bool
    listing_result: CrawlerAssetListingResult | None
    seed_page: dict[str, object]
    recommended_seed_uid: str
    download_import_result: CrawlerAssetDownloadImportResult | None
    downloads_root: Path
    curated_sqlite_path: Path
    plan_path: Path | None
    closure_stage: str
    next_action: str

    @property
    def succeeded(self) -> bool:
        return bool(self.download_import_result and self.download_import_result.succeeded)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "asset_id": self.asset_id,
            "provider_id": self.provider_id,
            "source_found": self.source_found,
            "closure_stage": self.closure_stage,
            "succeeded": self.succeeded,
            "recommended_seed_uid": self.recommended_seed_uid,
            "seed_page": self.seed_page,
            "artifacts": {
                "downloads_root": str(self.downloads_root),
                "curated_sqlite": str(self.curated_sqlite_path),
            },
            "next_action": self.next_action,
        }
        if self.plan_path is not None:
            payload["artifacts"]["plan"] = str(self.plan_path)
        if self.listing_result is not None:
            payload["listing"] = self.listing_result.to_dict()
        if self.download_import_result is not None:
            payload["download_import"] = self.download_import_result.to_dict()
        return payload


def run_recommended_seed_closure(
    asset_id: str,
    repository: ApiCatalogRepository,
    downloads_root: str | Path,
    *,
    provider_id: str = "",
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    import_sqlite_path: str | Path | None = None,
    listing_timeout: float = 12.0,
    listing_limit: int = 100,
    listing_max_pages: int = 0,
    seed_page_size: int = DEFAULT_CRAWLER_SEED_PAGE_SIZE,
    download_timeout: float = 30.0,
    download_limit: int = 1,
    import_existing_table_policy: str = "rename",
    listing_runner: ListingRunner = run_crawler_asset_listing,
    seed_download_runner: SeedDownloadRunner = run_crawler_seed_download_import,
) -> CrawlerAssetRecommendedSeedClosureResult:
    """Run listing, select the backend recommendation, then download/import it.

    The source catalog can enumerate many seeds.  This runner picks only the
    existing backend recommendation from page one, so tests and smoke jobs can
    prove a real source closure without turning it into an unbounded crawl.
    """

    clean_asset_id = str(asset_id or "").strip()
    clean_provider_id = str(provider_id or "").strip()
    root = Path(downloads_root).expanduser()
    closure_root = root / "recommended_seed_closure" / safe_closure_dirname(clean_asset_id)
    curated_sqlite = Path(import_sqlite_path) if import_sqlite_path is not None else closure_root / "curated_sources.db"
    plan_path = closure_root / "resolved_recommended_seed_download_plan.json"

    source = load_crawler_asset_source(clean_asset_id, primary_path, local_path) if clean_asset_id else None
    source_found = source is not None
    if not clean_provider_id and source is not None:
        clean_provider_id = str(getattr(source, "provider_id", "") or "").strip()

    listing_result = listing_runner(
        clean_asset_id,
        repository.conn,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
        timeout=listing_timeout,
        max_results=max(1, int(listing_limit or 1)),
        max_pages=max(0, int(listing_max_pages or 0)),
        complete_seed=True,
    )
    if listing_result.blocked:
        return CrawlerAssetRecommendedSeedClosureResult(
            asset_id=clean_asset_id,
            provider_id=clean_provider_id,
            source_found=source_found,
            listing_result=listing_result,
            seed_page={},
            recommended_seed_uid="",
            download_import_result=None,
            downloads_root=closure_root,
            curated_sqlite_path=curated_sqlite,
            plan_path=None,
            closure_stage="listing_blocked",
            next_action=listing_result.next_action or "review_crawler_asset_listing",
        )

    if not clean_provider_id:
        return CrawlerAssetRecommendedSeedClosureResult(
            asset_id=clean_asset_id,
            provider_id=clean_provider_id,
            source_found=source_found,
            listing_result=listing_result,
            seed_page={},
            recommended_seed_uid="",
            download_import_result=None,
            downloads_root=closure_root,
            curated_sqlite_path=curated_sqlite,
            plan_path=None,
            closure_stage="provider_id_missing",
            next_action="provide_crawler_asset_provider_id_or_fix_source_profile",
        )

    favorite_seed_uids = crawler_asset_favorite_seed_uids(clean_asset_id, str(profile_path or "") or None)
    page_payload = crawler_seed_page(
        repository,
        asset_id=clean_asset_id,
        provider_id=clean_provider_id,
        page=1,
        page_size=seed_page_size,
        favorite_seed_uids=favorite_seed_uids,
    )
    recommended_seed_uid = str(page_payload.get("recommended_seed_uid") or "")
    if not recommended_seed_uid:
        return CrawlerAssetRecommendedSeedClosureResult(
            asset_id=clean_asset_id,
            provider_id=clean_provider_id,
            source_found=source_found,
            listing_result=listing_result,
            seed_page=page_payload,
            recommended_seed_uid="",
            download_import_result=None,
            downloads_root=closure_root,
            curated_sqlite_path=curated_sqlite,
            plan_path=None,
            closure_stage="no_recommended_seed",
            next_action="review_seed_page_or_adjust_source_listing",
        )

    result = seed_download_runner(
        clean_asset_id,
        recommended_seed_uid,
        repository,
        closure_root,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
        import_sqlite_path=curated_sqlite,
        plan_path=plan_path,
        timeout=download_timeout,
        download_limit=download_limit,
        import_existing_table_policy=import_existing_table_policy,
    )
    return CrawlerAssetRecommendedSeedClosureResult(
        asset_id=clean_asset_id,
        provider_id=clean_provider_id,
        source_found=source_found,
        listing_result=listing_result,
        seed_page=page_payload,
        recommended_seed_uid=recommended_seed_uid,
        download_import_result=result,
        downloads_root=closure_root,
        curated_sqlite_path=curated_sqlite,
        plan_path=plan_path,
        closure_stage="download_import_completed" if result.succeeded else "download_import_incomplete",
        next_action=result.pipeline.next_action or result.plan_result.user_next_action,
    )


def recommended_seed_closure_payload(results: list[CrawlerAssetRecommendedSeedClosureResult]) -> dict[str, object]:
    succeeded = sum(1 for result in results if result.succeeded)
    return {
        "command": "crawler_asset_recommended_seed_closure",
        "request_count": len(results),
        "succeeded_count": succeeded,
        "failed_or_blocked_count": max(0, len(results) - succeeded),
        "next_action": "review_recommended_seed_closure_results" if results else "select_crawler_asset",
        "results": [result.to_dict() for result in results],
    }


def safe_closure_dirname(asset_id: str) -> str:
    """Return a stable folder segment for closure artifacts."""

    raw = str(asset_id or "").strip() or "crawler_asset"
    safe = [char if char.isalnum() or char in {"-", "_", "."} else "_" for char in raw]
    return "".join(safe)[:120].strip("._") or "crawler_asset"


__all__ = [
    "CrawlerAssetRecommendedSeedClosureResult",
    "recommended_seed_closure_payload",
    "run_recommended_seed_closure",
    "safe_closure_dirname",
]
