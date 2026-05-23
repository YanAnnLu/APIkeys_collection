"""Tk UI 的靜態設定與偏好讀取 helper。"""

from __future__ import annotations

import APIkeys_collection as core

from api_launcher.paths import state_file


DB_PATH = state_file(core.DB_NAME)
PRODUCT_DISPLAY_NAME = "RuRuKa Asset Launcher"
PRODUCT_SHORT_NAME = "RRKAL"

DOWNLOAD_PLAN_NAME = "APIkeys_collection_download_plan.json"
RESOLVED_DOWNLOAD_PLAN_NAME = "APIkeys_collection_download_plan.resolved.json"
MVP_DEMO_FLOW_NAME = "mvp_demo/flow.json"
YFINANCE_DEMO_PLAN_NAME = "yfinance_demo/plan.json"
YFINANCE_LIVE_PLAN_NAME = "yfinance_live/plan.json"
YFINANCE_STORAGE_REVIEW_NAME = "yfinance_live/storage_review.json"
YFINANCE_STORAGE_HANDOFF_NAME = "yfinance_live/storage_handoff.md"
CURATED_IMPORTS_NAME = "curated_imports.sqlite"
MANUAL_IMPORTS_DIR_NAME = "manual_imports"

DEFAULT_UI_LANGUAGE = "zh-TW"
UI_LANGUAGES = {
    "zh-TW": "繁體中文",
    "en-US": "English",
}

COLORS = {
    "bg": "#141a23",
    "sidebar": "#2a2f39",
    "panel": "#20252f",
    "header": "#3b4654",
    "text": "#e7edf6",
    "muted": "#9ba6b5",
    "accent": "#2da8ff",
    "accent_dark": "#1d5d8d",
    "border": "#4a5362",
}

# 只有這些 manifest 狀態能走 UI 重新排下載；其他狀態需要 adapter / manifest 層人工審核。
DOWNLOAD_REPAIR_ACTION_STATUSES = {"missing", "size_mismatch", "checksum_mismatch", "manifest_error"}

TABLE_COLUMNS = (
    # 欄位定義集中保存 label/比例/寬度上下限，避免 resize 邏輯散在 UI 程式各處。
    ("star", "*", 0.045, 44, 64, "center", False),
    ("install", "計畫", 0.06, 58, 82, "center", False),
    ("name", "資料集 / API 來源", 0.32, 220, 520, "w", True),
    ("category", "分類", 0.22, 150, 360, "w", True),
    ("local", "本地庫", 0.11, 95, 150, "center", False),
    ("download", "下載", 0.13, 110, 180, "center", False),
    ("action", "動作", 0.09, 82, 140, "center", False),
)

LAYOUT = {
    # Tk 沒有 CSS layout；這裡集中存比例與動畫參數，讓螢幕尺寸調整時行為一致。
    "initial_width_ratio": 0.82,
    "initial_height_ratio": 0.78,
    "min_width_ratio": 0.58,
    "min_height_ratio": 0.52,
    "sidebar_ratio": 0.145,
    "sidebar_min": 220,
    "sidebar_max": 320,
    "outer_pad_ratio": 0.018,
    "rowheight_ratio": 0.052,
    "detail_ratio": 0.28,
    "detail_min": 360,
    "detail_max": 560,
    "detail_gap": 18,
    "table_min_with_detail": 620,
    "column_manual_max": 920,
    "detail_animation_steps": 9,
    "detail_animation_delay_ms": 12,
}


def configured_ui_language() -> str:
    """讀取已儲存的 UI 語言，無效值一律回到繁中預設。"""

    # local config 可能由舊版本或人工編輯留下未知語言碼；UI 啟動時要保守 fallback。
    value = str(core.load_integration_config().get("ui_language") or DEFAULT_UI_LANGUAGE)
    return value if value in UI_LANGUAGES else DEFAULT_UI_LANGUAGE
