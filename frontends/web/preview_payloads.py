from __future__ import annotations

from dataclasses import dataclass
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
    download_import_stage_display_label,
)
from api_launcher.crawler_next_action_display import next_action_display_label_or_fallback
from api_launcher.crawler_asset_service import CrawlerAssetListingResult
from api_launcher.downloads.staging import safe_path_part
from api_launcher.paths import default_local_downloads_root, state_file


WEB_PREVIEW_DB_NAME = "web_preview.sqlite"
WEB_PREVIEW_DEFAULT_ENUMERATION_LIMIT = 1000


@dataclass(frozen=True)
class WebDownloadImportTargetPaths:
    db_path: Path
    downloads_root: Path
    import_sqlite_path: Path
    plan_path: Path


@dataclass(frozen=True)
class WebDownloadImportResultResponse:
    response: dict[str, object]
    plan_outcome: Mapping[str, object]
    plan_passport: Mapping[str, object]


@dataclass(frozen=True)
class WebPlanPreviewResultResponse:
    response: dict[str, object]
    plan_outcome: Mapping[str, object]
    plan_passport: Mapping[str, object]


def web_next_action_payload(next_action: object) -> dict[str, str]:
    """Pair a backend next_action id with the shared display label."""

    action = str(next_action or "").strip()
    return {
        "next_action": action,
        "next_action_label": next_action_display_label_or_fallback(action),
    }


def apply_web_next_action(response: dict[str, object], next_action: object) -> None:
    """Update an existing Web payload with the shared next-action contract."""

    response.update(web_next_action_payload(next_action))


def web_crawler_asset_listing_payload(result: CrawlerAssetListingResult) -> dict[str, object]:
    """Expose one listing result shape and add the Web display label."""

    payload = result.to_dict()
    payload["next_action_label"] = next_action_display_label_or_fallback(payload.get("next_action"))
    return payload


def web_crawler_asset_listing_result_response(result: CrawlerAssetListingResult) -> dict[str, object]:
    """Return the shared Web response fragment for a completed listing run."""

    payload = web_crawler_asset_listing_payload(result)
    response: dict[str, object] = {
        "listing_result": payload,
        "audit_summary": payload.get("audit_summary", {}),
    }
    apply_web_next_action(response, result.next_action)
    return response


def web_crawler_asset_listing_credential_blocked_response(
    asset_id: str,
    credential_guard: Mapping[str, object],
    listing_options: Mapping[str, object],
) -> dict[str, object]:
    """Return the shared Web payload when listing is blocked by credentials."""

    next_action = "edit_local_credentials_before_live_download"
    blocked_result = CrawlerAssetListingResult(
        asset_id=asset_id,
        source_found=True,
        listing_mode=str(listing_options.get("listing_mode") or "complete_seed"),
        blocked_reason="credential_setup_required",
        next_action=next_action,
        max_results=positive_int(listing_options.get("max_results"), WEB_PREVIEW_DEFAULT_ENUMERATION_LIMIT),
        max_pages=non_negative_int(listing_options.get("max_pages"), 0),
        full_crawl=True,
        complete_seed=bool(listing_options.get("complete_seed")),
        search_scope="blocked_by_credentials",
    )
    response: dict[str, object] = {
        "asset_id": asset_id,
        "credential_guard": credential_guard,
        "listing_options": dict(listing_options),
        **web_next_action_payload("review_candidates_or_build_download_plan"),
        "listing_result": web_crawler_asset_listing_payload(blocked_result),
    }
    apply_web_next_action(response, next_action)
    return response


def web_crawler_asset_credentials_event_context(
    asset: object,
    status: Mapping[str, object],
) -> dict[str, object]:
    """Return the safe event context for Web credential updates.

    Credential values themselves must stay out of the event log.  The event only
    records which profile/fields changed and the backend status that resulted.
    """

    fields = status.get("fields") if isinstance(status.get("fields"), list) else []
    return {
        "asset_id": str(getattr(asset, "asset_id", "") or ""),
        "provider_id": str(getattr(asset, "provider_id", "") or ""),
        "status": status.get("status"),
        "configured_count": status.get("configured_count"),
        "field_count": status.get("field_count"),
        "env_vars": [field.get("env_var") for field in fields if isinstance(field, dict)],
        "next_action": status.get("next_action"),
    }


