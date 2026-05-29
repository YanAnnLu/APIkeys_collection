"""Display-safe crawler asset payload helpers.

The backend owns status interpretation.  Tk, Web Preview, and future Qt should
receive labels, tones, summaries, and next-action strings from this module
instead of translating raw outcome buckets by themselves.  This prevents UI
surfaces from drifting when crawler/download/import behavior changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundFormSpec
from api_launcher.crawler_asset_bound_display import (
    bound_field_display_help,
    bound_field_display_label,
    capability_display_label,
    crawler_asset_bound_form_payload,
)
from api_launcher.crawler_asset_capabilities import BUILD_DOWNLOAD_PLAN, CrawlerAssetCapability
from api_launcher.crawler_asset_profiles import compact_crawler_asset_plan_passport
from api_launcher.crawler_assets import CrawlerAsset
from api_launcher.crawler_asset_review_display import (
    adapter_review_content_summary_label,
    adapter_review_content_summary_payload,
    adapter_review_display_payload,
    adapter_review_outcome_label,
    adapter_review_outcome_tone,
    content_pipeline_lane_label,
    content_pipeline_lane_tone,
    content_review_bucket_label,
    content_review_bucket_tone,
    plan_entry_content_status_payload,
)
from api_launcher.crawler_next_action_display import next_action_display_label
from api_launcher.crawler_plan_outcome_display import (
    DisplayProfile,
    PLAN_OUTCOME_DISPLAY,
    plan_outcome_display_label,
    plan_outcome_display_profile,
    plan_outcome_short_label,
)
from api_launcher.crawler_run_records import crawler_run_record_from_result
from api_launcher.crawler_seed_display import (
    SEED_ENUMERATION_DISPLAY_PROFILES,
    SeedEnumerationDisplayProfile,
    seed_enumeration_display_payload,
)


@dataclass(frozen=True)
class CrawlerAssetFlowStep:
    step_id: str
    label: str
    status: str
    summary: str
    evidence: str = ""
    warning_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "label": self.label,
            "status": self.status,
            "summary": self.summary,
            "evidence": self.evidence,
            "warning_codes": list(self.warning_codes),
        }


def crawler_asset_card_capabilities(
    capabilities: Iterable[CrawlerAssetCapability],
) -> list[dict[str, object]]:
    """Return compact capability rows for asset cards and lists."""

    return [
        {
            "capability_id": capability.capability_id,
            "label": capability.label,
            "display_label": capability_display_label(capability),
            "status": capability.status,
            "next_action": capability.next_action,
        }
        for capability in capabilities
    ]


def crawler_asset_flow_steps(
    asset: CrawlerAsset,
    form_spec: CrawlerAssetBoundFormSpec,
) -> list[dict[str, object]]:
    """建立 UI 共用流程條。

    Web、Tk、Qt 都應該顯示這份後端流程狀態，而不是各自推論 crawler 是否可用。
    """

    plan_capability = next(
        (capability for capability in asset.capabilities if capability.capability_id == BUILD_DOWNLOAD_PLAN),
        None,
    )
    source_type_known = bool(asset.source_type and asset.source_type != "unknown")
    has_bounds_form = bool(form_spec.fields)
    plan_status = plan_capability.status if plan_capability is not None else "missing_handler"
    review_needed = asset.health.status_code not in {"healthy", "ready"} or "review" in plan_status
    steps = (
        CrawlerAssetFlowStep(
            step_id="seed",
            label="Seed 註冊",
            status="complete" if asset.seed_count else "warning",
            summary=asset.seed_summary or f"{asset.seed_count} seed",
            evidence=asset.endpoint_url,
        ),
        CrawlerAssetFlowStep(
            step_id="source_pattern",
            label="來源範式",
            status="complete" if source_type_known else "review",
            summary=asset.source_type or "unknown",
            evidence=asset.source_surface,
        ),
        CrawlerAssetFlowStep(
            step_id="bounds",
            label="界域表單",
            status="complete" if has_bounds_form else "neutral",
            summary=f"{len(form_spec.fields)} 個欄位" if has_bounds_form else "不需或尚未定義界域",
            evidence=", ".join(form_spec.groups),
            warning_codes=tuple(form_spec.warning_codes),
        ),
        CrawlerAssetFlowStep(
            step_id="download_plan",
            label="下載計畫",
            status="complete" if plan_status in {"selectable", "ready", "bounded"} else "review",
            summary=plan_status,
            evidence=plan_capability.next_action if plan_capability is not None else "implement_source_handler",
        ),
        CrawlerAssetFlowStep(
            step_id="review_gate",
            label="審核閘門",
            status="review" if review_needed else "complete",
            summary=asset.health.status_code,
            evidence=asset.next_action,
        ),
    )
    return [step.to_dict() for step in steps]


def crawler_asset_plan_outcome_payload(result: object, *, added_count: int = 0) -> dict[str, object]:
    """Return a frontend-neutral display payload for one crawler-asset plan result.

    Tk/Web/Qt should render this payload instead of rebuilding outcome labels from
    ``outcome_bucket``.  The bucket remains the stable machine-readable contract;
    display strings here are only the shared presentation layer.
    """

    # Keep the bucket as the stable machine-readable value, then attach display
    # metadata next to it.  Frontends should prefer display_profile for text and
    # tone, not branch directly on the bucket unless they are doing diagnostics.
    bucket = str(getattr(result, "outcome_bucket", "") or "empty_plan")
    direct = _safe_int(getattr(result, "direct_download_count", 0))
    review = _safe_int(getattr(result, "review_required_count", 0))
    blocked_reason = str(getattr(result, "blocked_reason", "") or "")
    next_action = str(getattr(result, "user_next_action", "") or getattr(result, "next_action", "") or "")
    display = plan_outcome_display_profile(
        bucket,
        direct=direct,
        review=review,
        added_count=added_count,
        blocked_reason=blocked_reason,
        next_action=next_action,
    )
    resolved_plan = getattr(result, "resolved_plan", None)
    adapter_review = adapter_review_display_payload(resolved_plan) if isinstance(resolved_plan, dict) else {}
    content_review = adapter_review_content_summary_payload(adapter_review)
    return {
        "outcome_bucket": bucket,
        "display_profile": display.to_dict(),
        "display_label": display.display_label,
        "display_tone": display.display_tone,
        "short_label": display.short_label,
        "summary": display.summary,
        "direct_download_count": direct,
        "review_required_count": review,
        "added_count": added_count,
        "blocked": bool(getattr(result, "blocked", False)) or bucket == "blocked",
        "blocked_reason": blocked_reason,
        "next_action": display.next_action,
        "next_action_label": display.next_action_label,
        "adapter_review": adapter_review,
        "content_review": content_review,
        "content_review_label": content_review["display_label"],
    }


def crawler_asset_plan_passport_payload(
    result: object,
    *,
    plan_outcome: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Summarize one resolved plan without copying the full plan into UI state.

    The passport is meant for Tk/Web/Qt status panels: it gives users and agents
    enough evidence to decide the next action while keeping the bulky resolved
    plan in the backend review/download path.
    """

    resolved_plan = getattr(result, "resolved_plan", None)
    plan_build = getattr(result, "plan_build", None)
    adapter_review = adapter_review_display_payload(resolved_plan if isinstance(resolved_plan, dict) else {})
    outcome = dict(plan_outcome) if isinstance(plan_outcome, Mapping) else crawler_asset_plan_outcome_payload(result)
    content_review_payload = outcome.get("content_review")
    content_review = (
        content_review_payload
        if isinstance(content_review_payload, dict)
        else adapter_review_content_summary_payload(adapter_review)
    )
    credential_gates = getattr(plan_build, "credential_gates", ()) if plan_build is not None else ()
    blocked_credentials = _safe_int(getattr(plan_build, "blocked_credential_count", 0)) if plan_build is not None else 0
    missing_provider_ids = getattr(plan_build, "missing_provider_ids", ()) if plan_build is not None else ()
    bounds = getattr(result, "bounds", None)
    return {
        "asset_id": str(getattr(result, "asset_id", "") or ""),
        "has_resolved_plan": isinstance(resolved_plan, dict) and bool(resolved_plan),
        "outcome_bucket": str(outcome.get("outcome_bucket") or getattr(result, "outcome_bucket", "") or ""),
        "short_label": str(outcome.get("short_label") or ""),
        "display_tone": str(outcome.get("display_tone") or "neutral"),
        "candidate_count": _safe_int(getattr(plan_build, "candidate_count", 0)) if plan_build is not None else 0,
        "candidate_snapshot_signature": str(getattr(plan_build, "candidate_snapshot_signature", "") or "")
        if plan_build is not None
        else "",
        "candidate_snapshot_count": _safe_int(getattr(plan_build, "candidate_snapshot_count", 0))
        if plan_build is not None
        else 0,
        "candidate_snapshot_changed": bool(getattr(result, "candidate_snapshot_changed", False)),
        "upserted_candidate_count": _safe_int(getattr(plan_build, "upserted_candidate_count", 0)) if plan_build is not None else 0,
        "selected_version_count": _safe_int(getattr(plan_build, "selected_version_count", 0)) if plan_build is not None else 0,
        "filtered_version_count": _safe_int(getattr(plan_build, "filtered_version_count", 0)) if plan_build is not None else 0,
        "direct_download_count": _safe_int(getattr(result, "direct_download_count", 0)),
        "review_required_count": _safe_int(getattr(result, "review_required_count", 0)),
        "adapter_review_count": _safe_int(adapter_review.get("item_count")),
        "content_review_count": _safe_int(content_review.get("count") if isinstance(content_review, dict) else 0),
        "blocked_credential_count": blocked_credentials,
        "credential_gate_count": len(tuple(credential_gates)),
        "missing_provider_count": len(tuple(missing_provider_ids)),
        "next_action": str(getattr(result, "user_next_action", "") or getattr(result, "next_action", "") or ""),
        "source_signature": str(getattr(result, "source_signature", "") or ""),
        "bounds_signature": str(getattr(result, "bounds_signature", "") or ""),
        "bounds": bounds.to_dict() if hasattr(bounds, "to_dict") else {},
    }


