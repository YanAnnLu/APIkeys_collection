"""Bounded event summaries for the RRKAL Web Preview surface."""

from __future__ import annotations

from typing import Mapping

from api_launcher.crawler_asset_display import (
    crawler_asset_recent_plan_outcomes_from_events,
    crawler_asset_recent_plan_passports_from_events,
)
from api_launcher.crawler_run_records import crawler_run_context_summary
from api_launcher.event_log import latest_events


WEB_PREVIEW_EVENT_LIMIT = 80


def recent_crawler_asset_listing_outcomes(*, limit: int = 200) -> dict[str, dict[str, object]]:
    """Return the newest seed-enumeration summary for each crawler asset."""

    outcomes: dict[str, dict[str, object]] = {}
    for event in latest_events(limit):
        if event.get("event") != "crawler_asset_listing_recorded":
            continue
        context = event.get("context")
        if not isinstance(context, dict):
            continue
        asset_id = str(context.get("asset_id") or "").strip()
        if not asset_id:
            continue
        outcomes[asset_id] = compact_listing_outcome(context)
    return outcomes


def compact_listing_outcome(context: Mapping[str, object]) -> dict[str, object]:
    """Keep listing summaries small enough for cards and hero panels."""

    run_record = context.get("run_record")
    seed_enumeration = context.get("seed_enumeration")
    remote_pagination = context.get("remote_pagination")
    return {
        "asset_id": str(context.get("asset_id") or ""),
        "listing_mode": str(context.get("listing_mode") or ""),
        "candidate_count": int(context.get("candidate_count") or 0),
        "upserted_count": int(context.get("upserted_count") or 0),
        "duplicate_count": int(context.get("duplicate_count") or 0),
        "warning_count": int(context.get("warning_count") or 0),
        "error_count": int(context.get("error_count") or 0),
        "max_results": int(context.get("max_results") or 0),
        "max_pages": int(context.get("max_pages") or 0),
        "complete_seed": bool(context.get("complete_seed")),
        "search_scope": str(context.get("search_scope") or ""),
        "next_action": str(context.get("next_action") or ""),
        "seed_enumeration": seed_enumeration if isinstance(seed_enumeration, dict) else {},
        "remote_pagination": remote_pagination if isinstance(remote_pagination, dict) else {},
        "run_record": run_record if isinstance(run_record, dict) else {},
    }


def recent_crawler_asset_plan_outcomes(*, limit: int = 200) -> dict[str, dict[str, object]]:
    """Return the newest recorded plan outcome for each crawler asset."""

    return crawler_asset_recent_plan_outcomes_from_events(latest_events(limit))


def recent_crawler_asset_plan_passports(*, limit: int = 200) -> dict[str, dict[str, object]]:
    """Return the newest compact plan passport recorded for each asset."""

    return crawler_asset_recent_plan_passports_from_events(latest_events(limit))


def web_preview_recent_events(*, limit: int = 50) -> dict[str, object]:
    """Return bounded structured events for the Web Preview event workspace."""

    clamped_limit = max(1, min(int(limit), WEB_PREVIEW_EVENT_LIMIT))
    events = [web_preview_event_payload(event) for event in latest_events(clamped_limit)]
    events.reverse()
    return {
        "count": len(events),
        "limit": clamped_limit,
        "events": events,
    }


def web_preview_event_payload(event: Mapping[str, object]) -> dict[str, object]:
    context = event.get("context") if isinstance(event.get("context"), dict) else {}
    assert isinstance(context, dict)
    context_summary = crawler_run_context_summary(context)
    return {
        "timestamp": str(event.get("timestamp") or ""),
        "level": str(event.get("level") or "info"),
        "event": str(event.get("event") or ""),
        "component": str(event.get("component") or ""),
        "message": str(event.get("message") or ""),
        "context_summary": context_summary,
    }
