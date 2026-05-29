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

from pathlib import Path
from typing import Mapping

from api_launcher.crawler_asset_display import (
    adapter_review_display_payload,
    crawler_asset_download_import_display_payload,
    crawler_asset_plan_event_context,
    crawler_asset_plan_outcome_payload,
    crawler_asset_plan_passport_payload,
    credential_blocked_plan_outcome_payload,
    credential_blocked_plan_passport_payload,
)
from api_launcher.crawler_asset_download import run_crawler_asset_download_import, run_crawler_seed_download_import
from api_launcher.crawler_asset_listing_payloads import crawler_asset_listing_event_context
from api_launcher.crawler_asset_profiles import update_crawler_asset_plan_passport
from api_launcher.crawler_asset_schema_probe import (
    crawler_asset_bound_form_schema_probe,
)
from api_launcher.crawler_asset_service import (
    CrawlerRunner,
    CrawlerAssetListingResult,
    build_crawler_asset_download_plan,
    run_crawler_asset_listing,
)
from api_launcher.event_log import log_event
from api_launcher.local_credentials import (
    crawler_asset_credential_status,
    credential_status_blocks_download,
    update_crawler_asset_credentials,
)
from api_launcher.paths import default_local_downloads_root
from frontends.web.preview_assets import (
    crawler_asset_cards,
    crawler_asset_credential_detail,
    crawler_asset_detail,
    crawler_asset_seed_page,
    crawler_asset_seed_row,
    save_crawler_asset_seed_favorite,
)
from frontends.web.preview_context import (
    crawler_asset_for_preview,
    web_crawler_asset_action_context,
    web_preview_repository_context,
)
from frontends.web.preview_payloads import (
    apply_web_next_action,
    crawler_asset_listing_options,
    web_crawler_asset_listing_payload,
    web_download_import_credential_blocked_response,
    web_download_import_event_context,
    web_download_import_target_paths,
    web_next_action_payload,
)
from frontends.web.preview_diagnostics import (
    crawler_handler_smoke_diagnostics,
    developer_real_download_demo,
    web_preview_status,
    web_project_maturity,
    web_real_download_demo,
)


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

    asset = crawler_asset_for_preview(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
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
    asset = crawler_asset_for_preview(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
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
