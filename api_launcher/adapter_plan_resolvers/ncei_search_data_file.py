from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Callable

from api_launcher.adapter_plan_resolvers.ncei_search import entry_is_ncei_search_candidate, ncei_candidate_urls


FirstText = Callable[..., str]

NCEI_SEARCH_DATA_FILE_RESOLVER_ID = "ncei_search_data_file_resolver"
NCEI_DATA_FILE_LOOKUP_LIMIT = 1


def ncei_search_data_file_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
    *,
    fetch_json: Callable[[str], dict[str, object]],
    first_text: FirstText,
    first_query_value: Callable[[list[tuple[str, str]], str], str],
    direct_resource_entry: Callable[..., dict[str, object] | None],
    resource_url: Callable[[dict[str, object]], str],
    resource_looks_downloadable: Callable[[dict[str, object], str], bool],
    resource_exceeds_size_bound: Callable[[dict[str, object]], bool],
    source_format_from_url: Callable[[str], str],
    resolver_id: str = NCEI_SEARCH_DATA_FILE_RESOLVER_ID,
    lookup_limit: int = NCEI_DATA_FILE_LOOKUP_LIMIT,
) -> list[dict[str, object]]:
    # 這一層只做「Search metadata -> 一筆受限檔案候選」；真正下載仍交給通用 plan runner。
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    lookup_url = ncei_search_data_file_lookup_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        first_query_value=first_query_value,
        lookup_limit=lookup_limit,
    )
    if not lookup_url:
        return []
    try:
        payload = fetch_json(lookup_url)
    except Exception:
        return []

    resolved_entries: list[dict[str, object]] = []
    resources = ncei_search_data_file_resources(
        payload,
        lookup_url,
        first_text=first_text,
        source_format_from_url=source_format_from_url,
        lookup_limit=lookup_limit,
    )
    for resource_index, resource in enumerate(resources[:lookup_limit], start=1):
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
            resolved["adapter_resolution"] = {
                **resolved["adapter_resolution"],
                "policy": "single_bounded_ncei_search_data_file_under_size_limit",
                "lookup_url": lookup_url,
                "lookup_limit": lookup_limit,
            }
            resolved_entries.append(resolved)
    return resolved_entries


def ncei_search_data_file_lookup_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
    first_query_value: Callable[[list[tuple[str, str]], str], str],
    lookup_limit: int = NCEI_DATA_FILE_LOOKUP_LIMIT,
) -> str:
    if not entry_is_ncei_search_candidate(entry, option_metadata):
        return ""
    ncei_dataset_id = first_text(
        option_metadata.get("ncei_result_id"),
        option_metadata.get("ncei_dataset_id"),
        entry.get("dataset_id"),
        version_meta.get("dataset_id"),
    )
    for raw_url in ncei_candidate_urls(entry, version_meta, option_metadata, first_text=first_text):
        lookup_url = bounded_ncei_search_data_file_lookup_url(
            raw_url,
            ncei_dataset_id,
            first_query_value=first_query_value,
            lookup_limit=lookup_limit,
        )
        if lookup_url:
            return lookup_url
    return ""


def bounded_ncei_search_data_file_lookup_url(
    raw_url: str,
    ncei_dataset_id: str,
    *,
    first_query_value: Callable[[list[tuple[str, str]], str], str],
    lookup_limit: int = NCEI_DATA_FILE_LOOKUP_LIMIT,
) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/").lower()
    if "/access/services/search/v1/" not in path or not path.endswith("/data"):
        return ""
    query = ncei_data_file_lookup_query(
        urllib.parse.parse_qsl(parsed.query, keep_blank_values=True),
        ncei_dataset_id,
        first_query_value=first_query_value,
        lookup_limit=lookup_limit,
    )
    if not query:
        return ""
    return urllib.parse.urlunparse(parsed._replace(query=query, fragment=""))


