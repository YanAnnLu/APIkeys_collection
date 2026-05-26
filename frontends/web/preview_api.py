from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Mapping

from api_launcher.crawler_asset_bound_forms import (
    CrawlerAssetBoundFormSpec,
    CrawlerAssetBoundPayload,
    build_crawler_asset_bound_form_spec,
    crawler_asset_bound_payload_from_form_values,
)
from api_launcher.crawler_asset_display import (
    adapter_review_display_payload,
    crawler_asset_bound_form_payload,
    crawler_asset_card_capabilities,
    crawler_asset_flow_steps,
    crawler_asset_plan_event_badge_payload,
    crawler_asset_plan_outcome_payload,
    crawler_asset_plan_passport_payload,
)
from api_launcher.crawler_asset_service import build_crawler_asset_download_plan
from api_launcher.crawler_assets import BUILD_DOWNLOAD_PLAN, CrawlerAsset, load_crawler_assets
from api_launcher.db import connect_db
from api_launcher.event_log import latest_events, log_event
from api_launcher.paths import default_local_downloads_root, state_file
from api_launcher.repository import ApiCatalogRepository


WEB_PREVIEW_DB_NAME = "web_preview.sqlite"
WEB_PREVIEW_EVENT_LIMIT = 80
WEB_PREVIEW_PLAN_PASSPORT_KEYS = frozenset(
    {
        "asset_id",
        "has_resolved_plan",
        "outcome_bucket",
        "short_label",
        "display_tone",
        "candidate_count",
        "upserted_candidate_count",
        "selected_version_count",
        "filtered_version_count",
        "direct_download_count",
        "review_required_count",
        "adapter_review_count",
        "content_review_count",
        "blocked_credential_count",
        "credential_gate_count",
        "missing_provider_count",
        "next_action",
        "bounds",
    }
)


def web_preview_status() -> dict[str, object]:
    """Return a small machine-readable status for browser smoke checks."""

    return {
        "product": "RuRuKa Asset Launcher",
        "surface": "web_preview",
        "purpose": "uiux_review",
        "business_logic_owner": "api_launcher",
    }


