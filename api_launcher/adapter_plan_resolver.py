from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.db import utc_now_iso
from api_launcher.downloads.eligibility import looks_like_direct_download
from api_launcher.downloads.plan_runner import plan_entries
from api_launcher.downloads.staging import safe_path_part
from api_launcher.models import Dataset
from api_launcher.plans import (
    assess_dataset_version_download,
    dataset_download_target_path,
    dataset_import_plan_entry,
)


RESOURCE_RESOLVER_ID = "generic_resource_direct_download_resolver"
ERDDAP_RESOLVER_ID = "erddap_bounded_sample_query_resolver"
ERDDAP_SAMPLE_LIMIT = 25
USER_AGENT = "APIkeys_collection/0.4 (+adapter-plan-resolver; metadata-only)"


@dataclass(frozen=True)
class AdapterPlanResolution:
    entry_count: int
    output_entry_count: int
    resolved_review_entries: int
    unresolved_review_entries: int
    direct_entries_added: int
    resolver_id: str = RESOURCE_RESOLVER_ID
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "resolver_id": self.resolver_id,
            "entry_count": self.entry_count,
            "output_entry_count": self.output_entry_count,
            "resolved_review_entries": self.resolved_review_entries,
            "unresolved_review_entries": self.unresolved_review_entries,
            "direct_entries_added": self.direct_entries_added,
            "warnings": list(self.warnings),
        }


def resolve_adapter_review_plan_payload(
    plan_payload: dict[str, Any],
    downloads_root: str | Path = "downloads",
    keep_original_review_entries: bool = False,
) -> tuple[dict[str, Any], AdapterPlanResolution]:
    entries = plan_entries(plan_payload)
    output_entries: list[dict[str, object]] = []
    resolved_review_entries = 0
    unresolved_review_entries = 0
    direct_entries_added = 0
    warnings: list[str] = []

    for index, entry in enumerate(entries, start=1):
        resolved_entries = direct_resource_entries_for_plan_entry(entry, index, downloads_root)
        if resolved_entries:
            resolved_review_entries += 1
            direct_entries_added += len(resolved_entries)
            if keep_original_review_entries:
                output_entries.append(entry)
            output_entries.extend(resolved_entries)
            continue

        output_entries.append(entry)
        if wants_source_resolution(entry):
            unresolved_review_entries += 1
            resource_count = len(resource_mappings_from_entry(entry))
            if resource_count:
                warnings.append(
                    f"entry #{index} provider={entry.get('provider_id') or '-'} "
                    f"dataset={entry.get('dataset_id') or '-'} resources={resource_count} "
                    "but no direct downloadable resource URL was found"
                )

    resolved_payload = dict(plan_payload)
    resolved_payload["providers"] = output_entries
    resolved_payload["summary"] = recompute_plan_summary(plan_payload, output_entries)
    resolution = AdapterPlanResolution(
        entry_count=len(entries),
        output_entry_count=len(output_entries),
        resolved_review_entries=resolved_review_entries,
        unresolved_review_entries=unresolved_review_entries,
        direct_entries_added=direct_entries_added,
        warnings=tuple(warnings),
    )
    resolved_payload["adapter_resolution"] = {
        **resolution.to_dict(),
        "resolved_at": utc_now_iso(),
        "policy": "replace_resolved_review_entries" if not keep_original_review_entries else "keep_original_review_entries",
    }
    return resolved_payload, resolution


def direct_resource_entries_for_plan_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path = "downloads",
) -> list[dict[str, object]]:
    if not wants_source_resolution(entry):
        return []
    resolved_entries: list[dict[str, object]] = []
    for resource_index, resource in enumerate(resource_mappings_from_entry(entry), start=1):
        url = resource_url(resource)
        if not url or not looks_like_direct_download(url):
            continue
        resolved = direct_resource_entry(entry, resource, plan_index, resource_index, url, downloads_root)
        if resolved:
            resolved_entries.append(resolved)
    erddap_entry = erddap_bounded_sample_entry(entry, plan_index, downloads_root)
    if erddap_entry:
        resolved_entries.append(erddap_entry)
    return resolved_entries


