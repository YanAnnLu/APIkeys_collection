from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.discovery import extract_links
from api_launcher.models import Dataset


USER_AGENT = "APIkeys_collection/0.4 (+dataset-discovery; metadata only)"
DEFAULT_DATASET_DISCOVERY_SOURCES_NAME = "dataset_discovery_sources.json"


@dataclass(frozen=True)
class DatasetDiscoverySource:
    source_id: str
    provider_id: str
    name: str
    source_type: str
    endpoint_url: str
    docs_url: str = ""
    search_terms: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    geographic_scope: str = "global"
    max_results: int = 10
    dataset_id: str = ""
    dataset_title: str = ""
    data_type: str = ""
    native_format: str = ""
    file_url_regex: str = ""
    notes: str = ""


@dataclass(frozen=True)
class DatasetCandidate:
    dataset: Dataset
    source_id: str
    source_type: str
    source_url: str
    confidence: float
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "dataset": dataset_to_dict(self.dataset),
        }


def load_dataset_discovery_sources(path: str | Path) -> list[DatasetDiscoverySource]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        DatasetDiscoverySource(
            source_id=str(item["source_id"]).strip(),
            provider_id=str(item["provider_id"]).strip(),
            name=str(item["name"]).strip(),
            source_type=str(item["source_type"]).strip(),
            endpoint_url=str(item["endpoint_url"]).strip(),
            docs_url=str(item.get("docs_url") or "").strip(),
            search_terms=tuple(str(value).strip() for value in item.get("search_terms", []) if str(value).strip()),
            categories=tuple(str(value).strip() for value in item.get("categories", []) if str(value).strip()),
            geographic_scope=str(item.get("geographic_scope") or "global").strip(),
            max_results=int(item.get("max_results") or 10),
            dataset_id=str(item.get("dataset_id") or "").strip(),
            dataset_title=str(item.get("dataset_title") or "").strip(),
            data_type=str(item.get("data_type") or "").strip(),
            native_format=str(item.get("native_format") or "").strip(),
            file_url_regex=str(item.get("file_url_regex") or "").strip(),
            notes=str(item.get("notes") or "").strip(),
        )
        for item in data.get("sources", [])
    ]


def discover_dataset_candidates(
    sources: list[DatasetDiscoverySource],
    timeout: float = 12.0,
    max_results_override: int = 0,
    search_terms_override: tuple[str, ...] = (),
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        source_candidates = discover_dataset_candidates_for_source(
            source,
            timeout=timeout,
            max_results_override=max_results_override,
            search_terms_override=search_terms_override,
        )
        for candidate in source_candidates:
            key = (candidate.dataset.provider_id, candidate.dataset.dataset_id)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def discover_dataset_candidates_for_source(
    source: DatasetDiscoverySource,
    timeout: float = 12.0,
    max_results_override: int = 0,
    search_terms_override: tuple[str, ...] = (),
) -> list[DatasetCandidate]:
    limit = max_results_override or source.max_results
    search_terms = search_terms_override or source.search_terms
    if source.source_type == "ncei_search":
        candidates: list[DatasetCandidate] = []
        for term in search_terms or ("",):
            url = ncei_search_url(source.endpoint_url, term, limit)
            payload = fetch_json(url, timeout=timeout)
            candidates.extend(ncei_candidates_from_payload(source, payload, url, limit))
        return candidates
    if source.source_type == "erddap_all_datasets":
        payload = fetch_json(source.endpoint_url, timeout=timeout)
        return erddap_candidates_from_payload(source, payload, source.endpoint_url, limit, search_terms)
    if source.source_type == "html_file_index":
        text, final_url = fetch_text(source.endpoint_url, timeout=timeout)
        return html_file_index_candidates_from_text(source, text, final_url, limit)
    raise ValueError(f"Unsupported dataset discovery source_type: {source.source_type}")


def ncei_search_url(endpoint_url: str, search_term: str, limit: int) -> str:
    params = {"limit": str(max(1, limit)), "available": "true"}
    if search_term:
        params["text"] = search_term
    separator = "&" if urllib.parse.urlparse(endpoint_url).query else "?"
    return endpoint_url + separator + urllib.parse.urlencode(params)


def ncei_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    for item in payload.get("results", [])[:limit]:
        if not isinstance(item, dict):
            continue
        dataset_id = safe_dataset_id(str(item.get("id") or item.get("fileId") or item.get("name") or "dataset"))
        title = str(item.get("name") or dataset_id)
        description = str(item.get("description") or "")
        formats = tuple_names(item.get("formats"))
        observation_types = tuple_names(item.get("observationTypes"))
        keyword_names = tuple_names(item.get("keywords"))
        categories = merge_categories(source.categories, formats[:3], observation_types[:3])
        data_family = infer_data_family(" ".join((title, description, " ".join(categories), " ".join(keyword_names))))
        links = item.get("links") if isinstance(item.get("links"), dict) else {}
        landing_url = first_link_url(links, ("other", "documentation", "access")) or source.docs_url or source_url
        api_url = first_link_url(links, ("access",)) or source_url
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=categories or ("discovered",),
            data_type=data_family,
            native_format=choose_native_format(formats),
            geographic_scope=source.geographic_scope,
            temporal_coverage=temporal_coverage(item.get("startDate"), item.get("endDate")),
            landing_url=landing_url,
            api_url=api_url,
            version="discovered",
            metadata={
                "candidate_status": "needs_review",
                "discovery_source_id": source.source_id,
                "discovery_source_type": source.source_type,
                "source_url": source_url,
                "provider_backed": True,
                "data_family": data_family,
                "storage_hint": storage_hint_for_family(data_family),
                "sql_role": sql_role_for_family(data_family),
                "analysis_hint": analysis_hint_for_family(data_family),
                "viewer_hint": viewer_hint_for_family(data_family),
                "ncei_result_id": item.get("id") or "",
                "ncei_file_id": item.get("fileId") or "",
                "formats": formats,
                "observation_types": observation_types,
                "keyword_names": keyword_names[:12],
                "links": links,
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.82,
                evidence=("NCEI search result", f"formats: {', '.join(formats) or 'unknown'}"),
            )
        )
    return candidates


