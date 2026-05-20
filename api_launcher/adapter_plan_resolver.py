from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from api_launcher.crawlers.datacite import datacite_content_url_resources, datacite_content_urls
from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.db import utc_now_iso
from api_launcher.downloads.eligibility import DownloadEligibility, looks_like_direct_download
from api_launcher.downloads.plan_runner import plan_entries
from api_launcher.downloads.staging import safe_path_part
from api_launcher.models import Dataset
from api_launcher.plans import (
    assess_dataset_version_download,
    dataset_download_target_path,
    dataset_import_plan_entry,
)


RESOURCE_RESOLVER_ID = "generic_resource_direct_download_resolver"
CKAN_PACKAGE_RESOLVER_ID = "ckan_package_show_resource_resolver"
ERDDAP_RESOLVER_ID = "erddap_bounded_sample_query_resolver"
STAC_RESOLVER_ID = "stac_bounded_item_search_resolver"
CMR_GRANULE_RESOLVER_ID = "cmr_bounded_granule_search_resolver"
CMR_GRANULE_ASSET_RESOLVER_ID = "cmr_granule_asset_link_resolver"
SOCRATA_RESOLVER_ID = "socrata_bounded_sample_query_resolver"
NCEI_SEARCH_DATA_FILE_RESOLVER_ID = "ncei_search_data_file_resolver"
NCEI_SEARCH_RESOLVER_ID = "ncei_bounded_search_query_resolver"
NCEI_ACCESS_DATA_RESOLVER_ID = "ncei_bounded_access_data_query_resolver"
DATACITE_DOI_CONTENT_URL_RESOLVER_ID = "datacite_doi_content_url_resolver"
DATAVERSE_FILE_RESOLVER_ID = "dataverse_latest_version_file_resolver"
ERDDAP_SAMPLE_LIMIT = 25
STAC_ITEM_SAMPLE_LIMIT = 1
CMR_GRANULE_SAMPLE_LIMIT = 1
CMR_GRANULE_ASSET_MAX_LINKS = 5
SOCRATA_SAMPLE_LIMIT = 25
NCEI_DATA_FILE_LOOKUP_LIMIT = 1
NCEI_SEARCH_SAMPLE_LIMIT = 25
NCEI_ACCESS_DATA_MAX_DAYS = 7
DATACITE_MAX_CONTENT_URLS = 5
DATAVERSE_MAX_FILES = 5
DIRECT_RESOURCE_MAX_BYTES = 100 * 1024 * 1024
DIRECT_RESOURCE_FORMATS = {
    "csv",
    "csv.gz",
    "geojson",
    "json",
    "jsonl",
    "grb",
    "grib",
    "hdf",
    "hdf5",
    "netcdf",
    "parquet",
    "tif",
    "tiff",
    "zip",
    "tar.gz",
}
USER_AGENT = "APIkeys_collection/0.4 (+adapter-plan-resolver; metadata-only)"
SOCRATA_DATASET_ID_RE = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$", re.IGNORECASE)


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
            resources = resource_mappings_from_entry(entry)
            resource_count = len(resources)
            oversized_count = sum(1 for resource in resources if resource_exceeds_size_bound(resource))
            if oversized_count:
                warnings.append(
                    f"entry #{index} provider={entry.get('provider_id') or '-'} "
                    f"dataset={entry.get('dataset_id') or '-'} oversized_resources={oversized_count} "
                    f"exceeded the bounded resolver limit of {DIRECT_RESOURCE_MAX_BYTES} bytes"
                )
                continue
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
    stac_entry = stac_bounded_item_search_entry(entry, plan_index, downloads_root)
    if stac_entry:
        resolved_entries.append(stac_entry)
    cmr_entry = cmr_bounded_granule_search_entry(entry, plan_index, downloads_root)
    if cmr_entry:
        resolved_entries.append(cmr_entry)
    resources = resource_mappings_from_entry(entry)
    for resource_index, resource in enumerate(resources, start=1):
        url = resource_url(resource)
        if not url or not resource_looks_downloadable(resource, url):
            continue
        if entry_is_stac_collection(entry) and resource_is_stac_items_link(resource, url):
            continue
        if resource_is_ogc_records_metadata_link(entry, resource):
            continue
        if resource_is_cmr_metadata_link(entry, resource, url):
            continue
        if resource_is_socrata_api_url(url):
            continue
        if resource_is_ncei_access_data_url(url):
            continue
        if resource_exceeds_size_bound(resource):
            continue
        resolved = direct_resource_entry(entry, resource, plan_index, resource_index, url, downloads_root)
        if resolved:
            resolved_entries.append(resolved)
    if not resolved_entries:
        socrata_entry = socrata_bounded_sample_entry(entry, plan_index, downloads_root)
        if socrata_entry:
            resolved_entries.append(socrata_entry)
    if not resolved_entries and not resources:
        resolved_entries.extend(ncei_search_data_file_entries(entry, plan_index, downloads_root))
    if not resolved_entries:
        ncei_entry = ncei_bounded_search_entry(entry, plan_index, downloads_root)
        if ncei_entry:
            resolved_entries.append(ncei_entry)
    if not resolved_entries:
        ncei_access_entry = ncei_bounded_access_data_entry(entry, plan_index, downloads_root)
        if ncei_access_entry:
            resolved_entries.append(ncei_access_entry)
    if not resolved_entries and not resources:
        resolved_entries.extend(cmr_granule_asset_link_entries(entry, plan_index, downloads_root))
    if not resolved_entries and not resources:
        resolved_entries.extend(ckan_package_show_resource_entries(entry, plan_index, downloads_root))
    if not resolved_entries and not resources:
        resolved_entries.extend(datacite_doi_content_url_entries(entry, plan_index, downloads_root))
    if not resolved_entries and not resources:
        resolved_entries.extend(dataverse_latest_version_file_entries(entry, plan_index, downloads_root))
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
            nested_meta.get("distribution"),
            nested_meta.get("distributions"),
            nested_meta.get("dcat:distribution"),
            nested_meta.get("http://www.w3.org/ns/dcat#distribution"),
            nested_meta.get("https://www.w3.org/ns/dcat#distribution"),
            nested_meta.get("@graph"),
            nested_meta.get("links"),
            entry.get("resources"),
            entry.get("distribution"),
            entry.get("distributions"),
            entry.get("dcat:distribution"),
            entry.get("http://www.w3.org/ns/dcat#distribution"),
            entry.get("https://www.w3.org/ns/dcat#distribution"),
            entry.get("@graph"),
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
    return first_resource_url_text(
        resource.get("download_url"),
        resource.get("downloadURL"),
        resource.get("downloadUrl"),
        resource.get("downloadURI"),
        resource.get("downloadUri"),
        resource.get("dcat:downloadURL"),
        resource.get("dcat:downloadUrl"),
        resource.get("dcat:downloadURI"),
        resource.get("http://www.w3.org/ns/dcat#downloadURL"),
        resource.get("https://www.w3.org/ns/dcat#downloadURL"),
        resource.get("contentUrl"),
        resource.get("contentURL"),
        resource.get("content_url"),
        resource.get("schema:contentUrl"),
        resource.get("schema:contentURL"),
        resource.get("http://schema.org/contentUrl"),
        resource.get("https://schema.org/contentUrl"),
        resource.get("fileUrl"),
        resource.get("fileURL"),
        resource.get("url"),
        resource.get("href"),
    )


