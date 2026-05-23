from __future__ import annotations

import urllib.parse
from datetime import date
from pathlib import Path
from typing import Callable

from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.downloads.eligibility import DownloadEligibility
from api_launcher.models import Dataset
from api_launcher.plans import dataset_download_target_path, dataset_import_plan_entry


FirstText = Callable[..., str]

NCEI_ACCESS_DATA_RESOLVER_ID = "ncei_bounded_access_data_query_resolver"
NCEI_ACCESS_DATA_MAX_DAYS = 7


def ncei_bounded_access_data_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
    *,
    first_text: FirstText,
    first_query_value: Callable[[list[tuple[str, str]], str], str],
    parse_iso_calendar_date: Callable[[str], date | None],
    resource_mappings_from_entry: Callable[[dict[str, object]], list[dict[str, object]]],
    resource_url: Callable[[dict[str, object]], str],
    resolver_id: str = NCEI_ACCESS_DATA_RESOLVER_ID,
    max_days: int = NCEI_ACCESS_DATA_MAX_DAYS,
) -> dict[str, object]:
    # Access Data 只接受已經有清楚邊界的查詢；缺日期或缺空間條件時仍留在 adapter review。
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    sample_url, source_format, source_url, bounds = ncei_bounded_access_data_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        first_query_value=first_query_value,
        parse_iso_calendar_date=parse_iso_calendar_date,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
        max_days=max_days,
    )
    if not sample_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    ncei_dataset_id = first_text(bounds.get("dataset"), option_metadata.get("ncei_dataset_id"), option_metadata.get("ncei_result_id"))
    dataset_id = first_text(entry.get("dataset_id"), version_meta.get("dataset_id"), ncei_dataset_id, "ncei_access_data")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), dataset_id)
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-ncei-access-sample" if version else "ncei-access-sample"
    data_family = option_metadata.get("data_family") or entry.get("data_type") or "table_sample"
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
        data_type=str(data_family),
        native_format=source_format,
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
                "source_format": source_format,
                "max_days": max_days,
                "bounds": bounds,
            },
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset_uid,
        dataset_id=dataset_id,
        label=f"NCEI Access Data bounded sample {source_format.upper()}",
        version=sample_version,
        status="resolved_sample",
        download_url=sample_url,
        landing_url=dataset.landing_url,
        update_strategy="sample_then_review",
        notes="Bounded NOAA/NCEI Access Data Service request generated only when dataset, date range, and spatial bounds are present.",
        metadata={
            "native_format": source_format,
            "resolver_id": resolver_id,
            "ncei_dataset_id": ncei_dataset_id,
            "bounds": bounds,
        },
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason=(
            "The NOAA/NCEI Access Data request already includes dataset, spatial selector, "
            f"and a date range no longer than {max_days} days."
        ),
        direct_url=sample_url,
    )
    resolved = dict(entry)
    resolved.update(
        {
            "dataset_uid": dataset_uid,
            "dataset_id": dataset_id,
            "dataset_title": dataset.title,
            "dataset_version": option.to_plan_metadata(),
            "source_format": source_format,
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
                "policy": "bounded_access_data_query_only",
                "source_url": source_url,
                "source_format": source_format,
                "max_days": max_days,
                "bounds": bounds,
            },
        }
    )
    resolved.pop("adapter_review", None)
    resolved.pop("adapter_review_url", None)
    return resolved


def ncei_bounded_access_data_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
    first_query_value: Callable[[list[tuple[str, str]], str], str],
    parse_iso_calendar_date: Callable[[str], date | None],
    resource_mappings_from_entry: Callable[[dict[str, object]], list[dict[str, object]]],
    resource_url: Callable[[dict[str, object]], str],
    max_days: int = NCEI_ACCESS_DATA_MAX_DAYS,
) -> tuple[str, str, str, dict[str, object]]:
    for raw_url in ncei_access_data_candidate_urls(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
    ):
        sample_url, source_format, bounds = bounded_ncei_access_data_url(
            raw_url,
            first_query_value=first_query_value,
            parse_iso_calendar_date=parse_iso_calendar_date,
            max_days=max_days,
        )
        if sample_url:
            return sample_url, source_format, raw_url, bounds
    return "", "", "", {}


