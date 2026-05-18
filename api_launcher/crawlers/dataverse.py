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


def dataverse_search_url(endpoint_url: str, search_term: str, limit: int, start: int | None = None) -> str:
    params = {"q": search_term, "type": "dataset", "per_page": str(max(1, limit))}
    if start is not None:
        params["start"] = str(max(0, start))
    return search_endpoint_url(endpoint_url, params)


def dataverse_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Dataverse search payload missing data object")
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Dataverse search payload missing data.items list")
    candidates: list[DatasetCandidate] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        global_id = str(item.get("global_id") or item.get("identifier") or "").strip()
        dataset_id = safe_dataset_id(global_id or item.get("name") or "dataset")
        title = str(item.get("name") or dataset_id)
        description = str(item.get("description") or "")
        keywords = tuple(str(value) for value in item.get("keywords") or [] if value)
        subjects = tuple(str(value) for value in item.get("subjects") or [] if value)
        searchable = " ".join((title, description, " ".join(keywords), " ".join(subjects), " ".join(source.categories)))
        data_family = infer_data_family(searchable)
        major = str(item.get("majorVersion") or "").strip()
        minor = str(item.get("minorVersion") or "").strip()
        version = ".".join(value for value in (major, minor) if value) or str(item.get("updatedAt") or item.get("published_at") or "discovered")
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, keywords[:8], subjects[:4]),
            data_type=data_family,
            native_format="dataverse_dataset",
            geographic_scope=source.geographic_scope,
            landing_url=str(item.get("url") or source.docs_url or source_url),
            api_url=str(item.get("url") or source_url),
            license_url=str(item.get("licenseUrl") or ""),
            version=version,
            remote_updated_at=str(item.get("updatedAt") or item.get("published_at") or ""),
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
                "global_id": global_id,
                "publisher": item.get("publisher") or "",
                "dataverse_alias": item.get("identifier_of_dataverse") or "",
                "dataverse_name": item.get("name_of_dataverse") or "",
                "subjects": subjects,
                "keywords": keywords,
                "file_count": item.get("fileCount") or 0,
                "storage_identifier": item.get("storageIdentifier") or "",
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.81,
                evidence=("Dataverse search result", f"files: {item.get('fileCount') or 0}"),
            )
        )
    return candidates


def paginated_dataverse_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    start = 0
    for _page in range(discovery_page_cap(max_pages)):
        url = dataverse_search_url(source.endpoint_url, search_term, page_size, start=start)
        payload = fetch_json(url, timeout=timeout)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        items = data.get("items", [])
        page_candidates = dataverse_candidates_from_payload(source, payload, url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        total_count = int(data.get("total_count") or 0)
        if not isinstance(items, list) or not items or len(items) < page_size or added == 0:
            break
        start += len(items)
        if total_count and start >= total_count:
            break
    return candidates
