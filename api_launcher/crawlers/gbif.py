from __future__ import annotations

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
    viewer_hint_for_family,
)
from api_launcher.crawlers.pagination import append_new_candidates, discovery_page_cap
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


def gbif_dataset_search_url(endpoint_url: str, search_term: str, limit: int, offset: int | None = None) -> str:
    params = {"q": search_term, "limit": str(max(1, limit))}
    if offset is not None:
        params["offset"] = str(max(0, offset))
    return search_endpoint_url(endpoint_url, params)


def gbif_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("GBIF dataset search payload missing results list")
    candidates: list[DatasetCandidate] = []
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        dataset_id = safe_dataset_id(key or item.get("doi") or item.get("title") or "dataset")
        title = str(item.get("title") or dataset_id)
        description = str(item.get("description") or "")
        keywords = tuple(str(value) for value in item.get("keywords") or [] if value)
        searchable = " ".join((title, description, str(item.get("type") or ""), " ".join(keywords), " ".join(source.categories)))
        data_family = infer_data_family(searchable)
        landing_url = f"https://www.gbif.org/dataset/{key}" if key else source.docs_url or source_url
        api_url = f"https://api.gbif.org/v1/dataset/{key}" if key else source_url
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, keywords[:6], (str(item.get("type") or ""),)),
            data_type=data_family,
            native_format="gbif_dataset",
            geographic_scope=source.geographic_scope,
            landing_url=landing_url,
            api_url=api_url,
            license_url=str(item.get("license") or ""),
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
                "gbif_key": key,
                "dataset_type": item.get("type") or "",
                "record_count": item.get("recordCount") or 0,
                "publishing_organization": item.get("publishingOrganizationTitle") or "",
                "hosting_organization": item.get("hostingOrganizationTitle") or "",
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.84,
                evidence=("GBIF dataset search result", f"key: {key or 'unknown'}"),
            )
        )
    return candidates


def paginated_gbif_candidates(
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
        url = gbif_dataset_search_url(source.endpoint_url, search_term, page_size, offset=offset)
        payload = fetch_json(url, timeout=timeout)
        results = payload.get("results", [])
        page_candidates = gbif_candidates_from_payload(source, payload, url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        end_of_records = bool(payload.get("endOfRecords"))
        if not isinstance(results, list) or not results or end_of_records or len(results) < page_size or added == 0:
            break
        offset += len(results)
    return candidates
