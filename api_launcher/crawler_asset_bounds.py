from __future__ import annotations

from dataclasses import dataclass

from api_launcher.crawlers.source_type_registry import HTML_FILE_INDEX_SOURCE_TYPE, source_uses_file_index
from api_launcher.crawlers.types import DatasetDiscoverySource


@dataclass(frozen=True)
class CrawlerAssetBoundFacet:
    """爬蟲資產界域欄位的前端中立描述。

    這一層不直接產生 Tk 控件，也不直接改寫下載 URL；它只說明某個
    source type 在建立下載計畫前，使用者可以或必須界定哪些條件。
    Tk、Qt、CLI wizard 都應該讀這份 schema，再轉成自己的輸入表單。
    """

    facet_id: str
    label_zh_TW: str
    label_en: str
    group: str
    control: str
    value_type: str = "text"
    maps_to: tuple[str, ...] = ()
    required: bool = False
    default: object = ""
    options: tuple[str, ...] = ()
    requires_schema_probe: bool = False
    help_zh_TW: str = ""
    help_en: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "facet_id": self.facet_id,
            "label_zh_TW": self.label_zh_TW,
            "label_en": self.label_en,
            "group": self.group,
            "control": self.control,
            "value_type": self.value_type,
            "maps_to": list(self.maps_to),
            "required": self.required,
            "default": self.default,
            "options": list(self.options),
            "requires_schema_probe": self.requires_schema_probe,
            "help_zh_TW": self.help_zh_TW,
            "help_en": self.help_en,
        }


