from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

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


__all__ = [
    "crawler_asset_bound_form_payload",
    "crawler_asset_card_capabilities",
    "crawler_asset_flow_steps",
    "capability_display_label",
    "bound_field_display_label",
    "bound_field_display_help",
]