def first_resource_url_text(*values: object) -> str:
    for value in values:
        text = resource_url_text(value)
        if text:
            return text
    return ""


def resource_url_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return first_resource_url_text(*value)
    if isinstance(value, dict):
        return first_resource_url_text(
            value.get("@id"),
            value.get("id"),
            value.get("@value"),
            value.get("value"),
            value.get("url"),
            value.get("href"),
        )
    return str(value or "").strip()


def first_resource_text(*values: object) -> str:
    for value in values:
        text = resource_text(value)
        if text:
            return text
    return ""


def resource_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return first_resource_text(*value)
    if isinstance(value, dict):
        return first_resource_text(
            value.get("@id"),
            value.get("id"),
            value.get("@value"),
            value.get("value"),
            value.get("url"),
            value.get("href"),
            value.get("name"),
            value.get("label"),
        )
    return str(value or "").strip()


def direct_resource_entry(
    entry: dict[str, object],
    resource: dict[str, object],
    plan_index: int,
    resource_index: int,
    url: str,
    downloads_root: str | Path,
    resolver_id: str = RESOURCE_RESOLVER_ID,
    resolver_source_url: str = "",
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
            "resolver_id": resolver_id,
        },
    )
    eligibility = assess_dataset_version_download(option)
    if eligibility.status != "direct_download":
        if not resource_looks_downloadable(resource, url):
            return {}
        eligibility = DownloadEligibility(
            status="direct_download",
            label="Direct",
            reason="The resource metadata declares a supported direct file format even though the URL path has no file extension.",
            direct_url=url,
        )
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
                "resolver_id": resolver_id,
                "original_plan_index": plan_index,
                "resource_index": resource_index,
                "resource_name": resource_name,
                "resource_format": first_resource_text(
                    resource.get("format"),
                    resource.get("dct:format"),
                    resource.get("dc:format"),
                    resource.get("http://purl.org/dc/terms/format"),
                    resource.get("http://purl.org/dc/elements/1.1/format"),
                    resource.get("mimetype"),
                    resource.get("mimeType"),
                    resource.get("media_type"),
                    resource.get("mediaType"),
                    resource.get("dcat:mediaType"),
                    resource.get("http://www.w3.org/ns/dcat#mediaType"),
                    resource.get("https://www.w3.org/ns/dcat#mediaType"),
                    resource.get("content_type"),
                    resource.get("contentType"),
                    resource.get("encodingFormat"),
                    resource.get("schema:encodingFormat"),
                    resource.get("http://schema.org/encodingFormat"),
                    resource.get("https://schema.org/encodingFormat"),
                    resource.get("type"),
                ),
                "resource_size_bytes": resource_size_bytes(resource),
                "max_resource_size_bytes": DIRECT_RESOURCE_MAX_BYTES,
                "source_url": first_text(
                    resolver_source_url,
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


def ckan_package_show_resource_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    package_url = ckan_package_show_url(entry)
    if not package_url:
        return []
    try:
        payload = fetch_json(package_url)
    except Exception:
        return []
    resources = ckan_package_show_resources(payload)
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
            resolver_id=CKAN_PACKAGE_RESOLVER_ID,
            resolver_source_url=package_url,
        )
        if resolved:
            resolved_entries.append(resolved)
    return resolved_entries


def ckan_package_show_url(entry: dict[str, object]) -> str:
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


def ckan_package_show_resources(payload: dict[str, object]) -> list[dict[str, object]]:
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


def datacite_doi_content_url_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    lookup_url = datacite_doi_content_url_lookup_url(entry)
    if not lookup_url:
        return []
    try:
        payload = fetch_json(lookup_url)
    except Exception:
        return []

    resources = datacite_doi_content_url_resources(payload, lookup_url)
    resolved_entries: list[dict[str, object]] = []
    for resource_index, resource in enumerate(resources[:DATACITE_MAX_CONTENT_URLS], start=1):
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
            resolver_id=DATACITE_DOI_CONTENT_URL_RESOLVER_ID,
            resolver_source_url=lookup_url,
        )
        if resolved:
            resolved["adapter_resolution"] = {
                **resolved["adapter_resolution"],
                "policy": "single_datacite_doi_metadata_content_url_lookup",
                "lookup_url": lookup_url,
                "max_content_urls": DATACITE_MAX_CONTENT_URLS,
            }
            resolved_entries.append(resolved)
    return resolved_entries


