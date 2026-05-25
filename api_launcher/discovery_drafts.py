from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from api_launcher.crawlers.dataset_sources import (
    SUPPORTED_DATASET_SOURCE_TYPES,
    append_dataset_discovery_source,
    source_to_dict,
)
from api_launcher.crawlers.ogc_wms import ogc_wms_capabilities_url
from api_launcher.crawlers.types import DatasetDiscoverySource


EXPLICIT_SOURCE_TYPE_KEYS = ("dataset_source_type", "source_type", "crawler_source_type")
ENDPOINT_URL_KEYS = ("dataset_source_endpoint_url", "endpoint_url", "api_base_url", "source_url", "docs_url")
LOCAL_DISCOVERY_AUDIT_NEXT_ACTION = "run_local_discovery_audit_before_catalog_promotion"
LOCAL_DISCOVERY_AUDIT_COMMAND = (
    "python APIkeys_collection.py --promote-local-discovery-catalog "
    "--promote-local-discovery-dry-run --write-local-discovery-audit-json state/local_discovery_audit.json"
)
SourceEndpointNormalizer = Callable[[urllib.parse.ParseResult], str]
UrlSourceTypePredicate = Callable[[str], bool]


def dataset_source_from_provider_candidate(candidate: Mapping[str, object]) -> DatasetDiscoverySource:
    # Provider 候選只有在足以指向「可執行 crawler」時才轉成 source 草稿；推不出來就保留在人工審核。
    provider_id = clean_text(candidate.get("provider_id"))
    name = clean_text(candidate.get("name"))
    endpoint_url = first_text(candidate, ENDPOINT_URL_KEYS)
    missing = [
        label
        for label, value in (
            ("provider_id", provider_id),
            ("name", name),
            ("dataset_source_endpoint_url/endpoint_url/api_base_url/source_url/docs_url", endpoint_url),
        )
        if not value
    ]
    if missing:
        raise ValueError("missing required source draft fields: " + ", ".join(missing))

    source_type = first_supported_source_type(candidate) or infer_source_type(endpoint_url)
    if not source_type:
        raise ValueError("no supported dataset discovery source type could be inferred")

    endpoint_url = normalize_endpoint_for_source_type(source_type, endpoint_url)
    return DatasetDiscoverySource(
        source_id=clean_text(candidate.get("dataset_source_id") or candidate.get("source_id")) or f"{provider_id}_{source_type}",
        provider_id=provider_id,
        name=f"{name} dataset discovery",
        source_type=source_type,
        endpoint_url=endpoint_url,
        docs_url=clean_text(candidate.get("docs_url")),
        search_terms=tuple_from_candidate(candidate, "search_terms") or tuple_from_candidate(candidate, "categories")[:6],
        categories=tuple_from_candidate(candidate, "categories"),
        geographic_scope=clean_text(candidate.get("geographic_scope")) or "global",
        max_results=int_value(candidate.get("max_results"), default=10),
        min_expected_candidates=int_value(candidate.get("min_expected_candidates"), default=1),
        notes="Drafted from a provider candidate review. This local source must pass crawler audit before catalog promotion.",
    )


def write_provider_candidate_source_drafts(
    payload: Mapping[str, object],
    output_path: str | Path,
    provider_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    # 這裡只把 review JSON 轉成本機草稿；正式 catalog 仍必須經過 crawler audit 與 promotion guard。
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("provider candidate payload must contain a candidates list")

    output_path = Path(output_path)
    provider_filter = {provider_id.strip() for provider_id in provider_ids if provider_id.strip()}
    written: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, Mapping):
            skipped.append(skipped_candidate(index, {}, "candidate_not_object"))
            continue
        provider_id = clean_text(candidate.get("provider_id"))
        if provider_filter and provider_id not in provider_filter:
            skipped.append(skipped_candidate(index, candidate, "provider_filter"))
            continue
        try:
            source = dataset_source_from_provider_candidate(candidate)
        except ValueError as exc:
            # 無法證明 crawler type / endpoint 的項目留在 review，避免把 landing page 誤當可爬來源。
            skipped.append(skipped_candidate(index, candidate, str(exc)))
            continue
        append_dataset_discovery_source(output_path, source)
        written.append(source_to_dict(source))

    return {
        "schema_version": 1,
        "role": "local dataset discovery source drafts from provider candidate review; ignored local config only",
        "candidate_count": len(candidates),
        "provider_filter": sorted(provider_filter),
        "source_draft_count": len(written),
        "skipped_count": len(skipped),
        "dataset_source_path": str(output_path),
        # source draft 只是 staging；summary 直接帶下一步，避免接力 agent 把它誤當成已通過 crawler audit。
        "next_action": LOCAL_DISCOVERY_AUDIT_NEXT_ACTION,
        "audit_command": LOCAL_DISCOVERY_AUDIT_COMMAND,
        "audit_source_ids": [str(source.get("source_id") or "") for source in written],
        "sources": written,
        "skipped": skipped,
    }


