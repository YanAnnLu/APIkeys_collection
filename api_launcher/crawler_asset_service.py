from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from api_launcher.crawler_asset_profiles import crawler_asset_profile_for, load_crawler_asset_profiles
from api_launcher.crawler_assets import load_crawler_asset_source
from api_launcher.crawlers.orchestrator import DatasetCrawlOptions, DatasetCrawlResult, crawl_dataset_sources
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource, dataset_with_candidate_metadata
from api_launcher.repository import ApiCatalogRepository, load_providers


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
