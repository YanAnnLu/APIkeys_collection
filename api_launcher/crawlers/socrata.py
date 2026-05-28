from __future__ import annotations

import urllib.parse
from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.fetch import fetch_json
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


def socrata_catalog_search_url(
    endpoint_url: str,
    search_term: str,
    limit: int,
    offset: int | None = None,
) -> str:
    # Socrata catalog search 只找資料集 metadata；實際資料表下載必須加 `$limit` 邊界。
    params = {"limit": str(max(1, limit)), "only": "dataset"}
    if offset is not None:
        params["offset"] = str(max(0, offset))
    if search_term:
        params["q"] = search_term
    return replace_query_params(endpoint_url, params)


def socrata_catalog_results(payload: dict[str, Any]) -> list[Any]:
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("Socrata catalog payload missing results list")
    return results


def socrata_catalog_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    # Socrata resource id 會在 resolver 轉成 bounded API URL，crawler 階段只保留 metadata。
    results = socrata_catalog_results(payload)
    candidates: list[DatasetCandidate] = []
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        resource = item.get("resource") if isinstance(item.get("resource"), dict) else {}
        classification = item.get("classification") if isinstance(item.get("classification"), dict) else {}
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        resource_id = first_text(resource.get("id"), item.get("id"))
        title = first_text(
            resource.get("name"),
            resource.get("resource_name"),
            item.get("name"),
            resource_id,
            "Socrata dataset",
        )
        description = first_text(resource.get("description"), item.get("description"))
        domain = first_text(
            metadata.get("domain"),
            resource.get("domain"),
            domain_from_url(first_text(item.get("link"), item.get("permalink"))),
        )
        dataset_id = safe_dataset_id(resource_id or title)
        tags = socrata_tags(classification)
        columns = socrata_columns(resource)
        column_names = tuple(
            str(column.get("name") or column.get("field_name") or "")
            for column in columns
            if column.get("name") or column.get("field_name")
        )
        column_types = tuple(str(column.get("datatype") or "") for column in columns if column.get("datatype"))
        searchable = " ".join(
            (
                title,
                description,
                " ".join(tags),
                " ".join(column_names[:20]),
                " ".join(column_types[:20]),
                first_text(resource.get("type")),
                " ".join(source.categories),
            )
        )
        data_family = infer_data_family(searchable)
        landing_url = first_text(
            item.get("permalink"),
            item.get("link"),
            socrata_landing_url(domain, resource_id),
            source.docs_url,
        )
        api_view_url = socrata_api_view_url(domain, resource_id) or source_url
        resource_url = socrata_resource_url(domain, resource_id)
        license_text = first_text(metadata.get("license"), resource.get("license"))
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, tags[:12], column_types[:6]),
            data_type=data_family,
            native_format="socrata_resource",
            geographic_scope=source.geographic_scope,
            landing_url=landing_url,
            api_url=api_view_url,
            license_url=urlish_text(license_text),
            version=first_text(
                resource.get("data_updated_at"),
                resource.get("updatedAt"),
                resource.get("metadata_updated_at"),
                "discovered",
            ),
            remote_updated_at=first_text(
                resource.get("data_updated_at"),
                resource.get("updatedAt"),
                resource.get("metadata_updated_at"),
            ),
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
                "socrata_dataset_id": resource_id,
                "socrata_domain": domain,
                "socrata_api_view_url": api_view_url,
                "socrata_resource_url": resource_url,
                "resource_type": first_text(resource.get("type")),
                "attribution": first_text(resource.get("attribution")),
                "attribution_link": first_text(resource.get("attribution_link")),
                "owner": socrata_owner_summary(item.get("owner")),
                "license": license_text,
                "tags": tags,
                "domain_category": first_text(classification.get("domain_category")),
                "column_count": len(columns),
                "columns": columns[:24],
                "page_views": resource.get("page_views") if isinstance(resource.get("page_views"), dict) else {},
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
                evidence=(
                    "Socrata catalog result",
                    f"resource: {resource_id or dataset_id}",
                    f"domain: {domain or 'unknown'}",
                ),
            )
        )
    return candidates


def paginated_socrata_catalog_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    return list(paginated_socrata_catalog_output(source, search_term, timeout, page_size, max_pages).candidates)