def crawler_asset_listing_options(options: Mapping[str, object] | None) -> dict[str, object]:
    """Normalize Web listing controls into backend crawler bounds.

    Web asks for complete seed enumeration by default so users can inspect an
    entrance before choosing a seed. The backend still owns source-specific
    page caps, rate limits, credential gates, and pagination status.
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


def web_download_import_target_paths(
    asset_id: str,
    *,
    dataset_uid: str = "",
    db_path: str | Path | None = None,
    downloads_root: str | Path | None = None,
    import_sqlite_path: str | Path | None = None,
) -> WebDownloadImportTargetPaths:
    """Resolve Web Preview download/import paths without duplicating route logic.

    Seed-level runs get a stable seed subdirectory only for the default Web
    downloads root. Tests and callers that pass ``downloads_root`` keep exact
    path control.
    """

    target_db = Path(db_path) if db_path is not None else state_file(WEB_PREVIEW_DB_NAME)
    if downloads_root is not None:
        target_downloads = Path(downloads_root)
    else:
        target_downloads = default_local_downloads_root() / "RuRuKa Asset Launcher Web Preview" / asset_id
        if dataset_uid:
            target_downloads = target_downloads / safe_path_part(dataset_uid)[:96]
    target_import_sqlite = (
        Path(import_sqlite_path) if import_sqlite_path is not None else target_downloads / "curated_sources.db"
    )
    plan_name = "resolved_seed_download_plan.json" if dataset_uid else "resolved_download_plan.json"
    return WebDownloadImportTargetPaths(
        db_path=target_db,
        downloads_root=target_downloads,
        import_sqlite_path=target_import_sqlite,
        plan_path=target_downloads / plan_name,
    )


def web_download_import_event_context(
    result: object,
    plan_outcome: Mapping[str, object],
    plan_passport: Mapping[str, object],
    *,
    dataset_uid: str = "",
) -> dict[str, object]:
    """Build the shared event payload for Web download/import completion."""

    context = {
        **crawler_asset_plan_event_context(result.plan_result, plan_outcome, plan_passport=plan_passport),
        "stage": result.pipeline.stage,
        "succeeded": result.succeeded,
        "download_import": result.pipeline.to_dict(),
        "artifacts": result.to_dict().get("artifacts", {}),
    }
    if dataset_uid:
        context["dataset_uid"] = dataset_uid
    return context


def web_download_import_result_response(result: object) -> WebDownloadImportResultResponse:
    """Return the shared Web response fragment for download/import completion.

    The route still owns side effects such as profile passport persistence and
    event logging.  This helper keeps the display payload extraction in one
    place so asset-level and seed-level routes cannot drift.
    """

    response = crawler_asset_download_import_display_payload(result)
    plan_outcome = response["plan_outcome"] if isinstance(response.get("plan_outcome"), dict) else {}
    plan_passport = response["plan_passport"] if isinstance(response.get("plan_passport"), dict) else {}
    return WebDownloadImportResultResponse(
        response=response,
        plan_outcome=plan_outcome,
        plan_passport=plan_passport,
    )


def web_download_import_credential_blocked_response(
    asset_id: str,
    bounds_payload: Mapping[str, object],
    credential_guard: Mapping[str, object],
    *,
    dataset_uid: str = "",
    initial_next_action: str,
) -> dict[str, object]:
    """Return the shared Web payload for download/import credential blocks."""

    next_action = "edit_local_credentials_before_live_download"
    response: dict[str, object] = {
        "asset_id": asset_id,
        "bounds_payload": dict(bounds_payload),
        "credential_guard": credential_guard,
        **web_next_action_payload(initial_next_action),
        "plan_outcome": credential_blocked_plan_outcome_payload(credential_guard),
        "plan_passport": credential_blocked_plan_passport_payload(asset_id, credential_guard),
        "download_import": {
            "stage": "blocked_before_download",
            "stage_label": download_import_stage_display_label("blocked_before_download"),
            "succeeded": False,
            **web_next_action_payload(next_action),
        },
    }
    if dataset_uid:
        response["dataset_uid"] = dataset_uid
    apply_web_next_action(response, next_action)
    return response


def web_plan_preview_credential_blocked_response(
    asset_id: str,
    bounds_payload: Mapping[str, object],
    credential_guard: Mapping[str, object],
    *,
    execute: bool,
) -> dict[str, object]:
    """Return the shared Web payload for plan-preview credential blocks."""

    response: dict[str, object] = {
        "asset_id": asset_id,
        "execute": execute,
        "bounds_payload": dict(bounds_payload),
        "credential_guard": credential_guard,
        **web_next_action_payload("review_plan_outcome"),
        "plan_outcome": credential_blocked_plan_outcome_payload(credential_guard),
        "plan_passport": credential_blocked_plan_passport_payload(asset_id, credential_guard),
    }
    apply_web_next_action(response, "edit_local_credentials_before_live_download")
    return response


def web_plan_preview_result_payload(result: object) -> WebPlanPreviewResultResponse:
    """Return the shared Web response bundle for an executed plan preview.

    The response dict is what the browser receives.  The compact outcome and
    passport are broken out for the route because it must persist the passport
    and log an event without re-reading display fields from a generic dict.
    """

    plan_outcome = crawler_asset_plan_outcome_payload(result)
    plan_passport = crawler_asset_plan_passport_payload(result, plan_outcome=plan_outcome)
    response: dict[str, object] = {
        "plan_result": result.to_dict(),
        "plan_outcome": plan_outcome,
        "plan_passport": plan_passport,
        "adapter_review": adapter_review_display_payload(result.resolved_plan),
    }
    apply_web_next_action(response, result.user_next_action)
    if plan_outcome.get("next_action_label"):
        response["next_action_label"] = str(plan_outcome["next_action_label"])
    return WebPlanPreviewResultResponse(
        response=response,
        plan_outcome=plan_outcome,
        plan_passport=plan_passport,
    )


def web_plan_preview_result_response(result: object) -> dict[str, object]:
    """Return the shared Web response fragment for an executed plan preview."""

    return web_plan_preview_result_payload(result).response
