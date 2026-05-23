from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Callable

from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.downloads.eligibility import DownloadEligibility
from api_launcher.models import Dataset
from api_launcher.plans import dataset_download_target_path, dataset_import_plan_entry


FirstText = Callable[..., str]

NCEI_SEARCH_RESOLVER_ID = "ncei_bounded_search_query_resolver"
NCEI_SEARCH_SAMPLE_LIMIT = 25


def ncei_bounded_search_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
    *,
    first_text: FirstText,
    resolver_id: str = NCEI_SEARCH_RESOLVER_ID,
    sample_limit: int = NCEI_SEARCH_SAMPLE_LIMIT,
) -> dict[str, object]:
    # NCEI Search resolver 只產生 bounded JSON metadata sample，不直接抓 NOAA 原始資料檔。
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    sample_url, source_url, endpoint_kind, ncei_dataset_id = ncei_bounded_search_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        sample_limit=sample_limit,
    )
    if not sample_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset_id = first_text(entry.get("dataset_id"), version_meta.get("dataset_id"), ncei_dataset_id, "ncei_dataset")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), dataset_id)
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-ncei-search-sample" if version else "ncei-search-sample"
    data_family = str(option_metadata.get("data_family") or entry.get("data_type") or "metadata_sample")
    dataset = Dataset(
        dataset_uid=dataset_uid,
        provider_id=provider_id,
        dataset_id=dataset_id,
        title=first_text(entry.get("dataset_title"), entry.get("name"), dataset_id),
        categories=(
            tuple(str(value) for value in entry.get("categories", ()) if str(value).strip())
            if isinstance(entry.get("categories"), (list, tuple))
            else ()
        ),
        data_type=data_family,
        native_format="json",
        geographic_scope=str(entry.get("geographic_scope") or ""),
        landing_url=first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
        api_url=sample_url,
        license_url=str(entry.get("license_url") or ""),
        version=sample_version,
        metadata={
            **option_metadata,
            "data_family": data_family,
            "bounded_query": {
                "resolver_id": resolver_id,
                "source_url": source_url,
                "endpoint_kind": endpoint_kind,
                "sample_limit": sample_limit,
                "ncei_dataset_id": ncei_dataset_id,
            },
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset_uid,
        dataset_id=dataset_id,
        label="NCEI bounded search sample JSON",
        version=sample_version,
        status="resolved_sample",
        download_url=sample_url,
        landing_url=dataset.landing_url,
        update_strategy="sample_then_review",
        notes="Bounded NOAA/NCEI Search API sample generated from crawler metadata; this downloads search metadata only.",
        metadata={"native_format": "json", "resolver_id": resolver_id, "ncei_dataset_id": ncei_dataset_id},
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason=f"The NOAA/NCEI Search API request was bounded to {sample_limit} JSON metadata records.",
        direct_url=sample_url,
    )
    resolved = dict(entry)
    resolved.update(
        {
            "dataset_uid": dataset_uid,
            "dataset_id": dataset_id,
            "dataset_title": dataset.title,
            "dataset_version": option.to_plan_metadata(),
            "source_format": "json",
            "target": "local_file_asset",
            "use_staging": True,
            "download_eligibility": eligibility.to_dict(),
            "download_url": sample_url,
            "target_path": dataset_download_target_path(provider_id, dataset, option, downloads_root).as_posix(),
            "import_plan": dataset_import_plan_entry(dataset, option, eligibility),
            "plan_status": "planned",
            "adapter_resolution": {
                "resolver_id": resolver_id,
                "original_plan_index": plan_index,
                "sample_url": sample_url,
                "policy": "bounded_search_metadata_sample_only",
                "sample_limit": sample_limit,
                "source_url": source_url,
                "endpoint_kind": endpoint_kind,
                "ncei_dataset_id": ncei_dataset_id,
            },
        }
    )
    resolved.pop("adapter_review", None)
    resolved.pop("adapter_review_url", None)
    return resolved


def ncei_bounded_search_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
    sample_limit: int = NCEI_SEARCH_SAMPLE_LIMIT,
) -> tuple[str, str, str, str]:
    if not entry_is_ncei_search_candidate(entry, option_metadata):
        return "", "", "", ""
    ncei_dataset_id = first_text(
        option_metadata.get("ncei_result_id"),
        option_metadata.get("ncei_dataset_id"),
        entry.get("dataset_id"),
        version_meta.get("dataset_id"),
    )
    for raw_url in ncei_candidate_urls(entry, version_meta, option_metadata, first_text=first_text):
        sample_url, endpoint_kind = bounded_ncei_search_url(raw_url, ncei_dataset_id, sample_limit=sample_limit)
        if sample_url:
            return sample_url, raw_url, endpoint_kind, ncei_dataset_id
    endpoint_url = first_text(option_metadata.get("ncei_search_endpoint_url"), option_metadata.get("source_endpoint_url"))
    if endpoint_url:
        sample_url, endpoint_kind = bounded_ncei_search_url(endpoint_url, ncei_dataset_id, sample_limit=sample_limit)
        if sample_url:
            return sample_url, endpoint_url, endpoint_kind, ncei_dataset_id
    return "", "", "", ""


