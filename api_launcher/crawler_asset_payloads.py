"""Payload adapters for crawler asset bounds.

These helpers translate UI-neutral crawler asset form payloads into the older
source-download bounds/options contract.  They are deliberately kept separate
from crawler listing and plan orchestration so UI form evolution does not make
`crawler_asset_service.py` absorb another responsibility.
"""

from __future__ import annotations

from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundPayload
from api_launcher.source_download import SourceDownloadBounds, SourceDownloadOptions


def source_download_options_from_crawler_asset_payload(
    payload: CrawlerAssetBoundPayload | None,
    *,
    timeout: float = 12.0,
    max_results: int = 100,
    full_crawl: bool = True,
    max_pages: int = 0,
) -> SourceDownloadOptions:
    """Translate frontend-neutral crawler bounds into source-download options.

    This is the main adapter from dynamic UI form output to the older
    source-download service.  Keep new form fields mapped through
    ``CrawlerAssetBoundPayload.maps_to_values`` rather than adding UI-specific
    branches in Tk or Web.
    """

    bounds = source_download_bounds_from_crawler_asset_payload(payload)
    effective_max_results = bounds.candidate_limit or max_results
    effective_max_pages = bounds.max_pages or max_pages
    return SourceDownloadOptions(
        bounds=bounds,
        timeout=timeout,
        max_results_override=effective_max_results,
        search_terms_override=bounds.search_terms,
        full_crawl=full_crawl or bounds.full_crawl,
        max_pages=effective_max_pages,
        max_workers=1,
        selected_versions=selected_versions_from_crawler_asset_payload(payload),
    )


def source_download_bounds_from_crawler_asset_payload(payload: CrawlerAssetBoundPayload | None) -> SourceDownloadBounds:
    """Convert crawler asset bounds payload into the backend bounds contract.

    ``maps_to_values`` is authoritative for backend field names.  ``facet_values``
    is used as a fallback for composite user concepts such as time, bbox, and
    dataset selectors.
    """

    if payload is None:
        return SourceDownloadBounds()
    values = dict(payload.maps_to_values)
    facets = dict(payload.facet_values)
    candidate_limit = int_bound(values.get("SourceDownloadBounds.candidate_limit"), default=0)
    sample_limit = int_bound(values.get("SourceDownloadBounds.sample_limit"), default=25)
    max_pages = int_bound(values.get("SourceDownloadBounds.max_pages"), default=0)
    version_limit = int_bound(values.get("SourceDownloadBounds.version_limit"), default=1)
    bbox = bbox_bound(values.get("SourceDownloadBounds.bbox") or facets.get("bbox"))
    time_values = facets.get("time") if isinstance(facets.get("time"), dict) else {}
    search_terms = tuple_bound(values.get("SourceDownloadBounds.search_terms"))
    if not search_terms:
        search_terms = selector_terms_from_facets(facets)
    required_columns = tuple_bound(values.get("SourceDownloadBounds.required_columns"))
    return SourceDownloadBounds(
        candidate_limit=candidate_limit,
        version_limit=version_limit,
        sample_limit=sample_limit,
        max_pages=max_pages,
        full_crawl=bool_bound(values.get("SourceDownloadBounds.full_crawl"), default=False),
        start_date=str(values.get("SourceDownloadBounds.start_date") or time_values.get("start_date") or "").strip(),
        end_date=str(values.get("SourceDownloadBounds.end_date") or time_values.get("end_date") or "").strip(),
        bbox=bbox,
        search_terms=search_terms,
        required_columns=required_columns,
        time_field=str(values.get("SourceDownloadBounds.time_field") or time_values.get("time_field") or "").strip(),
        longitude_field=str(values.get("SourceDownloadBounds.longitude_field") or "").strip(),
        latitude_field=str(values.get("SourceDownloadBounds.latitude_field") or "").strip(),
        schema_probe_required=True,
    )


def selected_versions_from_crawler_asset_payload(payload: CrawlerAssetBoundPayload | None) -> dict[str, tuple[str, ...]]:
    """Extract a frontend-neutral version selector from crawler asset bounds.

    Crawler-asset forms are source-level forms: the user chooses a version before
    the concrete dataset candidate is known.  The wildcard key lets
    ``SourceDownloadOptions`` apply that selector to whichever dataset the
    crawler returns, while dataset-specific selectors can still override it
    later in more precise UI flows.
    """

    if payload is None:
        return {}
    raw = payload.maps_to_values.get("SourceDownloadOptions.selected_versions")
    if raw in ("", None, (), []):
        raw = payload.facet_values.get("version")
    selected = tuple_bound(raw)
    if not selected:
        return {}
    return {"*": selected}


def selector_terms_from_facets(facets: dict[str, object]) -> tuple[str, ...]:
    """Build broad source-query terms from selector facets when no query exists."""

    terms: list[str] = []
    for key in ("dataset", "collection", "package", "resource", "file_pattern", "format"):
        terms.extend(tuple_bound(facets.get(key)))
    return tuple(dict.fromkeys(terms))


def int_bound(value: object, *, default: int) -> int:
    if value in ("", None, (), []):
        return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def bool_bound(value: object, *, default: bool) -> bool:
    if value in ("", None, (), []):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def tuple_bound(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    if not text:
        return ()
    return (text,)


def bbox_bound(value: object) -> tuple[float, float, float, float] | None:
    if value in ("", None, (), []):
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return tuple(float(item) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None