FACET_DEFINITIONS: dict[str, CrawlerAssetBoundFacet] = {
    "search_terms": CrawlerAssetBoundFacet(
        facet_id="search_terms",
        label_zh_TW="搜尋詞",
        label_en="Search terms",
        group="QueryBounds",
        control="text_list",
        value_type="string_list",
        maps_to=("SourceDownloadBounds.search_terms",),
        help_zh_TW="限制入口清單擷取的關鍵詞；用於有界 seed，不代表完整資料庫。",
        help_en="Limits source listing by keywords; useful for bounded seed runs.",
    ),
    "max_results": CrawlerAssetBoundFacet(
        facet_id="max_results",
        label_zh_TW="候選數上限",
        label_en="Candidate limit",
        group="LimitBounds",
        control="integer",
        value_type="integer",
        maps_to=("SourceDownloadBounds.candidate_limit",),
        default=25,
        help_zh_TW="限制 crawler 回傳候選數，避免展示或 smoke 時把入口掃太大。",
        help_en="Limits crawler candidate output for bounded runs.",
    ),
    "max_pages": CrawlerAssetBoundFacet(
        facet_id="max_pages",
        label_zh_TW="頁數上限",
        label_en="Page limit",
        group="LimitBounds",
        control="integer",
        value_type="integer",
        maps_to=("SourceDownloadBounds.max_pages",),
        default=1,
        help_zh_TW="限制分頁 crawler 的頁數；0 代表交給後端預設策略。",
        help_en="Limits paginated crawler pages; 0 delegates to backend defaults.",
    ),
    "limit": CrawlerAssetBoundFacet(
        facet_id="limit",
        label_zh_TW="樣本 / 下載筆數上限",
        label_en="Sample/download limit",
        group="LimitBounds",
        control="integer",
        value_type="integer",
        maps_to=("SourceDownloadBounds.sample_limit",),
        default=25,
        help_zh_TW="第一輪下載先用小上限驗證資料形狀，再逐步放大。",
        help_en="Start with a small limit to validate data shape before expanding.",
    ),
    "granule_limit": CrawlerAssetBoundFacet(
        facet_id="granule_limit",
        label_zh_TW="Granule 上限",
        label_en="Granule limit",
        group="LimitBounds",
        control="integer",
        value_type="integer",
        maps_to=("SourceDownloadBounds.sample_limit",),
        default=1,
        help_zh_TW="NASA CMR 類來源先抓少量 granule metadata，再決定是否下載檔案資產。",
        help_en="For NASA CMR-like sources, probe a few granules before downloading assets.",
    ),
    "time": CrawlerAssetBoundFacet(
        facet_id="time",
        label_zh_TW="時間範圍",
        label_en="Time range",
        group="TimeBounds",
        control="datetime_range",
        value_type="datetime_range",
        maps_to=("SourceDownloadBounds.time_field", "SourceDownloadBounds.start_date", "SourceDownloadBounds.end_date"),
        requires_schema_probe=True,
        help_zh_TW="需要先知道資料欄位或 API 支援的時間參數，才能安全套用。",
        help_en="Requires schema/API knowledge before precise time filtering.",
    ),
    "bbox": CrawlerAssetBoundFacet(
        facet_id="bbox",
        label_zh_TW="空間邊界 bbox",
        label_en="Bounding box",
        group="SpatialBounds",
        control="bbox",
        value_type="bbox",
        maps_to=("SourceDownloadBounds.longitude_field", "SourceDownloadBounds.latitude_field", "SourceDownloadBounds.bbox"),
        requires_schema_probe=True,
        help_zh_TW="需要經緯度欄位或 API 支援 bbox，不能只憑資料集名稱猜測。",
        help_en="Requires lon/lat fields or an API-supported bbox parameter.",
    ),
    "columns": CrawlerAssetBoundFacet(
        facet_id="columns",
        label_zh_TW="欄位選擇 / 必要欄位",
        label_en="Columns / required fields",
        group="ColumnBounds",
        control="multiselect",
        value_type="column_names",
        maps_to=("SourceDownloadBounds.required_columns",),
        requires_schema_probe=True,
        help_zh_TW="先 head/probe 欄位後，再讓使用者選擇需要保留或驗證的欄位。",
        help_en="Requires a schema probe before users select required columns.",
    ),
    "version": CrawlerAssetBoundFacet(
        facet_id="version",
        label_zh_TW="版本",
        label_en="Version",
        group="VersionBounds",
        control="select_or_text",
        value_type="version",
        maps_to=("SourceDownloadOptions.selected_versions", "SourceDownloadBounds.version_limit"),
        default=1,
        help_zh_TW="版本選擇屬於 plan options；沒有明確版本時先保留版本上限。",
        help_en="Version selection belongs to plan options; fallback to version limit.",
    ),
    "file_pattern": CrawlerAssetBoundFacet(
        facet_id="file_pattern",
        label_zh_TW="檔名樣式",
        label_en="File pattern",
        group="VersionBounds",
        control="text",
        value_type="regex_or_glob",
        maps_to=("DatasetDiscoverySource.file_url_regex",),
        help_zh_TW="用於 HTML/file index 類入口，限制可列出的 shard 檔案。",
        help_en="Used by HTML/file-index sources to filter file shards.",
    ),
    "dataset": CrawlerAssetBoundFacet(
        facet_id="dataset",
        label_zh_TW="資料集 ID",
        label_en="Dataset ID",
        group="DatasetBounds",
        control="select_or_text",
        value_type="identifier",
        maps_to=("DatasetCandidate.dataset_id",),
        help_zh_TW="先由清單擷取得到 dataset id，再建立指定下載計畫。",
        help_en="Usually selected from listed dataset candidates before building a plan.",
    ),
    "collection": CrawlerAssetBoundFacet(
        facet_id="collection",
        label_zh_TW="Collection",
        label_en="Collection",
        group="DatasetBounds",
        control="select_or_text",
        value_type="identifier",
        maps_to=("DatasetCandidate.dataset_id",),
        help_zh_TW="STAC / CMR / OGC 類入口的 collection 選擇。",
        help_en="Collection selector for STAC / CMR / OGC-like sources.",
    ),
    "package": CrawlerAssetBoundFacet(
        facet_id="package",
        label_zh_TW="Package",
        label_en="Package",
        group="DatasetBounds",
        control="select_or_text",
        value_type="identifier",
        maps_to=("DatasetCandidate.dataset_id",),
        help_zh_TW="CKAN 類入口的 package 選擇。",
        help_en="Package selector for CKAN-like sources.",
    ),
    "resource": CrawlerAssetBoundFacet(
        facet_id="resource",
        label_zh_TW="Resource",
        label_en="Resource",
        group="DatasetBounds",
        control="select_or_text",
        value_type="identifier",
        maps_to=("DatasetVersionOption.download_url",),
        help_zh_TW="CKAN/resource 類資料中，選擇具體檔案或 API resource。",
        help_en="Specific file/API resource under a package-like dataset.",
    ),
    "station": CrawlerAssetBoundFacet(
        facet_id="station",
        label_zh_TW="測站",
        label_en="Station",
        group="SpatialBounds",
        control="text_list",
        value_type="identifier_list",
        maps_to=("provider_specific.station",),
        help_zh_TW="氣象、海洋或觀測資料常用的測站界域。",
        help_en="Station selector for weather/ocean/observation data.",
    ),
    "format": CrawlerAssetBoundFacet(
        facet_id="format",
        label_zh_TW="格式",
        label_en="Format",
        group="FormatBounds",
        control="select_or_text",
        value_type="format",
        maps_to=("DatasetVersionOption.source_format",),
        options=("csv", "json", "geojson", "netcdf", "geotiff", "zip"),
        help_zh_TW="優先選擇現有 importer 或 adapter 能處理的格式。",
        help_en="Prefer formats supported by existing importers or adapters.",
    ),
    "asset_role": CrawlerAssetBoundFacet(
        facet_id="asset_role",
        label_zh_TW="資產角色",
        label_en="Asset role",
        group="FormatBounds",
        control="select_or_text",
        value_type="string",
        maps_to=("DatasetVersionOption.metadata.asset_role",),
        options=("metadata", "data", "thumbnail", "browse", "science_file"),
        help_zh_TW="避免把 metadata/browse 圖誤當成正式科學資料下載。",
        help_en="Avoid treating metadata or browse assets as primary science files.",
    ),
    "where": CrawlerAssetBoundFacet(
        facet_id="where",
        label_zh_TW="查詢條件",
        label_en="Where clause",
        group="QueryBounds",
        control="text",
        value_type="query",
        maps_to=("provider_specific.where",),
        help_zh_TW="Socrata/OData 類來源可用，但必須維持有界與可審核。",
        help_en="For Socrata/OData-like sources; keep bounded and reviewable.",
    ),
    "auth_profile": CrawlerAssetBoundFacet(
        facet_id="auth_profile",
        label_zh_TW="憑證設定檔",
        label_en="Credential profile",
        group="AuthBounds",
        control="credential_profile",
        value_type="profile_id",
        maps_to=("CrawlerAssetProfile.credential_profile_id",),
        help_zh_TW="憑證屬於爬蟲資產設定，不屬於資料集本體；不得在表單中填入真實 secret。",
        help_en="Credentials belong to crawler asset profiles, not dataset rows; never enter raw secrets here.",
    ),
}