def paginated_socrata_catalog_output(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> DatasetCrawlerOutput:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    offset = 0
    remote_exhausted: bool | None = None
    remote_next_page_token = ""
    for _page in range(discovery_page_cap(max_pages)):
        url = socrata_catalog_search_url(source.endpoint_url, search_term, page_size, offset=offset)
        payload = fetch_json(url, timeout=timeout)
        results = socrata_catalog_results(payload)
        page_candidates = socrata_catalog_candidates_from_payload(source, payload, url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        result_set_size = int(payload.get("resultSetSize") or 0)
        if not results:
            remote_exhausted = True
            break
        offset += len(results)
        if len(results) < page_size:
            remote_exhausted = True
            break
        if result_set_size and offset >= result_set_size:
            remote_exhausted = True
            break
        if added == 0:
            remote_exhausted = None
            break
        polite_crawl_delay(source.crawl_rate_limit_seconds)
    else:
        remote_exhausted = False
        remote_next_page_token = str(offset)
    status = "exhausted" if remote_exhausted is True else "has_more" if remote_exhausted is False else "not_reported"
    return DatasetCrawlerOutput(
        candidates=tuple(candidates),
        remote_pagination_status=status,
        remote_exhausted=remote_exhausted,
        remote_next_page_token=remote_next_page_token,
    )


@crawler(
    source_type="socrata_catalog_search",
    source_family="catalog_search",
    transport="json",
    auth_profile="optional_api_key",
    result_shape="dataset_list",
    supports_full_crawl=True,
)
def socrata_catalog_candidates_for_source(
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
            output = paginated_socrata_catalog_output(source, term, timeout, limit, max_pages)
            candidates.extend(output.candidates)
            if output.remote_exhausted is False:
                remote_exhausted = False
                remote_next_page_token = output.remote_next_page_token
            elif output.remote_exhausted is True and remote_exhausted is not False:
                remote_exhausted = True
            elif remote_exhausted is not False:
                remote_exhausted = None
            continue
        url = socrata_catalog_search_url(source.endpoint_url, term, limit)
        payload = fetch_json(url, timeout=timeout)
        candidates.extend(socrata_catalog_candidates_from_payload(source, payload, url, limit))
    status = "exhausted" if remote_exhausted is True else "has_more" if remote_exhausted is False else "not_reported"
    return DatasetCrawlerOutput(
        candidates=tuple(candidates),
        remote_pagination_status=status,
        remote_exhausted=remote_exhausted,
        remote_next_page_token=remote_next_page_token,
    )


def replace_query_params(endpoint_url: str, params: dict[str, str]) -> str:
    parsed = urllib.parse.urlparse(endpoint_url)
    current = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key not in params
    ]
    current.extend((key, value) for key, value in params.items() if value)
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(current, doseq=True)))


def first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def socrata_tags(classification: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("categories", "tags", "domain_tags"):
        raw = classification.get(key)
        if isinstance(raw, list):
            values.extend(str(value).strip() for value in raw if str(value).strip())
    domain_category = first_text(classification.get("domain_category"))
    if domain_category:
        values.append(domain_category)
    return tuple(deduped(values))


def socrata_columns(resource: dict[str, Any]) -> list[dict[str, str]]:
    names = list_values(resource.get("columns_name"))
    fields = list_values(resource.get("columns_field_name"))
    datatypes = list_values(resource.get("columns_datatype"))
    descriptions = list_values(resource.get("columns_description"))
    count = max(len(names), len(fields), len(datatypes), len(descriptions))
    columns: list[dict[str, str]] = []
    for index in range(min(count, 80)):
        columns.append(
            {
                "name": value_at(names, index),
                "field_name": value_at(fields, index),
                "datatype": value_at(datatypes, index),
                "description": value_at(descriptions, index),
            }
        )
    return columns


def list_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item or "").strip() for item in value]


def value_at(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return values[index]


def socrata_owner_summary(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        "id": first_text(value.get("id")),
        "display_name": first_text(value.get("display_name")),
        "user_type": first_text(value.get("user_type")),
    }


def socrata_landing_url(domain: str, resource_id: str) -> str:
    if not domain or not resource_id:
        return ""
    return f"https://{domain}/d/{resource_id}"


def socrata_api_view_url(domain: str, resource_id: str) -> str:
    if not domain or not resource_id:
        return ""
    return f"https://{domain}/api/views/{resource_id}"


def socrata_resource_url(domain: str, resource_id: str) -> str:
    if not domain or not resource_id:
        return ""
    return f"https://{domain}/resource/{resource_id}.json"


def domain_from_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return parsed.netloc
    return ""


def urlish_text(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return ""


def deduped(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = safe_dataset_id(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