def entry_is_ncei_search_candidate(entry: dict[str, object], option_metadata: dict[str, object]) -> bool:
    markers = {
        str(entry.get("provider_id") or "").strip().lower(),
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("data_type") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
        str(option_metadata.get("source_type") or "").strip().lower(),
    }
    if "ncei_search" in markers:
        return True
    return any("ncei" in marker for marker in markers) and bool(
        option_metadata.get("ncei_result_id") or option_metadata.get("ncei_dataset_id")
    )


def ncei_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
) -> list[str]:
    candidates = [
        option_metadata.get("source_url"),
        option_metadata.get("ncei_search_url"),
        option_metadata.get("api_url"),
        version_meta.get("download_url"),
        (entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else "",
        entry.get("adapter_review_url"),
        entry.get("api_base_url"),
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


def bounded_ncei_search_url(
    raw_url: str,
    ncei_dataset_id: str,
    *,
    sample_limit: int = NCEI_SEARCH_SAMPLE_LIMIT,
) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", ""
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    if "/access/services/search/v1/" not in lower_path:
        return "", ""
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if lower_path.endswith("/data"):
        sample_query = ncei_limited_query(query, require_dataset=True, dataset_id=ncei_dataset_id, sample_limit=sample_limit)
        if not sample_query:
            return "", ""
        return urllib.parse.urlunparse(parsed._replace(query=sample_query, fragment="")), "data"
    if lower_path.endswith("/datasets"):
        data_endpoint = ncei_search_sibling_endpoint(parsed, "data")
        if ncei_dataset_id:
            sample_query = ncei_limited_query(
                query,
                require_dataset=True,
                dataset_id=ncei_dataset_id,
                for_data_endpoint=True,
                sample_limit=sample_limit,
            )
            if sample_query:
                return urllib.parse.urlunparse(data_endpoint._replace(query=sample_query, fragment="")), "data"
        sample_query = ncei_limited_query(
            query,
            require_dataset=False,
            dataset_id="",
            for_data_endpoint=False,
            sample_limit=sample_limit,
        )
        if not sample_query:
            return "", ""
        return urllib.parse.urlunparse(parsed._replace(query=sample_query, fragment="")), "datasets"
    return "", ""


def ncei_search_sibling_endpoint(parsed: urllib.parse.ParseResult, endpoint: str) -> urllib.parse.ParseResult:
    prefix = parsed.path.rsplit("/", 1)[0]
    return parsed._replace(path=f"{prefix}/{endpoint}", query="", fragment="")


def ncei_limited_query(
    query: list[tuple[str, str]],
    require_dataset: bool,
    dataset_id: str,
    for_data_endpoint: bool = True,
    *,
    sample_limit: int = NCEI_SEARCH_SAMPLE_LIMIT,
) -> str:
    if for_data_endpoint:
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
    else:
        filtered = [
            (key, value)
            for key, value in query
            if key.lower() not in {"limit", "offset"} and value != ""
        ]
    filtered = [(key, value) for key, value in filtered if key.lower() not in {"limit", "offset"}]
    keys = {key.lower() for key, _value in filtered}
    if dataset_id and "dataset" not in keys:
        filtered.insert(0, ("dataset", dataset_id))
    if require_dataset and "dataset" not in {key.lower() for key, _value in filtered}:
        return ""
    if not filtered:
        return ""
    filtered.append(("limit", str(sample_limit)))
    filtered.append(("offset", "0"))
    return urllib.parse.urlencode(filtered, doseq=True, safe=",:")
