from __future__ import annotations

import urllib.parse
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
    temporal_coverage,
    viewer_hint_for_family,
)
from api_launcher.crawlers.pagination import append_new_candidates, discovery_page_cap, polite_crawl_delay
from api_launcher.crawlers.registry import crawler
from api_launcher.crawlers.types import DatasetCandidate, DatasetCrawlerOutput, DatasetDiscoverySource
from api_launcher.models import Dataset


def ogc_records_search_url(endpoint_url: str, search_term: str, limit: int) -> str:
    # OGC API Records 使用 collections/items 查詢；limit 保護避免一次抓太多 feature。
    params = {"limit": str(max(1, limit))}
    if search_term:
        params["q"] = search_term
    return search_endpoint_url(endpoint_url, params)


def ogc_records_features(payload: dict[str, Any]) -> list[Any]:
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("OGC API Records payload missing features list")
    return features


def ogc_records_payload_item_count(payload: dict[str, Any]) -> int:
    for key in ("features", "collections"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    raise ValueError("OGC API Records payload missing features or collections list")


def ogc_records_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    # OGC feature 可能含 metadata/service/data 多種 link；crawler 只整理候選，resolver 再挑 data link。
    if isinstance(payload.get("collections"), list) and not isinstance(payload.get("features"), list):
        return ogc_collection_candidates_from_payload(source, payload, source_url, limit)

    features = ogc_records_features(payload)
    candidates: list[DatasetCandidate] = []
    for feature in features[:limit]:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        links = ogc_links(feature)
        keywords = ogc_text_values(properties.get("keywords") or properties.get("keyword") or properties.get("tags"))
        themes = ogc_text_values(properties.get("themes") or properties.get("theme") or properties.get("categories"))
        formats = ogc_formats(properties.get("formats") or properties.get("format"), links)
        record_id = str(feature.get("id") or properties.get("id") or properties.get("identifier") or "").strip()
        title = first_text(properties, ("title", "name", "label")) or record_id or "OGC API Record"
        description = first_text(properties, ("description", "abstract", "summary"))
        dataset_id = safe_dataset_id(record_id or title)
        searchable = " ".join(
            (
                title,
                description,
                " ".join(keywords),
                " ".join(themes),
                " ".join(formats),
                str(properties.get("type") or properties.get("resourceType") or ""),
                " ".join(source.categories),
            )
        )
        data_family = infer_data_family(searchable)
        landing_url = first_http_link_href(links, ("canonical", "alternate", "describedby", "self")) or source.docs_url or source_url
        api_url = first_http_link_href(links, ("data", "download", "items", "self")) or source_url
        license_url = first_link_href(links, ("license",)) or urlish_text(properties.get("license") or properties.get("rights"))
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, themes[:8], keywords[:8], formats[:4]),
            data_type=data_family,
            native_format=choose_native_format(formats) if formats else "ogc_record",
            geographic_scope=source.geographic_scope,
            temporal_coverage=ogc_temporal_coverage(properties),
            landing_url=landing_url,
            api_url=api_url,
            license_url=license_url,
            version=str(properties.get("updated") or properties.get("modified") or properties.get("created") or "discovered"),
            remote_updated_at=str(properties.get("updated") or properties.get("modified") or ""),
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
                "ogc_record_id": record_id,
                "geometry_type": ogc_geometry_type(feature.get("geometry")),
                "keywords": keywords,
                "themes": themes,
                "formats": formats,
                "links": links[:12],
                "properties": compact_properties(properties),
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.78,
                evidence=("OGC API Records feature", f"record: {record_id or dataset_id}"),
            )
        )
    return candidates


