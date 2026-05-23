from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Callable

from api_launcher.crawlers.datacite import datacite_content_url_resources, datacite_content_urls


FetchJson = Callable[[str], dict[str, object]]
DirectResourceEntry = Callable[..., dict[str, object] | None]
ResourceUrl = Callable[[dict[str, object]], str]
ResourceDownloadablePredicate = Callable[[dict[str, object], str], bool]
ResourceSizeGuard = Callable[[dict[str, object]], bool]
FirstText = Callable[..., str]

DATACITE_DOI_CONTENT_URL_RESOLVER_ID = "datacite_doi_content_url_resolver"
DATACITE_MAX_CONTENT_URLS = 5


def datacite_doi_content_url_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
    *,
    fetch_json: FetchJson,
    direct_resource_entry: DirectResourceEntry,
    resource_url: ResourceUrl,
    resource_looks_downloadable: ResourceDownloadablePredicate,
    resource_exceeds_size_bound: ResourceSizeGuard,
    first_text: FirstText,
    max_content_urls: int = DATACITE_MAX_CONTENT_URLS,
    resolver_id: str = DATACITE_DOI_CONTENT_URL_RESOLVER_ID,
) -> list[dict[str, object]]:
    # DataCite/OpenAlex 的 review item 通常只給 DOI metadata；這裡只做有界二階段查詢。
    lookup_url = datacite_doi_content_url_lookup_url(entry, first_text=first_text)
    if not lookup_url:
        return []
    try:
        payload = fetch_json(lookup_url)
    except Exception:
        # 外部 metadata API 失敗時保持 review 狀態，不讓 resolver 假裝成功。
        return []

    resources = datacite_doi_content_url_resources(payload, lookup_url)
    resolved_entries: list[dict[str, object]] = []
    for resource_index, resource in enumerate(resources[:max_content_urls], start=1):
        url = resource_url(resource)
        if not url or not resource_looks_downloadable(resource, url):
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
            # adapter_resolution 是 agent/UI 後續稽核入口，保留查詢策略與上限。
            resolved["adapter_resolution"] = {
                **resolved["adapter_resolution"],
                "policy": "single_datacite_doi_metadata_content_url_lookup",
                "lookup_url": lookup_url,
                "max_content_urls": max_content_urls,
            }
            resolved_entries.append(resolved)
    return resolved_entries


def datacite_doi_content_url_lookup_url(
    entry: dict[str, object],
    *,
    first_text: FirstText,
) -> str:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    if not entry_is_doi_metadata_candidate(entry, option_metadata):
        return ""
    doi = doi_identifier_from_entry(entry, version_meta, option_metadata, first_text=first_text)
    if not doi:
        return ""
    for raw_url in datacite_doi_candidate_urls(entry, version_meta, option_metadata, first_text=first_text):
        lookup_url = datacite_doi_api_url(raw_url, doi)
        if lookup_url:
            return lookup_url
    return f"https://api.datacite.org/dois/{urllib.parse.quote(doi, safe='')}"


def entry_is_doi_metadata_candidate(entry: dict[str, object], option_metadata: dict[str, object]) -> bool:
    markers = {
        str(entry.get("provider_id") or "").strip().lower(),
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("data_type") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
        str(option_metadata.get("source_type") or "").strip().lower(),
    }
    return bool(
        {"datacite", "datacite_doi", "datacite_dois", "openalex", "openalex_work", "openalex_works_search"} & markers
    )


def doi_identifier_from_entry(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
) -> str:
    candidates = [
        option_metadata.get("doi"),
        option_metadata.get("global_id"),
        option_metadata.get("persistent_id"),
        option_metadata.get("persistentId"),
        entry.get("dataset_id"),
        version_meta.get("dataset_id"),
        version_meta.get("download_url"),
        version_meta.get("landing_url"),
        entry.get("adapter_review_url"),
        entry.get("landing_url"),
    ]
    for candidate in candidates:
        doi = normalize_doi_identifier(first_text(candidate))
        if doi:
            return doi
    return ""


def normalize_doi_identifier(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered.startswith("doi:"):
        raw = raw[4:].strip()
    else:
        parsed = urllib.parse.urlparse(raw)
        if parsed.netloc.lower() in {"doi.org", "dx.doi.org"} and parsed.path.strip("/"):
            raw = urllib.parse.unquote(parsed.path.strip("/"))
        elif "/doi/" in parsed.path.lower():
            raw = urllib.parse.unquote(parsed.path.rsplit("/doi/", 1)[-1].strip("/"))
    return raw if raw.lower().startswith("10.") and "/" in raw else ""


def datacite_doi_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
) -> list[str]:
    candidates = [
        option_metadata.get("datacite_api_url"),
        option_metadata.get("api_url"),
        version_meta.get("download_url"),
        (entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else "",
        entry.get("adapter_review_url"),
        entry.get("api_base_url"),
        option_metadata.get("source_url"),
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


def datacite_doi_api_url(raw_url: str, doi: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if "datacite" not in parsed.netloc.lower():
        return ""
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    marker = "/dois"
    if marker not in lower_path:
        return ""
    prefix = path[: lower_path.index(marker) + len(marker)]
    encoded_doi = urllib.parse.quote(doi, safe="")
    return urllib.parse.urlunparse(parsed._replace(path=f"{prefix}/{encoded_doi}", query="", fragment=""))


def datacite_doi_content_url_resources(payload: dict[str, object], lookup_url: str) -> list[dict[str, object]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    attributes = data.get("attributes") if isinstance(data.get("attributes"), dict) else {}
    content_urls = datacite_content_urls(attributes.get("contentUrl"))
    raw_formats = attributes.get("formats")
    formats = (
        tuple(str(value).strip() for value in raw_formats if str(value).strip())
        if isinstance(raw_formats, list)
        else ()
    )
    resources = datacite_content_url_resources(content_urls, formats)
    for resource in resources:
        resource["source"] = "datacite_doi_content_url_lookup"
        resource["lookup_url"] = lookup_url
    return resources
