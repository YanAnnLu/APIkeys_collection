from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from api_launcher.adapter_review import adapter_review_items
from api_launcher.crawler_asset_display import (
    crawler_asset_download_import_display_payload,
    crawler_asset_plan_event_context,
    crawler_asset_plan_outcome_payload,
    crawler_asset_plan_passport_payload,
)
from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundPayload
from api_launcher.crawler_asset_listing_payloads import crawler_asset_listing_event_context
from api_launcher.crawler_next_action_display import next_action_display_label_or_fallback
from api_launcher.crawler_plan_outcome_display import blocked_reason_display_label_or_fallback
from api_launcher.crawler_assets import (
    BUILD_DOWNLOAD_PLAN,
    CrawlerAsset,
    crawler_asset_access_requirement_display_label,
    crawler_asset_maturity_label,
    crawler_asset_risk_tier_label,
    crawler_asset_source_surface_display_label,
    status_label,
)
from api_launcher.downloads.staging import safe_path_part
from api_launcher.paths import default_local_downloads_root, state_file
from frontends.tk.crawler_asset_seed_dialog import crawler_seed_dialog_import_label


@dataclass(frozen=True)
class CrawlerSeedDownloadImportUiMessage:
    """Display-ready Tk message for one seed download/import completion."""

    succeeded: bool
    stage: str
    dataset_uid: str
    title: str
    status_message: str
    body: str


@dataclass(frozen=True)
class CrawlerAssetRecommendedSeedClosureUiMessage:
    """Display-ready Tk message for a recommended-seed closure run."""

    succeeded: bool
    closure_stage: str
    recommended_seed_uid: str
    title: str
    status_message: str
    body: str


@dataclass(frozen=True)
class CrawlerSeedDownloadImportTargetPaths:
    """Filesystem targets for one Tk seed download/import worker."""

    downloads_root: Path
    import_sqlite_path: Path
    plan_path: Path


@dataclass(frozen=True)
class CrawlerAssetPlanOutcomeEventPayload:
    """Display/event payload prepared for Tk plan-outcome logging."""

    asset_id: str
    plan_passport: dict[str, object]
    context: dict[str, object]


@dataclass(frozen=True)
class CrawlerAssetListingOutcomeEventPayload:
    """Display/event payload prepared for Tk listing-outcome logging."""

    asset_id: str
    context: dict[str, object]
    preview: dict[str, object]


def _ui_next_action_text(action: object, *label_candidates: object, fallback: str) -> str:
    """Choose a user-facing next-action label and hide unknown backend ids."""

    raw = str(action or "").strip()
    for candidate in label_candidates:
        label = str(candidate or "").strip()
        if label and label != raw:
            return label
    return next_action_display_label_or_fallback(raw, fallback=fallback)


def crawler_seed_download_import_target_paths(
    asset_id: str,
    dataset_uid: str,
) -> CrawlerSeedDownloadImportTargetPaths:
    """Return stable Tk filesystem targets for one seed download/import job."""

    safe_asset = safe_path_part(asset_id)[:96]
    safe_seed = safe_path_part(dataset_uid)[:96]
    downloads_root = default_local_downloads_root() / "crawler_assets" / safe_asset / safe_seed
    return CrawlerSeedDownloadImportTargetPaths(
        downloads_root=downloads_root,
        import_sqlite_path=downloads_root / "curated_sources.db",
        plan_path=state_file(f"crawler_asset_seed_plans/{safe_asset}.{safe_seed}.resolved.json"),
    )


def crawler_asset_recommended_seed_closure_target_paths(asset_id: str) -> CrawlerSeedDownloadImportTargetPaths:
    """Return stable Tk filesystem targets for one recommended-seed closure.

    The backend closure service owns its inner artifact layout.  Tk passes a
    stable downloads root and SQLite target so Web/Tk can prove the same loop
    without inventing separate storage rules.
    """

    return crawler_seed_download_import_target_paths(asset_id, "recommended_seed_closure")


def crawler_asset_download_plan_bounds_schema(asset: CrawlerAsset) -> tuple[object, ...]:
    """Return the build-plan bounds schema advertised by a crawler asset.

    Tk workflows need this schema in several places, but the rule is a
    crawler-asset read-model concern: find the build-download-plan capability
    and expose its frontend-neutral bounds facets. Keeping it here prevents
    workflow handlers from repeating capability scans.
    """

    plan_capability = next((item for item in asset.capabilities if item.capability_id == BUILD_DOWNLOAD_PLAN), None)
    if plan_capability is None:
        return ()
    return tuple(plan_capability.bounds_schema or ())


def crawler_asset_bound_payload_from_cache(
    payloads: object,
    asset_id: str,
) -> CrawlerAssetBoundPayload | None:
    """Rehydrate a cached crawler-asset bounds payload for Tk workers.

    Bounds dialogs store a serializable dict so the same value can be written to
    event logs or future frontend surfaces.  Workers need the dataclass again
    before handing the payload to backend services; this helper keeps that
    conversion out of workflow event handlers.
    """

    payload = payloads.get(asset_id) if isinstance(payloads, dict) else None
    if isinstance(payload, CrawlerAssetBoundPayload):
        return payload
    if not isinstance(payload, dict):
        return None
    facet_values = payload.get("facet_values") if isinstance(payload.get("facet_values"), dict) else {}
    field_values = payload.get("field_values") if isinstance(payload.get("field_values"), dict) else {}
    maps_to_values = payload.get("maps_to_values") if isinstance(payload.get("maps_to_values"), dict) else {}
    warning_codes = payload.get("warning_codes") if isinstance(payload.get("warning_codes"), list) else ()
    return CrawlerAssetBoundPayload(
        asset_id=str(payload.get("asset_id") or asset_id),
        facet_values=dict(facet_values),
        field_values=dict(field_values),
        maps_to_values=dict(maps_to_values),
        warning_codes=tuple(str(code) for code in warning_codes),
    )


