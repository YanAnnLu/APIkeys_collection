from __future__ import annotations

import html
import re
import urllib.parse
from pathlib import Path
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
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


def datacite_dois_search_url(
    endpoint_url: str,
    search_term: str,
    limit: int,
    page_number: int | None = None,
) -> str:
    # DataCite 先抓 DOI metadata；contentUrl 是否能下載要交給 adapter resolver 再判斷。
    params = {
        "query": search_term,
        "resource-type-id": "dataset",
        "page[size]": str(max(1, limit)),
    }
    if page_number is not None:
        params["page[number]"] = str(max(1, page_number))
    return search_endpoint_url(endpoint_url, params)


def datacite_payload_items(payload: dict[str, Any]) -> list[Any]:
    items = payload.get("data")
    if not isinstance(items, list):
        raise ValueError("DataCite DOI payload missing data list")
    return items


def datacite_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    # DOI metadata 常是論文/資料集混合；這裡只建立候選與 provenance，不直接下載。
    items = datacite_payload_items(payload)
    candidates: list[DatasetCandidate] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
        doi = str(attributes.get("doi") or item.get("id") or "").strip()
        dataset_id = safe_dataset_id(doi or datacite_title(attributes) or "dataset")
        title = datacite_title(attributes) or dataset_id
        description = datacite_description(attributes)
        subjects = datacite_subjects(attributes.get("subjects"))
        formats = tuple(str(value).strip() for value in attributes.get("formats") or [] if str(value).strip())
        content_urls = datacite_content_urls(attributes.get("contentUrl"))
        types = attributes.get("types") if isinstance(attributes.get("types"), dict) else {}
        resource_type = str(types.get("resourceTypeGeneral") or "").strip()
        publisher = str(attributes.get("publisher") or "").strip()
        searchable = " ".join(
            (
                title,
                description,
                " ".join(subjects),
                " ".join(formats),
                resource_type,
                publisher,
                " ".join(source.categories),
            )
        )
        data_family = infer_data_family(searchable)
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, subjects[:8], (resource_type,)),
            data_type=data_family,
            native_format=choose_native_format(formats) if formats else "datacite_doi",
            geographic_scope=source.geographic_scope,
            landing_url=str(attributes.get("url") or (f"https://doi.org/{doi}" if doi else source.docs_url or source_url)),
            api_url=datacite_doi_api_url(source.endpoint_url, doi) if doi else source_url,
            license_url=datacite_rights_uri(attributes.get("rightsList")),
            version=str(attributes.get("version") or attributes.get("publicationYear") or attributes.get("updated") or "discovered"),
            remote_updated_at=str(attributes.get("updated") or attributes.get("registered") or attributes.get("created") or ""),
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
                "doi": doi,
                "resource_type": resource_type,
                "publisher": publisher,
                "publication_year": attributes.get("publicationYear") or "",
                "subjects": subjects,
                "formats": formats,
                "creators": datacite_names(attributes.get("creators"))[:12],
                "contributors": datacite_names(attributes.get("contributors"))[:12],
                "dates": attributes.get("dates") or [],
                "rights": attributes.get("rightsList") or [],
                "content_url": content_urls[0] if content_urls else "",
                "content_urls": content_urls,
                "resources": datacite_content_url_resources(content_urls, formats),
                "state": attributes.get("state") or "",
                "client_id": datacite_client_id(item),
                "view_count": attributes.get("viewCount") or 0,
                "download_count": attributes.get("downloadCount") or 0,
                "citation_count": attributes.get("citationCount") or 0,
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.79,
                evidence=("DataCite DOI metadata", f"doi: {doi or 'unknown'}"),
            )
        )
    return candidates


