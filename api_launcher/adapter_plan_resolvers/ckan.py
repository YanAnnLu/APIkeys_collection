from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Callable


FetchJson = Callable[[str], dict[str, object]]
DirectResourceEntry = Callable[..., dict[str, object] | None]
ResourceUrl = Callable[[dict[str, object]], str]
ResourceDownloadablePredicate = Callable[[dict[str, object], str], bool]
ResourceSizeGuard = Callable[[dict[str, object]], bool]
FirstText = Callable[..., str]

CKAN_PACKAGE_RESOLVER_ID = "ckan_package_show_resource_resolver"


def ckan_package_show_resource_entries(
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
    resolver_id: str = CKAN_PACKAGE_RESOLVER_ID,
) -> list[dict[str, object]]:
    # CKAN review item 可能只指向 package_search；先收斂到 package_show 再挑可下載 resource。
    package_url = ckan_package_show_url(entry, first_text=first_text)
    if not package_url:
        return []
    try:
        payload = fetch_json(package_url)
    except Exception:
        # 來源 API 失敗時維持 review，不把暫時性錯誤轉成空成功。
        return []
    resources = ckan_package_show_resources(payload, first_text=first_text)
    resolved_entries: list[dict[str, object]] = []
    for resource_index, resource in enumerate(resources, start=1):
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
            resolver_source_url=package_url,
        )
        if resolved:
            resolved_entries.append(resolved)
    return resolved_entries


def ckan_package_show_url(entry: dict[str, object], *, first_text: FirstText) -> str:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    package_id = first_text(option_metadata.get("ckan_id"), entry.get("dataset_id"), version_meta.get("dataset_id"))
    candidates = (
        first_text((entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else ""),
        first_text(entry.get("adapter_review_url")),
        first_text(version_meta.get("download_url")),
        first_text(entry.get("api_base_url")),
    )
    for raw_url in candidates:
        parsed = urllib.parse.urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        path = parsed.path.rstrip("/")
        endpoint = path.rsplit("/", 1)[-1].lower()
        if endpoint == "package_show":
            return ckan_url_with_package_id(raw_url, package_id)
        if endpoint == "package_search":
            package_show_path = f"{path.rsplit('/', 1)[0]}/package_show"
            package_show_url = urllib.parse.urlunparse(parsed._replace(path=package_show_path, query=""))
            return ckan_url_with_package_id(package_show_url, package_id)
    return ""


def ckan_url_with_package_id(raw_url: str, package_id: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    query_pairs = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    if not query_pairs.get("id"):
        if not package_id:
            return ""
        query_pairs["id"] = package_id
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query_pairs)))


def ckan_package_show_resources(payload: dict[str, object], *, first_text: FirstText) -> list[dict[str, object]]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    resources = result.get("resources") if isinstance(result.get("resources"), list) else []
    normalized: list[dict[str, object]] = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        normalized.append(
            {
                "id": resource.get("id") or "",
                "name": first_text(resource.get("name"), resource.get("description"), resource.get("id")),
                "format": resource.get("format") or resource.get("mimetype") or "",
                "mimetype": resource.get("mimetype") or "",
                "url": resource.get("url") or resource.get("download_url") or "",
                "size": resource.get("size") or resource.get("bytes") or resource.get("content_length") or "",
                "last_modified": resource.get("last_modified") or resource.get("created") or "",
            }
        )
    return normalized
