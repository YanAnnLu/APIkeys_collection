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
from api_launcher.crawler_asset_profiles import (
    compact_crawler_asset_plan_passport,
    crawler_asset_favorite_seed_uids,
    set_crawler_asset_seed_favorite,
    update_crawler_asset_plan_passport,
)
from api_launcher.crawler_asset_service import (
    CrawlerRunner,
    CrawlerAssetListingResult,
    build_crawler_asset_download_plan,
    crawler_asset_listing_event_context,
    crawler_seed_enumeration_payload,
    run_crawler_asset_listing,
)
from api_launcher.crawler_assets import BUILD_DOWNLOAD_PLAN, CrawlerAsset, load_crawler_asset_source, load_crawler_assets
from api_launcher.developer_diagnostics import crawler_handler_smoke_diagnostics_payload
from api_launcher.crawler_run_records import crawler_run_context_summary, crawler_run_record_from_result
from api_launcher.crawler_seed_registry import crawler_seed_page, crawler_seed_row
from api_launcher.db import connect_db
from api_launcher.event_log import latest_events, log_event
from api_launcher.local_credentials import crawler_asset_credential_status, update_crawler_asset_credentials
from api_launcher.paths import default_local_downloads_root, state_file
from api_launcher.repository import ApiCatalogRepository
from api_launcher.web_real_download_demo import run_web_real_download_demo