def erddap_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
    search_terms: tuple[str, ...],
) -> list[DatasetCandidate]:
    table = payload.get("table") if isinstance(payload.get("table"), dict) else {}
    columns = [str(value) for value in table.get("columnNames", [])]
    rows = table.get("rows", [])
    candidates: list[DatasetCandidate] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        item = {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
        searchable = " ".join(str(item.get(key) or "") for key in ("datasetID", "title", "summary", "institution")).lower()
        if search_terms and not any(term.lower() in searchable for term in search_terms):
            continue
        dataset_id = safe_dataset_id(str(item.get("datasetID") or "dataset"))
        title = str(item.get("title") or dataset_id)
        data_family = infer_data_family(searchable)
        api_url = str(item.get("griddap") or item.get("tabledap") or item.get("infoUrl") or source_url)
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, (str(item.get("cdm_data_type") or ""),)),
            data_type=data_family,
            native_format="erddap",
            geographic_scope=source.geographic_scope,
            landing_url=str(item.get("infoUrl") or source.docs_url or source_url),
            api_url=api_url,
            version="discovered",
            metadata={
                "candidate_status": "needs_review",
                "discovery_source_id": source.source_id,
                "discovery_source_type": source.source_type,
                "source_url": source_url,
                "provider_backed": True,
                "data_family": data_family,
                "storage_hint": storage_hint_for_family(data_family),
                "sql_role": sql_role_for_family(data_family),
                "analysis_hint": analysis_hint_for_family(data_family),
                "viewer_hint": viewer_hint_for_family(data_family),
                "erddap_dataset_id": item.get("datasetID") or "",
                "erddap_protocols": {
                    "griddap": item.get("griddap") or "",
                    "tabledap": item.get("tabledap") or "",
                    "wms": item.get("wms") or "",
                },
                "summary": item.get("summary") or "",
                "institution": item.get("institution") or "",
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.86,
                evidence=("ERDDAP allDatasets row",),
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def html_file_index_candidates_from_text(
    source: DatasetDiscoverySource,
    text: str,
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    if not source.file_url_regex:
        return []
    pattern = re.compile(source.file_url_regex)
    versions: list[dict[str, object]] = []
    seen: set[str] = set()
    for link in extract_links(text, source_url):
        filename = Path(urllib.parse.urlparse(link).path).name
        match = pattern.search(filename) or pattern.search(link)
        if not match or link in seen:
            continue
        seen.add(link)
        version = match.groupdict().get("version") if match.groupdict() else ""
        versions.append(
            {
                "label": filename,
                "version": version or filename,
                "version_status": "discovered_file_shard",
                "download_url": link,
                "landing_url": source.docs_url or source_url,
                "update_strategy": "append_or_partition_by_discovered_shard",
                "notes": "Discovered from an HTML file index; review size and scope before bulk download.",
            }
        )
        if len(versions) >= limit:
            break
    if not versions:
        return []
    dataset_id = safe_dataset_id(source.dataset_id or source.source_id)
    data_family = infer_data_family(" ".join((source.dataset_title, source.data_type, " ".join(source.categories))))
    dataset = Dataset(
        dataset_uid=dataset_uid(source.provider_id, dataset_id),
        provider_id=source.provider_id,
        dataset_id=dataset_id,
        title=source.dataset_title or source.name,
        categories=source.categories or ("discovered",),
        data_type=source.data_type or data_family,
        native_format=source.native_format,
        geographic_scope=source.geographic_scope,
        landing_url=source.docs_url or source_url,
        api_url=str(versions[0]["download_url"]),
        version=str(versions[0]["version"]),
        metadata={
            "candidate_status": "needs_review",
            "discovery_source_id": source.source_id,
            "discovery_source_type": source.source_type,
            "source_url": source_url,
            "provider_backed": True,
            "data_family": data_family,
            "storage_hint": storage_hint_for_family(data_family),
            "sql_role": sql_role_for_family(data_family),
            "analysis_hint": analysis_hint_for_family(data_family),
            "viewer_hint": viewer_hint_for_family(data_family),
            "available_versions": versions,
            "chunking_hint": "file_shard_index",
            "notes": source.notes,
        },
    )
    return [
        DatasetCandidate(
            dataset=dataset,
            source_id=source.source_id,
            source_type=source.source_type,
            source_url=source_url,
            confidence=0.8,
            evidence=(f"matched {len(versions)} file links",),
        )
    ]


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    text, _ = fetch_text(url, timeout=timeout)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return payload


def fetch_text(url: str, timeout: float) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()
    return data.decode(charset, errors="replace"), final_url


def dataset_to_dict(dataset: Dataset) -> dict[str, object]:
    return {
        "dataset_uid": dataset.dataset_uid,
        "provider_id": dataset.provider_id,
        "dataset_id": dataset.dataset_id,
        "title": dataset.title,
        "categories": list(dataset.categories),
        "data_type": dataset.data_type,
        "native_format": dataset.native_format,
        "geographic_scope": dataset.geographic_scope,
        "temporal_coverage": dataset.temporal_coverage,
        "landing_url": dataset.landing_url,
        "api_url": dataset.api_url,
        "license_url": dataset.license_url,
        "version": dataset.version,
        "remote_updated_at": dataset.remote_updated_at,
        "remote_etag": dataset.remote_etag,
        "remote_hash": dataset.remote_hash,
        "metadata": dataset.metadata,
    }


def safe_dataset_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().lower()).strip("_")
    return cleaned or "dataset"


def tuple_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("id") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return tuple(names)


def merge_categories(*groups: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            normalized = safe_dataset_id(value).replace("-", "_")
            if normalized and normalized not in seen:
                values.append(normalized)
                seen.add(normalized)
    return tuple(values)


def first_link_url(links: object, groups: tuple[str, ...]) -> str:
    if not isinstance(links, dict):
        return ""
    for group in groups:
        values = links.get(group)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict) and item.get("url"):
                return str(item["url"])
    return ""


def choose_native_format(formats: tuple[str, ...]) -> str:
    preferred = ("csv", "json", "netcdf", "grib", "shapefile", "geojson", "native")
    lowered = {value.lower(): value.lower() for value in formats}
    for value in preferred:
        if value in lowered:
            return lowered[value]
    return formats[0].lower() if formats else "unknown"


def temporal_coverage(start: object, end: object) -> str:
    start_text = str(start or "").strip()
    end_text = str(end or "").strip()
    if start_text and end_text:
        return f"{start_text}/{end_text}"
    return start_text or end_text


def infer_data_family(text: str) -> str:
    lowered = text.lower()
    if any(value in lowered for value in ("ais", "vessel", "trajectory", "ship")):
        return "spatiotemporal_trajectory"
    if any(value in lowered for value in ("cloud", "imagery", "satellite", "raster", "abi", "goes")):
        return "raster_or_grid"
    if any(value in lowered for value in ("netcdf", "grib", "grid", "sst", "sea surface temperature")):
        return "grid_or_array"
    if any(value in lowered for value in ("boundary", "polygon", "shapefile", "geojson", "gis")):
        return "gis"
    if any(value in lowered for value in ("hourly", "daily", "time series", "timeseries")):
        return "timeseries"
    return "table_or_document"


def storage_hint_for_family(data_family: str) -> str:
    hints = {
        "spatiotemporal_trajectory": "filesystem_or_object_storage_then_partitioned_columnar_store",
        "raster_or_grid": "netcdf_zarr_cog_or_object_storage",
        "grid_or_array": "netcdf_zarr_hdf5_or_object_storage",
        "gis": "geopackage_geojson_shapefile_or_postgis",
        "timeseries": "timeseries_db_or_partitioned_files",
    }
    return hints.get(data_family, "filesystem_or_sql_after_review")


def sql_role_for_family(data_family: str) -> str:
    if data_family in {"spatiotemporal_trajectory", "raster_or_grid", "grid_or_array", "gis"}:
        return "metadata_index_or_curated_sample_table"
    return "primary_or_curated_table_after_review"


def analysis_hint_for_family(data_family: str) -> str:
    hints = {
        "spatiotemporal_trajectory": "duckdb_geopandas_postgis_dask_spark",
        "raster_or_grid": "xarray_rioxarray_dask_or_gdal",
        "grid_or_array": "xarray_dask_or_netcdf_tools",
        "gis": "qgis_postgis_geopandas",
        "timeseries": "duckdb_timescaledb_clickhouse",
    }
    return hints.get(data_family, "python_sql_or_domain_adapter")


def viewer_hint_for_family(data_family: str) -> str:
    hints = {
        "spatiotemporal_trajectory": "map_trajectory_heatmap_or_timeline",
        "raster_or_grid": "globe_texture_or_time_animation",
        "grid_or_array": "map_layer_or_timeseries_preview",
        "gis": "map_layer_or_unreal_globe_overlay",
        "timeseries": "tradingview_like_chart",
    }
    return hints.get(data_family, "table_or_document_preview")
