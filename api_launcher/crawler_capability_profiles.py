from __future__ import annotations

from dataclasses import dataclass, replace

from api_launcher.crawler_asset_bounds import bounds_facets_for_source
from api_launcher.crawler_asset_capabilities import credential_mode_for_source, terms_risk_for_source
from api_launcher.crawlers.request_policy import SourceRequestPolicy, source_request_policy
from api_launcher.crawlers.source_type_registry import source_uses_file_index
from api_launcher.crawlers.types import DatasetDiscoverySource


PAGINATION_MODE_BY_SOURCE_TYPE: dict[str, str] = {
    "ckan_package_search": "offset",
    "socrata_catalog_search": "offset",
    "ncei_search": "offset",
    "gbif_dataset_search": "offset",
    "dataverse_search": "page_number",
    "cmr_collections": "page_number",
    "openalex_works_search": "cursor",
    "datacite_dois": "next_link",
    "zenodo_records_search": "next_link",
    "stac_collections": "next_link",
    "ogc_api_records": "next_link",
    "html_file_index": "linked_index_pages",
    "erddap_all_datasets": "single_catalog",
    "ogc_wms_capabilities": "single_capabilities_document",
}

CONTENT_FORMAT_HINTS_BY_SOURCE_TYPE: dict[str, tuple[str, ...]] = {
    "ckan_package_search": ("csv", "json", "zip", "excel", "pdf", "unknown"),
    "socrata_catalog_search": ("csv", "json", "geojson"),
    "ncei_search": ("csv", "json", "netcdf", "zip"),
    "erddap_all_datasets": ("csv", "json", "netcdf"),
    "gbif_dataset_search": ("json", "dwca", "zip"),
    "dataverse_search": ("json", "zip", "tabular", "unknown"),
    "zenodo_records_search": ("json", "zip", "unknown"),
    "datacite_dois": ("metadata", "unknown"),
    "openalex_works_search": ("metadata", "json"),
    "cmr_collections": ("hdf", "netcdf", "geotiff", "zip", "metadata"),
    "stac_collections": ("geotiff", "cog", "zarr", "netcdf", "json"),
    "ogc_api_records": ("geojson", "gml", "xml", "geotiff", "unknown"),
    "ogc_wms_capabilities": ("map_tile", "xml", "image"),
    "html_file_index": ("csv", "json", "zip", "netcdf", "hdf", "geotiff", "parquet", "unknown"),
}


@dataclass(frozen=True)
class CrawlerCapabilityProfile:
    """Validated profile for one crawler source capability cell.

    This is the typed staging point for the medium-term declarative
    architecture. It does not replace existing handlers; it describes how a
    source should be routed, guarded, and explained to UI/agent consumers.
    """

    source_id: str
    source_type: str
    auth_mode: str
    terms_risk: str
    pagination_mode: str
    content_formats: tuple[str, ...]
    bound_facets: tuple[str, ...]
    middleware: tuple[str, ...]
    failure_policy: dict[str, str]
    request_policy: SourceRequestPolicy

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "auth_mode": self.auth_mode,
            "terms_risk": self.terms_risk,
            "pagination_mode": self.pagination_mode,
            "content_formats": list(self.content_formats),
            "bound_facets": list(self.bound_facets),
            "middleware": list(self.middleware),
            "failure_policy": dict(self.failure_policy),
            "request_policy": self.request_policy.to_dict(),
        }


def crawler_capability_profile(
    source: DatasetDiscoverySource,
    *,
    fallback_timeout: float = 12.0,
    fallback_max_pages: int = 0,
    max_results_override: int = 0,
    full_crawl: bool = False,
) -> CrawlerCapabilityProfile:
    policy = source_request_policy(
        source,
        fallback_timeout=fallback_timeout,
        fallback_max_pages=fallback_max_pages,
        max_results_override=max_results_override,
        full_crawl=full_crawl,
    )
    policy = replace(
        policy,
        credential_mode=credential_mode_for_source(source),
        terms_risk=terms_risk_for_source(source),
    )
    pagination_mode = pagination_mode_for_source(source)
    return CrawlerCapabilityProfile(
        source_id=source.source_id,
        source_type=source.source_type,
        auth_mode=policy.credential_mode,
        terms_risk=policy.terms_risk,
        pagination_mode=pagination_mode,
        content_formats=content_format_hints_for_source(source),
        bound_facets=bounds_facets_for_source(source),
        middleware=middleware_for_profile(source, policy=policy, pagination_mode=pagination_mode),
        failure_policy=failure_policy_for_profile(policy),
        request_policy=policy,
    )


def pagination_mode_for_source(source: DatasetDiscoverySource) -> str:
    if source_uses_file_index(source):
        return "linked_index_pages"
    return PAGINATION_MODE_BY_SOURCE_TYPE.get(source.source_type, "unknown")


def content_format_hints_for_source(source: DatasetDiscoverySource) -> tuple[str, ...]:
    native = tuple(
        token.strip().lower()
        for token in str(source.native_format or "").replace(";", ",").replace("|", ",").split(",")
        if token.strip()
    )
    if native:
        return native
    return CONTENT_FORMAT_HINTS_BY_SOURCE_TYPE.get(source.source_type, ("unknown",))


def middleware_for_profile(
    source: DatasetDiscoverySource,
    *,
    policy: SourceRequestPolicy,
    pagination_mode: str,
) -> tuple[str, ...]:
    middleware: list[str] = []
    if policy.credential_mode == "user_credential_required":
        middleware.append("credential_guard")
    if policy.terms_risk == "terms_review_required":
        middleware.append("terms_review_guard")
    middleware.append("bounded_fetch")
    if pagination_mode not in {"single_catalog", "single_capabilities_document", "unknown"}:
        middleware.append("pagination_driver")
    if policy.rate_limit_seconds > 0:
        middleware.append("rate_limit")
    if source_uses_file_index(source) and source.file_url_regex:
        middleware.append("file_pattern_filter")
    middleware.append("audit_warning")
    return tuple(middleware)


def failure_policy_for_profile(policy: SourceRequestPolicy) -> dict[str, str]:
    missing_credentials_action = (
        "open_credential_editor"
        if policy.credential_mode == "user_credential_required"
        else "review_source_profile"
    )
    return {
        "zero_candidates": "review_query_or_bounds",
        "missing_credentials": missing_credentials_action,
        "unsupported_content": "adapter_review",
        "pagination_limit_reached": "show_has_more",
        "large_payload_blocked": "reduce_bounds_or_review_source",
    }


__all__ = [
    "CrawlerCapabilityProfile",
    "content_format_hints_for_source",
    "crawler_capability_profile",
    "failure_policy_for_profile",
    "middleware_for_profile",
    "pagination_mode_for_source",
]
