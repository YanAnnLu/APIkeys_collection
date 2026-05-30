"""Typed capability profiles for crawler source routing.

This module is the first concrete form of the medium-term
``Matrix Cell -> Validated Profile -> Capability Gateway`` idea.  It does not
replace existing crawler handlers and it is not a universal YAML interpreter.
Instead, it gathers the decisions that were starting to spread across UI,
resolver, and crawler code into one typed profile:

source type + auth + pagination + content hints + bounds + request policy

Downstream layers can read the profile and render/guard/route consistently
without repeating ``if source_type == ...`` in every surface.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from api_launcher.crawler_asset_bounds import bounds_facets_for_source
from api_launcher.crawler_asset_capabilities import credential_mode_for_source, terms_risk_for_source
from api_launcher.crawlers.registry import CrawlerCapabilityCode, CrawlerSpec, crawler_spec
from api_launcher.crawlers.request_policy import SourceRequestPolicy, source_request_policy
from api_launcher.crawlers.source_type_registry import source_uses_file_index
from api_launcher.crawlers.types import DatasetDiscoverySource


# Source type -> pagination style is a capability decision, not a UI decision.
# Keeping it here lets future middleware choose a page driver without teaching
# every frontend the details of CKAN offset, CMR page numbers, STAC next links,
# or HTML linked-index traversal.
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

# These are hints about likely payloads, not parser guarantees.  The content
# parser/import registry still owns the final answer to "can this artifact be
# imported automatically?"
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
    source_family: str
    transport: str
    auth_mode: str
    terms_risk: str
    result_shape: str
    seed_scope: str
    supports_full_crawl: bool
    capability_code: CrawlerCapabilityCode | None
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
            "source_family": self.source_family,
            "transport": self.transport,
            "auth_mode": self.auth_mode,
            "terms_risk": self.terms_risk,
            "result_shape": self.result_shape,
            "seed_scope": self.seed_scope,
            "supports_full_crawl": self.supports_full_crawl,
            "capability_code": self.capability_code.to_dict() if self.capability_code else {},
            "capability_bits": self.capability_code.bits if self.capability_code else None,
            "capability_binary": self.capability_code.binary if self.capability_code else "",
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
    """Build a validated profile for one configured source.

    This is intentionally a read/describe operation.  It does not crawl, write
    the catalog, or build a download plan.  The profile tells later layers which
    guards and drivers should wrap the existing handler.
    """

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
    spec = crawler_spec_for_source_type(source.source_type)
    return CrawlerCapabilityProfile(
        source_id=source.source_id,
        source_type=source.source_type,
        source_family=spec.source_family if spec else "unknown",
        transport=spec.transport if spec else "unknown",
        auth_mode=policy.credential_mode,
        terms_risk=policy.terms_risk,
        result_shape=spec.result_shape if spec else "unknown",
        seed_scope=spec.seed_scope if spec else "unknown",
        supports_full_crawl=bool(spec.supports_full_crawl) if spec else False,
        capability_code=spec.capability_code if spec else None,
        pagination_mode=pagination_mode,
        content_formats=content_format_hints_for_source(source),
        bound_facets=bounds_facets_for_source(source),
        middleware=middleware_for_profile(source, policy=policy, pagination_mode=pagination_mode),
        failure_policy=failure_policy_for_profile(policy),
        request_policy=policy,
    )


def crawler_spec_for_source_type(source_type: str) -> CrawlerSpec | None:
    """Return registry metadata when this source type has a registered handler."""

    try:
        return crawler_spec(source_type)
    except ValueError:
        return None


def pagination_mode_for_source(source: DatasetDiscoverySource) -> str:
    """Return the pagination driver id that should wrap this source handler."""

    if source_uses_file_index(source):
        return "linked_index_pages"
    return PAGINATION_MODE_BY_SOURCE_TYPE.get(source.source_type, "unknown")


def content_format_hints_for_source(source: DatasetDiscoverySource) -> tuple[str, ...]:
    """Return normalized payload format hints from explicit source metadata first."""

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
    """List middleware ids needed for this source profile.

    The ids are declarative labels for the gateway; they avoid hiding control
    flow in Python decorators too early.  A later pipeline can map these ids to
    concrete functions once the pattern stabilizes.
    """

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
    """Map common failure buckets to user-facing next actions."""

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
    "crawler_spec_for_source_type",
    "failure_policy_for_profile",
    "middleware_for_profile",
    "pagination_mode_for_source",
]
