from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from api_launcher.crawlers.ckan import (
    ckan_candidates_for_source,
    ckan_candidates_from_payload,
    ckan_package_search_url,
    paginated_ckan_candidates,
)
from api_launcher.crawlers.cmr import (
    cmr_candidates_for_source,
    cmr_candidates_from_payload,
    cmr_collections_url,
    cmr_payload_entries,
    paginated_cmr_candidates,
)
from api_launcher.crawlers.datacite import (
    datacite_candidates_for_source,
    datacite_candidates_from_payload,
    datacite_dois_search_url,
    datacite_payload_items,
    paginated_datacite_candidates,
)
from api_launcher.crawlers.dataverse import (
    dataverse_candidates_for_source,
    dataverse_candidates_from_payload,
    dataverse_search_url,
    paginated_dataverse_candidates,
)
from api_launcher.crawlers.erddap import erddap_candidates_for_source, erddap_candidates_from_payload
from api_launcher.crawlers.gbif import (
    gbif_candidates_for_source,
    gbif_candidates_from_payload,
    gbif_dataset_search_url,
    paginated_gbif_candidates,
)
from api_launcher.crawlers.html_index import (
    html_file_index_candidates_for_source,
    html_file_index_candidates_from_text,
)
from api_launcher.crawlers.ncei import (
    ncei_candidates_for_source,
    ncei_candidates_from_payload,
    ncei_search_url,
    paginated_ncei_candidates,
)
from api_launcher.crawlers.ogc_records import (
    ogc_records_candidates_for_source,
    ogc_records_candidates_from_payload,
    ogc_records_search_url,
    paginated_ogc_records_candidates,
)
from api_launcher.crawlers.ogc_wms import (
    ogc_wms_candidates_for_source,
    ogc_wms_candidates_from_xml,
    ogc_wms_capabilities_url,
)
from api_launcher.crawlers.openalex import (
    openalex_candidates_for_source,
    openalex_candidates_from_payload,
    openalex_payload_items,
    openalex_works_search_url,
    paginated_openalex_candidates,
)
from api_launcher.crawlers.pagination import MAX_FULL_CRAWL_PAGES, append_new_candidates, discovery_page_cap
from api_launcher.crawlers.socrata import (
    paginated_socrata_catalog_candidates,
    socrata_catalog_candidates_for_source,
    socrata_catalog_candidates_from_payload,
    socrata_catalog_search_url,
)
from api_launcher.crawlers.stac import (
    paginated_stac_candidates,
    stac_candidates_for_source,
    stac_candidates_from_payload,
    stac_next_link,
)
from api_launcher.crawlers.types import (
    DatasetCandidate,
    DatasetDiscoverySource,
    dataset_to_dict,
    dataset_with_candidate_metadata,
)
from api_launcher.crawlers.zenodo import (
    paginated_zenodo_candidates,
    zenodo_candidates_for_source,
    zenodo_candidates_from_payload,
    zenodo_records_search_url,
)


DEFAULT_DATASET_DISCOVERY_SOURCES_NAME = "dataset_discovery_sources.json"
LOCAL_DATASET_DISCOVERY_SOURCES_NAME = "dataset_discovery_sources.local.json"
DEFAULT_FULL_CRAWL_PAGE_SIZE = 100
DatasetSourceCrawler = Callable[
    [DatasetDiscoverySource, float, int, tuple[str, ...], bool, int],
    list[DatasetCandidate],
]


def _erddap_source_crawler(
    source: DatasetDiscoverySource,
    timeout: float,
    limit: int,
    search_terms: tuple[str, ...],
    _full_crawl: bool,
    _max_pages: int,
) -> list[DatasetCandidate]:
    # ERDDAP allDatasets 是單頁目錄型來源；full_crawl 參數在這裡沒有額外意義。
    return erddap_candidates_for_source(source, timeout, limit, search_terms)


def _html_file_index_source_crawler(
    source: DatasetDiscoverySource,
    timeout: float,
    limit: int,
    _search_terms: tuple[str, ...],
    full_crawl: bool,
    max_pages: int,
) -> list[DatasetCandidate]:
    # HTML index 沒有標準分頁；只在 full_crawl 時用 max_pages 跟同網域索引頁。
    return html_file_index_candidates_for_source(source, timeout, limit, full_crawl, max_pages=max_pages)


