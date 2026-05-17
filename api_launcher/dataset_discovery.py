from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.discovery import extract_links
from api_launcher.models import Dataset


USER_AGENT = "APIkeys_collection/0.4 (+dataset-discovery; metadata only)"
DEFAULT_DATASET_DISCOVERY_SOURCES_NAME = "dataset_discovery_sources.json"


@dataclass(frozen=True)
class DatasetDiscoverySource:
    source_id: str
    provider_id: str
    name: str
    source_type: str
    endpoint_url: str
    docs_url: str = ""
    search_terms: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    geographic_scope: str = "global"
    max_results: int = 10
    dataset_id: str = ""
    dataset_title: str = ""
    data_type: str = ""
    native_format: str = ""
    file_url_regex: str = ""
    notes: str = ""


@dataclass(frozen=True)
class DatasetCandidate:
    dataset: Dataset
    source_id: str
    source_type: str
    source_url: str
    confidence: float
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "dataset": dataset_to_dict(self.dataset),
        }


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
            notes=str(item.get("notes") or "").strip(),
        )
        for item in data.get("sources", [])
    ]


def discover_dataset_candidates(
    sources: list[DatasetDiscoverySource],
    timeout: float = 12.0,
    max_results_override: int = 0,
    search_terms_override: tuple[str, ...] = (),
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        source_candidates = discover_dataset_candidates_for_source(
            source,
            timeout=timeout,
            max_results_override=max_results_override,
            search_terms_override=search_terms_override,
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
) -> list[DatasetCandidate]:
    limit = max_results_override or source.max_results
    search_terms = search_terms_override or source.search_terms
    if source.source_type == "ncei_search":
        candidates: list[DatasetCandidate] = []
        for term in search_terms or ("",):
            url = ncei_search_url(source.endpoint_url, term, limit)
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(ncei_candidates_from_payload(source, payload, url, limit))
        return candidates
    if source.source_type == "erddap_all_datasets":
        payload = fetch_json(source.endpoint_url, timeout=timeout)
        return erddap_candidates_from_payload(source, payload, source.endpoint_url, limit, search_terms)
    if source.source_type == "html_file_index":
        text, final_url = fetch_text(source.endpoint_url, timeout=timeout)
        return html_file_index_candidates_from_text(source, text, final_url, limit)
    if source.source_type == "cmr_collections":
        candidates = []
        for term in search_terms or ("",):
            url = cmr_collections_url(source.endpoint_url, term, limit)
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(cmr_candidates_from_payload(source, payload, url, limit))
        return candidates
    if source.source_type == "stac_collections":
        payload = fetch_json(source.endpoint_url, timeout=timeout)
        return stac_candidates_from_payload(source, payload, source.endpoint_url, limit, search_terms)
    if source.source_type == "gbif_dataset_search":
        candidates = []
        for term in search_terms or ("",):
            url = search_endpoint_url(source.endpoint_url, {"q": term, "limit": str(max(1, limit))})
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(gbif_candidates_from_payload(source, payload, url, limit))
        return candidates
    if source.source_type == "ckan_package_search":
        candidates = []
        for term in search_terms or ("",):
            url = search_endpoint_url(source.endpoint_url, {"q": term, "rows": str(max(1, limit))})
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(ckan_candidates_from_payload(source, payload, url, limit))
        return candidates
    raise ValueError(f"Unsupported dataset discovery source_type: {source.source_type}")


def ncei_search_url(endpoint_url: str, search_term: str, limit: int) -> str:
    return search_endpoint_url(
        endpoint_url,
        {"limit": str(max(1, limit)), "available": "true", "text": search_term},
    )


def cmr_collections_url(endpoint_url: str, search_term: str, limit: int) -> str:
    return search_endpoint_url(
        endpoint_url,
        {"page_size": str(max(1, limit)), "downloadable": "true", "keyword": search_term},
    )


def search_endpoint_url(endpoint_url: str, params: dict[str, str]) -> str:
    clean_params = {key: value for key, value in params.items() if value}
    separator = "&" if urllib.parse.urlparse(endpoint_url).query else "?"
    return endpoint_url + separator + urllib.parse.urlencode(clean_params)


def ncei_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    for item in payload.get("results", [])[:limit]:
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


def erddap_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
    search_terms: tuple[str, ...],
) -> list[DatasetCandidate]:
    table = payload.get("table") if isinstance(payload.get("table"), dict) else {}
    columns = [str(value) for value in table.get("columnNames", [])]
    rows = table.get("rows", [])
    candidates: list[DatasetCandidate] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        item = {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
        searchable = " ".join(str(item.get(key) or "") for key in ("datasetID", "title", "summary", "institution")).lower()
        if search_terms and not any(term.lower() in searchable for term in search_terms):
            continue
        dataset_id = safe_dataset_id(str(item.get("datasetID") or "dataset"))
        title = str(item.get("title") or dataset_id)
        data_family = infer_data_family(searchable)
        api_url = str(item.get("griddap") or item.get("tabledap") or item.get("infoUrl") or source_url)
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, (str(item.get("cdm_data_type") or ""),)),
            data_type=data_family,
            native_format="erddap",
            geographic_scope=source.geographic_scope,
            landing_url=str(item.get("infoUrl") or source.docs_url or source_url),
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
                "erddap_dataset_id": item.get("datasetID") or "",
                "erddap_protocols": {
                    "griddap": item.get("griddap") or "",
                    "tabledap": item.get("tabledap") or "",
                    "wms": item.get("wms") or "",
                },
                "summary": item.get("summary") or "",
                "institution": item.get("institution") or "",
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.86,
                evidence=("ERDDAP allDatasets row",),
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def cmr_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    feed = payload.get("feed") if isinstance(payload.get("feed"), dict) else {}
    entries = feed.get("entry", [])
    if not isinstance(entries, list):
        return []
    candidates: list[DatasetCandidate] = []
    for item in entries[:limit]:
        if not isinstance(item, dict):
            continue
        concept_id = str(item.get("id") or "").strip()
        short_name = str(item.get("short_name") or item.get("entry_id") or concept_id or "dataset").strip()
        version = str(item.get("version_id") or "").strip()
        dataset_id = safe_dataset_id("-".join(part for part in (short_name, version) if part))
        title = str(item.get("title") or item.get("dataset_id") or short_name)
        summary = str(item.get("summary") or "")
        searchable = " ".join(
            (
                title,
                summary,
                short_name,
                str(item.get("data_center") or ""),
                platform_names(item.get("platforms")),
                " ".join(source.categories),
            )
        )
        data_family = infer_data_family(searchable)
        links = item.get("links") if isinstance(item.get("links"), list) else []
        landing_url = first_cmr_link_url(links, ("metadata", "browse", "documentation")) or source.docs_url or source_url
        api_url = (
            "https://cmr.earthdata.nasa.gov/search/granules.json?"
            + urllib.parse.urlencode({"collection_concept_id": concept_id})
            if concept_id
            else source_url
        )
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, tuple(filter(None, (str(item.get("data_center") or ""),)))),
            data_type=data_family,
            native_format="cmr_collection",
            geographic_scope=source.geographic_scope,
            temporal_coverage=temporal_coverage(item.get("time_start"), item.get("time_end")),
            landing_url=landing_url,
            api_url=api_url,
            version=version or "discovered",
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
                "cmr_concept_id": concept_id,
                "short_name": short_name,
                "data_center": item.get("data_center") or "",
                "cloud_hosted": bool(item.get("cloud_hosted")),
                "online_access_flag": bool(item.get("online_access_flag")),
                "links": links[:12],
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.85,
                evidence=("NASA CMR collection search result", f"short_name: {short_name}"),
            )
        )
    return candidates


