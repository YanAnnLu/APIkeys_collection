from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from api_launcher.adapter_review import adapter_review_agent_payload
from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundFormField, CrawlerAssetBoundFormSpec
from api_launcher.crawler_asset_capabilities import BUILD_DOWNLOAD_PLAN, CrawlerAssetCapability
from api_launcher.crawler_assets import CrawlerAsset


CAPABILITY_DISPLAY_LABELS = {
    "fetch_metadata": "抓取元資料",
    "list_datasets": "擷取資料清單",
    "build_download_plan": "建立下載計畫",
}

FIELD_DISPLAY_TEXT = {
    "collection": ("資料集合", "選擇或輸入入口中的 collection、package 或 dataset 名稱。"),
    "time_field": ("時間欄位", "資料集中代表時間的欄位名稱；未來 schema probe 可改成欄位選擇器。"),
    "start_date": ("起始日期", "界域查詢的起始時間。"),
    "end_date": ("結束日期", "界域查詢的結束時間。"),
    "bbox_west": ("西界經度", "界定地理範圍的最小經度。"),
    "bbox_south": ("南界緯度", "界定地理範圍的最小緯度。"),
    "bbox_east": ("東界經度", "界定地理範圍的最大經度。"),
    "bbox_north": ("北界緯度", "界定地理範圍的最大緯度。"),
    "limit": ("資料筆數上限", "控制下載計畫或預覽結果的最大筆數。"),
    "max_results": ("候選數上限", "控制 crawler 回傳的候選資料集數量。"),
    "max_pages": ("頁數上限", "控制 crawler 掃描頁數，避免無界探索。"),
    "search_terms": ("搜尋關鍵字", "用逗號分隔多個搜尋詞。"),
    "format": ("輸出格式", "指定偏好的資料格式；未知格式會留在 adapter review。"),
    "credential_profile": ("憑證設定檔", "需要 API key 或帳號時，由爬蟲資產讀取對應的本機私有設定。"),
}

PLAN_OUTCOME_DISPLAY = {
    "ready_to_download": {
        "display_label": "可開始下載",
        "display_tone": "success",
        "summary": "已建立可直接下載的計畫。",
    },
    "partial_review_required": {
        "display_label": "部分可下載",
        "display_tone": "warning",
        "summary": "部分項目已可下載，仍有項目需要 Adapter 審核。",
    },
    "review_required": {
        "display_label": "待 Adapter 審核",
        "display_tone": "review",
        "summary": "目前沒有可直接下載項目，需要先審核或調整界域。",
    },
    "zero_candidates": {
        "display_label": "零候選",
        "display_tone": "neutral",
        "summary": "本次界域沒有抓到候選資料。",
    },
    "empty_plan": {
        "display_label": "空計畫",
        "display_tone": "neutral",
        "summary": "後端沒有產生可執行的下載計畫。",
    },
    "blocked": {
        "display_label": "已阻擋",
        "display_tone": "danger",
        "summary": "此爬蟲資產目前被設定或狀態擋下。",
    },
}

NEXT_ACTION_DISPLAY_LABELS = {
    "open_downloader_and_start_or_pause_queue": "前往下載器開始或暫停佇列",
    "open_adapter_review_or_adjust_bounds": "開啟 Adapter 審核或調整界域",
    "adjust_bounds_or_refresh_source_listing": "放寬界域或重新抓取清單",
    "review_resolved_download_plan": "檢查後端 resolved plan",
    "select_crawler_asset": "先選擇一個爬蟲資產",
    "enable_before_building_download_plan": "先啟用爬蟲資產",
    "unarchive_before_building_download_plan": "先解除封存",
    "refresh_or_repair_crawler_source_catalog": "重新整理或修復來源設定",
}

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


def crawler_asset_bound_form_payload(spec: CrawlerAssetBoundFormSpec) -> dict[str, object]:
    payload = spec.to_dict()
    payload["fields"] = [crawler_asset_bound_field_payload(field) for field in spec.fields]
    return payload


def crawler_asset_bound_field_payload(field: CrawlerAssetBoundFormField) -> dict[str, object]:
    payload = field.to_dict()
    payload["display_label"] = bound_field_display_label(field)
    payload["display_help"] = bound_field_display_help(field)
    return payload


def capability_display_label(capability: CrawlerAssetCapability) -> str:
    return CAPABILITY_DISPLAY_LABELS.get(capability.capability_id) or capability.label or capability.capability_id


def bound_field_display_label(field: CrawlerAssetBoundFormField) -> str:
    configured = FIELD_DISPLAY_TEXT.get(field.field_id)
    if configured:
        return configured[0]
    return field.label_zh_TW or field.label_en or field.field_id


