from __future__ import annotations

from typing import Any

from api_launcher.adapters.base import dataset_uid
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
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


def ckan_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
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