WEB_PREVIEW_DB_NAME = "web_preview.sqlite"
WEB_PREVIEW_EVENT_LIMIT = 80
WEB_PREVIEW_DEFAULT_ENUMERATION_LIMIT = 1000
CREDENTIAL_BLOCKING_STATUSES = frozenset(
    {
        "missing_credentials",
        "partial_credentials",
        "credential_profile_required",
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
        "credentials": crawler_asset_credential_status(asset, env_path=env_path),
        "next_action": asset.next_action,
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
    target_db = Path(db_path) if db_path is not None else state_file(WEB_PREVIEW_DB_NAME)
    with contextlib.closing(connect_db(target_db)) as conn:
        repository = ApiCatalogRepository(conn)
        repository.init_schema()
        return crawler_seed_page(
            repository,
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
    if not dataset_uid:
        raise ValueError("dataset_uid is required")
    favorite = bool(payload.get("favorite", True))
    profile = set_crawler_asset_seed_favorite(asset.asset_id, dataset_uid, favorite, profile_path)
    is_favorite = dataset_uid in profile.favorite_seed_uids
    result = {
        "asset_id": asset.asset_id,
        "dataset_uid": dataset_uid,
        "favorite": is_favorite,
        "favorite_seed_count": len(profile.favorite_seed_uids),
        "next_action": "seed_favorite_saved",
    }
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
        "next_action": "review_candidates_or_build_download_plan",
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
        response["listing_result"] = {
            "asset_id": asset.asset_id,
            "source_found": True,
            "listing_mode": listing_options["listing_mode"],
            "blocked": True,
            "blocked_reason": "credential_setup_required",
            "candidate_count": 0,
            "upserted_count": 0,
            "skipped_provider_count": 0,
            "duplicate_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "next_action": "edit_local_credentials_before_live_download",
            "audit_summary": {},
            "max_results": listing_options["max_results"],
            "max_pages": listing_options["max_pages"],
            "full_crawl": True,
            "complete_seed": listing_options["complete_seed"],
            "search_scope": "blocked_by_credentials",
            "seed_enumeration": crawler_seed_enumeration_payload(blocked_result),
        }
        response["next_action"] = "edit_local_credentials_before_live_download"
        return response

    target_db = Path(db_path) if db_path is not None else state_file(WEB_PREVIEW_DB_NAME)
    with contextlib.closing(connect_db(target_db)) as conn:
        repository = ApiCatalogRepository(conn)
        repository.init_schema()
        repository.seed_builtin_providers()
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
        result = run_crawler_asset_listing(asset.asset_id, conn, **kwargs)
        conn.commit()

    payload = result.to_dict()
    response["listing_result"] = payload
    response["audit_summary"] = payload.get("audit_summary", {})
    response["next_action"] = result.next_action
    log_event(
        "crawler_asset_listing_recorded",
        "Web Preview crawler asset workflow recorded the visible listing outcome.",
        component="web.crawler_assets",
        context=crawler_asset_listing_event_context(result),
    )
    return response


def crawler_asset_listing_options(options: Mapping[str, object] | None) -> dict[str, object]:
    """Normalize Web listing controls into backend crawler bounds.

    入口分頁的預設心流是「選入口就枚舉 seed」。這個 helper 讓 Web/Tk/Qt
    後續都能共用同一組安全上限，而不是在 UI 內各自猜 crawler 參數。
    """

    values = dict(options or {})
    requested_mode = str(values.get("listing_mode") or values.get("mode") or "complete_seed").strip()
    complete_seed = requested_mode not in {"bounded", "sample", "quick_sample"}
    listing_mode = "complete_seed" if complete_seed else "bounded"
    return {
        "listing_mode": listing_mode,
        "complete_seed": complete_seed,
        "max_results": positive_int(values.get("max_results"), WEB_PREVIEW_DEFAULT_ENUMERATION_LIMIT),
        "max_pages": non_negative_int(values.get("max_pages"), 0),
    }


def positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def non_negative_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


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
        "run_record": run_record if isinstance(run_record, dict) else {},
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

    return compact_crawler_asset_plan_passport(plan_passport)


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
    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    plan_capability = next(
        (capability for capability in asset.capabilities if capability.capability_id == BUILD_DOWNLOAD_PLAN),
        None,
    )
    bounds_schema = plan_capability.bounds_schema if plan_capability is not None else ()
    source = load_crawler_asset_source(asset_id, primary_path, local_path)
    return build_crawler_asset_bound_form_spec(asset.asset_id, bounds_schema, source=source)


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

    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    credential_guard = crawler_asset_credential_status(asset, env_path=env_path)
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
        "credential_guard": credential_guard,
        "next_action": "click_build_plan_to_call_backend" if not execute else "review_plan_outcome",
    }
    if not execute:
        return response
    if credential_status_blocks_plan(credential_guard):
        # 防呆邊界：需要帳號/API Key 的來源先停在本機憑證設定，
        # 不讓 Web Preview 發出必然失敗的 live crawler request。
        response["plan_outcome"] = credential_blocked_plan_outcome(credential_guard)
        response["plan_passport"] = credential_blocked_plan_passport(asset_id, credential_guard)
        response["next_action"] = "edit_local_credentials_before_live_download"
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
    update_crawler_asset_plan_passport(result.asset_id, plan_passport, profile_path)
    response["adapter_review"] = adapter_review_display_payload(result.resolved_plan)
    response["next_action"] = result.user_next_action
    log_event(
        "crawler_asset_plan_outcome_recorded",
        "Web Preview crawler asset workflow recorded the visible plan outcome.",
        component="web.crawler_assets",
        context=crawler_asset_plan_event_context(result, plan_outcome, plan_passport=plan_passport),
    )
    return response


def credential_status_blocks_plan(credential_guard: Mapping[str, object]) -> bool:
    return str(credential_guard.get("status") or "") in CREDENTIAL_BLOCKING_STATUSES


def credential_blocked_plan_outcome(credential_guard: Mapping[str, object]) -> dict[str, object]:
    missing = credential_guard.get("missing_required")
    missing_count = len(missing) if isinstance(missing, list) else 0
    suffix = f"（缺 {missing_count} 欄）" if missing_count else ""
    return {
        "outcome_bucket": "credential_setup_required",
        "display_label": f"先設定登入 / API Key{suffix}",
        "short_label": "需要登入",
        "display_tone": "warning",
        "summary": "這個來源需要本機憑證。已先停止建立下載計畫，避免送出必然失敗的遠端請求。",
        "next_action": "edit_local_credentials_before_live_download",
        "next_action_label": "先編輯本機憑證，再建立下載計畫",
        "direct_download_count": 0,
        "review_required_count": 0,
        "content_review_label": "",
        "content_review": {},
    }


def credential_blocked_plan_passport(
    asset_id: str,
    credential_guard: Mapping[str, object],
) -> dict[str, object]:
    return {
        "asset_id": asset_id,
        "has_resolved_plan": False,
        "outcome_bucket": "credential_setup_required",
        "short_label": "需要登入",
        "display_tone": "warning",
        "candidate_count": 0,
        "direct_download_count": 0,
        "review_required_count": 0,
        "adapter_review_count": 0,
        "content_review_count": 0,
        "blocked_credential_count": len(credential_guard.get("missing_required") or ()),
        "next_action": "edit_local_credentials_before_live_download",
    }


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
        "run_record": crawler_run_record_from_result(result),
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
