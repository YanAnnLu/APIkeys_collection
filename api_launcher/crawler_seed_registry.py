"""Seed paging and favorite state for crawler assets.

Crawler listing can enumerate many seeds into the local catalog.  UI surfaces
should not rerun discovery just because the user scrolls a seed list.  This
module provides the shared read/write contract:

- read a bounded page of already-enumerated seeds from the catalog
- mark favorite seeds at seed level, not crawler-asset level

The result payloads are frontend-neutral so Tk, Web, CLI, and future Qt can use
the same paging/favorite semantics.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from api_launcher.content_registry import content_import_profile, detect_content_format
from api_launcher.crawler_asset_profiles import set_crawler_asset_seed_favorite


# Keep pages intentionally small.  "Show more" expands the local view while the
# actual enumeration completeness is tracked separately by crawler listing
# status and remote pagination metadata.
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
    seed_rows = [crawler_seed_row(dataset, favorite_seed_uids=favorites) for dataset in rows]
    recommended_seed = recommended_crawler_seed_row(seed_rows)
    return {
        "asset_id": clean_asset_id,
        "provider_id": clean_provider_id,
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
        "has_more": bool(page_summary["has_more"]),
        "page_summary": page_summary,
        "favorite_seed_count": len(favorites),
        "recommended_seed": recommended_seed,
        "recommended_seed_uid": str(recommended_seed.get("dataset_uid") or ""),
        "recommended_seed_next_action": "download_recommended_seed" if recommended_seed else "select_seed_manually",
        "seeds": seed_rows,
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
    """List catalog candidates that belong to one crawler asset source.

    This is a catalog filter, not a live crawler call.  Discovery/listing code is
    responsible for putting seed candidates into the repository first.
    """

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
    """Check the discovery-source marker written during crawler listing."""

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
    import_profile = crawler_seed_content_import_profile(dataset)
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
        "content_import_profile": import_profile,
        "content_importability": str(import_profile.get("importability") or ""),
        "content_pipeline_lane": str(import_profile.get("pipeline_lane") or ""),
        "content_next_action": str(import_profile.get("next_action") or ""),
        "content_display_label": str(import_profile.get("display_label") or ""),
        "content_display_tone": str(import_profile.get("display_tone") or ""),
        "content_review_required": bool(import_profile.get("review_required")),
        "favorite": favorite_key in favorites,
    }


def recommended_crawler_seed_row(seed_rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Return a compact one-click default seed from the visible page.

    UI shells should not guess which row is safest for a first download.  A seed
    is recommended only when the backend content contract says it can enter the
    SQLite import lane without adapter review.
    """

    for row in seed_rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("content_review_required"):
            continue
        if str(row.get("content_pipeline_lane") or "") != "sqlite_curated_import":
            continue
        return {
            "dataset_uid": str(row.get("dataset_uid") or ""),
            "dataset_id": str(row.get("dataset_id") or ""),
            "title": str(row.get("title") or ""),
            "content_display_label": str(row.get("content_display_label") or ""),
            "content_next_action": str(row.get("content_next_action") or ""),
        }
    return {}


def crawler_seed_content_import_profile(dataset: object) -> dict[str, object]:
    """Return the content import profile that a seed row should display.

    Seed pages appear before a user builds or runs a download plan.  Computing
    this profile here gives every UI surface an early, truthful hint such as
    "can import to SQLite" or "needs content parser review" without requiring
    JavaScript, Tk, or future Qt code to know content-format rules.
    """

    metadata = getattr(dataset, "metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    existing_profile = first_mapping(
        metadata.get("content_import_profile"),
        metadata.get("import_profile"),
        nested_mapping(metadata.get("content_detection"), "import_profile"),
        nested_mapping(metadata.get("content_detection"), "capability", "import_profile"),
    )
    if existing_profile:
        return dict(existing_profile)

    native_format = str(getattr(dataset, "native_format", "") or "").strip()
    if native_format:
        return content_import_profile(native_format).to_dict()

    detection = detect_content_format(
        url=str(getattr(dataset, "api_url", "") or ""),
        filename=str(getattr(dataset, "landing_url", "") or ""),
    )
    return detection.to_dict()["import_profile"]


def first_mapping(*values: object) -> Mapping[str, object] | None:
    """Return the first mapping from optional nested metadata slots."""

    for value in values:
        if isinstance(value, Mapping):
            return value
    return None


def nested_mapping(value: object, *keys: str) -> Mapping[str, object] | None:
    """Safely read a nested mapping without making metadata shape assumptions."""

    current = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current if isinstance(current, Mapping) else None


def crawler_seed_favorite_key(dataset: object) -> str:
    """Return the stable key used by seed favorite state.

    ``dataset_uid`` is preferred because it survives title changes.  The
    fallback chain keeps older or partially imported candidates selectable.
    """

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
    "crawler_seed_content_import_profile",
    "crawler_seed_favorite_key",
    "crawler_seed_page",
    "crawler_seed_page_summary",
    "crawler_seed_row",
    "list_crawler_asset_seed_candidates",
    "normalize_crawler_seed_page",
    "recommended_crawler_seed_row",
    "save_crawler_seed_favorite",
]
