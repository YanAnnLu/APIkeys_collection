"""Restore crawler asset Tk read-model state from structured events.

These helpers only rebuild display continuity after the Tk panel is reopened.
They do not treat event log data as fresh backend truth, and they do not run
crawlers, rebuild plans, or write profiles.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from api_launcher.crawler_asset_display import (
    adapter_review_content_summary_label,
    adapter_review_display_payload,
)
from frontends.tk.crawler_asset_ui_helpers import crawler_asset_listing_event_preview_payload


PlanReader = Callable[[str], object]


@dataclass(frozen=True)
class CrawlerAssetRestoredPlanState:
    """Display state recovered from recent crawler asset plan events."""

    plan_outcomes: dict[str, str]
    content_review_outcomes: dict[str, str]
    resolved_plans: dict[str, dict[str, object]]
    plan_passports: dict[str, dict[str, object]]


def read_resolved_plan_json(path_text: str) -> object:
    """Read a saved resolved-plan JSON file referenced by a Tk event."""

    return json.loads(Path(path_text).read_text(encoding="utf-8"))


def crawler_asset_plan_state_from_events(
    events: Iterable[dict[str, object]],
    *,
    read_plan: PlanReader = read_resolved_plan_json,
) -> CrawlerAssetRestoredPlanState:
    """Recover the visible plan outcome cache from structured events.

    The event stream is only a UI continuity source. If the saved resolved plan
    file is missing or unreadable, the visible outcome and passport still remain
    useful, but the resolved plan itself is intentionally skipped.
    """

    plan_outcomes: dict[str, str] = {}
    content_review_outcomes: dict[str, str] = {}
    resolved_plans: dict[str, dict[str, object]] = {}
    plan_passports: dict[str, dict[str, object]] = {}

    for event in events:
        if event.get("event") != "crawler_asset_plan_outcome_recorded":
            continue
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        asset_id = str(context.get("asset_id") or "").strip()
        outcome_label = str(context.get("outcome_label") or "").strip()
        if not asset_id or not outcome_label:
            continue

        plan_outcomes[asset_id] = outcome_label
        content_review_label = _content_review_label_from_context(context)
        if content_review_label:
            content_review_outcomes[asset_id] = content_review_label

        plan_passport = context.get("plan_passport") if isinstance(context.get("plan_passport"), dict) else {}
        if isinstance(plan_passport, dict) and plan_passport:
            plan_passports[asset_id] = dict(plan_passport)

        resolved_plan_path = str(context.get("resolved_plan") or "").strip()
        if not resolved_plan_path:
            continue
        try:
            payload = read_plan(resolved_plan_path)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            resolved_plans[asset_id] = payload
            if not content_review_label:
                label = adapter_review_content_summary_label(adapter_review_display_payload(payload))
                if label:
                    content_review_outcomes[asset_id] = label

    return CrawlerAssetRestoredPlanState(
        plan_outcomes=plan_outcomes,
        content_review_outcomes=content_review_outcomes,
        resolved_plans=resolved_plans,
        plan_passports=plan_passports,
    )


def crawler_asset_listing_outcomes_from_events(
    events: Iterable[dict[str, object]],
) -> dict[str, dict[str, object]]:
    """Recover compact listing/seed-enumeration state from structured events."""

    outcomes: dict[str, dict[str, object]] = {}
    for event in events:
        if event.get("event") != "crawler_asset_listing_recorded":
            continue
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        asset_id = str(context.get("asset_id") or "").strip()
        if not asset_id:
            continue
        outcomes[asset_id] = crawler_asset_listing_event_preview_payload(context)
    return outcomes


def _content_review_label_from_context(context: dict[str, object]) -> str:
    """Extract the compact content-review label already stored in an event."""

    content_review_label = str(context.get("content_review_label") or "").strip()
    if content_review_label:
        return content_review_label
    content_review_payload = context.get("content_review") if isinstance(context.get("content_review"), dict) else {}
    if isinstance(content_review_payload, dict):
        return str(content_review_payload.get("display_label") or "").strip()
    return ""