def skipped_candidate(index: int, candidate: Mapping[str, Any], reason: str) -> dict[str, object]:
    return {
        "index": index,
        "provider_id": clean_text(candidate.get("provider_id")),
        "name": clean_text(candidate.get("name")),
        "reason": reason,
    }


def first_supported_source_type(candidate: Mapping[str, object]) -> str:
    supported = set(SUPPORTED_DATASET_SOURCE_TYPES)
    for key in EXPLICIT_SOURCE_TYPE_KEYS:
        value = clean_text(candidate.get(key))
        if value in supported:
            return value
    return ""


def infer_source_type(url: str) -> str:
    # 只處理穩定且已經有 crawler handler 的公開 API 形狀；未知入口不做猜測，避免假成功。
    normalized = url.lower()
    for source_type, matches in SOURCE_TYPE_INFERENCE_RULES:
        if matches(normalized):
            return source_type
    return ""


def url_matches_ckan_package_search(normalized_url: str) -> bool:
    return "package_search" in normalized_url or "/api/3/action" in normalized_url or "/api/action" in normalized_url


def url_matches_socrata_catalog_search(normalized_url: str) -> bool:
    return "api.us.socrata.com/api/catalog" in normalized_url or "/api/catalog/v1" in normalized_url


def url_matches_gbif_dataset_search(normalized_url: str) -> bool:
    return "api.gbif.org" in normalized_url and "/dataset" in normalized_url


def url_matches_cmr_collections(normalized_url: str) -> bool:
    return "cmr.earthdata.nasa.gov/search" in normalized_url


def url_matches_stac_collections(normalized_url: str) -> bool:
    return "stac" in normalized_url


def url_matches_erddap_all_datasets(normalized_url: str) -> bool:
    return "erddap" in normalized_url


def url_matches_dataverse_search(normalized_url: str) -> bool:
    return "/api/search" in normalized_url and "dataverse" in normalized_url


def url_matches_zenodo_records_search(normalized_url: str) -> bool:
    return "zenodo.org/api/records" in normalized_url


def url_matches_datacite_dois(normalized_url: str) -> bool:
    return "api.datacite.org/dois" in normalized_url


def url_matches_openalex_works_search(normalized_url: str) -> bool:
    return "api.openalex.org/works" in normalized_url


def url_matches_ogc_api_records(normalized_url: str) -> bool:
    return "collections" in normalized_url and "items" in normalized_url and normalized_url.startswith(("http://", "https://"))


def url_matches_ncei_search(normalized_url: str) -> bool:
    return "access/services/search/v1" in normalized_url and "ncei.noaa.gov" in normalized_url


SOURCE_TYPE_INFERENCE_RULES: tuple[tuple[str, UrlSourceTypePredicate], ...] = (
    ("ckan_package_search", url_matches_ckan_package_search),
    ("socrata_catalog_search", url_matches_socrata_catalog_search),
    ("gbif_dataset_search", url_matches_gbif_dataset_search),
    ("cmr_collections", url_matches_cmr_collections),
    ("stac_collections", url_matches_stac_collections),
    ("erddap_all_datasets", url_matches_erddap_all_datasets),
    ("dataverse_search", url_matches_dataverse_search),
    ("zenodo_records_search", url_matches_zenodo_records_search),
    ("datacite_dois", url_matches_datacite_dois),
    ("openalex_works_search", url_matches_openalex_works_search),
    ("ogc_api_records", url_matches_ogc_api_records),
    ("ncei_search", url_matches_ncei_search),
)


def normalize_endpoint_for_source_type(source_type: str, endpoint_url: str) -> str:
    # 保持這層很薄：UI/CLI 只丟 source_type，範式自己的 endpoint 規則留在 registry 內。
    parsed = urllib.parse.urlparse(endpoint_url)
    normalizer = SOURCE_ENDPOINT_NORMALIZERS.get(source_type)
    if normalizer:
        return normalizer(parsed)
    return endpoint_url


def normalize_stac_collections_endpoint(parsed: urllib.parse.ParseResult) -> str:
    path = parsed.path.rstrip("/")
    path_lower = path.lower()
    if not path_lower.endswith("/collections"):
        path = f"{path}/collections"
    return endpoint_with_path(parsed, path)


def normalize_ogc_api_records_endpoint(parsed: urllib.parse.ParseResult) -> str:
    path = parsed.path.rstrip("/")
    path_lower = path.lower()
    if "/collections" not in path_lower:
        path = f"{path}/collections"
    return endpoint_with_path(parsed, path)


def normalize_ogc_wms_capabilities_endpoint(parsed: urllib.parse.ParseResult) -> str:
    return ogc_wms_capabilities_url(urllib.parse.urlunparse(parsed))


def normalize_dataverse_search_endpoint(parsed: urllib.parse.ParseResult) -> str:
    path = parsed.path.rstrip("/")
    path_lower = path.lower()
    if not path_lower.endswith("/api/search"):
        path = f"{path}/api/search" if path else "/api/search"
    return endpoint_with_path(parsed, path)


