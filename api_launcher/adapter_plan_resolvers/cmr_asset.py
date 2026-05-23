from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Callable


FetchJson = Callable[[str], dict[str, object]]
DirectResourceEntry = Callable[..., dict[str, object] | None]
ResourceUrl = Callable[[dict[str, object]], str]
ResourceDownloadablePredicate = Callable[[dict[str, object], str], bool]
ResourceSizeGuard = Callable[[dict[str, object]], bool]
ResourceMetadataPredicate = Callable[[dict[str, object], dict[str, object], str], bool]
ResourceRels = Callable[[dict[str, object]], list[str]]
RelPredicate = Callable[[str], bool]
FirstText = Callable[..., str]

CMR_GRANULE_ASSET_RESOLVER_ID = "cmr_granule_asset_link_resolver"
CMR_GRANULE_ASSET_MAX_LINKS = 5
CMR_GRANULE_SAMPLE_LIMIT = 1


def cmr_granule_asset_link_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
    *,
    fetch_json: FetchJson,
    direct_resource_entry: DirectResourceEntry,
    resource_url: ResourceUrl,
    resource_looks_downloadable: ResourceDownloadablePredicate,
    resource_exceeds_size_bound: ResourceSizeGuard,
    resource_is_cmr_metadata_link: ResourceMetadataPredicate,
    resource_link_rels: ResourceRels,
    cmr_link_rel_is_data: RelPredicate,
    first_text: FirstText,
    resolver_id: str = CMR_GRANULE_ASSET_RESOLVER_ID,
    max_asset_links: int = CMR_GRANULE_ASSET_MAX_LINKS,
) -> list[dict[str, object]]:
    # CMR granule metadata 可能混合 metadata 與 data links；這裡只提升明確 data link。
    lookup_url = cmr_granule_asset_lookup_url(entry, first_text=first_text)
    if not lookup_url:
        return []
    try:
        payload = fetch_json(lookup_url)
    except Exception:
        # 外部 CMR API 暫時失敗時，保持 adapter review，不把失敗當成空成功。
        return []
    resources = cmr_granule_asset_resources(payload, first_text=first_text, resource_url=resource_url)
    resolved_entries: list[dict[str, object]] = []
    for resource_index, resource in enumerate(resources[:max_asset_links], start=1):
        url = resource_url(resource)
        if not url or not resource_looks_downloadable(resource, url):
            continue
        if not any(cmr_link_rel_is_data(rel) for rel in resource_link_rels(resource)):
            continue
        if resource_is_cmr_metadata_link(entry, resource, url):
            continue
        if resource_exceeds_size_bound(resource):
            continue
        resolved = direct_resource_entry(
            entry,
            resource,
            plan_index,
            resource_index,
            url,
            downloads_root,
            resolver_id=resolver_id,
            resolver_source_url=lookup_url,
        )
        if resolved:
            resolved["adapter_resolution"] = {
                **resolved["adapter_resolution"],
                "policy": "explicit_cmr_granule_data_links_under_size_limit",
                "lookup_url": lookup_url,
                "max_asset_links": max_asset_links,
            }
            resolved_entries.append(resolved)
    return resolved_entries


def cmr_granule_asset_lookup_url(entry: dict[str, object], *, first_text: FirstText) -> str:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    if not entry_is_cmr_granule(entry, option_metadata):
        return ""
    for raw_url in cmr_granule_asset_candidate_urls(entry, version_meta, option_metadata, first_text=first_text):
        lookup_url = bounded_cmr_granule_asset_lookup_url(raw_url)
        if lookup_url:
            return lookup_url
    return ""


def entry_is_cmr_granule(entry: dict[str, object], option_metadata: dict[str, object]) -> bool:
    markers = {
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("data_type") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
        str(option_metadata.get("source_type") or "").strip().lower(),
    }
    if {"cmr_granule", "cmr_granules"} & markers:
        return True
    return bool(
        option_metadata.get("granule_concept_id")
        or option_metadata.get("cmr_granule_id")
        or option_metadata.get("granule_ur")
    )


