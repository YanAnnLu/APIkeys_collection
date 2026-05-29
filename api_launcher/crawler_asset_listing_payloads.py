"""Payload helpers for crawler asset listing results.

Listing results sit between crawler execution and UI/CLI/event surfaces.  Keep
their compact projection helpers outside ``crawler_asset_service.py`` so the
service can stay focused on source lookup, crawler execution, and catalog
updates.
"""

from __future__ import annotations

from api_launcher.crawler_asset_display import seed_enumeration_display_payload
from api_launcher.crawler_run_records import crawler_run_record_from_result


def crawler_seed_enumeration_payload(result: object) -> dict[str, object]:
    """Return display-safe seed enumeration status for UI shells.

    Candidate count alone is ambiguous: 1,000 candidates can mean "complete"
    for a small catalog or "local safety limit reached" for a large portal.
    This payload keeps the interpretation in the backend projection layer so
    Web/Tk/Qt do not duplicate count heuristics.
    """

    candidate_count = int(getattr(result, "candidate_count", 0) or 0)
    max_results = int(getattr(result, "max_results", 0) or 0)
    warning_count = int(getattr(result, "warning_count", 0) or 0)
    error_count = int(getattr(result, "error_count", 0) or 0)
    remote_pagination = crawler_remote_pagination_payload(result)
    remote_exhausted = remote_pagination["exhausted"] is True
    remote_has_more = remote_pagination["status"] == "has_more"
    next_action = str(getattr(result, "next_action", "") or "")
    if bool(getattr(result, "blocked", False)):
        return seed_enumeration_display_payload(
            "blocked",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
            next_action=next_action,
        )
    if error_count:
        return seed_enumeration_display_payload(
            "error",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
            next_action=next_action,
        )
    if candidate_count <= 0:
        return seed_enumeration_display_payload(
            "empty",
            candidate_count=0,
            max_results=max_results,
            remote_pagination=remote_pagination,
            next_action=next_action,
        )
    limited = bool(
        getattr(result, "complete_seed", False) and max_results > 0 and candidate_count >= max_results and not remote_exhausted
    )
    if limited:
        return seed_enumeration_display_payload(
            "local_limit_reached",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
        )
    if warning_count:
        return seed_enumeration_display_payload(
            "warning",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
            warning_count=warning_count,
            next_action=next_action,
            completion_confidence=_remote_seed_completion_confidence(
                remote_exhausted=remote_exhausted,
                remote_has_more=remote_has_more,
                default="warning_with_unknown_remote_completion",
            ),
        )
    if bool(getattr(result, "complete_seed", False)):
        return seed_enumeration_display_payload(
            "within_current_limits",
            candidate_count=candidate_count,
            max_results=max_results,
            remote_pagination=remote_pagination,
            next_action=next_action,
            completion_confidence=_remote_seed_completion_confidence(
                remote_exhausted=remote_exhausted,
                remote_has_more=remote_has_more,
                default="within_current_local_limits",
            ),
        )
    return seed_enumeration_display_payload(
        "bounded_sample",
        candidate_count=candidate_count,
        max_results=max_results,
        remote_pagination=remote_pagination,
        next_action=next_action,
    )


def _remote_seed_completion_confidence(*, remote_exhausted: bool, remote_has_more: bool, default: str) -> str:
    if remote_exhausted:
        return "remote_reported_exhausted"
    if remote_has_more:
        return "remote_has_more"
    return default


def crawler_remote_pagination_payload(result: object) -> dict[str, object]:
    """Return explicit remote pagination evidence without exposing raw tokens."""

    status = str(getattr(result, "remote_pagination_status", "") or "").strip() or "not_reported"
    token_present = bool(str(getattr(result, "remote_next_page_token", "") or "").strip())
    exhausted = getattr(result, "remote_exhausted", None)
    if exhausted is True:
        status = "exhausted"
    elif exhausted is False and token_present and status == "not_reported":
        status = "has_more"
    return {
        "status": status,
        "exhausted": exhausted,
        "next_page_token_present": token_present,
    }


def crawler_asset_listing_event_context(result: object) -> dict[str, object]:
    """Return the compact listing-event payload shared by Tk/Web/CLI callers.

    Structured events are handoff evidence.  Keep this payload bounded and
    display-safe; do not store full candidate lists or raw remote pagination
    tokens here.
    """

    return {
        "asset_id": str(getattr(result, "asset_id", "") or ""),
        "listing_mode": str(getattr(result, "listing_mode", "") or ""),
        "source_found": bool(getattr(result, "source_found", False)),
        "blocked": bool(getattr(result, "blocked", False)),
        "blocked_reason": str(getattr(result, "blocked_reason", "") or ""),
        "candidate_count": int(getattr(result, "candidate_count", 0) or 0),
        "upserted_count": int(getattr(result, "upserted_count", 0) or 0),
        "skipped_provider_count": int(getattr(result, "skipped_provider_count", 0) or 0),
        "duplicate_count": int(getattr(result, "duplicate_count", 0) or 0),
        "error_count": int(getattr(result, "error_count", 0) or 0),
        "warning_count": int(getattr(result, "warning_count", 0) or 0),
        "next_action": str(getattr(result, "next_action", "") or ""),
        "max_results": int(getattr(result, "max_results", 0) or 0),
        "max_pages": int(getattr(result, "max_pages", 0) or 0),
        "complete_seed": bool(getattr(result, "complete_seed", False)),
        "search_scope": str(getattr(result, "search_scope", "") or ""),
        "remote_pagination": crawler_remote_pagination_payload(result),
        "seed_enumeration": crawler_seed_enumeration_payload(result),
        "run_record": crawler_run_record_from_result(result),
    }


__all__ = [
    "crawler_asset_listing_event_context",
    "crawler_remote_pagination_payload",
    "crawler_seed_enumeration_payload",
]