def ogc_collection_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    collections = payload.get("collections")
    if not isinstance(collections, list):
        raise ValueError("OGC API collections payload missing collections list")

    candidates: list[DatasetCandidate] = []
    for collection in collections[:limit]:
        if not isinstance(collection, dict):
            continue
        collection_id = str(collection.get("id") or collection.get("identifier") or "").strip()
        links = ogc_links(collection)
        keywords = ogc_text_values(collection.get("keywords") or collection.get("keyword") or collection.get("tags"))
        themes = ogc_text_values(collection.get("themes") or collection.get("theme") or collection.get("categories"))
        formats = ogc_formats(collection.get("formats") or collection.get("format") or collection.get("itemType"), links)
        title = first_text(collection, ("title", "name", "label")) or collection_id or "OGC API Collection"
        description = first_text(collection, ("description", "abstract", "summary"))
        dataset_id = safe_dataset_id(collection_id or title)
        searchable = " ".join(
            (
                title,
                description,
                " ".join(keywords),
                " ".join(themes),
                " ".join(formats),
                str(collection.get("itemType") or collection.get("type") or ""),
                " ".join(source.categories),
            )
        )
        data_family = infer_data_family(searchable)
        landing_url = first_http_link_href(links, ("self", "alternate", "canonical", "describedby")) or source.docs_url or source_url
        api_url = first_http_link_href(links, ("items", "data", "download", "self")) or ogc_collection_items_url(
            source_url, collection_id
        )
        license_url = first_link_href(links, ("license",)) or urlish_text(collection.get("license") or collection.get("rights"))
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, themes[:8], keywords[:8], formats[:4]),
            data_type=data_family,
            native_format=choose_native_format(formats) if formats else "ogc_collection",
            geographic_scope=source.geographic_scope,
            temporal_coverage=ogc_temporal_coverage(collection),
            landing_url=landing_url,
            api_url=api_url,
            license_url=license_url,
            version=str(collection.get("updated") or collection.get("modified") or collection.get("created") or "discovered"),
            remote_updated_at=str(collection.get("updated") or collection.get("modified") or ""),
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
                "ogc_collection_id": collection_id,
                "keywords": keywords,
                "themes": themes,
                "formats": formats,
                "links": links[:12],
                "extent": collection.get("extent") if isinstance(collection.get("extent"), dict) else {},
                "properties": compact_properties(collection),
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.76,
                evidence=("OGC API collection", f"collection: {collection_id or dataset_id}"),
            )
        )
    return candidates


def paginated_ogc_records_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    return list(paginated_ogc_records_output(source, search_term, timeout, page_size, max_pages).candidates)