def crawler_asset_cards(
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    """Return cards for the Web Preview asset rail.

    The payload is deliberately smaller than CrawlerAsset.to_dict() so the web
    layer can render a stable UX contract without depending on every internal
    field.  The detail endpoint can still expose the full asset when needed.
    """

    assets = load_crawler_assets(primary_path, local_path, profile_path)
    latest_plan_outcomes = recent_crawler_asset_plan_outcomes()
    latest_plan_passports = recent_crawler_asset_plan_passports()
    return {
        "count": len(assets),
        "assets": [
            crawler_asset_card(
                asset,
                latest_plan_outcome=latest_plan_outcomes.get(asset.asset_id),
                latest_plan_passport=latest_plan_passports.get(asset.asset_id),
            )
            for asset in assets
        ],
    }


def crawler_asset_card(
    asset: CrawlerAsset,
    *,
    latest_plan_outcome: dict[str, object] | None = None,
    latest_plan_passport: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "asset_id": asset.asset_id,
        "display_name": asset.display_name,
        "provider_id": asset.provider_id,
        "source_type": asset.source_type,
        "source_surface": asset.source_surface,
        "endpoint_url": asset.endpoint_url,
        "docs_url": asset.docs_url,
        "categories": list(asset.categories),
        "geographic_scope": asset.geographic_scope,
        "maturity": asset.maturity,
        "risk_tier": asset.risk_tier,
        "trust_score": asset.trust_score,
        "seed_summary": asset.seed_summary,
        "current_seed_scope": asset.current_seed_scope,
        "enabled": asset.enabled,
        "archived": asset.archived,
        "health": asset.health.to_dict(),
        "capabilities": crawler_asset_card_capabilities(asset.capabilities),
        "next_action": asset.next_action,
        "latest_plan_outcome": latest_plan_outcome or {},
        "latest_plan_passport": latest_plan_passport or {},
    }


def crawler_asset_detail(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    form_spec = crawler_asset_bound_form(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    return {
        "asset": asset.to_dict(),
        "card": crawler_asset_card(
            asset,
            latest_plan_outcome=recent_crawler_asset_plan_outcomes().get(asset.asset_id),
            latest_plan_passport=recent_crawler_asset_plan_passports().get(asset.asset_id),
        ),
        "bound_form": crawler_asset_bound_form_payload(form_spec),
        "flow_steps": crawler_asset_flow_steps(asset, form_spec),
    }


def recent_crawler_asset_plan_outcomes(*, limit: int = 200) -> dict[str, dict[str, object]]:
    """Return the newest recorded plan outcome for each crawler asset.

    Tk and Web both write/read the same structured event stream, so the preview
    can show recent backend state without localStorage or duplicate UI rules.
    """

    outcomes: dict[str, dict[str, object]] = {}
    for event in latest_events(limit):
        if event.get("event") != "crawler_asset_plan_outcome_recorded":
            continue
        context = event.get("context")
        if not isinstance(context, dict):
            continue
        asset_id = str(context.get("asset_id") or "").strip()
        if not asset_id:
            continue
        outcomes[asset_id] = crawler_asset_plan_event_badge_payload(context)
    return outcomes


def recent_crawler_asset_plan_passports(*, limit: int = 200) -> dict[str, dict[str, object]]:
    """Return the newest compact plan passport recorded for each asset.

    Event logs may outlive the browser session, but they must not become a
    second resolved-plan store.  Only the compact passport keys needed by
    Web/Tk/Qt status panels are allowed through this boundary.
    """

    passports: dict[str, dict[str, object]] = {}
    for event in latest_events(limit):
        if event.get("event") != "crawler_asset_plan_outcome_recorded":
            continue
        context = event.get("context")
        if not isinstance(context, dict):
            continue
        asset_id = str(context.get("asset_id") or "").strip()
        if not asset_id:
            continue
        passport = compact_web_plan_passport_payload(context.get("plan_passport"))
        if passport:
            passports[asset_id] = passport
    return passports


def compact_web_plan_passport_payload(plan_passport: object) -> dict[str, object]:
    """Keep event-backed plan passports bounded and UI-safe."""

    if not isinstance(plan_passport, Mapping):
        return {}
    payload = {
        key: value
        for key, value in plan_passport.items()
        if key in WEB_PREVIEW_PLAN_PASSPORT_KEYS
    }
    bounds = payload.get("bounds")
    if "bounds" in payload and not isinstance(bounds, Mapping):
        payload["bounds"] = {}
    return dict(payload)


def web_preview_recent_events(*, limit: int = 50) -> dict[str, object]:
    """Return bounded structured events for the Web Preview event workspace.

    Web 只顯示可閱讀摘要，不把可能很大的 plan/context 原文搬進 UI 狀態；
    agent 若需要完整事件，仍應讀 `state/logs/launcher_events.jsonl`。
    """

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
    summary_keys = (
        "asset_id",
        "outcome_bucket",
        "outcome_label",
        "direct_download_count",
        "review_required_count",
        "review_queue_count",
        "stage",
        "succeeded",
        "row_count",
        "next_action",
        "user_next_action",
    )
    context_summary = {key: context[key] for key in summary_keys if key in context}
    if isinstance(context.get("content_review"), dict):
        content_review = context["content_review"]
        context_summary["content_review"] = {
            "display_label": content_review.get("display_label", ""),
            "display_tone": content_review.get("display_tone", ""),
            "count": content_review.get("count", 0),
            "has_review": bool(content_review.get("has_review")),
        }
    return {
        "timestamp": str(event.get("timestamp") or ""),
        "level": str(event.get("level") or "info"),
        "event": str(event.get("event") or ""),
        "component": str(event.get("component") or ""),
        "message": str(event.get("message") or ""),
        "context_summary": context_summary,
    }


def crawler_asset_bound_form(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAssetBoundFormSpec:
    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    plan_capability = next(
        (capability for capability in asset.capabilities if capability.capability_id == BUILD_DOWNLOAD_PLAN),
        None,
    )
    bounds_schema = plan_capability.bounds_schema if plan_capability is not None else ()
    return build_crawler_asset_bound_form_spec(asset.asset_id, bounds_schema)


def crawler_asset_payload_from_web_values(
    asset_id: str,
    values: Mapping[str, object],
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAssetBoundPayload:
    form_spec = crawler_asset_bound_form(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    return crawler_asset_bound_payload_from_form_values(form_spec, values)


def crawler_asset_plan_preview(
    asset_id: str,
    values: Mapping[str, object],
    *,
    execute: bool = False,
    db_path: str | Path | None = None,
    downloads_root: str | Path | None = None,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    """Preview or execute the crawler-asset plan build.

    ``execute=False`` is the default for UIUX work: it proves the dynamic form
    can produce the same backend payload without making a live crawl.  When the
    user explicitly clicks the build-plan button, ``execute=True`` calls the
    existing crawler asset service and keeps unresolved work in adapter review.
    """

    payload = crawler_asset_payload_from_web_values(
        asset_id,
        values,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    response: dict[str, object] = {
        "asset_id": asset_id,
        "execute": execute,
        "bounds_payload": payload.to_dict(),
        "next_action": "click_build_plan_to_call_backend" if not execute else "review_plan_outcome",
    }
    if not execute:
        return response

    target_db = Path(db_path) if db_path is not None else state_file(WEB_PREVIEW_DB_NAME)
    target_downloads = Path(downloads_root) if downloads_root is not None else default_local_downloads_root()
    with contextlib.closing(connect_db(target_db)) as conn:
        repository = ApiCatalogRepository(conn)
        repository.init_schema()
        repository.seed_builtin_providers()
        result = build_crawler_asset_download_plan(
            asset_id,
            conn,
            bounds_payload=payload,
            downloads_root=target_downloads,
            primary_path=primary_path,
            local_path=local_path,
            profile_path=profile_path,
        )
        conn.commit()
    response["plan_result"] = result.to_dict()
    plan_outcome = crawler_asset_plan_outcome_payload(result)
    response["plan_outcome"] = plan_outcome
    plan_passport = crawler_asset_plan_passport_payload(result, plan_outcome=plan_outcome)
    response["plan_passport"] = plan_passport
    response["adapter_review"] = adapter_review_display_payload(result.resolved_plan)
    response["next_action"] = result.user_next_action
    log_event(
        "crawler_asset_plan_outcome_recorded",
        "Web Preview crawler asset workflow recorded the visible plan outcome.",
        component="web.crawler_assets",
        context=crawler_asset_plan_event_context(result, plan_outcome, plan_passport=plan_passport),
    )
    return response


def crawler_asset_plan_event_context(
    result: object,
    plan_outcome: Mapping[str, object],
    *,
    added_count: int = 0,
    plan_passport: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the shared event context used by Tk/Web/Qt plan-outcome badges.

    Web Preview does not write a resolved-plan file like Tk does, so it records
    a compact event context only.  The card badge can be rebuilt from this
    payload without logging the full plan into JSONL.
    """

    content_review = plan_outcome.get("content_review")
    return {
        "asset_id": str(getattr(result, "asset_id", "") or ""),
        "outcome_bucket": str(
            getattr(result, "outcome_bucket", "")
            or plan_outcome.get("outcome_bucket")
            or ""
        ),
        "outcome_label": str(plan_outcome.get("short_label") or plan_outcome.get("display_label") or ""),
        "added_count": added_count,
        "direct_download_count": int(getattr(result, "direct_download_count", 0) or 0),
        "review_required_count": int(getattr(result, "review_required_count", 0) or 0),
        "review_queue_count": int(getattr(result, "review_required_count", 0) or 0),
        "content_review_label": str(plan_outcome.get("content_review_label") or ""),
        "content_review": content_review if isinstance(content_review, dict) else {},
        "resolved_plan": "",
        "resolved_plan_available": bool(getattr(result, "resolved_plan", None)),
        "plan_passport": compact_web_plan_passport_payload(plan_passport),
        "user_next_action": str(
            getattr(result, "user_next_action", "")
            or getattr(result, "next_action", "")
            or plan_outcome.get("next_action")
            or ""
        ),
    }


def _crawler_asset(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAsset:
    key = asset_id.strip()
    for asset in load_crawler_assets(primary_path, local_path, profile_path):
        if asset.asset_id == key:
            return asset
    raise KeyError(f"crawler asset not found: {asset_id}")
