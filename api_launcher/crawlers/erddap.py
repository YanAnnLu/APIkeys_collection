from __future__ import annotations

from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.fetch import fetch_json
from api_launcher.crawlers.metadata import (
    analysis_hint_for_family,
    infer_data_family,
    merge_categories,
    safe_dataset_id,
    sql_role_for_family,
    storage_hint_for_family,
    viewer_hint_for_family,
)
from api_launcher.crawlers.registry import crawler
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


def erddap_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
    search_terms: tuple[str, ...],
) -> list[DatasetCandidate]:
    # ERDDAP allDatasets 回傳的是資料集目錄；bounded CSV sample 由 adapter resolver 產生。
    table = payload.get("table")
    if not isinstance(table, dict):
        raise ValueError("ERDDAP allDatasets payload missing table object")
    column_names = table.get("columnNames", [])
    if not isinstance(column_names, list):
        raise ValueError("ERDDAP allDatasets payload missing table.columnNames list")
    columns = [str(value) for value in column_names]
    rows = table.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("ERDDAP allDatasets payload missing table.rows list")
    candidates: list[DatasetCandidate] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        # ERDDAP rows 是欄位陣列；先轉成 dict，後續欄位取值才不依賴順序。
        item = {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
        searchable = " ".join(str(item.get(key) or "") for key in ("datasetID", "title", "summary", "institution")).lower()
        if search_terms and not any(term.lower() in searchable for term in search_terms):
            continue
        dataset_id = safe_dataset_id(str(item.get("datasetID") or "dataset"))
        title = str(item.get("title") or dataset_id)
        data_family = infer_data_family(searchable)
        api_url = str(item.get("griddap") or item.get("tabledap") or item.get("infoUrl") or source_url)
        # griddap/tabledap 只代表可查 API，不代表可直接下載完整資料。
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


def erddap_candidates_for_source(
    source: DatasetDiscoverySource,
    timeout: float,
    limit: int,
    search_terms: tuple[str, ...],
) -> list[DatasetCandidate]:
    # ERDDAP allDatasets JSON 已是目錄端點；這層只負責抓取後交給 parser。
    payload = fetch_json(source.endpoint_url, timeout=timeout)
    return erddap_candidates_from_payload(source, payload, source.endpoint_url, limit, search_terms)


@crawler(
    source_type="erddap_all_datasets",
    source_family="catalog_index",
    transport="json",
    auth_profile="none",
    result_shape="dataset_list",
    supports_full_crawl=False,
)
def erddap_source_crawler(
    source: DatasetDiscoverySource,
    timeout: float,
    limit: int,
    search_terms: tuple[str, ...],
    _full_crawl: bool,
    _max_pages: int,
) -> list[DatasetCandidate]:
    # The registry expects the common six-argument crawler signature.  ERDDAP
    # itself is still a single endpoint, so full_crawl/max_pages are ignored.
    return erddap_candidates_for_source(source, timeout, limit, search_terms)