DEFAULT_BOUND_FACETS = ("limit",)
FILE_INDEX_BOUND_FACETS = ("version", "file_pattern", "limit")
METADATA_DATASET_BOUND_FACETS = ("dataset", "version", "format", "limit")
SOURCE_BOUND_FACETS: dict[str, tuple[str, ...]] = {
    # Frontend-neutral source of truth for crawler bounds forms.
    # UI layers render these facets instead of branching on source_type.
    HTML_FILE_INDEX_SOURCE_TYPE: FILE_INDEX_BOUND_FACETS,
    "stac_collections": ("collection", "time", "bbox", "asset_role", "limit"),
    "cmr_collections": ("collection", "time", "bbox", "granule_limit", "asset_role"),
    "erddap_all_datasets": ("dataset", "columns", "time", "bbox", "limit"),
    "ncei_search": ("dataset", "time", "bbox", "station", "format", "limit"),
    "socrata_catalog_search": ("dataset", "columns", "where", "time", "limit"),
    "ckan_package_search": ("package", "resource", "format", "limit"),
    "gbif_dataset_search": METADATA_DATASET_BOUND_FACETS,
    "dataverse_search": METADATA_DATASET_BOUND_FACETS,
    "zenodo_records_search": METADATA_DATASET_BOUND_FACETS,
    "datacite_dois": METADATA_DATASET_BOUND_FACETS,
    "openalex_works_search": METADATA_DATASET_BOUND_FACETS,
    "ogc_api_records": ("collection", "bbox", "time", "format", "limit"),
    "ogc_wms_capabilities": ("collection", "bbox", "time", "format", "limit"),
}


def bounds_schema_for_facets(
    facets: tuple[str, ...],
    *,
    credential_mode: str = "public_or_review",
) -> tuple[CrawlerAssetBoundFacet, ...]:
    """把簡短 facet id 轉成正式 bounds schema。

    未知 facet 仍保留為通用文字欄位，讓 UI 可以顯示「需要後端補規格」，
    而不是靜默丟失來源能力。
    """

    schema: list[CrawlerAssetBoundFacet] = [facet_definition(facet) for facet in facets]
    if credential_mode == "user_credential_required":
        schema.append(FACET_DEFINITIONS["auth_profile"])
    return tuple(schema)


def bounds_schema_for_source(
    source: DatasetDiscoverySource,
    *,
    credential_mode: str = "public_or_review",
) -> tuple[CrawlerAssetBoundFacet, ...]:
    return bounds_schema_for_facets(bounds_facets_for_source(source), credential_mode=credential_mode)


def facet_definition(facet_id: str) -> CrawlerAssetBoundFacet:
    known = FACET_DEFINITIONS.get(facet_id)
    if known is not None:
        return known
    return CrawlerAssetBoundFacet(
        facet_id=facet_id,
        label_zh_TW=facet_id,
        label_en=facet_id,
        group="ProviderSpecificBounds",
        control="text",
        value_type="text",
        maps_to=(f"provider_specific.{facet_id}",),
        help_zh_TW="這是 provider-specific 界域；需要後端補正式 schema 才能精準驗證。",
        help_en="Provider-specific bound; backend should formalize it before strict validation.",
    )


def bounds_facets_for_source(source: DatasetDiscoverySource) -> tuple[str, ...]:
    """推估建立下載計畫時需要的界域維度，供 UI 動態表單使用。"""

    if source_uses_file_index(source):
        return FILE_INDEX_BOUND_FACETS
    return SOURCE_BOUND_FACETS.get(source.source_type, DEFAULT_BOUND_FACETS)


__all__ = [
    "CrawlerAssetBoundFacet",
    "SOURCE_BOUND_FACETS",
    "bounds_facets_for_source",
    "bounds_schema_for_facets",
    "bounds_schema_for_source",
    "facet_definition",
]
