from __future__ import annotations

from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.metadata import (
    analysis_hint_for_family,
    infer_data_family,
    matches_any_term,
    merge_categories,
    safe_dataset_id,
    sql_role_for_family,
    storage_hint_for_family,
    temporal_coverage,
    viewer_hint_for_family,
)
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


def stac_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
    search_terms: tuple[str, ...],
) -> list[DatasetCandidate]:
    collections = payload.get("collections")
    if not isinstance(collections, list):
        raise ValueError("STAC collections payload missing collections list")
    candidates: list[DatasetCandidate] = []
    for item in collections:
        if not isinstance(item, dict):
            continue
        keywords = tuple(str(value) for value in item.get("keywords") or [] if value)
        providers = item.get("providers") if isinstance(item.get("providers"), list) else []
        asset_map = item.get("assets") or item.get("item_assets") or {}
        if not isinstance(asset_map, dict):
            asset_map = {}
        searchable = " ".join(
            (
                str(item.get("id") or ""),
                str(item.get("title") or ""),
                str(item.get("description") or ""),
                " ".join(keywords),
                " ".join(provider.get("name", "") for provider in providers if isinstance(provider, dict)),
            )
        )
        if search_terms and not matches_any_term(searchable, search_terms):
            continue
        dataset_id = safe_dataset_id(str(item.get("id") or "dataset"))
        title = str(item.get("title") or dataset_id)
        data_family = infer_data_family(searchable)
        links = item.get("links") if isinstance(item.get("links"), list) else []
        landing_url = first_stac_link_url(links, ("self", "root", "parent")) or source.docs_url or source_url
        api_url = first_stac_link_url(links, ("items", "self")) or source_url
        temporal = stac_temporal_coverage(item.get("extent"))
        categories = merge_categories(source.categories, keywords[:6])
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=categories or ("stac",),
            data_type=data_family,
            native_format="stac_collection",
            geographic_scope=source.geographic_scope,
            temporal_coverage=temporal,
            landing_url=landing_url,
            api_url=api_url,
            license_url=str(item.get("license") or ""),
            version=str(item.get("version") or item.get("stac_version") or "discovered"),
            metadata={
                "candidate_status": "needs_review",
                "discovery_source_id": source.source_id,
                "discovery_source_type": source.source_type,
                "source_url": source_url,
                "provider_backed": True,
                "data_family": data_family,
                "storage_hint": storage_hint_for_family(data_family),
                "sql_role": sql_role_for_family(data_family),
                "analysis_hint": analysis_hint_for_family(data_family),
                "viewer_hint": viewer_hint_for_family(data_family),
                "stac_id": item.get("id") or "",
                "stac_version": item.get("stac_version") or "",
                "keywords": keywords,
                "providers": providers,
                "asset_keys": sorted(asset_map.keys())[:24],
                "extent": item.get("extent") or {},
                "links": links[:12],
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.87,
                evidence=("STAC collection", f"collection: {dataset_id}"),
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def first_stac_link_url(links: list[object], rels: tuple[str, ...]) -> str:
    for rel in rels:
        for link in links:
            if isinstance(link, dict) and str(link.get("rel") or "").lower() == rel and link.get("href"):
                return str(link["href"])
    return ""


def stac_temporal_coverage(extent: object) -> str:
    if not isinstance(extent, dict):
        return ""
    temporal = extent.get("temporal") if isinstance(extent.get("temporal"), dict) else {}
    intervals = temporal.get("interval") if isinstance(temporal.get("interval"), list) else []
    if not intervals or not isinstance(intervals[0], list):
        return ""
    start = str(intervals[0][0] or "") if len(intervals[0]) > 0 else ""
    end = str(intervals[0][1] or "") if len(intervals[0]) > 1 else ""
    return temporal_coverage(start, end)
