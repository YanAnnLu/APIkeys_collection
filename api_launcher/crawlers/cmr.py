from __future__ import annotations

import urllib.parse
from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.fetch import fetch_json, search_endpoint_url
from api_launcher.crawlers.metadata import (
    analysis_hint_for_family,
    infer_data_family,
    merge_categories,
    safe_dataset_id,
    sql_role_for_family,
    storage_hint_for_family,
    temporal_coverage,
    viewer_hint_for_family,
)
from api_launcher.crawlers.pagination import append_new_candidates, discovery_page_cap
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


def cmr_collections_url(endpoint_url: str, search_term: str, limit: int, page_num: int = 0) -> str:
    params = {"page_size": str(max(1, limit)), "downloadable": "true", "keyword": search_term}
    if page_num > 0:
        params["page_num"] = str(page_num)
    return search_endpoint_url(
        endpoint_url,
        params,
    )


def cmr_payload_entries(payload: dict[str, Any]) -> list[Any]:
    feed = payload.get("feed") if isinstance(payload.get("feed"), dict) else {}
    entries = feed.get("entry", [])
    if not isinstance(payload.get("feed"), dict):
        raise ValueError("CMR payload missing feed object")
    if not isinstance(entries, list):
        raise ValueError("CMR payload missing feed.entry list")
    return entries


def cmr_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    entries = cmr_payload_entries(payload)
    candidates: list[DatasetCandidate] = []
    for item in entries[:limit]:
        if not isinstance(item, dict):
            continue
        concept_id = str(item.get("id") or "").strip()
        short_name = str(item.get("short_name") or item.get("entry_id") or concept_id or "dataset").strip()
        version = str(item.get("version_id") or "").strip()
        dataset_id = safe_dataset_id("-".join(part for part in (short_name, version) if part))
        title = str(item.get("title") or item.get("dataset_id") or short_name)
        summary = str(item.get("summary") or "")
        searchable = " ".join(
            (
                title,
                summary,
                short_name,
                str(item.get("data_center") or ""),
                platform_names(item.get("platforms")),
                " ".join(source.categories),
            )
        )
        data_family = infer_data_family(searchable)
        links = item.get("links") if isinstance(item.get("links"), list) else []
        landing_url = first_cmr_link_url(links, ("metadata", "browse", "documentation")) or source.docs_url or source_url
        api_url = (
            "https://cmr.earthdata.nasa.gov/search/granules.json?"
            + urllib.parse.urlencode({"collection_concept_id": concept_id})
            if concept_id
            else source_url
        )
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, tuple(filter(None, (str(item.get("data_center") or ""),)))),
            data_type=data_family,
            native_format="cmr_collection",
            geographic_scope=source.geographic_scope,
            temporal_coverage=temporal_coverage(item.get("time_start"), item.get("time_end")),
            landing_url=landing_url,
            api_url=api_url,
            version=version or "discovered",
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
                "cmr_concept_id": concept_id,
                "short_name": short_name,
                "data_center": item.get("data_center") or "",
                "cloud_hosted": bool(item.get("cloud_hosted")),
                "online_access_flag": bool(item.get("online_access_flag")),
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
                confidence=0.85,
                evidence=("NASA CMR collection search result", f"short_name: {short_name}"),
            )
        )
    return candidates


def paginated_cmr_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    for page_num in range(1, discovery_page_cap(max_pages) + 1):
        url = cmr_collections_url(source.endpoint_url, search_term, page_size, page_num)
        payload = fetch_json(url, timeout=timeout)
        entries = cmr_payload_entries(payload)
        page_candidates = cmr_candidates_from_payload(source, payload, url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        if not entries or len(entries) < page_size or added == 0:
            break
    return candidates


def first_cmr_link_url(links: list[object], hints: tuple[str, ...]) -> str:
    for link in links:
        if not isinstance(link, dict) or not link.get("href"):
            continue
        searchable = " ".join(str(link.get(key) or "") for key in ("rel", "title", "type")).lower()
        if any(hint in searchable for hint in hints):
            return str(link["href"])
    for link in links:
        if isinstance(link, dict) and str(link.get("href") or "").startswith("http"):
            return str(link["href"])
    return ""


def platform_names(platforms: object) -> str:
    if not isinstance(platforms, list):
        return ""
    names = []
    for platform in platforms:
        if isinstance(platform, dict):
            names.append(str(platform.get("short_name") or platform.get("long_name") or ""))
    return " ".join(name for name in names if name)