def datacite_doi_content_url_lookup_url(entry: dict[str, object]) -> str:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    if not entry_is_doi_metadata_candidate(entry, option_metadata):
        return ""
    doi = doi_identifier_from_entry(entry, version_meta, option_metadata)
    if not doi:
        return ""
    for raw_url in datacite_doi_candidate_urls(entry, version_meta, option_metadata):
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


def dataverse_latest_version_file_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    latest_url = dataverse_latest_version_url(entry)
    if not latest_url:
        return []
    try:
        payload = fetch_json(latest_url)
    except Exception:
        return []
    resources = dataverse_file_resources(payload, latest_url)
    resolved_entries: list[dict[str, object]] = []
    for resource_index, resource in enumerate(resources[:DATAVERSE_MAX_FILES], start=1):
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
            resolver_id=DATAVERSE_FILE_RESOLVER_ID,
            resolver_source_url=latest_url,
        )
        if resolved:
            resolved["adapter_resolution"] = {
                **resolved["adapter_resolution"],
                "policy": "latest_version_files_under_size_limit",
                "max_files": DATAVERSE_MAX_FILES,
            }
            resolved_entries.append(resolved)
    return resolved_entries


def dataverse_latest_version_url(entry: dict[str, object]) -> str:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    if not entry_is_dataverse_candidate(entry, option_metadata):
        return ""
    persistent_id = dataverse_persistent_id(option_metadata)
    if not persistent_id:
        return ""
    base_url = dataverse_base_url(entry, version_meta, option_metadata)
    if not base_url:
        return ""
    query = urllib.parse.urlencode({"persistentId": persistent_id})
    return f"{base_url}/api/datasets/:persistentId/versions/:latest?{query}"


def entry_is_dataverse_candidate(entry: dict[str, object], option_metadata: dict[str, object]) -> bool:
    markers = {
        str(entry.get("provider_id") or "").strip().lower(),
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("data_type") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
        str(option_metadata.get("source_type") or "").strip().lower(),
    }
    return any("dataverse" in marker for marker in markers) and bool(dataverse_persistent_id(option_metadata))


def dataverse_persistent_id(option_metadata: dict[str, object]) -> str:
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


def dataverse_file_resources(payload: dict[str, object], latest_url: str) -> list[dict[str, object]]:
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
                "format": dataverse_file_format(filename, content_type),
                "mimetype": content_type,
                "url": dataverse_datafile_access_url(latest_url, file_id),
                "size": first_text(data_file.get("filesize"), data_file.get("size"), item.get("filesize"), item.get("size")),
                "checksum": dataverse_file_checksum(data_file),
                "persistent_id": first_text(data_file.get("persistentId"), item.get("persistentId")),
            }
        )
    return resources


def dataverse_datafile_access_url(latest_url: str, file_id: str) -> str:
    parsed = urllib.parse.urlparse(latest_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse(parsed._replace(path=f"/api/access/datafile/{urllib.parse.quote(file_id, safe='')}", query="", fragment=""))


def dataverse_file_format(filename: str, content_type: str) -> str:
    from_name = source_format_from_url(filename)
    if from_name != "unknown":
        return from_name
    return normalize_resource_format(content_type)


def dataverse_file_checksum(data_file: dict[str, object]) -> str:
    checksum = data_file.get("checksum")
    if isinstance(checksum, dict):
        checksum_type = first_text(checksum.get("type"))
        checksum_value = first_text(checksum.get("value"))
        if checksum_type and checksum_value:
            return f"{checksum_type}:{checksum_value}"
        return checksum_value or checksum_type
    return first_text(checksum, data_file.get("md5"))


def socrata_bounded_sample_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    sample_url, source_format, source_url = socrata_sample_url(entry, version_meta, option_metadata)
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
        categories=tuple(str(value) for value in entry.get("categories", ()) if str(value).strip()) if isinstance(entry.get("categories"), (list, tuple)) else (),
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
                "resolver_id": SOCRATA_RESOLVER_ID,
                "source_url": source_url,
                "sample_limit": SOCRATA_SAMPLE_LIMIT,
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
        metadata={"native_format": source_format, "resolver_id": SOCRATA_RESOLVER_ID, "socrata_dataset_id": dataset_id},
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason=f"The Socrata resource was resolved into a bounded sample request with $limit={SOCRATA_SAMPLE_LIMIT}.",
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
                "resolver_id": SOCRATA_RESOLVER_ID,
                "original_plan_index": plan_index,
                "sample_url": sample_url,
                "policy": "bounded_rows_sample_only",
                "sample_limit": SOCRATA_SAMPLE_LIMIT,
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
) -> tuple[str, str, str]:
    for raw_url in socrata_candidate_urls(entry, version_meta, option_metadata):
        sample_url, source_format = bounded_socrata_url(raw_url)
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
            sample_url, source_format = bounded_socrata_url(generated)
            if sample_url:
                return sample_url, source_format, generated
    return "", "", ""


def socrata_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
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


def bounded_socrata_url(raw_url: str) -> tuple[str, str]:
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
    query_pairs.append(("$limit", str(SOCRATA_SAMPLE_LIMIT)))
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