SOURCE_CRAWLER_HANDLERS: dict[str, DatasetSourceCrawler] = {
    # source_type 的唯一 dispatch 表；新增 crawler 時要從這裡接入，避免 portal intake 與 CLI 分歧。
    "ncei_search": ncei_candidates_for_source,
    "erddap_all_datasets": _erddap_source_crawler,
    "html_file_index": _html_file_index_source_crawler,
    "cmr_collections": cmr_candidates_for_source,
    "stac_collections": stac_candidates_for_source,
    "gbif_dataset_search": gbif_candidates_for_source,
    "dataverse_search": dataverse_candidates_for_source,
    "zenodo_records_search": zenodo_candidates_for_source,
    "ckan_package_search": ckan_candidates_for_source,
    "datacite_dois": datacite_candidates_for_source,
    "ogc_api_records": ogc_records_candidates_for_source,
    "ogc_wms_capabilities": ogc_wms_candidates_for_source,
    "socrata_catalog_search": socrata_catalog_candidates_for_source,
    "openalex_works_search": openalex_candidates_for_source,
}
SUPPORTED_DATASET_SOURCE_TYPES = tuple(SOURCE_CRAWLER_HANDLERS)


def load_dataset_discovery_sources(path: str | Path) -> list[DatasetDiscoverySource]:
    # catalog JSON 是人工可維護格式；載入時在這裡正規化型別與空白。
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
            min_expected_candidates=int(item.get("min_expected_candidates") if item.get("min_expected_candidates") is not None else 1),
            seed_discovery_mode=str(item.get("seed_discovery_mode") or "auto").strip() or "auto",
            notes=str(item.get("notes") or "").strip(),
        )
        for item in data.get("sources", [])
    ]


def load_all_dataset_discovery_sources(
    primary_path: str | Path,
    local_path: str | Path | None = None,
) -> list[DatasetDiscoverySource]:
    # built-in source 先載入，local source 後載入；source_id 重複時保留第一筆，避免本機覆蓋官方。
    paths = [Path(primary_path)]
    if local_path is not None:
        paths.append(Path(local_path))
    sources: list[DatasetDiscoverySource] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for source in load_dataset_discovery_sources(path):
            if source.source_id in seen:
                continue
            seen.add(source.source_id)
            sources.append(source)
    return sources


def append_dataset_discovery_source(path: str | Path, source: DatasetDiscoverySource) -> None:
    # 追加前先以 source_id 去重，讓 promotion script 可以重跑而不產生重複列。
    path = Path(path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"schema_version": 1, "sources": []}
    sources = [item for item in data.get("sources", []) if item.get("source_id") != source.source_id]
    sources.append(source_to_dict(source))
    data["sources"] = sorted(sources, key=lambda item: item["source_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def source_to_dict(source: DatasetDiscoverySource) -> dict[str, object]:
    # 寫回 JSON 時保持欄位順序穩定，降低 git diff 與人工 review 成本。
    payload = {
        "source_id": source.source_id,
        "provider_id": source.provider_id,
        "name": source.name,
        "source_type": source.source_type,
        "endpoint_url": source.endpoint_url,
        "docs_url": source.docs_url,
        "search_terms": list(source.search_terms),
        "categories": list(source.categories),
        "geographic_scope": source.geographic_scope,
        "max_results": source.max_results,
        "dataset_id": source.dataset_id,
        "dataset_title": source.dataset_title,
        "data_type": source.data_type,
        "native_format": source.native_format,
        "file_url_regex": source.file_url_regex,
        "min_expected_candidates": source.min_expected_candidates,
        "notes": source.notes,
    }
    if source.seed_discovery_mode != "auto":
        payload["seed_discovery_mode"] = source.seed_discovery_mode
    return payload


def discover_dataset_candidates(
    sources: list[DatasetDiscoverySource],
    timeout: float = 12.0,
    max_results_override: int = 0,
    search_terms_override: tuple[str, ...] = (),
    full_crawl: bool = False,
    max_pages: int = 0,
) -> list[DatasetCandidate]:
    # 跨來源 dedupe 用 provider_id + dataset_id，避免同一來源重複命中造成 UI 候選膨脹。
    candidates: list[DatasetCandidate] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        source_candidates = discover_dataset_candidates_for_source(
            source,
            timeout=timeout,
            max_results_override=max_results_override,
            search_terms_override=search_terms_override,
            full_crawl=full_crawl,
            max_pages=max_pages,
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
    full_crawl: bool = False,
    max_pages: int = 0,
) -> list[DatasetCandidate]:
    # full crawl 只在使用者明確要求時提高 page size；一般 demo 保持 bounded。
    limit = max_results_override or source.max_results
    if full_crawl and not max_results_override:
        limit = max(limit, DEFAULT_FULL_CRAWL_PAGE_SIZE)
    search_terms = search_terms_override or source.search_terms
    handler = SOURCE_CRAWLER_HANDLERS.get(source.source_type)
    if handler is not None:
        return handler(source, timeout, limit, search_terms, full_crawl, max_pages)
    # 不支援的 source_type 必須明確失敗，否則 portal intake 會以為 crawler 已接好。
    raise ValueError(f"Unsupported dataset discovery source_type: {source.source_type}")
