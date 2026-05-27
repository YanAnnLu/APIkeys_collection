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
from api_launcher.crawler_asset_bounds import bounds_facets_for_source
from api_launcher.crawler_asset_profiles import (
    CrawlerAssetProfile,
    crawler_asset_bounds_signature,
    crawler_asset_plan_passport_for_profile,
    crawler_asset_profile_for,
    crawler_asset_source_signature,
    load_crawler_asset_profiles,
)
from api_launcher.crawler_asset_capabilities import (
    BUILD_DOWNLOAD_PLAN,
    CrawlerAssetCapability,
    access_requirement_for_source,
    capability_status,
    crawler_asset_capabilities,
    status_label,
)
from api_launcher.crawler_asset_health import CrawlerAssetHealth, evaluate_crawler_asset_health
from api_launcher.dataset_seed_coverage import source_seed_coverage
from api_launcher.paths import catalog_file, local_config_file


SOURCE_SURFACE_LABELS: dict[str, str] = {
    # UI card/passport labels should come from this registry instead of
    # branching on source_type. Unknown API-like endpoints still fall back to
    # endpoint shape detection in source_surface_label().
    "html_file_index": "file_index",
    "ogc_wms_capabilities": "map_service",
    "stac_collections": "catalog",
    "ogc_api_records": "catalog",
    "ncei_search": "api",
    "erddap_all_datasets": "api",
    "cmr_collections": "api",
    "ckan_package_search": "api",
    "socrata_catalog_search": "api",
    "gbif_dataset_search": "api",
    "dataverse_search": "api",
    "zenodo_records_search": "api",
    "datacite_dois": "api",
    "openalex_works_search": "api",
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
    credential_profile_id: str
    api_key_env_var: str
    account_hint: str
    schedule_policy: str
    rate_limit_policy: str
    retry_policy: str
    seed_scope_policy: str
    status_note: str
    local_logo_path: str
    official_logo_url: str
    favicon_url: str
    logo_source: str
    logo_license_note: str
    latest_plan_passport: dict[str, object]
    health: CrawlerAssetHealth
    capabilities: tuple[CrawlerAssetCapability, ...]

    @property
    def capability_summary(self) -> str:
        return " / ".join(f"{item.label}:{status_label(item.status)}" for item in self.capabilities)

    def capability_status(self, capability_id: str) -> str:
        return capability_status(self.capabilities, capability_id)

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
            "credential_profile_id": self.credential_profile_id,
            "api_key_env_var": self.api_key_env_var,
            "account_hint": self.account_hint,
            "schedule_policy": self.schedule_policy,
            "rate_limit_policy": self.rate_limit_policy,
            "retry_policy": self.retry_policy,
            "seed_scope_policy": self.seed_scope_policy,
            "status_note": self.status_note,
            "local_logo_path": self.local_logo_path,
            "official_logo_url": self.official_logo_url,
            "favicon_url": self.favicon_url,
            "logo_source": self.logo_source,
            "logo_license_note": self.logo_license_note,
            "latest_plan_passport": dict(self.latest_plan_passport),
            "health": self.health.to_dict(),
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
    next_action = "archived_disabled" if profile.archived else coverage.next_action
    health = evaluate_crawler_asset_health(
        asset_id=source.source_id,
        enabled=profile.enabled,
        archived=profile.archived,
        risk_tier=risk_tier,
        maturity=maturity,
        capabilities=capabilities,
        next_action=next_action,
    )
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
        next_action=health.next_action or next_action,
        enabled=profile.enabled,
        archived=profile.archived,
        profile_state=profile.profile_state,
        credential_profile_id=profile.credential_profile_id,
        api_key_env_var=profile.api_key_env_var,
        account_hint=profile.account_hint,
        schedule_policy=profile.schedule_policy,
        rate_limit_policy=profile.rate_limit_policy,
        retry_policy=profile.retry_policy,
        seed_scope_policy=profile.seed_scope_policy,
        status_note=profile.status_note,
        local_logo_path=profile.local_logo_path,
        official_logo_url=profile.official_logo_url,
        favicon_url=profile.favicon_url,
        logo_source=profile.logo_source,
        logo_license_note=profile.logo_license_note,
        latest_plan_passport=crawler_asset_plan_passport_for_profile(
            profile,
            source_signature=crawler_asset_source_signature(source),
            bounds_signature=crawler_asset_bounds_signature(bounds_facets_for_source(source)),
        ),
        health=health,
        capabilities=capabilities,
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
    known = SOURCE_SURFACE_LABELS.get(source.source_type)
    if known is not None:
        return known
    endpoint = source.endpoint_url.lower()
    if endpoint.endswith(".json") or "api" in endpoint:
        return "api"
    return "catalog"


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


__all__ = [
    "BUILD_DOWNLOAD_PLAN",
    "CrawlerAsset",
    "CrawlerAssetCapability",
    "SOURCE_SURFACE_LABELS",
    "crawler_asset_from_source",
    "load_crawler_asset_source",
    "load_crawler_assets",
    "status_label",
]