def paginated_datacite_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    next_url = datacite_dois_search_url(source.endpoint_url, search_term, page_size, page_number=1)
    for _page in range(discovery_page_cap(max_pages)):
        payload = fetch_json(next_url, timeout=timeout)
        items = datacite_payload_items(payload)
        page_candidates = datacite_candidates_from_payload(source, payload, next_url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        links = payload.get("links") if isinstance(payload.get("links"), dict) else {}
        next_candidate = str(links.get("next") or "")
        if not items or len(items) < page_size or added == 0 or not next_candidate:
            break
        polite_crawl_delay(source.crawl_rate_limit_seconds)
        next_url = next_candidate
    return candidates


def datacite_candidates_for_source(
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
            candidates.extend(paginated_datacite_candidates(source, term, timeout, limit, max_pages))
            continue
        url = datacite_dois_search_url(source.endpoint_url, term, limit)
        payload = fetch_json(url, timeout=timeout)
        candidates.extend(datacite_candidates_from_payload(source, payload, url, limit))
    return candidates


def datacite_title(attributes: dict[str, Any]) -> str:
    titles = attributes.get("titles")
    if not isinstance(titles, list):
        return ""
    for item in titles:
        if isinstance(item, dict) and item.get("title"):
            return str(item["title"]).strip()
    return ""


def datacite_description(attributes: dict[str, Any]) -> str:
    descriptions = attributes.get("descriptions")
    if not isinstance(descriptions, list):
        return ""
    for item in descriptions:
        if isinstance(item, dict) and item.get("description"):
            return strip_markup(item["description"])
    return ""


def datacite_subjects(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    subjects = []
    for item in value:
        if isinstance(item, dict):
            subject = str(item.get("subject") or "").strip()
        else:
            subject = str(item).strip()
        if subject:
            subjects.append(subject)
    return tuple(subjects)


def datacite_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                names.append(name)
    return tuple(names)


def datacite_rights_uri(value: object) -> str:
    if not isinstance(value, list):
        return ""
    for item in value:
        if isinstance(item, dict) and item.get("rightsUri"):
            return str(item["rightsUri"])
    return ""


def datacite_content_urls(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, dict):
        text = str(value.get("url") or value.get("contentUrl") or value.get("@id") or "").strip()
        return (text,) if text else ()
    if not isinstance(value, list):
        return ()
    urls: list[str] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, dict):
            text = str(item.get("url") or item.get("contentUrl") or item.get("@id") or "").strip()
        else:
            text = str(item or "").strip()
        if text and text not in seen:
            urls.append(text)
            seen.add(text)
    return tuple(urls)


def datacite_content_url_resources(urls: tuple[str, ...], formats: tuple[str, ...]) -> list[dict[str, object]]:
    resources: list[dict[str, object]] = []
    for index, url in enumerate(urls[:12], start=1):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        name = Path(urllib.parse.unquote(parsed.path)).name or f"content_url_{index}"
        resources.append(
            {
                "name": name,
                "format": datacite_resource_format(url, formats),
                "download_url": url,
                "rel": "contentUrl",
                "source": "datacite_content_url",
            }
        )
    return resources


def datacite_resource_format(url: str, formats: tuple[str, ...]) -> str:
    path = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path))
    suffixes = [suffix.lower().lstrip(".") for suffix in path.suffixes]
    # Preserve compound suffixes because downstream import plans distinguish these from plain gzip.
    compound_suffixes = (
        (("geojson", "gz"), "geojson.gz"),
        (("jsonl", "gz"), "jsonl.gz"),
        (("ndjson", "gz"), "ndjson.gz"),
        (("json", "gz"), "json.gz"),
        (("csv", "gz"), "csv.gz"),
        (("tar", "gz"), "tar.gz"),
    )
    for parts, source_format in compound_suffixes:
        if len(suffixes) >= len(parts) and tuple(suffixes[-len(parts) :]) == parts:
            return source_format
    if suffixes:
        return suffixes[-1]
    return choose_native_format(formats) if formats else "unknown"


def datacite_client_id(item: dict[str, Any]) -> str:
    relationships = item.get("relationships") if isinstance(item.get("relationships"), dict) else {}
    client = relationships.get("client") if isinstance(relationships.get("client"), dict) else {}
    data = client.get("data") if isinstance(client.get("data"), dict) else {}
    return str(data.get("id") or "")


def datacite_doi_api_url(endpoint_url: str, doi: str) -> str:
    base_url = endpoint_url.split("?", 1)[0].rstrip("/")
    return f"{base_url}/{urllib.parse.quote(doi, safe='')}"


def strip_markup(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
