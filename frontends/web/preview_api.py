"""Backend API helpers for the RRKAL Web Preview surface.

The Web Preview is the UI/UX lead surface, but it should still behave like a
thin frontend.  This module adapts backend services into browser-friendly JSON:
asset cards, detail payloads, seed pages, credential status, download/import
actions, and developer diagnostics.

Do not place crawler, resolver, importer, or credential policy decisions in the
JavaScript layer.  When a new UI state is needed, add it to the backend display
or service contract first, then expose it here.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection
from typing import Iterator, Mapping

from api_launcher.crawler_asset_bound_forms import (
    CrawlerAssetBoundFormSpec,
    CrawlerAssetBoundPayload,
    crawler_asset_bound_payload_from_form_values,
)
from api_launcher.crawler_asset_display import (
    adapter_review_display_payload,
    crawler_asset_bound_form_payload,
    crawler_asset_card_capabilities,
    crawler_asset_download_import_display_payload,
    crawler_asset_flow_steps,
    crawler_asset_plan_event_context,
    crawler_asset_plan_outcome_payload,
    crawler_asset_plan_passport_payload,
    crawler_asset_recent_plan_outcomes_from_events,
    crawler_asset_recent_plan_passports_from_events,
    credential_blocked_plan_outcome_payload,
    credential_blocked_plan_passport_payload,
    next_action_display_label,
)
from api_launcher.crawler_asset_download import run_crawler_asset_download_import, run_crawler_seed_download_import
from api_launcher.crawler_asset_profiles import (
    crawler_asset_favorite_seed_uids,
    update_crawler_asset_plan_passport,
)
from api_launcher.crawler_asset_schema_probe import (
    crawler_asset_bound_form_spec,
    crawler_asset_bound_form_schema_probe,
)
from api_launcher.crawler_asset_service import (
    CrawlerRunner,
    CrawlerAssetListingResult,
    build_crawler_asset_download_plan,
    crawler_asset_listing_event_context,
    run_crawler_asset_listing,
)
from api_launcher.crawler_assets import CrawlerAsset, load_crawler_assets
from api_launcher.developer_diagnostics import crawler_handler_smoke_diagnostics_payload
from api_launcher.crawler_run_records import crawler_run_context_summary
from api_launcher.crawler_seed_registry import crawler_seed_page, crawler_seed_row, save_crawler_seed_favorite
from api_launcher.db import connect_db
from api_launcher.event_log import latest_events, log_event
from api_launcher.local_credentials import (
    crawler_asset_credential_status,
    credential_status_blocks_download,
    update_crawler_asset_credentials,
)
from api_launcher.paths import default_local_downloads_root, state_file
from api_launcher.project_maturity import build_project_maturity_payload
from api_launcher.repository import ApiCatalogRepository
from api_launcher.web_real_download_demo import run_web_real_download_demo
from frontends.web.preview_payloads import (
    WEB_PREVIEW_DB_NAME,
    apply_web_next_action,
    crawler_asset_listing_options,
    web_crawler_asset_listing_payload,
    web_download_import_credential_blocked_response,
    web_download_import_event_context,
    web_download_import_target_paths,
    web_next_action_payload,
)


WEB_PREVIEW_EVENT_LIMIT = 80


@dataclass(frozen=True)
class WebPreviewRepositorySession:
    db_path: Path
    conn: Connection
    repository: ApiCatalogRepository


@dataclass(frozen=True)
class WebCrawlerAssetActionContext:
    asset: CrawlerAsset
    credential_guard: Mapping[str, object]
    bounds_payload: CrawlerAssetBoundPayload


def web_crawler_asset_action_context(
    asset_id: str,
    values: Mapping[str, object],
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> WebCrawlerAssetActionContext:
    """Resolve the repeated Web endpoint inputs without making policy choices.

    Plan preview, asset download/import, and seed download/import all need the
    same asset, credential guard, and bounds payload before they can decide
    their route-specific behavior.  Keeping this setup in one helper prevents
    those endpoints from drifting while leaving blocking, planning, and import
    decisions explicit in the endpoint functions.
    """

    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    return WebCrawlerAssetActionContext(
        asset=asset,
        credential_guard=crawler_asset_credential_status(asset, env_path=env_path),
        bounds_payload=crawler_asset_payload_from_web_values(
            asset_id,
            values,
            primary_path=primary_path,
            local_path=local_path,
            profile_path=profile_path,
        ),
    )


def web_preview_status() -> dict[str, object]:
    """Return a small machine-readable status for browser smoke checks."""

    return {
        "product": "RuRuKa Asset Launcher",
        "surface": "web_preview",
        "purpose": "uiux_review",
        "business_logic_owner": "api_launcher",
    }


def web_project_maturity(*, db_path: str | Path | None = None) -> dict[str, object]:
    """Return the maturity matrix for the Web Preview maturity tab.

    The matrix itself is owned by `api_launcher.project_maturity`; Web only
    exposes the payload so the browser can show construction/contract surfaces
    without re-implementing maturity rules.
    """

    with web_preview_repository_context(db_path) as session:
        return build_project_maturity_payload(session.repository, db_path=session.db_path)


def crawler_handler_smoke_diagnostics() -> dict[str, object]:
    """Return a compact developer-only crawler handler contract diagnostic.

    Web Preview 需要能讓 agent / 開發者用瀏覽器確認 crawler handler 契約，
    但正式使用者下載流程不應看到完整 smoke report 或每個 source 的大 payload。
    因此這裡只回傳共用 compact summary 與清楚的 developer-only 標記。
    """

    return crawler_handler_smoke_diagnostics_payload("web_preview")


def web_real_download_demo() -> dict[str, object]:
    """Run the narrow real-download proof path for Web Preview.

    這個 endpoint 是展示用的真資料閉環：瀏覽器觸發後端既有
    download/import pipeline，實際抓取小型公開 CSV，寫 sidecar manifest，
    再匯入 isolated SQLite。它不是 crawler 全覆蓋宣告。
    """

    result = run_web_real_download_demo()
    payload = result.to_dict()
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    log_event(
        "web_real_download_demo_completed",
        "Web Preview completed a real public CSV download/import demo.",
        component="web.demo",
        context={
            "stage": payload.get("stage"),
            "succeeded": payload.get("succeeded"),
            "row_count": payload.get("row_count"),
            "table_name": payload.get("table_name"),
            "source_url": payload.get("source_url"),
            "downloaded_file": artifacts.get("downloaded_file"),
            "manifest": artifacts.get("manifest"),
            "curated_sqlite": artifacts.get("curated_sqlite"),
            "next_action": payload.get("next_action"),
        },
    )
    return payload


def developer_real_download_demo() -> dict[str, object]:
    """Run the public CSV proof path as a developer-only diagnostic."""

    payload = web_real_download_demo()
    payload["developer_only"] = True
    payload["scope"] = "developer_diagnostic_public_csv_not_main_download_flow"
    payload["main_download_endpoint"] = "POST /api/crawler-assets/{asset_id}/download-import"
    payload["seed_download_endpoint"] = "POST /api/crawler-assets/{asset_id}/seed-download-import"
    return payload


def crawler_asset_cards(
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    """Return cards for the Web Preview asset rail.

    The payload is deliberately smaller than CrawlerAsset.to_dict() so the web
    layer can render a stable UX contract without depending on every internal
    field.  The detail endpoint can still expose the full asset when needed.
    """

    assets = load_crawler_assets(primary_path, local_path, profile_path)
    latest_plan_outcomes = recent_crawler_asset_plan_outcomes()
    latest_plan_passports = recent_crawler_asset_plan_passports()
    latest_listings = recent_crawler_asset_listing_outcomes()
    return {
        "count": len(assets),
        "assets": [
            crawler_asset_card(
                asset,
                latest_plan_outcome=latest_plan_outcomes.get(asset.asset_id),
                latest_plan_passport=asset.latest_plan_passport or latest_plan_passports.get(asset.asset_id),
                latest_listing=latest_listings.get(asset.asset_id),
                env_path=env_path,
            )
            for asset in assets
        ],
    }


def crawler_asset_card(
    asset: CrawlerAsset,
    *,
    latest_plan_outcome: dict[str, object] | None = None,
    latest_plan_passport: dict[str, object] | None = None,
    latest_listing: dict[str, object] | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    """Build the compact card payload shown in the asset rail."""

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
        "capability_profile": asset.capability_profile.to_dict(),
        "capabilities": crawler_asset_card_capabilities(asset.capabilities),
        "credentials": crawler_asset_credential_status(asset, env_path=env_path),
        "next_action": asset.next_action,
        "next_action_label": next_action_display_label(asset.next_action),
        "latest_listing": latest_listing or {},
        "latest_plan_outcome": latest_plan_outcome or {},
        "latest_plan_passport": latest_plan_passport or {},
    }


def crawler_asset_detail(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    """Return detail payload for one asset, including form and flow contracts."""

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
            latest_plan_passport=asset.latest_plan_passport
            or recent_crawler_asset_plan_passports().get(asset.asset_id),
            latest_listing=recent_crawler_asset_listing_outcomes().get(asset.asset_id),
            env_path=env_path,
        ),
        "bound_form": crawler_asset_bound_form_payload(form_spec),
        "flow_steps": crawler_asset_flow_steps(asset, form_spec),
    }


def crawler_asset_seed_page(
    asset_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    db_path: str | Path | None = None,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    """Return a paged view of seeds already enumerated into the local catalog."""

    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    favorite_seed_uids = set(crawler_asset_favorite_seed_uids(asset.asset_id, profile_path))
    with web_preview_repository_context(db_path) as session:
        return crawler_seed_page(
            session.repository,
            asset_id=asset.asset_id,
            provider_id=asset.provider_id,
            page=page,
            page_size=page_size,
            favorite_seed_uids=favorite_seed_uids,
        )


def crawler_asset_seed_row(
    dataset: object,
    *,
    favorite_seed_uids: set[str] | frozenset[str] | None = None,
) -> dict[str, object]:
    return crawler_seed_row(dataset, favorite_seed_uids=favorite_seed_uids or ())


def save_crawler_asset_seed_favorite(
    asset_id: str,
    payload: Mapping[str, object],
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    """Persist a seed-level favorite for Web/Tk/Qt shared profile state."""

    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    dataset_uid = str(payload.get("dataset_uid") or "").strip()
    favorite = bool(payload.get("favorite", True))
    result = save_crawler_seed_favorite(
        asset_id=asset.asset_id,
        dataset_uid=dataset_uid,
        favorite=favorite,
        profile_path=profile_path,
    )
    log_event(
        "crawler_asset_seed_favorite_updated",
        "Web Preview updated a seed-level favorite.",
        component="web.crawler_assets",
        context=result,
    )
    return result


def crawler_asset_credential_detail(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    return crawler_asset_credential_status(asset, env_path=env_path)


def crawler_asset_listing(
    asset_id: str,
    *,
    db_path: str | Path | None = None,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
    options: Mapping[str, object] | None = None,
    crawler_runner: CrawlerRunner | None = None,
) -> dict[str, object]:
    """Run the crawler asset listing path for Web/Tk/Qt-style UX.

    This is the first real crawler action a human should try before building a
    download plan: it refreshes the source candidate list, records a compact
    audit event, and keeps credential-gated assets out of doomed live requests.
    """

    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    credential_guard = crawler_asset_credential_status(asset, env_path=env_path)
    listing_options = crawler_asset_listing_options(options)
    response: dict[str, object] = {
        "asset_id": asset.asset_id,
        "credential_guard": credential_guard,
        "listing_options": listing_options,
        **web_next_action_payload("review_candidates_or_build_download_plan"),
    }
    if credential_status_blocks_plan(credential_guard):
        blocked_result = CrawlerAssetListingResult(
            asset_id=asset.asset_id,
            source_found=True,
            listing_mode=listing_options["listing_mode"],
            blocked_reason="credential_setup_required",
            next_action="edit_local_credentials_before_live_download",
            max_results=listing_options["max_results"],
            max_pages=listing_options["max_pages"],
            full_crawl=True,
            complete_seed=listing_options["complete_seed"],
            search_scope="blocked_by_credentials",
        )
        response["listing_result"] = web_crawler_asset_listing_payload(blocked_result)
        apply_web_next_action(response, "edit_local_credentials_before_live_download")
        return response

    with web_preview_repository_context(db_path, seed_builtin_providers=True) as session:
        kwargs: dict[str, object] = {
            "primary_path": primary_path,
            "local_path": local_path,
            "profile_path": profile_path,
            "max_results": listing_options["max_results"],
            "max_pages": listing_options["max_pages"],
            "full_crawl": True,
            "complete_seed": listing_options["complete_seed"],
        }
        if crawler_runner is not None:
            kwargs["crawl_runner"] = crawler_runner
        result = run_crawler_asset_listing(asset.asset_id, session.conn, **kwargs)
        session.conn.commit()

    payload = web_crawler_asset_listing_payload(result)
    response["listing_result"] = payload
    response["audit_summary"] = payload.get("audit_summary", {})
    apply_web_next_action(response, result.next_action)
    log_event(
        "crawler_asset_listing_recorded",
        "Web Preview crawler asset workflow recorded the visible listing outcome.",
        component="web.crawler_assets",
        context=crawler_asset_listing_event_context(result),
    )
    return response


def save_crawler_asset_credentials(
    asset_id: str,
    payload: Mapping[str, object],
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    status = update_crawler_asset_credentials(asset, payload, env_path=env_path)
    log_event(
        "crawler_asset_local_credentials_updated",
        "Web Preview updated local credential settings for a crawler asset.",
        component="web.credentials",
        context={
            "asset_id": asset.asset_id,
            "provider_id": asset.provider_id,
            "status": status.get("status"),
            "configured_count": status.get("configured_count"),
            "field_count": status.get("field_count"),
            "env_vars": [field.get("env_var") for field in status.get("fields", []) if isinstance(field, dict)],
            "next_action": status.get("next_action"),
        },
    )
    return status


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
    """Return the newest recorded plan outcome for each crawler asset.

    Tk and Web both write/read the same structured event stream, so the preview
    can show recent backend state without localStorage or duplicate UI rules.
    """

    return crawler_asset_recent_plan_outcomes_from_events(latest_events(limit))


def recent_crawler_asset_plan_passports(*, limit: int = 200) -> dict[str, dict[str, object]]:
    """Return the newest compact plan passport recorded for each asset.

    Event logs may outlive the browser session, but they must not become a
    second resolved-plan store.  Only the compact passport keys needed by
    Web/Tk/Qt status panels are allowed through this boundary.
    """

    return crawler_asset_recent_plan_passports_from_events(latest_events(limit))


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
    context_summary = crawler_run_context_summary(context)
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
    return crawler_asset_bound_form_spec(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )


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
    env_path: str | Path | None = None,
) -> dict[str, object]:
    """Preview or execute the crawler-asset plan build.

    ``execute=False`` is the default for UIUX work: it proves the dynamic form
    can produce the same backend payload without making a live crawl.  When the
    user explicitly clicks the build-plan button, ``execute=True`` calls the
    existing crawler asset service and keeps unresolved work in adapter review.
    """

    action_context = web_crawler_asset_action_context(
        asset_id,
        values,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
        env_path=env_path,
    )
    asset = action_context.asset
    credential_guard = action_context.credential_guard
    payload = action_context.bounds_payload
    response: dict[str, object] = {
        "asset_id": asset_id,
        "execute": execute,
        "bounds_payload": payload.to_dict(),
        "credential_guard": credential_guard,
        **web_next_action_payload("click_build_plan_to_call_backend" if not execute else "review_plan_outcome"),
    }
    if not execute:
        return response
    if credential_status_blocks_plan(credential_guard):
        # 防呆邊界：需要帳號/API Key 的來源先停在本機憑證設定，
        # 不讓 Web Preview 發出必然失敗的 live crawler request。
        response["plan_outcome"] = credential_blocked_plan_outcome_payload(credential_guard)
        response["plan_passport"] = credential_blocked_plan_passport_payload(asset_id, credential_guard)
        apply_web_next_action(response, "edit_local_credentials_before_live_download")
        return response

    target_downloads = Path(downloads_root) if downloads_root is not None else default_local_downloads_root()
    with web_preview_repository_context(db_path, seed_builtin_providers=True) as session:
        result = build_crawler_asset_download_plan(
            asset_id,
            session.conn,
            bounds_payload=payload,
            downloads_root=target_downloads,
            primary_path=primary_path,
            local_path=local_path,
            profile_path=profile_path,
            timeout=8.0,
            max_results=1,
            max_pages=1,
        )
        session.conn.commit()
    response["plan_result"] = result.to_dict()
    plan_outcome = crawler_asset_plan_outcome_payload(result)
    response["plan_outcome"] = plan_outcome
    plan_passport = crawler_asset_plan_passport_payload(result, plan_outcome=plan_outcome)
    response["plan_passport"] = plan_passport
    update_crawler_asset_plan_passport(result.asset_id, plan_passport, profile_path)
    response["adapter_review"] = adapter_review_display_payload(result.resolved_plan)
    apply_web_next_action(response, result.user_next_action)
    if plan_outcome.get("next_action_label"):
        response["next_action_label"] = str(plan_outcome["next_action_label"])
    log_event(
        "crawler_asset_plan_outcome_recorded",
        "Web Preview crawler asset workflow recorded the visible plan outcome.",
        component="web.crawler_assets",
        context=crawler_asset_plan_event_context(result, plan_outcome, plan_passport=plan_passport),
    )
    return response


def crawler_asset_download_import(
    asset_id: str,
    values: Mapping[str, object],
    *,
    db_path: str | Path | None = None,
    downloads_root: str | Path | None = None,
    import_sqlite_path: str | Path | None = None,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    """Run the formal crawler-asset download/import path for Web Preview.

    Unlike ``web_real_download_demo()``, this endpoint starts from the selected
    crawler asset and dynamic bounds form.  Review-only sources still return a
    structured blocked/review result instead of pretending a download happened.
    """

    action_context = web_crawler_asset_action_context(
        asset_id,
        values,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
        env_path=env_path,
    )
    asset = action_context.asset
    credential_guard = action_context.credential_guard
    payload = action_context.bounds_payload
    response: dict[str, object] = {
        "asset_id": asset.asset_id,
        "bounds_payload": payload.to_dict(),
        "credential_guard": credential_guard,
        **web_next_action_payload("run_crawler_asset_download_import"),
    }
    if credential_status_blocks_plan(credential_guard):
        return web_download_import_credential_blocked_response(
            asset.asset_id,
            payload.to_dict(),
            credential_guard,
            initial_next_action="run_crawler_asset_download_import",
        )

    targets = web_download_import_target_paths(
        asset.asset_id,
        db_path=db_path,
        downloads_root=downloads_root,
        import_sqlite_path=import_sqlite_path,
    )
    with web_preview_repository_context(targets.db_path, seed_builtin_providers=True) as session:
        result = run_crawler_asset_download_import(
            asset.asset_id,
            session.repository,
            targets.downloads_root,
            bounds_payload=payload,
            import_sqlite_path=targets.import_sqlite_path,
            plan_path=targets.plan_path,
            primary_path=primary_path,
            local_path=local_path,
            profile_path=profile_path,
            timeout=8.0,
            max_results=1,
            max_pages=1,
        )
        session.conn.commit()

    response.update(crawler_asset_download_import_display_payload(result))
    plan_outcome = response["plan_outcome"] if isinstance(response.get("plan_outcome"), dict) else {}
    plan_passport = response["plan_passport"] if isinstance(response.get("plan_passport"), dict) else {}
    update_crawler_asset_plan_passport(result.asset_id, plan_passport, profile_path)
    log_event(
        "crawler_asset_download_import_completed",
        "Web Preview ran the formal crawler asset download/import path.",
        component="web.crawler_assets",
        context=web_download_import_event_context(result, plan_outcome, plan_passport),
    )
    return response


def crawler_seed_download_import(
    asset_id: str,
    values: Mapping[str, object],
    *,
    db_path: str | Path | None = None,
    downloads_root: str | Path | None = None,
    import_sqlite_path: str | Path | None = None,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    """Run the formal download/import path for one visible seed row."""

    dataset_uid = str(values.get("dataset_uid") or "").strip()
    if not dataset_uid:
        raise ValueError("dataset_uid is required")
    action_context = web_crawler_asset_action_context(
        asset_id,
        values,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
        env_path=env_path,
    )
    asset = action_context.asset
    credential_guard = action_context.credential_guard
    payload = action_context.bounds_payload
    response: dict[str, object] = {
        "asset_id": asset.asset_id,
        "dataset_uid": dataset_uid,
        "bounds_payload": payload.to_dict(),
        "credential_guard": credential_guard,
        **web_next_action_payload("run_crawler_seed_download_import"),
    }
    if credential_status_blocks_plan(credential_guard):
        return web_download_import_credential_blocked_response(
            asset.asset_id,
            payload.to_dict(),
            credential_guard,
            dataset_uid=dataset_uid,
            initial_next_action="run_crawler_seed_download_import",
        )

    targets = web_download_import_target_paths(
        asset.asset_id,
        dataset_uid=dataset_uid,
        db_path=db_path,
        downloads_root=downloads_root,
        import_sqlite_path=import_sqlite_path,
    )
    with web_preview_repository_context(targets.db_path, seed_builtin_providers=True) as session:
        result = run_crawler_seed_download_import(
            asset.asset_id,
            dataset_uid,
            session.repository,
            targets.downloads_root,
            bounds_payload=payload,
            import_sqlite_path=targets.import_sqlite_path,
            plan_path=targets.plan_path,
            primary_path=primary_path,
            local_path=local_path,
            profile_path=profile_path,
            timeout=8.0,
        )
        session.conn.commit()

    response.update(crawler_asset_download_import_display_payload(result))
    plan_outcome = response["plan_outcome"] if isinstance(response.get("plan_outcome"), dict) else {}
    plan_passport = response["plan_passport"] if isinstance(response.get("plan_passport"), dict) else {}
    update_crawler_asset_plan_passport(result.asset_id, plan_passport, profile_path)
    log_event(
        "crawler_seed_download_import_completed",
        "Web Preview ran the formal seed download/import path.",
        component="web.crawler_assets",
        context=web_download_import_event_context(result, plan_outcome, plan_passport, dataset_uid=dataset_uid),
    )
    return response


def credential_status_blocks_plan(credential_guard: Mapping[str, object]) -> bool:
    return credential_status_blocks_download(credential_guard)


@contextlib.contextmanager
def web_preview_repository_context(
    db_path: str | Path | None = None,
    *,
    seed_builtin_providers: bool = False,
) -> Iterator[WebPreviewRepositorySession]:
    """Open a Web Preview repository session without hiding commit policy.

    The endpoint still decides when to commit.  This helper only centralizes the
    repeated connection/schema/provider bootstrap so route functions stay thin.
    """

    target_db = Path(db_path) if db_path is not None else state_file(WEB_PREVIEW_DB_NAME)
    with contextlib.closing(connect_db(target_db)) as conn:
        repository = ApiCatalogRepository(conn)
        repository.init_schema()
        if seed_builtin_providers:
            repository.seed_builtin_providers()
        yield WebPreviewRepositorySession(db_path=target_db, conn=conn, repository=repository)


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
