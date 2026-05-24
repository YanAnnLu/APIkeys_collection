from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from api_launcher.adapter_plan_resolvers.datacite import (
    datacite_doi_content_url_entries as resolve_datacite_doi_content_url_entries,
)
from api_launcher.adapter_plan_resolvers.dataverse import (
    dataverse_latest_version_file_entries as resolve_dataverse_latest_version_file_entries,
)
from api_launcher.adapter_plan_resolvers.ckan import (
    ckan_package_show_resource_entries as resolve_ckan_package_show_resource_entries,
)
from api_launcher.adapter_plan_resolvers.cmr_asset import (
    bounded_cmr_granule_asset_lookup_url as resolve_bounded_cmr_granule_asset_lookup_url,
    cmr_feed_link_resource as resolve_cmr_feed_link_resource,
    cmr_granule_asset_candidate_urls as resolve_cmr_granule_asset_candidate_urls,
    cmr_granule_asset_link_entries as resolve_cmr_granule_asset_link_entries,
    cmr_granule_asset_lookup_url as resolve_cmr_granule_asset_lookup_url,
    cmr_granule_asset_resources as resolve_cmr_granule_asset_resources,
    cmr_granule_concept_id_from_path,
    cmr_granule_records,
    cmr_link_resources as resolve_cmr_link_resources,
    entry_is_cmr_granule as resolve_entry_is_cmr_granule,
)
from api_launcher.adapter_plan_resolvers.cmr_collection import (
    bounded_cmr_granules_url as resolve_bounded_cmr_granules_url,
    cmr_bounded_granule_search_entry as resolve_cmr_bounded_granule_search_entry,
    cmr_bounded_granule_search_url as resolve_cmr_bounded_granule_search_url,
    cmr_candidate_urls as resolve_cmr_candidate_urls,
    entry_is_cmr_collection as resolve_entry_is_cmr_collection,
)
from api_launcher.adapter_plan_resolvers.erddap import (
    absolute_erddap_url as resolve_absolute_erddap_url,
    erddap_bounded_sample_entry as resolve_erddap_bounded_sample_entry,
    erddap_info_dimensions_and_variables as resolve_erddap_info_dimensions_and_variables,
    erddap_info_url as resolve_erddap_info_url,
    erddap_protocol_url as resolve_erddap_protocol_url,
    erddap_sample_csv_url as resolve_erddap_sample_csv_url,
    tabledap_sample_variables as resolve_tabledap_sample_variables,
)
from api_launcher.adapter_plan_resolvers.ncei_search import (
    bounded_ncei_search_url as resolve_bounded_ncei_search_url,
    entry_is_ncei_search_candidate as resolve_entry_is_ncei_search_candidate,
    ncei_bounded_search_entry as resolve_ncei_bounded_search_entry,
    ncei_bounded_search_url as resolve_ncei_bounded_search_url,
    ncei_candidate_urls as resolve_ncei_candidate_urls,
    ncei_limited_query as resolve_ncei_limited_query,
    ncei_search_sibling_endpoint as resolve_ncei_search_sibling_endpoint,
)
from api_launcher.adapter_plan_resolvers.ncei_access_data import (
    bounded_ncei_access_data_url as resolve_bounded_ncei_access_data_url,
    canonical_ncei_access_data_query as resolve_canonical_ncei_access_data_query,
    ncei_access_data_bounds as resolve_ncei_access_data_bounds,
    ncei_access_data_candidate_urls as resolve_ncei_access_data_candidate_urls,
    ncei_access_data_is_safely_bounded as resolve_ncei_access_data_is_safely_bounded,
    ncei_bounded_access_data_entry as resolve_ncei_bounded_access_data_entry,
    ncei_bounded_access_data_url as resolve_ncei_bounded_access_data_url,
    resource_is_ncei_access_data_url as resolve_resource_is_ncei_access_data_url,
)
from api_launcher.adapter_plan_resolvers.ncei_search_data_file import (
    bounded_ncei_search_data_file_lookup_url as resolve_bounded_ncei_search_data_file_lookup_url,
    ncei_data_file_lookup_query as resolve_ncei_data_file_lookup_query,
    ncei_noaa_host as resolve_ncei_noaa_host,
    ncei_search_data_file_bounds as resolve_ncei_search_data_file_bounds,
    ncei_search_data_file_entries as resolve_ncei_search_data_file_entries,
    ncei_search_data_file_lookup_is_bounded as resolve_ncei_search_data_file_lookup_is_bounded,
    ncei_search_data_file_lookup_url as resolve_ncei_search_data_file_lookup_url,
    ncei_search_data_file_resource as resolve_ncei_search_data_file_resource,
    ncei_search_data_file_resources as resolve_ncei_search_data_file_resources,
    ncei_search_data_file_url as resolve_ncei_search_data_file_url,
)
from api_launcher.adapter_plan_resolvers.metadata_guards import (
    cmr_link_rel_is_data as resolve_cmr_link_rel_is_data,
    cmr_link_rel_is_metadata as resolve_cmr_link_rel_is_metadata,
    cmr_link_rel_token as resolve_cmr_link_rel_token,
    entry_is_cmr_candidate as resolve_entry_is_cmr_candidate,
    entry_is_ogc_records_candidate as resolve_entry_is_ogc_records_candidate,
    resource_is_cmr_metadata_link as resolve_resource_is_cmr_metadata_link,
    resource_is_ogc_records_metadata_link as resolve_resource_is_ogc_records_metadata_link,
    resource_link_rels as resolve_resource_link_rels,
    resource_url_is_cmr_api_metadata as resolve_resource_url_is_cmr_api_metadata,
    resource_value_is_truthy as resolve_resource_value_is_truthy,
)
from api_launcher.adapter_plan_resolvers.resource_formats import (
    normalize_resource_format as resolve_normalize_resource_format,
    source_format_from_url as resolve_source_format_from_url,
)
from api_launcher.adapter_plan_resolvers.resource_sizes import (
    positive_int_from_resource_value as resolve_positive_int_from_resource_value,
    positive_int_or_none as resolve_positive_int_or_none,
    resource_exceeds_size_bound as resolve_resource_exceeds_size_bound,
    resource_size_bytes as resolve_resource_size_bytes,
)
from api_launcher.adapter_plan_resolvers.socrata import (
    bounded_socrata_url,
    resource_is_socrata_api_url,
    socrata_bounded_sample_entry as resolve_socrata_bounded_sample_entry,
    socrata_candidate_urls as resolve_socrata_candidate_urls,
    socrata_dataset_id_from_url,
    socrata_resource_url_from_domain,
    socrata_sample_url as resolve_socrata_sample_url,
    strip_socrata_output_suffix,
)
from api_launcher.adapter_plan_resolvers.stac import (
    bounded_stac_items_url as resolve_bounded_stac_items_url,
    entry_is_stac_collection as resolve_entry_is_stac_collection,
    resource_is_stac_items_link as resolve_resource_is_stac_items_link,
    stac_bounded_item_search_entry as resolve_stac_bounded_item_search_entry,
    stac_item_search_url as resolve_stac_item_search_url,
    stac_items_endpoint_from_url as resolve_stac_items_endpoint_from_url,
    stac_link_mappings as resolve_stac_link_mappings,
)
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
    "geojson.gz",
    "json",
    "json.gz",
    "jsonl",
    "jsonl.gz",
    "ndjson",
    "ndjson.gz",
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
    # 這個入口把「需要 adapter review 的 plan」轉成可下載的小型 direct entries。
    # 它不直接執行下載，目的只是產生下一階段 download/import runner 能理解的 plan。
    entries = plan_entries(plan_payload)
    output_entries: list[dict[str, object]] = []
    resolved_review_entries = 0
    unresolved_review_entries = 0
    direct_entries_added = 0
    warnings: list[str] = []

    for index, entry in enumerate(entries, start=1):
        # index 使用原 plan 的人類可見順序，方便 warning 回頭對照使用者匯出的 JSON。
        resolved_entries = direct_resource_entries_for_plan_entry(entry, index, downloads_root)
        if resolved_entries:
            resolved_review_entries += 1
            direct_entries_added += len(resolved_entries)
            if keep_original_review_entries:
                output_entries.append(entry)
            # 預設用 resolved entries 取代 review entry，避免同一資料集同時留在待辦與可執行隊列。
            output_entries.extend(resolved_entries)
            continue

        output_entries.append(entry)
        if wants_source_resolution(entry):
            # 無法解析時保留原 entry，讓人類或後續 adapter 繼續接手，而不是靜默丟失。
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
        # 已經是 direct download 或一般 plan entry 的資料，不在這裡重新判斷。
        return []
    resolved_entries: list[dict[str, object]] = []
    # 先跑需要明確邊界的 API resolver，再看泛用 resources，避免未加 limit 的 API 被誤當檔案。
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
        # 下列 API/metadata 連結看起來可能像 JSON，但語意不是可直接下載的資料檔。
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
            # 超過上限的資源必須留在 review，避免 resolver 產生大型或昂貴的下載工作。
            continue
        resolved = direct_resource_entry(entry, resource, plan_index, resource_index, url, downloads_root)
        if resolved:
            resolved_entries.append(resolved)
    if not resolved_entries:
        # Socrata resource URL 要改寫成 `$limit=25` 小樣本，不能直接下載整張表。
        socrata_entry = socrata_bounded_sample_entry(entry, plan_index, downloads_root)
        if socrata_entry:
            resolved_entries.append(socrata_entry)
    if not resolved_entries and not resources:
        # 沒有 resource 摘要時才做 metadata lookup，避免重複查詢已經足夠明確的 plan。
        resolved_entries.extend(ncei_search_data_file_entries(entry, plan_index, downloads_root))
    if not resolved_entries:
        # NCEI Search metadata 可以產出 bounded sample；仍失敗才保留原 review entry。
        ncei_entry = ncei_bounded_search_entry(entry, plan_index, downloads_root)
        if ncei_entry:
            resolved_entries.append(ncei_entry)
    if not resolved_entries:
        # NCEI Access Data 必須有日期/空間等約束，不能把整個資料集直接排進下載。
        ncei_access_entry = ncei_bounded_access_data_entry(entry, plan_index, downloads_root)
        if ncei_access_entry:
            resolved_entries.append(ncei_access_entry)
    if not resolved_entries and not resources:
        # CMR granule lookup 只處理已經指到單一 granule metadata 的項目。
        resolved_entries.extend(cmr_granule_asset_link_entries(entry, plan_index, downloads_root))
    if not resolved_entries and not resources:
        # CKAN/DataCite/Dataverse lookup 都是二階段 metadata 查詢；有 resources 時先尊重原摘要。
        resolved_entries.extend(ckan_package_show_resource_entries(entry, plan_index, downloads_root))
    if not resolved_entries and not resources:
        resolved_entries.extend(datacite_doi_content_url_entries(entry, plan_index, downloads_root))
    if not resolved_entries and not resources:
        resolved_entries.extend(dataverse_latest_version_file_entries(entry, plan_index, downloads_root))
    erddap_entry = erddap_bounded_sample_entry(entry, plan_index, downloads_root)
    if erddap_entry:
        # ERDDAP sample 是 bounded query，不依賴 resources 清單；能產生樣本時可與其他解析結果並存。
        resolved_entries.append(erddap_entry)
    return resolved_entries


