from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.ckan import ckan_candidates_from_payload
from api_launcher.crawlers.cmr import cmr_candidates_from_payload, cmr_payload_entries
from api_launcher.crawlers.dataverse import dataverse_candidates_from_payload
from api_launcher.crawlers.erddap import erddap_candidates_from_payload
from api_launcher.crawlers.gbif import gbif_candidates_from_payload
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
from api_launcher.crawlers.stac import (
    first_stac_link_url,
    stac_candidates_from_payload,
    stac_temporal_coverage,
)
from api_launcher.crawlers.types import (
    DatasetCandidate,
    DatasetDiscoverySource,
    dataset_to_dict,
    dataset_with_candidate_metadata,
)
from api_launcher.discovery import extract_links
from api_launcher.models import Dataset


USER_AGENT = "APIkeys_collection/0.4 (+dataset-discovery; metadata only)"
DEFAULT_DATASET_DISCOVERY_SOURCES_NAME = "dataset_discovery_sources.json"
LOCAL_DATASET_DISCOVERY_SOURCES_NAME = "dataset_discovery_sources.local.json"
DEFAULT_FULL_CRAWL_PAGE_SIZE = 100
MAX_FULL_CRAWL_PAGES = 1000


def load_dataset_discovery_sources(path: str | Path) -> list[DatasetDiscoverySource]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        DatasetDiscoverySource(
            source_id=str(item["source_id"]).strip(),
            provider_id=str(item["provider_id"]).strip(),
            name=str(item["name"]).strip(),
            source_type=str(item["source_type"]).strip(),
            endpoint_url=str(item["endpoint_url"]).strip(),
            docs_url=str(item.get("docs_url") or "").strip(),
            search_terms=tuple(str(value).strip() for value in item.get("search_terms", []) if str(value).strip()),
            categories=tuple(str(value).strip() for value in item.get("categories", []) if str(value).strip()),
            geographic_scope=str(item.get("geographic_scope") or "global").strip(),
            max_results=int(item.get("max_results") or 10),
            dataset_id=str(item.get("dataset_id") or "").strip(),
            dataset_title=str(item.get("dataset_title") or "").strip(),
            data_type=str(item.get("data_type") or "").strip(),
            native_format=str(item.get("native_format") or "").strip(),
            file_url_regex=str(item.get("file_url_regex") or "").strip(),
            min_expected_candidates=int(item.get("min_expected_candidates") if item.get("min_expected_candidates") is not None else 1),
            notes=str(item.get("notes") or "").strip(),
        )
        for item in data.get("sources", [])
    ]


def load_all_dataset_discovery_sources(
    primary_path: str | Path,
    local_path: str | Path | None = None,
) -> list[DatasetDiscoverySource]:
    paths = [Path(primary_path)]
    if local_path is not None:
        paths.append(Path(local_path))
    sources: list[DatasetDiscoverySource] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for source in load_dataset_discovery_sources(path):
            if source.source_id in seen:
                continue
            seen.add(source.source_id)
            sources.append(source)
    return sources


