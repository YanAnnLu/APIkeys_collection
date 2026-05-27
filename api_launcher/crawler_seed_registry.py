from __future__ import annotations

from pathlib import Path
from typing import Iterable

from api_launcher.crawler_asset_profiles import set_crawler_asset_seed_favorite


MAX_CRAWLER_SEED_PAGE_SIZE = 50
DEFAULT_CRAWLER_SEED_PAGE_SIZE = 50


def crawler_seed_page(
    repository: object,
    *,
    asset_id: str,
    provider_id: str,
    page: int = 1,
    page_size: int = DEFAULT_CRAWLER_SEED_PAGE_SIZE,
    favorite_seed_uids: Iterable[str] = (),
) -> dict[str, object]:
    """Return a UI-neutral page of seeds already enumerated into the catalog.

    這裡只讀已經由 crawler 寫進本機 catalog 的 seed，不重新打遠端 crawler。
    Web/Tk/Qt 共用這份 contract，避免每個前端各自重算頁碼與收藏狀態。
    """

    clean_asset_id = str(asset_id or "").strip()
    clean_provider_id = str(provider_id or "").strip()
    safe_page, safe_page_size = normalize_crawler_seed_page(page=page, page_size=page_size)
    favorites = frozenset(str(value).strip() for value in favorite_seed_uids if str(value).strip())
    candidates = list_crawler_asset_seed_candidates(
        repository,
        asset_id=clean_asset_id,
        provider_id=clean_provider_id,
    )
    total = len(candidates)
    start = (safe_page - 1) * safe_page_size
    rows = candidates[start : start + safe_page_size]
    page_summary = crawler_seed_page_summary(
        total=total,
        page=safe_page,
        page_size=safe_page_size,
        row_count=len(rows),
    )
    return {
        "asset_id": clean_asset_id,
        "provider_id": clean_provider_id,
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
        "has_more": bool(page_summary["has_more"]),
        "page_summary": page_summary,
        "favorite_seed_count": len(favorites),
        "seeds": [crawler_seed_row(dataset, favorite_seed_uids=favorites) for dataset in rows],
    }


