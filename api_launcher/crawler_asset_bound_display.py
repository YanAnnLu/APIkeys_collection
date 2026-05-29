"""Display helpers for crawler asset capability and bounds forms.

Bounds form labels are part of the UI-neutral contract.  Keeping them here
prevents Tk/Web/Qt from drifting into separate translations for the same field
ids.
"""

from __future__ import annotations

from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundFormField, CrawlerAssetBoundFormSpec
from api_launcher.crawler_asset_capabilities import CrawlerAssetCapability


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


__all__ = [
    "bound_field_display_help",
    "bound_field_display_label",
    "capability_display_label",
    "crawler_asset_bound_field_payload",
    "crawler_asset_bound_form_payload",
    "crawler_asset_bound_group_payload",
]