def cmr_granule_asset_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
) -> list[str]:
    candidates = [
        option_metadata.get("cmr_granule_url"),
        option_metadata.get("granule_concept_url"),
        version_meta.get("download_url"),
        entry.get("adapter_review_url"),
        option_metadata.get("cmr_granules_url"),
        option_metadata.get("source_url"),
        (entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else "",
        entry.get("api_base_url"),
        entry.get("landing_url"),
        version_meta.get("landing_url"),
        entry.get("docs_url"),
    ]
    urls: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = first_text(candidate)
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def bounded_cmr_granule_asset_lookup_url(raw_url: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "cmr.earthdata.nasa.gov":
        return ""
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    concept_id = cmr_granule_concept_id_from_path(path)
    if concept_id:
        concept_path = path.rsplit("/", 1)[0] + f"/{concept_id}.json"
        return urllib.parse.urlunparse(parsed._replace(path=concept_path, query="", fragment=""))
    if lower_path.endswith("/search/granules"):
        path = f"{path}.json"
    elif not lower_path.endswith("/search/granules.json"):
        return ""
    query_pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in {"page_size", "page_num", "offset"}
    ]
    query_pairs.append(("page_size", str(CMR_GRANULE_SAMPLE_LIMIT)))
    query = urllib.parse.urlencode(query_pairs, doseq=True, safe=",")
    return urllib.parse.urlunparse(parsed._replace(path=path, query=query, fragment=""))


def cmr_granule_concept_id_from_path(path: str) -> str:
    segments = [segment for segment in path.rstrip("/").split("/") if segment]
    if len(segments) < 3 or segments[-2].lower() != "concepts":
        return ""
    candidate = segments[-1]
    for suffix in (".json", ".html"):
        if candidate.lower().endswith(suffix):
            candidate = candidate[: -len(suffix)]
            break
    return candidate if candidate.upper().startswith("G") else ""


def cmr_granule_asset_resources(
    payload: dict[str, object],
    *,
    first_text: FirstText,
    resource_url: ResourceUrl,
) -> list[dict[str, object]]:
    resources: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for record in cmr_granule_records(payload):
        for resource in cmr_link_resources(record, first_text=first_text, resource_url=resource_url):
            url = resource_url(resource)
            rel = first_text(resource.get("rel"))
            key = (url, rel)
            if not url or key in seen:
                continue
            seen.add(key)
            resources.append(resource)
    return resources


def cmr_granule_records(payload: dict[str, object]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    feed = payload.get("feed") if isinstance(payload.get("feed"), dict) else {}
    feed_entries = feed.get("entry") if isinstance(feed.get("entry"), list) else []
    records.extend(dict(item) for item in feed_entries if isinstance(item, dict))
    for key in ("entry", "items", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            records.extend(dict(item) for item in value if isinstance(item, dict))
    if payload.get("links"):
        records.append(payload)
    return records


def cmr_link_resources(
    record: dict[str, object],
    *,
    first_text: FirstText,
    resource_url: ResourceUrl,
) -> list[dict[str, object]]:
    resources: list[dict[str, object]] = []
    links = record.get("links") if isinstance(record.get("links"), list) else []
    for link in links:
        if isinstance(link, dict):
            resources.append(cmr_feed_link_resource(link, first_text=first_text))
    return [resource for resource in resources if resource_url(resource)]


def cmr_feed_link_resource(link: dict[str, object], *, first_text: FirstText) -> dict[str, object]:
    url = first_text(link.get("href"), link.get("url"))
    return {
        "name": first_text(link.get("title"), link.get("name"), link.get("rel"), Path(urllib.parse.urlparse(url).path).name),
        "format": first_text(link.get("format"), link.get("mimetype"), link.get("mimeType"), link.get("type")),
        "mimetype": first_text(link.get("mimetype"), link.get("mimeType"), link.get("type")),
        "download_url": url,
        "rel": link.get("rel") or "",
        "size": first_text(link.get("sizeInBytes"), link.get("SizeInBytes"), link.get("size_bytes"), link.get("size")),
        "inherited": link.get("inherited") or False,
        "source": "cmr_granule_link",
    }
