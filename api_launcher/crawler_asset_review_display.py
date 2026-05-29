"""Display helpers for adapter-review and content parser status.

These functions are UI-neutral: Tk, Web Preview, and future Qt should consume
the same labels, tones, and compact summary payloads instead of each surface
translating adapter-review buckets independently.
"""

from __future__ import annotations

from api_launcher.adapter_review import adapter_review_agent_payload


ADAPTER_REVIEW_OUTCOME_DISPLAY = {
    "source_resolution_required": ("來源解析待辦", "review"),
    "downloaded_payload_transform": ("下載後轉換待辦", "warning"),
    "import_transform_required": ("匯入轉換待辦", "warning"),
    "import_adapter_required": ("匯入 Adapter 待辦", "review"),
    "adapter_review_required": ("Adapter 審核待辦", "review"),
}

CONTENT_REVIEW_BUCKET_DISPLAY = {
    "content_parser_required": ("內容 Parser 待辦", "review"),
    "downloaded_payload_transform": ("需解壓/轉換", "warning"),
    "unsupported_payload_format": ("未支援格式", "danger"),
}

CONTENT_IMPORT_STATUS_DISPLAY = {
    "supported_after_download": ("下載後可匯入", "success"),
    "requires_unpack_or_adapter": ("需解壓/轉換", "warning"),
    "manual_review_required": ("需內容 Parser review", "review"),
    "adapter_review_required": ("需 Adapter", "review"),
}

CONTENT_PIPELINE_LANE_DISPLAY = {
    "sqlite_curated_import": ("可匯入 SQLite", "success"),
    "downloaded_payload_transform": ("下載後需解壓或轉換", "warning"),
    "content_parser_review": ("內容 Parser 待辦", "warning"),
    "adapter_review": ("內容格式待審核", "danger"),
}

TONE_SEVERITY = {
    "neutral": 0,
    "success": 0,
    "review": 1,
    "warning": 2,
    "danger": 3,
}


def adapter_review_display_payload(plan_payload: dict[str, object]) -> dict[str, object]:
    """Summarize adapter-review work for UI surfaces without parsing prose."""

    review_payload = adapter_review_agent_payload(plan_payload if isinstance(plan_payload, dict) else {})
    summary = review_payload.get("summary") if isinstance(review_payload.get("summary"), dict) else {}
    by_outcome = summary.get("by_outcome") if isinstance(summary.get("by_outcome"), dict) else {}
    by_content_review_bucket = (
        summary.get("by_content_review_bucket") if isinstance(summary.get("by_content_review_bucket"), dict) else {}
    )
    by_content_parser = summary.get("by_content_parser") if isinstance(summary.get("by_content_parser"), dict) else {}
    by_content_pipeline_lane = (
        summary.get("by_content_pipeline_lane") if isinstance(summary.get("by_content_pipeline_lane"), dict) else {}
    )
    by_content_importability = (
        summary.get("by_content_importability") if isinstance(summary.get("by_content_importability"), dict) else {}
    )
    outcomes = [
        {
            "outcome_bucket": str(bucket),
            "display_label": adapter_review_outcome_label(str(bucket)),
            "display_tone": adapter_review_outcome_tone(str(bucket)),
            "count": _safe_int(count),
        }
        for bucket, count in sorted(by_outcome.items())
    ]
    content_review_buckets = [
        {
            "review_bucket": str(bucket),
            "display_label": content_review_bucket_label(str(bucket)),
            "display_tone": content_review_bucket_tone(str(bucket)),
            "count": _safe_int(count),
        }
        for bucket, count in sorted(by_content_review_bucket.items())
    ]
    content_parsers = [
        {
            "parser_id": str(parser_id),
            "count": _safe_int(count),
        }
        for parser_id, count in sorted(by_content_parser.items())
    ]
    content_pipeline_lanes = [
        {
            "pipeline_lane": str(lane),
            "display_label": content_pipeline_lane_label(str(lane)),
            "display_tone": content_pipeline_lane_tone(str(lane)),
            "count": _safe_int(count),
        }
        for lane, count in sorted(by_content_pipeline_lane.items())
    ]
    return {
        "item_count": _safe_int(summary.get("item_count")),
        "adapter_count": _safe_int(summary.get("adapter_count")),
        "by_outcome": dict(by_outcome),
        "by_content_review_bucket": dict(by_content_review_bucket),
        "by_content_parser": dict(by_content_parser),
        "by_content_pipeline_lane": dict(by_content_pipeline_lane),
        "by_content_importability": dict(by_content_importability),
        "outcomes": outcomes,
        "content_review_buckets": content_review_buckets,
        "content_parsers": content_parsers,
        "content_pipeline_lanes": content_pipeline_lanes,
        "items": review_payload.get("items", []),
    }