def credential_blocked_plan_outcome_payload(credential_guard: Mapping[str, object]) -> dict[str, object]:
    """Build the shared plan-outcome payload when credentials block live work.

    Credential gating is backend policy, not a Web route concern.  Keeping this
    payload here lets Tk/Web/Qt display the same review state whenever a source
    needs local login or API-key setup before plan building or download/import.
    """

    missing = credential_guard.get("missing_required")
    missing_required = (
        list(missing)
        if isinstance(missing, Iterable) and not isinstance(missing, (str, bytes))
        else []
    )
    suffix = f"（缺 {len(missing_required)} 欄）" if missing_required else ""
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


def credential_blocked_plan_passport_payload(
    asset_id: str,
    credential_guard: Mapping[str, object],
) -> dict[str, object]:
    """Build the compact plan passport for credential-blocked crawler assets."""

    missing = credential_guard.get("missing_required")
    missing_required = (
        list(missing)
        if isinstance(missing, Iterable) and not isinstance(missing, (str, bytes))
        else []
    )
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
        "blocked_credential_count": len(missing_required),
        "next_action": "edit_local_credentials_before_live_download",
        "next_action_label": next_action_display_label("edit_local_credentials_before_live_download"),
    }


def crawler_asset_plan_event_context(
    result: object,
    plan_outcome: Mapping[str, object],
    *,
    added_count: int = 0,
    plan_passport: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the shared event context used by Tk/Web/Qt plan-outcome badges.

    UI surfaces should log a compact event context, not a full resolved plan.
    Keeping this shape in the backend display module prevents each frontend from
    inventing its own event keys for badges, recent events, and agent handoff.
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
        "direct_download_count": _safe_int(getattr(result, "direct_download_count", 0) or 0),
        "review_required_count": _safe_int(getattr(result, "review_required_count", 0) or 0),
        "review_queue_count": _safe_int(getattr(result, "review_required_count", 0) or 0),
        "content_review_label": str(plan_outcome.get("content_review_label") or ""),
        "content_review": content_review if isinstance(content_review, dict) else {},
        "run_record": crawler_run_record_from_result(result),
        "resolved_plan": "",
        "resolved_plan_available": bool(getattr(result, "resolved_plan", None)),
        "plan_passport": compact_crawler_asset_plan_passport(plan_passport),
        "user_next_action": str(
            getattr(result, "user_next_action", "")
            or getattr(result, "next_action", "")
            or plan_outcome.get("next_action")
            or ""
        ),
    }