def crawler_seed_page_summary(
    *,
    total: int,
    page: int,
    page_size: int,
    row_count: int,
) -> dict[str, object]:
    """Return display-neutral paging metadata for seed list expansion controls."""

    safe_total = max(0, int(total or 0))
    safe_page, safe_page_size = normalize_crawler_seed_page(page=page, page_size=page_size)
    safe_row_count = max(0, int(row_count or 0))
    start_index = (safe_page - 1) * safe_page_size
    shown_start = start_index + 1 if safe_total and safe_row_count else 0
    shown_end = min(start_index + safe_row_count, safe_total)
    has_more = shown_end < safe_total
    remaining = max(0, safe_total - shown_end)
    page_count = ((safe_total - 1) // safe_page_size + 1) if safe_total else 0
    return {
        "shown_start": shown_start,
        "shown_end": shown_end,
        "row_count": safe_row_count,
        "remaining": remaining,
        "page_count": page_count,
        "has_more": has_more,
        "next_page": safe_page + 1 if has_more else 0,
        "next_action": "show_next_seed_page" if has_more else "seed_page_complete",
    }


def normalize_crawler_seed_page(
    *,
    page: int = 1,
    page_size: int = DEFAULT_CRAWLER_SEED_PAGE_SIZE,
) -> tuple[int, int]:
    """Clamp seed paging input to the product's bounded preview window."""

    safe_page = max(1, int(page or 1))
    safe_page_size = min(max(1, int(page_size or DEFAULT_CRAWLER_SEED_PAGE_SIZE)), MAX_CRAWLER_SEED_PAGE_SIZE)
    return safe_page, safe_page_size


def list_crawler_asset_seed_candidates(
    repository: object,
    *,
    asset_id: str,
    provider_id: str,
) -> list[object]:
    """List catalog candidates that belong to one crawler asset source."""

    candidates = [
        dataset
        for dataset in repository.list_dataset_candidates(status="all", provider_id=provider_id)
        if crawler_seed_belongs_to_asset(dataset, asset_id)
    ]
    return sorted(
        candidates,
        key=lambda dataset: (
            str(getattr(dataset, "title", "") or "").casefold(),
            str(getattr(dataset, "dataset_uid", "") or ""),
        ),
    )


def crawler_seed_belongs_to_asset(dataset: object, asset_id: str) -> bool:
    metadata = getattr(dataset, "metadata", {})
    if not isinstance(metadata, dict):
        return False
    return str(metadata.get("discovery_source_id") or "").strip() == str(asset_id or "").strip()


def crawler_seed_row(
    dataset: object,
    *,
    favorite_seed_uids: Iterable[str] = (),
) -> dict[str, object]:
    """Convert a catalog candidate into the shared seed row payload."""

    metadata = getattr(dataset, "metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    dataset_uid = str(getattr(dataset, "dataset_uid", "") or "")
    dataset_id = str(getattr(dataset, "dataset_id", "") or "")
    title = str(getattr(dataset, "title", "") or "")
    favorite_key = crawler_seed_favorite_key(dataset)
    favorites = frozenset(str(value).strip() for value in favorite_seed_uids if str(value).strip())
    return {
        "dataset_uid": dataset_uid,
        "dataset_id": dataset_id,
        "title": title,
        "favorite_key": favorite_key,
        "native_format": str(getattr(dataset, "native_format", "") or ""),
        "data_type": str(getattr(dataset, "data_type", "") or ""),
        "version": str(getattr(dataset, "version", "") or ""),
        "landing_url": str(getattr(dataset, "landing_url", "") or ""),
        "api_url": str(getattr(dataset, "api_url", "") or ""),
        "candidate_status": str(metadata.get("candidate_status") or ""),
        "source_type": str(metadata.get("discovery_source_type") or ""),
        "data_family": str(metadata.get("data_family") or ""),
        "favorite": favorite_key in favorites,
    }


def crawler_seed_favorite_key(dataset: object) -> str:
    """Return the stable key used by seed favorite state."""

    for attr in ("dataset_uid", "dataset_id", "title"):
        value = str(getattr(dataset, attr, "") or "").strip()
        if value:
            return value
    return ""


def save_crawler_seed_favorite(
    *,
    asset_id: str,
    dataset_uid: str,
    favorite: bool = True,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    """Persist a seed-level favorite and return the shared result payload.

    profile 目前仍是收藏的儲存 lane；這裡先把寫入語意集中起來，讓 Web/Tk/Qt
    之後不需要各自知道 `favorite_seed_uids` 的欄位名稱。
    """

    clean_asset_id = str(asset_id or "").strip()
    clean_dataset_uid = str(dataset_uid or "").strip()
    if not clean_asset_id:
        raise ValueError("asset_id is required")
    if not clean_dataset_uid:
        raise ValueError("dataset_uid is required")
    profile = set_crawler_asset_seed_favorite(
        clean_asset_id,
        clean_dataset_uid,
        bool(favorite),
        profile_path,
    )
    return {
        "asset_id": clean_asset_id,
        "dataset_uid": clean_dataset_uid,
        "favorite": clean_dataset_uid in profile.favorite_seed_uids,
        "favorite_seed_count": len(profile.favorite_seed_uids),
        "next_action": "seed_favorite_saved",
    }


__all__ = [
    "DEFAULT_CRAWLER_SEED_PAGE_SIZE",
    "MAX_CRAWLER_SEED_PAGE_SIZE",
    "crawler_seed_belongs_to_asset",
    "crawler_seed_favorite_key",
    "crawler_seed_page",
    "crawler_seed_page_summary",
    "crawler_seed_row",
    "list_crawler_asset_seed_candidates",
    "normalize_crawler_seed_page",
    "save_crawler_seed_favorite",
]
