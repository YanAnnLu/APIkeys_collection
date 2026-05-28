from __future__ import annotations

from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.fetch import fetch_json, search_endpoint_url
from api_launcher.crawlers.metadata import (
    analysis_hint_for_family,
    choose_native_format,
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


def ckan_package_search_url(endpoint_url: str, search_term: str, limit: int, start: int | None = None) -> str:
    # CKAN package_search 用 rows/start 分頁；limit 在這裡先做最小值保護。
    params = {"q": search_term, "rows": str(max(1, limit))}
    if start is not None:
        params["start"] = str(max(0, start))
    return search_endpoint_url(endpoint_url, params)


def ckan_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    # CKAN resources 常同時列多種格式，這裡只先建立 candidate，不直接判定下載。
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("CKAN package_search payload missing result object")
    results = result.get("results", [])
    if not isinstance(results, list):
        raise ValueError("CKAN package_search payload missing result.results list")
    candidates: list[DatasetCandidate] = []
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        dataset_id = safe_dataset_id(str(item.get("name") or item.get("id") or item.get("title") or "dataset"))
        title = str(item.get("title") or dataset_id)
        description = str(item.get("notes") or item.get("description") or "")
        tags = tuple(
            str(tag.get("display_name") or tag.get("name") or "")
            for tag in item.get("tags", [])
            if isinstance(tag, dict) and (tag.get("display_name") or tag.get("name"))
        )
        resources = item.get("resources") if isinstance(item.get("resources"), list) else []
        formats = tuple(str(resource.get("format") or "").strip() for resource in resources if isinstance(resource, dict) and resource.get("format"))
        searchable = " ".join((title, description, " ".join(tags), " ".join(formats), " ".join(source.categories)))
        data_family = infer_data_family(searchable)
        resource_url = first_resource_url(resources)
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, tags[:8], formats[:4]),
            data_type=data_family,
            native_format=choose_native_format(formats),
            geographic_scope=source.geographic_scope,
            landing_url=str(item.get("url") or source.docs_url or source_url),
            api_url=resource_url or source_url,
            license_url=str(item.get("license_url") or ""),
            version=str(item.get("metadata_modified") or item.get("revision_timestamp") or "discovered"),
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
                "ckan_id": item.get("id") or "",
                "organization": item.get("organization") or {},
                "license_title": item.get("license_title") or "",
                "resource_count": len(resources),
                "resources": resource_summaries(resources),
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.8,
                evidence=("CKAN package_search result", f"resources: {len(resources)}"),
            )
        )
    return candidates


def paginated_ckan_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    return list(paginated_ckan_output(source, search_term, timeout, page_size, max_pages).candidates)


def paginated_ckan_output(
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
        url = ckan_package_search_url(source.endpoint_url, search_term, page_size, start=start)
        payload = fetch_json(url, timeout=timeout)
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        results = result.get("results", [])
        page_candidates = ckan_candidates_from_payload(source, payload, url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        count = int(result.get("count") or 0)
        if not isinstance(results, list) or not results:
            remote_exhausted = True
            break
        start += len(results)
        if len(results) < page_size:
            remote_exhausted = True
            break
        if count and start >= count:
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
    source_type="ckan_package_search",
    source_family="catalog_search",
    transport="json",
    auth_profile="none",
    result_shape="dataset_list",
    supports_full_crawl=True,
)
def ckan_candidates_for_source(
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
            output = paginated_ckan_output(source, term, timeout, limit, max_pages)
            candidates.extend(output.candidates)
            if output.remote_exhausted is False:
                remote_exhausted = False
                remote_next_page_token = output.remote_next_page_token
            elif output.remote_exhausted is True and remote_exhausted is not False:
                remote_exhausted = True
            elif remote_exhausted is not False:
                remote_exhausted = None
            continue
        url = ckan_package_search_url(source.endpoint_url, term, limit)
        payload = fetch_json(url, timeout=timeout)
        candidates.extend(ckan_candidates_from_payload(source, payload, url, limit))
    status = "exhausted" if remote_exhausted is True else "has_more" if remote_exhausted is False else "not_reported"
    return DatasetCrawlerOutput(
        candidates=tuple(candidates),
        remote_pagination_status=status,
        remote_exhausted=remote_exhausted,
        remote_next_page_token=remote_next_page_token,
    )


def first_resource_url(resources: list[object]) -> str:
    for resource in resources:
        if isinstance(resource, dict) and resource.get("url"):
            return str(resource["url"])
    return ""


def resource_summaries(resources: list[object]) -> list[dict[str, object]]:
    summaries = []
    for resource in resources[:12]:
        if not isinstance(resource, dict):
            continue
        summaries.append(
            {
                "name": resource.get("name") or resource.get("id") or "",
                "format": resource.get("format") or "",
                "url": resource.get("url") or "",
            }
        )
    return summaries