def ncei_search_data_file_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    lookup_url = ncei_search_data_file_lookup_url(entry, version_meta, option_metadata)
    if not lookup_url:
        return []
    try:
        payload = fetch_json(lookup_url)
    except Exception:
        return []

    resolved_entries: list[dict[str, object]] = []
    resources = ncei_search_data_file_resources(payload, lookup_url)
    for resource_index, resource in enumerate(resources[:NCEI_DATA_FILE_LOOKUP_LIMIT], start=1):
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
            resolver_id=NCEI_SEARCH_DATA_FILE_RESOLVER_ID,
            resolver_source_url=lookup_url,
        )
        if resolved:
            resolved["adapter_resolution"] = {
                **resolved["adapter_resolution"],
                "policy": "single_bounded_ncei_search_data_file_under_size_limit",
                "lookup_url": lookup_url,
                "lookup_limit": NCEI_DATA_FILE_LOOKUP_LIMIT,
            }
            resolved_entries.append(resolved)
    return resolved_entries


def ncei_search_data_file_lookup_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> str:
    if not entry_is_ncei_search_candidate(entry, option_metadata):
        return ""
    ncei_dataset_id = first_text(
        option_metadata.get("ncei_result_id"),
        option_metadata.get("ncei_dataset_id"),
        entry.get("dataset_id"),
        version_meta.get("dataset_id"),
    )
    for raw_url in ncei_candidate_urls(entry, version_meta, option_metadata):
        lookup_url = bounded_ncei_search_data_file_lookup_url(raw_url, ncei_dataset_id)
        if lookup_url:
            return lookup_url
    return ""


def bounded_ncei_search_data_file_lookup_url(raw_url: str, ncei_dataset_id: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/").lower()
    if "/access/services/search/v1/" not in path or not path.endswith("/data"):
        return ""
    query = ncei_data_file_lookup_query(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True), ncei_dataset_id)
    if not query:
        return ""
    return urllib.parse.urlunparse(parsed._replace(query=query, fragment=""))


def ncei_data_file_lookup_query(query: list[tuple[str, str]], ncei_dataset_id: str) -> str:
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
    bounds = ncei_search_data_file_bounds(filtered)
    if not ncei_search_data_file_lookup_is_bounded(bounds):
        return ""
    filtered = [(key, value) for key, value in filtered if key.lower() not in {"limit", "offset"}]
    filtered.append(("limit", str(NCEI_DATA_FILE_LOOKUP_LIMIT)))
    filtered.append(("offset", "0"))
    return urllib.parse.urlencode(filtered, doseq=True, safe=",:")


def ncei_search_data_file_bounds(query: list[tuple[str, str]]) -> dict[str, object]:
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


def ncei_search_data_file_resources(payload: dict[str, object], lookup_url: str) -> list[dict[str, object]]:
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    resources: list[dict[str, object]] = []
    for item in results[:NCEI_DATA_FILE_LOOKUP_LIMIT]:
        if not isinstance(item, dict):
            continue
        resource = ncei_search_data_file_resource(item, lookup_url)
        if resource:
            resources.append(resource)
    return resources


def ncei_search_data_file_resource(item: dict[str, object], lookup_url: str) -> dict[str, object]:
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