def stac_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
    search_terms: tuple[str, ...],
) -> list[DatasetCandidate]:
    collections = payload.get("collections", [])
    if not isinstance(collections, list):
        return []
    candidates: list[DatasetCandidate] = []
    for item in collections:
        if not isinstance(item, dict):
            continue
        keywords = tuple(str(value) for value in item.get("keywords") or [] if value)
        providers = item.get("providers") if isinstance(item.get("providers"), list) else []
        asset_map = item.get("assets") or item.get("item_assets") or {}
        if not isinstance(asset_map, dict):
            asset_map = {}
        searchable = " ".join(
            (
                str(item.get("id") or ""),
                str(item.get("title") or ""),
                str(item.get("description") or ""),
                " ".join(keywords),
                " ".join(provider.get("name", "") for provider in providers if isinstance(provider, dict)),
            )
        )
        if search_terms and not matches_any_term(searchable, search_terms):
            continue
        dataset_id = safe_dataset_id(str(item.get("id") or "dataset"))
        title = str(item.get("title") or dataset_id)
        data_family = infer_data_family(searchable)
        links = item.get("links") if isinstance(item.get("links"), list) else []
        landing_url = first_stac_link_url(links, ("self", "root", "parent")) or source.docs_url or source_url
        api_url = first_stac_link_url(links, ("items", "self")) or source_url
        temporal = stac_temporal_coverage(item.get("extent"))
        categories = merge_categories(source.categories, keywords[:6])
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=categories or ("stac",),
            data_type=data_family,
            native_format="stac_collection",
            geographic_scope=source.geographic_scope,
            temporal_coverage=temporal,
            landing_url=landing_url,
            api_url=api_url,
            license_url=str(item.get("license") or ""),
            version=str(item.get("version") or item.get("stac_version") or "discovered"),
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
                "stac_id": item.get("id") or "",
                "stac_version": item.get("stac_version") or "",
                "keywords": keywords,
                "providers": providers,
                "asset_keys": sorted(asset_map.keys())[:24],
                "extent": item.get("extent") or {},
                "links": links[:12],
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.87,
                evidence=("STAC collection", f"collection: {dataset_id}"),
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def gbif_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    results = payload.get("results", [])
    if not isinstance(results, list):
        return []
    candidates: list[DatasetCandidate] = []
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        dataset_id = safe_dataset_id(key or item.get("doi") or item.get("title") or "dataset")
        title = str(item.get("title") or dataset_id)
        description = str(item.get("description") or "")
        keywords = tuple(str(value) for value in item.get("keywords") or [] if value)
        searchable = " ".join((title, description, str(item.get("type") or ""), " ".join(keywords), " ".join(source.categories)))
        data_family = infer_data_family(searchable)
        landing_url = f"https://www.gbif.org/dataset/{key}" if key else source.docs_url or source_url
        api_url = f"https://api.gbif.org/v1/dataset/{key}" if key else source_url
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, keywords[:6], (str(item.get("type") or ""),)),
            data_type=data_family,
            native_format="gbif_dataset",
            geographic_scope=source.geographic_scope,
            landing_url=landing_url,
            api_url=api_url,
            license_url=str(item.get("license") or ""),
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
                "gbif_key": key,
                "dataset_type": item.get("type") or "",
                "record_count": item.get("recordCount") or 0,
                "publishing_organization": item.get("publishingOrganizationTitle") or "",
                "hosting_organization": item.get("hostingOrganizationTitle") or "",
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.84,
                evidence=("GBIF dataset search result", f"key: {key or 'unknown'}"),
            )
        )
    return candidates