def wants_source_resolution(entry: dict[str, object]) -> bool:
    # 舊 plan 可能只標 download_eligibility，較新的 plan 會有 adapter_review.required_action。
    eligibility = entry.get("download_eligibility") if isinstance(entry.get("download_eligibility"), dict) else {}
    review = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
    action = str(review.get("required_action") or "").strip()
    status = str(eligibility.get("status") or "").strip()
    return action == "resolve_source_to_direct_download_entries" or status == "adapter_required"


def resource_mappings_from_entry(entry: dict[str, object]) -> list[dict[str, object]]:
    # 同時讀 entry 與 dataset_version.metadata，因 crawler/adapter 交接時兩種位置都可能出現。
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
                # 同一 resource 可能同時出現在 DCAT distribution、links 與 @graph；用 URL 去重。
                seen_urls.add(url)
            resources.append(dict(item))
    return resources


def resource_mappings_from_candidate(candidate: object, group: str = "") -> list[dict[str, object]]:
    if isinstance(candidate, list):
        # catalog metadata 常把 resources 包成多層陣列，遞迴攤平後才方便共用判斷。
        resources: list[dict[str, object]] = []
        for item in candidate:
            resources.extend(resource_mappings_from_candidate(item, group=group))
        return resources
    if not isinstance(candidate, dict):
        return []
    if resource_url(candidate):
        resource = dict(candidate)
        if group and not resource.get("group"):
            # group 保存外層欄位名稱，讓後續 warning 或 target path 還看得出來源脈絡。
            resource["group"] = group
        if group and not resource.get("name") and not resource.get("title"):
            resource["name"] = group
        return [resource]
    resources = []
    for key, value in candidate.items():
        if isinstance(value, (list, dict)):
            # 沒有 URL 的 dict 仍可能是 JSON-LD/Schema.org 外殼，往內層找真正 distribution。
            resources.extend(resource_mappings_from_candidate(value, group=str(key)))
    return resources


