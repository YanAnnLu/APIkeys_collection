from __future__ import annotations

from typing import Iterable


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

    這層只讀本機 catalog，不重新跑 crawler。Web/Tk/Qt 都應該共用這個分頁
    contract，避免「顯示更多 seed」在不同 UI 裡各自實作成不同語意。
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
    return {
        "asset_id": clean_asset_id,
        "provider_id": clean_provider_id,
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
        "has_more": start + safe_page_size < total,
        "favorite_seed_count": len(favorites),
        "seeds": [crawler_seed_row(dataset, favorite_seed_uids=favorites) for dataset in rows],
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


__all__ = [
    "DEFAULT_CRAWLER_SEED_PAGE_SIZE",
    "MAX_CRAWLER_SEED_PAGE_SIZE",
    "crawler_seed_belongs_to_asset",
    "crawler_seed_favorite_key",
    "crawler_seed_page",
    "crawler_seed_row",
    "list_crawler_asset_seed_candidates",
    "normalize_crawler_seed_page",
]
