from __future__ import annotations

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
