from __future__ import annotations

import html
import re
import urllib.parse
from pathlib import Path
from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.metadata import (
    analysis_hint_for_family,
    infer_data_family,
    merge_categories,
    safe_dataset_id,
    sql_role_for_family,
    storage_hint_for_family,
    viewer_hint_for_family,
)
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


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
