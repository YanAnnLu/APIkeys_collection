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


def zenodo_records_search_url(endpoint_url: str, search_term: str, limit: int) -> str:
    return search_endpoint_url(endpoint_url, {"q": search_term, "type": "dataset", "size": str(max(1, limit))})


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


def paginated_zenodo_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    next_url = zenodo_records_search_url(source.endpoint_url, search_term, page_size)
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


def zenodo_candidates_for_source(
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
            candidates.extend(paginated_zenodo_candidates(source, term, timeout, limit, max_pages))
            continue
        url = zenodo_records_search_url(source.endpoint_url, term, limit)
        payload = fetch_json(url, timeout=timeout)
        candidates.extend(zenodo_candidates_from_payload(source, payload, url, limit))
    return candidates


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
