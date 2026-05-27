from __future__ import annotations

from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.fetch import fetch_json, search_endpoint_url
from api_launcher.crawlers.metadata import (
    analysis_hint_for_family,
    choose_native_format,
    first_link_url,
    infer_data_family,
    merge_categories,
    safe_dataset_id,
    sql_role_for_family,
    storage_hint_for_family,
    temporal_coverage,
    tuple_names,
    viewer_hint_for_family,
)
from api_launcher.crawlers.pagination import append_new_candidates, discovery_page_cap, polite_crawl_delay
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


def ncei_search_url(endpoint_url: str, search_term: str, limit: int, offset: int = 0) -> str:
    # NCEI search 先列資料集 metadata；實際 data/access API 必須在 resolver 加日期/空間邊界。
    params = {"limit": str(max(1, limit)), "available": "true", "text": search_term}
    if offset > 0:
        params["offset"] = str(offset)
    return search_endpoint_url(
        endpoint_url,
        params,
    )


def ncei_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    # NCEI candidate 保留 dataset id 與 API URL，讓後續 bounded resolver 能產生小樣本 plan。
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("NCEI search payload missing results list")
    candidates: list[DatasetCandidate] = []
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        dataset_id = safe_dataset_id(str(item.get("id") or item.get("fileId") or item.get("name") or "dataset"))
        title = str(item.get("name") or dataset_id)
        description = str(item.get("description") or "")
        formats = tuple_names(item.get("formats"))
        observation_types = tuple_names(item.get("observationTypes"))
        keyword_names = tuple_names(item.get("keywords"))
        categories = merge_categories(source.categories, formats[:3], observation_types[:3])
        data_family = infer_data_family(" ".join((title, description, " ".join(categories), " ".join(keyword_names))))
        links = item.get("links") if isinstance(item.get("links"), dict) else {}
        landing_url = first_link_url(links, ("other", "documentation", "access")) or source.docs_url or source_url
        api_url = first_link_url(links, ("access",)) or source_url
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=categories or ("discovered",),
            data_type=data_family,
            native_format=choose_native_format(formats),
            geographic_scope=source.geographic_scope,
            temporal_coverage=temporal_coverage(item.get("startDate"), item.get("endDate")),
            landing_url=landing_url,
            api_url=api_url,
            version="discovered",
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
                "ncei_result_id": item.get("id") or "",
                "ncei_file_id": item.get("fileId") or "",
                "formats": formats,
                "observation_types": observation_types,
                "keyword_names": keyword_names[:12],
                "links": links,
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.82,
                evidence=("NCEI search result", f"formats: {', '.join(formats) or 'unknown'}"),
            )
        )
    return candidates


def paginated_ncei_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    offset = 0
    for _page in range(discovery_page_cap(max_pages)):
        url = ncei_search_url(source.endpoint_url, search_term, page_size, offset)
        payload = fetch_json(url, timeout=timeout)
        page_items = payload.get("results", [])
        page_candidates = ncei_candidates_from_payload(source, payload, url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        if not isinstance(page_items, list) or not page_items or len(page_items) < page_size or added == 0:
            break
        offset += len(page_items)
        polite_crawl_delay(source.crawl_rate_limit_seconds)
    return candidates


def ncei_candidates_for_source(
    source: DatasetDiscoverySource,
    timeout: float,
    limit: int,
    search_terms: tuple[str, ...],
    full_crawl: bool,
    max_pages: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    for term in search_terms or ("",):
        if full_crawl:
            candidates.extend(paginated_ncei_candidates(source, term, timeout, limit, max_pages))
            continue
        url = ncei_search_url(source.endpoint_url, term, limit)
        payload = fetch_json(url, timeout=timeout)
        candidates.extend(ncei_candidates_from_payload(source, payload, url, limit))
    return candidates
