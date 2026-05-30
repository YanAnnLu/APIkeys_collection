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
}


def next_action_display_label(action: object) -> str:
    """Return the shared human label for a stable backend next_action id."""

    text = str(action or "").strip()
    return NEXT_ACTION_DISPLAY_LABELS.get(text, text)


__all__ = [
    "NEXT_ACTION_DISPLAY_LABELS",
    "next_action_display_label",
]
