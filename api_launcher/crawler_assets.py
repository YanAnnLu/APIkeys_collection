from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_launcher.crawlers.dataset_sources import (
    DEFAULT_DATASET_DISCOVERY_SOURCES_NAME,
    LOCAL_DATASET_DISCOVERY_SOURCES_NAME,
    SUPPORTED_DATASET_SOURCE_TYPES,
    load_all_dataset_discovery_sources,
)
from api_launcher.crawlers.types import DatasetDiscoverySource
from api_launcher.crawler_asset_profiles import CrawlerAssetProfile, crawler_asset_profile_for, load_crawler_asset_profiles
from api_launcher.dataset_seed_coverage import source_seed_coverage
from api_launcher.paths import catalog_file, local_config_file


@dataclass(frozen=True)
class CrawlerAssetCapability:
    """單一入口爬蟲可對外提供的能力槽。"""

    capability_id: str
    label: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "capability_id": self.capability_id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class CrawlerAsset:
    """把一個資料入口視為可治理的爬蟲資產，而不是單次工作。"""

    asset_id: str
    display_name: str
    provider_id: str
    source_type: str
    source_surface: str
    access_requirement: str
    endpoint_url: str
    docs_url: str
    categories: tuple[str, ...]
    geographic_scope: str
    maturity: str
    risk_tier: str
    trust_score: int
    seed_count: int
    seed_summary: str
    current_seed_scope: str
    next_action: str
    enabled: bool
    archived: bool
    profile_state: str
    capabilities: tuple[CrawlerAssetCapability, ...]

    @property
    def capability_summary(self) -> str:
        return " / ".join(f"{item.label}:{status_label(item.status)}" for item in self.capabilities)

    def capability_status(self, capability_id: str) -> str:
        for item in self.capabilities:
            if item.capability_id == capability_id:
                return item.status
        return "unknown"

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "display_name": self.display_name,
            "provider_id": self.provider_id,
            "source_type": self.source_type,
            "source_surface": self.source_surface,
            "access_requirement": self.access_requirement,
            "endpoint_url": self.endpoint_url,
            "docs_url": self.docs_url,
            "categories": list(self.categories),
            "geographic_scope": self.geographic_scope,
            "maturity": self.maturity,
            "risk_tier": self.risk_tier,
            "trust_score": self.trust_score,
            "seed_count": self.seed_count,
            "seed_summary": self.seed_summary,
            "current_seed_scope": self.current_seed_scope,
            "next_action": self.next_action,
            "enabled": self.enabled,
            "archived": self.archived,
            "profile_state": self.profile_state,
            "capabilities": [item.to_dict() for item in self.capabilities],
        }


