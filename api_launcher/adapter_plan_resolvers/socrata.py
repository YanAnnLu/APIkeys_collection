from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Callable

from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.downloads.eligibility import DownloadEligibility
from api_launcher.models import Dataset
from api_launcher.plans import dataset_download_target_path, dataset_import_plan_entry


FirstText = Callable[..., str]
ResourceMappingsFromEntry = Callable[[dict[str, object]], list[dict[str, object]]]
ResourceUrl = Callable[[dict[str, object]], str]

SOCRATA_RESOLVER_ID = "socrata_bounded_sample_query_resolver"
SOCRATA_SAMPLE_LIMIT = 25
SOCRATA_DATASET_ID_RE = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$", re.IGNORECASE)


def socrata_bounded_sample_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
    *,
    first_text: FirstText,
    resource_mappings_from_entry: ResourceMappingsFromEntry,
    resource_url: ResourceUrl,
    resolver_id: str = SOCRATA_RESOLVER_ID,
    sample_limit: int = SOCRATA_SAMPLE_LIMIT,
) -> dict[str, object]:
    # Socrata/SODA 可能代表整張資料表；resolver 只產生有界小樣本，避免誤下載大表。
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    sample_url, source_format, source_url = socrata_sample_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
        sample_limit=sample_limit,
    )
    if not sample_url:
        return {}

    dataset_id = first_text(
        option_metadata.get("socrata_dataset_id"),
        socrata_dataset_id_from_url(source_url),
        socrata_dataset_id_from_url(sample_url),
        entry.get("dataset_id"),
        version_meta.get("dataset_id"),
        "socrata_dataset",
    )
    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), dataset_id)
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-socrata-sample" if version else "socrata-sample"
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
        data_type=str(option_metadata.get("data_family") or entry.get("data_type") or "table_sample"),
        native_format=source_format,
        geographic_scope=str(entry.get("geographic_scope") or ""),
        landing_url=first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
        api_url=sample_url,
        license_url=str(entry.get("license_url") or ""),
        version=sample_version,
        metadata={
            **option_metadata,
            "data_family": option_metadata.get("data_family") or entry.get("data_type") or "table_sample",
            "bounded_query": {
                "resolver_id": resolver_id,
                "source_url": source_url,
                "sample_limit": sample_limit,
                "socrata_dataset_id": dataset_id,
            },
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset_uid,
        dataset_id=dataset_id,
        label=f"Socrata bounded sample {source_format.upper()}",
        version=sample_version,
        status="resolved_sample",
        download_url=sample_url,
        landing_url=dataset.landing_url,
        update_strategy="sample_then_review",
        notes="Bounded Socrata/SODA sample generated from a resource endpoint; this downloads a small row sample only.",
        metadata={"native_format": source_format, "resolver_id": resolver_id, "socrata_dataset_id": dataset_id},
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason=f"The Socrata resource was resolved into a bounded sample request with $limit={sample_limit}.",
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
                "policy": "bounded_rows_sample_only",
                "sample_limit": sample_limit,
                "source_url": source_url,
                "socrata_dataset_id": dataset_id,
            },
        }
    )
    resolved.pop("adapter_review", None)
    resolved.pop("adapter_review_url", None)
    return resolved


def socrata_sample_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
    resource_mappings_from_entry: ResourceMappingsFromEntry,
    resource_url: ResourceUrl,
    sample_limit: int = SOCRATA_SAMPLE_LIMIT,
) -> tuple[str, str, str]:
    for raw_url in socrata_candidate_urls(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
    ):
        sample_url, source_format = bounded_socrata_url(raw_url, sample_limit=sample_limit)
        if sample_url:
            return sample_url, source_format, raw_url

    dataset_id = first_text(
        option_metadata.get("socrata_dataset_id"),
        option_metadata.get("soda_dataset_id"),
        option_metadata.get("dataset_identifier"),
        option_metadata.get("four_by_four_id"),
    )
    domain = first_text(option_metadata.get("socrata_domain"), option_metadata.get("soda_domain"))
    if SOCRATA_DATASET_ID_RE.match(dataset_id) and domain:
        generated = socrata_resource_url_from_domain(domain, dataset_id)
        if generated:
            sample_url, source_format = bounded_socrata_url(generated, sample_limit=sample_limit)
            if sample_url:
                return sample_url, source_format, generated
    return "", "", ""


def socrata_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
    resource_mappings_from_entry: ResourceMappingsFromEntry,
    resource_url: ResourceUrl,
) -> list[str]:
    candidates = [
        option_metadata.get("socrata_resource_url"),
        option_metadata.get("soda_resource_url"),
        option_metadata.get("api_url"),
        option_metadata.get("source_url"),
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


def socrata_resource_url_from_domain(domain: str, dataset_id: str) -> str:
    raw_domain = domain.strip()
    if not raw_domain:
        return ""
    parsed = urllib.parse.urlparse(raw_domain if urllib.parse.urlparse(raw_domain).scheme else f"https://{raw_domain}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse(parsed._replace(path=f"/resource/{dataset_id}.json", query="", fragment=""))


def bounded_socrata_url(raw_url: str, *, sample_limit: int = SOCRATA_SAMPLE_LIMIT) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", ""
    path = parsed.path.rstrip("/")
    dataset_id = socrata_dataset_id_from_url(raw_url)
    if not dataset_id:
        return "", ""
    lowered_path = path.lower()
    source_format = "json"
    if lowered_path.endswith(".csv"):
        source_format = "csv"
    elif lowered_path.endswith(".geojson"):
        source_format = "geojson"
    if "/api/views/" in lowered_path:
        source_format = "json"
    sample_path = f"/resource/{dataset_id}.{source_format}"
    query_pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() != "$limit"
    ]
    query_pairs.append(("$limit", str(sample_limit)))
    query = urllib.parse.urlencode(query_pairs, doseq=True, safe="$,:")
    return urllib.parse.urlunparse(parsed._replace(path=sample_path, query=query, fragment="")), source_format


def resource_is_socrata_api_url(url: str) -> bool:
    return bool(socrata_dataset_id_from_url(url))


def socrata_dataset_id_from_url(raw_url: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    segments = [urllib.parse.unquote(segment) for segment in parsed.path.split("/") if segment]
    for index, segment in enumerate(segments[:-1]):
        marker = segment.lower()
        if marker == "resource":
            dataset_id = strip_socrata_output_suffix(segments[index + 1])
            if SOCRATA_DATASET_ID_RE.match(dataset_id):
                return dataset_id
        if marker == "views" and index > 0 and segments[index - 1].lower() == "api":
            dataset_id = strip_socrata_output_suffix(segments[index + 1])
            if SOCRATA_DATASET_ID_RE.match(dataset_id):
                return dataset_id
    return ""


def strip_socrata_output_suffix(value: str) -> str:
    lowered = value.lower()
    for suffix in (".geojson", ".json", ".csv"):
        if lowered.endswith(suffix):
            return value[: -len(suffix)]
    return value