def paginated_ogc_records_output(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> DatasetCrawlerOutput:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    seen_page_urls: set[str] = set()
    next_url = ogc_records_search_url(source.endpoint_url, search_term, page_size)
    next_candidate = ""
    remote_exhausted: bool | None = None
    remote_next_page_token = ""
    for _page in range(discovery_page_cap(max_pages)):
        if next_url in seen_page_urls:
            remote_exhausted = None
            break
        seen_page_urls.add(next_url)
        payload = fetch_json(next_url, timeout=timeout)
        item_count = ogc_records_payload_item_count(payload)
        page_candidates = ogc_records_candidates_from_payload(source, payload, next_url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        next_candidate = next_link_href(payload.get("links"), next_url)
        if item_count < page_size or not next_candidate:
            remote_exhausted = True
            break
        if added == 0:
            remote_exhausted = None
            break
        polite_crawl_delay(source.crawl_rate_limit_seconds)
        next_url = next_candidate
    else:
        remote_exhausted = False
        remote_next_page_token = next_candidate
    status = "exhausted" if remote_exhausted is True else "has_more" if remote_exhausted is False else "not_reported"
    return DatasetCrawlerOutput(
        candidates=tuple(candidates),
        remote_pagination_status=status,
        remote_exhausted=remote_exhausted,
        remote_next_page_token=remote_next_page_token,
    )


@crawler(
    source_type="ogc_api_records",
    source_family="catalog_search",
    transport="json",
    auth_profile="none",
    result_shape="dataset_list",
    supports_full_crawl=True,
)
def ogc_records_candidates_for_source(
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
            output = paginated_ogc_records_output(source, term, timeout, limit, max_pages)
            candidates.extend(output.candidates)
            if output.remote_exhausted is False:
                remote_exhausted = False
                remote_next_page_token = output.remote_next_page_token
            elif output.remote_exhausted is True and remote_exhausted is not False:
                remote_exhausted = True
            elif remote_exhausted is not False:
                remote_exhausted = None
            continue
        url = ogc_records_search_url(source.endpoint_url, term, limit)
        payload = fetch_json(url, timeout=timeout)
        candidates.extend(ogc_records_candidates_from_payload(source, payload, url, limit))
    status = "exhausted" if remote_exhausted is True else "has_more" if remote_exhausted is False else "not_reported"
    return DatasetCrawlerOutput(
        candidates=tuple(candidates),
        remote_pagination_status=status,
        remote_exhausted=remote_exhausted,
        remote_next_page_token=remote_next_page_token,
    )


def first_text(properties: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def ogc_text_values(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if not isinstance(value, list):
        return ()
    values: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("name")
                or item.get("title")
                or item.get("label")
                or item.get("id")
                or item.get("code")
                or ""
            ).strip()
        else:
            text = str(item).strip()
        if text:
            values.append(text)
    return tuple(values)


def ogc_formats(value: object, links: list[dict[str, object]]) -> tuple[str, ...]:
    formats = list(ogc_text_values(value))
    for link in links:
        media_type = str(link.get("type") or "").strip()
        if media_type:
            formats.append(media_type.split(";")[0].split("/")[-1])
    seen: set[str] = set()
    deduped: list[str] = []
    for value in formats:
        key = safe_dataset_id(value)
        if key and key not in seen:
            seen.add(key)
            deduped.append(value)
    return tuple(deduped)


def ogc_links(feature: dict[str, Any]) -> list[dict[str, object]]:
    raw_links = feature.get("links")
    if not isinstance(raw_links, list):
        raw_links = []
    links: list[dict[str, object]] = []
    for link in raw_links:
        if not isinstance(link, dict) or not link.get("href"):
            continue
        links.append(
            {
                "rel": link.get("rel") or "",
                "href": link.get("href") or "",
                "type": link.get("type") or "",
                "title": link.get("title") or "",
            }
        )
    return links


def first_link_href(links: list[dict[str, object]], rels: tuple[str, ...]) -> str:
    for rel in rels:
        for link in links:
            if str(link.get("rel") or "").lower() == rel and link.get("href"):
                return str(link["href"])
    return ""


def first_http_link_href(links: list[dict[str, object]], rels: tuple[str, ...]) -> str:
    for rel in rels:
        for link in links:
            href = str(link.get("href") or "")
            parsed = urllib.parse.urlparse(href)
            if str(link.get("rel") or "").lower() == rel and parsed.scheme in {"http", "https"} and parsed.netloc:
                return href
    return ""


def ogc_collection_items_url(source_url: str, collection_id: str) -> str:
    parsed = urllib.parse.urlparse(source_url)
    path = parsed.path.rstrip("/")
    if collection_id and path.lower().endswith("/collections"):
        path = f"{path}/{urllib.parse.quote(collection_id, safe='')}/items"
    elif collection_id and not path.lower().endswith("/items"):
        path = f"{path}/items"
    return urllib.parse.urlunparse(parsed._replace(path=path, query=""))


def next_link_href(links: object, current_url: str) -> str:
    if not isinstance(links, list):
        return ""
    for link in links:
        if isinstance(link, dict) and str(link.get("rel") or "").lower() == "next" and link.get("href"):
            return urllib.parse.urljoin(current_url, str(link["href"]))
    return ""


def ogc_temporal_coverage(properties: dict[str, Any]) -> str:
    start = properties.get("start_datetime") or properties.get("startDate") or properties.get("start")
    end = properties.get("end_datetime") or properties.get("endDate") or properties.get("end")
    if start or end:
        return temporal_coverage(start, end)
    extent = properties.get("extent")
    if isinstance(extent, dict):
        temporal = extent.get("temporal")
        if isinstance(temporal, dict):
            interval = temporal.get("interval")
            if isinstance(interval, list) and interval:
                first = interval[0]
                if isinstance(first, list):
                    return temporal_coverage(first[0] if first else "", first[1] if len(first) > 1 else "")
    time_value = properties.get("time") or properties.get("temporal")
    if isinstance(time_value, dict):
        interval = time_value.get("interval")
        if isinstance(interval, list) and interval:
            first = interval[0]
            if isinstance(first, list):
                return temporal_coverage(first[0] if first else "", first[1] if len(first) > 1 else "")
        return temporal_coverage(time_value.get("start"), time_value.get("end"))
    return str(properties.get("datetime") or "").strip()


def ogc_geometry_type(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("type") or "").strip()
    return ""


def compact_properties(properties: dict[str, Any]) -> dict[str, object]:
    compact: dict[str, object] = {}
    for key, value in properties.items():
        if len(compact) >= 30:
            break
        if isinstance(value, (str, int, float, bool)) or value is None:
            compact[key] = value
        elif isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) for item in value[:12]):
            compact[key] = value[:12]
    return compact


def urlish_text(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return ""
