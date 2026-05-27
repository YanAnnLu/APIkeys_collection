from __future__ import annotations

import re
import sys
from collections.abc import Mapping


WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def platform_name() -> str:
    # 避免 platform.system() 在部分 Windows/雲端碟環境卡住；這裡只需要粗略 OS 名稱。
    if sys.platform.startswith("win"):
        return "Windows"
    if sys.platform == "darwin":
        return "Darwin"
    if sys.platform.startswith("linux"):
        return "Linux"
    return sys.platform or "unknown"


def is_windows_absolute_path(value: str) -> bool:
    raw = value.strip()
    return bool(WINDOWS_ABSOLUTE_RE.match(raw)) or raw.startswith("\\\\")


def is_posix_absolute_path(value: str) -> bool:
    return value.strip().startswith("/")


def is_foreign_platform_path(raw_path: str, system: str | None = None) -> bool:
    # 先辨識外平台路徑，避免 macOS/Linux 把 Windows 磁碟路徑當相對路徑處理。
    value = raw_path.strip()
    if not value:
        return False
    current = system or platform_name()
    if current != "Windows" and is_windows_absolute_path(value):
        return True
    if current == "Windows" and is_posix_absolute_path(value):
        return True
    return False


def normalize_path_for_platform(raw_path: str, system: str | None = None) -> str:
    # 外平台路徑回空字串，讓啟動檢查警告而不是讓 pathlib 解析成錯誤相對路徑。
    value = raw_path.strip()
    if not value or is_foreign_platform_path(value, system):
        return ""
    current = system or platform_name()
    if current == "Windows":
        return value.replace("/", "\\") if is_windows_absolute_path(value) else value
    return value.replace("\\", "/")


def platform_config_path(
    item: Mapping[str, object],
    key: str,
    system: str | None = None,
) -> str:
    # *_by_platform 優先於 generic key，讓同一 config 可以安全跨 Windows/macOS/Linux。
    current = system or platform_name()
    by_platform = item.get(f"{key}_by_platform") or {}
    if isinstance(by_platform, Mapping) and current in by_platform:
        return normalize_path_for_platform(str(by_platform.get(current) or ""), current)
    return normalize_path_for_platform(str(item.get(key) or ""), current)
