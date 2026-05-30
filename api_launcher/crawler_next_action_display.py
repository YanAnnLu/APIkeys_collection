"""Display labels for stable backend next_action ids.

The ids remain machine-readable contracts.  This module owns the human labels
so Tk, Web, CLI diagnostics, and future Qt skins do not translate action ids
independently.
"""

from __future__ import annotations


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
    "run_full_crawl_or_export_candidates": "執行完整枚舉或匯出候選資料",
    "preview_payload_before_building_plan": "先預覽界域 payload",
    "click_build_plan_to_call_backend": "建立下載計畫並交給後端判斷",
    "review_plan_outcome": "檢查下載計畫結果",
    "choose_schema_backed_bounds": "使用探測到的欄位定義界域",
    "enable_before_building_download_plan": "先啟用爬蟲資產",
    "unarchive_before_building_download_plan": "先解除封存",
    "rebuild_download_plan": "重新建立下載計畫",
    "rebuild_download_plan_after_profile_change": "資產設定改變，請重新建立下載計畫",
    "rebuild_download_plan_after_source_change": "來源設定改變，請重新建立下載計畫",
    "rebuild_download_plan_after_bounds_change": "界域表單改變，請重新建立下載計畫",
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
    "resolve_source_to_direct_download_entries": "解析來源，產生可下載 resources",
    "resolve_api": "解析 API，產生可下載 resources",
    "unpack_or_transform_downloaded_payload": "解壓或轉換下載內容",
    "configure_credentials_before_download": "先完成憑證設定，再下載",
    "resolve_download_url": "解析實際下載網址",
    "download_then_import_verified_payload": "下載後匯入已驗證內容",
    "resolve_bounded_api_sample_then_download_import": "解析界域樣本後下載 / 匯入",
    "review_payload_format_or_keep_raw_artifact": "審核內容格式或保留原始檔",
    "add_content_parser_or_keep_raw_artifact": "新增內容 Parser 或保留原始檔",
}


def next_action_display_label(action: object) -> str:
    """Return the shared human label for a stable backend next_action id."""

    text = str(action or "").strip()
    return NEXT_ACTION_DISPLAY_LABELS.get(text, text)


def next_action_display_label_or_fallback(action: object, *, fallback: str = "檢查下一步設定") -> str:
    """Return a UI-safe label without leaking unknown snake_case action ids.

    ``next_action_display_label`` intentionally preserves unknown values for
    diagnostics.  User-facing surfaces should call this stricter helper so a new
    backend action id does not appear as raw snake_case text in Tk/Web/Qt.
    """

    text = str(action or "").strip()
    if not text:
        return ""
    label = next_action_display_label(text)
    if label != text:
        return label
    if _looks_like_backend_action_id(text):
        safe_fallback = str(fallback or "").strip()
        return safe_fallback or "檢查下一步設定"
    return label


def _looks_like_backend_action_id(text: str) -> bool:
    """Heuristic for stable backend ids such as ``review_or_upsert_candidates``."""

    return "_" in text and text.lower() == text and all(ch.isalnum() or ch in {"_", "-"} for ch in text)


__all__ = [
    "NEXT_ACTION_DISPLAY_LABELS",
    "next_action_display_label",
    "next_action_display_label_or_fallback",
]
