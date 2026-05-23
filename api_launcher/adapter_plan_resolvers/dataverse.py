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
FormatNormalizer = Callable[[str], str]

DATAVERSE_FILE_RESOLVER_ID = "dataverse_latest_version_file_resolver"
DATAVERSE_MAX_FILES = 5


def dataverse_latest_version_file_entries(
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
    source_format_from_url: FormatNormalizer,
    normalize_resource_format: FormatNormalizer,
    max_files: int = DATAVERSE_MAX_FILES,
    resolver_id: str = DATAVERSE_FILE_RESOLVER_ID,
) -> list[dict[str, object]]:
    # Dataverse landing/review item 需要先查 latest version files，不能直接把 dataset page 當下載檔。
    latest_url = dataverse_latest_version_url(entry, first_text=first_text)
    if not latest_url:
        return []
    try:
        payload = fetch_json(latest_url)
    except Exception:
        # 查詢失敗時維持 adapter review，避免把暫時性 API 問題誤判為可下載。
        return []
    resources = dataverse_file_resources(
        payload,
        latest_url,
        first_text=first_text,
        source_format_from_url=source_format_from_url,
        normalize_resource_format=normalize_resource_format,
    )
    resolved_entries: list[dict[str, object]] = []
    for resource_index, resource in enumerate(resources[:max_files], start=1):
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
            resolver_source_url=latest_url,
        )
        if resolved:
            resolved["adapter_resolution"] = {
                **resolved["adapter_resolution"],
                "policy": "latest_version_files_under_size_limit",
                "max_files": max_files,
            }
            resolved_entries.append(resolved)
    return resolved_entries


def dataverse_latest_version_url(
    entry: dict[str, object],
    *,
    first_text: FirstText,
) -> str:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    if not entry_is_dataverse_candidate(entry, option_metadata, first_text=first_text):
        return ""
    persistent_id = dataverse_persistent_id(option_metadata, first_text=first_text)
    if not persistent_id:
        return ""
    base_url = dataverse_base_url(entry, version_meta, option_metadata, first_text=first_text)
    if not base_url:
        return ""
    query = urllib.parse.urlencode({"persistentId": persistent_id})
    return f"{base_url}/api/datasets/:persistentId/versions/:latest?{query}"


def entry_is_dataverse_candidate(
    entry: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
) -> bool:
    markers = {
        str(entry.get("provider_id") or "").strip().lower(),
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("data_type") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
        str(option_metadata.get("source_type") or "").strip().lower(),
    }
    return any("dataverse" in marker for marker in markers) and bool(
        dataverse_persistent_id(option_metadata, first_text=first_text)
    )


def dataverse_persistent_id(option_metadata: dict[str, object], *, first_text: FirstText) -> str:
    raw_id = first_text(
        option_metadata.get("global_id"),
        option_metadata.get("persistent_id"),
        option_metadata.get("persistentId"),
        option_metadata.get("doi"),
    )
    if not raw_id:
        return ""
    lowered = raw_id.lower()
    if lowered.startswith(("doi:", "hdl:")):
        return raw_id
    parsed = urllib.parse.urlparse(raw_id)
    if parsed.netloc.lower() in {"doi.org", "dx.doi.org"} and parsed.path.strip("/"):
        return f"doi:{urllib.parse.unquote(parsed.path.strip('/'))}"
    if raw_id.startswith("10."):
        return f"doi:{raw_id}"
    return raw_id


def dataverse_base_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
) -> str:
    candidates = [
        option_metadata.get("dataverse_api_base_url"),
        option_metadata.get("api_base_url"),
        option_metadata.get("source_url"),
        version_meta.get("download_url"),
        (entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else "",
        entry.get("adapter_review_url"),
        entry.get("api_base_url"),
        entry.get("landing_url"),
        version_meta.get("landing_url"),
        entry.get("docs_url"),
    ]
    for candidate in candidates:
        raw_url = first_text(candidate)
        parsed = urllib.parse.urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        path = parsed.path.rstrip("/")
        marker = "/api/"
        if marker in path:
            path = path.split(marker, 1)[0]
        else:
            path = ""
        return urllib.parse.urlunparse(parsed._replace(path=path, params="", query="", fragment="")).rstrip("/")
    return ""


def dataverse_file_resources(
    payload: dict[str, object],
    latest_url: str,
    *,
    first_text: FirstText,
    source_format_from_url: FormatNormalizer,
    normalize_resource_format: FormatNormalizer,
) -> list[dict[str, object]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    files = data.get("files")
    if files is None and isinstance(data.get("items"), list):
        files = data.get("items")
    if not isinstance(files, list):
        return []
    resources: list[dict[str, object]] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        data_file = item.get("dataFile") if isinstance(item.get("dataFile"), dict) else item
        if bool(item.get("restricted") or data_file.get("restricted")):
            continue
        file_id = first_text(data_file.get("id"), item.get("dataFileId"), item.get("fileId"))
        if not file_id:
            continue
        filename = first_text(data_file.get("filename"), item.get("label"), data_file.get("label"), f"dataverse-file-{file_id}")
        content_type = first_text(data_file.get("contentType"), item.get("contentType"), data_file.get("mimetype"), item.get("mimetype"))
        resources.append(
            {
                "id": file_id,
                "name": filename,
                "format": dataverse_file_format(
                    filename,
                    content_type,
                    source_format_from_url=source_format_from_url,
                    normalize_resource_format=normalize_resource_format,
                ),
                "mimetype": content_type,
                "url": dataverse_datafile_access_url(latest_url, file_id),
                "size": first_text(data_file.get("filesize"), data_file.get("size"), item.get("filesize"), item.get("size")),
                "checksum": dataverse_file_checksum(data_file, first_text=first_text),
                "persistent_id": first_text(data_file.get("persistentId"), item.get("persistentId")),
            }
        )
    return resources


def dataverse_datafile_access_url(latest_url: str, file_id: str) -> str:
    parsed = urllib.parse.urlparse(latest_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse(
        parsed._replace(path=f"/api/access/datafile/{urllib.parse.quote(file_id, safe='')}", query="", fragment="")
    )


def dataverse_file_format(
    filename: str,
    content_type: str,
    *,
    source_format_from_url: FormatNormalizer,
    normalize_resource_format: FormatNormalizer,
) -> str:
    from_name = source_format_from_url(filename)
    if from_name != "unknown":
        return from_name
    return normalize_resource_format(content_type)


def dataverse_file_checksum(data_file: dict[str, object], *, first_text: FirstText) -> str:
    checksum = data_file.get("checksum")
    if isinstance(checksum, dict):
        checksum_type = first_text(checksum.get("type"))
        checksum_value = first_text(checksum.get("value"))
        if checksum_type and checksum_value:
            return f"{checksum_type}:{checksum_value}"
        return checksum_value or checksum_type
    return first_text(checksum, data_file.get("md5"))