def write_crawler_asset_download_plan_artifacts(
    asset_id: str,
    original_plan: object,
    resolved_plan: object,
) -> dict[str, str]:
    """Persist the original/resolved plan pair for the Tk download-plan handoff."""

    if original_plan is None or resolved_plan is None:
        return {}
    slug = safe_path_part(asset_id)
    original_path = state_file(f"crawler_asset_plans/{slug}.original.json")
    resolved_path = state_file(f"crawler_asset_plans/{slug}.resolved.json")
    original_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_text(json.dumps(original_plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    resolved_path.write_text(json.dumps(resolved_plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"original": str(original_path), "resolved": str(resolved_path)}


def crawler_asset_download_plan_built_event_context(
    asset_id: str,
    result: object,
    written_paths: object,
) -> dict[str, object]:
    """Return the compact event context for a written crawler download plan."""

    paths = written_paths if isinstance(written_paths, dict) else {}
    return {
        "asset_id": asset_id,
        "direct_download_count": int(getattr(result, "direct_download_count", 0) or 0),
        "review_required_count": int(getattr(result, "review_required_count", 0) or 0),
        "resolved_plan": str(paths.get("resolved") or ""),
    }


def crawler_asset_download_plan_summary_text(
    result: object,
    added_count: int,
    resolved_path: str,
    tr: Callable[[str, str], str],
) -> str:
    """Convert a backend plan outcome into the Tk download-plan message.

    The backend display payload owns bucket labels and next-action text. Tk
    only adds desktop-specific wording and optional resolved-plan path context.
    """

    bucket = str(getattr(result, "outcome_bucket", "") or "")
    direct = int(getattr(result, "direct_download_count", 0) or 0)
    review = int(getattr(result, "review_required_count", 0) or 0)
    blocked = bool(getattr(result, "blocked", False))
    blocked_reason = str(getattr(result, "blocked_reason", "") or "")
    next_action = str(getattr(result, "user_next_action", "") or getattr(result, "next_action", "") or "-")
    outcome_payload = crawler_asset_plan_outcome_payload(result, added_count=added_count)
    next_action_label = _ui_next_action_text(
        next_action,
        outcome_payload.get("next_action_label"),
        fallback="檢查下載計畫結果",
    )

    if blocked or bucket == "blocked":
        summary = str(outcome_payload.get("summary") or "").strip() or "被阻擋：狀態不符合執行條件。"
        reason_label = blocked_reason_display_label_or_fallback(blocked_reason, fallback="狀態不符合執行條件")
        zh = f"這個爬蟲資產暫時不能建立下載計畫：{reason_label}。\n{summary}\n下一步：{next_action_label}"
        en = f"This crawler asset cannot build a download plan: {reason_label}.\n{summary}\nNext: {next_action_label}"
        return tr(zh, en)
    if bucket == "partial_review_required":
        zh = (
            f"已加入下載器 {added_count} 筆，可先展示或開始下載；另有 {review} 筆需要 Adapter 待辦。\n"
            "下一步：到下載器確認隊列，剩餘項目再進 Adapter review 或調整界域。"
        )
        en = (
            f"Added {added_count} item(s) to Downloader; {review} item(s) still need Adapter review.\n"
            "Next: confirm the queue in Downloader, then review adapters or adjust bounds."
        )
    elif bucket == "ready_to_download":
        zh = (
            f"已建立可下載計畫：直接下載 {direct} 筆，已加入下載器 {added_count} 筆。\n"
            "下一步：到下載器使用開始 / 暫停控制隊列。"
        )
        en = (
            f"Download plan is ready: direct {direct}, added {added_count} item(s) to Downloader.\n"
            "Next: use start / pause in Downloader."
        )
    elif bucket == "review_required":
        zh = (
            f"已建立計畫，但目前沒有可直接下載項目；{review} 筆需要 Adapter 待辦。\n"
            "下一步：開 Adapter review，或回到界域設定調整條件。"
        )
        en = (
            f"Plan built, but no direct downloads are ready; {review} item(s) require Adapter review.\n"
            "Next: open Adapter review or adjust bounds."
        )
    elif bucket == "zero_candidates":
        zh = "沒有找到符合界域的候選資料。\n下一步：放寬時間 / 空間 / 筆數條件，或先重新擷取清單。"
        en = "No candidates matched the selected bounds.\nNext: loosen time / spatial / limit bounds, or refresh the source listing."
    else:
        zh = "已建立下載計畫，但沒有可執行的下載項目。\n下一步：檢查 resolved plan，或調整界域後重試。"
        en = "Plan built, but no executable download item was produced.\nNext: inspect the resolved plan, or adjust bounds and retry."

    content_review_label = str(outcome_payload.get("content_review_label") or "").strip()
    if content_review_label:
        zh = f"{zh}\n內容格式待辦：{content_review_label}"
        en = f"{en}\nContent review: {content_review_label}"

    if resolved_path:
        zh = f"{zh}\n\nResolved plan：{resolved_path}"
        en = f"{en}\n\nResolved plan: {resolved_path}"
    return tr(zh, en)


def crawler_asset_listing_blocked_status_text(result: object, tr: Callable[[str, str], str]) -> str:
    """Render blocked listing status without leaking raw backend next_action ids."""

    blocked_reason = blocked_reason_display_label_or_fallback(getattr(result, "blocked_reason", ""), fallback="狀態不符合執行條件")
    next_action = str(getattr(result, "next_action", "") or "").strip()
    next_action_label = (
        next_action_display_label_or_fallback(next_action, fallback="檢查爬蟲資產狀態")
        if next_action
        else ""
    )
    zh = f"爬蟲資產暫停執行：{blocked_reason}；下一步：{next_action_label or '-'}"
    en = f"Crawler asset blocked: {blocked_reason}; next action: {next_action_label or '-'}"
    return tr(zh, en)


def crawler_asset_plan_outcome_label(result: object, added_count: int) -> str:
    """Return the compact Tk table label for a backend plan outcome."""

    payload = crawler_asset_plan_outcome_payload(result, added_count=added_count)
    short_label = str(payload.get("short_label") or "").strip()
    return short_label or str(payload.get("display_label") or "需檢查")


def cache_crawler_asset_plan_state(owner: object, result: object, added_count: int) -> dict[str, object]:
    """Update Tk crawler-asset plan caches from one backend plan result.

    The backend owns the outcome/passport payload shape; Tk keeps small lookup
    caches so rows and sidebars can redraw without reparsing the resolved plan.
    Keeping cache mutation here prevents workflow completion handlers from
    growing a second display-state mapper.
    """

    asset_id = str(getattr(result, "asset_id", "") or "")
    plan_outcomes = _ensure_dict_attr(owner, "crawler_asset_plan_outcomes")
    resolved_plans = _ensure_dict_attr(owner, "crawler_asset_resolved_plans")
    content_reviews = _ensure_dict_attr(owner, "crawler_asset_content_review_outcomes")
    plan_passports = _ensure_dict_attr(owner, "crawler_asset_plan_passports")

    outcome_payload = crawler_asset_plan_outcome_payload(result, added_count=added_count)
    plan_outcomes[asset_id] = crawler_asset_plan_outcome_label(result, added_count)
    plan_passports[asset_id] = crawler_asset_plan_passport_payload(result, plan_outcome=outcome_payload)

    content_review_label = str(outcome_payload.get("content_review_label") or "").strip()
    if content_review_label:
        content_reviews[asset_id] = content_review_label
    else:
        content_reviews.pop(asset_id, None)

    resolved_plan = getattr(result, "resolved_plan", None)
    if resolved_plan:
        resolved_plans[asset_id] = resolved_plan
    else:
        resolved_plans.pop(asset_id, None)
    return outcome_payload


def crawler_asset_plan_outcome_event_payload(
    result: object,
    *,
    added_count: int,
    written_paths: object,
) -> CrawlerAssetPlanOutcomeEventPayload:
    """Build the Tk event payload for one crawler-asset plan outcome.

    The backend display module owns status/count/passport semantics.  Tk adds
    only the UI-local resolved-plan artifact path and review queue count before
    writing the event log.
    """

    outcome_payload = crawler_asset_plan_outcome_payload(result, added_count=added_count)
    plan_passport = crawler_asset_plan_passport_payload(result, plan_outcome=outcome_payload)
    context = crawler_asset_plan_event_context(
        result,
        outcome_payload,
        added_count=added_count,
        plan_passport=plan_passport,
    )
    paths = written_paths if isinstance(written_paths, dict) else {}
    context["resolved_plan"] = str(paths.get("resolved") or "")
    context["review_queue_count"] = crawler_asset_review_count_from_plan(getattr(result, "resolved_plan", None))
    return CrawlerAssetPlanOutcomeEventPayload(
        asset_id=str(getattr(result, "asset_id", "") or ""),
        plan_passport=plan_passport,
        context=context,
    )


def crawler_asset_plan_passport_summary_text(
    plan_passport: object,
    tr: Callable[[str, str], str],
) -> str:
    """Render a compact plan passport into the Tk crawler-asset sidebar."""

    if not isinstance(plan_passport, dict) or not plan_passport:
        return ""
    candidates = _plan_passport_count(plan_passport.get("candidate_count"))
    direct = _plan_passport_count(plan_passport.get("direct_download_count"))
    review = _plan_passport_count(plan_passport.get("review_required_count"))
    adapter = _plan_passport_count(plan_passport.get("adapter_review_count"))
    content = _plan_passport_count(plan_passport.get("content_review_count"))
    credentials = _plan_passport_count(plan_passport.get("blocked_credential_count"))
    missing = _plan_passport_count(plan_passport.get("missing_provider_count"))
    has_plan = bool(plan_passport.get("has_resolved_plan"))
    is_stale = bool(plan_passport.get("stale"))
    snapshot_changed = bool(plan_passport.get("candidate_snapshot_changed"))
    stale_reason = str(plan_passport.get("stale_reason") or "profile_changed").strip()
    stale_label = str(plan_passport.get("stale_label") or "").strip()
    stale_next_action = str(plan_passport.get("stale_next_action") or "").strip()
    stale_next_action_label = str(plan_passport.get("stale_next_action_label") or "").strip()
    state_zh = "resolved plan 已建立" if has_plan else "resolved plan 尚未建立"
    state_en = "resolved plan available" if has_plan else "resolved plan unavailable"
    zh = (
        f"Plan Passport：{state_zh}；候選 {candidates}；可下載 {direct}；待 Adapter {review}；"
        f"Adapter 佇列 {adapter}；內容待辦 {content}"
    )
    en = (
        f"Plan Passport: {state_en}; candidates {candidates}; direct {direct}; review {review}; "
        f"adapter {adapter}; content {content}"
    )
    if credentials or missing:
        zh = f"{zh}；憑證阻擋 {credentials}；缺 Provider {missing}"
        en = f"{en}; credentials blocked {credentials}; missing providers {missing}"
    if is_stale:
        stale_text_zh = stale_label or _ui_next_action_text(stale_next_action, stale_next_action_label, fallback="計畫需重建")
        stale_text_en = _ui_next_action_text(stale_next_action, stale_next_action_label, fallback="rebuild the plan passport")
        zh = f"{zh}；狀態可能過期：{stale_text_zh}"
        en = f"{en}; stale {stale_text_en}"
    if snapshot_changed:
        zh = f"{zh}；候選快照已變更"
        en = f"{en}; candidate snapshot changed"
    return tr(zh, en)


def _plan_passport_count(value: object) -> int:
    """Old events may contain non-numeric counts; keep Tk summaries tolerant."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _ensure_dict_attr(owner: object, attr: str) -> dict:
    value = getattr(owner, attr, None)
    if isinstance(value, dict):
        return value
    value = {}
    setattr(owner, attr, value)
    return value


def crawler_asset_credential_guard_message(
    credential_guard: object,
    tr: Callable[[str, str], str],
) -> str:
    """Translate backend credential guard payload into a Tk-safe prompt."""

    guard = credential_guard if isinstance(credential_guard, dict) else {}
    display_profile = guard.get("display_profile") if isinstance(guard.get("display_profile"), dict) else {}
    label = str(display_profile.get("label") or guard.get("display_label") or "需要登入 / API Key").strip()
    provider_name = str(guard.get("provider_name") or guard.get("provider_id") or "").strip()
    missing = guard.get("missing_required") if isinstance(guard.get("missing_required"), list) else []
    missing_text = ", ".join(str(item) for item in missing if str(item).strip()) or "-"
    next_action = str(guard.get("next_action") or "edit_local_credentials_before_live_download").strip()
    next_action_zh = _ui_next_action_text(
        next_action,
        guard.get("next_action_label_zh_TW"),
        display_profile.get("next_action_label_zh_TW"),
        display_profile.get("next_action_label"),
        fallback="檢查登入設定或事件紀錄",
    )
    next_action_en = _ui_next_action_text(
        next_action,
        guard.get("next_action_label_en"),
        display_profile.get("next_action_label_en"),
        fallback="Check login settings or event logs",
    )
    entry_label = str(guard.get("credential_entry_label") or "").strip()
    zh_lines = [
        f"{label}。",
        f"來源：{provider_name or '-'}",
        f"缺少欄位：{missing_text}",
        "請先完成登入設定；如果需要 API Key，請到官方入口申請後再回來下載。",
        f"下一步：{next_action_zh}",
    ]
    if entry_label:
        zh_lines.append(f"可用入口：{entry_label}")
    en_lines = [
        f"{label}.",
        f"Source: {provider_name or '-'}",
        f"Missing fields: {missing_text}",
        "Finish login settings first. If an API key is required, get it from the official portal before downloading.",
        f"Next action: {next_action_en}",
    ]
    if entry_label:
        en_lines.append(f"Available entry: {entry_label}")
    return tr("\n".join(zh_lines), "\n".join(en_lines))


def crawler_seed_download_import_ui_message(
    result: object,
    tr: Callable[[str, str], str],
) -> CrawlerSeedDownloadImportUiMessage:
    """Convert backend download/import display payload into a Tk message.

    The backend helper owns outcome, stage, next-action and artifact fields.
    Tk only chooses whether the result is shown as an info or warning dialog.
    """

    display_payload = crawler_asset_download_import_display_payload(result)
    raw_payload = display_payload.get("download_result")
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    raw_download_import = display_payload.get("download_import")
    download_import = raw_download_import if isinstance(raw_download_import, dict) else {}
    stage = str(download_import.get("stage") or payload.get("stage") or getattr(getattr(result, "pipeline", None), "stage", "") or "-")
    succeeded = bool(
        download_import.get("succeeded")
        if "succeeded" in download_import
        else payload.get("succeeded")
        if "succeeded" in payload
        else getattr(result, "succeeded", False)
    )
    stage_label = str(download_import.get("stage_label") or "下載狀態待確認").strip()
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    downloads_root = str(artifacts.get("downloads_root") or "")
    curated_sqlite = str(artifacts.get("curated_sqlite") or "")
    dataset_uid = str(payload.get("dataset_uid") or "").strip()
    next_action = str(display_payload.get("next_action") or download_import.get("next_action") or payload.get("next_action") or "").strip()
    next_action_label = _ui_next_action_text(
        next_action,
        display_payload.get("next_action_label"),
        download_import.get("next_action_label"),
        payload.get("next_action_label"),
        fallback="檢查下載 / 匯入結果",
    )
    raw_callback_diagnostics = display_payload.get("callback_diagnostics")
    callback_diagnostics = raw_callback_diagnostics if isinstance(raw_callback_diagnostics, dict) else {}
    callback_count = int(callback_diagnostics.get("count") or download_import.get("callback_error_count") or 0)
    callback_label = str(callback_diagnostics.get("display_label") or "").strip()
    callback_next_action = str(callback_diagnostics.get("next_action_label") or callback_diagnostics.get("summary") or "").strip()
    body = tr(
        (
            f"Seed：{dataset_uid or '-'}\n"
            f"階段：{stage_label}\n"
            f"Downloads：{downloads_root or '-'}\n"
            f"SQLite：{curated_sqlite or '-'}\n"
            f"下一步：{next_action_label or '-'}"
        ),
        (
            f"Seed: {dataset_uid or '-'}\n"
            f"Stage: {stage_label}\n"
            f"Downloads: {downloads_root or '-'}\n"
            f"SQLite: {curated_sqlite or '-'}\n"
            f"Next: {next_action_label or '-'}"
        ),
    )
    if callback_count:
        body += "\n" + tr(
            f"\n進度回報：{callback_label or '進度回報有警告'} ({callback_count})\n建議：{callback_next_action or '檢查事件紀錄或 UI 進度回報'}",
            f"\nProgress callback: {callback_label or 'callback warning'} ({callback_count})\nNext: {callback_next_action or 'Inspect event logs or UI progress callbacks'}",
        )
    if succeeded:
        return CrawlerSeedDownloadImportUiMessage(
            succeeded=True,
            stage=stage,
            dataset_uid=dataset_uid,
            title=tr("Seed 下載 / 匯入完成", "Seed download/import completed"),
            status_message=tr(f"Seed 下載 / 匯入完成：{dataset_uid or '-'}", f"Seed download/import completed: {dataset_uid or '-'}"),
            body=body,
        )
    return CrawlerSeedDownloadImportUiMessage(
        succeeded=False,
        stage=stage,
        dataset_uid=dataset_uid,
        title=tr("Seed 下載 / 匯入未完成", "Seed download/import incomplete"),
        status_message=tr(f"Seed 下載 / 匯入未完成：{stage_label}", f"Seed download/import did not complete: {stage_label}"),
        body=body,
    )


def crawler_asset_recommended_seed_closure_ui_message(
    result: object,
    tr: Callable[[str, str], str],
) -> CrawlerAssetRecommendedSeedClosureUiMessage:
    """Convert backend recommended-seed closure result into a Tk message."""

    payload = result.to_dict() if hasattr(result, "to_dict") else {}
    payload = payload if isinstance(payload, dict) else {}
    closure_stage = str(payload.get("closure_stage") or getattr(result, "closure_stage", "") or "-")
    closure_stage_label = str(payload.get("closure_stage_label") or "閉環狀態待確認").strip()
    recommended_seed_uid = str(payload.get("recommended_seed_uid") or getattr(result, "recommended_seed_uid", "") or "").strip()
    next_action = str(payload.get("next_action") or getattr(result, "next_action", "") or "").strip()
    next_action_label = _ui_next_action_text(next_action, payload.get("next_action_label"), fallback="檢查推薦 seed 閉環結果")
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    download_result = getattr(result, "download_import_result", None)
    succeeded = bool(getattr(result, "succeeded", False))
    if download_result is not None:
        seed_message = crawler_seed_download_import_ui_message(download_result, tr)
        body = tr(
            (
                f"推薦 Seed：{recommended_seed_uid or '-'}\n"
                f"閉環階段：{closure_stage_label}\n"
                f"{seed_message.body}"
            ),
            (
                f"Recommended seed: {recommended_seed_uid or '-'}\n"
                f"Closure stage: {closure_stage_label}\n"
                f"{seed_message.body}"
            ),
        )
    else:
        body = tr(
            (
                f"推薦 Seed：{recommended_seed_uid or '-'}\n"
                f"閉環階段：{closure_stage_label}\n"
                f"Downloads：{artifacts.get('downloads_root') or '-'}\n"
                f"SQLite：{artifacts.get('curated_sqlite') or '-'}\n"
                f"下一步：{next_action_label}"
            ),
            (
                f"Recommended seed: {recommended_seed_uid or '-'}\n"
                f"Closure stage: {closure_stage_label}\n"
                f"Downloads: {artifacts.get('downloads_root') or '-'}\n"
                f"SQLite: {artifacts.get('curated_sqlite') or '-'}\n"
                f"Next: {next_action_label}"
            ),
        )
    if succeeded:
        return CrawlerAssetRecommendedSeedClosureUiMessage(
            succeeded=True,
            closure_stage=closure_stage,
            recommended_seed_uid=recommended_seed_uid,
            title=tr("推薦 Seed 閉環完成", "Recommended seed loop completed"),
            status_message=tr(
                f"推薦 Seed 閉環完成：{recommended_seed_uid or '-'}",
                f"Recommended seed loop completed: {recommended_seed_uid or '-'}",
            ),
            body=body,
        )
    return CrawlerAssetRecommendedSeedClosureUiMessage(
        succeeded=False,
        closure_stage=closure_stage,
        recommended_seed_uid=recommended_seed_uid,
        title=tr("推薦 Seed 閉環未完成", "Recommended seed loop incomplete"),
        status_message=tr(
            f"推薦 Seed 閉環未完成：{closure_stage}",
            f"Recommended seed loop did not complete: {closure_stage}",
        ),
        body=body,
    )


def crawler_asset_recommended_seed_closure_event_context(result: object) -> dict[str, object]:
    """Return a compact structured event context for one closure run."""

    payload = result.to_dict() if hasattr(result, "to_dict") else {}
    payload = payload if isinstance(payload, dict) else {}
    context: dict[str, object] = {
        "asset_id": payload.get("asset_id") or getattr(result, "asset_id", ""),
        "provider_id": payload.get("provider_id") or getattr(result, "provider_id", ""),
        "closure_stage": payload.get("closure_stage") or getattr(result, "closure_stage", ""),
        "succeeded": bool(payload.get("succeeded") if "succeeded" in payload else getattr(result, "succeeded", False)),
        "recommended_seed_uid": payload.get("recommended_seed_uid") or getattr(result, "recommended_seed_uid", ""),
        "next_action": payload.get("next_action") or getattr(result, "next_action", ""),
        "artifacts": payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {},
    }
    seed_page = payload.get("seed_page") if isinstance(payload.get("seed_page"), dict) else {}
    if seed_page:
        context["seed_page_summary"] = {
            "total": seed_page.get("total"),
            "page": seed_page.get("page"),
            "page_size": seed_page.get("page_size"),
            "recommended_seed_uid": seed_page.get("recommended_seed_uid"),
        }
    download_result = getattr(result, "download_import_result", None)
    if download_result is not None:
        context["download_import"] = crawler_seed_download_import_event_context(
            str(context["asset_id"]),
            str(context["recommended_seed_uid"]),
            download_result,
        )
    return context


def crawler_asset_review_count_from_plan(payload: object) -> int:
    """Count adapter-review items in a resolved plan for compact Tk labels."""

    if not isinstance(payload, dict):
        return 0
    return len(adapter_review_items(payload))


def crawler_asset_seed_page_status_text(
    payload: object,
    tr: Callable[[str, str], str],
) -> str:
    """Render the shared seed-page payload into a Tk status-bar message."""

    if not isinstance(payload, dict):
        return tr("尚未讀取 seed 清單。", "No seed page loaded.")
    summary = payload.get("page_summary") if isinstance(payload.get("page_summary"), dict) else {}
    total = int(payload.get("total") or 0)
    shown_start = int(summary.get("shown_start") or 0)
    shown_end = int(summary.get("shown_end") or 0)
    remaining = int(summary.get("remaining") or 0)
    if total <= 0:
        return tr("本機 catalog 目前沒有這個入口的 seed；請先執行清單擷取。", "No seeds for this source in the local catalog yet; run listing first.")
    if remaining:
        return tr(
            f"Seed 清單：顯示第 {shown_start}-{shown_end} 筆，共 {total} 筆；還有 {remaining} 筆可展開。",
            f"Seed page: showing {shown_start}-{shown_end} of {total}; {remaining} remaining.",
        )
    return tr(
        f"Seed 清單：顯示第 {shown_start}-{shown_end} 筆，共 {total} 筆；已到最後一頁。",
        f"Seed page: showing {shown_start}-{shown_end} of {total}; final page.",
    )


def crawler_asset_seed_page_preview_text(
    payload: object,
    tr: Callable[[str, str], str],
    *,
    preview_limit: int = 8,
    listing_outcome: object | None = None,
) -> str:
    """Render a seed-page payload into the Tk sidebar preview.

    The paging window and completeness semantics stay in the backend seed
    registry.  Tk only projects that payload into a compact text preview.
    """

    listing_note = crawler_asset_seed_enumeration_note_text(listing_outcome, tr)
    if not isinstance(payload, dict):
        base = tr("尚未讀取 seed。先執行清單擷取，再查看本機 seed 視窗。", "No seed page loaded yet. Run listing first, then inspect local seeds.")
        return f"{listing_note}\n\n{base}" if listing_note else base
    seeds = payload.get("seeds") if isinstance(payload.get("seeds"), list) else []
    status = crawler_asset_seed_page_status_text(payload, tr)
    if not seeds:
        return f"{status}\n\n{listing_note}" if listing_note else status
    lines: list[str] = [status, ""]
    if listing_note:
        lines.extend([listing_note, ""])
    for index, row in enumerate(seeds[: max(1, preview_limit)], start=1):
        if not isinstance(row, dict):
            continue
        favorite = "★ " if row.get("favorite") else ""
        title = str(row.get("title") or row.get("dataset_id") or row.get("dataset_uid") or "-").strip()
        native_format = str(row.get("native_format") or row.get("data_type") or "").strip()
        version = str(row.get("version") or "").strip()
        import_label = crawler_seed_dialog_import_label(row)
        suffix_parts = [part for part in (native_format, version, import_label) if part]
        suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
        lines.append(f"{index:02d}. {favorite}{title}{suffix}")
    remaining_on_page = max(0, len(seeds) - preview_limit)
    if remaining_on_page:
        lines.append(tr(f"...本頁另有 {remaining_on_page} 筆", f"...{remaining_on_page} more on this page"))
    if payload.get("has_more"):
        lines.append(tr("按「顯示更多 Seed」展開下一批。", "Use Show more seeds for the next page."))
    return "\n".join(lines)


def crawler_asset_credential_badge_label(credential_status: object) -> str:
    """Return the short credential label used in the crawler asset table."""

    status = credential_status if isinstance(credential_status, dict) else {}
    badge = str(status.get("display_badge_label") or "").strip()
    if badge:
        return badge
    label = str(status.get("display_label") or "").strip()
    configured = int(status.get("configured_count") or 0)
    total = int(status.get("field_count") or 0)
    if label and total:
        return f"{label} {configured}/{total}"
    return label or "免登入"


def crawler_asset_credential_summary_text(
    credential_status: object,
    tr: Callable[[str, str], str],
) -> str:
    """Render credential status from the backend UI-safe payload.

    Tk may describe status and next action, but it must not inspect raw secrets
    or duplicate credential-blocking policy.  Those rules stay in
    ``api_launcher.local_credentials``.
    """

    status = credential_status if isinstance(credential_status, dict) else {}
    display_profile = status.get("display_profile") if isinstance(status.get("display_profile"), dict) else {}
    summary_zh = str(status.get("display_summary_zh_TW") or "").strip()
    summary_en = str(status.get("display_summary_en") or "").strip()
    if summary_zh or summary_en:
        return tr(summary_zh or summary_en, summary_en or summary_zh)
    label = str(status.get("display_label") or "免登入").strip()
    configured = int(status.get("configured_count") or 0)
    total = int(status.get("field_count") or 0)
    next_action = str(status.get("next_action") or "").strip()
    next_action_zh = _ui_next_action_text(
        next_action,
        status.get("next_action_label_zh_TW"),
        display_profile.get("next_action_label_zh_TW"),
        display_profile.get("next_action_label"),
        fallback="檢查登入設定",
    )
    next_action_en = _ui_next_action_text(
        next_action,
        status.get("next_action_label_en"),
        display_profile.get("next_action_label_en"),
        fallback="Check login settings",
    )
    missing = status.get("missing_required") if isinstance(status.get("missing_required"), list) else []
    missing_text = ", ".join(str(item) for item in missing if str(item).strip())
    if total:
        zh = f"登入：{label}（{configured}/{total}）"
        en = f"Login: {label} ({configured}/{total})"
    else:
        zh = f"登入：{label}"
        en = f"Login: {label}"
    if missing_text:
        zh = f"{zh}；缺少 {missing_text}"
        en = f"{en}; missing {missing_text}"
    if next_action_zh or next_action_en:
        zh = f"{zh}；下一步：{next_action_zh}"
        en = f"{en}; next: {next_action_en}"
    return tr(zh, en)


def crawler_asset_credential_event_context(asset: CrawlerAsset, credential_status: object) -> dict[str, object]:
    """Return a sanitized event payload for credential changes.

    This intentionally excludes raw field values.  Event logs should only show
    status, counts, and field names so local secrets never leak into JSONL.
    """

    status = credential_status if isinstance(credential_status, dict) else {}
    fields = status.get("fields") if isinstance(status.get("fields"), list) else []
    field_names = [
        str(field.get("env_var") or "")
        for field in fields
        if isinstance(field, dict) and str(field.get("env_var") or "").strip()
    ]
    return {
        "asset_id": asset.asset_id,
        "provider_id": asset.provider_id,
        "status": str(status.get("status") or ""),
        "display_label": str(status.get("display_label") or ""),
        "configured_count": int(status.get("configured_count") or 0),
        "field_count": int(status.get("field_count") or 0),
        "missing_required": list(status.get("missing_required") or []),
        "field_names": field_names,
        "remember_local": bool(status.get("remember_local")),
        "next_action": str(status.get("next_action") or ""),
    }


def crawler_asset_row_values(
    asset: CrawlerAsset,
    *,
    credential_status: object,
    last_plan_outcome: object = "",
    content_review: object = "",
) -> tuple[object, ...]:
    """Return the stable row tuple for the crawler asset table."""

    plan_outcome_text = str(
        last_plan_outcome
        or next_action_display_label_or_fallback(asset.next_action, fallback="檢查爬蟲資產設定")
    )
    content_review_text = str(content_review or "").strip()
    if content_review_text:
        plan_outcome_text = f"{plan_outcome_text} / {content_review_text}"
    seed_scope_label = crawler_asset_seed_scope_label(asset)
    return (
        asset.display_name,
        crawler_asset_state_label(asset),
        crawler_asset_credential_badge_label(credential_status),
        asset.provider_id,
        crawler_asset_source_type_label(asset),
        status_label(asset.capability_status("fetch_metadata")),
        status_label(asset.capability_status("list_datasets")),
        status_label(asset.capability_status(BUILD_DOWNLOAD_PLAN)),
        asset.seed_summary,
        f"{asset.trust_score}%",
        seed_scope_label,
        plan_outcome_text,
    )


def crawler_asset_seed_scope_label(asset: CrawlerAsset) -> str:
    """Return backend display wording for the seed enumeration surface."""

    profile = getattr(asset, "capability_profile", None)
    return str(
        getattr(profile, "seed_scope_label", "")
        or getattr(profile, "seed_scope", "")
        or getattr(asset, "current_seed_scope", "")
        or "unknown"
    )


def crawler_asset_source_type_label(asset: CrawlerAsset) -> str:
    """Return backend display wording for the crawler source type."""

    return str(getattr(asset, "source_type_label", "") or "來源範式待確認")


def crawler_asset_source_surface_label(asset: CrawlerAsset) -> str:
    """Return backend display wording for the crawler entry surface."""

    return str(
        getattr(asset, "source_surface_label", "")
        or crawler_asset_source_surface_display_label(str(getattr(asset, "source_surface", "")))
    )


def crawler_asset_access_requirement_label(asset: CrawlerAsset) -> str:
    """Return backend display wording for the crawler access boundary."""

    return str(
        getattr(asset, "access_requirement_label", "")
        or crawler_asset_access_requirement_display_label(str(getattr(asset, "access_requirement", "")))
    )


def crawler_asset_detail_text(
    asset: CrawlerAsset,
    *,
    last_plan_outcome: object,
    content_review: object,
    resolved_plan: object,
    plan_passport: object,
    credential_status: object,
    tr: Callable[[str, str], str],
) -> str:
    """Return the right-side passport text for one selected crawler asset."""

    capability_lines = "\n".join(
        f"- {item.label}：{status_label(item.status)}；{item.detail}" for item in asset.capabilities
    )
    last_plan_outcome_text = str(last_plan_outcome or "").strip()
    content_review_text = str(content_review or "").strip()
    last_plan_line_zh = f"\n上次送進下載器：{last_plan_outcome_text}\n" if last_plan_outcome_text else ""
    last_plan_line_en = f"\nLast send-to-downloader result: {last_plan_outcome_text}\n" if last_plan_outcome_text else ""
    content_review_line_zh = f"內容格式待辦：{content_review_text}\n" if content_review_text else ""
    content_review_line_en = f"Content review: {content_review_text}\n" if content_review_text else ""
    review_count = crawler_asset_review_count_from_plan(resolved_plan)
    review_line_zh = f"本次 Adapter 待辦：{review_count}\n" if review_count else ""
    review_line_en = f"Current adapter queue: {review_count}\n" if review_count else ""
    plan_passport_summary = crawler_asset_plan_passport_summary_text(plan_passport, tr)
    plan_passport_line = f"{plan_passport_summary}\n" if plan_passport_summary else ""
    credential_line = crawler_asset_credential_summary_text(credential_status, tr)
    credential_line = f"{credential_line}\n" if credential_line else ""
    bounds_schema = crawler_asset_download_plan_bounds_schema(asset)
    bounds_summary_zh = "、".join(f"{facet.label_zh_TW}({facet.group})" for facet in bounds_schema)
    bounds_summary_en = ", ".join(f"{facet.label_en}({facet.group})" for facet in bounds_schema)
    seed_scope_label = crawler_asset_seed_scope_label(asset)
    source_type_label = crawler_asset_source_type_label(asset)
    source_surface_label = crawler_asset_source_surface_label(asset)
    access_requirement_label = crawler_asset_access_requirement_label(asset)
    maturity_label = crawler_asset_maturity_label(asset.maturity)
    risk_label = crawler_asset_risk_tier_label(asset.risk_tier)
    return tr(
        (
            f"{asset.display_name}\n\n"
            f"入口：{source_surface_label} / {source_type_label}\n"
            f"狀態：{crawler_asset_state_label(asset)}\n"
            f"存取邊界：{access_requirement_label}\n"
            f"成熟度：{maturity_label}；風險：{risk_label}；信任：{asset.trust_score}%\n"
            f"Seed：{asset.seed_summary} / {seed_scope_label}\n\n"
            f"{credential_line}"
            f"{last_plan_line_zh}"
            f"{content_review_line_zh}"
            f"{review_line_zh}"
            f"{plan_passport_line}"
            f"{capability_lines}\n\n"
            f"界域 schema：{bounds_summary_zh or '無'}\n\n"
            "下載指定資料庫會套用界域裝飾器：版本、時間、bbox、欄位與筆數上限。"
        ),
        (
            f"{asset.display_name}\n\n"
            f"Surface: {source_surface_label} / {source_type_label}\n"
            f"State: {crawler_asset_state_label(asset)}\n"
            f"Access: {access_requirement_label}\n"
            f"Maturity: {maturity_label}; risk: {risk_label}; trust: {asset.trust_score}%\n"
            f"Seed: {asset.seed_summary} / {seed_scope_label}\n\n"
            f"{credential_line}"
            f"{last_plan_line_en}"
            f"{content_review_line_en}"
            f"{review_line_en}"
            f"{plan_passport_line}"
            f"{capability_lines}\n\n"
            f"Bounds schema: {bounds_summary_en or 'none'}\n\n"
            "Selected downloads are decorated by bounds: version, time, bbox, columns, and limits."
        ),
    )


def crawler_asset_listing_event_preview_payload(context: object) -> dict[str, object]:
    """Keep only listing fields that Tk needs to explain seed enumeration state."""

    if not isinstance(context, dict):
        return {}
    seed_enumeration = context.get("seed_enumeration") if isinstance(context.get("seed_enumeration"), dict) else {}
    remote_pagination = context.get("remote_pagination") if isinstance(context.get("remote_pagination"), dict) else {}
    return {
        "asset_id": str(context.get("asset_id") or ""),
        "candidate_count": int(context.get("candidate_count") or 0),
        "upserted_count": int(context.get("upserted_count") or 0),
        "warning_count": int(context.get("warning_count") or 0),
        "error_count": int(context.get("error_count") or 0),
        "max_results": int(context.get("max_results") or 0),
        "complete_seed": bool(context.get("complete_seed")),
        "next_action": str(context.get("next_action") or ""),
        "seed_enumeration": dict(seed_enumeration),
        "remote_pagination": dict(remote_pagination),
    }


def crawler_asset_listing_outcome_event_payload(result: object) -> CrawlerAssetListingOutcomeEventPayload:
    """Build compact event and sidebar-preview payloads for one listing result."""

    context = crawler_asset_listing_event_context(result)
    return CrawlerAssetListingOutcomeEventPayload(
        asset_id=str(context.get("asset_id") or "").strip(),
        context=context,
        preview=crawler_asset_listing_event_preview_payload(context),
    )


def crawler_seed_schema_probe_event_context(
    asset_id: str,
    dataset_uid: str,
    probe: object,
    spec: object,
) -> dict[str, object]:
    """Return the compact Tk event payload for one seed schema probe."""

    probe_payload = probe.to_dict() if hasattr(probe, "to_dict") else {}
    return {
        "asset_id": asset_id,
        "dataset_uid": dataset_uid,
        "probe": probe_payload if isinstance(probe_payload, dict) else {},
        "schema_probe_required_count": int(getattr(spec, "schema_probe_required_count", 0) or 0),
        "warning_codes": list(getattr(spec, "warning_codes", ()) or ()),
    }


def crawler_seed_download_import_event_context(
    asset_id: str,
    dataset_uid: str,
    result: object,
) -> dict[str, object]:
    """Return the compact Tk event payload for one seed download/import run."""

    pipeline = getattr(result, "pipeline", None)
    pipeline_payload = pipeline.to_dict() if hasattr(pipeline, "to_dict") else {}
    result_payload = result.to_dict() if hasattr(result, "to_dict") else {}
    artifacts = result_payload.get("artifacts") if isinstance(result_payload, dict) else {}
    return {
        "asset_id": asset_id,
        "dataset_uid": dataset_uid,
        "stage": str(getattr(pipeline, "stage", "") or ""),
        "succeeded": bool(getattr(result, "succeeded", False)),
        "download_import": pipeline_payload if isinstance(pipeline_payload, dict) else {},
        "artifacts": artifacts if isinstance(artifacts, dict) else {},
    }


def crawler_asset_seed_enumeration_note_text(
    listing_outcome: object,
    tr: Callable[[str, str], str],
) -> str:
    """Render backend seed-enumeration confidence without exposing raw pagination tokens."""

    if not isinstance(listing_outcome, dict):
        return ""
    enumeration = listing_outcome.get("seed_enumeration") if isinstance(listing_outcome.get("seed_enumeration"), dict) else {}
    remote = enumeration.get("remote_pagination") if isinstance(enumeration.get("remote_pagination"), dict) else {}
    if not remote:
        remote = listing_outcome.get("remote_pagination") if isinstance(listing_outcome.get("remote_pagination"), dict) else {}
    label = str(enumeration.get("label") or "").strip()
    help_text = str(enumeration.get("help") or "").strip()
    status = str(remote.get("status") or "").strip()
    exhausted = remote.get("exhausted")
    token_present = bool(remote.get("next_page_token_present"))
    display_help_zh = str(remote.get("display_help_zh_TW") or "").strip()
    display_help_en = str(remote.get("display_help_en") or "").strip()
    if display_help_zh:
        remote_text = tr(display_help_zh, display_help_en or display_help_zh)
    elif status == "has_more":
        remote_text = tr(
            "遠端狀態：crawler 回報還有下一頁線索；token 已由後端遮蔽。",
            "Remote status: crawler reported another page; token is hidden by the backend.",
        )
    elif status == "exhausted" or exhausted is True:
        remote_text = tr(
            "遠端狀態：crawler 回報已列完。",
            "Remote status: crawler reported that the remote listing is exhausted.",
        )
    elif status and status != "not_reported":
        remote_text = tr(
            "遠端狀態：待確認。請檢查 crawler audit 或來源分頁合約。",
            "Remote status: needs review. Check the crawler audit or source pagination contract.",
        )
    elif token_present:
        remote_text = tr(
            "遠端狀態：偵測到下一頁線索；token 已由後端遮蔽。",
            "Remote status: detected another page; token is hidden by the backend.",
        )
    else:
        remote_text = tr(
            "遠端完整度：這個 handler 尚未回報，只能依本機 catalog 視窗判斷。",
            "Remote completeness: this handler has not reported it; rely on the local catalog window.",
        )
    lines = [part for part in (label, help_text, remote_text) if part]
    return "\n".join(lines)


def crawler_asset_state_label(asset: CrawlerAsset) -> str:
    """Return the compact state label for the crawler asset table and passport."""

    if getattr(asset, "health", None) is not None:
        code = asset.health.status_code
        labels = {
            "archived": "封存",
            "disabled": "停用",
            "missing_handler": "待實作",
            "needs_bounds": "需界域",
            "review_needed": "待審",
            "healthy": "可用",
            "unknown": "未知",
        }
        return f"{asset.health.status_emoji} {labels.get(code, code)}"
    if asset.archived:
        return "📦 封存"
    if not asset.enabled:
        return "⏸ 停用"
    if asset.risk_tier == "needs_handler":
        return "⚙️ 待補"
    if asset.risk_tier == "needs_review":
        return "🟡 待審"
    return "🟢 啟用"
