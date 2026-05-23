from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Callable

from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.downloads.eligibility import DownloadEligibility
from api_launcher.models import Dataset
from api_launcher.plans import dataset_download_target_path, dataset_import_plan_entry


FirstText = Callable[..., str]
FetchJson = Callable[[str], dict[str, object]]
EligibilityFromOption = Callable[[DatasetVersionOption], DownloadEligibility]

ERDDAP_RESOLVER_ID = "erddap_bounded_sample_query_resolver"
ERDDAP_SAMPLE_LIMIT = 25


def erddap_bounded_sample_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
    *,
    fetch_json: FetchJson,
    first_text: FirstText,
    eligibility_from_option: EligibilityFromOption,
    resolver_id: str = ERDDAP_RESOLVER_ID,
    sample_limit: int = ERDDAP_SAMPLE_LIMIT,
) -> dict[str, object]:
    # ERDDAP tabledap/griddap 可以代表很大的資料格；這裡先讀 info/index.json 產生 bounded sample。
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    protocols = option_metadata.get("erddap_protocols") if isinstance(option_metadata.get("erddap_protocols"), dict) else {}
    source_format = str(entry.get("source_format") or option_metadata.get("native_format") or "").strip().lower()
    if source_format != "erddap" and not protocols:
        return {}

    dataset_id = first_text(option_metadata.get("erddap_dataset_id"), entry.get("dataset_id"), version_meta.get("dataset_id"))
    protocol_name, protocol_url = erddap_protocol_url(entry, protocols, version_meta, first_text=first_text)
    if not dataset_id or not protocol_url or protocol_name not in {"tabledap", "griddap"}:
        return {}

    info_url = erddap_info_url(protocol_url, dataset_id)
    if not info_url:
        return {}
    try:
        info = fetch_json(info_url)
    except Exception:
        # API lookup 失敗時維持 adapter review，避免暫時性網路問題被誤升級成 direct plan。
        return {}
    dimensions, variables = erddap_info_dimensions_and_variables(info)
    sample_url = erddap_sample_csv_url(protocol_url, protocol_name, dimensions, variables, sample_limit=sample_limit)
    if not sample_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), dataset_id)
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-erddap-sample" if version else "erddap-sample"
    data_family = str(option_metadata.get("data_family") or entry.get("data_type") or "table_or_grid_sample")
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
        native_format="csv",
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
                "protocol": protocol_name,
                "info_url": info_url,
                "sample_limit": sample_limit,
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
        metadata={"native_format": "csv", "resolver_id": resolver_id, "protocol": protocol_name},
    )
    eligibility = eligibility_from_option(option)
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
                "resolver_id": resolver_id,
                "original_plan_index": plan_index,
                "protocol": protocol_name,
                "info_url": info_url,
                "policy": "bounded_sample_only",
                "sample_limit": sample_limit,
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
    *,
    first_text: FirstText,
) -> tuple[str, str]:
    for name in ("tabledap", "griddap"):
        raw_url = first_text(protocols.get(name))
        if raw_url:
            return name, absolute_erddap_url(raw_url, entry, version_meta, first_text=first_text)
    raw_download = first_text(version_meta.get("download_url"), entry.get("adapter_review_url"), entry.get("api_base_url"))
    lowered = raw_download.lower()
    if "/tabledap/" in lowered:
        return "tabledap", absolute_erddap_url(raw_download, entry, version_meta, first_text=first_text)
    if "/griddap/" in lowered:
        return "griddap", absolute_erddap_url(raw_download, entry, version_meta, first_text=first_text)
    return "", ""


def absolute_erddap_url(
    raw_url: str,
    entry: dict[str, object],
    version_meta: dict[str, object],
    *,
    first_text: FirstText,
) -> str:
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


def erddap_sample_csv_url(
    protocol_url: str,
    protocol_name: str,
    dimensions: list[str],
    variables: list[str],
    *,
    sample_limit: int = ERDDAP_SAMPLE_LIMIT,
) -> str:
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
    return f"{clean_url}.csv?{query}&.limit={sample_limit}"


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