def plan_entry_content_status_payload(entry: dict[str, object]) -> dict[str, object]:
    """Return a UI-safe content/import status for one download plan entry."""

    import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
    content_parser = entry.get("content_parser") if isinstance(entry.get("content_parser"), dict) else {}
    import_profile = _content_import_profile_from_entry(entry, import_plan, content_parser)
    status = str(import_plan.get("status") or content_parser.get("import_status") or "").strip()
    review_bucket = str(import_plan.get("review_bucket") or content_parser.get("review_bucket") or "").strip()
    parser_id = str(
        content_parser.get("parser_id")
        or import_plan.get("content_parser")
        or import_plan.get("importer")
        or ""
    ).strip()
    source_format = str(
        content_parser.get("source_format")
        or import_plan.get("source_format")
        or entry.get("source_format")
        or ""
    ).strip()
    reason = str(import_plan.get("reason") or content_parser.get("reason") or "").strip()
    if import_profile:
        source_format = str(import_profile.get("source_format") or source_format).strip()
        status = str(import_profile.get("import_status") or status).strip()
        parser_id = str(import_profile.get("parser_id") or parser_id).strip()
        review_bucket = str(import_profile.get("review_bucket") or review_bucket).strip()
        display_label = str(import_profile.get("display_label") or "").strip()
        display_tone = str(import_profile.get("display_tone") or "").strip()
        if not display_label:
            display_label, display_tone = _legacy_content_display(status, review_bucket)
    elif review_bucket:
        display_label = content_review_bucket_label(review_bucket)
        display_tone = content_review_bucket_tone(review_bucket)
    else:
        display_label, display_tone = _legacy_content_display(status, review_bucket)
    detail_parts = [part for part in (source_format, parser_id) if part]
    summary = " / ".join(detail_parts) if detail_parts else reason
    return {
        "source_format": source_format,
        "import_status": status,
        "parser_id": parser_id,
        "review_bucket": review_bucket,
        "import_profile": import_profile,
        "pipeline_lane": str(import_profile.get("pipeline_lane") or ""),
        "importability": str(import_profile.get("importability") or ""),
        "next_action": str(import_profile.get("next_action") or ""),
        "review_required": bool(import_profile.get("review_required")) if import_profile else bool(review_bucket),
        "supported_importer": str(import_profile.get("supported_importer") or ""),
        "display_label": display_label,
        "display_tone": display_tone,
        "summary": summary,
        "reason": reason,
    }


def adapter_review_content_summary_label(adapter_review_payload: dict[str, object]) -> str:
    """Build a compact content-format review label from adapter-review display data."""

    return str(adapter_review_content_summary_payload(adapter_review_payload)["display_label"])


