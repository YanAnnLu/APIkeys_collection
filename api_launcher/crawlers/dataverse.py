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
from api_launcher.crawlers.pagination import append_new_candidates, discovery_page_cap, polite_crawl_delay
from api_launcher.crawlers.registry import crawler
from api_launcher.crawlers.types import DatasetCandidate, DatasetCrawlerOutput, DatasetDiscoverySource
from api_launcher.models import Dataset


def dataverse_search_url(endpoint_url: str, search_term: str, limit: int, start: int | None = None) -> str:
    # Dataverse search 先取得 dataset persistent id；檔案清單由 latest-version resolver 查詢。
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
    # Dataverse candidate 必須保留 global_id，後續才能安全查最新版本與 restricted file 狀態。
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
    return list(paginated_dataverse_output(source, search_term, timeout, page_size, max_pages).candidates)


def paginated_dataverse_output(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> DatasetCrawlerOutput:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    start = 0
    remote_exhausted: bool | None = None
    remote_next_page_token = ""
    for _page in range(discovery_page_cap(max_pages)):
        url = dataverse_search_url(source.endpoint_url, search_term, page_size, start=start)
        payload = fetch_json(url, timeout=timeout)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        items = data.get("items", [])
        page_candidates = dataverse_candidates_from_payload(source, payload, url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        total_count = int(data.get("total_count") or 0)
        if not isinstance(items, list) or not items:
            remote_exhausted = True
            break
        start += len(items)
        if len(items) < page_size or (total_count and start >= total_count):
            remote_exhausted = True
            break
        if added == 0:
            remote_exhausted = None
            break
        polite_crawl_delay(source.crawl_rate_limit_seconds)
    else:
        remote_exhausted = False
        remote_next_page_token = str(start)
    status = "exhausted" if remote_exhausted is True else "has_more" if remote_exhausted is False else "not_reported"
    return DatasetCrawlerOutput(
        candidates=tuple(candidates),
        remote_pagination_status=status,
        remote_exhausted=remote_exhausted,
        remote_next_page_token=remote_next_page_token,
    )


@crawler(
    source_type="dataverse_search",
    source_family="catalog_search",
    transport="json",
    auth_profile="none",
    result_shape="dataset_list",
    seed_scope="paginated_catalog",
    supports_full_crawl=True,
)
def dataverse_candidates_for_source(
    source: DatasetDiscoverySource,
    timeout: float,
    limit: int,
    search_terms: tuple[str, ...],
    full_crawl: bool,
    max_pages: int,
) -> DatasetCrawlerOutput:
    candidates: list[DatasetCandidate] = []
    remote_exhausted: bool | None = None
    remote_next_page_token = ""
    for term in search_terms or ("",):
        if full_crawl:
            output = paginated_dataverse_output(source, term, timeout, limit, max_pages)
            candidates.extend(output.candidates)
            if output.remote_exhausted is False:
                remote_exhausted = False
                remote_next_page_token = output.remote_next_page_token
            elif output.remote_exhausted is True and remote_exhausted is not False:
                remote_exhausted = True
            elif remote_exhausted is not False:
                remote_exhausted = None
            continue
        url = dataverse_search_url(source.endpoint_url, term, limit)
        payload = fetch_json(url, timeout=timeout)
        candidates.extend(dataverse_candidates_from_payload(source, payload, url, limit))
    status = "exhausted" if remote_exhausted is True else "has_more" if remote_exhausted is False else "not_reported"
    return DatasetCrawlerOutput(
        candidates=tuple(candidates),
        remote_pagination_status=status,
        remote_exhausted=remote_exhausted,
        remote_next_page_token=remote_next_page_token,
    )