def bound_field_display_help(field: CrawlerAssetBoundFormField) -> str:
    configured = FIELD_DISPLAY_TEXT.get(field.field_id)
    if configured:
        return configured[1]
    return field.help_zh_TW or field.help_en or ""


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

    bucket = str(getattr(result, "outcome_bucket", "") or "empty_plan")
    direct = _safe_int(getattr(result, "direct_download_count", 0))
    review = _safe_int(getattr(result, "review_required_count", 0))
    blocked_reason = str(getattr(result, "blocked_reason", "") or "")
    next_action = str(getattr(result, "user_next_action", "") or getattr(result, "next_action", "") or "")
    display = PLAN_OUTCOME_DISPLAY.get(bucket, PLAN_OUTCOME_DISPLAY["empty_plan"])
    summary = _plan_outcome_summary(
        bucket,
        default_summary=str(display["summary"]),
        direct=direct,
        review=review,
        added_count=added_count,
        blocked_reason=blocked_reason,
    )
    return {
        "outcome_bucket": bucket,
        "display_label": display["display_label"],
        "display_tone": display["display_tone"],
        "short_label": _plan_outcome_short_label(
            bucket,
            direct=direct,
            review=review,
            added_count=added_count,
            blocked_reason=blocked_reason,
        ),
        "summary": summary,
        "direct_download_count": direct,
        "review_required_count": review,
        "added_count": added_count,
        "blocked": bool(getattr(result, "blocked", False)) or bucket == "blocked",
        "blocked_reason": blocked_reason,
        "next_action": next_action,
        "next_action_label": NEXT_ACTION_DISPLAY_LABELS.get(next_action, next_action),
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
    return {
        "item_count": _safe_int(summary.get("item_count")),
        "adapter_count": _safe_int(summary.get("adapter_count")),
        "by_outcome": dict(by_outcome),
        "by_content_review_bucket": dict(by_content_review_bucket),
        "by_content_parser": dict(by_content_parser),
        "outcomes": outcomes,
        "content_review_buckets": content_review_buckets,
        "content_parsers": content_parsers,
        "items": review_payload.get("items", []),
    }


def plan_entry_content_status_payload(entry: dict[str, object]) -> dict[str, object]:
    """Return a UI-safe content/import status for one download plan entry.

    Download-plan panels should not expose raw values such as
    ``manual_review_required``.  Keep that machine contract in the payload, then
    provide a small display layer that Tk/Web/Qt can share.
    """

    import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
    content_parser = entry.get("content_parser") if isinstance(entry.get("content_parser"), dict) else {}
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
    if review_bucket:
        display_label = content_review_bucket_label(review_bucket)
        display_tone = content_review_bucket_tone(review_bucket)
    else:
        display_label, display_tone = CONTENT_IMPORT_STATUS_DISPLAY.get(status, (status or "未指定", "neutral"))
    detail_parts = [part for part in (source_format, parser_id) if part]
    summary = " / ".join(detail_parts) if detail_parts else reason
    return {
        "source_format": source_format,
        "import_status": status,
        "parser_id": parser_id,
        "review_bucket": review_bucket,
        "display_label": display_label,
        "display_tone": display_tone,
        "summary": summary,
        "reason": reason,
    }


def adapter_review_outcome_label(bucket: str) -> str:
    return ADAPTER_REVIEW_OUTCOME_DISPLAY.get(bucket, (bucket or "unknown", "review"))[0]


def adapter_review_outcome_tone(bucket: str) -> str:
    return ADAPTER_REVIEW_OUTCOME_DISPLAY.get(bucket, (bucket or "unknown", "review"))[1]


def content_review_bucket_label(bucket: str) -> str:
    return CONTENT_REVIEW_BUCKET_DISPLAY.get(bucket, (bucket or "unknown", "review"))[0]


def content_review_bucket_tone(bucket: str) -> str:
    return CONTENT_REVIEW_BUCKET_DISPLAY.get(bucket, (bucket or "unknown", "review"))[1]


def plan_outcome_display_label(bucket: str) -> str:
    display = PLAN_OUTCOME_DISPLAY.get(bucket, PLAN_OUTCOME_DISPLAY["empty_plan"])
    return str(display["display_label"])


def plan_outcome_short_label(bucket: str, *, added_count: int = 0, review_count: int = 0) -> str:
    return _plan_outcome_short_label(
        bucket,
        direct=0,
        review=review_count,
        added_count=added_count,
        blocked_reason="",
    )


def _plan_outcome_summary(
    bucket: str,
    *,
    default_summary: str,
    direct: int,
    review: int,
    added_count: int,
    blocked_reason: str,
) -> str:
    if bucket == "ready_to_download":
        return f"直接下載 {direct} 筆；已加入下載器 {added_count} 筆。"
    if bucket == "partial_review_required":
        return f"已加入下載器 {added_count} 筆；仍有 {review} 筆需要 Adapter 審核。"
    if bucket == "review_required":
        return f"{review} 筆需要 Adapter 審核；目前沒有可直接下載項目。"
    if bucket == "zero_candidates":
        return "本次界域沒有候選資料；請放寬時間、空間或查詢條件。"
    if bucket == "blocked" and blocked_reason:
        return f"被阻擋：{blocked_reason}。"
    return default_summary


def _plan_outcome_short_label(
    bucket: str,
    *,
    direct: int,
    review: int,
    added_count: int,
    blocked_reason: str,
) -> str:
    if bucket == "ready_to_download":
        return f"可下載 {added_count or direct}"
    if bucket == "partial_review_required":
        return f"可下載 {added_count} / 待辦 {review}"
    if bucket == "review_required":
        return f"待 Adapter {review}"
    if bucket == "zero_candidates":
        return "零候選"
    if bucket == "blocked":
        return f"已阻擋 {blocked_reason or 'blocked'}"
    return "需檢查"


def _safe_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


__all__ = [
    "adapter_review_display_payload",
    "adapter_review_outcome_label",
    "adapter_review_outcome_tone",
    "content_review_bucket_label",
    "content_review_bucket_tone",
    "crawler_asset_bound_form_payload",
    "crawler_asset_card_capabilities",
    "crawler_asset_flow_steps",
    "crawler_asset_plan_outcome_payload",
    "plan_entry_content_status_payload",
    "capability_display_label",
    "bound_field_display_label",
    "bound_field_display_help",
    "plan_outcome_display_label",
    "plan_outcome_short_label",
]