def append_dataset_discovery_source(path: str | Path, source: DatasetDiscoverySource) -> None:
    path = Path(path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"schema_version": 1, "sources": []}
    sources = [item for item in data.get("sources", []) if item.get("source_id") != source.source_id]
    sources.append(source_to_dict(source))
    data["sources"] = sorted(sources, key=lambda item: item["source_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def source_to_dict(source: DatasetDiscoverySource) -> dict[str, object]:
    return {
        "source_id": source.source_id,
        "provider_id": source.provider_id,
        "name": source.name,
        "source_type": source.source_type,
        "endpoint_url": source.endpoint_url,
        "docs_url": source.docs_url,
        "search_terms": list(source.search_terms),
        "categories": list(source.categories),
        "geographic_scope": source.geographic_scope,
        "max_results": source.max_results,
        "dataset_id": source.dataset_id,
        "dataset_title": source.dataset_title,
        "data_type": source.data_type,
        "native_format": source.native_format,
        "file_url_regex": source.file_url_regex,
        "min_expected_candidates": source.min_expected_candidates,
        "notes": source.notes,
    }


def discover_dataset_candidates(
    sources: list[DatasetDiscoverySource],
    timeout: float = 12.0,
    max_results_override: int = 0,
    search_terms_override: tuple[str, ...] = (),
    full_crawl: bool = False,
    max_pages: int = 0,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        source_candidates = discover_dataset_candidates_for_source(
            source,
            timeout=timeout,
            max_results_override=max_results_override,
            search_terms_override=search_terms_override,
            full_crawl=full_crawl,
            max_pages=max_pages,
        )
        for candidate in source_candidates:
            key = (candidate.dataset.provider_id, candidate.dataset.dataset_id)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def discover_dataset_candidates_for_source(
    source: DatasetDiscoverySource,
    timeout: float = 12.0,
    max_results_override: int = 0,
    search_terms_override: tuple[str, ...] = (),
    full_crawl: bool = False,
    max_pages: int = 0,
) -> list[DatasetCandidate]:
    limit = max_results_override or source.max_results
    if full_crawl and not max_results_override:
        limit = max(limit, DEFAULT_FULL_CRAWL_PAGE_SIZE)
    search_terms = search_terms_override or source.search_terms
    if source.source_type == "ncei_search":
        candidates: list[DatasetCandidate] = []
        for term in search_terms or ("",):
            if full_crawl:
                candidates.extend(paginated_ncei_candidates(source, term, timeout, limit, max_pages))
                continue
            url = ncei_search_url(source.endpoint_url, term, limit)
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(ncei_candidates_from_payload(source, payload, url, limit))
        return candidates
    if source.source_type == "erddap_all_datasets":
        payload = fetch_json(source.endpoint_url, timeout=timeout)
        return erddap_candidates_from_payload(source, payload, source.endpoint_url, limit, search_terms)
    if source.source_type == "html_file_index":
        text, final_url = fetch_text(source.endpoint_url, timeout=timeout)
        return html_file_index_candidates_from_text(source, text, final_url, 0 if full_crawl else limit)
    if source.source_type == "cmr_collections":
        candidates = []
        for term in search_terms or ("",):
            if full_crawl:
                candidates.extend(paginated_cmr_candidates(source, term, timeout, limit, max_pages))
                continue
            url = cmr_collections_url(source.endpoint_url, term, limit)
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(cmr_candidates_from_payload(source, payload, url, limit))
        return candidates
    if source.source_type == "stac_collections":
        if full_crawl:
            return paginated_stac_candidates(source, timeout, limit, search_terms, max_pages)
        payload = fetch_json(source.endpoint_url, timeout=timeout)
        return stac_candidates_from_payload(source, payload, source.endpoint_url, limit, search_terms)
    if source.source_type == "gbif_dataset_search":
        candidates = []
        for term in search_terms or ("",):
            if full_crawl:
                candidates.extend(paginated_gbif_candidates(source, term, timeout, limit, max_pages))
                continue
            url = search_endpoint_url(source.endpoint_url, {"q": term, "limit": str(max(1, limit))})
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(gbif_candidates_from_payload(source, payload, url, limit))
        return candidates
    if source.source_type == "dataverse_search":
        candidates = []
        for term in search_terms or ("",):
            if full_crawl:
                candidates.extend(paginated_dataverse_candidates(source, term, timeout, limit, max_pages))
                continue
            url = search_endpoint_url(source.endpoint_url, {"q": term, "type": "dataset", "per_page": str(max(1, limit))})
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(dataverse_candidates_from_payload(source, payload, url, limit))
        return candidates
    if source.source_type == "zenodo_records_search":
        candidates = []
        for term in search_terms or ("",):
            if full_crawl:
                candidates.extend(paginated_zenodo_candidates(source, term, timeout, limit, max_pages))
                continue
            url = search_endpoint_url(source.endpoint_url, {"q": term, "type": "dataset", "size": str(max(1, limit))})
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(zenodo_candidates_from_payload(source, payload, url, limit))
        return candidates
    if source.source_type == "ckan_package_search":
        candidates = []
        for term in search_terms or ("",):
            if full_crawl:
                candidates.extend(paginated_ckan_candidates(source, term, timeout, limit, max_pages))
                continue
            url = search_endpoint_url(source.endpoint_url, {"q": term, "rows": str(max(1, limit))})
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(ckan_candidates_from_payload(source, payload, url, limit))
        return candidates
    raise ValueError(f"Unsupported dataset discovery source_type: {source.source_type}")


def ncei_search_url(endpoint_url: str, search_term: str, limit: int, offset: int = 0) -> str:
    params = {"limit": str(max(1, limit)), "available": "true", "text": search_term}
    if offset > 0:
        params["offset"] = str(offset)
    return search_endpoint_url(
        endpoint_url,
        params,
    )


def cmr_collections_url(endpoint_url: str, search_term: str, limit: int, page_num: int = 0) -> str:
    params = {"page_size": str(max(1, limit)), "downloadable": "true", "keyword": search_term}
    if page_num > 0:
        params["page_num"] = str(page_num)
    return search_endpoint_url(
        endpoint_url,
        params,
    )


def search_endpoint_url(endpoint_url: str, params: dict[str, str]) -> str:
    clean_params = {key: value for key, value in params.items() if value}
    separator = "&" if urllib.parse.urlparse(endpoint_url).query else "?"
    return endpoint_url + separator + urllib.parse.urlencode(clean_params)


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


def paginated_stac_candidates(
    source: DatasetDiscoverySource,
    timeout: float,
    page_size: int,
    search_terms: tuple[str, ...],
    max_pages: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    seen_page_urls: set[str] = set()
    next_url = source.endpoint_url
    for _page in range(discovery_page_cap(max_pages)):
        if next_url in seen_page_urls:
            break
        seen_page_urls.add(next_url)
        payload = fetch_json(next_url, timeout=timeout)
        collections = payload.get("collections", [])
        page_candidates = stac_candidates_from_payload(source, payload, next_url, page_size, search_terms)
        append_new_candidates(candidates, page_candidates, seen)
        next_link = stac_next_link(payload, next_url)
        if not isinstance(collections, list) or not collections or not next_link:
            break
        next_url = next_link
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
        url = search_endpoint_url(source.endpoint_url, {"q": search_term, "limit": str(max(1, page_size)), "offset": str(offset)})
        payload = fetch_json(url, timeout=timeout)
        results = payload.get("results", [])
        page_candidates = gbif_candidates_from_payload(source, payload, url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        end_of_records = bool(payload.get("endOfRecords"))
        if not isinstance(results, list) or not results or end_of_records or len(results) < page_size or added == 0:
            break
        offset += len(results)
    return candidates


def paginated_ckan_candidates(
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
        url = search_endpoint_url(source.endpoint_url, {"q": search_term, "rows": str(max(1, page_size)), "start": str(start)})
        payload = fetch_json(url, timeout=timeout)
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        results = result.get("results", [])
        page_candidates = ckan_candidates_from_payload(source, payload, url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        count = int(result.get("count") or 0)
        if not isinstance(results, list) or not results or len(results) < page_size or added == 0:
            break
        start += len(results)
        if count and start >= count:
            break
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
        url = search_endpoint_url(
            source.endpoint_url,
            {"q": search_term, "type": "dataset", "per_page": str(max(1, page_size)), "start": str(start)},
        )
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


def paginated_zenodo_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    next_url = search_endpoint_url(source.endpoint_url, {"q": search_term, "type": "dataset", "size": str(max(1, page_size))})
    for _page in range(discovery_page_cap(max_pages)):
        payload = fetch_json(next_url, timeout=timeout)
        hits = payload.get("hits") if isinstance(payload.get("hits"), dict) else {}
        records = hits.get("hits", [])
        page_candidates = zenodo_candidates_from_payload(source, payload, next_url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        links = payload.get("links") if isinstance(payload.get("links"), dict) else {}
        next_candidate = str(links.get("next") or "")
        if not isinstance(records, list) or not records or len(records) < page_size or added == 0 or not next_candidate:
            break
        next_url = next_candidate
    return candidates


def discovery_page_cap(max_pages: int) -> int:
    if max_pages > 0:
        return min(max_pages, MAX_FULL_CRAWL_PAGES)
    return MAX_FULL_CRAWL_PAGES


def append_new_candidates(candidates: list[DatasetCandidate], page_candidates: list[DatasetCandidate], seen: set[str]) -> int:
    added = 0
    for candidate in page_candidates:
        key = candidate.dataset.dataset_uid
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
        added += 1
    return added


def stac_next_link(payload: dict[str, Any], current_url: str) -> str:
    links = payload.get("links", [])
    if not isinstance(links, list):
        return ""
    for item in links:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("rel") or "").lower()
        href = str(item.get("href") or "").strip()
        if rel == "next" and href:
            return urllib.parse.urljoin(current_url, href)
    return ""


def ncei_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
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


def zenodo_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    hits = payload.get("hits")
    if not isinstance(hits, dict):
        raise ValueError("Zenodo records payload missing hits object")
    records = hits.get("hits", [])
    if not isinstance(records, list):
        raise ValueError("Zenodo records payload missing hits.hits list")
    candidates: list[DatasetCandidate] = []
    for item in records[:limit]:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        links = item.get("links") if isinstance(item.get("links"), dict) else {}
        dataset_id = safe_dataset_id(str(item.get("doi") or item.get("conceptdoi") or item.get("recid") or item.get("id") or metadata.get("title") or "dataset"))
        title = str(item.get("title") or metadata.get("title") or dataset_id)
        description = strip_markup(metadata.get("description") or "")
        keywords = tuple(str(value) for value in metadata.get("keywords") or [] if value)
        resource_type = metadata.get("resource_type") if isinstance(metadata.get("resource_type"), dict) else {}
        searchable = " ".join((title, description, " ".join(keywords), str(resource_type.get("title") or ""), " ".join(source.categories)))
        data_family = infer_data_family(searchable)
        license_meta = metadata.get("license") if isinstance(metadata.get("license"), dict) else {}
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, keywords[:8], (str(resource_type.get("type") or ""),)),
            data_type=data_family,
            native_format="zenodo_record",
            geographic_scope=source.geographic_scope,
            landing_url=str(links.get("self_html") or item.get("doi_url") or source.docs_url or source_url),
            api_url=str(links.get("self") or source_url),
            license_url=str(license_meta.get("id") or ""),
            version=str(item.get("modified") or metadata.get("publication_date") or "discovered"),
            remote_updated_at=str(item.get("modified") or ""),
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
                "doi": item.get("doi") or metadata.get("doi") or "",
                "record_id": item.get("recid") or item.get("id") or "",
                "resource_type": resource_type,
                "keywords": keywords,
                "file_count": len(item.get("files") or []) if isinstance(item.get("files"), list) else 0,
                "files": zenodo_file_summaries(item.get("files")),
                "resources": zenodo_file_summaries(item.get("files")),
                "links": {key: links.get(key) for key in ("self", "self_html", "files", "archive") if links.get(key)},
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
                evidence=("Zenodo records search result", f"record: {item.get('recid') or item.get('id') or 'unknown'}"),
            )
        )
    return candidates


def html_file_index_candidates_from_text(
    source: DatasetDiscoverySource,
    text: str,
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    if not source.file_url_regex:
        raise ValueError("HTML file index source missing file_url_regex")
    pattern = re.compile(source.file_url_regex)
    versions: list[dict[str, object]] = []
    seen: set[str] = set()
    for link in extract_links(text, source_url):
        filename = Path(urllib.parse.urlparse(link).path).name
        match = pattern.search(filename) or pattern.search(link)
        if not match or link in seen:
            continue
        seen.add(link)
        version = match.groupdict().get("version") if match.groupdict() else ""
        versions.append(
            {
                "label": filename,
                "version": version or filename,
                "version_status": "discovered_file_shard",
                "download_url": link,
                "landing_url": source.docs_url or source_url,
                "update_strategy": "append_or_partition_by_discovered_shard",
                "notes": "Discovered from an HTML file index; review size and scope before bulk download.",
            }
        )
        if limit > 0 and len(versions) >= limit:
            break
    if not versions:
        return []
    dataset_id = safe_dataset_id(source.dataset_id or source.source_id)
    data_family = infer_data_family(" ".join((source.dataset_title, source.data_type, " ".join(source.categories))))
    dataset = Dataset(
        dataset_uid=dataset_uid(source.provider_id, dataset_id),
        provider_id=source.provider_id,
        dataset_id=dataset_id,
        title=source.dataset_title or source.name,
        categories=source.categories or ("discovered",),
        data_type=source.data_type or data_family,
        native_format=source.native_format,
        geographic_scope=source.geographic_scope,
        landing_url=source.docs_url or source_url,
        api_url=str(versions[0]["download_url"]),
        version=str(versions[0]["version"]),
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
            "available_versions": versions,
            "chunking_hint": "file_shard_index",
            "notes": source.notes,
        },
    )
    return [
        DatasetCandidate(
            dataset=dataset,
            source_id=source.source_id,
            source_type=source.source_type,
            source_url=source_url,
            confidence=0.8,
            evidence=(f"matched {len(versions)} file links",),
        )
    ]


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    text, _ = fetch_text(url, timeout=timeout)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return payload


def fetch_text(url: str, timeout: float) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()
    return data.decode(charset, errors="replace"), final_url


def zenodo_file_summaries(files: object) -> list[dict[str, object]]:
    if not isinstance(files, list):
        return []
    summaries = []
    for file_meta in files[:12]:
        if not isinstance(file_meta, dict):
            continue
        key = str(file_meta.get("key") or "")
        links = file_meta.get("links") if isinstance(file_meta.get("links"), dict) else {}
        summaries.append(
            {
                "key": key,
                "name": key,
                "format": Path(urllib.parse.urlparse(key).path).suffix.lower().lstrip(".") or "unknown",
                "download_url": links.get("self") or links.get("content") or links.get("download") or "",
                "size": file_meta.get("size") or 0,
                "checksum": file_meta.get("checksum") or "",
            }
        )
    return summaries


def strip_markup(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