def resource_url(resource: dict[str, object]) -> str:
    # 欄位順序偏好明確 download/content URL，最後才退回泛用 url/href。
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
        # JSON-LD 或 Schema.org 常把 URL 包在 @id/@value/value 裡，這裡集中拆解。
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
    # 這裡把「一個可下載 resource」包成完整 plan entry，後續 runner 才能沿用既有下載/匯入邏輯。
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    source_format = source_format_for_resource(resource, url, str(entry.get("source_format") or "unknown"))
    resource_name = first_text(resource.get("name"), resource.get("id"), resource.get("title"), resource.get("rel"), resource.get("group"), Path(urllib.parse.urlparse(url).path).name)
    base_version = first_text(version_meta.get("version"), entry.get("version"), "resolved")
    resource_part = safe_path_part(resource_name or f"resource_{resource_index}")
    # version 需要混入 resource 名稱，避免同一 dataset 的多個檔案撞到同一個 target path。
    version = f"{base_version}-{resource_part}" if base_version and resource_part else base_version or resource_part
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"))
    dataset_id = first_text(entry.get("dataset_id"), version_meta.get("dataset_id"), "dataset")
    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    # Dataset/DatasetVersionOption 是臨時物件，用來重用既有 target path、eligibility 與 import policy。
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
        # 有些 API 回傳無副檔名 URL，但 metadata 已宣告可匯入格式；這裡補成 direct_download。
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
                # adapter_resolution 保留解析來源，讓日後出錯時能回查是哪個 resolver 做的判斷。
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
    # 解析成功後移除 review 標記，避免 UI/agent 把它再次列為待辦。
    resolved.pop("adapter_review", None)
    resolved.pop("adapter_review_url", None)
    return resolved


