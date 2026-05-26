from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256


RUN_EVENT_SUMMARY_KEYS = (
    "asset_id",
    "source_found",
    "blocked",
    "blocked_reason",
    "candidate_count",
    "upserted_count",
    "skipped_provider_count",
    "duplicate_count",
    "error_count",
    "warning_count",
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

RUN_RECORD_SUMMARY_KEYS = (
    "record_key",
    "stage",
    "status",
    "outcome_bucket",
    "asset_id",
    "source_id",
    "candidate_count",
    "direct_download_count",
    "review_required_count",
    "error_count",
    "warning_count",
    "duplicate_count",
    "candidate_snapshot_count",
    "next_action",
    "storage_lane",
    "future_sqlite_table",
)

RUN_COUNT_KEYS = (
    "candidate_count",
    "upserted_count",
    "skipped_provider_count",
    "direct_download_count",
    "review_required_count",
    "review_queue_count",
    "error_count",
    "warning_count",
    "duplicate_count",
    "candidate_snapshot_count",
)

DEFAULT_CRAWLER_RUN_EVENT_SCAN_LIMIT = 500
CRAWLER_RUN_LISTING_EVENT = "crawler_asset_listing_recorded"
CRAWLER_RUN_PLAN_EVENT = "crawler_asset_plan_outcome_recorded"


def crawler_run_record(
    *,
    stage: str,
    asset_id: str,
    status: str,
    next_action: str = "",
    outcome_bucket: str = "",
    candidate_count: int = 0,
    direct_download_count: int = 0,
    review_required_count: int = 0,
    error_count: int = 0,
    warning_count: int = 0,
    duplicate_count: int = 0,
    source_signature: str = "",
    bounds_signature: str = "",
    candidate_snapshot_signature: str = "",
    candidate_snapshot_count: int = 0,
) -> dict[str, object]:
    """Build the compact crawler-run handoff payload shared by UI and agents.

    這不是永久 DB schema；目前先作為 structured event / JSON handoff
    的共用骨架。等 run registry 表定案後，這裡的欄位可以直接映射
    到 SQLite registry。
    """

    payload: dict[str, object] = {
        "record_key": "",
        "stage": stage,
        "asset_id": asset_id,
        "status": status,
        "outcome_bucket": outcome_bucket,
        "candidate_count": int(candidate_count),
        "direct_download_count": int(direct_download_count),
        "review_required_count": int(review_required_count),
        "error_count": int(error_count),
        "warning_count": int(warning_count),
        "duplicate_count": int(duplicate_count),
        "source_signature": source_signature,
        "bounds_signature": bounds_signature,
        "candidate_snapshot_signature": candidate_snapshot_signature,
        "candidate_snapshot_count": int(candidate_snapshot_count),
        "next_action": next_action,
        "storage_lane": "structured_event_log",
        "future_sqlite_table": "crawler_run_registry",
    }
    payload["record_key"] = crawler_run_record_key(payload)
    return payload


def crawler_run_record_key(payload: Mapping[str, object]) -> str:
    stable_payload = {key: value for key, value in payload.items() if key != "record_key"}
    raw = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def crawler_run_record_from_result(result: object) -> dict[str, object]:
    """Extract the compact run record from a result object when available.

    Tk/Web/Qt should not know how every crawler result calculates status.  They
    can call this helper and keep the event context bounded; objects without a
    ``to_dict().run_record`` contract simply return an empty payload.
    """

    to_dict = getattr(result, "to_dict", None)
    if not callable(to_dict):
        return {}
    try:
        payload = to_dict()
    except Exception:
        # 事件紀錄不能因單一 result 的序列化錯誤而拖垮 Tk/Web 回報路徑。
        return {}
    if not isinstance(payload, dict):
        return {}
    run_record = payload.get("run_record")
    return dict(run_record) if isinstance(run_record, dict) else {}


def crawler_run_context_summary(context: Mapping[str, object]) -> dict[str, object]:
    """把 crawler event context 壓成 Web / handoff 可共用的白名單摘要。"""

    summary: dict[str, object] = {key: context[key] for key in RUN_EVENT_SUMMARY_KEYS if key in context}
    content_review = context.get("content_review")
    if isinstance(content_review, Mapping):
        summary["content_review"] = {
            "display_label": content_review.get("display_label", ""),
            "display_tone": content_review.get("display_tone", ""),
            "count": content_review.get("count", 0),
            "has_review": bool(content_review.get("has_review")),
        }
    run_record = context.get("run_record")
    if isinstance(run_record, Mapping):
        summary["run_record"] = compact_crawler_run_record(run_record)
    return summary


def crawler_run_event_summary(event: Mapping[str, object]) -> dict[str, object]:
    """把完整 structured event 壓成 agent handoff 用的 bounded run 摘要。"""

    if not event:
        return {}
    context = event.get("context") if isinstance(event.get("context"), Mapping) else {}
    assert isinstance(context, Mapping)
    run_record = context.get("run_record") if isinstance(context.get("run_record"), Mapping) else {}
    assert isinstance(run_record, Mapping)
    summary: dict[str, object] = {
        "event_at": str(event.get("timestamp") or ""),
        "event": str(event.get("event") or ""),
        "level": str(event.get("level") or ""),
        "asset_id": str(context.get("asset_id") or run_record.get("asset_id") or ""),
        "status": str(run_record.get("status") or context.get("status") or ""),
        "outcome_bucket": str(run_record.get("outcome_bucket") or context.get("outcome_bucket") or ""),
        "next_action": str(
            context.get("user_next_action")
            or context.get("next_action")
            or run_record.get("next_action")
            or ""
        ),
        "resolved_plan_available": "resolved_plan" in context and context.get("resolved_plan") is not None,
    }
    summary.update(crawler_run_event_counts(context, run_record))
    if run_record:
        summary["run_record"] = compact_crawler_run_record(run_record)
    content_review = context.get("content_review")
    if isinstance(content_review, Mapping):
        summary["content_review"] = {
            "display_label": content_review.get("display_label", ""),
            "display_tone": content_review.get("display_tone", ""),
            "count": content_review.get("count", 0),
            "has_review": bool(content_review.get("has_review")),
        }
    return summary


def crawler_run_summary_from_events(events: list[dict[str, object]]) -> dict[str, object]:
    """Return the latest crawler listing/plan summaries without replaying crawlers."""

    latest_listing = latest_crawler_run_event(events, CRAWLER_RUN_LISTING_EVENT)
    latest_plan_build = latest_crawler_run_event(events, CRAWLER_RUN_PLAN_EVENT)
    return {
        "latest_listing": crawler_run_event_summary(latest_listing),
        "latest_download_plan_build": crawler_run_event_summary(latest_plan_build),
    }


def latest_crawler_run_event(events: list[dict[str, object]], event_name: str) -> dict[str, object]:
    for event in reversed(events):
        if event.get("event") == event_name:
            return event
    return {}


def crawler_run_event_counts(
    context: Mapping[str, object],
    run_record: Mapping[str, object],
) -> dict[str, object]:
    counts: dict[str, object] = {}
    for key in RUN_COUNT_KEYS:
        if key in run_record:
            counts[key] = run_record[key]
        elif key in context:
            counts[key] = context[key]
    return counts


def compact_crawler_run_record(run_record: Mapping[str, object]) -> dict[str, object]:
    return {key: run_record[key] for key in RUN_RECORD_SUMMARY_KEYS if key in run_record}


__all__ = [
    "CRAWLER_RUN_LISTING_EVENT",
    "CRAWLER_RUN_PLAN_EVENT",
    "DEFAULT_CRAWLER_RUN_EVENT_SCAN_LIMIT",
    "compact_crawler_run_record",
    "crawler_run_context_summary",
    "crawler_run_event_summary",
    "crawler_run_record",
    "crawler_run_record_from_result",
    "crawler_run_record_key",
    "crawler_run_summary_from_events",
    "latest_crawler_run_event",
]