def ncei_bounded_search_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    sample_url, source_url, endpoint_kind, ncei_dataset_id = ncei_bounded_search_url(entry, version_meta, option_metadata)
    if not sample_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset_id = first_text(entry.get("dataset_id"), version_meta.get("dataset_id"), ncei_dataset_id, "ncei_dataset")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), dataset_id)
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-ncei-search-sample" if version else "ncei-search-sample"
    dataset = Dataset(
        dataset_uid=dataset_uid,
        provider_id=provider_id,
        dataset_id=dataset_id,
        title=first_text(entry.get("dataset_title"), entry.get("name"), dataset_id),
        categories=tuple(str(value) for value in entry.get("categories", ()) if str(value).strip()) if isinstance(entry.get("categories"), (list, tuple)) else (),
        data_type=str(option_metadata.get("data_family") or entry.get("data_type") or "metadata_sample"),
        native_format="json",
        geographic_scope=str(entry.get("geographic_scope") or ""),
        landing_url=first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
        api_url=sample_url,
        license_url=str(entry.get("license_url") or ""),
        version=sample_version,
        metadata={
            **option_metadata,
            "data_family": option_metadata.get("data_family") or entry.get("data_type") or "metadata_sample",
            "bounded_query": {
                "resolver_id": NCEI_SEARCH_RESOLVER_ID,
                "source_url": source_url,
                "endpoint_kind": endpoint_kind,
                "sample_limit": NCEI_SEARCH_SAMPLE_LIMIT,
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
        metadata={"native_format": "json", "resolver_id": NCEI_SEARCH_RESOLVER_ID, "ncei_dataset_id": ncei_dataset_id},
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason=f"The NOAA/NCEI Search API request was bounded to {NCEI_SEARCH_SAMPLE_LIMIT} JSON metadata records.",
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
                "resolver_id": NCEI_SEARCH_RESOLVER_ID,
                "original_plan_index": plan_index,
                "sample_url": sample_url,
                "policy": "bounded_search_metadata_sample_only",
                "sample_limit": NCEI_SEARCH_SAMPLE_LIMIT,
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
) -> tuple[str, str, str, str]:
    if not entry_is_ncei_search_candidate(entry, option_metadata):
        return "", "", "", ""
    ncei_dataset_id = first_text(
        option_metadata.get("ncei_result_id"),
        option_metadata.get("ncei_dataset_id"),
        entry.get("dataset_id"),
        version_meta.get("dataset_id"),
    )
    for raw_url in ncei_candidate_urls(entry, version_meta, option_metadata):
        sample_url, endpoint_kind = bounded_ncei_search_url(raw_url, ncei_dataset_id)
        if sample_url:
            return sample_url, raw_url, endpoint_kind, ncei_dataset_id
    endpoint_url = first_text(option_metadata.get("ncei_search_endpoint_url"), option_metadata.get("source_endpoint_url"))
    if endpoint_url:
        sample_url, endpoint_kind = bounded_ncei_search_url(endpoint_url, ncei_dataset_id)
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


def bounded_ncei_search_url(raw_url: str, ncei_dataset_id: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", ""
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    if "/access/services/search/v1/" not in lower_path:
        return "", ""
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if lower_path.endswith("/data"):
        sample_query = ncei_limited_query(query, require_dataset=True, dataset_id=ncei_dataset_id)
        if not sample_query:
            return "", ""
        return urllib.parse.urlunparse(parsed._replace(query=sample_query, fragment="")), "data"
    if lower_path.endswith("/datasets"):
        data_endpoint = ncei_search_sibling_endpoint(parsed, "data")
        if ncei_dataset_id:
            sample_query = ncei_limited_query(query, require_dataset=True, dataset_id=ncei_dataset_id, for_data_endpoint=True)
            if sample_query:
                return urllib.parse.urlunparse(data_endpoint._replace(query=sample_query, fragment="")), "data"
        sample_query = ncei_limited_query(query, require_dataset=False, dataset_id="", for_data_endpoint=False)
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
    filtered.append(("limit", str(NCEI_SEARCH_SAMPLE_LIMIT)))
    filtered.append(("offset", "0"))
    return urllib.parse.urlencode(filtered, doseq=True, safe=",:")


def ncei_bounded_access_data_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    sample_url, source_format, source_url, bounds = ncei_bounded_access_data_url(entry, version_meta, option_metadata)
    if not sample_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    ncei_dataset_id = first_text(bounds.get("dataset"), option_metadata.get("ncei_dataset_id"), option_metadata.get("ncei_result_id"))
    dataset_id = first_text(entry.get("dataset_id"), version_meta.get("dataset_id"), ncei_dataset_id, "ncei_access_data")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), dataset_id)
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-ncei-access-sample" if version else "ncei-access-sample"
    dataset = Dataset(
        dataset_uid=dataset_uid,
        provider_id=provider_id,
        dataset_id=dataset_id,
        title=first_text(entry.get("dataset_title"), entry.get("name"), dataset_id),
        categories=tuple(str(value) for value in entry.get("categories", ()) if str(value).strip()) if isinstance(entry.get("categories"), (list, tuple)) else (),
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
                "resolver_id": NCEI_ACCESS_DATA_RESOLVER_ID,
                "source_url": source_url,
                "source_format": source_format,
                "max_days": NCEI_ACCESS_DATA_MAX_DAYS,
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
            "resolver_id": NCEI_ACCESS_DATA_RESOLVER_ID,
            "ncei_dataset_id": ncei_dataset_id,
            "bounds": bounds,
        },
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason=(
            "The NOAA/NCEI Access Data request already includes dataset, spatial selector, "
            f"and a date range no longer than {NCEI_ACCESS_DATA_MAX_DAYS} days."
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
                "resolver_id": NCEI_ACCESS_DATA_RESOLVER_ID,
                "original_plan_index": plan_index,
                "sample_url": sample_url,
                "policy": "bounded_access_data_query_only",
                "source_url": source_url,
                "source_format": source_format,
                "max_days": NCEI_ACCESS_DATA_MAX_DAYS,
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
) -> tuple[str, str, str, dict[str, object]]:
    for raw_url in ncei_access_data_candidate_urls(entry, version_meta, option_metadata):
        sample_url, source_format, bounds = bounded_ncei_access_data_url(raw_url)
        if sample_url:
            return sample_url, source_format, raw_url, bounds
    return "", "", "", {}


def ncei_access_data_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
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


def bounded_ncei_access_data_url(raw_url: str) -> tuple[str, str, dict[str, object]]:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", "", {}
    if not resource_is_ncei_access_data_url(raw_url):
        return "", "", {}

    query = canonical_ncei_access_data_query(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    if not query:
        return "", "", {}
    bounds = ncei_access_data_bounds(query)
    if not ncei_access_data_is_safely_bounded(bounds):
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


def ncei_access_data_bounds(query: list[tuple[str, str]]) -> dict[str, object]:
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


def ncei_access_data_is_safely_bounded(bounds: dict[str, object]) -> bool:
    days = bounds.get("days")
    return bool(
        bounds.get("dataset")
        and bounds.get("startDate")
        and bounds.get("endDate")
        and isinstance(days, int)
        and 0 <= days <= NCEI_ACCESS_DATA_MAX_DAYS
        and bounds.get("spatial_keys")
    )


def cmr_bounded_granule_search_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    sample_url, source_url, concept_id = cmr_bounded_granule_search_url(entry, version_meta, option_metadata)
    if not sample_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), concept_id)
    dataset_id = first_text(entry.get("dataset_id"), version_meta.get("dataset_id"), concept_id, "cmr_collection")
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-cmr-granules-sample" if version else "cmr-granules-sample"
    data_family = str(option_metadata.get("data_family") or entry.get("data_type") or "raster_or_grid")
    dataset = Dataset(
        dataset_uid=dataset_uid,
        provider_id=provider_id,
        dataset_id=dataset_id,
        title=first_text(entry.get("dataset_title"), entry.get("name"), dataset_id),
        categories=tuple(str(value) for value in entry.get("categories", ()) if str(value).strip()) if isinstance(entry.get("categories"), (list, tuple)) else (),
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
                "resolver_id": CMR_GRANULE_RESOLVER_ID,
                "source_url": source_url,
                "sample_limit": CMR_GRANULE_SAMPLE_LIMIT,
                "cmr_concept_id": concept_id,
            },
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset_uid,
        dataset_id=dataset_id,
        label="CMR bounded granule metadata sample JSON",
        version=sample_version,
        status="resolved_sample",
        download_url=sample_url,
        landing_url=dataset.landing_url,
        update_strategy="sample_then_review",
        notes="Bounded NASA CMR granule metadata sample generated from collection metadata; this downloads metadata only, not science data assets.",
        metadata={"native_format": "json", "resolver_id": CMR_GRANULE_RESOLVER_ID, "cmr_concept_id": concept_id},
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason=f"The NASA CMR collection was resolved into a bounded granule metadata request with page_size={CMR_GRANULE_SAMPLE_LIMIT}.",
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
                "resolver_id": CMR_GRANULE_RESOLVER_ID,
                "original_plan_index": plan_index,
                "sample_url": sample_url,
                "policy": "bounded_granule_metadata_sample_only",
                "sample_limit": CMR_GRANULE_SAMPLE_LIMIT,
                "source_url": source_url,
                "cmr_concept_id": concept_id,
            },
        }
    )
    resolved.pop("adapter_review", None)
    resolved.pop("adapter_review_url", None)
    return resolved