def wants_source_resolution(entry: dict[str, object]) -> bool:
    eligibility = entry.get("download_eligibility") if isinstance(entry.get("download_eligibility"), dict) else {}
    review = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
    action = str(review.get("required_action") or "").strip()
    status = str(eligibility.get("status") or "").strip()
    return action == "resolve_source_to_direct_download_entries" or status == "adapter_required"


def resource_mappings_from_entry(entry: dict[str, object]) -> list[dict[str, object]]:
    candidates: list[object] = []
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    nested_meta = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    candidates.extend(
        (
            nested_meta.get("resources"),
            nested_meta.get("links"),
            entry.get("resources"),
            entry.get("resource_summaries"),
            entry.get("links"),
        )
    )
    resources: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    for candidate in candidates:
        for item in resource_mappings_from_candidate(candidate):
            url = resource_url(item)
            if url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            resources.append(dict(item))
    return resources


def resource_mappings_from_candidate(candidate: object, group: str = "") -> list[dict[str, object]]:
    if isinstance(candidate, list):
        resources: list[dict[str, object]] = []
        for item in candidate:
            resources.extend(resource_mappings_from_candidate(item, group=group))
        return resources
    if not isinstance(candidate, dict):
        return []
    if resource_url(candidate):
        resource = dict(candidate)
        if group and not resource.get("group"):
            resource["group"] = group
        if group and not resource.get("name") and not resource.get("title"):
            resource["name"] = group
        return [resource]
    resources = []
    for key, value in candidate.items():
        if isinstance(value, (list, dict)):
            resources.extend(resource_mappings_from_candidate(value, group=str(key)))
    return resources


def resource_url(resource: dict[str, object]) -> str:
    return first_text(resource.get("download_url"), resource.get("url"), resource.get("href"))