def ckan_package_show_resource_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    # 這個相容 wrapper 保留舊測試 patch 點：測試仍可 patch 本模組的 fetch_json。
    return resolve_ckan_package_show_resource_entries(
        entry,
        plan_index,
        downloads_root,
        fetch_json=fetch_json,
        direct_resource_entry=direct_resource_entry,
        resource_url=resource_url,
        resource_looks_downloadable=resource_looks_downloadable,
        resource_exceeds_size_bound=resource_exceeds_size_bound,
        first_text=first_text,
        resolver_id=CKAN_PACKAGE_RESOLVER_ID,
    )


def datacite_doi_content_url_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    # 這個相容 wrapper 保留舊測試 patch 點：測試仍可 patch 本模組的 fetch_json。
    return resolve_datacite_doi_content_url_entries(
        entry,
        plan_index,
        downloads_root,
        fetch_json=fetch_json,
        direct_resource_entry=direct_resource_entry,
        resource_url=resource_url,
        resource_looks_downloadable=resource_looks_downloadable,
        resource_exceeds_size_bound=resource_exceeds_size_bound,
        first_text=first_text,
        max_content_urls=DATACITE_MAX_CONTENT_URLS,
        resolver_id=DATACITE_DOI_CONTENT_URL_RESOLVER_ID,
    )


def dataverse_latest_version_file_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    # 這個相容 wrapper 保留舊測試 patch 點：測試仍可 patch 本模組的 fetch_json。
    return resolve_dataverse_latest_version_file_entries(
        entry,
        plan_index,
        downloads_root,
        fetch_json=fetch_json,
        direct_resource_entry=direct_resource_entry,
        resource_url=resource_url,
        resource_looks_downloadable=resource_looks_downloadable,
        resource_exceeds_size_bound=resource_exceeds_size_bound,
        first_text=first_text,
        source_format_from_url=source_format_from_url,
        normalize_resource_format=normalize_resource_format,
        max_files=DATAVERSE_MAX_FILES,
        resolver_id=DATAVERSE_FILE_RESOLVER_ID,
    )