def ckan_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    results = result.get("results", [])
    if not isinstance(results, list):
        return []
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


def html_file_index_candidates_from_text(
    source: DatasetDiscoverySource,
    text: str,
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    if not source.file_url_regex:
        return []
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
        if len(versions) >= limit:
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


def dataset_to_dict(dataset: Dataset) -> dict[str, object]:
    return {
        "dataset_uid": dataset.dataset_uid,
        "provider_id": dataset.provider_id,
        "dataset_id": dataset.dataset_id,
        "title": dataset.title,
        "categories": list(dataset.categories),
        "data_type": dataset.data_type,
        "native_format": dataset.native_format,
        "geographic_scope": dataset.geographic_scope,
        "temporal_coverage": dataset.temporal_coverage,
        "landing_url": dataset.landing_url,
        "api_url": dataset.api_url,
        "license_url": dataset.license_url,
        "version": dataset.version,
        "remote_updated_at": dataset.remote_updated_at,
        "remote_etag": dataset.remote_etag,
        "remote_hash": dataset.remote_hash,
        "metadata": dataset.metadata,
    }


def safe_dataset_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().lower()).strip("_")
    return cleaned or "dataset"


def tuple_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("id") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return tuple(names)


def merge_categories(*groups: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            normalized = safe_dataset_id(value).replace("-", "_")
            if normalized and normalized not in seen:
                values.append(normalized)
                seen.add(normalized)
    return tuple(values)


def first_link_url(links: object, groups: tuple[str, ...]) -> str:
    if not isinstance(links, dict):
        return ""
    for group in groups:
        values = links.get(group)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict) and item.get("url"):
                return str(item["url"])
    return ""


def choose_native_format(formats: tuple[str, ...]) -> str:
    preferred = (
        "parquet",
        "geoparquet",
        "zarr",
        "netcdf",
        "hdf5",
        "geotiff",
        "tiff",
        "grib",
        "geojson",
        "shapefile",
        "csv",
        "json",
        "api",
        "native",
    )
    lowered = {safe_dataset_id(value).replace("-", "_"): value.lower() for value in formats}
    for value in preferred:
        if value in lowered:
            return lowered[value]
    return formats[0].lower() if formats else "unknown"


def temporal_coverage(start: object, end: object) -> str:
    start_text = str(start or "").strip()
    end_text = str(end or "").strip()
    if start_text and end_text:
        return f"{start_text}/{end_text}"
    return start_text or end_text


