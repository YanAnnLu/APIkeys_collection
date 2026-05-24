from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
CATALOG_DIR = PROJECT_ROOT / "catalog"
CONFIG_DIR = PROJECT_ROOT / "config"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
STATE_DIR = PROJECT_ROOT / "state"
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
LOGS_DIR = STATE_DIR / "logs"
STAGING_DIR = STATE_DIR / "staging"
LOCAL_PRODUCT_DOWNLOADS_DIRNAME = "RuRuKa Asset Launcher"


def project_path(path: str | Path) -> Path:
    # 所有相對路徑都錨定 repo root，避免 CLI/UI 從不同工作目錄啟動時寫散。
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def first_existing(*paths: Path) -> Path:
    # 兼容舊版根目錄檔案；找到舊路徑時先用舊路徑，避免升級後立即找不到資料。
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def catalog_file(name: str) -> Path:
    return first_existing(CATALOG_DIR / name, PROJECT_ROOT / name)


def config_file(name: str) -> Path:
    return first_existing(CONFIG_DIR / name, PROJECT_ROOT / name)


def local_config_file(name: str) -> Path:
    # local config 預期在 config/，但舊根目錄檔案仍可被讀取以支援平滑搬遷。
    legacy = PROJECT_ROOT / name
    if legacy.exists():
        return legacy
    return CONFIG_DIR / name


def state_file(name: str) -> Path:
    # state 檔預設進 ignored state/；舊根目錄 runtime 檔存在時仍優先使用。
    legacy = PROJECT_ROOT / name
    if legacy.exists():
        return legacy
    return STATE_DIR / name


def log_file(name: str) -> Path:
    return LOGS_DIR / name


def user_downloads_dir() -> Path:
    # 一般使用者不一定知道 repo 內的 downloads/；預設指向 OS 慣用 Downloads，CI/開發仍可用參數覆寫。
    candidates = []
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        candidates.append(Path(userprofile) / "Downloads")
    try:
        home = Path.home()
    except RuntimeError:
        # 測試、CI 或受限服務帳號可能沒有可解析的 home；此時退回 repo 內舊 downloads/，避免 CLI parse_args 階段就中斷。
        home = None
    if home is not None:
        candidates.extend((home / "Downloads", home))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DOWNLOADS_DIR


def default_local_downloads_root() -> Path:
    # 下載 payload/manifest 放在專屬子資料夾，避免把大量 .csv/.manifest.json 直接灑在使用者 Downloads 根目錄。
    return user_downloads_dir() / LOCAL_PRODUCT_DOWNLOADS_DIRNAME / "downloads"


def default_local_curated_db_path() -> Path:
    # 第一階段展示格式先固定為 SQLite .db；CSV payload 仍由 download plan 放在 downloads root。
    return user_downloads_dir() / LOCAL_PRODUCT_DOWNLOADS_DIRNAME / "curated_imports.db"
