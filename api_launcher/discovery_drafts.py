from __future__ import annotations

import re
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from api_launcher.crawlers.dataset_sources import (
    SUPPORTED_DATASET_SOURCE_TYPES,
    append_dataset_discovery_source,
    source_to_dict,
)
from api_launcher.crawlers.types import DatasetDiscoverySource


EXPLICIT_SOURCE_TYPE_KEYS = ("dataset_source_type", "source_type", "crawler_source_type")
ENDPOINT_URL_KEYS = ("dataset_source_endpoint_url", "endpoint_url", "api_base_url", "source_url", "docs_url")
LOCAL_DISCOVERY_AUDIT_NEXT_ACTION = "run_local_discovery_audit_before_catalog_promotion"
LOCAL_DISCOVERY_AUDIT_COMMAND = (
    "python APIkeys_collection.py --promote-local-discovery-catalog "
    "--promote-local-discovery-dry-run --write-local-discovery-audit-json state/local_discovery_audit.json"
)


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
    if "package_search" in normalized or "/api/3/action" in normalized or "/api/action" in normalized:
        return "ckan_package_search"
    if "api.us.socrata.com/api/catalog" in normalized or "/api/catalog/v1" in normalized:
        return "socrata_catalog_search"
    if "api.gbif.org" in normalized and "/dataset" in normalized:
        return "gbif_dataset_search"
    if "cmr.earthdata.nasa.gov/search" in normalized:
        return "cmr_collections"
    if "stac" in normalized:
        return "stac_collections"
    if "erddap" in normalized:
        return "erddap_all_datasets"
    if "/api/search" in normalized and "dataverse" in normalized:
        return "dataverse_search"
    if "zenodo.org/api/records" in normalized:
        return "zenodo_records_search"
    if "api.datacite.org/dois" in normalized:
        return "datacite_dois"
    if "api.openalex.org/works" in normalized:
        return "openalex_works_search"
    if "collections" in normalized and "items" in normalized and normalized.startswith(("http://", "https://")):
        return "ogc_api_records"
    if "access/services/search/v1" in normalized and "ncei.noaa.gov" in normalized:
        return "ncei_search"
    return ""


def normalize_endpoint_for_source_type(source_type: str, endpoint_url: str) -> str:
    # 常見 provider API base 會停在 catalog root；這裡只補已知 crawler 需要的固定 endpoint。
    parsed = urllib.parse.urlparse(endpoint_url)
    base = endpoint_url.rstrip("/")
    lowered = endpoint_url.lower()
    if source_type == "stac_collections" and not lowered.rstrip("/").endswith("/collections"):
        return f"{base}/collections"
    if source_type == "gbif_dataset_search" and "/dataset/search" not in lowered:
        return urllib.parse.urlunparse(parsed._replace(path="/v1/dataset/search", query=""))
    if source_type == "ckan_package_search" and "package_search" not in lowered:
        path = parsed.path.rstrip("/")
        if path.endswith("/api/3/action") or path.endswith("/api/action"):
            return urllib.parse.urlunparse(parsed._replace(path=f"{path}/package_search"))
    if source_type == "cmr_collections" and not lowered.endswith(("collections.json", "collections")):
        return urllib.parse.urlunparse(parsed._replace(path="/search/collections.json", query=""))
    if source_type == "erddap_all_datasets" and "alldatasets" not in lowered:
        path = parsed.path.rstrip("/") + "/tabledap/allDatasets.json"
        query = "datasetID,title,summary,institution,cdm_data_type,griddap,tabledap,wms,fgdc,iso19115,infoUrl"
        return urllib.parse.urlunparse(parsed._replace(path=path, query=query))
    return endpoint_url


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
