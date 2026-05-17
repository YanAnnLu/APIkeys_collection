from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
CATALOG_DIR = PROJECT_ROOT / "catalog"
CONFIG_DIR = PROJECT_ROOT / "config"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
STATE_DIR = PROJECT_ROOT / "state"
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"


def project_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def catalog_file(name: str) -> Path:
    return first_existing(CATALOG_DIR / name, PROJECT_ROOT / name)


def config_file(name: str) -> Path:
    return first_existing(CONFIG_DIR / name, PROJECT_ROOT / name)


def local_config_file(name: str) -> Path:
    legacy = PROJECT_ROOT / name
    if legacy.exists():
        return legacy
    return CONFIG_DIR / name


def state_file(name: str) -> Path:
    legacy = PROJECT_ROOT / name
    if legacy.exists():
        return legacy
    return STATE_DIR / name