def direct_resource_entry(
    entry: dict[str, object],
    resource: dict[str, object],
    plan_index: int,
    resource_index: int,
    url: str,
    downloads_root: str | Path,
) -> dict[str, object]:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    source_format = source_format_for_resource(resource, url, str(entry.get("source_format") or "unknown"))
    resource_name = first_text(resource.get("name"), resource.get("id"), resource.get("title"), resource.get("rel"), resource.get("group"), Path(urllib.parse.urlparse(url).path).name)
    base_version = first_text(version_meta.get("version"), entry.get("version"), "resolved")
    resource_part = safe_path_part(resource_name or f"resource_{resource_index}")
    version = f"{base_version}-{resource_part}" if base_version and resource_part else base_version or resource_part
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"))
    dataset_id = first_text(entry.get("dataset_id"), version_meta.get("dataset_id"), "dataset")
    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset = Dataset(
        dataset_uid=dataset_uid,
        provider_id=provider_id,
        dataset_id=dataset_id,
        title=first_text(entry.get("dataset_title"), entry.get("name"), dataset_id),
        categories=tuple(str(value) for value in entry.get("categories", ()) if str(value).strip()) if isinstance(entry.get("categories"), (list, tuple)) else (),
        data_type=str(option_metadata.get("data_family") or entry.get("data_type") or ""),
        native_format=source_format,
        geographic_scope=str(entry.get("geographic_scope") or ""),
        landing_url=first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
        api_url=url,
        license_url=str(entry.get("license_url") or ""),
        version=version,
        metadata={**option_metadata, "resolved_resource": resource, "data_family": option_metadata.get("data_family") or entry.get("data_type") or ""},
    )
    option = DatasetVersionOption(
        dataset_uid=dataset_uid,
        dataset_id=dataset_id,
        label=resource_name or first_text(version_meta.get("label"), dataset.title),
        version=version,
        status="resolved_resource",
        download_url=url,
        landing_url=dataset.landing_url,
        update_strategy=str(version_meta.get("update_strategy") or "full_replace_if_needed"),
        notes=f"Resolved from adapter_review plan entry #{plan_index}.",
        metadata={
            "native_format": source_format,
            "resource": resource,
            "resolved_from_plan_index": plan_index,
            "resolver_id": RESOURCE_RESOLVER_ID,
        },
    )
    eligibility = assess_dataset_version_download(option)
    if eligibility.status != "direct_download":
        return {}
    resolved = dict(entry)
    resolved.update(
        {
            "dataset_uid": dataset_uid,
            "dataset_id": dataset_id,
            "dataset_title": dataset.title,
            "dataset_version": option.to_plan_metadata(),
            "source_format": source_format or "unknown",
            "target": "local_file_asset",
            "use_staging": True,
            "download_eligibility": eligibility.to_dict(),
            "download_url": url,
            "target_path": dataset_download_target_path(provider_id, dataset, option, downloads_root).as_posix(),
            "import_plan": dataset_import_plan_entry(dataset, option, eligibility),
            "plan_status": "planned",
            "adapter_resolution": {
                "resolver_id": RESOURCE_RESOLVER_ID,
                "original_plan_index": plan_index,
                "resource_index": resource_index,
                "resource_name": resource_name,
                "resource_format": first_text(resource.get("format"), resource.get("mimetype"), resource.get("type")),
                "source_url": first_text(
                    (entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else "",
                    entry.get("adapter_review_url"),
                    version_meta.get("download_url"),
                ),
            },
        }
    )
    resolved.pop("adapter_review", None)
    resolved.pop("adapter_review_url", None)
    return resolved


def erddap_bounded_sample_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    protocols = option_metadata.get("erddap_protocols") if isinstance(option_metadata.get("erddap_protocols"), dict) else {}
    source_format = str(entry.get("source_format") or option_metadata.get("native_format") or "").strip().lower()
    if source_format != "erddap" and not protocols:
        return {}

    dataset_id = first_text(option_metadata.get("erddap_dataset_id"), entry.get("dataset_id"), version_meta.get("dataset_id"))
    protocol_name, protocol_url = erddap_protocol_url(entry, protocols, version_meta)
    if not dataset_id or not protocol_url or protocol_name not in {"tabledap", "griddap"}:
        return {}

    info_url = erddap_info_url(protocol_url, dataset_id)
    if not info_url:
        return {}
    try:
        info = fetch_json(info_url)
    except Exception:
        return {}
    dimensions, variables = erddap_info_dimensions_and_variables(info)
    sample_url = erddap_sample_csv_url(protocol_url, protocol_name, dimensions, variables)
    if not sample_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), dataset_id)
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-erddap-sample" if version else "erddap-sample"
    dataset = Dataset(
        dataset_uid=dataset_uid,
        provider_id=provider_id,
        dataset_id=dataset_id,
        title=first_text(entry.get("dataset_title"), entry.get("name"), dataset_id),
        categories=tuple(str(value) for value in entry.get("categories", ()) if str(value).strip()) if isinstance(entry.get("categories"), (list, tuple)) else (),
        data_type=str(option_metadata.get("data_family") or entry.get("data_type") or "table_or_grid_sample"),
        native_format="csv",
        geographic_scope=str(entry.get("geographic_scope") or ""),
        landing_url=first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
        api_url=sample_url,
        license_url=str(entry.get("license_url") or ""),
        version=sample_version,
        metadata={
            **option_metadata,
            "data_family": option_metadata.get("data_family") or entry.get("data_type") or "table_or_grid_sample",
            "bounded_query": {
                "resolver_id": ERDDAP_RESOLVER_ID,
                "protocol": protocol_name,
                "info_url": info_url,
                "sample_limit": ERDDAP_SAMPLE_LIMIT,
                "dimensions": dimensions,
                "variables": variables[:8],
            },
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset_uid,
        dataset_id=dataset_id,
        label="ERDDAP bounded sample CSV",
        version=sample_version,
        status="resolved_sample",
        download_url=sample_url,
        landing_url=dataset.landing_url,
        update_strategy="sample_then_review",
        notes="Bounded ERDDAP sample generated from allDatasets metadata and info/index.json.",
        metadata={"native_format": "csv", "resolver_id": ERDDAP_RESOLVER_ID, "protocol": protocol_name},
    )
    eligibility = assess_dataset_version_download(option)
    if eligibility.status != "direct_download":
        return {}
    resolved = dict(entry)
    resolved.update(
        {
            "dataset_uid": dataset_uid,
            "dataset_id": dataset_id,
            "dataset_title": dataset.title,
            "dataset_version": option.to_plan_metadata(),
            "source_format": "csv",
            "target": "local_file_asset",
            "use_staging": True,
            "download_eligibility": eligibility.to_dict(),
            "download_url": sample_url,
            "target_path": dataset_download_target_path(provider_id, dataset, option, downloads_root).as_posix(),
            "import_plan": dataset_import_plan_entry(dataset, option, eligibility),
            "plan_status": "planned",
            "adapter_resolution": {
                "resolver_id": ERDDAP_RESOLVER_ID,
                "original_plan_index": plan_index,
                "protocol": protocol_name,
                "info_url": info_url,
                "policy": "bounded_sample_only",
                "sample_limit": ERDDAP_SAMPLE_LIMIT,
            },
        }
    )
    resolved.pop("adapter_review", None)
    resolved.pop("adapter_review_url", None)
    return resolved


def erddap_protocol_url(
    entry: dict[str, object],
    protocols: dict[str, object],
    version_meta: dict[str, object],
) -> tuple[str, str]:
    for name in ("tabledap", "griddap"):
        raw_url = first_text(protocols.get(name))
        if raw_url:
            return name, absolute_erddap_url(raw_url, entry, version_meta)
    raw_download = first_text(version_meta.get("download_url"), entry.get("adapter_review_url"), entry.get("api_base_url"))
    lowered = raw_download.lower()
    if "/tabledap/" in lowered:
        return "tabledap", absolute_erddap_url(raw_download, entry, version_meta)
    if "/griddap/" in lowered:
        return "griddap", absolute_erddap_url(raw_download, entry, version_meta)
    return "", ""


def absolute_erddap_url(raw_url: str, entry: dict[str, object], version_meta: dict[str, object]) -> str:
    if urllib.parse.urlparse(raw_url).scheme:
        return raw_url
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    base_candidates = [
        first_text((entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else ""),
        first_text(option_metadata.get("source_url")),
        first_text(version_meta.get("landing_url"), entry.get("landing_url"), entry.get("api_base_url"), entry.get("docs_url")),
    ]
    for base in base_candidates:
        parsed = urllib.parse.urlparse(base)
        if parsed.scheme and parsed.netloc:
            if raw_url.startswith("/"):
                return f"{parsed.scheme}://{parsed.netloc}{raw_url}"
            return urllib.parse.urljoin(base, raw_url)
    return raw_url


def erddap_info_url(protocol_url: str, dataset_id: str) -> str:
    parsed = urllib.parse.urlparse(protocol_url)
    marker = "/erddap/"
    if not parsed.scheme or not parsed.netloc or marker not in parsed.path:
        return ""
    prefix = parsed.path.split(marker, 1)[0]
    root = f"{parsed.scheme}://{parsed.netloc}{prefix}/erddap"
    return f"{root}/info/{urllib.parse.quote(dataset_id, safe='')}/index.json"


def erddap_info_dimensions_and_variables(payload: dict[str, object]) -> tuple[list[str], list[str]]:
    table = payload.get("table") if isinstance(payload.get("table"), dict) else {}
    column_names = table.get("columnNames") if isinstance(table.get("columnNames"), list) else []
    rows = table.get("rows") if isinstance(table.get("rows"), list) else []
    columns = [str(value) for value in column_names]
    dimensions: list[str] = []
    variables: list[str] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        item = {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
        row_type = str(item.get("Row Type") or item.get("row_type") or "").strip().lower()
        variable_name = str(item.get("Variable Name") or item.get("variable_name") or "").strip()
        if not variable_name:
            continue
        if row_type == "dimension" and variable_name not in dimensions:
            dimensions.append(variable_name)
        elif row_type == "variable" and variable_name not in variables:
            variables.append(variable_name)
    return dimensions, variables


def erddap_sample_csv_url(protocol_url: str, protocol_name: str, dimensions: list[str], variables: list[str]) -> str:
    clean_url = protocol_url.rstrip("/")
    if protocol_name == "griddap":
        if not variables:
            return ""
        query = variables[0] + "".join("[0:1:0]" for _dimension in dimensions)
        return f"{clean_url}.csv?{urllib.parse.quote(query, safe=',[]:')}"
    selected = tabledap_sample_variables(dimensions, variables)
    if not selected:
        return ""
    query = urllib.parse.quote(",".join(selected), safe=",")
    return f"{clean_url}.csv?{query}&.limit={ERDDAP_SAMPLE_LIMIT}"


def tabledap_sample_variables(dimensions: list[str], variables: list[str]) -> list[str]:
    ordered: list[str] = []
    for preferred in ("time", "latitude", "longitude", "depth", "station", "station_id"):
        if preferred in dimensions and preferred not in ordered:
            ordered.append(preferred)
        if preferred in variables and preferred not in ordered:
            ordered.append(preferred)
    for name in [*dimensions, *variables]:
        if name not in ordered:
            ordered.append(name)
        if len(ordered) >= 6:
            break
    return ordered[:6]


def fetch_json(url: str, timeout: float = 12.0) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def source_format_for_resource(resource: dict[str, object], url: str, fallback: str = "unknown") -> str:
    hinted = normalize_resource_format(first_text(resource.get("format"), resource.get("mimetype"), resource.get("media_type"), resource.get("type")))
    inferred = source_format_from_url(url)
    if inferred in {"csv.gz", "csv.zst", "tar.gz", "zip", "zst", "gz", "xz", "bz2"}:
        return inferred
    if hinted != "unknown":
        return hinted
    if inferred != "unknown":
        return inferred
    return normalize_resource_format(fallback)


def normalize_resource_format(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return "unknown"
    normalized = normalized.replace("application/", "").replace("text/", "")
    normalized = normalized.replace("x-", "").replace(" ", "_")
    if "csv" in normalized and ("zst" in normalized or "zstandard" in normalized):
        return "csv.zst"
    if "csv" in normalized and "gz" in normalized:
        return "csv.gz"
    if "geojson" in normalized or "geo+json" in normalized:
        return "geojson"
    if "jsonl" in normalized or "ndjson" in normalized:
        return "jsonl"
    if "json" in normalized:
        return "json"
    if "parquet" in normalized:
        return "parquet"
    if "netcdf" in normalized or normalized in {"nc", "cdf"}:
        return "netcdf"
    if "zip" in normalized:
        return "zip"
    if "tar" in normalized and "gz" in normalized:
        return "tar.gz"
    if "zst" in normalized or "zstandard" in normalized:
        return "zst"
    return normalized or "unknown"


def source_format_from_url(url: str) -> str:
    suffixes = [suffix.lower().lstrip(".") for suffix in Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).suffixes]
    if not suffixes:
        return "unknown"
    if len(suffixes) >= 2 and suffixes[-2:] == ["csv", "gz"]:
        return "csv.gz"
    if len(suffixes) >= 2 and suffixes[-2:] == ["csv", "zst"]:
        return "csv.zst"
    if len(suffixes) >= 2 and suffixes[-2:] == ["tar", "gz"]:
        return "tar.gz"
    return suffixes[-1]


def recompute_plan_summary(plan_payload: dict[str, Any], entries: Iterable[dict[str, object]]) -> dict[str, object]:
    entry_list = list(entries)
    provider_ids = {str(entry.get("provider_id") or "") for entry in entry_list if entry.get("provider_id")}
    direct_count = 0
    for entry in entry_list:
        eligibility = entry.get("download_eligibility") if isinstance(entry.get("download_eligibility"), dict) else {}
        if eligibility.get("status") == "direct_download":
            direct_count += 1
    old_summary = plan_payload.get("summary") if isinstance(plan_payload.get("summary"), dict) else {}
    return {
        **old_summary,
        "provider_count": len(provider_ids),
        "dataset_version_count": len(entry_list),
        "direct_download_count": direct_count,
        "review_required_count": len(entry_list) - direct_count,
        "status": "planned",
    }


def first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""