def adapter_review_content_summary_payload(adapter_review_payload: dict[str, object]) -> dict[str, object]:
    """Return a compact badge payload for content parser review work."""

    buckets = (
        adapter_review_payload.get("content_review_buckets")
        if isinstance(adapter_review_payload.get("content_review_buckets"), list)
        else []
    )
    parts: list[str] = []
    total = 0
    display_tone = "neutral"
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        label = str(bucket.get("display_label") or bucket.get("review_bucket") or "").strip()
        count = _safe_int(bucket.get("count"))
        if label and count:
            parts.append(f"{label} {count}")
            total += count
            tone = str(bucket.get("display_tone") or "review")
            if TONE_SEVERITY.get(tone, 1) > TONE_SEVERITY.get(display_tone, 0):
                display_tone = tone
    display_label = " / ".join(parts)
    pipeline_lanes = (
        adapter_review_payload.get("content_pipeline_lanes")
        if isinstance(adapter_review_payload.get("content_pipeline_lanes"), list)
        else []
    )
    if not display_label:
        lane_parts: list[str] = []
        for lane in pipeline_lanes:
            if not isinstance(lane, dict):
                continue
            label = str(lane.get("display_label") or lane.get("pipeline_lane") or "").strip()
            count = _safe_int(lane.get("count"))
            if label and count:
                lane_parts.append(f"{label} {count}")
                tone = str(lane.get("display_tone") or "review")
                if TONE_SEVERITY.get(tone, 1) > TONE_SEVERITY.get(display_tone, 0):
                    display_tone = tone
        display_label = " / ".join(lane_parts)
    return {
        "display_label": display_label,
        "display_tone": display_tone if display_label else "neutral",
        "count": total,
        "has_review": bool(display_label),
        "buckets": buckets,
        "pipeline_lanes": pipeline_lanes,
    }


def adapter_review_outcome_label(bucket: str) -> str:
    return ADAPTER_REVIEW_OUTCOME_DISPLAY.get(bucket, (bucket or "unknown", "review"))[0]


def adapter_review_outcome_tone(bucket: str) -> str:
    return ADAPTER_REVIEW_OUTCOME_DISPLAY.get(bucket, (bucket or "unknown", "review"))[1]


def content_review_bucket_label(bucket: str) -> str:
    return CONTENT_REVIEW_BUCKET_DISPLAY.get(bucket, (bucket or "unknown", "review"))[0]


def content_review_bucket_tone(bucket: str) -> str:
    return CONTENT_REVIEW_BUCKET_DISPLAY.get(bucket, (bucket or "unknown", "review"))[1]


def content_pipeline_lane_label(lane: str) -> str:
    return CONTENT_PIPELINE_LANE_DISPLAY.get(lane, (lane or "unknown", "review"))[0]


def content_pipeline_lane_tone(lane: str) -> str:
    return CONTENT_PIPELINE_LANE_DISPLAY.get(lane, (lane or "unknown", "review"))[1]


def _legacy_content_display(status: str, review_bucket: str) -> tuple[str, str]:
    if review_bucket:
        return content_review_bucket_label(review_bucket), content_review_bucket_tone(review_bucket)
    return CONTENT_IMPORT_STATUS_DISPLAY.get(status, (status or "未指定", "neutral"))


def _content_import_profile_from_entry(
    entry: dict[str, object],
    import_plan: dict[str, object],
    content_parser: dict[str, object],
) -> dict[str, object]:
    content_detection = entry.get("content_detection") if isinstance(entry.get("content_detection"), dict) else {}
    detection_capability = (
        content_detection.get("capability") if isinstance(content_detection.get("capability"), dict) else {}
    )
    for value in (
        content_parser.get("import_profile"),
        import_plan.get("content_import_profile"),
        content_detection.get("import_profile"),
        detection_capability.get("import_profile"),
    ):
        if isinstance(value, dict):
            return dict(value)
    return {}


def _safe_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


__all__ = [
    "adapter_review_content_summary_label",
    "adapter_review_content_summary_payload",
    "adapter_review_display_payload",
    "adapter_review_outcome_label",
    "adapter_review_outcome_tone",
    "content_pipeline_lane_label",
    "content_pipeline_lane_tone",
    "content_review_bucket_label",
    "content_review_bucket_tone",
    "plan_entry_content_status_payload",
]