def socrata_bounded_sample_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    # 主模組只保留相容 wrapper；Socrata 的有界樣本策略由專屬 resolver 模組維護。
    return resolve_socrata_bounded_sample_entry(
        entry,
        plan_index,
        downloads_root,
        first_text=first_text,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
        resolver_id=SOCRATA_RESOLVER_ID,
        sample_limit=SOCRATA_SAMPLE_LIMIT,
    )


def socrata_sample_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> tuple[str, str, str]:
    return resolve_socrata_sample_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
        sample_limit=SOCRATA_SAMPLE_LIMIT,
    )


def socrata_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> list[str]:
    return resolve_socrata_candidate_urls(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
    )


def ncei_search_data_file_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    return resolve_ncei_search_data_file_entries(
        entry,
        plan_index,
        downloads_root,
        fetch_json=fetch_json,
        first_text=first_text,
        first_query_value=first_query_value,
        direct_resource_entry=direct_resource_entry,
        resource_url=resource_url,
        resource_looks_downloadable=resource_looks_downloadable,
        resource_exceeds_size_bound=resource_exceeds_size_bound,
        source_format_from_url=source_format_from_url,
        resolver_id=NCEI_SEARCH_DATA_FILE_RESOLVER_ID,
        lookup_limit=NCEI_DATA_FILE_LOOKUP_LIMIT,
    )


def ncei_search_data_file_lookup_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> str:
    return resolve_ncei_search_data_file_lookup_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        first_query_value=first_query_value,
        lookup_limit=NCEI_DATA_FILE_LOOKUP_LIMIT,
    )


def bounded_ncei_search_data_file_lookup_url(raw_url: str, ncei_dataset_id: str) -> str:
    return resolve_bounded_ncei_search_data_file_lookup_url(
        raw_url,
        ncei_dataset_id,
        first_query_value=first_query_value,
        lookup_limit=NCEI_DATA_FILE_LOOKUP_LIMIT,
    )


def ncei_data_file_lookup_query(query: list[tuple[str, str]], ncei_dataset_id: str) -> str:
    return resolve_ncei_data_file_lookup_query(
        query,
        ncei_dataset_id,
        first_query_value=first_query_value,
        lookup_limit=NCEI_DATA_FILE_LOOKUP_LIMIT,
    )


def ncei_search_data_file_bounds(query: list[tuple[str, str]]) -> dict[str, object]:
    return resolve_ncei_search_data_file_bounds(query, first_query_value=first_query_value)


def ncei_search_data_file_lookup_is_bounded(bounds: dict[str, object]) -> bool:
    return resolve_ncei_search_data_file_lookup_is_bounded(bounds)


def ncei_search_data_file_resources(payload: dict[str, object], lookup_url: str) -> list[dict[str, object]]:
    return resolve_ncei_search_data_file_resources(
        payload,
        lookup_url,
        first_text=first_text,
        source_format_from_url=source_format_from_url,
        lookup_limit=NCEI_DATA_FILE_LOOKUP_LIMIT,
    )


def ncei_search_data_file_resource(item: dict[str, object], lookup_url: str) -> dict[str, object]:
    return resolve_ncei_search_data_file_resource(
        item,
        lookup_url,
        first_text=first_text,
        source_format_from_url=source_format_from_url,
    )


def ncei_search_data_file_url(file_path: str, lookup_url: str) -> str:
    return resolve_ncei_search_data_file_url(file_path, lookup_url)


def ncei_noaa_host(netloc: str) -> bool:
    return resolve_ncei_noaa_host(netloc)


def ncei_bounded_search_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    return resolve_ncei_bounded_search_entry(
        entry,
        plan_index,
        downloads_root,
        first_text=first_text,
        resolver_id=NCEI_SEARCH_RESOLVER_ID,
        sample_limit=NCEI_SEARCH_SAMPLE_LIMIT,
    )


def ncei_bounded_search_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> tuple[str, str, str, str]:
    return resolve_ncei_bounded_search_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        sample_limit=NCEI_SEARCH_SAMPLE_LIMIT,
    )