def crawler_asset_recent_plan_outcomes_from_events(
    events: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Extract latest compact plan outcome badges from structured events.

    Frontends may read events from different stores, but the rule for which
    event keys are allowed into a status badge belongs to the backend display
    contract.  This keeps Web/Tk/Qt from each parsing event context slightly
    differently.
    """

    outcomes: dict[str, dict[str, object]] = {}
    for event in events:
        if event.get("event") != "crawler_asset_plan_outcome_recorded":
            continue
        context = event.get("context")
        if not isinstance(context, Mapping):
            continue
        asset_id = str(context.get("asset_id") or "").strip()
        if not asset_id:
            continue
        outcomes[asset_id] = crawler_asset_plan_event_badge_payload(context)
    return outcomes


def crawler_asset_recent_plan_passports_from_events(
    events: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Extract latest compact plan passports from structured events.

    Event logs are evidence, not a resolved-plan database.  Only the compact
    passport shape may cross into UI status surfaces.
    """

    passports: dict[str, dict[str, object]] = {}
    for event in events:
        if event.get("event") != "crawler_asset_plan_outcome_recorded":
            continue
        context = event.get("context")
        if not isinstance(context, Mapping):
            continue
        asset_id = str(context.get("asset_id") or "").strip()
        if not asset_id:
            continue
        passport = compact_crawler_asset_plan_passport(context.get("plan_passport"))
        if passport:
            passports[asset_id] = passport
    return passports


def crawler_asset_download_import_display_payload(
    result: object,
    *,
    plan_outcome: Mapping[str, object] | None = None,
    plan_passport: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the shared Web/Tk/Qt payload for a download/import run.

    The download/import service already owns plan, download, and import state.
    This helper only packages that state for UI surfaces so endpoints do not
    each rebuild next-action labels, adapter review summaries, and plan badges.
    """

    download_result = result.to_dict() if hasattr(result, "to_dict") else {}
    if not isinstance(download_result, dict):
        download_result = {}
    plan_result = getattr(result, "plan_result", None)
    plan_result_payload = plan_result.to_dict() if hasattr(plan_result, "to_dict") else {}
    if not isinstance(plan_result_payload, dict):
        plan_result_payload = {}
    outcome = dict(plan_outcome) if isinstance(plan_outcome, Mapping) else crawler_asset_plan_outcome_payload(plan_result)
    passport = (
        dict(plan_passport)
        if isinstance(plan_passport, Mapping)
        else crawler_asset_plan_passport_payload(plan_result, plan_outcome=outcome)
    )
    resolved_plan = getattr(plan_result, "resolved_plan", None)
    adapter_review = adapter_review_display_payload(resolved_plan if isinstance(resolved_plan, dict) else {})
    pipeline = getattr(result, "pipeline", None)
    download_import = pipeline.to_dict() if hasattr(pipeline, "to_dict") else download_result.get("download_import", {})
    if not isinstance(download_import, dict):
        download_import = {}
    if "stage" not in download_import and "stage" in download_result:
        download_import["stage"] = download_result["stage"]
    if "succeeded" not in download_import and "succeeded" in download_result:
        download_import["succeeded"] = download_result["succeeded"]
    if "next_action" not in download_import and "next_action" in download_result:
        download_import["next_action"] = download_result["next_action"]
    next_action = str(
        getattr(pipeline, "next_action", "")
        or getattr(plan_result, "user_next_action", "")
        or download_result.get("next_action")
        or ""
    )
    next_action_label = str(
        download_result.get("next_action_label")
        or outcome.get("next_action_label")
        or next_action_display_label(next_action)
        or ""
    )
    download_import["next_action_label"] = next_action_label
    callback_errors = _download_import_callback_errors(download_import)
    callback_diagnostics = _callback_diagnostics_payload(callback_errors)
    # Callback diagnostics are about observers such as Tk/Web progress updates,
    # not the downloader itself.  Keep them next to the shared display payload
    # so UI surfaces can show a warning without reclassifying the run as failed.
    download_import["callback_error_count"] = len(callback_errors)
    download_import["callback_errors"] = list(callback_errors)
    download_import["callback_diagnostics"] = callback_diagnostics
    return {
        "download_result": download_result,
        "plan_result": plan_result_payload,
        "plan_outcome": outcome,
        "plan_passport": passport,
        "adapter_review": adapter_review,
        "download_import": download_import,
        "callback_diagnostics": callback_diagnostics,
        "next_action": next_action,
        "next_action_label": next_action_label,
    }


def crawler_asset_plan_event_badge_payload(context: Mapping[str, object]) -> dict[str, object]:
    """Rebuild a compact plan-outcome badge from a structured event context.

    Tk writes ``crawler_asset_plan_outcome_recorded`` after a crawler asset is
    sent to the downloader.  Web/Qt can read that event and render the same
    badge without replaying the plan build or parsing UI prose.
    """

    bucket = str(context.get("outcome_bucket") or "empty_plan")
    direct = _safe_int(context.get("direct_download_count"))
    review = _safe_int(context.get("review_required_count") or context.get("review_queue_count"))
    added_count = _safe_int(context.get("added_count"))
    blocked_reason = str(context.get("blocked_reason") or "")
    next_action = str(context.get("user_next_action") or "")
    display = plan_outcome_display_profile(
        bucket,
        direct=direct,
        review=review,
        added_count=added_count,
        blocked_reason=blocked_reason,
        next_action=next_action,
    )
    short_label = str(context.get("outcome_label") or "").strip() or display.short_label
    content_review = _content_review_payload_from_event_context(context)
    return {
        "outcome_bucket": bucket,
        "display_label": display.display_label,
        "display_tone": display.display_tone,
        "short_label": short_label,
        "summary": display.summary,
        "direct_download_count": direct,
        "review_required_count": review,
        "added_count": added_count,
        "blocked": bucket == "blocked",
        "blocked_reason": blocked_reason,
        "next_action": next_action,
        "next_action_label": display.next_action_label,
        "content_review": content_review,
        "content_review_label": content_review["display_label"],
    }


def _content_review_payload_from_event_context(context: Mapping[str, object]) -> dict[str, object]:
    payload = context.get("content_review")
    if isinstance(payload, dict) and payload.get("display_label"):
        return dict(payload)
    label = str(context.get("content_review_label") or "").strip()
    if not label:
        return adapter_review_content_summary_payload({})
    return {
        "display_label": label,
        "display_tone": "review",
        "count": _safe_int(context.get("review_queue_count")) or 1,
        "has_review": True,
        "buckets": [],
    }


def _download_import_callback_errors(download_import: Mapping[str, object]) -> tuple[str, ...]:
    result = download_import.get("result") if isinstance(download_import, Mapping) else {}
    raw_errors = result.get("callback_errors") if isinstance(result, Mapping) else ()
    if not isinstance(raw_errors, (list, tuple)):
        return ()
    return tuple(text for text in (str(item).strip() for item in raw_errors) if text)


def _callback_diagnostics_payload(callback_errors: tuple[str, ...]) -> dict[str, object]:
    if not callback_errors:
        return {
            "count": 0,
            "display_tone": "neutral",
            "display_label": "進度回報正常",
            "summary": "",
            "next_action": "",
            "next_action_label": "",
            "errors": [],
        }
    next_action = "inspect_event_logs_or_ui_callback"
    return {
        "count": len(callback_errors),
        "display_tone": "warning",
        "display_label": "進度回報有警告",
        "summary": "下載或匯入可能已完成，但 UI/progress callback 回報失敗。",
        "next_action": next_action,
        "next_action_label": next_action_display_label(next_action),
        "errors": list(callback_errors),
    }


def _safe_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


__all__ = [
    "adapter_review_display_payload",
    "adapter_review_content_summary_label",
    "adapter_review_outcome_label",
    "adapter_review_outcome_tone",
    "content_pipeline_lane_label",
    "content_pipeline_lane_tone",
    "content_review_bucket_label",
    "content_review_bucket_tone",
    "crawler_asset_bound_form_payload",
    "crawler_asset_card_capabilities",
    "crawler_asset_flow_steps",
    "crawler_asset_download_import_display_payload",
    "crawler_asset_plan_event_badge_payload",
    "crawler_asset_plan_event_context",
    "crawler_asset_recent_plan_outcomes_from_events",
    "crawler_asset_recent_plan_passports_from_events",
    "crawler_asset_plan_outcome_payload",
    "crawler_asset_plan_passport_payload",
    "credential_blocked_plan_outcome_payload",
    "credential_blocked_plan_passport_payload",
    "plan_entry_content_status_payload",
    "DisplayProfile",
    "SeedEnumerationDisplayProfile",
    "capability_display_label",
    "bound_field_display_label",
    "bound_field_display_help",
    "next_action_display_label",
    "plan_outcome_display_label",
    "plan_outcome_display_profile",
    "plan_outcome_short_label",
    "seed_enumeration_display_payload",
]