def normalize_ncei_search_endpoint(parsed: urllib.parse.ParseResult) -> str:
    path = parsed.path.rstrip("/")
    path_lower = path.lower()
    marker = "/access/services/search/v1"
    if marker in path_lower:
        prefix = path[: path_lower.index(marker) + len(marker)]
        return endpoint_with_path(parsed, f"{prefix}/datasets")
    return endpoint_with_path(parsed, "/access/services/search/v1/datasets")


def normalize_cmr_collections_endpoint(parsed: urllib.parse.ParseResult) -> str:
    path = parsed.path.rstrip("/")
    if path.lower().endswith(("collections.json", "collections")):
        return endpoint_with_path(parsed, path)
    return endpoint_with_path(parsed, "/search/collections.json")


def normalize_erddap_all_datasets_endpoint(parsed: urllib.parse.ParseResult) -> str:
    path = parsed.path.rstrip("/")
    path_lower = path.lower()
    if "/erddap" in path_lower:
        erddap_end = path_lower.index("/erddap") + len("/erddap")
        erddap_root = parsed.path[:erddap_end]
    else:
        erddap_root = path + "/erddap"
    normalized_path = erddap_root.rstrip("/") + "/tabledap/allDatasets.json"
    query = "datasetID,title,summary,institution,cdm_data_type,griddap,tabledap,wms,fgdc,iso19115,infoUrl"
    return endpoint_with_path(parsed, normalized_path, query=query)


def endpoint_with_path(parsed: urllib.parse.ParseResult, path: str, query: str = "") -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return urllib.parse.urlunparse(parsed._replace(path=normalized_path, query=query, fragment=""))


def normalize_gbif_dataset_search_endpoint(parsed: urllib.parse.ParseResult) -> str:
    return endpoint_with_path(parsed, "/v1/dataset/search")


def normalize_zenodo_records_search_endpoint(parsed: urllib.parse.ParseResult) -> str:
    return endpoint_with_path(parsed, "/api/records")


def normalize_datacite_dois_endpoint(parsed: urllib.parse.ParseResult) -> str:
    return endpoint_with_path(parsed, "/dois")


def normalize_openalex_works_search_endpoint(parsed: urllib.parse.ParseResult) -> str:
    return endpoint_with_path(parsed, "/works")


def normalize_ckan_package_search_endpoint(parsed: urllib.parse.ParseResult) -> str:
    path = parsed.path.rstrip("/")
    path_lower = path.lower()
    for action_root in ("/api/3/action", "/api/action"):
        marker = f"{action_root}/"
        if path_lower == action_root:
            return urllib.parse.urlunparse(parsed._replace(path=f"{path}/package_search", query="", fragment=""))
        if marker in path_lower:
            prefix = path[: path_lower.index(marker) + len(action_root)]
            return urllib.parse.urlunparse(parsed._replace(path=f"{prefix}/package_search", query="", fragment=""))
    return urllib.parse.urlunparse(parsed._replace(path="/api/3/action/package_search", query="", fragment=""))


def normalize_socrata_catalog_endpoint(parsed: urllib.parse.ParseResult) -> str:
    query_values = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    domain = clean_text((query_values.get("domains") or [""])[0])
    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    host = re.sub(r"^www\.", "", host)
    if not domain and host != "api.us.socrata.com":
        domain = host
    query = urllib.parse.urlencode({"domains": domain}) if domain else ""
    return urllib.parse.urlunparse(
        parsed._replace(
            scheme="https",
            netloc="api.us.socrata.com",
            path="/api/catalog/v1",
            query=query,
            fragment="",
        )
    )


SOURCE_ENDPOINT_NORMALIZERS: dict[str, SourceEndpointNormalizer] = {
    "stac_collections": normalize_stac_collections_endpoint,
    "ogc_api_records": normalize_ogc_api_records_endpoint,
    "ogc_wms_capabilities": normalize_ogc_wms_capabilities_endpoint,
    "gbif_dataset_search": normalize_gbif_dataset_search_endpoint,
    "dataverse_search": normalize_dataverse_search_endpoint,
    "zenodo_records_search": normalize_zenodo_records_search_endpoint,
    "datacite_dois": normalize_datacite_dois_endpoint,
    "openalex_works_search": normalize_openalex_works_search_endpoint,
    "ncei_search": normalize_ncei_search_endpoint,
    "ckan_package_search": normalize_ckan_package_search_endpoint,
    "socrata_catalog_search": normalize_socrata_catalog_endpoint,
    "cmr_collections": normalize_cmr_collections_endpoint,
    "erddap_all_datasets": normalize_erddap_all_datasets_endpoint,
}


def clean_text(value: object) -> str:
    return str(value or "").strip()


def first_text(candidate: Mapping[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = clean_text(candidate.get(key))
        if value:
            return value
    return ""


def tuple_from_candidate(candidate: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = candidate.get(key)
    if isinstance(value, str):
        parts = re.split(r"[,;]+", value)
        return tuple(clean_text(part) for part in parts if clean_text(part))
    if isinstance(value, (list, tuple)):
        return tuple(clean_text(item) for item in value if clean_text(item))
    return ()


def int_value(value: object, default: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        return default
    return max(parsed, 1)