def entry_is_ncei_search_candidate(entry: dict[str, object], option_metadata: dict[str, object]) -> bool:
    return resolve_entry_is_ncei_search_candidate(entry, option_metadata)


def ncei_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> list[str]:
    return resolve_ncei_candidate_urls(entry, version_meta, option_metadata, first_text=first_text)


def bounded_ncei_search_url(raw_url: str, ncei_dataset_id: str) -> tuple[str, str]:
    return resolve_bounded_ncei_search_url(raw_url, ncei_dataset_id, sample_limit=NCEI_SEARCH_SAMPLE_LIMIT)


def ncei_search_sibling_endpoint(parsed: urllib.parse.ParseResult, endpoint: str) -> urllib.parse.ParseResult:
    return resolve_ncei_search_sibling_endpoint(parsed, endpoint)


def ncei_limited_query(
    query: list[tuple[str, str]],
    require_dataset: bool,
    dataset_id: str,
    for_data_endpoint: bool = True,
) -> str:
    return resolve_ncei_limited_query(
        query,
        require_dataset,
        dataset_id,
        for_data_endpoint=for_data_endpoint,
        sample_limit=NCEI_SEARCH_SAMPLE_LIMIT,
    )


def ncei_bounded_access_data_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    return resolve_ncei_bounded_access_data_entry(
        entry,
        plan_index,
        downloads_root,
        first_text=first_text,
        first_query_value=first_query_value,
        parse_iso_calendar_date=parse_iso_calendar_date,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
        resolver_id=NCEI_ACCESS_DATA_RESOLVER_ID,
        max_days=NCEI_ACCESS_DATA_MAX_DAYS,
    )


def ncei_bounded_access_data_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> tuple[str, str, str, dict[str, object]]:
    return resolve_ncei_bounded_access_data_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        first_query_value=first_query_value,
        parse_iso_calendar_date=parse_iso_calendar_date,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
        max_days=NCEI_ACCESS_DATA_MAX_DAYS,
    )


def ncei_access_data_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> list[str]:
    return resolve_ncei_access_data_candidate_urls(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        resource_mappings_from_entry=resource_mappings_from_entry,
        resource_url=resource_url,
    )


def bounded_ncei_access_data_url(raw_url: str) -> tuple[str, str, dict[str, object]]:
    return resolve_bounded_ncei_access_data_url(
        raw_url,
        first_query_value=first_query_value,
        parse_iso_calendar_date=parse_iso_calendar_date,
        max_days=NCEI_ACCESS_DATA_MAX_DAYS,
    )


def canonical_ncei_access_data_query(query: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return resolve_canonical_ncei_access_data_query(query)


def ncei_access_data_bounds(query: list[tuple[str, str]]) -> dict[str, object]:
    return resolve_ncei_access_data_bounds(
        query,
        first_query_value=first_query_value,
        parse_iso_calendar_date=parse_iso_calendar_date,
    )


def ncei_access_data_is_safely_bounded(bounds: dict[str, object]) -> bool:
    return resolve_ncei_access_data_is_safely_bounded(bounds, max_days=NCEI_ACCESS_DATA_MAX_DAYS)


def cmr_bounded_granule_search_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    # CMR collection bounded sample 與 CMR granule asset link 是兩條不同 resolver path。
    return resolve_cmr_bounded_granule_search_entry(
        entry,
        plan_index,
        downloads_root,
        first_text=first_text,
        resolver_id=CMR_GRANULE_RESOLVER_ID,
        sample_limit=CMR_GRANULE_SAMPLE_LIMIT,
    )


def cmr_bounded_granule_search_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> tuple[str, str, str]:
    return resolve_cmr_bounded_granule_search_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        sample_limit=CMR_GRANULE_SAMPLE_LIMIT,
    )


def entry_is_cmr_collection(entry: dict[str, object], option_metadata: dict[str, object]) -> bool:
    return resolve_entry_is_cmr_collection(entry, option_metadata)


def cmr_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> list[str]:
    return resolve_cmr_candidate_urls(entry, version_meta, option_metadata, first_text=first_text)


