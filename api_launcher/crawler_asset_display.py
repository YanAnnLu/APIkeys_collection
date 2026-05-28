"""Display-safe crawler asset payload helpers.

The backend owns status interpretation.  Tk, Web Preview, and future Qt should
receive labels, tones, summaries, and next-action strings from this module
instead of translating raw outcome buckets by themselves.  This prevents UI
surfaces from drifting when crawler/download/import behavior changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from api_launcher.adapter_review import adapter_review_agent_payload
from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundFormField, CrawlerAssetBoundFormSpec
from api_launcher.crawler_asset_capabilities import BUILD_DOWNLOAD_PLAN, CrawlerAssetCapability
from api_launcher.crawler_asset_profiles import compact_crawler_asset_plan_passport
from api_launcher.crawler_assets import CrawlerAsset
from api_launcher.crawler_run_records import crawler_run_record_from_result


# Stable backend ids -> human labels.  Raw capability ids remain in payloads for
# tests and agents; these labels are the shared presentation contract.
CAPABILITY_DISPLAY_LABELS = {
    "fetch_metadata": "抓取元資料",
    "list_datasets": "擷取資料清單",
    "build_download_plan": "建立下載計畫",
}

# Field text belongs here rather than in Tk/Web widgets.  The same field id can
# then render consistently in every UI surface.
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

BOUND_GROUP_DISPLAY_TEXT = {
    "AuthBounds": ("憑證設定", "帳號、API key 或 credential profile 只屬於 crawler asset 設定，不屬於資料集本身。"),
    "ColumnBounds": ("欄位界域", "需要先知道資料 schema，才能把欄位選擇轉成可靠的匯入或查詢條件。"),
    "DatasetBounds": ("資料集選擇", "用來指定 collection、package、resource 或 dataset id。"),
    "FormatBounds": ("格式與角色", "用來區分 CSV、JSON、NetCDF、GeoTIFF、ZIP 或 browse/metadata/data 等資產角色。"),
    "LimitBounds": ("擷取上限", "先用小範圍驗證候選、下載與匯入流程，再逐步放大。"),
    "ProviderSpecificBounds": ("來源特規", "這些欄位屬於特定平台或 API 的查詢條件。"),
    "QueryBounds": ("查詢條件", "用於關鍵字、where clause 或 API 查詢式；應保持 bounded 並可審核。"),
    "SpatialBounds": ("空間界域", "用 bbox、站點或座標欄位界定地理範圍。"),
    "TimeBounds": ("時間界域", "用起迄時間與時間欄位界定時間序列範圍。"),
    "VersionBounds": ("版本控制", "可指定精確版本；留空時改用版本上限避免誤選不存在的版本。"),
}

# Outcome buckets are machine contracts.  This table is the UI-neutral display
# layer for those buckets.
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
    "select_seed": "先選擇一筆 seed",
    "probe_schema_then_define_bounds": "先探測資料結構，再定義界域",
    "review_or_upsert_dataset_candidates": "審核或寫入候選資料",
    "review_candidates_or_build_plan": "審核候選或建立下載計畫",
    "preview_payload_before_building_plan": "先預覽界域 payload",
    "click_build_plan_to_call_backend": "建立下載計畫並交給後端判斷",
    "review_plan_outcome": "檢查下載計畫結果",
    "choose_schema_backed_bounds": "使用探測到的欄位定義界域",
    "enable_before_building_download_plan": "先啟用爬蟲資產",
    "unarchive_before_building_download_plan": "先解除封存",
    "enable_before_crawl": "先啟用爬蟲資產，再枚舉 seed",
    "unarchive_before_crawl": "先解除封存，再枚舉 seed",
    "enable_before_downloading_seed": "先啟用爬蟲資產，再下載 seed",
    "unarchive_before_downloading_seed": "先解除封存，再下載 seed",
    "refresh_or_repair_crawler_source_catalog": "重新整理或修復來源設定",
    "refresh_seed_listing_or_select_another_seed": "重新枚舉 seed 或選擇其他 seed",
    "repair_provider_catalog_before_download": "先修復 provider catalog，再下載",
    "download_selected_seed": "下載選取的 seed",
    "adjust_version_selection_for_seed": "調整 seed 版本選擇",
    "run_crawler_asset_download_import": "下載 / 匯入目前爬蟲資產",
    "run_crawler_seed_download_import": "下載 / 匯入選取的 seed",
    "show_next_seed_page": "顯示下一批 seed",
    "seed_page_complete": "已顯示目前 seed 清單",
    "edit_local_credentials_before_live_download": "先完成登入設定，再下載資料",
    "optional_edit_local_credentials": "可選擇補上登入設定",
    "run_adapter_review_or_resolve_adapter_plan_before_downloading": "先處理 Adapter 審核或解析計畫，再下載",
    "inspect_manifest": "檢查 manifest 與最近事件紀錄",
    "inspect_event_logs_or_ui_callback": "檢查事件紀錄或 UI 進度回報",
    "run_dataset_discovery_handler_smoke_json_if_summary_fails": "摘要失敗時，執行 handler smoke JSON 診斷",
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


@dataclass(frozen=True)
class DisplayProfile:
    """UI-neutral display contract for one backend status.

    This keeps label/tone/next-action decisions in the backend so Tk, Web, and
    future Qt surfaces can render the same state without reimplementing business
    branching.
    """

    profile_id: str
    display_label: str
    display_tone: str = "neutral"
    short_label: str = ""
    summary: str = ""
    next_action: str = ""
    next_action_label: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "profile_id": self.profile_id,
            "display_label": self.display_label,
            "display_tone": self.display_tone,
            "short_label": self.short_label,
            "summary": self.summary,
            "next_action": self.next_action,
            "next_action_label": self.next_action_label,
        }


@dataclass(frozen=True)
class SeedEnumerationDisplayProfile:
    """Shared UI text contract for crawler seed enumeration outcomes.

    The crawler asset service decides which status applies.  This profile owns
    the label, tone, default next action, and confidence text so Tk/Web/Qt do
    not each recreate the same branching table.
    """

    status: str
    display_tone: str
    label_template: str
    help: str
    default_next_action: str
    limited_by_max_results: bool
    completion_confidence: str

    def payload(
        self,
        *,
        candidate_count: int,
        max_results: int,
        remote_pagination: dict[str, object],
        warning_count: int = 0,
        next_action: str = "",
        completion_confidence: str = "",
    ) -> dict[str, object]:
        label = self.label_template.format(
            candidate_count=candidate_count,
            max_results=max_results,
            warning_count=warning_count,
        )
        return {
            "status": self.status,
            "display_tone": self.display_tone,
            "label": label,
            "help": self.help,
            "next_action": next_action or self.default_next_action,
            "limited_by_max_results": self.limited_by_max_results,
            "candidate_count": candidate_count,
            "max_results": max_results,
            "remote_pagination": remote_pagination,
            "completion_confidence": completion_confidence or self.completion_confidence,
        }


SEED_ENUMERATION_DISPLAY_PROFILES = {
    "blocked": SeedEnumerationDisplayProfile(
        status="blocked",
        display_tone="warning",
        label_template="需要登入或啟用後才能枚舉 seed",
        help="完成登入設定、解除封存或啟用入口後再重新枚舉。",
        default_next_action="",
        limited_by_max_results=False,
        completion_confidence="blocked",
    ),
    "error": SeedEnumerationDisplayProfile(
        status="error",
        display_tone="danger",
        label_template="seed 枚舉發生錯誤",
        help="請查看 crawler audit 或事件紀錄中的錯誤來源。",
        default_next_action="inspect_crawler_error",
        limited_by_max_results=False,
        completion_confidence="error",
    ),
    "empty": SeedEnumerationDisplayProfile(
        status="empty",
        display_tone="warning",
        label_template="尚未找到 seed",
        help="可調整界域、檢查入口 URL、登入狀態或 crawler parser。",
        default_next_action="adjust_bounds_or_refresh_source_listing",
        limited_by_max_results=False,
        completion_confidence="zero_candidates",
    ),
    "local_limit_reached": SeedEnumerationDisplayProfile(
        status="local_limit_reached",
        display_tone="warning",
        label_template="已枚舉前 {candidate_count} 筆 seed",
        help="結果已達本機安全上限，遠端可能還有更多 seed；可縮小界域或提高枚舉上限。",
        default_next_action="narrow_bounds_or_raise_seed_limit",
        limited_by_max_results=True,
        completion_confidence="local_limit_only",
    ),
    "warning": SeedEnumerationDisplayProfile(
        status="warning",
        display_tone="warning",
        label_template="已枚舉 {candidate_count} 筆 seed，但有 {warning_count} 個警告",
        help="候選已寫入本機 catalog；建議先查看 crawler audit，再建立下載計畫。",
        default_next_action="inspect_source_audit_results_before_upsert_or_promotion",
        limited_by_max_results=False,
        completion_confidence="warning_with_unknown_remote_completion",
    ),
    "within_current_limits": SeedEnumerationDisplayProfile(
        status="within_current_limits",
        display_tone="success",
        label_template="已枚舉 {candidate_count} 筆 seed",
        help="結果低於本機枚舉上限；若來源支援遠端分頁，完整性仍以 crawler audit 為準。",
        default_next_action="review_seed_list_or_build_download_plan",
        limited_by_max_results=False,
        completion_confidence="within_current_local_limits",
    ),
    "bounded_sample": SeedEnumerationDisplayProfile(
        status="bounded_sample",
        display_tone="info",
        label_template="已取得 {candidate_count} 筆 seed 樣本",
        help="這是 bounded/sample 模式；若要完整列入口 seed，請重新枚舉 seed。",
        default_next_action="rerun_complete_seed_enumeration",
        limited_by_max_results=False,
        completion_confidence="bounded_sample",
    ),
}


def seed_enumeration_display_payload(
    status: str,
    *,
    candidate_count: int,
    max_results: int,
    remote_pagination: dict[str, object],
    warning_count: int = 0,
    next_action: str = "",
    completion_confidence: str = "",
) -> dict[str, object]:
    profile = SEED_ENUMERATION_DISPLAY_PROFILES[status]
    return profile.payload(
        candidate_count=candidate_count,
        max_results=max_results,
        remote_pagination=remote_pagination,
        warning_count=warning_count,
        next_action=next_action,
        completion_confidence=completion_confidence,
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


def crawler_asset_bound_form_payload(spec: CrawlerAssetBoundFormSpec) -> dict[str, object]:
    """Decorate a form spec with shared display labels and group help text."""

    payload = spec.to_dict()
    payload["fields"] = [crawler_asset_bound_field_payload(field) for field in spec.fields]
    payload["group_display"] = [crawler_asset_bound_group_payload(group) for group in spec.groups]
    return payload


def crawler_asset_bound_field_payload(field: CrawlerAssetBoundFormField) -> dict[str, object]:
    payload = field.to_dict()
    payload["display_label"] = bound_field_display_label(field)
    payload["display_help"] = bound_field_display_help(field)
    return payload


def crawler_asset_bound_group_payload(group: str) -> dict[str, str]:
    label, help_text = BOUND_GROUP_DISPLAY_TEXT.get(group, (group, ""))
    return {
        "group": group,
        "display_label": label,
        "display_help": help_text,
    }


def capability_display_label(capability: CrawlerAssetCapability) -> str:
    return CAPABILITY_DISPLAY_LABELS.get(capability.capability_id) or capability.label or capability.capability_id


def next_action_display_label(action: object) -> str:
    """Return the shared human label for a stable backend next_action id."""

    text = str(action or "").strip()
    return NEXT_ACTION_DISPLAY_LABELS.get(text, text)


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
        or NEXT_ACTION_DISPLAY_LABELS.get(next_action, next_action)
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
    display = PLAN_OUTCOME_DISPLAY.get(bucket, PLAN_OUTCOME_DISPLAY["empty_plan"])
    short_label = str(context.get("outcome_label") or "").strip() or _plan_outcome_short_label(
        bucket,
        direct=direct,
        review=review,
        added_count=added_count,
        blocked_reason=blocked_reason,
    )
    content_review = _content_review_payload_from_event_context(context)
    return {
        "outcome_bucket": bucket,
        "display_label": display["display_label"],
        "display_tone": display["display_tone"],
        "short_label": short_label,
        "summary": _plan_outcome_summary(
            bucket,
            default_summary=str(display["summary"]),
            direct=direct,
            review=review,
            added_count=added_count,
            blocked_reason=blocked_reason,
        ),
        "direct_download_count": direct,
        "review_required_count": review,
        "added_count": added_count,
        "blocked": bucket == "blocked",
        "blocked_reason": blocked_reason,
        "next_action": next_action,
        "next_action_label": NEXT_ACTION_DISPLAY_LABELS.get(next_action, next_action),
        "content_review": content_review,
        "content_review_label": content_review["display_label"],
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
    """Return a UI-safe content/import status for one download plan entry.

    Download-plan panels should not expose raw values such as
    ``manual_review_required``.  Keep that machine contract in the payload, then
    provide a small display layer that Tk/Web/Qt can share.
    """

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


def adapter_review_content_summary_payload(adapter_review_payload: dict[str, object]) -> dict[str, object]:
    """Return a compact badge payload for content parser review work.

    The raw adapter-review payload keeps the full bucket list. This helper gives
    UI layers one stable badge shape so Tk/Web/Qt do not need to reimplement
    count aggregation or warning tone selection.
    """

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
        "next_action_label": NEXT_ACTION_DISPLAY_LABELS[next_action],
        "errors": list(callback_errors),
    }


def plan_outcome_display_label(bucket: str) -> str:
    return plan_outcome_display_profile(bucket).display_label


def plan_outcome_short_label(bucket: str, *, added_count: int = 0, review_count: int = 0) -> str:
    return plan_outcome_display_profile(bucket, review=review_count, added_count=added_count).short_label


def plan_outcome_display_profile(
    bucket: str,
    *,
    direct: int = 0,
    review: int = 0,
    added_count: int = 0,
    blocked_reason: str = "",
    next_action: str = "",
) -> DisplayProfile:
    display = PLAN_OUTCOME_DISPLAY.get(bucket, PLAN_OUTCOME_DISPLAY["empty_plan"])
    summary = _plan_outcome_summary(
        bucket,
        default_summary=str(display["summary"]),
        direct=direct,
        review=review,
        added_count=added_count,
        blocked_reason=blocked_reason,
    )
    return DisplayProfile(
        profile_id=bucket,
        display_label=str(display["display_label"]),
        display_tone=str(display["display_tone"]),
        short_label=_plan_outcome_short_label(
            bucket,
            direct=direct,
            review=review,
            added_count=added_count,
            blocked_reason=blocked_reason,
        ),
        summary=summary,
        next_action=next_action,
        next_action_label=NEXT_ACTION_DISPLAY_LABELS.get(next_action, next_action),
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