def load_crawler_assets(
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> list[CrawlerAsset]:
    """讀取正式與本機入口設定，轉成 UI 可直接呈現的爬蟲資產。"""

    source_path = Path(primary_path) if primary_path is not None else catalog_file(DEFAULT_DATASET_DISCOVERY_SOURCES_NAME)
    local_source_path = Path(local_path) if local_path is not None else local_config_file(LOCAL_DATASET_DISCOVERY_SOURCES_NAME)
    sources = load_all_dataset_discovery_sources(source_path, local_source_path)
    profiles = load_crawler_asset_profiles(profile_path)
    return [crawler_asset_from_source(source, crawler_asset_profile_for(source.source_id, profiles)) for source in sources]


def load_crawler_asset_source(
    asset_id: str,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
) -> DatasetDiscoverySource | None:
    """依資產 id 找回原始入口設定，供 crawler worker 精準執行單一入口。"""

    source_path = Path(primary_path) if primary_path is not None else catalog_file(DEFAULT_DATASET_DISCOVERY_SOURCES_NAME)
    local_source_path = Path(local_path) if local_path is not None else local_config_file(LOCAL_DATASET_DISCOVERY_SOURCES_NAME)
    for source in load_all_dataset_discovery_sources(source_path, local_source_path):
        if source.source_id == asset_id:
            return source
    return None


def crawler_asset_from_source(source: DatasetDiscoverySource, profile: CrawlerAssetProfile | None = None) -> CrawlerAsset:
    coverage = source_seed_coverage(source)
    profile = profile or crawler_asset_profile_for(source.source_id, {})
    supported = source.source_type in SUPPORTED_DATASET_SOURCE_TYPES
    capabilities = crawler_asset_capabilities(source, supported=supported)
    maturity = crawler_asset_maturity(coverage.complete_seed_ready, supported, source)
    risk_tier = "archived" if profile.archived else crawler_asset_risk_tier(supported, coverage.complete_seed_ready, capabilities)
    return CrawlerAsset(
        asset_id=source.source_id,
        display_name=source.name or source.source_id,
        provider_id=source.provider_id,
        source_type=source.source_type,
        source_surface=source_surface_label(source),
        access_requirement=access_requirement_for_source(source),
        endpoint_url=source.endpoint_url,
        docs_url=source.docs_url,
        categories=source.categories,
        geographic_scope=source.geographic_scope,
        maturity=maturity,
        risk_tier=risk_tier,
        trust_score=trust_score_for_asset(maturity, risk_tier, coverage.complete_seed_ready),
        seed_count=configured_seed_count(source),
        seed_summary=seed_summary_for_source(source, coverage.current_seed_scope),
        current_seed_scope=coverage.current_seed_scope,
        next_action="archived_disabled" if profile.archived else coverage.next_action,
        enabled=profile.enabled,
        archived=profile.archived,
        profile_state=profile.profile_state,
        capabilities=capabilities,
    )


def crawler_asset_capabilities(source: DatasetDiscoverySource, *, supported: bool) -> tuple[CrawlerAssetCapability, ...]:
    """一個入口一隻蟲；蟲內用能力槽標示可做到哪一步。"""

    if supported:
        metadata_status = "ready"
        metadata_detail = "已接到入口 handler，可抓取入口層 metadata。"
    else:
        metadata_status = "needs_handler"
        metadata_detail = "尚未有對應 source_type handler，需先補 crawler。"

    if supported and source.search_terms:
        listing_status = "bounded"
        listing_detail = "目前以 search_terms 做有界清單擷取，可再切到完整 seed。"
    elif supported:
        listing_status = "ready"
        listing_detail = "可對入口執行清單擷取或完整 seed 嘗試。"
    else:
        listing_status = "needs_handler"
        listing_detail = "清單擷取需要先建立入口 handler。"

    if source.file_url_regex or source.source_type == "html_file_index":
        download_status = "selectable"
        download_detail = "入口可列出檔案 shard，下一步是選版本/界域後下載。"
    elif supported:
        download_status = "needs_bounds_or_adapter"
        download_detail = "需要先看 schema/head，再由界域表單或 adapter 產生指定下載。"
    else:
        download_status = "needs_handler"
        download_detail = "下載指定資料庫前需先補入口 handler 與資料集解析。"

    return (
        CrawlerAssetCapability("fetch_metadata", "元資料", metadata_status, metadata_detail),
        CrawlerAssetCapability("list_datasets", "清單", listing_status, listing_detail),
        CrawlerAssetCapability("download_selected", "下載", download_status, download_detail),
    )


def crawler_asset_maturity(complete_seed_ready: bool, supported: bool, source: DatasetDiscoverySource) -> str:
    if complete_seed_ready:
        return "ready"
    if supported and source.search_terms:
        return "bounded"
    if supported:
        return "assembled"
    return "unbuilt"


def crawler_asset_risk_tier(
    supported: bool,
    complete_seed_ready: bool,
    capabilities: tuple[CrawlerAssetCapability, ...],
) -> str:
    if not supported:
        return "needs_handler"
    if complete_seed_ready and all(item.status in {"ready", "selectable"} for item in capabilities[:2]):
        return "normal"
    return "needs_review"


def trust_score_for_asset(maturity: str, risk_tier: str, complete_seed_ready: bool) -> int:
    if risk_tier == "needs_handler":
        return 25
    if complete_seed_ready:
        return 86
    if maturity == "bounded":
        return 68
    if maturity == "assembled":
        return 58
    return 40


def source_surface_label(source: DatasetDiscoverySource) -> str:
    endpoint = source.endpoint_url.lower()
    if endpoint.endswith(".json") or "api" in endpoint or source.source_type in {"ncei_search", "cmr_collections", "ckan_package_search"}:
        return "api"
    if source.source_type == "html_file_index":
        return "file_index"
    return "catalog"


def access_requirement_for_source(source: DatasetDiscoverySource) -> str:
    # 帳號、token、rate limit 都是爬蟲能力的邊界，不放到資料庫本體上。
    text = " ".join([source.source_id, source.provider_id, source.endpoint_url, source.docs_url, source.notes]).lower()
    guarded_words = ("token", "api key", "apikey", "oauth", "login", "account", "earthdata", "kaggle", "cdsapi")
    if any(word in text for word in guarded_words):
        return "crawler_managed_auth"
    return "public_or_review"


def configured_seed_count(source: DatasetDiscoverySource) -> int:
    count = len(source.search_terms)
    if source.dataset_id:
        count += 1
    return count


def seed_summary_for_source(source: DatasetDiscoverySource, current_seed_scope: str) -> str:
    count = configured_seed_count(source)
    if count:
        return f"{count} configured"
    if current_seed_scope in {"entry_listing", "paginated_catalog", "complete_entry_listing"}:
        return "full entry"
    return "none"


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