def bounded_cmr_granules_url(raw_url: str, concept_id: str) -> str:
    return resolve_bounded_cmr_granules_url(raw_url, concept_id, sample_limit=CMR_GRANULE_SAMPLE_LIMIT)


def cmr_granule_asset_link_entries(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> list[dict[str, object]]:
    # 主模組保留舊入口與 fetch_json patch 點；CMR data-link 篩選交給專屬 resolver。
    return resolve_cmr_granule_asset_link_entries(
        entry,
        plan_index,
        downloads_root,
        fetch_json=fetch_json,
        direct_resource_entry=direct_resource_entry,
        resource_url=resource_url,
        resource_looks_downloadable=resource_looks_downloadable,
        resource_exceeds_size_bound=resource_exceeds_size_bound,
        resource_is_cmr_metadata_link=resource_is_cmr_metadata_link,
        resource_link_rels=resource_link_rels,
        cmr_link_rel_is_data=cmr_link_rel_is_data,
        first_text=first_text,
        resolver_id=CMR_GRANULE_ASSET_RESOLVER_ID,
        max_asset_links=CMR_GRANULE_ASSET_MAX_LINKS,
    )


def cmr_granule_asset_lookup_url(entry: dict[str, object]) -> str:
    return resolve_cmr_granule_asset_lookup_url(entry, first_text=first_text)


def entry_is_cmr_granule(entry: dict[str, object], option_metadata: dict[str, object]) -> bool:
    return resolve_entry_is_cmr_granule(entry, option_metadata)


def cmr_granule_asset_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> list[str]:
    return resolve_cmr_granule_asset_candidate_urls(entry, version_meta, option_metadata, first_text=first_text)


def bounded_cmr_granule_asset_lookup_url(raw_url: str) -> str:
    return resolve_bounded_cmr_granule_asset_lookup_url(raw_url)


def cmr_granule_asset_resources(payload: dict[str, object]) -> list[dict[str, object]]:
    return resolve_cmr_granule_asset_resources(payload, first_text=first_text, resource_url=resource_url)


def cmr_link_resources(record: dict[str, object]) -> list[dict[str, object]]:
    return resolve_cmr_link_resources(record, first_text=first_text, resource_url=resource_url)


def cmr_feed_link_resource(link: dict[str, object]) -> dict[str, object]:
    return resolve_cmr_feed_link_resource(link, first_text=first_text)


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
    return resolve_resource_is_ncei_access_data_url(url)


def stac_bounded_item_search_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    return resolve_stac_bounded_item_search_entry(
        entry,
        plan_index,
        downloads_root,
        first_text=first_text,
        resolver_id=STAC_RESOLVER_ID,
        sample_limit=STAC_ITEM_SAMPLE_LIMIT,
    )


def erddap_bounded_sample_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
) -> dict[str, object]:
    return resolve_erddap_bounded_sample_entry(
        entry,
        plan_index,
        downloads_root,
        fetch_json=fetch_json,
        first_text=first_text,
        eligibility_from_option=assess_dataset_version_download,
        resolver_id=ERDDAP_RESOLVER_ID,
        sample_limit=ERDDAP_SAMPLE_LIMIT,
    )


def erddap_protocol_url(
    entry: dict[str, object],
    protocols: dict[str, object],
    version_meta: dict[str, object],
) -> tuple[str, str]:
    return resolve_erddap_protocol_url(entry, protocols, version_meta, first_text=first_text)


def absolute_erddap_url(raw_url: str, entry: dict[str, object], version_meta: dict[str, object]) -> str:
    return resolve_absolute_erddap_url(raw_url, entry, version_meta, first_text=first_text)


def entry_is_stac_collection(entry: dict[str, object]) -> bool:
    return resolve_entry_is_stac_collection(entry)


def stac_item_search_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
) -> str:
    return resolve_stac_item_search_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        sample_limit=STAC_ITEM_SAMPLE_LIMIT,
    )


def stac_link_mappings(links: object) -> list[dict[str, object]]:
    return resolve_stac_link_mappings(links)


def stac_items_endpoint_from_url(raw_url: str, collection_id: str = "") -> str:
    return resolve_stac_items_endpoint_from_url(raw_url, collection_id)


def bounded_stac_items_url(url: str) -> str:
    return resolve_bounded_stac_items_url(url, sample_limit=STAC_ITEM_SAMPLE_LIMIT)


