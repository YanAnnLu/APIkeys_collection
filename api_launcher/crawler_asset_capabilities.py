from __future__ import annotations

from dataclasses import dataclass

from api_launcher.crawler_asset_bounds import (
    CrawlerAssetBoundFacet,
    bounds_facets_for_source,
    bounds_schema_for_facets,
    bounds_schema_for_source,
)
from api_launcher.crawlers.types import DatasetDiscoverySource


FETCH_METADATA = "fetch_metadata"
LIST_DATASETS = "list_datasets"
BUILD_DOWNLOAD_PLAN = "build_download_plan"

CAPABILITY_ALIASES = {
    # 早期 Tk UI 用 download_selected 表示第三槽；後端契約改成 build_download_plan。
    # 保留 alias，讓舊測試、舊 UI 與未來 Qt bridge 不會因命名調整直接斷裂。
    "download_selected": BUILD_DOWNLOAD_PLAN,
}


@dataclass(frozen=True)
class CrawlerAssetCapability:
    """單一入口爬蟲可對外提供的能力槽與治理契約。"""

    capability_id: str
    label: str
    status: str
    detail: str
    input_contract: str
    output_contract: str
    credential_mode: str
    bounds_facets: tuple[str, ...] = ()
    bounds_schema: tuple[CrawlerAssetBoundFacet, ...] = ()
    error_buckets: tuple[str, ...] = ()
    rate_limit_policy: str = "polite_default"
    terms_risk: str = "review"
    next_action: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "credential_mode": self.credential_mode,
            "bounds_facets": list(self.bounds_facets),
            "bounds_schema": [facet.to_dict() for facet in self.bounds_schema],
            "error_buckets": list(self.error_buckets),
            "rate_limit_policy": self.rate_limit_policy,
            "terms_risk": self.terms_risk,
            "next_action": self.next_action,
        }


def normalize_capability_id(capability_id: str) -> str:
    return CAPABILITY_ALIASES.get(capability_id, capability_id)


def crawler_asset_capabilities(source: DatasetDiscoverySource, *, supported: bool) -> tuple[CrawlerAssetCapability, ...]:
    """建立一個入口 crawler 的三槽能力契約。

    這裡只描述「這隻蟲會什麼」與「下一步需要什麼 guard」；實際 HTTP、
    catalog upsert、下載計畫產生都留給 service / adapter。這個切分能讓 Tk、
    未來 Qt 與 CLI 共用同一份能力判斷。
    """

    credential_mode = credential_mode_for_source(source)
    terms_risk = terms_risk_for_source(source)
    bounds_facets = bounds_facets_for_source(source)
    plan_bounds_schema = bounds_schema_for_source(source, credential_mode=credential_mode)

    if supported:
        metadata_status = "ready"
        metadata_detail = "已接到入口 handler，可抓取入口層 metadata。"
        metadata_next = "list_datasets"
    else:
        metadata_status = "needs_handler"
        metadata_detail = "尚未有對應 source_type handler，需先補 crawler。"
        metadata_next = "implement_source_handler"

    if supported and source.search_terms:
        listing_status = "bounded"
        listing_detail = "目前以 search_terms 做有界清單擷取，可再切到完整 seed。"
        listing_next = "review_candidates_or_expand_seed"
    elif supported:
        listing_status = "ready"
        listing_detail = "可對入口執行清單擷取或完整 seed 嘗試。"
        listing_next = "review_candidates"
    else:
        listing_status = "needs_handler"
        listing_detail = "清單擷取需要先建立入口 handler。"
        listing_next = "implement_source_handler"

    if source.file_url_regex or source.source_type == "html_file_index":
        plan_status = "selectable"
        plan_detail = "入口可列出檔案 shard，下一步是選版本/界域後建立下載計畫。"
        plan_next = "select_version_and_bounds"
    elif supported:
        plan_status = "needs_bounds_or_adapter"
        plan_detail = "需要先看 schema/head，再由界域表單或 adapter 建立指定下載計畫。"
        plan_next = "probe_schema_then_define_bounds"
    else:
        plan_status = "needs_handler"
        plan_detail = "下載指定資料庫前需先補入口 handler 與資料集解析。"
        plan_next = "implement_source_handler"

    return (
        CrawlerAssetCapability(
            capability_id=FETCH_METADATA,
            label="元資料",
            status=metadata_status,
            detail=metadata_detail,
            input_contract="DatasetDiscoverySource",
            output_contract="source metadata / audit summary",
            credential_mode=credential_mode,
            error_buckets=("source_not_found", "unsupported_source_type", "network_error", "unexpected_payload"),
            terms_risk=terms_risk,
            next_action=metadata_next,
        ),
        CrawlerAssetCapability(
            capability_id=LIST_DATASETS,
            label="清單",
            status=listing_status,
            detail=listing_detail,
            input_contract="DatasetDiscoverySource + DatasetCrawlOptions",
            output_contract="DatasetCandidate[] + audit summary",
            credential_mode=credential_mode,
            bounds_facets=("search_terms", "max_results", "max_pages"),
            bounds_schema=bounds_schema_for_facets(("search_terms", "max_results", "max_pages"), credential_mode=credential_mode),
            error_buckets=("zero_candidates", "duplicate_heavy", "low_candidate_count", "unexpected_payload"),
            terms_risk=terms_risk,
            next_action=listing_next,
        ),
        CrawlerAssetCapability(
            capability_id=BUILD_DOWNLOAD_PLAN,
            label="下載計畫",
            status=plan_status,
            detail=plan_detail,
            input_contract="DatasetCandidate + SourceDownloadBounds",
            output_contract="download plan entry / adapter review item",
            credential_mode=credential_mode,
            bounds_facets=bounds_facets,
            bounds_schema=plan_bounds_schema,
            error_buckets=("missing_schema", "unbounded_query", "adapter_required", "credential_required", "terms_review_required"),
            terms_risk=terms_risk,
            next_action=plan_next,
        ),
    )


def capability_status(
    capabilities: tuple[CrawlerAssetCapability, ...],
    capability_id: str,
) -> str:
    normalized = normalize_capability_id(capability_id)
    for item in capabilities:
        if item.capability_id == normalized:
            return item.status
    return "unknown"


def access_requirement_for_source(source: DatasetDiscoverySource) -> str:
    mode = credential_mode_for_source(source)
    if mode == "user_credential_required":
        return "crawler_managed_auth"
    return "public_or_review"


def credential_mode_for_source(source: DatasetDiscoverySource) -> str:
    text = " ".join([source.source_id, source.provider_id, source.endpoint_url, source.docs_url, source.notes]).lower()
    guarded_words = ("token", "api key", "apikey", "oauth", "login", "account", "earthdata", "kaggle", "cdsapi")
    if any(word in text for word in guarded_words):
        return "user_credential_required"
    return "public_or_review"


def terms_risk_for_source(source: DatasetDiscoverySource) -> str:
    text = " ".join([source.source_id, source.provider_id, source.endpoint_url, source.docs_url, source.notes]).lower()
    if any(word in text for word in ("restricted", "license", "terms", "commercial", "citation", "earthdata", "kaggle")):
        return "terms_review_required"
    return "public_or_review"


def status_label(status: str) -> str:
    labels = {
        "ready": "可用",
        "bounded": "有界",
        "selectable": "可選",
        "needs_bounds_or_adapter": "需界域",
        "needs_handler": "待補",
        "archived": "封存",
        "disabled": "停用",
        "active": "啟用",
    }
    return labels.get(status, status)