def ncei_access_data_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
    resource_mappings_from_entry: Callable[[dict[str, object]], list[dict[str, object]]],
    resource_url: Callable[[dict[str, object]], str],
) -> list[str]:
    candidates = [
        option_metadata.get("ncei_access_data_url"),
        option_metadata.get("access_data_url"),
        option_metadata.get("api_url"),
        version_meta.get("download_url"),
        (entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else "",
        entry.get("adapter_review_url"),
        entry.get("api_base_url"),
        entry.get("landing_url"),
        version_meta.get("landing_url"),
        entry.get("docs_url"),
    ]
    candidates.extend(resource_url(resource) for resource in resource_mappings_from_entry(entry))
    urls: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = first_text(candidate)
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def bounded_ncei_access_data_url(
    raw_url: str,
    *,
    first_query_value: Callable[[list[tuple[str, str]], str], str],
    parse_iso_calendar_date: Callable[[str], date | None],
    max_days: int = NCEI_ACCESS_DATA_MAX_DAYS,
) -> tuple[str, str, dict[str, object]]:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", "", {}
    if not resource_is_ncei_access_data_url(raw_url):
        return "", "", {}

    query = canonical_ncei_access_data_query(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    if not query:
        return "", "", {}
    bounds = ncei_access_data_bounds(
        query,
        first_query_value=first_query_value,
        parse_iso_calendar_date=parse_iso_calendar_date,
    )
    if not ncei_access_data_is_safely_bounded(bounds, max_days=max_days):
        return "", "", {}

    source_format = first_query_value(query, "format").lower()
    if source_format not in {"csv", "json"}:
        source_format = "json"
    query = [(key, value) for key, value in query if key.lower() != "format"]
    query.append(("format", source_format))
    sample_query = urllib.parse.urlencode(query, doseq=True, safe=",:")
    return urllib.parse.urlunparse(parsed._replace(query=sample_query, fragment="")), source_format, bounds


def canonical_ncei_access_data_query(query: list[tuple[str, str]]) -> list[tuple[str, str]]:
    allowed_keys = {
        "bbox": "bbox",
        "datatypes": "dataTypes",
        "dataset": "dataset",
        "enddate": "endDate",
        "format": "format",
        "includeattributes": "includeAttributes",
        "includestationlocation": "includeStationLocation",
        "includestationname": "includeStationName",
        "locationids": "locationIds",
        "options": "options",
        "startdate": "startDate",
        "stations": "stations",
        "units": "units",
    }
    canonical: list[tuple[str, str]] = []
    for key, value in query:
        normalized = key.strip().lower()
        if not value or normalized not in allowed_keys:
            continue
        canonical.append((allowed_keys[normalized], value))
    return canonical


def ncei_access_data_bounds(
    query: list[tuple[str, str]],
    *,
    first_query_value: Callable[[list[tuple[str, str]], str], str],
    parse_iso_calendar_date: Callable[[str], date | None],
) -> dict[str, object]:
    start_text = first_query_value(query, "startDate")
    end_text = first_query_value(query, "endDate")
    start = parse_iso_calendar_date(start_text)
    end = parse_iso_calendar_date(end_text)
    days = (end - start).days if start and end else None
    spatial_keys = [key for key in ("stations", "bbox", "locationIds") if first_query_value(query, key)]
    return {
        "dataset": first_query_value(query, "dataset"),
        "startDate": start_text,
        "endDate": end_text,
        "days": days,
        "spatial_keys": spatial_keys,
        "dataTypes": first_query_value(query, "dataTypes"),
    }


def ncei_access_data_is_safely_bounded(
    bounds: dict[str, object],
    *,
    max_days: int = NCEI_ACCESS_DATA_MAX_DAYS,
) -> bool:
    days = bounds.get("days")
    return bool(
        bounds.get("dataset")
        and bounds.get("startDate")
        and bounds.get("endDate")
        and isinstance(days, int)
        and 0 <= days <= max_days
        and bounds.get("spatial_keys")
    )


def resource_is_ncei_access_data_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    path = parsed.path.rstrip("/").lower()
    return path.endswith("/access/services/data/v1")