def cmr_bounded_granule_search_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> tuple[str, str, str]:
    if not entry_is_cmr_collection(entry, option_metadata):
        return "", "", ""
    concept_id = first_text(
        option_metadata.get("cmr_concept_id"),
        option_metadata.get("collection_concept_id"),
        option_metadata.get("concept_id"),
    )
    if not concept_id:
        return "", "", ""
    for raw_url in cmr_candidate_urls(entry, version_meta, option_metadata):
        sample_url = bounded_cmr_granules_url(raw_url, concept_id)
        if sample_url:
            return sample_url, raw_url, concept_id
    return "", "", ""


def entry_is_cmr_collection(entry: dict[str, object], option_metadata: dict[str, object]) -> bool:
    markers = {
        str(entry.get("provider_id") or "").strip().lower(),
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("data_type") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
        str(option_metadata.get("source_type") or "").strip().lower(),
    }
    if {"cmr_collection", "cmr_collections"} & markers:
        return True
    return any("cmr" in marker for marker in markers) and bool(
        option_metadata.get("cmr_concept_id")
        or option_metadata.get("collection_concept_id")
        or option_metadata.get("concept_id")
    )


def cmr_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> list[str]:
    candidates = [
        option_metadata.get("cmr_granules_url"),
        option_metadata.get("api_url"),
        version_meta.get("download_url"),
        (entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else "",
        entry.get("adapter_review_url"),
        entry.get("api_base_url"),
        option_metadata.get("source_url"),
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


def bounded_cmr_granules_url(raw_url: str, concept_id: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    if lower_path.endswith("/search/collections.json"):
        path = f"{path.rsplit('/', 1)[0]}/granules.json"
    elif lower_path.endswith("/search/collections"):
        path = f"{path.rsplit('/', 1)[0]}/granules.json"
    elif lower_path.endswith("/search/granules"):
        path = f"{path}.json"
    elif not lower_path.endswith("/search/granules.json"):
        return ""

    query_pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in {"page_size", "page_num", "offset"}
    ]
    keys = {key.lower() for key, _value in query_pairs}
    if "collection_concept_id" not in keys:
        query_pairs.insert(0, ("collection_concept_id", concept_id))
    query_pairs.append(("page_size", str(CMR_GRANULE_SAMPLE_LIMIT)))
    query = urllib.parse.urlencode(query_pairs, doseq=True, safe=",")
    return urllib.parse.urlunparse(parsed._replace(path=path, query=query, fragment=""))


def cmr_granule_asset_link_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    lookup_url = cmr_granule_asset_lookup_url(entry)
    if not lookup_url:
        return []
    try:
        payload = fetch_json(lookup_url)
    except Exception:
        return []
    resources = cmr_granule_asset_resources(payload)
    resolved_entries: list[dict[str, object]] = []
    for resource_index, resource in enumerate(resources[:CMR_GRANULE_ASSET_MAX_LINKS], start=1):
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
            resolver_id=CMR_GRANULE_ASSET_RESOLVER_ID,
            resolver_source_url=lookup_url,
        )
        if resolved:
            resolved["adapter_resolution"] = {
                **resolved["adapter_resolution"],
                "policy": "explicit_cmr_granule_data_links_under_size_limit",
                "lookup_url": lookup_url,
                "max_asset_links": CMR_GRANULE_ASSET_MAX_LINKS,
            }
            resolved_entries.append(resolved)
    return resolved_entries


def cmr_granule_asset_lookup_url(entry: dict[str, object]) -> str:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    if not entry_is_cmr_granule(entry, option_metadata):
        return ""
    for raw_url in cmr_granule_asset_candidate_urls(entry, version_meta, option_metadata):
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


def cmr_granule_asset_resources(payload: dict[str, object]) -> list[dict[str, object]]:
    resources: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for record in cmr_granule_records(payload):
        for resource in cmr_link_resources(record):
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


def cmr_link_resources(record: dict[str, object]) -> list[dict[str, object]]:
    resources: list[dict[str, object]] = []
    links = record.get("links") if isinstance(record.get("links"), list) else []
    for link in links:
        if isinstance(link, dict):
            resources.append(cmr_feed_link_resource(link))
    return [resource for resource in resources if resource_url(resource)]


def cmr_feed_link_resource(link: dict[str, object]) -> dict[str, object]:
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


def parse_iso_calendar_date(value: str) -> date | None:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", value.strip())
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def first_query_value(query: list[tuple[str, str]], key: str) -> str:
    lowered = key.lower()
    for query_key, value in query:
        if query_key.lower() == lowered:
            return value
    return ""


def resource_is_ncei_access_data_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    path = parsed.path.rstrip("/").lower()
    return path.endswith("/access/services/data/v1")


def stac_bounded_item_search_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    if not entry_is_stac_collection(entry):
        return {}
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    item_search_url = stac_item_search_url(entry, version_meta, option_metadata)
    if not item_search_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), option_metadata.get("stac_id"))
    dataset_id = first_text(entry.get("dataset_id"), version_meta.get("dataset_id"), option_metadata.get("stac_id"), "stac_collection")
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-stac-items-sample" if version else "stac-items-sample"
    dataset = Dataset(
        dataset_uid=dataset_uid,
        provider_id=provider_id,
        dataset_id=dataset_id,
        title=first_text(entry.get("dataset_title"), entry.get("name"), dataset_id),
        categories=tuple(str(value) for value in entry.get("categories", ()) if str(value).strip()) if isinstance(entry.get("categories"), (list, tuple)) else (),
        data_type=str(option_metadata.get("data_family") or entry.get("data_type") or "raster_or_grid"),
        native_format="geojson",
        geographic_scope=str(entry.get("geographic_scope") or ""),
        landing_url=first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
        api_url=item_search_url,
        license_url=str(entry.get("license_url") or ""),
        version=sample_version,
        metadata={
            **option_metadata,
            "data_family": option_metadata.get("data_family") or entry.get("data_type") or "raster_or_grid",
            "bounded_query": {
                "resolver_id": STAC_RESOLVER_ID,
                "item_search_url": item_search_url,
                "sample_limit": STAC_ITEM_SAMPLE_LIMIT,
                "asset_keys": option_metadata.get("asset_keys") or (),
            },
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset_uid,
        dataset_id=dataset_id,
        label="STAC bounded item sample GeoJSON",
        version=sample_version,
        status="resolved_sample",
        download_url=item_search_url,
        landing_url=dataset.landing_url,
        update_strategy="sample_then_review",
        notes="Bounded STAC item search generated from collection metadata; this downloads item metadata only, not raster assets.",
        metadata={"native_format": "geojson", "resolver_id": STAC_RESOLVER_ID, "source_format": "stac_collection"},
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason="The STAC collection was resolved into a bounded item-search GeoJSON request with limit=1.",
        direct_url=item_search_url,
    )
    resolved = dict(entry)
    resolved.update(
        {
            "dataset_uid": dataset_uid,
            "dataset_id": dataset_id,
            "dataset_title": dataset.title,
            "dataset_version": option.to_plan_metadata(),
            "source_format": "geojson",
            "target": "local_file_asset",
            "use_staging": True,
            "download_eligibility": eligibility.to_dict(),
            "download_url": item_search_url,
            "target_path": dataset_download_target_path(provider_id, dataset, option, downloads_root).as_posix(),
            "import_plan": dataset_import_plan_entry(dataset, option, eligibility),
            "plan_status": "planned",
            "adapter_resolution": {
                "resolver_id": STAC_RESOLVER_ID,
                "original_plan_index": plan_index,
                "item_search_url": item_search_url,
                "policy": "bounded_item_metadata_sample_only",
                "sample_limit": STAC_ITEM_SAMPLE_LIMIT,
                "source_url": first_text(
                    (entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else "",
                    entry.get("adapter_review_url"),
                    version_meta.get("download_url"),
                ),
                "asset_keys": list(option_metadata.get("asset_keys") or ()),
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


def entry_is_stac_collection(entry: dict[str, object]) -> bool:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    markers = {
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("data_type") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
    }
    if {"stac", "stac_collection", "stac_collections"} & markers:
        return True
    return bool(option_metadata.get("stac_id") or option_metadata.get("asset_keys"))


def stac_item_search_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> str:
    for link in stac_link_mappings(option_metadata.get("links")):
        if str(link.get("rel") or "").strip().lower() == "items":
            url = first_text(link.get("href"), link.get("url"))
            if url:
                return bounded_stac_items_url(url)

    candidates = [
        first_text(version_meta.get("download_url")),
        first_text(entry.get("adapter_review_url")),
        first_text(entry.get("api_base_url")),
        first_text((entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else ""),
        first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
    ]
    for raw_url in candidates:
        if not raw_url:
            continue
        candidate = stac_items_endpoint_from_url(raw_url, first_text(option_metadata.get("stac_id"), entry.get("dataset_id")))
        if candidate:
            return bounded_stac_items_url(candidate)
    return ""


def stac_link_mappings(links: object) -> list[dict[str, object]]:
    if not isinstance(links, list):
        return []
    return [dict(link) for link in links if isinstance(link, dict)]


def stac_items_endpoint_from_url(raw_url: str, collection_id: str = "") -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    lowered = path.lower()
    if lowered.endswith("/items") or "/items/" in lowered:
        return raw_url
    if "/collections/" in lowered:
        return urllib.parse.urlunparse(parsed._replace(path=f"{path}/items", query=""))
    if lowered.endswith("/collections") and collection_id:
        return urllib.parse.urlunparse(parsed._replace(path=f"{path}/{urllib.parse.quote(collection_id, safe='')}/items", query=""))
    return ""


def bounded_stac_items_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["limit"] = str(STAC_ITEM_SAMPLE_LIMIT)
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def resource_is_stac_items_link(resource: dict[str, object], url: str) -> bool:
    rel = str(resource.get("rel") or "").strip().lower()
    if rel == "items":
        return True
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.rstrip("/").lower()
    return path.endswith("/items") or "/items/" in path


def resource_is_ogc_records_metadata_link(entry: dict[str, object], resource: dict[str, object]) -> bool:
    if not entry_is_ogc_records_candidate(entry):
        return False
    rel = str(resource.get("rel") or "").strip().lower()
    return rel in {
        "alternate",
        "canonical",
        "collection",
        "describedby",
        "items",
        "parent",
        "related",
        "root",
        "self",
        "service-desc",
        "service-doc",
    }


def resource_is_cmr_metadata_link(entry: dict[str, object], resource: dict[str, object], url: str) -> bool:
    if not (entry_is_cmr_candidate(entry) or resource_url_is_cmr_api_metadata(url)):
        return False
    rels = resource_link_rels(resource)
    if any(cmr_link_rel_is_data(rel) for rel in rels):
        return False
    if any(cmr_link_rel_is_metadata(rel) for rel in rels):
        return True
    if resource_value_is_truthy(resource.get("inherited")):
        return True
    return resource_url_is_cmr_api_metadata(url)


def entry_is_cmr_candidate(entry: dict[str, object]) -> bool:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    markers = [
        str(entry.get("provider_id") or ""),
        str(entry.get("source_format") or ""),
        str(entry.get("data_type") or ""),
        str(option_metadata.get("native_format") or ""),
        str(option_metadata.get("source_format") or ""),
        str(option_metadata.get("discovery_source_type") or ""),
        str(option_metadata.get("source_type") or ""),
    ]
    categories = entry.get("categories")
    if isinstance(categories, (list, tuple)):
        markers.extend(str(value) for value in categories)
    review = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
    markers.append(str(review.get("adapter_id") or ""))
    return any("cmr" in marker.strip().lower() for marker in markers)


def resource_link_rels(resource: dict[str, object]) -> list[str]:
    rel = resource.get("rel")
    if isinstance(rel, str):
        return [rel]
    if isinstance(rel, list):
        return [str(value) for value in rel if str(value).strip()]
    return []


def cmr_link_rel_is_data(rel: str) -> bool:
    token = cmr_link_rel_token(rel)
    return token in {"data", "download", "enclosure"}


def cmr_link_rel_is_metadata(rel: str) -> bool:
    token = cmr_link_rel_token(rel)
    return token in {
        "alternate",
        "browse",
        "canonical",
        "collection",
        "describedby",
        "documentation",
        "metadata",
        "opendap",
        "parent",
        "related",
        "root",
        "self",
        "service",
        "service-desc",
        "service-doc",
    }


def cmr_link_rel_token(rel: str) -> str:
    cleaned = rel.strip().lower().rstrip("#/")
    if not cleaned:
        return ""
    return cleaned.rsplit("/", 1)[-1]


def resource_value_is_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def resource_url_is_cmr_api_metadata(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != "cmr.earthdata.nasa.gov":
        return False
    path = parsed.path.rstrip("/").lower()
    return path.startswith("/search/") and (
        path.endswith("/collections")
        or path.endswith("/collections.json")
        or path.endswith("/granules")
        or path.endswith("/granules.json")
        or "/concepts/" in path
    )


def entry_is_ogc_records_candidate(entry: dict[str, object]) -> bool:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    markers = {
        str(entry.get("source_format") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
        str(option_metadata.get("source_type") or "").strip().lower(),
    }
    return "ogc_api_records" in markers or "ogc_record" in markers


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


def resource_exceeds_size_bound(resource: dict[str, object]) -> bool:
    size = resource_size_bytes(resource)
    return size > DIRECT_RESOURCE_MAX_BYTES if size is not None else False


def resource_looks_downloadable(resource: dict[str, object], url: str) -> bool:
    if looks_like_direct_download(url):
        return True
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    return source_format_for_resource(resource, url, "unknown") in DIRECT_RESOURCE_FORMATS


def resource_size_bytes(resource: dict[str, object]) -> int | None:
    for key in (
        "size",
        "bytes",
        "content_length",
        "contentLength",
        "file_size",
        "fileSize",
        "FileSize",
        "size_bytes",
        "sizeInBytes",
        "SizeInBytes",
        "byteSize",
        "dcat:byteSize",
        "http://www.w3.org/ns/dcat#byteSize",
        "https://www.w3.org/ns/dcat#byteSize",
        "contentSize",
        "schema:contentSize",
        "http://schema.org/contentSize",
        "https://schema.org/contentSize",
    ):
        value = resource.get(key)
        if value in ("", None):
            continue
        size = positive_int_from_resource_value(value)
        if size is not None:
            return size
    return None


def positive_int_from_resource_value(value: object) -> int | None:
    if isinstance(value, (list, tuple)):
        for item in value:
            size = positive_int_from_resource_value(item)
            if size is not None:
                return size
        return None
    if isinstance(value, dict):
        return positive_int_from_resource_value(
            first_resource_text(
                value.get("@value"),
                value.get("value"),
                value.get("bytes"),
                value.get("size"),
            )
        )
    return positive_int_or_none(value)


def positive_int_or_none(value: object) -> int | None:
    try:
        size = int(float(str(value)))
    except (TypeError, ValueError):
        return None
    return size if size >= 0 else None


def fetch_json(url: str, timeout: float = 12.0) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def source_format_for_resource(resource: dict[str, object], url: str, fallback: str = "unknown") -> str:
    hinted = normalize_resource_format(
        first_resource_text(
            resource.get("format"),
            resource.get("dct:format"),
            resource.get("dc:format"),
            resource.get("http://purl.org/dc/terms/format"),
            resource.get("http://purl.org/dc/elements/1.1/format"),
            resource.get("mimetype"),
            resource.get("mimeType"),
            resource.get("media_type"),
            resource.get("mediaType"),
            resource.get("dcat:mediaType"),
            resource.get("http://www.w3.org/ns/dcat#mediaType"),
            resource.get("https://www.w3.org/ns/dcat#mediaType"),
            resource.get("content_type"),
            resource.get("contentType"),
            resource.get("encodingFormat"),
            resource.get("schema:encodingFormat"),
            resource.get("http://schema.org/encodingFormat"),
            resource.get("https://schema.org/encodingFormat"),
            resource.get("type"),
        )
    )
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