def ncei_data_file_lookup_query(
    query: list[tuple[str, str]],
    ncei_dataset_id: str,
    *,
    first_query_value: Callable[[list[tuple[str, str]], str], str],
    lookup_limit: int = NCEI_DATA_FILE_LOOKUP_LIMIT,
) -> str:
    allowed_keys = {
        "bbox": "bbox",
        "datatypes": "dataTypes",
        "dataset": "dataset",
        "enddate": "endDate",
        "locationids": "locationIds",
        "startdate": "startDate",
        "stations": "stations",
    }
    filtered = [
        (allowed_keys[key.lower()], value)
        for key, value in query
        if key.lower() in allowed_keys and value != ""
    ]
    keys = {key.lower() for key, _value in filtered}
    if ncei_dataset_id and "dataset" not in keys:
        filtered.insert(0, ("dataset", ncei_dataset_id))

    # 只允許 dataset + 明確空間/站點邊界；缺邊界時退回 bounded metadata sample，不碰原始檔。
    bounds = ncei_search_data_file_bounds(filtered, first_query_value=first_query_value)
    if not ncei_search_data_file_lookup_is_bounded(bounds):
        return ""
    filtered = [(key, value) for key, value in filtered if key.lower() not in {"limit", "offset"}]
    filtered.append(("limit", str(lookup_limit)))
    filtered.append(("offset", "0"))
    return urllib.parse.urlencode(filtered, doseq=True, safe=",:")


def ncei_search_data_file_bounds(
    query: list[tuple[str, str]],
    *,
    first_query_value: Callable[[list[tuple[str, str]], str], str],
) -> dict[str, object]:
    spatial_keys = [key for key in ("stations", "bbox", "locationIds") if first_query_value(query, key)]
    return {
        "dataset": first_query_value(query, "dataset"),
        "spatial_keys": spatial_keys,
        "startDate": first_query_value(query, "startDate"),
        "endDate": first_query_value(query, "endDate"),
        "dataTypes": first_query_value(query, "dataTypes"),
    }


def ncei_search_data_file_lookup_is_bounded(bounds: dict[str, object]) -> bool:
    return bool(bounds.get("dataset") and bounds.get("spatial_keys"))


def ncei_search_data_file_resources(
    payload: dict[str, object],
    lookup_url: str,
    *,
    first_text: FirstText,
    source_format_from_url: Callable[[str], str],
    lookup_limit: int = NCEI_DATA_FILE_LOOKUP_LIMIT,
) -> list[dict[str, object]]:
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    resources: list[dict[str, object]] = []
    for item in results[:lookup_limit]:
        if not isinstance(item, dict):
            continue
        resource = ncei_search_data_file_resource(
            item,
            lookup_url,
            first_text=first_text,
            source_format_from_url=source_format_from_url,
        )
        if resource:
            resources.append(resource)
    return resources


def ncei_search_data_file_resource(
    item: dict[str, object],
    lookup_url: str,
    *,
    first_text: FirstText,
    source_format_from_url: Callable[[str], str],
) -> dict[str, object]:
    file_path = first_text(item.get("filePath"), item.get("filepath"), item.get("path"))
    url = ncei_search_data_file_url(file_path, lookup_url)
    if not url:
        return {}
    return {
        "id": first_text(item.get("id")),
        "name": first_text(item.get("name"), Path(urllib.parse.urlparse(url).path).name, item.get("id")),
        "format": source_format_from_url(url),
        "download_url": url,
        "fileSize": first_text(item.get("fileSize"), item.get("size"), item.get("bytes")),
        "tar": first_text(item.get("tar")),
        "source": "ncei_search_data_file",
        "search_file_path": file_path,
    }


def ncei_search_data_file_url(file_path: str, lookup_url: str) -> str:
    if not file_path:
        return ""
    parsed_file = urllib.parse.urlparse(file_path)
    if parsed_file.scheme in {"http", "https"}:
        if ncei_noaa_host(parsed_file.netloc) and parsed_file.path.startswith("/data/"):
            return file_path
        return ""
    if not file_path.startswith("/data/"):
        return ""
    parsed_lookup = urllib.parse.urlparse(lookup_url)
    if parsed_lookup.scheme not in {"http", "https"} or not ncei_noaa_host(parsed_lookup.netloc):
        return ""
    return urllib.parse.urlunparse(parsed_lookup._replace(path=file_path, query="", fragment=""))


def ncei_noaa_host(netloc: str) -> bool:
    host = netloc.split("@")[-1].split(":")[0].lower()
    return host == "ncei.noaa.gov" or host.endswith(".ncei.noaa.gov")