def resource_is_stac_items_link(resource: dict[str, object], url: str) -> bool:
    return resolve_resource_is_stac_items_link(resource, url)


def resource_is_ogc_records_metadata_link(entry: dict[str, object], resource: dict[str, object]) -> bool:
    return resolve_resource_is_ogc_records_metadata_link(entry, resource)


def resource_is_cmr_metadata_link(entry: dict[str, object], resource: dict[str, object], url: str) -> bool:
    return resolve_resource_is_cmr_metadata_link(entry, resource, url)


def entry_is_cmr_candidate(entry: dict[str, object]) -> bool:
    return resolve_entry_is_cmr_candidate(entry)


def resource_link_rels(resource: dict[str, object]) -> list[str]:
    return resolve_resource_link_rels(resource)


def cmr_link_rel_is_data(rel: str) -> bool:
    return resolve_cmr_link_rel_is_data(rel)


def cmr_link_rel_is_metadata(rel: str) -> bool:
    return resolve_cmr_link_rel_is_metadata(rel)


def cmr_link_rel_token(rel: str) -> str:
    return resolve_cmr_link_rel_token(rel)


def resource_value_is_truthy(value: object) -> bool:
    return resolve_resource_value_is_truthy(value)


def resource_url_is_cmr_api_metadata(url: str) -> bool:
    return resolve_resource_url_is_cmr_api_metadata(url)


def entry_is_ogc_records_candidate(entry: dict[str, object]) -> bool:
    return resolve_entry_is_ogc_records_candidate(entry)


def erddap_info_url(protocol_url: str, dataset_id: str) -> str:
    return resolve_erddap_info_url(protocol_url, dataset_id)


def erddap_info_dimensions_and_variables(payload: dict[str, object]) -> tuple[list[str], list[str]]:
    return resolve_erddap_info_dimensions_and_variables(payload)


def erddap_sample_csv_url(protocol_url: str, protocol_name: str, dimensions: list[str], variables: list[str]) -> str:
    return resolve_erddap_sample_csv_url(
        protocol_url,
        protocol_name,
        dimensions,
        variables,
        sample_limit=ERDDAP_SAMPLE_LIMIT,
    )


def tabledap_sample_variables(dimensions: list[str], variables: list[str]) -> list[str]:
    return resolve_tabledap_sample_variables(dimensions, variables)


def resource_exceeds_size_bound(resource: dict[str, object]) -> bool:
    return resolve_resource_exceeds_size_bound(
        resource,
        DIRECT_RESOURCE_MAX_BYTES,
        text_reader=first_resource_text,
    )


def resource_looks_downloadable(resource: dict[str, object], url: str) -> bool:
    if looks_like_direct_download(url):
        return True
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    # 有些資料目錄的 URL 沒副檔名，只能靠 metadata 的 format/mediaType 判斷。
    return source_format_for_resource(resource, url, "unknown") in DIRECT_RESOURCE_FORMATS


def resource_size_bytes(resource: dict[str, object]) -> int | None:
    return resolve_resource_size_bytes(resource, text_reader=first_resource_text)


def positive_int_from_resource_value(value: object) -> int | None:
    return resolve_positive_int_from_resource_value(value, text_reader=first_resource_text)


def positive_int_or_none(value: object) -> int | None:
    return resolve_positive_int_or_none(value)


def fetch_json(url: str, timeout: float = 12.0) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def source_format_for_resource(resource: dict[str, object], url: str, fallback: str = "unknown") -> str:
    # 格式判斷會影響 importer；先保留 URL 的 compound suffix，再退回 metadata hint。
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
    if inferred in {
        "csv.gz",
        "csv.zst",
        "geojson.gz",
        "json.gz",
        "jsonl.gz",
        "ndjson.gz",
        "tar.gz",
        "zip",
        "zst",
        "gz",
        "xz",
        "bz2",
    }:
        return inferred
    if hinted != "unknown":
        return hinted
    if inferred != "unknown":
        return inferred
    return normalize_resource_format(fallback)


def normalize_resource_format(value: str) -> str:
    return resolve_normalize_resource_format(value)


def source_format_from_url(url: str) -> str:
    return resolve_source_format_from_url(url)


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
