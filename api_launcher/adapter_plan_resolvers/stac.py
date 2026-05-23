from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Callable

from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.downloads.eligibility import DownloadEligibility
from api_launcher.models import Dataset
from api_launcher.plans import dataset_download_target_path, dataset_import_plan_entry


FirstText = Callable[..., str]

STAC_RESOLVER_ID = "stac_bounded_item_search_resolver"
STAC_ITEM_SAMPLE_LIMIT = 1


def stac_bounded_item_search_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
    *,
    first_text: FirstText,
    resolver_id: str = STAC_RESOLVER_ID,
    sample_limit: int = STAC_ITEM_SAMPLE_LIMIT,
) -> dict[str, object]:
    # STAC collection 可能代表大量影像資產；MVP 只取 item metadata 小樣本，不碰 raster asset。
    if not entry_is_stac_collection(entry):
        return {}
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    item_search_url = stac_item_search_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        sample_limit=sample_limit,
    )
    if not item_search_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), option_metadata.get("stac_id"))
    dataset_id = first_text(
        entry.get("dataset_id"),
        version_meta.get("dataset_id"),
        option_metadata.get("stac_id"),
        "stac_collection",
    )
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-stac-items-sample" if version else "stac-items-sample"
    data_family = str(option_metadata.get("data_family") or entry.get("data_type") or "raster_or_grid")
    dataset = Dataset(
        dataset_uid=dataset_uid,
        provider_id=provider_id,
        dataset_id=dataset_id,
        title=first_text(entry.get("dataset_title"), entry.get("name"), dataset_id),
        categories=(
            tuple(str(value) for value in entry.get("categories", ()) if str(value).strip())
            if isinstance(entry.get("categories"), (list, tuple))
            else ()
        ),
        data_type=data_family,
        native_format="geojson",
        geographic_scope=str(entry.get("geographic_scope") or ""),
        landing_url=first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
        api_url=item_search_url,
        license_url=str(entry.get("license_url") or ""),
        version=sample_version,
        metadata={
            **option_metadata,
            "data_family": data_family,
            "bounded_query": {
                "resolver_id": resolver_id,
                "item_search_url": item_search_url,
                "sample_limit": sample_limit,
                "asset_keys": option_metadata.get("asset_keys") or (),
            },
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset_uid,
        dataset_id=dataset_id,
        label="STAC bounded item sample GeoJSON",
        version=sample_version,
        status="resolved_sample",
        download_url=item_search_url,
        landing_url=dataset.landing_url,
        update_strategy="sample_then_review",
        notes="Bounded STAC item search generated from collection metadata; this downloads item metadata only, not raster assets.",
        metadata={"native_format": "geojson", "resolver_id": resolver_id, "source_format": "stac_collection"},
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason=f"The STAC collection was resolved into a bounded item-search GeoJSON request with limit={sample_limit}.",
        direct_url=item_search_url,
    )
    resolved = dict(entry)
    resolved.update(
        {
            "dataset_uid": dataset_uid,
            "dataset_id": dataset_id,
            "dataset_title": dataset.title,
            "dataset_version": option.to_plan_metadata(),
            "source_format": "geojson",
            "target": "local_file_asset",
            "use_staging": True,
            "download_eligibility": eligibility.to_dict(),
            "download_url": item_search_url,
            "target_path": dataset_download_target_path(provider_id, dataset, option, downloads_root).as_posix(),
            "import_plan": dataset_import_plan_entry(dataset, option, eligibility),
            "plan_status": "planned",
            "adapter_resolution": {
                "resolver_id": resolver_id,
                "original_plan_index": plan_index,
                "item_search_url": item_search_url,
                "policy": "bounded_item_metadata_sample_only",
                "sample_limit": sample_limit,
                "source_url": first_text(
                    (entry.get("adapter_review") or {}).get("source_url")
                    if isinstance(entry.get("adapter_review"), dict)
                    else "",
                    entry.get("adapter_review_url"),
                    version_meta.get("download_url"),
                ),
                "asset_keys": list(option_metadata.get("asset_keys") or ()),
            },
        }
    )
    resolved.pop("adapter_review", None)
    resolved.pop("adapter_review_url", None)
    return resolved


def entry_is_stac_collection(entry: dict[str, object]) -> bool:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    markers = {
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("data_type") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
    }
    if {"stac", "stac_collection", "stac_collections"} & markers:
        return True
    return bool(option_metadata.get("stac_id") or option_metadata.get("asset_keys"))


def stac_item_search_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
    sample_limit: int = STAC_ITEM_SAMPLE_LIMIT,
) -> str:
    # 優先使用 catalog links 的 items rel；沒有 rel 時才從 collection URL 推導 /items。
    for link in stac_link_mappings(option_metadata.get("links")):
        if str(link.get("rel") or "").strip().lower() == "items":
            url = first_text(link.get("href"), link.get("url"))
            if url:
                return bounded_stac_items_url(url, sample_limit=sample_limit)

    candidates = [
        first_text(version_meta.get("download_url")),
        first_text(entry.get("adapter_review_url")),
        first_text(entry.get("api_base_url")),
        first_text((entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else ""),
        first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
    ]
    for raw_url in candidates:
        if not raw_url:
            continue
        candidate = stac_items_endpoint_from_url(raw_url, first_text(option_metadata.get("stac_id"), entry.get("dataset_id")))
        if candidate:
            return bounded_stac_items_url(candidate, sample_limit=sample_limit)
    return ""


def stac_link_mappings(links: object) -> list[dict[str, object]]:
    if not isinstance(links, list):
        return []
    return [dict(link) for link in links if isinstance(link, dict)]


def stac_items_endpoint_from_url(raw_url: str, collection_id: str = "") -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    lowered = path.lower()
    if lowered.endswith("/items") or "/items/" in lowered:
        return raw_url
    if "/collections/" in lowered:
        return urllib.parse.urlunparse(parsed._replace(path=f"{path}/items", query=""))
    if lowered.endswith("/collections") and collection_id:
        return urllib.parse.urlunparse(
            parsed._replace(path=f"{path}/{urllib.parse.quote(collection_id, safe='')}/items", query="")
        )
    return ""


def bounded_stac_items_url(url: str, *, sample_limit: int = STAC_ITEM_SAMPLE_LIMIT) -> str:
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["limit"] = str(sample_limit)
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def resource_is_stac_items_link(resource: dict[str, object], url: str) -> bool:
    rel = str(resource.get("rel") or "").strip().lower()
    if rel == "items":
        return True
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.rstrip("/").lower()
    return path.endswith("/items") or "/items/" in path