def infer_data_family(text: str) -> str:
    lowered = text.lower()
    if any(value in lowered for value in ("gbif", "biodiversity", "species occurrence", "occurrence", "taxon")):
        return "biodiversity_occurrence"
    if any(value in lowered for value in ("ais", "vessel", "trajectory", "ship")):
        return "spatiotemporal_trajectory"
    if any(value in lowered for value in ("cloud", "imagery", "satellite", "raster", "abi", "goes")):
        return "raster_or_grid"
    if any(value in lowered for value in ("netcdf", "grib", "grid", "sst", "sea surface temperature")):
        return "grid_or_array"
    if any(value in lowered for value in ("boundary", "polygon", "shapefile", "geojson", "gis")):
        return "gis"
    if any(value in lowered for value in ("hourly", "daily", "time series", "timeseries")):
        return "timeseries"
    return "table_or_document"


def storage_hint_for_family(data_family: str) -> str:
    hints = {
        "biodiversity_occurrence": "duckdb_postgis_or_partitioned_occurrence_files",
        "spatiotemporal_trajectory": "filesystem_or_object_storage_then_partitioned_columnar_store",
        "raster_or_grid": "netcdf_zarr_cog_or_object_storage",
        "grid_or_array": "netcdf_zarr_hdf5_or_object_storage",
        "gis": "geopackage_geojson_shapefile_or_postgis",
        "timeseries": "timeseries_db_or_partitioned_files",
    }
    return hints.get(data_family, "filesystem_or_sql_after_review")


def sql_role_for_family(data_family: str) -> str:
    if data_family in {"spatiotemporal_trajectory", "raster_or_grid", "grid_or_array", "gis"}:
        return "metadata_index_or_curated_sample_table"
    return "primary_or_curated_table_after_review"


def analysis_hint_for_family(data_family: str) -> str:
    hints = {
        "biodiversity_occurrence": "duckdb_postgis_geopandas_or_gbif_tools",
        "spatiotemporal_trajectory": "duckdb_geopandas_postgis_dask_spark",
        "raster_or_grid": "xarray_rioxarray_dask_or_gdal",
        "grid_or_array": "xarray_dask_or_netcdf_tools",
        "gis": "qgis_postgis_geopandas",
        "timeseries": "duckdb_timescaledb_clickhouse",
    }
    return hints.get(data_family, "python_sql_or_domain_adapter")


def viewer_hint_for_family(data_family: str) -> str:
    hints = {
        "biodiversity_occurrence": "map_points_heatmap_or_species_filter",
        "spatiotemporal_trajectory": "map_trajectory_heatmap_or_timeline",
        "raster_or_grid": "globe_texture_or_time_animation",
        "grid_or_array": "map_layer_or_timeseries_preview",
        "gis": "map_layer_or_unreal_globe_overlay",
        "timeseries": "tradingview_like_chart",
    }
    return hints.get(data_family, "table_or_document_preview")


def matches_any_term(text: str, search_terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in search_terms)


def first_stac_link_url(links: list[object], rels: tuple[str, ...]) -> str:
    for rel in rels:
        for link in links:
            if isinstance(link, dict) and str(link.get("rel") or "").lower() == rel and link.get("href"):
                return str(link["href"])
    return ""


def first_cmr_link_url(links: list[object], hints: tuple[str, ...]) -> str:
    for link in links:
        if not isinstance(link, dict) or not link.get("href"):
            continue
        searchable = " ".join(str(link.get(key) or "") for key in ("rel", "title", "type")).lower()
        if any(hint in searchable for hint in hints):
            return str(link["href"])
    for link in links:
        if isinstance(link, dict) and str(link.get("href") or "").startswith("http"):
            return str(link["href"])
    return ""


def platform_names(platforms: object) -> str:
    if not isinstance(platforms, list):
        return ""
    names = []
    for platform in platforms:
        if isinstance(platform, dict):
            names.append(str(platform.get("short_name") or platform.get("long_name") or ""))
    return " ".join(name for name in names if name)


def stac_temporal_coverage(extent: object) -> str:
    if not isinstance(extent, dict):
        return ""
    temporal = extent.get("temporal") if isinstance(extent.get("temporal"), dict) else {}
    intervals = temporal.get("interval") if isinstance(temporal.get("interval"), list) else []
    if not intervals or not isinstance(intervals[0], list):
        return ""
    start = str(intervals[0][0] or "") if len(intervals[0]) > 0 else ""
    end = str(intervals[0][1] or "") if len(intervals[0]) > 1 else ""
    return temporal_coverage(start, end)


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
